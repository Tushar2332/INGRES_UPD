"""
parser.py — Query Parser, Intent Detector & Scope Guard for INGRES Chatbot (Review 2)

Pipeline:
  User Query → parse_query() → {intent, locations, is_in_scope, out_of_scope_reason, ...}
"""
import re
from typing import Optional, List, Dict, Any, Tuple, Union, Iterable

# ─── Assessment year (default synced from data_processor at runtime) ─────────
ASSESSMENT_YEAR = "2024-2025"

# ─── Forecast / future-tense patterns ────────────────────────────────────────
# Note: Only treat years strictly > 2025 (beyond 2024-2025 cycle) as forecasts,
# so historical queries like "in 2022" or "in 2020" reach year_unavailable instead.
FORECAST_PATTERNS = [
    r'\bwill\b', r'\bnext year\b', r'\bfuture\b', r'\bpredict\b',
    r'\bforecast\b', r'\btomorrow\b', r'\bcoming year\b', r'\bupcoming\b',
    r'\bin 20(?:2[6-9]|[3-9]\d)\b', r'\bby 20(?:2[6-9]|[3-9]\d)\b',
    r'\b202[6-9]\b', r'\b203\d\b', r'\b204\d\b',
    r'\bprojection\b', r'\bexpect\b', r'\bwhen will\b', r'\bhow much rain.*come\b',
    # Hindi future markers
    r'\bhoga\b', r'\bhogi\b', r'\bkya hoga\b', r'\bagle saal\b',
    r'आएगा', r'होगा', r'होगी', r'मिलेगा', r'अगले साल',
]

# ─── Unsupported metric / unrelated scope patterns ────────────────────────────
UNSUPPORTED_METRICS = [
    'temperature', 'flood risk', 'air quality', 'pollution', 'population',
    'crime', 'gdp', 'economy', 'stock', 'cricket', 'movie', 'recipe',
    'humidity', 'wind speed',
]

# ─── City / district / state canonical aliases (verified against ingres.db) ───
LOCATION_ALIASES: Dict[str, str] = {
    'bengaluru urban': 'BENGALURU (URBAN)',
    'bangalore urban': 'BENGALURU (URBAN)',
    'bengaluru rural': 'BENGALURU (RURAL)',
    'bangalore rural': 'BENGALURU (RURAL)',
    'bangalore': 'BENGALURU (URBAN)',
    'bengaluru': 'BENGALURU (URBAN)',
    'bengalore': 'BENGALURU (URBAN)',
    'bangaluru': 'BENGALURU (URBAN)',
    'mysore': 'MYSURU',
    'maisuru': 'MYSURU',
    'bombay': 'MUMBAI',
    'mumbai suburban': 'MUMBAI SUB',
    'madras': 'CHENNAI',
    'calcutta': 'KOLKATTA',
    'kolkata': 'KOLKATTA',
    'howrah': 'HAORA',
    'hooghly': 'HUGLI',
    'darjeeling': 'DARJILING',
    'cooch behar': 'KOCH BIHAR',
    'trivandrum': 'THIRUVANANTHAPURAM',
    'cochin': 'ERNAKULAM',
    'kochi': 'ERNAKULAM',
    'calicut': 'KOZHIKKODE',
    'kozhikode': 'KOZHIKKODE',
    'kasaragod': 'KASARGOD',
    'baroda': 'VADODARA',
    'poona': 'PUNE',
    'vizag': 'VISAKHAPATNAM',
    'visakha': 'VISAKHAPATNAM',
    'new delhi': 'NEW DELHI',
    'dilli': 'DELHI',
    'tamil nadu': 'TAMILNADU',
    'gulbarga': 'KALBURGI',
    'kalaburagi': 'KALBURGI',
    'belgaum': 'BELAGAVI',
    'bellary': 'BALLARI',
    'bijapur': 'VIJAYAPURA',
    'shimoga': 'SHIVAMOGGA',
    'tumkur': 'TUMAKURU',
    'chikmagalur': 'CHIKKAMAGALURU',
    'chikkaballapur': 'CHIKKABALLAPURA',
    'chamarajanagar': 'CHAMARAJANAGARA',
    'kolar': 'KOLARA',
    'hubli': 'DHARWAD',
    'hubballi': 'DHARWAD',
    'mangalore': 'DAKSHINA KANNADA',
    'mangaluru': 'DAKSHINA KANNADA',
    'kanyakumari': 'KANNIYAKUMARI',
    'trichy': 'TIRUCHIRAPPALLI',
}

