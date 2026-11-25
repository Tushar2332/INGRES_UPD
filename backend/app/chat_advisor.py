"""
chat_advisor.py — Grounded Agricultural, Irrigation & Groundwater Advisory Engine

Provides context-aware, scientifically honest responses using:
  1. Verified INGRES / CGWB 2024-2025 assessment data
  2. Derived calculations (official C + NC stage, sectoral shares, Safe gap)
  3. General qualitative agricultural reference profiles (never presented as local verified facts)
  4. Explicit disclosure of missing local data (soil, farm yield, piezometer trends, MI Census)
"""

from typing import Any, Dict, List, Optional, Tuple
from .models import GroundwaterData
from .whatif import CGWB_SAFE_THRESHOLD, calculate_official_cgwb_metrics, classify_cgwb


# Qualitative agronomic profiles (general agricultural knowledge, NOT district-verified data)
CROP_PROFILES: Dict[str, Dict[str, str]] = {
    "mango": {
        "display_name": "Mango",
        "water_demand_tier": "low_to_moderate",
        "water_demand_label": "Low to moderate (perennial orchard crop)",
        "soil_and_drainage": "Deep, well-drained loamy/alluvial/red soils; sensitive to waterlogging and high salinity.",
        "climate_notes": "Warm tropical/sub-tropical climate with a distinct dry period before flowering; excess unseasonal rain can affect flowering/fruit set.",
        "irrigation_notes": "Critical during establishment (first 2–3 years) and fruit development; mature orchards tolerate dry spells well and work efficiently with drip irrigation.",
    },
    "rice": {
        "display_name": "Rice (Paddy)",
        "water_demand_tier": "high",
        "water_demand_label": "High (water-intensive crop)",
        "soil_and_drainage": "Clayey or clay-loam soils with low permeability that can retain standing water.",
        "climate_notes": "High seasonal moisture/rainfall demand; relies heavily on reliable canal or groundwater irrigation in low-rainfall zones.",
        "irrigation_notes": "Substantially higher seasonal groundwater demand than orchard or millet crops; techniques like Alternate Wetting and Drying (AWD) or DSR can reduce pumping.",
    },
    "sugarcane": {
        "display_name": "Sugarcane",
        "water_demand_tier": "high",
        "water_demand_label": "Very high (long-duration perennial/annual crop)",
        "soil_and_drainage": "Deep, fertile, well-drained loamy soils.",
        "climate_notes": "Long growing season spanning dry summer months, creating sustained year-round irrigation demand.",
        "irrigation_notes": "Frequently a major driver of groundwater stress where flood-irrigated; subsurface/surface drip irrigation significantly lowers applied water.",
    },
    "banana": {
        "display_name": "Banana",
        "water_demand_tier": "high",
        "water_demand_label": "High (shallow-rooted perennial)",
        "soil_and_drainage": "Deep, rich, well-drained loamy soil; poor drainage harms root health.",
        "climate_notes": "Warm, humid climate with frequent moisture needs throughout the year.",
        "irrigation_notes": "Requires frequent, regular irrigation; drip fertigation is strongly preferred over flood irrigation.",
    },
    "coconut": {
        "display_name": "Coconut",
        "water_demand_tier": "moderate_to_high",
        "water_demand_label": "Moderate to high (year-round perennial)",
        "soil_and_drainage": "Deep sandy loam, alluvial, or red sandy loam with good drainage.",
        "climate_notes": "Humid tropical climate; prolonged dry spells reduce nut yield without supplemental irrigation.",
        "irrigation_notes": "Responds well to basin/drip irrigation and moisture-conservation mulching.",
    },
    "arecanut": {
        "display_name": "Arecanut",
        "water_demand_tier": "moderate_to_high",
        "water_demand_label": "Moderate to high (perennial palm)",
        "soil_and_drainage": "Deep, well-drained gravelly loam or lateritic soils; sensitive to waterlogging.",
        "climate_notes": "Humid tropics with steady soil moisture requirements in dry months.",
        "irrigation_notes": "Micro-irrigation (drip/micro-sprinkler) is widely used to manage summer water stress.",
    },
    "wheat": {
        "display_name": "Wheat",
        "water_demand_tier": "moderate",
        "water_demand_label": "Moderate (Rabi winter seasonal crop)",
        "soil_and_drainage": "Well-drained loam to clay-loam soils.",
        "climate_notes": "Cool winter (Rabi) growing season with several critical irrigation stages (CRI, tillering, grain filling).",
        "irrigation_notes": "Requires assured winter irrigation where residual soil moisture is insufficient.",
    },
    "maize": {
        "display_name": "Maize",
        "water_demand_tier": "moderate",
        "water_demand_label": "Moderate (seasonal Kharif/Rabi crop)",
        "soil_and_drainage": "Well-drained fertile loamy soils; sensitive to waterlogging.",
        "climate_notes": "Adaptable across Kharif (rainfed/supplemental) and irrigated Rabi seasons.",
        "irrigation_notes": "Less water-intensive than paddy or sugarcane; sensitive to moisture stress around flowering/silking.",
    },
    "cotton": {
        "display_name": "Cotton",
        "water_demand_tier": "moderate",
        "water_demand_label": "Moderate (long-season Kharif crop)",
        "soil_and_drainage": "Deep black cotton soils (Vertisols) or well-drained alluvial soils.",
        "climate_notes": "Warm climate with dry weather during boll opening.",
        "irrigation_notes": "Often grown rainfed with supplemental irrigation; drip irrigation helps stabilize yields in semi-arid areas.",
    },
    "groundnut": {
        "display_name": "Groundnut",
        "water_demand_tier": "low_to_moderate",
        "water_demand_label": "Low to moderate (oilseed crop)",
        "soil_and_drainage": "Well-drained sandy loam or light red soils (essential for pegging/pod development).",
        "climate_notes": "Warm growing conditions; thrives as a Kharif rainfed crop or irrigated summer/Rabi crop.",
        "irrigation_notes": "Substantially lower water demand than paddy; sprinkler/drip improves water-use efficiency.",
    },
    "millets": {
        "display_name": "Millets (Ragi / Jowar / Bajra)",
        "water_demand_tier": "low",
        "water_demand_label": "Low (drought-resilient dryland cereals)",
        "soil_and_drainage": "Adaptable to light red, sandy loam, and shallow soils with good drainage.",
        "climate_notes": "Well suited to semi-arid and moderate-rainfall zones with erratic monsoon distribution.",
        "irrigation_notes": "Generally rainfed or requires only minimal life-saving supplemental irrigation.",
    },
    "pulses": {
        "display_name": "Pulses (Tur / Gram / Lentils)",
        "water_demand_tier": "low",
        "water_demand_label": "Low (nitrogen-fixing dryland/Rabi crops)",
        "soil_and_drainage": "Well-drained loamy to clay-loam soils; sensitive to waterlogging and salinity.",
        "climate_notes": "Often grown on residual post-monsoon moisture or light Kharif rainfall.",
        "irrigation_notes": "Requires far less irrigation than rice or sugarcane (typically 1–2 supplemental irrigations if needed).",
    },
    "vegetables": {
        "display_name": "Vegetables (Horticultural crops)",
        "water_demand_tier": "moderate",
        "water_demand_label": "Moderate (short-duration, frequent irrigation)",
        "soil_and_drainage": "Fertile, well-drained loamy soils.",
        "climate_notes": "Varies widely by vegetable crop and season.",
        "irrigation_notes": "Short roots require frequent light irrigation; drip + mulching significantly reduces groundwater waste.",
    },
    "coffee": {
        "display_name": "Coffee",
        "water_demand_tier": "moderate",
        "water_demand_label": "Moderate (shade-grown perennial)",
        "soil_and_drainage": "Deep, friable, well-drained acidic loamy forest soils on slopes.",
        "climate_notes": "Cool-to-moderate humid hill/plateau zones with well-distributed rainfall and blossom showers.",
        "irrigation_notes": "Typically rainfed with targeted blossom/backing sprinkler irrigation where dry spells occur.",
    },
}


