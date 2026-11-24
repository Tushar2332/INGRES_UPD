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
    if annual_extractable <= 0:
        raise ValueError("annual_extractable_gw_resource must be > 0 for simulation")

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