# Qualified location phrases that should not be rewritten by single-word aliases
_QUALIFIED_LOCATION_PHRASES = (
    'bengaluru (rural)', 'bengaluru rural', 'bangalore rural',
    'bengaluru (urban)', 'bengaluru urban', 'bangalore urban',
    'bengaluru south', 'bangalore south',
    'mumbai sub', 'mumbai suburban', 'new delhi',
)

# ─── Known crop names & synonyms for agricultural intent parsing ───────────
CROP_SYNONYMS: Dict[str, str] = {
    'mangoes': 'mango',
    'mango': 'mango',
    'paddy': 'rice',
    'rice': 'rice',
    'sugarcane': 'sugarcane',
    'cane': 'sugarcane',
    'wheat': 'wheat',
    'maize': 'maize',
    'corn': 'maize',
    'cotton': 'cotton',
    'millets': 'millets',
    'millet': 'millets',
    'ragi': 'millets',
    'jowar': 'millets',
    'bajra': 'millets',
    'pulses': 'pulses',
    'pulse': 'pulses',
    'lentils': 'pulses',
    'chickpea': 'pulses',
    'gram': 'pulses',
    'tur': 'pulses',
    'groundnut': 'groundnut',
    'peanut': 'groundnut',
    'banana': 'banana',
    'bananas': 'banana',
    'coconut': 'coconut',
    'arecanut': 'arecanut',
    'coffee': 'coffee',
    'vegetables': 'vegetables',
    'vegetable': 'vegetables',
    'tomato': 'vegetables',
    'onion': 'vegetables',
    'potato': 'vegetables',
}

# ─── Contextual reference phrases ─────────────────────────────────────────────
CONTEXT_LOCATION_PATTERNS = [
    r'\bthere\b',
    r'\bhere\b',
    r'\bthis district\b',
    r'\bthis state\b',
    r'\bthis area\b',
    r'\bthis region\b',
    r'\bthis location\b',
    r'\bthis place\b',
    r'\bsame district\b',
    r'\bsame area\b',
    r'\bthat district\b',
    r'\bthat area\b',
    r'\bwhat about\b',
    r'\bhow about\b',
    r'\bwould\b.*\bbe better\b',
    r'\bis it sustainable\b',
    r'\bis it suitable\b',
]

