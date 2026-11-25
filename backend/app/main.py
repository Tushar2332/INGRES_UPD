"""
main.py — INGRES AI Chatbot API (Review 2 — Verified Groundwater Assistant)

Request pipeline:
  User Query
    → Query Parser (scope guard, intent, locations)
    → Scope Guard (forecast / unknown location / unsupported metric)
    → Data Retriever
    → Answer Builder (CGWB classification, assessment year, source)
    → Number Verifier
    → Verified Response Card

New endpoints:
  POST /whatif          — What-If simulation
  GET  /evaluate        — Benchmark evaluation (50 test questions)
  GET  /cgwb/{state}    — CGWB category distribution for a state
  GET  /assessment_year — Dataset assessment year
"""

from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any

from . import models, schemas, crud, data_processor
from .database import engine, get_db
from .translation import translator
from .data_processor import load_ingres_data_to_db
from .parser import parse_query, build_scope_refusal, normalize_location, LOCATION_ALIASES
from .verifier import verify_response
from .whatif import simulate_whatif, build_whatif_response, classify_cgwb
from . import chat_advisor
from .diagnostics.engine import run_diagnostic, run_multi_scenario_whatif
from .diagnostics.schemas import (
    DiagnosticRequest,
    DiagnosticResponse,
    MultiScenarioRequest,
    MultiScenarioResponse,
)
from . import evaluate as eval_module

import logging
import httpx
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="INGRES Chatbot API", version="4.0 (Review 2)")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rasa configuration
RASA_SERVER_URL = os.environ.get("RASA_SERVER_URL", "http://localhost:5005")
USE_RASA = os.environ.get("USE_RASA", "false").lower() == "true"

# Data confidence tag
DATA_CONFIDENCE = "Latest Available Assessment"

# Bounded server-side conversation context per session_id (clears oldest if > 500 sessions)
_SESSION_CONTEXT: Dict[str, Dict[str, Any]] = {}


# ─── Startup ─────────────────────────────────────────────────────────────────

@app.on_event("startup")
async def startup_event():
    try:
        xlsx_path = os.path.join(os.path.dirname(__file__), "..", "ingres-data.xlsx")
        xlsx_path = os.path.abspath(xlsx_path)
        count = load_ingres_data_to_db(xlsx_path)
        logger.info(
            f"✓ Loaded {count} records from INGRES dataset "
            f"(year={data_processor.ASSESSMENT_YEAR})"
        )
    except Exception as exc:
        logger.error(f"✗ Error loading data: {exc}")

    global USE_RASA
    if USE_RASA:
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                r = await client.get(f"{RASA_SERVER_URL}/status")
                if r.status_code == 200:
                    logger.info("✓ Rasa server available")
                else:
                    USE_RASA = False
        except Exception:
            logger.warning("⚠ Rasa not available — using pattern matching")
            USE_RASA = False


# ─── Helpers ─────────────────────────────────────────────────────────────────

def normalize_location_name(name: str) -> set:
    """Generate spelling/alias variations for a DB district name without clobbering siblings."""
    name_lower = name.lower().strip()
    variations = {name_lower}
    exact_district_aliases = {
        'bengaluru (urban)': ['bengaluru (urban)', 'bengaluru urban', 'bangalore urban', 'bangalore', 'bengaluru'],
        'bengaluru (rural)': ['bengaluru (rural)', 'bengaluru rural', 'bangalore rural'],
        'bengaluru south':   ['bengaluru south', 'bangalore south'],
        'mysuru':            ['mysuru', 'mysore', 'maisuru'],
        'mumbai':            ['mumbai', 'bombay'],
        'mumbai sub':        ['mumbai sub', 'mumbai suburban'],
        'chennai':           ['chennai', 'madras'],
        'kolkatta':          ['kolkatta', 'kolkata', 'calcutta'],
        'thiruvananthapuram': ['thiruvananthapuram', 'trivandrum'],
        'ernakulam':         ['ernakulam', 'cochin', 'kochi'],
        'kozhikkode':        ['kozhikkode', 'kozhikode', 'calicut'],
        'kasargod':          ['kasargod', 'kasaragod'],
        'vadodara':          ['vadodara', 'baroda'],
        'pune':              ['pune', 'poona'],
        'visakhapatnam':     ['visakhapatnam', 'vizag', 'visakha'],
        'new delhi':         ['new delhi', 'dilli'],
        'kalburgi':          ['kalburgi', 'kalaburagi', 'gulbarga'],
        'belagavi':          ['belagavi', 'belgaum'],
        'ballari':           ['ballari', 'bellary'],
        'vijayapura':        ['vijayapura', 'bijapur'],
        'shivamogga':        ['shivamogga', 'shimoga'],
        'tumakuru':          ['tumakuru', 'tumkur'],
        'chikkamagaluru':    ['chikkamagaluru', 'chikmagalur'],
        'chikkaballapura':   ['chikkaballapura', 'chikkaballapur'],
        'chamarajanagara':   ['chamarajanagara', 'chamarajanagar'],
        'kolara':            ['kolara', 'kolar'],
        'dharwad':           ['dharwad', 'hubli', 'hubballi'],
        'dakshina kannada':  ['dakshina kannada', 'mangalore', 'mangaluru'],
        'haora':             ['haora', 'howrah'],
        'hugli':             ['hugli', 'hooghly'],
        'darjiling':         ['darjiling', 'darjeeling'],
        'koch bihar':        ['koch bihar', 'cooch behar'],
        'kanniyakumari':     ['kanniyakumari', 'kanyakumari'],
        'tiruchirappalli':   ['tiruchirappalli', 'trichy'],
    }
    if name_lower in exact_district_aliases:
        variations.update(exact_district_aliases[name_lower])
    return variations


async def get_rasa_prediction(text: str) -> Optional[Dict[str, Any]]:
    """Get intent and entities from Rasa (if enabled)."""
    if not USE_RASA:
        return None
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            r = await client.post(
                f"{RASA_SERVER_URL}/model/parse",
                json={"text": text}
            )
            if r.status_code == 200:
                return r.json()
    except Exception as exc:
        logger.warning(f"Rasa call failed: {exc}")
    return None