def _district_snapshot(record: GroundwaterData) -> Dict[str, Any]:
    """Compute official C+NC metrics and sector shares for a single district record."""
    official = calculate_official_cgwb_metrics(
        extractable_c_ham=record.extractable_c_ham,
        extractable_nc_ham=record.extractable_nc_ham,
        extractable_pq_ham=record.extractable_pq_ham,
        extraction_c_ham=record.extraction_c_ham,
        extraction_nc_ham=record.extraction_nc_ham,
        extraction_pq_ham=record.extraction_pq_ham,
        official_stage_pct=record.stage_of_gw_extraction,
        total_extractable_ham=record.annual_extractable_gw_resource,
        total_extraction_ham=record.gw_extraction,
    )
    tot_ext = record.gw_extraction
    irr_share = (
        round((record.extraction_irrigation_ham / tot_ext) * 100.0, 2)
        if tot_ext and tot_ext > 0 and record.extraction_irrigation_ham is not None
        else None
    )
    dom_share = (
        round((record.extraction_domestic_ham / tot_ext) * 100.0, 2)
        if tot_ext and tot_ext > 0 and record.extraction_domestic_ham is not None
        else None
    )
    ind_share = (
        round((record.extraction_industrial_ham / tot_ext) * 100.0, 2)
        if tot_ext and tot_ext > 0 and record.extraction_industrial_ham is not None
        else None
    )

    off_stage = official.get("reported_official_stage_pct")
    if off_stage is None:
        off_stage = official.get("computed_official_stage_pct")
    off_cat = official.get("official_category") or {}

    allowed_nums: List[float] = []
    for val in (
        record.rainfall_mm, record.ground_water_recharge, record.annual_extractable_gw_resource,
        record.gw_extraction, record.stage_of_gw_extraction, record.net_gw_availability,
        record.extraction_irrigation_ham, record.extraction_domestic_ham, record.extraction_industrial_ham,
        official.get("fresh_extraction_ham"), official.get("fresh_extractable_ham"),
        official.get("reported_official_stage_pct"), official.get("computed_official_stage_pct"),
        official.get("safe_target_extraction_ham"), official.get("required_reduction_to_safe_ham"),
        official.get("required_reduction_to_safe_pct"), official.get("total_based_stage_pct"),
        irr_share, dom_share, ind_share,
    ):
        if val is not None:
            allowed_nums.append(float(val))
            allowed_nums.append(abs(float(val)))

    return {
        "official": official,
        "official_stage": off_stage,
        "official_category": off_cat,
        "irr_share": irr_share,
        "dom_share": dom_share,
        "ind_share": ind_share,
        "allowed_nums": allowed_nums,
    }


