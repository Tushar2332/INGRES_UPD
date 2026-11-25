"""
Sector-wise What-If Scenario Simulator.

Strictly distinguishes:
  1. Official CGWB Freshwater (C + NC) extraction & stage calculations
  2. Total (C + NC + PQ) extraction calculations
  3. Mathematical scenario outputs vs. practically feasible / validated outcomes
"""

from typing import Any, Dict, List, Optional, Tuple
from ..models import GroundwaterData
from ..whatif import CGWB_SAFE_THRESHOLD, calculate_official_cgwb_metrics, classify_cgwb
from .schemas import ScenarioInput, ScenarioResult


def _sector_cnc_availability(
    record: GroundwaterData,
    official: Dict[str, Any],
) -> Tuple[bool, Dict[str, float], str]:
    """
    Determine whether exact sector-wise Freshwater (C + NC) data is available
    and reconciles with official C + NC extraction.
    """
    fresh_extractable = official.get("fresh_extractable_ham") or 0.0
    fresh_extraction = official.get("fresh_extraction_ham") or 0.0

    if fresh_extractable <= 0.0:
        return False, {}, "Freshwater (C + NC) annual extractable resource is missing or <= 0."

    # Check if any C or NC sector data exists
    raw_pairs = [
        ("irrigation", record.extraction_irrigation_c_ham, record.extraction_irrigation_nc_ham, record.extraction_irrigation_ham),
        ("domestic", record.extraction_domestic_c_ham, record.extraction_domestic_nc_ham, record.extraction_domestic_ham),
        ("industrial", record.extraction_industrial_c_ham, record.extraction_industrial_nc_ham, record.extraction_industrial_ham),
    ]

    has_any_cnc = any(c is not None or nc is not None for _, c, nc, _ in raw_pairs)
    has_pq = bool(official.get("has_pq_zone"))

    sector_fresh: Dict[str, float] = {}
    if has_any_cnc:
        for key, c_val, nc_val, _tot_val in raw_pairs:
            sector_fresh[key] = (c_val or 0.0) + (nc_val or 0.0)
        sum_fresh = sum(sector_fresh.values())
        if abs(sum_fresh - fresh_extraction) <= 1.0:
            return True, sector_fresh, "Exact sector-wise Freshwater (C + NC) extraction reconciled."
        return (
            False,
            sector_fresh,
            (
                f"Sector-wise C+NC sum ({sum_fresh:.2f} ham) differs from reported "
                f"C+NC total ({fresh_extraction:.2f} ham) by > 1.0 ham."
            ),
        )

    # Non-PQ districts: PQ == 0 so Total sectoral extraction equals Freshwater C+NC
    if not has_pq and (
        record.extraction_irrigation_ham is not None
        or record.extraction_domestic_ham is not None
        or record.extraction_industrial_ham is not None
    ):
        for key, _, _, tot_val in raw_pairs:
            sector_fresh[key] = tot_val or 0.0
        sum_tot = sum(sector_fresh.values())
        if abs(sum_tot - fresh_extraction) <= 1.0:
            return True, sector_fresh, "No PQ zone present; total sector extraction equals Freshwater (C + NC)."

    return False, {}, "Sector-wise C + NC breakdown unavailable for PQ-zone district."