# ─── Intent patterns (order matters: specific advisory intents before generic) ─
INTENT_PATTERNS: Dict[str, List[str]] = {
    'greet': [
        r'\bhello\b', r'\bhi\b', r'\bhey\b', r'\bnamaste\b', r'\bnamaskar\b',
        r'नमस्ते', r'नमस्कार', r'\bgood morning\b', r'\bgood afternoon\b',
        r'\bgood evening\b', r'\bstart\b',
    ],
    'ask_state_list': [
        r'\bshow states\b', r'\blist states\b', r'\ball states\b',
        r'\bavailable states\b', r'\bwhich states\b', r'\bshow all\b',
    ],
    'ask_crop_water_requirements': [
        r'\bwhich crops?\b.*\b(less|low|minimal|little|more|high)\s+water\b',
        r'\blow[- ]water crops?\b', r'\bless[- ]water crops?\b', r'\bdrought[- ]tolerant crops?\b',
        r'\bcrop water requirement', r'\bwater requirement.*\bcrop',
        r'\bhow much water does\b.*\bneed\b', r'\bwater[- ]intensive crops?\b',
    ],
    'ask_agricultural_suitability': [
        r'\b(?:grow|cultivat\w*|plant|farm\w*|crop\w*|orchard|horticultur\w*)\b',
        r'\b(?:suitable|good|viable|feasible|better)\b.*\b(?:crop|crops|grow|cultivat|mango|mangoes|rice|paddy|wheat|sugarcane|cotton|millet|millets|pulses|banana|coconut|maize|groundnut|vegetables?)\b',
        r'\bwhat about\b.*\b(?:mango|mangoes|rice|paddy|wheat|sugarcane|cotton|millet|millets|pulses|banana|coconut|maize|groundnut|vegetables?)\b',
        r'\bwould\b.*\b(?:mango|mangoes|rice|paddy|wheat|sugarcane|cotton|millet|millets|pulses|banana|coconut|maize|groundnut|vegetables?)\b.*\bbetter\b',
        r'\b(?:mango|mangoes|rice|paddy|wheat|sugarcane|cotton|millet|millets|pulses|banana|coconut|maize|groundnut|vegetables?)\b',
    ],
    'ask_irrigation_impact': [
        r'\b(?:increas\w*|expand\w*|more|excessive|heavy)\b.*\birrigat\w*\b',
        r'\birrigat\w*\b.*\b(?:pressure|stress|impact|effect|deplet\w*|groundwater|sustainab\w*)\b',
        r'\bwhat if\b.*\birrigat\w*\b',
        r'\b(?:drip|sprinkler|micro[- ]irrigat\w*|flood irrigat\w*|irrigat\w* efficiency|irrigat\w* scheduling)\b',
        r'\bpressure on groundwater\b',
    ],
    'ask_sustainability': [
        r'\bsustainab\w*\b', r'\blong[- ]term\b.*\b(?:water|groundwater|farming|extraction)\b',
        r'\bcan it support\b', r'\bsafe to pump\b',
    ],
    'ask_trends_causes': [
        r'\bwhy is\b.*\b(?:over[- ]?exploit\w*|critical|stressed|high|low|deplet\w*)\b',
        r'\b(?:causes?|reasons?|drivers?|trends?)\b.*\b(?:groundwater|extraction|stress|deplet\w*|decline)\b',
        r'\bgroundwater trends?\b',
    ],
    'ask_general_groundwater': [
        r'\bwhat does\b.*\bmean\b', r'\bmeaning of\b', r'\bhow is\b.*\bcalculated\b',
        r'\bexplain\b.*\b(?:cgwb|stage|groundwater|recharge|extraction|safe|over.exploit)\b',
        r'\bwhat are the cgwb categor',
    ],
    'ask_whatif': [
        r'\bwhat.if\b', r'\bwhat if\b',
        r'\bif (?:i |we )?reduce\b', r'\bif (?:i |we )?increase\b',
        r'\bif extraction\b', r'\bsimulat\b', r'\bscenario\b',
        r'\bwhat happens\b', r'\bif we\b', r'\bif the\b.*\bextraction\b',
        r'\bक्या होगा\b', r'\breduce extraction\b', r'\bincrease extraction\b',
        r'\bchange extraction\b',
    ],
    'compare': [
        r'\bcompare\b', r'\bvs\.?\b', r'\bversus\b', r'\bdifference between\b',
        r'\btulna\b', r'\bतुलना\b', r'\bwhich is (better|worse|higher|lower)\b',
        r'\bbetween\b.*\band\b',
    ],
    'ask_rainfall': [
        r'\brainfall\b', r'\brain\b', r'\bprecipitation\b', r'\bbarish\b',
        r'\bवर्षा\b', r'\bबारिश\b', r'\b\.mm\b', r'\bmillimeter\b',
    ],
    'ask_extraction': [
        r'\bextraction\b', r'\bstage of\b', r'\bover.exploit\b',
        r'\bover exploit\b', r'\bnिष्कर्षण\b', r'\bexploitation\b',
        r'\bpumping\b', r'\bdraft\b',
    ],
    'ask_recharge': [
        r'\brecharge\b', r'\bरिचार्ज\b', r'\breplenish\b',
        r'\bgroundwater recharge\b', r'\bgw recharge\b',
    ],
    'ask_availability': [
        r'\bavailability\b', r'\bnet availability\b', r'\bfuture use\b',
        r'\bउपलब्धता\b', r'\bnet annual\b', r'\bremaining\b',
    ],
    'ask_category': [
        r'\bcategory\b', r'\bcgwb\b', r'\bsafe\b', r'\bcritical\b',
        r'\bover.exploit\b', r'\bsemi.critical\b', r'\bstatus\b',
        r'\bclassif\b',
    ],
    'ask_groundwater': [
        r'\bgroundwater\b', r'\bground water\b', r'\bbhujal\b',
        r'\bभूजल\b', r'\bwater table\b', r'\baquifer\b',
        r'\bdata\b', r'\binfo\b', r'\btell me about\b', r'\bshow me\b',
        r'\bwhat is\b', r'\bहालत\b', r'\bस्थिति\b',
    ],
}