def _build_district_map(all_data) -> Dict:
    """Build {dist_key: (dist_val, state_val)} for location matching."""
    dm = {}
    for d in all_data:
        if d.district:
            for variant in normalize_location_name(d.district):
                dm[variant] = (d.district, d.state)
    return dm


def _format_records(data_results, include_all: bool = False) -> List[dict]:
    """Serialise ORM records to dicts with CGWB category, preserving valid 0.0 values."""
    out = []
    limit = 50 if include_all else 15
    year_str = str(data_processor.ASSESSMENT_YEAR)
    source_str = data_processor.DATA_SOURCE
    for d in data_results[:limit]:
        stage = d.stage_of_gw_extraction
        cat = classify_cgwb(stage) if stage is not None else None
        out.append({
            "state":            d.state,
            "district":         d.district,
            "rainfall":         round(d.rainfall_mm, 2)                    if d.rainfall_mm is not None                    else None,
            "extraction_stage": round(stage, 2)                            if stage is not None                            else None,
            "gw_recharge":      round(d.ground_water_recharge, 2)          if d.ground_water_recharge is not None          else None,
            "net_availability": round(d.net_gw_availability, 2)            if d.net_gw_availability is not None            else None,
            "gw_extraction":    round(d.gw_extraction, 2)                  if d.gw_extraction is not None                  else None,
            "annual_extractable": round(d.annual_extractable_gw_resource, 2)
                                   if d.annual_extractable_gw_resource is not None else None,
            "cgwb_category":    cat['category']  if cat else None,
            "cgwb_color":       cat['color']     if cat else None,
            "cgwb_emoji":       cat['emoji']     if cat else None,
            "assessment_year":  year_str,
            "data_source":      source_str,
        })
    return out


def _pick_state_cgwb(stats: Dict) -> Optional[Dict]:
    """Return CGWB classification for the state average extraction stage."""
    avg_stage = stats.get('avg_extraction_stage')
    if avg_stage is None:
        return None
    return classify_cgwb(avg_stage)


# ─── Chat Endpoint ────────────────────────────────────────────────────────────