def _format_district_gw_bullets(record: GroundwaterData, snap: Dict[str, Any]) -> List[str]:
    off = snap["official"]
    stage = snap["official_stage"]
    cat = snap["official_category"]
    lines = []
    if stage is not None and cat:
        lines.append(
            f"- **Official CGWB Status (C+NC Freshwater):** **{stage:.2f}%** ({cat.get('emoji', '')} **{cat.get('category', 'N/A')}**)"
        )
    if record.rainfall_mm is not None:
        lines.append(f"- **Assessed Rainfall:** **{record.rainfall_mm:.2f} mm**")
    if record.gw_extraction is not None and record.annual_extractable_gw_resource is not None:
        lines.append(
            f"- **Total Extraction vs. Extractable:** **{record.gw_extraction:.2f} ham** / **{record.annual_extractable_gw_resource:.2f} ham**"
        )
    if record.extraction_irrigation_ham is not None:
        sh = f" ({snap['irr_share']:.1f}% of total draft)" if snap["irr_share"] is not None else ""
        lines.append(f"- **Irrigation Extraction:** **{record.extraction_irrigation_ham:.2f} ham**{sh}")
    if record.net_gw_availability is not None:
        lines.append(f"- **Net GW Availability for Future Use:** **{record.net_gw_availability:.2f} ham**")
    if off.get("has_pq_zone"):
        lines.append(
            f"- **PQ-Zone Note:** District includes Poor Quality (PQ) groundwater; official C+NC stage ({stage:.2f}%) differs from Total-extraction stage ({off['total_based_stage_pct']:.2f}%)."
        )
    return lines


def _format_state_gw_bullets(state_name: str, stats: Dict[str, Any]) -> Tuple[List[str], List[float]]:
    avg_stage = stats.get("avg_extraction_stage", 0.0)
    cat = classify_cgwb(avg_stage)
    lines = [
        f"- **State Average Official Stage ({stats['total_records']} districts):** **{avg_stage:.2f}%** ({cat['emoji']} **{cat['category']}**)",
        f"- **State Average Rainfall:** **{stats['avg_rainfall']:.2f} mm**",
        f"- **State Average Net Availability:** **{stats['avg_net_availability']:.2f} ham**",
    ]
    nums = [
        round(stats["avg_extraction_stage"], 2),
        round(stats["avg_rainfall"], 2),
        round(stats["avg_net_availability"], 2),
        round(stats["avg_recharge"], 2),
    ]
    return lines, nums