def _match_patterns(text: str, patterns: List[str]) -> bool:
    """Return True if any pattern matches in text (case-insensitive)."""
    for pat in patterns:
        if re.search(pat, text, re.IGNORECASE):
            return True
    return False


def is_forecast_query(text: str) -> bool:
    """Return True if the query asks about future/forecast data."""
    return _match_patterns(text, FORECAST_PATTERNS)


def has_unsupported_metric(text: str) -> bool:
    """Return True if the query asks about metrics not in INGRES dataset."""
    text_lower = text.lower()
    return any(m in text_lower for m in UNSUPPORTED_METRICS)


def extract_year(text: str) -> Optional[int]:
    """Extract a 4-digit year from text if present."""
    match = re.search(r'\b(19\d{2}|20\d{2})\b', text)
    return int(match.group(1)) if match else None


def apply_location_aliases(text: str) -> str:
    """Replace known city/state aliases with canonical DB forms using longest-first boundaries."""
    text_lower = text.lower()
    # Apply longest keys first so qualified phrases like 'bengaluru rural' take priority over 'bengaluru'
    for alias, canonical in sorted(LOCATION_ALIASES.items(), key=lambda kv: len(kv[0]), reverse=True):
        # Skip replacing bare 'bengaluru'/'bangalore' when already qualified as rural/south/urban
        if alias in ('bengaluru', 'bangalore', 'bengalore', 'bangaluru'):
            if any(q in text_lower for q in _QUALIFIED_LOCATION_PHRASES):
                continue
        pattern = r'\b' + re.escape(alias) + r'\b'
        if re.search(pattern, text_lower):
            text_lower = re.sub(pattern, canonical.lower(), text_lower)
    return text_lower


def normalize_location(name: str) -> str:
    """Normalize location name by resolving aliases and trimming."""
    name_clean = name.strip()
    lower = name_clean.lower()
    return LOCATION_ALIASES.get(lower, name_clean.upper())


def _extract_available_years(assessment_year: Union[int, str, Iterable[int]]) -> set:
    """Normalize assessment_year (int, '2024-2025', or iterable) into a set of integer years."""
    if isinstance(assessment_year, int):
        return {assessment_year}
    if isinstance(assessment_year, str):
        yrs = {int(y) for y in re.findall(r'(19\d{2}|20\d{2})', assessment_year)}
        return yrs if yrs else {2024, 2025}
    return {int(y) for y in assessment_year}


_NON_LOCATION_TOKENS = {
    'what', 'which', 'where', 'when', 'how', 'is', 'are', 'was', 'were', 'the', 'a', 'an',
    'in', 'of', 'for', 'about', 'tell', 'me', 'show', 'give', 'list', 'all', 'states', 'state',
    'district', 'districts', 'city', 'groundwater', 'ground', 'water', 'data', 'info',
    'information', 'status', 'category', 'cgwb', 'safe', 'critical', 'semi', 'over', 'exploited',
    'rainfall', 'rain', 'extraction', 'stage', 'recharge', 'availability', 'net', 'annual',
    'compare', 'vs', 'versus', 'and', 'or', 'between', 'difference', 'with', 'from', 'to',
    'reduce', 'increase', 'increasing', 'decreasing', 'simulate', 'whatif', 'if', 'we', 'i',
    'by', 'more', 'less', 'higher', 'lower', 'better', 'worse', 'please', 'find', 'check',
    'can', 'you', 'good', 'grow', 'growing', 'cultivate', 'cultivation', 'suitable', 'suitability',
    'viable', 'crop', 'crops', 'there', 'here', 'this', 'that', 'same', 'area', 'region',
    'place', 'farm', 'farming', 'agriculture', 'agricultural', 'irrigation', 'irrigated',
    'sustainable', 'sustainability', 'pressure', 'stress', 'require', 'requires', 'need', 'needs',
    'would', 'could', 'should', 'will', 'does', 'do', 'put', 'mean', 'means', 'explain',
    'trend', 'trends', 'cause', 'causes', 'reason', 'reasons', 'why', 'soil', 'drainage',
    'climate', 'drip', 'sprinkler', 'well', 'wells', 'borewell', 'borewells', 'pump', 'pumps',
    'mango', 'mangoes', 'rice', 'paddy', 'wheat', 'sugarcane', 'maize', 'cotton', 'millet',
    'millets', 'pulses', 'groundnut', 'banana', 'coconut', 'arecanut', 'coffee', 'vegetables',
}