@app.post("/chat", response_model=schemas.ChatResponse)
async def chat(message: schemas.ChatMessage, db: Session = Depends(get_db)):
    try:
        user_message  = message.message.strip()
        user_language = message.language

        logger.info(f"{'=' * 60}")
        logger.info(f"Query: '{user_message}' | Language: '{user_language}'")

        # ── 1. Language detection + translation to English ──────────────────
        if user_language in ("auto", ""):
            user_language = translator.detect_language(user_message)
        english_message = user_message.lower()
        if user_language != 'en':
            try:
                english_message = translator.translate_text(user_message, 'en', user_language).lower()
                logger.info(f"Translated: '{english_message}'")
            except Exception as exc:
                logger.error(f"Translation error: {exc}")
                english_message = user_message.lower()

        # ── 2. Build lookup maps ─────────────────────────────────────────────
        states    = crud.get_all_states(db)
        all_data  = db.query(models.GroundwaterData).all()
        dist_map  = _build_district_map(all_data)
        state_map = {s.lower(): s for d in all_data if d.state for s in [d.state]}

        assessment_year_str = str(data_processor.ASSESSMENT_YEAR)
        data_source_str     = data_processor.DATA_SOURCE

        # ── 2b. Resolve previous conversation context ────────────────────────
        prev_context: Dict[str, Any] = {}
        if message.session_id and message.session_id in _SESSION_CONTEXT:
            prev_context = dict(_SESSION_CONTEXT[message.session_id])
        if message.context:
            prev_context = {**prev_context, **message.context}

        # ── 3. Parse query (scope guard, intent, locations) ──────────────────
        search_text = f"{user_message.lower()} {english_message}"
        parsed = parse_query(
            search_text,
            states,
            dist_map,
            data_processor.ASSESSMENT_YEAR,
            original_text=user_message,
        )

        logger.info(f"Parsed: intent={parsed['intent']}, in_scope={parsed['is_in_scope']}, "
                    f"locations={parsed['locations']}, crop={parsed.get('crop')}, uses_ctx={parsed.get('uses_context')}")

        # ── 4. Scope Guard — handle out-of-scope queries first ───────────────
        if not parsed['is_in_scope']:
            reason = parsed['out_of_scope_reason']

            # For forecast: try to include latest actual value
            latest_val  = None
            latest_metric = ''
            locs = parsed['locations']

            if reason == 'forecast' and (locs['districts'] or locs['states']):
                try:
                    loc = locs['districts'][0] if locs['districts'] else locs['states'][0]
                    is_dist = bool(locs['districts'])
                    recs = (crud.get_data_by_district(db, loc) if is_dist
                            else crud.get_data_by_state(db, loc))
                    if recs:
                        # Try to infer metric
                        if any(w in search_text for w in ['rain', 'rainfall', 'वर्षा', 'barish']):
                            latest_val = recs[0].rainfall_mm
                            latest_metric = 'rainfall (mm)'
                        elif any(w in search_text for w in ['extraction', 'stage']):
                            latest_val = recs[0].stage_of_gw_extraction
                            latest_metric = 'extraction stage (%)'
                        else:
                            latest_val = recs[0].rainfall_mm
                            latest_metric = 'rainfall (mm)'
                except Exception:
                    pass

            refusal_msg = build_scope_refusal(
                reason=reason,
                location=(parsed.get('unknown_location_candidate') or user_message) if reason == 'unknown_location' else '',
                latest_year=assessment_year_str,
                latest_value=latest_val,
                metric=latest_metric,
            )

            if user_language != 'en':
                try:
                    refusal_msg = translator.translate_text(refusal_msg, user_language, 'en')
                except Exception:
                    pass

            return schemas.ChatResponse(
                response=refusal_msg,
                context=prev_context or None,
                scope_status='out_of_scope',
                out_of_scope_reason=reason,
                assessment_year=assessment_year_str,
                data_source=data_source_str,
                data_confidence=DATA_CONFIDENCE,
                verified=True,       # refusals are inherently verified
                verification_issues=[],
            )

        # ── 5. Handle year unavailable ───────────────────────────────────────
        if not parsed['year_available'] and parsed['year_requested']:
            yr = parsed['year_requested']
            refusal_msg = build_scope_refusal(
                reason='year_unavailable',
                year=yr,
                latest_year=assessment_year_str,
            )
            if user_language != 'en':
                try:
                    refusal_msg = translator.translate_text(refusal_msg, user_language, 'en')
                except Exception:
                    pass
            return schemas.ChatResponse(
                response=refusal_msg,
                scope_status='out_of_scope',
                out_of_scope_reason='year_unavailable',
                assessment_year=assessment_year_str,
                data_source=data_source_str,
                data_confidence=DATA_CONFIDENCE,
                verified=True,
                verification_issues=[],
            )

        # ── 6. Rasa (optional) ───────────────────────────────────────────────
        rasa_data     = await get_rasa_prediction(english_message)
        rasa_intent   = None
        rasa_confidence = 0.0
        rasa_entities = []
        if rasa_data:
            rasa_intent     = rasa_data.get('intent', {}).get('name')
            rasa_confidence = rasa_data.get('intent', {}).get('confidence', 0.0)
            rasa_entities   = rasa_data.get('entities', [])

        # Merge Rasa entities into locations
        locations = dict(parsed['locations'])  # copy
        for entity in rasa_entities:
            ev   = entity.get('value', '').lower()
            etype = entity.get('entity', '')
            if etype in ('state', 'location'):
                for s in states:
                    if s.lower() in ev or ev in s.lower():
                        if s not in locations['states']:
                            locations['states'].append(s)
            if etype in ('district', 'location'):
                for dk, (dv, sv) in dist_map.items():
                    if dk in ev or ev in dk:
                        if dv not in locations['districts']:
                            locations['districts'].append(dv)

        # ── 7. Use best available intent + resolve context ───────────────────
        final_intent = parsed['intent']
        if rasa_intent and rasa_confidence > 0.6:
            final_intent = rasa_intent

        crop_name = parsed.get('crop')
        explicit_location_found = bool(locations['districts'] or locations['states'])
        resolved_from_context = False
        pending_clarification: Optional[Dict[str, Any]] = None

        # If bot just asked for a location for a pending clarification and user supplied one
        prev_pending = prev_context.get('pending_clarification')
        if explicit_location_found and prev_pending and final_intent == 'ask_groundwater' and not crop_name:
            final_intent = prev_pending.get('intent', final_intent)
            crop_name = prev_pending.get('crop')

        # Resolve location from context on follow-up references or contextual advisory intents
        if not explicit_location_found:
            should_use_context = parsed.get('uses_context') or final_intent in (
                'ask_crop_water_requirements',
                'ask_irrigation_impact',
                'ask_sustainability',
                'ask_trends_causes',
            )
            if should_use_context and (prev_context.get('last_district') or prev_context.get('last_state')):
                if prev_context.get('last_district'):
                    locations['districts'] = [prev_context['last_district']]
                if prev_context.get('last_state'):
                    locations['states'] = [prev_context['last_state']]
                resolved_from_context = True

        logger.info(
            f"Intent: {final_intent} | Locations: {locations} | "
            f"Crop: {crop_name} | FromCtx: {resolved_from_context}"
        )

        # ── 8. Data retrieval + answer building ──────────────────────────────
        bot_response  = ""
        data_results  = []
        suggestions   = []
        chart_data    = None
        cgwb_cat_info = None
        extra_allowed: List[float] = []

        # Helper to resolve single district record or state stats for advisory intents
        def _resolve_advisory_target():
            d_rec = None
            s_name = None
            s_stats = None
            if locations['districts']:
                matched_dist = locations['districts'][0]
                recs = crud.get_data_by_district(db, matched_dist)
                if recs and locations['states']:
                    filtered = [r for r in recs if r.state in locations['states']]
                    if filtered:
                        recs = filtered
                if recs:
                    d_rec = recs[0]
                    s_name = d_rec.state
            elif locations['states']:
                s_name = locations['states'][0]
                s_stats = crud.get_statistics(db, s_name)
            return d_rec, s_name, s_stats

        # ── GREET ──
        if final_intent == 'greet':
            bot_response = (
                "👋 Hello! I'm your **INGRES AI Assistant** — your verified groundwater & irrigation guide for India.\n\n"
                "I can help you with:\n"
                "- 🌧️ Rainfall, recharge, extraction stages & CGWB categories\n"
                "- 🌱 Crop water suitability & lower-water crop guidance\n"
                "- 🚿 Irrigation pressure & groundwater sustainability\n"
                "- 🔬 What-If & Diagnostic analysis\n\n"
                f"All groundwater data is from the INGRES/CGWB assessment ({assessment_year_str})."
            )
            suggestions = ['What is the groundwater status of Mysuru?', 'Karnataka groundwater', 'Which crops require less water?', 'Show all states']

        # ── AGRICULTURAL CROP SUITABILITY ──
        elif final_intent == 'ask_agricultural_suitability':
            d_rec, s_name, s_stats = _resolve_advisory_target()
            if d_rec:
                data_results = [d_rec]
            adv = chat_advisor.build_agricultural_suitability_response(
                crop=crop_name,
                district_record=d_rec,
                state_name=s_name,
                state_stats=s_stats,
            )
            bot_response = adv['response']
            suggestions = adv['suggestions']
            extra_allowed.extend(adv['extra_allowed'])
            cgwb_cat_info = adv['cgwb_cat']
            pending_clarification = adv.get('pending_clarification')

        # ── CROP WATER REQUIREMENTS ──
        elif final_intent == 'ask_crop_water_requirements':
            d_rec, _, _ = _resolve_advisory_target()
            if d_rec:
                data_results = [d_rec]
            adv = chat_advisor.build_crop_water_requirements_response(
                crop=crop_name,
                district_record=d_rec,
            )
            bot_response = adv['response']
            suggestions = adv['suggestions']
            extra_allowed.extend(adv['extra_allowed'])
            cgwb_cat_info = adv['cgwb_cat']

        # ── IRRIGATION IMPACT ──
        elif final_intent == 'ask_irrigation_impact':
            d_rec, s_name, s_stats = _resolve_advisory_target()
            if d_rec:
                data_results = [d_rec]
            adv = chat_advisor.build_irrigation_impact_response(
                district_record=d_rec,
                state_name=s_name,
                state_stats=s_stats,
            )
            bot_response = adv['response']
            suggestions = adv['suggestions']
            extra_allowed.extend(adv['extra_allowed'])
            cgwb_cat_info = adv['cgwb_cat']

        # ── GROUNDWATER SUSTAINABILITY ──
        elif final_intent == 'ask_sustainability':
            d_rec, s_name, s_stats = _resolve_advisory_target()
            if d_rec:
                data_results = [d_rec]
            adv = chat_advisor.build_sustainability_response(
                district_record=d_rec,
                state_name=s_name,
                state_stats=s_stats,
                crop=crop_name,
            )
            bot_response = adv['response']
            suggestions = adv['suggestions']
            extra_allowed.extend(adv['extra_allowed'])
            cgwb_cat_info = adv['cgwb_cat']
            pending_clarification = adv.get('pending_clarification')

        # ── TRENDS & CAUSES ──
        elif final_intent == 'ask_trends_causes':
            d_rec, s_name, s_stats = _resolve_advisory_target()
            if d_rec:
                data_results = [d_rec]
            adv = chat_advisor.build_trends_causes_response(
                district_record=d_rec,
                state_name=s_name,
                state_stats=s_stats,
            )
            bot_response = adv['response']
            suggestions = adv['suggestions']
            extra_allowed.extend(adv['extra_allowed'])
            cgwb_cat_info = adv['cgwb_cat']
            pending_clarification = adv.get('pending_clarification')

        # ── GENERAL GROUNDWATER GUIDE ──
        elif final_intent == 'ask_general_groundwater':
            adv = chat_advisor.build_general_groundwater_response(assessment_year_str)
            bot_response = adv['response']
            suggestions = adv['suggestions']
            extra_allowed.extend(adv['extra_allowed'])
            cgwb_cat_info = adv['cgwb_cat']

        # ── STATE LIST ──
        elif final_intent == 'ask_state_list':
            bot_response = f"I have groundwater data for **{len(states)} states** across India."
            suggestions  = sorted(states[:20])

        # ── WHAT-IF ──
        elif final_intent == 'ask_whatif':
            if locations['districts']:
                loc_name = locations['districts'][0]
                recs = crud.get_data_by_district(db, loc_name)
                if recs and locations['states']:
                    filtered = [r for r in recs if r.state in locations['states']]
                    if filtered:
                        recs = filtered
                if recs:
                    r = recs[0]
                    if (
                        r.gw_extraction is not None
                        and r.annual_extractable_gw_resource is not None
                        and r.annual_extractable_gw_resource > 0
                    ):
                        stage_txt = (
                            f"{r.stage_of_gw_extraction:.2f}%"
                            if r.stage_of_gw_extraction is not None
                            else "N/A"
                        )
                        bot_response = (
                            f"I found groundwater data for **{r.district}**, {r.state}.\n\n"
                            f"📊 Current Extraction: **{r.gw_extraction:.2f} ham**\n"
                            f"📐 Current Stage: **{stage_txt}**\n"
                            f"🏗️ Annual Extractable Resource: **{r.annual_extractable_gw_resource:.2f} ham**\n\n"
                            "To run a What-If simulation, please use the **🔬 What-If Analysis** tab "
                            "in the navigation, or specify a percentage change:\n"
                            "*e.g., 'What if we reduce extraction by 20% in Mysuru?'*"
                        )
                        data_results = [r]
                        cgwb_cat_info = classify_cgwb(r.stage_of_gw_extraction) if r.stage_of_gw_extraction is not None else None
                    else:
                        bot_response = (
                            f"⚠️ What-If simulation requires both **GW Extraction** and "
                            f"**Annual Extractable Resource** (> 0) data for {loc_name}. "
                            "These values may not be available in the dataset for this location."
                        )
                else:
                    bot_response = (
                        f"⚠️ I couldn't find data for **{loc_name}** in the INGRES dataset. "
                        "Please use the What-If Analysis tab to select from available districts."
                    )
                suggestions = ['Karnataka What-If', 'Punjab extraction', 'Show all states']
            elif locations['states']:
                loc_name = locations['states'][0]
                recs = crud.get_data_by_state(db, loc_name)
                stats = crud.get_statistics(db, loc_name)
                districts_in_state = crud.get_districts_by_state(db, loc_name)
                if recs and stats:
                    total_ext = round(sum(r.gw_extraction for r in recs if r.gw_extraction is not None), 2)
                    total_extable = round(sum(
                        r.annual_extractable_gw_resource for r in recs
                        if r.annual_extractable_gw_resource is not None
                    ), 2)
                    avg_stage = round(stats['avg_extraction_stage'], 2)
                    extra_allowed.extend([avg_stage, total_ext, total_extable, len(recs)])
                    data_results = recs
                    cgwb_cat_info = classify_cgwb(avg_stage)
                    sample_dists = ", ".join(d.title() for d in districts_in_state[:4])
                    bot_response = (
                        f"What-If simulations in INGRES operate at the **district level** rather than a single state-wide unit.\n\n"
                        f"📍 **State Overview — {loc_name.title()}** ({len(recs)} districts):\n"
                        f"- **Total GW Extraction (district sum):** **{total_ext:.2f} ham**\n"
                        f"- **Total Extractable Resource (district sum):** **{total_extable:.2f} ham**\n"
                        f"- **Average Extraction Stage:** **{avg_stage:.2f}%** ({cgwb_cat_info['emoji']} {cgwb_cat_info['category']})\n\n"
                        f"Please select a district in **{loc_name.title()}** (e.g., {sample_dists}) or use the **🔬 What-If Analysis** tab to run a district simulation."
                    )
                    suggestions = [f"What if {d.title()} reduces extraction by 20%?" for d in districts_in_state[:4]]
                else:
                    bot_response = (
                        f"⚠️ I couldn't find data for **{loc_name}** in the INGRES dataset. "
                        "Please use the What-If Analysis tab to select from available districts."
                    )
                    suggestions = ['Karnataka What-If', 'Punjab extraction', 'Show all states']
            else:
                bot_response = (
                    "Please use the **🔬 What-If Analysis** tab to select a state and district, "
                    "then enter a percentage change to simulate groundwater extraction scenarios."
                )
                suggestions = ['Karnataka What-If', 'Punjab extraction', 'Show all states']

        # ── COMPARE ──
        elif final_intent == 'compare':
            entities_to_compare = locations['states'] + locations['districts']
            if len(entities_to_compare) >= 2:
                comparison_data = []
                for entity in entities_to_compare[:3]:
                    if entity in states:
                        stats = crud.get_statistics(db, entity)
                        if stats:
                            cat = classify_cgwb(stats['avg_extraction_stage'])
                            comparison_data.append({
                                'name': entity, 'type': 'State',
                                'rainfall': round(stats['avg_rainfall'], 2),
                                'extraction': round(stats['avg_extraction_stage'], 2),
                                'category': cat['category'], 'color': cat['color'],
                            })
                    else:
                        recs = crud.get_data_by_district(db, entity)
                        if recs:
                            d = recs[0]
                            cat = classify_cgwb(d.stage_of_gw_extraction) if d.stage_of_gw_extraction is not None else None
                            comparison_data.append({
                                'name': d.district, 'type': 'District',
                                'rainfall': round(d.rainfall_mm, 2) if d.rainfall_mm is not None else 0.0,
                                'extraction': round(d.stage_of_gw_extraction, 2) if d.stage_of_gw_extraction is not None else 0.0,
                                'state': d.state,
                                'category': cat['category'] if cat else 'N/A',
                                'color': cat['color'] if cat else '#888',
                            })
                if comparison_data:
                    names = " vs ".join(c['name'].title() for c in comparison_data)
                    is_rainfall_cmp = any(
                        w in search_text
                        for w in ('rainfall', 'rain', 'precipitation', 'barish', 'वर्षा', 'बारिश')
                    )
                    if is_rainfall_cmp:
                        rain_lines = []
                        for c in comparison_data:
                            extra_allowed.append(round(c['rainfall'], 2))
                            scope_lbl = "State Avg" if c['type'] == 'State' else c.get('state', '').title()
                            rain_lines.append(
                                f"- 🌧️ **{c['name'].title()}** ({scope_lbl}): **{c['rainfall']:.2f} mm**"
                            )
                        bot_response = (
                            f"Here's the **rainfall comparison** (**{names}**):\n\n"
                            + "\n".join(rain_lines)
                        )
                    else:
                        bot_response = f"Here's the groundwater comparison: **{names}**"
                    chart_data   = {'type': 'comparison', 'data': comparison_data}
                else:
                    bot_response = "I found the locations but couldn't retrieve comparison data."
            else:
                bot_response = "Please specify at least **two locations** to compare, e.g., 'Compare Karnataka and Maharashtra'."

        # ── RAINFALL ──
        elif final_intent == 'ask_rainfall':
            loc, loc_type = None, None
            if locations['districts']:
                loc, loc_type = locations['districts'][0], 'district'
            elif locations['states']:
                loc, loc_type = locations['states'][0], 'state'

            if loc:
                if loc_type == 'state':
                    data_results = crud.get_data_by_state(db, loc)
                    stats = crud.get_statistics(db, loc)
                    if stats:
                        extra_allowed.append(round(stats['avg_rainfall'], 2))
                        bot_response = (
                            f"🌧️ **Rainfall data for {loc.title()}**\n\n"
                            f"Average rainfall: **{stats['avg_rainfall']:.2f} mm** "
                            f"across {stats['total_records']} districts."
                        )
                        chart_data = {
                            'type': 'rainfall',
                            'data': [
                                {'district': d.district.title(), 'rainfall': d.rainfall_mm}
                                for d in data_results[:15] if d.rainfall_mm is not None
                            ]
                        }
                else:
                    data_results = crud.get_data_by_district(db, loc)
                    if data_results:
                        d = data_results[0]
                        if d.rainfall_mm is not None:
                            bot_response = (
                                f"🌧️ **Rainfall in {d.district.title()}, {d.state.title()}**\n\n"
                                f"Rainfall: **{d.rainfall_mm:.2f} mm**"
                            )
                        else:
                            bot_response = f"Rainfall data not available for {d.district.title()}."
            else:
                bot_response = "Please specify a location for rainfall data, e.g., 'Rainfall in Karnataka'."
                suggestions   = ['Karnataka rainfall', 'Mysore rainfall', 'Punjab rainfall']

        # ── EXTRACTION STAGE ──
        elif final_intent == 'ask_extraction':
            loc, loc_type = None, None
            if locations['districts']:
                loc, loc_type = locations['districts'][0], 'district'
            elif locations['states']:
                loc, loc_type = locations['states'][0], 'state'

            if loc:
                if loc_type == 'state':
                    data_results = crud.get_data_by_state(db, loc)
                    stats = crud.get_statistics(db, loc)
                    if stats:
                        cat = classify_cgwb(stats['avg_extraction_stage'])
                        cgwb_cat_info = cat
                        extra_allowed.append(round(stats['avg_extraction_stage'], 2))
                        bot_response = (
                            f"📊 **Groundwater Extraction — {loc.title()}**\n\n"
                            f"Average Stage of Extraction: **{stats['avg_extraction_stage']:.2f}%**\n"
                            f"CGWB Category (avg): {cat['emoji']} **{cat['category']}**\n"
                            f"Districts: {stats['total_records']}"
                        )
                        chart_data = {
                            'type': 'extraction',
                            'data': [
                                {
                                    'district': d.district.title(),
                                    'extraction': d.stage_of_gw_extraction,
                                    'category': classify_cgwb(d.stage_of_gw_extraction)['category']
                                               if d.stage_of_gw_extraction is not None else 'N/A',
                                }
                                for d in data_results[:15] if d.stage_of_gw_extraction is not None
                            ]
                        }
                else:
                    data_results = crud.get_data_by_district(db, loc)
                    if data_results:
                        d = data_results[0]
                        if d.stage_of_gw_extraction is not None:
                            cat = classify_cgwb(d.stage_of_gw_extraction)
                            cgwb_cat_info = cat
                            bot_response = (
                                f"📊 **Extraction Stage — {d.district.title()}, {d.state.title()}**\n\n"
                                f"Stage of Extraction: **{d.stage_of_gw_extraction:.2f}%**\n"
                                f"CGWB Category: {cat['emoji']} **{cat['category']}**"
                            )
                        else:
                            bot_response = f"Extraction stage data not available for {d.district.title()}."
            else:
                bot_response = "Please specify a location for extraction stage data."
                suggestions   = ['Karnataka extraction', 'Punjab stage', 'Mysore extraction']

        # ── RECHARGE ──
        elif final_intent == 'ask_recharge':
            loc, loc_type = None, None
            if locations['districts']:
                loc, loc_type = locations['districts'][0], 'district'
            elif locations['states']:
                loc, loc_type = locations['states'][0], 'state'
            if loc:
                if loc_type == 'state':
                    data_results = crud.get_data_by_state(db, loc)
                    stats = crud.get_statistics(db, loc)
                    if stats:
                        extra_allowed.append(round(stats['avg_recharge'], 2))
                        bot_response = (
                            f"♻️ **Groundwater Recharge — {loc.title()}**\n\n"
                            f"Average GW Recharge: **{stats['avg_recharge']:.2f} ham** "
                            f"across {stats['total_records']} districts."
                        )
                else:
                    data_results = crud.get_data_by_district(db, loc)
                    if data_results:
                        d = data_results[0]
                        bot_response = (
                            f"♻️ **GW Recharge — {d.district.title()}, {d.state.title()}**\n\n"
                            f"Ground Water Recharge: **{d.ground_water_recharge:.2f} ham**"
                            if d.ground_water_recharge is not None else
                            f"Recharge data not available for {d.district.title()}."
                        )
            else:
                bot_response = "Please specify a location for recharge data."

        # ── AVAILABILITY ──
        elif final_intent == 'ask_availability':
            loc, loc_type = None, None
            if locations['districts']:
                loc, loc_type = locations['districts'][0], 'district'
            elif locations['states']:
                loc, loc_type = locations['states'][0], 'state'
            if loc:
                if loc_type == 'state':
                    data_results = crud.get_data_by_state(db, loc)
                    stats = crud.get_statistics(db, loc)
                    if stats:
                        extra_allowed.append(round(stats['avg_net_availability'], 2))
                        bot_response = (
                            f"💦 **Net GW Availability — {loc.title()}**\n\n"
                            f"Average Net Availability: **{stats['avg_net_availability']:.2f} ham** "
                            f"across {stats['total_records']} districts."
                        )
                else:
                    data_results = crud.get_data_by_district(db, loc)
                    if data_results:
                        d = data_results[0]
                        bot_response = (
                            f"💦 **Net GW Availability — {d.district.title()}, {d.state.title()}**\n\n"
                            f"Net Annual GW Availability: **{d.net_gw_availability:.2f} ham**"
                            if d.net_gw_availability is not None else
                            f"Net availability data not found for {d.district.title()}."
                        )
            else:
                bot_response = "Please specify a location for availability data."

        # ── DEFAULT (general groundwater info) ──
        else:
            if locations['districts']:
                matched = locations['districts'][0]
                data_results = crud.get_data_by_district(db, matched)
                if data_results and locations['states']:
                    state_filtered = [r for r in data_results if r.state in locations['states']]
                    if state_filtered:
                        data_results = state_filtered
                if data_results:
                    d = data_results[0]
                    cat = classify_cgwb(d.stage_of_gw_extraction) if d.stage_of_gw_extraction is not None else None
                    cgwb_cat_info = cat

                    details = []
                    if d.rainfall_mm is not None:
                        details.append(f"🌧️ Rainfall: **{d.rainfall_mm:.2f} mm**")
                    if d.stage_of_gw_extraction is not None:
                        details.append(
                            f"📊 Extraction Stage: **{d.stage_of_gw_extraction:.2f}%** "
                            f"({cat['emoji']} {cat['category']})"
                        )
                    if d.ground_water_recharge is not None:
                        details.append(f"♻️ GW Recharge: **{d.ground_water_recharge:.2f} ham**")
                    if d.net_gw_availability is not None:
                        details.append(f"💦 Net Availability: **{d.net_gw_availability:.2f} ham**")

                    bot_response = (
                        f"🗺️ **Groundwater Data — {d.district.title()}, {d.state.title()}**\n\n"
                        + "\n".join(details)
                    )

                    # Build extraction chart
                    all_state_data = crud.get_data_by_state(db, d.state)
                    chart_data = {
                        'type': 'extraction',
                        'data': [
                            {
                                'district': rec.district.title(),
                                'extraction': rec.stage_of_gw_extraction,
                                'category': classify_cgwb(rec.stage_of_gw_extraction)['category']
                                            if rec.stage_of_gw_extraction is not None else 'N/A',
                            }
                            for rec in all_state_data[:15] if rec.stage_of_gw_extraction is not None
                        ]
                    }

                    districts_in_state = crud.get_districts_by_state(db, d.state)
                    suggestions = [dist.title() for dist in districts_in_state if dist != matched][:8]
                else:
                    bot_response = (
                        f"⚠️ I couldn't find data for **{matched}** in the INGRES dataset.\n"
                        "Try a valid Indian state or district name."
                    )
                    suggestions = ['Karnataka', 'Mysore', 'Punjab', 'Rajasthan', 'Show all states']

            elif locations['states']:
                matched = locations['states'][0]
                data_results = crud.get_data_by_state(db, matched)
                stats = crud.get_statistics(db, matched)

                if stats:
                    cat = classify_cgwb(stats['avg_extraction_stage'])
                    cgwb_cat_info = cat
                    dist_counts = crud.get_cgwb_distribution(db, matched)
                    extra_allowed.extend([
                        round(stats['avg_rainfall'], 2),
                        round(stats['avg_extraction_stage'], 2),
                        round(stats['avg_recharge'], 2),
                        round(stats['avg_net_availability'], 2),
                    ])

                    bot_response = (
                        f"🗺️ **Groundwater Data — {matched.title()}**\n\n"
                        f"🌧️ Avg Rainfall: **{stats['avg_rainfall']:.2f} mm**\n"
                        f"📊 Avg Extraction Stage: **{stats['avg_extraction_stage']:.2f}%** "
                        f"({cat['emoji']} {cat['category']})\n"
                        f"♻️ Avg GW Recharge: **{stats['avg_recharge']:.2f} ham**\n"
                        f"💦 Avg Net Availability: **{stats['avg_net_availability']:.2f} ham**\n"
                        f"📍 Total Districts: **{stats['total_records']}**\n\n"
                        f"🏷️ District Category Breakdown:\n"
                        f"🟢 Safe: {dist_counts['SAFE']}  "
                        f"🟡 Semi-Critical: {dist_counts['SEMI-CRITICAL']}  "
                        f"🟠 Critical: {dist_counts['CRITICAL']}  "
                        f"🔴 Over-Exploited: {dist_counts['OVER-EXPLOITED']}"
                    )

                    # Rainfall bar chart
                    chart_data = {
                        'type': 'state_overview',
                        'rainfall_data': [
                            {'district': d.district.title(), 'rainfall': d.rainfall_mm}
                            for d in data_results[:15] if d.rainfall_mm is not None
                        ],
                        'extraction_data': [
                            {
                                'district': d.district.title(),
                                'extraction': d.stage_of_gw_extraction,
                                'category': classify_cgwb(d.stage_of_gw_extraction)['category']
                                            if d.stage_of_gw_extraction is not None else 'N/A',
                            }
                            for d in data_results[:15] if d.stage_of_gw_extraction is not None
                        ],
                        'cgwb_distribution': [
                            {'name': k, 'value': v, 'color': classify_cgwb(
                                0 if k == 'SAFE' else 80 if k == 'SEMI-CRITICAL'
                                else 95 if k == 'CRITICAL' else 110
                            )['color']}
                            for k, v in dist_counts.items() if v > 0
                        ],
                    }

                    districts = crud.get_districts_by_state(db, matched)
                    suggestions = [d.title() for d in districts[:12]]

            else:
                bot_response = (
                    "I couldn't identify a location in your query. "
                    "Try asking about a specific state or district:\n"
                    "*e.g., 'Karnataka groundwater', 'Mysore extraction stage'*"
                )
                suggestions = ['Karnataka', 'Mysore', 'Maharashtra', 'Punjab', 'Rajasthan', 'Show all states']

        # ── 9. Number Verification ───────────────────────────────────────────
        formatted_data = _format_records(data_results)
        verification   = verify_response(bot_response, formatted_data, extra_allowed=extra_allowed or None)
        verified       = verification['verified']
        v_issues       = verification['issues']

        # If verification fails, append a caveat rather than discarding the response
        # (The response already came from actual DB data — bad numbers are very rare)
        if not verified:
            logger.warning(f"Verification failed: {v_issues}")

        # ── 10. Translate back if needed ─────────────────────────────────────
        if user_language != 'en' and bot_response:
            try:
                bot_response = translator.translate_text(bot_response, user_language, 'en')
            except Exception:
                pass

        # ── 11. Build updated conversation context & log history ─────────────
        next_context: Dict[str, Any] = {
            "last_intent": final_intent,
            "pending_clarification": pending_clarification,
        }
        if explicit_location_found:
            if locations['districts']:
                resolved_dist = data_results[0].district if data_results else locations['districts'][0]
                resolved_state = data_results[0].state if data_results else (locations['states'][0] if locations['states'] else None)
                next_context["last_district"] = resolved_dist
                next_context["last_state"] = resolved_state
                next_context["last_location_type"] = "district"
            elif locations['states']:
                next_context["last_state"] = locations['states'][0]
                next_context["last_district"] = None
                next_context["last_location_type"] = "state"
        else:
            if prev_context.get("last_state"):
                next_context["last_state"] = prev_context["last_state"]
            if prev_context.get("last_district"):
                next_context["last_district"] = prev_context["last_district"]
            if prev_context.get("last_location_type"):
                next_context["last_location_type"] = prev_context["last_location_type"]

        # Preserve crop only across crop/sustainability follow-ups, clear on location-only lookup shifts
        if crop_name:
            next_context["last_crop"] = crop_name
        elif final_intent in ('ask_sustainability', 'ask_crop_water_requirements') and prev_context.get("last_crop"):
            next_context["last_crop"] = prev_context["last_crop"]
        else:
            next_context["last_crop"] = None

        if message.session_id:
            if len(_SESSION_CONTEXT) >= 500 and message.session_id not in _SESSION_CONTEXT:
                oldest_key = next(iter(_SESSION_CONTEXT))
                _SESSION_CONTEXT.pop(oldest_key, None)
            _SESSION_CONTEXT[message.session_id] = next_context

        try:
            db.add(models.ChatHistory(
                user_message=user_message,
                bot_response=bot_response,
                language=user_language,
            ))
            db.commit()
        except Exception:
            db.rollback()

        logger.info(f"Response (first 100): {bot_response[:100]}")

        return schemas.ChatResponse(
            response=bot_response,
            data=formatted_data if formatted_data else None,
            suggestions=suggestions if suggestions else None,
            chart_data=chart_data,
            context=next_context,
            # Review 2 fields
            verified=verified,
            verification_issues=v_issues if not verified else [],
            scope_status='in_scope',
            out_of_scope_reason=None,
            assessment_year=assessment_year_str,
            data_source=data_source_str,
            data_confidence=DATA_CONFIDENCE,
            cgwb_category=cgwb_cat_info['category'] if cgwb_cat_info else None,
            cgwb_color=cgwb_cat_info['color']    if cgwb_cat_info else None,
        )

    except Exception as exc:
        logger.error(f"Chat error: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))


# ─── What-If Endpoint ─────────────────────────────────────────────────────────

@app.post("/whatif", response_model=schemas.WhatIfResponse)
async def run_whatif(req: schemas.WhatIfRequest, db: Session = Depends(get_db)):
    """Run a What-If simulation for a specific district's groundwater extraction."""
    try:
        record, ambiguous = crud.get_whatif_lookup_result(db, req.state, req.district)
        if ambiguous:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"Ambiguous district '{req.district}' in state '{req.state}'. "
                    f"Matching districts: {', '.join(ambiguous)}"
                )
            )
        if not record:
            raise HTTPException(
                status_code=404,
                detail=f"No data found for district '{req.district}' in state '{req.state}'"
            )

        if (
            record.gw_extraction is None
            or record.annual_extractable_gw_resource is None
            or record.annual_extractable_gw_resource <= 0
        ):
            raise HTTPException(
                status_code=422,
                detail=(
                    f"What-If requires non-null 'gw_extraction' and positive 'annual_extractable_gw_resource' "
                    f"for {record.district}. These values may be missing or zero in the dataset."
                )
            )

        result = simulate_whatif(
            current_extraction=record.gw_extraction,
            annual_extractable=record.annual_extractable_gw_resource,
            pct_change=req.pct_change,
        )
        response_text = build_whatif_response(
            result=result,
            district=record.district,
            state=record.state,
            pct_change=req.pct_change,
        )

        return schemas.WhatIfResponse(
            response=response_text,
            result=result,
            chart_data=result['chart_data'],
            assessment_year=str(data_processor.ASSESSMENT_YEAR),
            data_source=data_processor.DATA_SOURCE,
            district=record.district,
            state=record.state,
        )

    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"What-If error: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/whatif/scenarios", response_model=MultiScenarioResponse)
