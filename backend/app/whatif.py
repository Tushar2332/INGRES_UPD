"""
whatif.py — What-If Simulation Engine for INGRES Chatbot (Review 2)

Formula:
  new_extraction = current_extraction × (1 + pct_change / 100)
  new_stage      = (new_extraction / annual_extractable) × 100

CGWB Classification:
  Safe          : stage ≤ 70%
  Semi-Critical : 70% < stage ≤ 90%
  Critical      : 90% < stage ≤ 100%
  Over-Exploited: stage > 100%
"""
import math
from typing import Dict, Any, Optional


# ─── CGWB Thresholds ─────────────────────────────────────────────────────────
CGWB_SAFE_THRESHOLD        = 70.0
CGWB_SEMI_CRITICAL_THRESHOLD = 90.0
CGWB_CRITICAL_THRESHOLD    = 100.0


def classify_cgwb(stage: float) -> Dict[str, str]:
    """
    Classify groundwater extraction stage into CGWB category.

    Returns:
        { category: str, color: str, emoji: str, css_class: str }
    """
    if stage <= CGWB_SAFE_THRESHOLD:
        return {'category': 'SAFE', 'color': '#10b981', 'emoji': '🟢', 'css_class': 'cgwb-safe'}
    elif stage <= CGWB_SEMI_CRITICAL_THRESHOLD:
        return {'category': 'SEMI-CRITICAL', 'color': '#f59e0b', 'emoji': '🟡', 'css_class': 'cgwb-semi-critical'}
    elif stage <= CGWB_CRITICAL_THRESHOLD:
        return {'category': 'CRITICAL', 'color': '#f97316', 'emoji': '🟠', 'css_class': 'cgwb-critical'}
    else:
        return {'category': 'OVER-EXPLOITED', 'color': '#ef4444', 'emoji': '🔴', 'css_class': 'cgwb-over-exploited'}


def simulate_whatif(
    current_extraction: float,
    annual_extractable: float,
    pct_change: float,
) -> Dict[str, Any]:
    """
    Simulate the effect of changing groundwater extraction by pct_change%.

    Args:
        current_extraction  : Current GW extraction (ham) from DB
        annual_extractable  : Annual extractable GW resource (ham) from DB
        pct_change          : % change (negative = reduction, positive = increase)

    Returns:
        Full simulation result dict.
    """
    if not math.isfinite(current_extraction) or current_extraction < 0:
        raise ValueError("gw_extraction must be a finite non-negative number")
    if not math.isfinite(annual_extractable) or annual_extractable <= 0:
        raise ValueError("annual_extractable_gw_resource must be > 0 for simulation")
    if not math.isfinite(pct_change) or pct_change < -100.0:
        raise ValueError("pct_change must be a finite number >= -100")

    # Core calculation
    new_extraction = max(0.0, current_extraction * (1 + pct_change / 100))

    current_stage = (current_extraction / annual_extractable) * 100
    new_stage     = (new_extraction / annual_extractable) * 100

    current_category = classify_cgwb(current_stage)
    new_category     = classify_cgwb(new_stage)

    # How much reduction needed to drop below 100% (stop being Over-Exploited)
    reduction_to_non_over: Optional[float] = None
    if current_stage > CGWB_CRITICAL_THRESHOLD:
        reduction_to_non_over = round(
            (current_extraction - annual_extractable) / current_extraction * 100, 2
        )

    # How much reduction needed to reach Safe (≤70%)
    reduction_to_safe: Optional[float] = None
    if current_stage > CGWB_SAFE_THRESHOLD:
        safe_extraction = CGWB_SAFE_THRESHOLD / 100 * annual_extractable
        reduction_to_safe = round(
            (current_extraction - safe_extraction) / current_extraction * 100, 2
        )

    return {
        # Raw values
        'current_extraction_ham':  round(current_extraction, 2),
        'new_extraction_ham':      round(new_extraction, 2),
        'annual_extractable_ham':  round(annual_extractable, 2),
        # Stages
        'current_stage':  round(current_stage, 2),
        'new_stage':      round(new_stage, 2),
        'stage_change':   round(new_stage - current_stage, 2),
        # Applied change
        'pct_change_applied': pct_change,
        # Categories
        'current_category': current_category,
        'new_category':     new_category,
        'category_changed': current_category['category'] != new_category['category'],
        # Guidance
        'reduction_needed_to_non_overexploited_pct': reduction_to_non_over,
        'reduction_needed_to_safe_pct':              reduction_to_safe,
        # Chart data for frontend
        'chart_data': {
            'type': 'whatif_comparison',
            'data': [
                {
                    'name': 'Current',
                    'stage': round(current_stage, 2),
                    'extraction': round(current_extraction, 2),
                    'category': current_category['category'],
                    'color': current_category['color'],
                },
                {
                    'name': 'Simulated',
                    'stage': round(new_stage, 2),
                    'extraction': round(new_extraction, 2),
                    'category': new_category['category'],
                    'color': new_category['color'],
                },
            ],
            'thresholds': {
                'safe': CGWB_SAFE_THRESHOLD,
                'semi_critical': CGWB_SEMI_CRITICAL_THRESHOLD,
                'critical': CGWB_CRITICAL_THRESHOLD,
            },
        },
    }