_LOCATION_LOOKUP_INTENTS = {
    'ask_groundwater', 'ask_rainfall', 'ask_extraction', 'ask_recharge',
    'ask_availability', 'ask_category', 'compare',
}


def extract_crop(text: str) -> Optional[str]:
    """Extract canonical crop name from text if mentioned (known or '<grow|cultivate> <crop>')."""
    lower = text.lower()
    for term, canonical in sorted(CROP_SYNONYMS.items(), key=lambda kv: len(kv[0]), reverse=True):
        if re.search(r'\b' + re.escape(term) + r'\b', lower):
            return canonical
    m = re.search(r'\b(?:grow|cultivate|cultivating|growing|plant|planting)\s+([a-z]{3,20})\b', lower)
    if m and m.group(1) not in _NON_LOCATION_TOKENS:
        return m.group(1)
    return None


def uses_context_reference(text: str) -> bool:
    """Return True if the message refers to a previously discussed location/topic."""
    return _match_patterns(text, CONTEXT_LOCATION_PATTERNS)


def extract_unknown_location_candidate(original_text: str, lower: str, intent: str) -> Optional[str]:
    """
    Extract a plausible unrecognized place name ONLY for location-lookup queries,
    never returning an entire natural-language sentence.
    """
    if intent not in _LOCATION_LOOKUP_INTENTS:
        return None
    if uses_context_reference(lower):
        return None

    # 1. Explicit '<word> city/district/state'
    m = re.search(r'\b([a-z][a-z\-]{2,})\s+(?:city|district|state)\b', lower)
    if m and m.group(1) not in _NON_LOCATION_TOKENS:
        return m.group(1).title()

    # 2. Explicit preposition '<in|of|for|about> <Candidate>'
    for m in re.finditer(r'\b(?:in|of|for|about)\s+([a-z][a-z\-]{2,})\b', lower):
        tok = m.group(1)
        if tok not in _NON_LOCATION_TOKENS and not tok.isdigit():
            return tok.title()

    # 3. Any remaining non-stopword capitalized/alpha token
    for tok in re.findall(r'\b[a-z]{4,}\b', lower):
        if tok not in _NON_LOCATION_TOKENS:
            return tok.title()

    return None


def detect_intent(text: str) -> str:
    """Return the best-matching intent string from the query."""
    for intent, patterns in INTENT_PATTERNS.items():
        if _match_patterns(text, patterns):
            return intent
    return 'ask_groundwater'  # sensible default