async def run_whatif_scenarios(req: MultiScenarioRequest, db: Session = Depends(get_db)):
    """Run multi-sector What-If scenario comparison with C+NC official stage separation."""
    try:
        return run_multi_scenario_whatif(db, req)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        msg = str(exc)
        if msg.startswith("AMBIGUOUS:"):
            raise HTTPException(status_code=422, detail=msg.replace("AMBIGUOUS:", "", 1))
        raise HTTPException(status_code=422, detail=msg)
    except Exception as exc:
        logger.error(f"What-If scenarios error: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))


# ─── Groundwater Diagnostic Endpoint ──────────────────────────────────────────

@app.post("/diagnose", response_model=DiagnosticResponse)
async def diagnose_groundwater(req: DiagnosticRequest, db: Session = Depends(get_db)):
    """Run evidence-based groundwater stress diagnosis and intervention analysis."""
    try:
        return run_diagnostic(db, req)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        msg = str(exc)
        if msg.startswith("AMBIGUOUS:"):
            raise HTTPException(status_code=422, detail=msg.replace("AMBIGUOUS:", "", 1))
        raise HTTPException(status_code=422, detail=msg)
    except Exception as exc:
        logger.error(f"Diagnostic error: {exc}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))


# ─── Evaluation Endpoint ──────────────────────────────────────────────────────

@app.get("/evaluate")
async def run_evaluation(db: Session = Depends(get_db)):
    """
    Run the 50-question benchmark evaluation against the live database.
    Returns accuracy, refusal rate, unsupported number rate, and latency.
    """
    async def _chat_fn(msg: str, lang: str = 'en') -> dict:
        cm = schemas.ChatMessage(message=msg, language=lang)
        resp = await chat(cm, db)
        return resp.__dict__

    report = await eval_module.run_evaluation(_chat_fn)
    return report


# ─── Existing + New REST Endpoints ───────────────────────────────────────────

@app.get("/states", response_model=List[str])
def get_states(db: Session = Depends(get_db)):
    return crud.get_all_states(db)


@app.get("/districts/{state}", response_model=List[str])
def get_districts(state: str, db: Session = Depends(get_db)):
    return crud.get_districts_by_state(db, state)


@app.get("/data/{state}")
def get_state_data(state: str, db: Session = Depends(get_db)):
    data = crud.get_data_by_state(db, state)
    return _format_records(data, include_all=True)


@app.get("/stats/total")
def get_total_stats(db: Session = Depends(get_db)):
    total_records   = db.query(models.GroundwaterData).count()
    total_states    = db.query(models.GroundwaterData.state).distinct().count()
    total_districts = db.query(models.GroundwaterData.district).distinct().count()
    return {
        "total_records":   total_records,
        "total_states":    total_states,
        "total_districts": total_districts,
        "rasa_enabled":    USE_RASA,
        "assessment_year": data_processor.ASSESSMENT_YEAR,
        "data_source":     data_processor.DATA_SOURCE,
    }


@app.get("/stats/{state}")
def get_state_stats(state: str, db: Session = Depends(get_db)):
    stats = crud.get_statistics(db, state)
    if not stats:
        raise HTTPException(status_code=404, detail="State not found")
    cat = classify_cgwb(stats['avg_extraction_stage'])
    return {**stats, 'cgwb_category': cat['category'], 'cgwb_color': cat['color']}


@app.get("/cgwb/{state}")
def get_cgwb_distribution(state: str, db: Session = Depends(get_db)):
    """Get CGWB category distribution (count per category) for a state."""
    dist = crud.get_cgwb_distribution(db, state)
    if sum(dist.values()) == 0:
        raise HTTPException(status_code=404, detail=f"State '{state}' not found")
    return {
        "state":        state,
        "distribution": dist,
        "chart_data": {
            'type': 'cgwb_distribution',
            'data': [
                {'name': k, 'value': v,
                 'color': classify_cgwb(
                     0 if k == 'SAFE' else
                     80 if k == 'SEMI-CRITICAL' else
                     95 if k == 'CRITICAL' else 110
                 )['color']}
                for k, v in dist.items() if v > 0
            ]
        }
    }


@app.get("/assessment_year")
def get_assessment_year():
    """Return the assessment year and data source for the loaded dataset."""
    return {
        "assessment_year": data_processor.ASSESSMENT_YEAR,
        "data_source":     data_processor.DATA_SOURCE,
        "data_confidence": DATA_CONFIDENCE,
    }


@app.get("/health")
def health_check():
    return {
        "status":       "healthy",
        "version":      "4.0 (Review 2)",
        "rasa_enabled": USE_RASA,
        "assessment_year": data_processor.ASSESSMENT_YEAR,
        "features": [
            "scope_guard", "number_verifier", "whatif_simulator",
            "cgwb_classification", "benchmark_evaluation",
            "groundwater_diagnostics", "multisector_whatif"
        ]
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