def build_agricultural_suitability_response(
    crop: Optional[str],
    district_record: Optional[GroundwaterData],
    state_name: Optional[str],
    state_stats: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Build a grounded, evidence-separated agricultural suitability answer.
    Asks for clarification if no location is known in current query or context.
    """
    crop_key = (crop or "").lower().strip()
    profile = CROP_PROFILES.get(crop_key)
    crop_display = profile["display_name"] if profile else (crop_key.title() if crop_key else "this crop")

    if not district_record and not state_stats:
        msg = (
            f"Which district or location are you considering for **{crop_display.lower()}** cultivation?\n\n"
            "Once you share a district (for example, *Mysuru*, *Bengaluru Rural*, or *Anakapalli*), "
            "I can check its INGRES/CGWB groundwater extraction stage, rainfall, and net availability "
            "and explain what those conditions indicate alongside missing local soil/farm checks."
        )
        return {
            "response": msg,
            "suggestions": [
                f"Is {crop_display.lower()} good in Mysuru?" if crop_key else "Is mango good in Mysuru?",
                "What is the groundwater status of Mysuru?",
                "Which crops require less water?",
            ],
            "extra_allowed": [],
            "cgwb_cat": None,
            "pending_clarification": {"intent": "ask_agricultural_suitability", "crop": crop_key or None},
        }

    lines: List[str] = []
    extra_allowed: List[float] = []
    cgwb_cat: Optional[Dict[str, str]] = None

    if district_record:
        loc_label = f"{district_record.district.title()}, {district_record.state.title()}"
        snap = _district_snapshot(district_record)
        cgwb_cat = snap["official_category"] or None
        extra_allowed.extend(snap["allowed_nums"])
        stage = snap["official_stage"]

        lines.append(f"🌱 **Agricultural & Groundwater Assessment: {crop_display} in {loc_label}**\n")
        lines.append("**1. Verified INGRES / CGWB Groundwater Data (District Level)**")
        lines.extend(_format_district_gw_bullets(district_record, snap))

        # Derived resource implication
        lines.append("\n**2. What the Groundwater Data Indicates (Derived)**")
        if stage is None:
            lines.append("- Extraction stage data is missing in the dataset for this district, so groundwater headroom cannot be quantified.")
        elif stage <= CGWB_SAFE_THRESHOLD:
            lines.append(
                f"- Because official extraction stage is **{stage:.2f}%** (within the **70%** Safe ceiling) with **{district_record.net_gw_availability or 0.0:.2f} ham** net future availability, district-level groundwater resources currently have headroom for moderate supplemental irrigation."
            )
        elif stage <= 90.0:
            lines.append(
                f"- Official extraction stage is **{stage:.2f}% (SEMI-CRITICAL)** — district groundwater is approaching heavy utilization, so low-to-moderate water-demand crops or efficient drip irrigation are preferable to high-water crops."
            )
        else:
            lines.append(
                f"- Official extraction stage is **{stage:.2f}% ({cgwb_cat.get('category', 'STRESSED')})**, exceeding the Safe threshold; expanding groundwater-dependent irrigation faces high resource stress unless offset by reductions elsewhere."
            )

        lines.append(
            "- *Important distinction:* CGWB extraction stage is a **district-wide water-balance ratio** — it does **not** independently confirm farm-level borewell yield, declining water tables, or agronomic crop viability."
        )
    else:
        loc_label = state_name.title()
        bullets, nums = _format_state_gw_bullets(state_name, state_stats)
        extra_allowed.extend(nums)
        cgwb_cat = classify_cgwb(state_stats.get("avg_extraction_stage", 0.0))
        stage = state_stats.get("avg_extraction_stage")

        lines.append(f"🌱 **Agricultural & Groundwater Assessment: {crop_display} in {loc_label} (State Overview)**\n")
        lines.append("**1. Verified INGRES / CGWB State Summary**")
        lines.extend(bullets)
        lines.append("\n**2. Derived Resource Context**")
        lines.append(
            f"- State-wide averages mask large district-to-district variation; specify a district in {loc_label} for district-level extraction and rainfall figures."
        )

    # 3. General Agricultural Knowledge
    lines.append("\n**3. General Agricultural Context (Not District-Verified Data)**")
    if profile:
        lines.append(f"- **Crop Water Demand:** {profile['water_demand_label']}")
        lines.append(f"- **Soil & Drainage:** {profile['soil_and_drainage']}")
        lines.append(f"- **Climate & Seasonal Fit:** {profile['climate_notes']}")
        lines.append(f"- **Irrigation Practice:** {profile['irrigation_notes']}")
    else:
        lines.append(
            f"- Crop-specific agronomic parameters for **{crop_display}** are not in INGRES. Evaluate its seasonal water demand, rooting depth, and drainage sensitivity before planting."
        )

    # 4. Missing data & local verification
    lines.append("\n**4. Information Unavailable in INGRES (Verify Locally)**")
    lines.append(
        "- **Soil type, depth, pH & drainage**, **water quality (salinity/fluoride)**, **local borewell depth / piezometer trends**, **seasonal rainfall distribution**, and **sub-district (taluk/block) stress pockets** are not available in this dataset."
    )

    # 5. Qualified Practical Conclusion
    lines.append("\n**5. Qualified Conclusion**")
    if district_record and stage is not None:
        tier = profile["water_demand_tier"] if profile else "unknown"
        if stage <= CGWB_SAFE_THRESHOLD and tier in ("low", "low_to_moderate", "moderate"):
            lines.append(
                f"- **Groundwater conditions in {district_record.district.title()} appear supportive** of {crop_display.lower()} from a district water-balance standpoint (especially with efficient irrigation), **provided** local soil drainage, water quality, and farm borewell yield are verified with local horticulture/agriculture officers."
            )
        elif stage <= CGWB_SAFE_THRESHOLD and tier in ("moderate_to_high", "high"):
            lines.append(
                f"- While {district_record.district.title()} is **SAFE** at the district average (**{stage:.2f}%**), **{crop_display.lower()}** has a **{profile['water_demand_label'].lower()}** footprint — confirm canal/surface-water support, sub-district block status, and efficient irrigation rather than assuming unlimited groundwater."
            )
        elif stage > CGWB_SAFE_THRESHOLD and tier in ("low", "low_to_moderate"):
            lines.append(
                f"- Because {district_record.district.title()} is already **{cgwb_cat.get('category', 'stressed')} ({stage:.2f}%)**, lower-water crops like **{crop_display.lower()}** (paired with drip/micro-irrigation) put less pressure on groundwater than water-intensive crops, **subject to** local soil, water-table, and quality checks."
            )
        elif stage > CGWB_SAFE_THRESHOLD and tier in ("moderate_to_high", "high"):
            lines.append(
                f"- Growing a **high-water crop ({crop_display.lower()})** in a **{cgwb_cat.get('category', 'stressed')} ({stage:.2f}%)** district risks worsening groundwater extraction pressure unless supported by non-groundwater surface supply and strict water-saving practices."
            )
        else:
            lines.append(
                f"- Use the district groundwater status (**{stage:.2f}%**) as a screening indicator and verify crop suitability with local agricultural extension / KVK records before committing."
            )
    else:
        lines.append(
            "- Specify a district for sharper groundwater screening, and confirm local soil, drainage, and water-table conditions with local agricultural authorities."
        )

    suggestions = ["What about rice?", "Which crops require less water?", "Is it sustainable?"]
    if district_record:
        suggestions.append(f"What if irrigation increases in {district_record.district.title()}?")

    return {
        "response": "\n".join(lines),
        "suggestions": suggestions,
        "extra_allowed": extra_allowed,
        "cgwb_cat": cgwb_cat,
        "pending_clarification": None,
    }


def build_crop_water_requirements_response(
    crop: Optional[str],
    district_record: Optional[GroundwaterData],
) -> Dict[str, Any]:
    """Answer questions about low-water crops or specific crop water requirements."""
    extra_allowed: List[float] = []
    cgwb_cat = None
    lines: List[str] = ["🌾 **Crop Water Requirements & Lower-Water Alternatives**\n"]

    if district_record:
        snap = _district_snapshot(district_record)
        cgwb_cat = snap["official_category"] or None
        extra_allowed.extend(snap["allowed_nums"])
        stage = snap["official_stage"]
        lines.append(
            f"📍 **Context Location ({district_record.district.title()}, {district_record.state.title()}):** "
            f"Official stage **{stage:.2f}%** ({cgwb_cat.get('category', 'N/A')}), Rainfall **{district_record.rainfall_mm:.2f} mm**.\n"
            if stage is not None and district_record.rainfall_mm is not None else
            f"📍 **Context Location ({district_record.district.title()}, {district_record.state.title()})**.\n"
        )

    if crop and crop in CROP_PROFILES:
        p = CROP_PROFILES[crop]
        lines.append(f"**{p['display_name']} — General Water Profile:**")
        lines.append(f"- **Water Demand Tier:** {p['water_demand_label']}")
        lines.append(f"- **Soil/Drainage:** {p['soil_and_drainage']}")
        lines.append(f"- **Irrigation Note:** {p['irrigation_notes']}\n")

    lines.append("**General Crop Water-Demand Tiers (Agronomic Reference, Not District-Specific):**")
    lines.append("- **Lower Water Demand:** Millets (*ragi, jowar, bajra*), Pulses (*tur, gram, lentils*), Groundnut (oilseeds).")
    lines.append("- **Low to Moderate Demand:** Mango and similar dryland-adapted orchard crops (once established, especially under drip).")
    lines.append("- **Moderate Demand:** Maize, Wheat (Rabi), Cotton, Vegetables (with micro-irrigation).")
    lines.append("- **High Water Demand:** Rice (paddy), Sugarcane, Banana (require substantially more seasonal irrigation).\n")
    lines.append(
        "📋 *Note:* Exact crop evapotranspiration (`mm/season`) depends on local climate, soil texture, sowing window, and irrigation method — verify local crop calendars with your district KVK / Agriculture Department."
    )

    return {
        "response": "\n".join(lines),
        "suggestions": [
            "Is it good to grow mango crops there?" if district_record else "What is the groundwater status of Mysuru?",
            "What about rice?",
            "Would increasing irrigation put pressure on groundwater?",
        ],
        "extra_allowed": extra_allowed,
        "cgwb_cat": cgwb_cat,
    }


def build_irrigation_impact_response(
    district_record: Optional[GroundwaterData],
    state_name: Optional[str],
    state_stats: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """Explain how increasing or modifying irrigation affects groundwater pressure."""
    lines: List[str] = ["🚿 **Irrigation Pressure & Groundwater Impact**\n"]
    extra_allowed: List[float] = []
    cgwb_cat = None

    if district_record:
        snap = _district_snapshot(district_record)
        cgwb_cat = snap["official_category"] or None
        extra_allowed.extend(snap["allowed_nums"])
        stage = snap["official_stage"]

        lines.append(f"**1. Verified INGRES Data — {district_record.district.title()}, {district_record.state.title()}**")
        lines.extend(_format_district_gw_bullets(district_record, snap))
        lines.append("\n**2. Derived Irrigation Pressure Assessment**")
        if snap["irr_share"] is not None:
            lines.append(
                f"- Irrigation already accounts for **{snap['irr_share']:.1f}%** (**{district_record.extraction_irrigation_ham:.2f} ham**) of total groundwater extraction here."
            )
        if stage is not None:
            if stage > CGWB_SAFE_THRESHOLD:
                lines.append(
                    f"- Because official extraction stage is already **{stage:.2f}% ({cgwb_cat.get('category', 'STRESSED')})**, increasing groundwater irrigation will further raise extraction stage and widen the gap above the **70%** Safe ceiling."
                )
            else:
                lines.append(
                    f"- Even though current stage is **{stage:.2f}% (SAFE)**, sustained increases in groundwater pumping reduce net future availability (**{district_record.net_gw_availability or 0.0:.2f} ham**) and can push the district toward Semi-Critical (**>70%**) over time."
                )
    elif state_stats and state_name:
        bullets, nums = _format_state_gw_bullets(state_name, state_stats)
        extra_allowed.extend(nums)
        cgwb_cat = classify_cgwb(state_stats.get("avg_extraction_stage", 0.0))
        lines.append(f"**1. Verified State Context — {state_name.title()}**")
        lines.extend(bullets)
        lines.append("\n**2. General Irrigation Impact**")
        lines.append("- Increasing groundwater-fed irrigation directly raises extraction draft relative to annual extractable recharge.")
    else:
        lines.append("**General Hydrological Relationship:**")
        lines.append("- Expanding groundwater-irrigated area or pumping hours directly increases extraction (`ham`), raising the CGWB Stage of Extraction (`Extraction / Extractable × 100`).")

    lines.append("\n**3. Practical Caveats & Missing Data**")
    lines.append("- **Surface vs. Groundwater:** Expanding *canal/surface-water* irrigation affects groundwater differently than expanding *tubewell/borewell* pumping.")
    lines.append("- **Energy vs. Water Distinction:** Upgrading to efficient or solar pumps reduces electricity/diesel use per m³, **not** total groundwater extraction unless pumping hours or volume are limited.")
    lines.append("- **Missing Local Evidence:** Well/tubewell counts (MI Census), drip/sprinkler adoption, and piezometer water-level decline trends are not in INGRES; use the **🔬 What-If Analysis** or **🩺 Diagnostics** tabs to model exact % scenarios.")

    return {
        "response": "\n".join(lines),
        "suggestions": ["Which crops require less water?", "Is it sustainable?", "Karnataka groundwater"],
        "extra_allowed": extra_allowed,
        "cgwb_cat": cgwb_cat,
    }


def build_sustainability_response(
    district_record: Optional[GroundwaterData],
    state_name: Optional[str],
    state_stats: Optional[Dict[str, Any]],
    crop: Optional[str] = None,
) -> Dict[str, Any]:
    """Assess groundwater sustainability honestly without claiming farm-level proof."""
    if not district_record and not state_stats:
        return {
            "response": (
                "Which district or state would you like me to evaluate for groundwater sustainability?\n\n"
                "Ask for a district like *Mysuru*, *Bengaluru Rural*, or *Aurangabad*, and I will check its "
                "official CGWB extraction stage, sectoral extraction balance, and net future availability."
            ),
            "suggestions": ["What is the groundwater status of Mysuru?", "Karnataka groundwater", "Which crops require less water?"],
            "extra_allowed": [],
            "cgwb_cat": None,
            "pending_clarification": {"intent": "ask_sustainability", "crop": crop},
        }

    lines: List[str] = ["⚖️ **Groundwater Sustainability Assessment**\n"]
    extra_allowed: List[float] = []
    cgwb_cat = None

    if district_record:
        snap = _district_snapshot(district_record)
        cgwb_cat = snap["official_category"] or None
        extra_allowed.extend(snap["allowed_nums"])
        stage = snap["official_stage"]
        off = snap["official"]

        lines.append(f"**1. Verified CGWB Assessment — {district_record.district.title()}, {district_record.state.title()}**")
        lines.extend(_format_district_gw_bullets(district_record, snap))

        lines.append("\n**2. Sustainability Interpretation (Derived)**")
        if stage is not None:
            if stage <= CGWB_SAFE_THRESHOLD:
                lines.append(
                    f"- At **{stage:.2f}% (SAFE)**, current district-wide extraction remains below the **70%** CGWB threshold and leaves **{district_record.net_gw_availability or 0.0:.2f} ham** net availability."
                )
            else:
                lines.append(
                    f"- At **{stage:.2f}% ({cgwb_cat.get('category', 'STRESSED')})**, current extraction is **not sustainable** at the district balance level and requires a **{off['required_reduction_to_safe_ham']:.2f} ham ({off['required_reduction_to_safe_pct']:.1f}%)** reduction to reach the **70%** Safe ceiling."
                )
    else:
        bullets, nums = _format_state_gw_bullets(state_name, state_stats)
        extra_allowed.extend(nums)
        cgwb_cat = classify_cgwb(state_stats.get("avg_extraction_stage", 0.0))
        lines.append(f"**1. Verified State Context — {state_name.title()}**")
        lines.extend(bullets)

    lines.append("\n**3. What Cannot Be Proven from INGRES Alone (Missing Evidence)**")
    lines.append("- **Actual Water-Table Decline:** Multi-year piezometer depth-to-water-level trends (`m bgl/yr`) are not loaded in INGRES; high extraction stage does not automatically quantify water-table decline rates, and Safe stage does not rule out localized decline.")
    lines.append("- **Local Scale Limits:** District aggregates do not prove farm-level or taluk/block-level sustainability, and groundwater quality tagging is currently empty (`0/726` districts).")

    return {
        "response": "\n".join(lines),
        "suggestions": ["Which crops require less water?", "Would increasing irrigation put pressure on groundwater?"],
        "extra_allowed": extra_allowed,
        "cgwb_cat": cgwb_cat,
        "pending_clarification": None,
    }


def build_trends_causes_response(
    district_record: Optional[GroundwaterData],
    state_name: Optional[str],
    state_stats: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """Explain observed sectoral extraction drivers and missing multi-year trend data."""
    if not district_record and not state_stats:
        return {
            "response": (
                "Which district or state would you like me to analyze for groundwater extraction drivers?\n\n"
                "For full multi-factor analysis, you can also open the **🩺 Diagnostics** tab."
            ),
            "suggestions": ["Bengaluru Urban groundwater", "Punjab extraction", "Mysuru groundwater"],
            "extra_allowed": [],
            "cgwb_cat": None,
            "pending_clarification": {"intent": "ask_trends_causes", "crop": None},
        }

    lines: List[str] = ["🔎 **Groundwater Stress Drivers & Trend Evidence**\n"]
    extra_allowed: List[float] = []
    cgwb_cat = None

    if district_record:
        snap = _district_snapshot(district_record)
        cgwb_cat = snap["official_category"] or None
        extra_allowed.extend(snap["allowed_nums"])
        lines.append(f"**1. Verified Sectoral Breakdown — {district_record.district.title()}, {district_record.state.title()}**")
        lines.extend(_format_district_gw_bullets(district_record, snap))
        if district_record.extraction_domestic_ham is not None and snap["dom_share"] is not None:
            lines.append(f"- **Domestic Extraction:** **{district_record.extraction_domestic_ham:.2f} ham** ({snap['dom_share']:.1f}%)")
        if district_record.extraction_industrial_ham is not None and snap["ind_share"] is not None:
            lines.append(f"- **Industrial Extraction:** **{district_record.extraction_industrial_ham:.2f} ham** ({snap['ind_share']:.1f}%)")
    else:
        bullets, nums = _format_state_gw_bullets(state_name, state_stats)
        extra_allowed.extend(nums)
        cgwb_cat = classify_cgwb(state_stats.get("avg_extraction_stage", 0.0))
        lines.append(f"**1. Verified State Context — {state_name.title()}**")
        lines.extend(bullets)

    lines.append("\n**2. Evidence Limits (Trends vs. Snapshot)**")
    lines.append("- **Single-Cycle Snapshot Only:** The loaded INGRES workbook covers **2024–2025** only — multi-year extraction trends, piezometer water-level time series, crop mix, and well/pump counts are **unavailable**, so causal attribution beyond observed sectoral shares requires external data (check the **🩺 Diagnostics** tab for the full gap breakdown).")

    return {
        "response": "\n".join(lines),
        "suggestions": ["Is it sustainable?", "Which crops require less water?"],
        "extra_allowed": extra_allowed,
        "cgwb_cat": cgwb_cat,
        "pending_clarification": None,
    }


def build_general_groundwater_response(assessment_year: str) -> Dict[str, Any]:
    """Answer general conceptual groundwater questions without fabricating location data."""
    msg = (
        "💧 **INGRES / CGWB Groundwater Assessment Guide**\n\n"
        "The Central Ground Water Board (CGWB) classifies areas using the **Stage of Groundwater Extraction (%)** "
        "(`Freshwater C+NC Extraction / Annual Extractable Freshwater Resource × 100`):\n"
        "- 🟢 **Safe:** `<= 70%`\n"
        "- 🟡 **Semi-Critical:** `70% – 90%`\n"
        "- 🟠 **Critical:** `90% – 100%`\n"
        "- 🔴 **Over-Exploited:** `> 100%`\n\n"
        f"Our database covers **726 districts** across **37 states/UTs** from the **{assessment_year}** assessment.\n"
        "Ask about any state or district, crop water suitability in an area, or switch to **🩺 Diagnostics** and **🔬 What-If Analysis** for sector-level breakdowns."
    )
    return {
        "response": msg,
        "suggestions": [
            "What is the groundwater status of Mysuru?",
            "Which crops require less water?",
            "Show all states",
        ],
        "extra_allowed": [726.0, 37.0],
        "cgwb_cat": None,
    }