def parse_query(
    text: str,
    available_states: List[str],
    district_map: Dict[str, Any],
    assessment_year: Union[int, str, Iterable[int]] = ASSESSMENT_YEAR,
    original_text: str = '',
) -> Dict[str, Any]:
    """
    Full query parse.

    Returns:
        {
            intent: str,
            locations: {states: List[str], districts: List[str]},
            crop: str | None,
            uses_context: bool,
            unknown_location_candidate: str | None,
            is_in_scope: bool,
            out_of_scope_reason: str | None,
            year_requested: int | None,
            year_available: bool,
        }
    """
    lower = text.lower()
    aliased = apply_location_aliases(lower)
    crop = extract_crop(lower)
    uses_ctx = uses_context_reference(lower)

    # 1. Forecast check — highest priority
    if is_forecast_query(lower):
        return {
            'intent': 'forecast',
            'locations': {'states': [], 'districts': []},
            'crop': crop,
            'uses_context': uses_ctx,
            'unknown_location_candidate': None,
            'is_in_scope': False,
            'out_of_scope_reason': 'forecast',
            'year_requested': None,
            'year_available': True,
        }

    # 2. Unsupported metric / unrelated topic
    if has_unsupported_metric(lower):
        return {
            'intent': 'unsupported_metric',
            'locations': {'states': [], 'districts': []},
            'crop': crop,
            'uses_context': uses_ctx,
            'unknown_location_candidate': None,
            'is_in_scope': False,
            'out_of_scope_reason': 'unsupported_metric',
            'year_requested': None,
            'year_available': True,
        }

    # 3. Year extraction + validation
    year_requested = extract_year(lower)
    available_years = _extract_available_years(assessment_year)
    year_available = (year_requested is None) or (year_requested in available_years)

    # 4. Intent detection
    intent = detect_intent(lower)

    # 5. Location extraction (word-boundary / exact-first on states and districts)
    found_states: List[str] = []
    found_districts: List[str] = []

    for state in available_states:
        s_low = state.lower()
        if re.search(r'\b' + re.escape(s_low) + r'\b', aliased) or re.search(r'\b' + re.escape(s_low) + r'\b', lower):
            if state not in found_states:
                found_states.append(state)

    for dist_key, (dist_val, state_val) in district_map.items():
        if not dist_key:
            continue
        pat = r'\b' + re.escape(dist_key) + r'\b'
        if re.search(pat, aliased) or re.search(pat, lower) or (dist_key in aliased and '(' in dist_key):
            if dist_val not in found_districts:
                found_districts.append(dist_val)
            if state_val not in found_states:
                found_states.append(state_val)

    # 6. Unknown location check (ONLY for location-lookup queries with an explicit place candidate)
    unknown_candidate = None
    if not found_states and not found_districts:
        unknown_candidate = extract_unknown_location_candidate(original_text or text, lower, intent)
        if unknown_candidate:
            return {
                'intent': intent,
                'locations': {'states': [], 'districts': []},
                'crop': crop,
                'uses_context': uses_ctx,
                'unknown_location_candidate': unknown_candidate,
                'is_in_scope': False,
                'out_of_scope_reason': 'unknown_location',
                'year_requested': year_requested,
                'year_available': year_available,
            }

    return {
        'intent': intent,
        'locations': {'states': found_states, 'districts': found_districts},
        'crop': crop,
        'uses_context': uses_ctx,
        'unknown_location_candidate': None,
        'is_in_scope': True,
        'out_of_scope_reason': None,
        'year_requested': year_requested,
        'year_available': year_available,
    }


def build_scope_refusal(
    reason: str,
    location: str = '',
    year: Optional[int] = None,
    latest_year: int = ASSESSMENT_YEAR,
    latest_value: Optional[float] = None,
    metric: str = '',
) -> str:
    """Build a human-friendly, honest refusal message for out-of-scope queries."""
    if reason == 'forecast':
        msg = (
            "⚠️ **I cannot predict future values.** The INGRES dataset contains only "
            "historically assessed groundwater data — it does not support forecasting."
        )
        if latest_value is not None and metric:
            msg += (
                f"\n\nThe latest available assessed **{metric}** is "
                f"**{latest_value:.2f}** (Assessment Year: {latest_year}, Source: INGRES/CGWB)."
            )
        return msg

    if reason == 'unknown_location':
        return (
            f"⚠️ Sorry, **{location}** is not found in the INGRES groundwater dataset. "
            "Please try a valid Indian state or district name. "
            "Use 'Show all states' to see available locations."
        )

    if reason == 'unsupported_metric':
        return (
            "⚠️ This metric is not available in the INGRES groundwater dataset.\n\n"
            "I can answer questions about:\n"
            "- 🌧️ Rainfall (mm)\n"
            "- ♻️ Groundwater Recharge (ham)\n"
            "- 📊 Stage of Groundwater Extraction (%)\n"
            "- 💦 Net Groundwater Availability (ham)\n"
            "- 🏷️ CGWB Category (Safe / Semi-Critical / Critical / Over-Exploited)"
        )

    if reason == 'year_unavailable':
        return (
            f"⚠️ Data for the year **{year}** is not available in the INGRES dataset.\n"
            f"The latest available assessment year is **{latest_year}** (GEC-{latest_year})."
        )

    return "⚠️ This query is out of scope for the INGRES groundwater dataset."