def build_default_scenarios(
    official_stage_pct: Optional[float],
    required_reduction_pct: Optional[float],
    dominant_sector: Optional[str],
    uniform_pct_change: Optional[float] = None,
) -> List[ScenarioInput]:
    """Build relevant default mathematical scenarios from current stress level."""
    scenarios: List[ScenarioInput] = []

    if uniform_pct_change is not None and uniform_pct_change != 0.0:
        scenarios.append(
            ScenarioInput(
                name=f"User Uniform Change ({uniform_pct_change:+.1f}%)",
                irrigation_pct_change=uniform_pct_change,
                domestic_pct_change=uniform_pct_change,
                industrial_pct_change=uniform_pct_change,
            )
        )

    if official_stage_pct is not None and official_stage_pct > CGWB_SAFE_THRESHOLD:
        scenarios.extend([
            ScenarioInput(
                name="Scenario A: Irrigation-Focused (-20%)",
                irrigation_pct_change=-20.0,
                domestic_pct_change=0.0,
                industrial_pct_change=0.0,
            ),
            ScenarioInput(
                name="Scenario B: Irrigation (-15%) + Domestic (-10%)",
                irrigation_pct_change=-15.0,
                domestic_pct_change=-10.0,
                industrial_pct_change=0.0,
            ),
            ScenarioInput(
                name="Scenario C: Multi-Sector (-20% Irr, -10% Ind, -5% Dom)",
                irrigation_pct_change=-20.0,
                domestic_pct_change=-5.0,
                industrial_pct_change=-10.0,
            ),
        ])
        if required_reduction_pct and required_reduction_pct > 0:
            req = min(100.0, round(required_reduction_pct, 2))
            scenarios.append(
                ScenarioInput(
                    name=f"Scenario D: Uniform Safe-Target Check (-{req:.1f}%)",
                    irrigation_pct_change=-req,
                    domestic_pct_change=-req,
                    industrial_pct_change=-req,
                )
            )
    else:
        dom_label = (dominant_sector or "Irrigation").title()
        scenarios.extend([
            ScenarioInput(
                name="Scenario A: Conservation (-10% Irrigation)",
                irrigation_pct_change=-10.0,
                domestic_pct_change=0.0,
                industrial_pct_change=0.0,
            ),
            ScenarioInput(
                name=f"Scenario B: Demand Growth Stress (+15% {dom_label})",
                irrigation_pct_change=15.0 if dom_label == "Irrigation" else 0.0,
                domestic_pct_change=15.0 if dom_label == "Domestic" else 0.0,
                industrial_pct_change=15.0 if dom_label == "Industrial" else 0.0,
            ),
            ScenarioInput(
                name="Scenario C: Balanced Growth (+10% All Sectors)",
                irrigation_pct_change=10.0,
                domestic_pct_change=10.0,
                industrial_pct_change=10.0,
            ),
        ])

    return scenarios