def build_whatif_response(
    result: Dict[str, Any],
    district: str,
    state: str,
    pct_change: float,
) -> str:
    """Build a clear, human-readable explanation of the What-If simulation."""
    direction   = "reduction" if pct_change < 0 else "increase"
    abs_pct     = abs(pct_change)
    curr_cat    = result['current_category']
    new_cat     = result['new_category']
    stage_delta = result['stage_change']
    delta_dir   = "decrease" if stage_delta < 0 else "increase"

    lines = [
        f"**What-If Analysis: {district.title()}, {state.title()}**",
        "",
        f"📊 **Current Stage:** {result['current_stage']:.2f}%  "
        f"{curr_cat['emoji']} **{curr_cat['category']}**",
        f"🔧 **Applied Change:** {abs_pct:.1f}% {direction} in groundwater extraction",
        f"📉 **Simulated Stage:** {result['new_stage']:.2f}%  "
        f"{new_cat['emoji']} **{new_cat['category']}**",
        f"📐 **Stage Change:** {abs(stage_delta):.2f}% {delta_dir}",
    ]

    if result['category_changed']:
        lines.append(
            f"\n✨ **Category transition:** {curr_cat['category']} → {new_cat['category']}"
        )
    else:
        lines.append(f"\n📌 **Category remains:** {curr_cat['category']}")

    r2non = result['reduction_needed_to_non_overexploited_pct']
    r2safe = result['reduction_needed_to_safe_pct']

    if r2non is not None:
        lines.append(
            f"\n💡 To exit **Over-Exploited** status (stage ≤100%), "
            f"a **{r2non:.1f}%** extraction reduction is needed."
        )

    if r2safe is not None:
        lines.append(
            f"💡 To reach **Safe** category (stage ≤70%), "
            f"a **{r2safe:.1f}%** extraction reduction is required."
        )

    lines.append(
        f"\n📋 *Calculation based on actual INGRES database values. "
        f"No database records were modified.*"
    )

    return "\n".join(lines)


def calculate_official_cgwb_metrics(
    extractable_c_ham: Optional[float],
    extractable_nc_ham: Optional[float],
    extractable_pq_ham: Optional[float],
    extraction_c_ham: Optional[float],
    extraction_nc_ham: Optional[float],
    extraction_pq_ham: Optional[float],
    official_stage_pct: Optional[float],
    total_extractable_ham: Optional[float] = None,
    total_extraction_ham: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Compute official CGWB Stage of Extraction and Safe-threshold targets using
    freshwater Command + Non-Command (C + NC) zones, kept strictly separate from
    total-extraction What-If simulations.

    Official CGWB methodology excludes Poor Quality (PQ / saline) zones from the
    overall Stage of Ground Water Extraction (%) denominator/numerator.
    """
    extbl_c = extractable_c_ham or 0.0
    extbl_nc = extractable_nc_ham or 0.0
    extbl_pq = extractable_pq_ham or 0.0

    extr_c = extraction_c_ham or 0.0
    extr_nc = extraction_nc_ham or 0.0
    extr_pq = extraction_pq_ham or 0.0

    fresh_extractable = extbl_c + extbl_nc
    fresh_extraction = extr_c + extr_nc
    has_pq_zone = (extbl_pq > 0.0) or (extr_pq > 0.0)

    computed_official_stage: Optional[float] = None
    if fresh_extractable > 0.0:
        computed_official_stage = round((fresh_extraction / fresh_extractable) * 100.0, 4)

    reported_stage = round(official_stage_pct, 4) if official_stage_pct is not None else None
    effective_stage = reported_stage if reported_stage is not None else computed_official_stage
    official_category = classify_cgwb(effective_stage) if effective_stage is not None else None

    safe_target_extraction_ham: Optional[float] = None
    required_reduction_ham: Optional[float] = None
    required_reduction_pct: Optional[float] = None

    if fresh_extractable > 0.0:
        safe_target_extraction_ham = round((CGWB_SAFE_THRESHOLD / 100.0) * fresh_extractable, 2)
        if fresh_extraction > safe_target_extraction_ham:
            red_ham = fresh_extraction - safe_target_extraction_ham
            required_reduction_ham = round(red_ham, 2)
            required_reduction_pct = round((red_ham / fresh_extraction) * 100.0, 2) if fresh_extraction > 0 else 0.0
        else:
            required_reduction_ham = 0.0
            required_reduction_pct = 0.0

    total_based_stage: Optional[float] = None
    if total_extractable_ham and total_extractable_ham > 0 and total_extraction_ham is not None:
        total_based_stage = round((total_extraction_ham / total_extractable_ham) * 100.0, 4)

    pq_note = None
    if has_pq_zone:
        pq_note = (
            "District includes Poor Quality (PQ) groundwater zones. Official CGWB Stage "
            "is computed on Freshwater (C + NC) zones only, whereas total-extraction What-If "
            "uses Total (C + NC + PQ) values."
        )

    return {
        "official_basis": "C + NC (Freshwater)",
        "fresh_extractable_ham": round(fresh_extractable, 2),
        "fresh_extraction_ham": round(fresh_extraction, 2),
        "extractable_c_ham": round(extbl_c, 2),
        "extractable_nc_ham": round(extbl_nc, 2),
        "extractable_pq_ham": round(extbl_pq, 2),
        "extraction_c_ham": round(extr_c, 2),
        "extraction_nc_ham": round(extr_nc, 2),
        "extraction_pq_ham": round(extr_pq, 2),
        "has_pq_zone": has_pq_zone,
        "computed_official_stage_pct": computed_official_stage,
        "reported_official_stage_pct": reported_stage,
        "official_category": official_category,
        "safe_threshold_pct": CGWB_SAFE_THRESHOLD,
        "safe_target_extraction_ham": safe_target_extraction_ham,
        "required_reduction_to_safe_ham": required_reduction_ham,
        "required_reduction_to_safe_pct": required_reduction_pct,
        "total_extractable_ham": round(total_extractable_ham, 2) if total_extractable_ham is not None else None,
        "total_extraction_ham": round(total_extraction_ham, 2) if total_extraction_ham is not None else None,
        "total_based_stage_pct": total_based_stage,
        "pq_note": pq_note,
    }