def simulate_sector_scenarios(
    record: GroundwaterData,
    scenarios: List[ScenarioInput],
) -> List[ScenarioResult]:
    """
    Evaluate one or more sector-wise What-If scenarios for a district.
    Computes both Official CGWB Freshwater (C+NC) stage (when exact sector C+NC
    data is available) and Total (C+NC+PQ) extraction stage.
    """
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

    exact_cnc_ok, sector_fresh_map, cnc_reason = _sector_cnc_availability(record, official)

    base_total_sectors: Dict[str, Optional[float]] = {
        "irrigation": round(record.extraction_irrigation_ham, 2) if record.extraction_irrigation_ham is not None else None,
        "domestic": round(record.extraction_domestic_ham, 2) if record.extraction_domestic_ham is not None else None,
        "industrial": round(record.extraction_industrial_ham, 2) if record.extraction_industrial_ham is not None else None,
    }
    base_total_sum = sum(v for v in base_total_sectors.values() if v is not None)
    base_total_ext = record.gw_extraction if record.gw_extraction is not None else base_total_sum
    total_extractable = record.annual_extractable_gw_resource
    fresh_extractable = official["fresh_extractable_ham"]
    fresh_extraction = official["fresh_extraction_ham"]
    safe_target_fresh = official["safe_target_extraction_ham"]

    has_pq = bool(official["has_pq_zone"])
    results: List[ScenarioResult] = []

    for sc in scenarios:
        # 1. Total-extraction revised sectors (always computable if sector totals exist)
        rev_tot_irr = max(0.0, (record.extraction_irrigation_ham or 0.0) * (1.0 + sc.irrigation_pct_change / 100.0))
        rev_tot_dom = max(0.0, (record.extraction_domestic_ham or 0.0) * (1.0 + sc.domestic_pct_change / 100.0))
        rev_tot_ind = max(0.0, (record.extraction_industrial_ham or 0.0) * (1.0 + sc.industrial_pct_change / 100.0))
        rev_total_ext = rev_tot_irr + rev_tot_dom + rev_tot_ind

        # Preserve any minor unallocated residual if base_total_ext differed slightly
        residual_tot = max(0.0, (base_total_ext or 0.0) - (
            (record.extraction_irrigation_ham or 0.0)
            + (record.extraction_domestic_ham or 0.0)
            + (record.extraction_industrial_ham or 0.0)
        ))
        rev_total_ext_adj = rev_total_ext + residual_tot

        base_tot_stage = (
            round((base_total_ext / total_extractable) * 100.0, 2)
            if total_extractable and total_extractable > 0 and base_total_ext is not None
            else None
        )
        sim_tot_stage = (
            round((rev_total_ext_adj / total_extractable) * 100.0, 2)
            if total_extractable and total_extractable > 0
            else None
        )
        sim_tot_cat = classify_cgwb(sim_tot_stage) if sim_tot_stage is not None else None

        # 2. Official C + NC calculations
        if exact_cnc_ok:
            b_irr_f = sector_fresh_map.get("irrigation", 0.0)
            b_dom_f = sector_fresh_map.get("domestic", 0.0)
            b_ind_f = sector_fresh_map.get("industrial", 0.0)
            r_irr_f = max(0.0, b_irr_f * (1.0 + sc.irrigation_pct_change / 100.0))
            r_dom_f = max(0.0, b_dom_f * (1.0 + sc.domestic_pct_change / 100.0))
            r_ind_f = max(0.0, b_ind_f * (1.0 + sc.industrial_pct_change / 100.0))
            rev_fresh_ext = r_irr_f + r_dom_f + r_ind_f

            sim_off_stage = round((rev_fresh_ext / fresh_extractable) * 100.0, 2) if fresh_extractable > 0 else None
            sim_off_cat = classify_cgwb(sim_off_stage) if sim_off_stage is not None else None

            red_ham = round(fresh_extraction - rev_fresh_ext, 2)
            red_pct = round((red_ham / fresh_extraction) * 100.0, 2) if fresh_extraction > 0 else 0.0

            if safe_target_fresh is not None:
                rem_ham = round(max(0.0, rev_fresh_ext - safe_target_fresh), 2)
                rem_pct = round((rem_ham / rev_fresh_ext) * 100.0, 2) if rev_fresh_ext > 0 and rem_ham > 0 else 0.0
                reaches_safe = (sim_off_stage is not None) and (sim_off_stage <= CGWB_SAFE_THRESHOLD)
            else:
                rem_ham, rem_pct, reaches_safe = None, None, None

            base_fresh_sectors = {
                "irrigation": round(b_irr_f, 2),
                "domestic": round(b_dom_f, 2),
                "industrial": round(b_ind_f, 2),
            }
            rev_fresh_sectors = {
                "irrigation": round(r_irr_f, 2),
                "domestic": round(r_dom_f, 2),
                "industrial": round(r_ind_f, 2),
            }
            sim_basis = "EXACT_CGWB_C_NC"
            status_label = "Mathematical Scenario (Exact C+NC Official Basis)"
            assumption_note = (
                "Sectoral percentage changes are applied directly to official Freshwater (C + NC) "
                "extraction. Assumes percentage reductions apply uniformly across C and NC zones."
            )
            limitation_note = (
                "Mathematical simulation only; practical feasibility requires field data on "
                "well/pump counts, cropping patterns, and aquifer response (currently DATA_MISSING)."
            )
            if has_pq:
                limitation_note += (
                    " District also contains Poor Quality (PQ) zones: Total-extraction stage "
                    f"({sim_tot_stage}%) differs from official C+NC stage ({sim_off_stage}%)."
                )
        else:
            # Estimate / Mathematical fallback when exact C+NC sector reconciliation is unavailable
            sim_basis = "ESTIMATE_MATHEMATICAL_SCENARIO"
            status_label = "Mathematical Scenario (Estimate — Sector C+NC Split Unavailable)"
            base_fresh_sectors = {"irrigation": None, "domestic": None, "industrial": None}
            rev_fresh_sectors = {"irrigation": None, "domestic": None, "industrial": None}

            # Estimate proportional impact on C+NC if fresh_extractable > 0
            scale_ratio = (
                (rev_total_ext_adj / base_total_ext)
                if base_total_ext and base_total_ext > 0
                else None
            )
            if scale_ratio is not None and fresh_extractable > 0 and fresh_extraction > 0:
                est_fresh_ext = fresh_extraction * scale_ratio
                sim_off_stage = round((est_fresh_ext / fresh_extractable) * 100.0, 2)
                sim_off_cat = classify_cgwb(sim_off_stage)
                red_ham = round(fresh_extraction - est_fresh_ext, 2)
                red_pct = round((1.0 - scale_ratio) * 100.0, 2)
                rem_ham = round(max(0.0, est_fresh_ext - (safe_target_fresh or 0.0)), 2) if safe_target_fresh is not None else None
                rem_pct = round((rem_ham / est_fresh_ext) * 100.0, 2) if rem_ham and est_fresh_ext > 0 else 0.0
                reaches_safe = sim_off_stage <= CGWB_SAFE_THRESHOLD
            else:
                est_fresh_ext = None
                sim_off_stage, sim_off_cat = None, None
                red_ham = round((base_total_ext or 0.0) - rev_total_ext_adj, 2) if base_total_ext is not None else None
                red_pct = round((red_ham / base_total_ext) * 100.0, 2) if red_ham is not None and base_total_ext else None
                rem_ham, rem_pct, reaches_safe = None, None, None

            rev_fresh_ext = round(est_fresh_ext, 2) if est_fresh_ext is not None else None
            assumption_note = (
                "Estimate only: assumes total sectoral extraction changes scale Freshwater (C + NC) "
                f"extraction proportionally ({cnc_reason})."
            )
            limitation_note = (
                f"Exact simulated official CGWB stage cannot be guaranteed ({cnc_reason}). "
                "Practical feasibility also remains unverified without MI Census, crop, and piezometer data."
            )

        results.append(
            ScenarioResult(
                name=sc.name,
                inputs=sc,
                simulation_basis=sim_basis,
                simulation_status_label=status_label,
                assumption_note=assumption_note,
                limitation_note=limitation_note,
                baseline_sector_total_ham=base_total_sectors,
                revised_sector_total_ham={
                    "irrigation": round(rev_tot_irr, 2),
                    "domestic": round(rev_tot_dom, 2),
                    "industrial": round(rev_tot_ind, 2),
                },
                baseline_sector_fresh_ham=base_fresh_sectors,
                revised_sector_fresh_ham=rev_fresh_sectors,
                baseline_total_extraction_ham=round(base_total_ext, 2) if base_total_ext is not None else None,
                revised_total_extraction_ham=round(rev_total_ext_adj, 2),
                baseline_official_extraction_ham=round(fresh_extraction, 2) if exact_cnc_ok or fresh_extraction > 0 else None,
                revised_official_extraction_ham=round(rev_fresh_ext, 2) if rev_fresh_ext is not None else None,
                baseline_official_stage_pct=official.get("reported_official_stage_pct"),
                simulated_official_stage_pct=sim_off_stage,
                simulated_official_category=sim_off_cat,
                baseline_total_stage_pct=base_tot_stage,
                simulated_total_stage_pct=sim_tot_stage,
                simulated_total_category=sim_tot_cat,
                reduction_achieved_ham=red_ham,
                reduction_achieved_pct=red_pct,
                remaining_reduction_to_safe_ham=rem_ham,
                remaining_reduction_to_safe_pct=rem_pct,
                reaches_safe=reaches_safe,
            )
        )

    return results
