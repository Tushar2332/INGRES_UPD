"""
Main Diagnostic Engine orchestrator for INGRES_UPD.
Connects verified 2024-2025 CGWB INGRES records, official C+NC Safe-target math,
evidence-gated interventions, multi-sector mathematical What-If scenarios,
and numeric response verification.
"""

from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session

from .. import crud, data_processor
from ..models import GroundwaterData
from ..verifier import verify_response
from ..whatif import CGWB_SAFE_THRESHOLD, calculate_official_cgwb_metrics
from .intervention_engine import analyze_interventions
from .scenario_simulator import build_default_scenarios, simulate_sector_scenarios
from .schemas import (
    DiagnosticRequest,
    DiagnosticResponse,
    MultiScenarioRequest,
    MultiScenarioResponse,
    RechargeBreakdownItem,
    SectorBreakdownItem,
    TaggedStatement,
)


def _pct(part: Optional[float], whole: Optional[float]) -> Optional[float]:
    if part is None or whole is None or whole <= 0:
        return None
    return round((part / whole) * 100.0, 2)


def _collect_record_numeric_values(record: GroundwaterData, official: Dict[str, Any], scenarios) -> List[float]:
    """Collect all verified DB and derived numbers for verifier.py validation."""
    vals: List[float] = []
    for attr in (
        "rainfall_mm", "total_geographical_area", "recharge_worthy_area_ha", "hilly_area_ha",
        "ground_water_recharge", "annual_extractable_gw_resource", "gw_extraction",
        "stage_of_gw_extraction", "net_gw_availability", "env_flows_ham",
        "extraction_domestic_ham", "extraction_industrial_ham", "extraction_irrigation_ham",
        "domestic_alloc_2025_ham", "recharge_rainfall_ham", "recharge_canals_ham",
        "recharge_sw_irrigation_ham", "recharge_gw_irrigation_ham",
        "recharge_tanks_ponds_ham", "recharge_wcs_ham", "recharge_pipelines_ham",
        "recharge_sewages_flash_flood_ham",
        "extractable_c_ham", "extractable_nc_ham", "extractable_pq_ham",
        "extraction_c_ham", "extraction_nc_ham", "extraction_pq_ham",
    ):
        v = getattr(record, attr, None)
        if v is not None:
            vals.append(float(v))

    for k in (
        "fresh_extractable_ham", "fresh_extraction_ham", "computed_official_stage_pct",
        "reported_official_stage_pct", "safe_target_extraction_ham",
        "required_reduction_to_safe_ham", "required_reduction_to_safe_pct",
        "total_based_stage_pct",
    ):
        v = official.get(k)
        if v is not None:
            vals.append(float(v))

    # Add shares and scenario figures
    tot_ext = record.gw_extraction
    if tot_ext and tot_ext > 0:
        for part in (record.extraction_irrigation_ham, record.extraction_domestic_ham, record.extraction_industrial_ham):
            if part is not None:
                vals.append(round((part / tot_ext) * 100.0, 2))

    if record.total_geographical_area and record.recharge_worthy_area_ha is not None:
        vals.append(round((record.recharge_worthy_area_ha / record.total_geographical_area) * 100.0, 1))

    tot_rech = record.ground_water_recharge
    if tot_rech and tot_rech > 0:
        for part in (
            record.recharge_rainfall_ham, record.recharge_canals_ham,
            record.recharge_sw_irrigation_ham, record.recharge_gw_irrigation_ham,
            record.recharge_tanks_ponds_ham, record.recharge_wcs_ham,
            record.recharge_pipelines_ham, record.recharge_sewages_flash_flood_ham,
        ):
            if part is not None:
                vals.append(round((part / tot_rech) * 100.0, 2))

    for sc in scenarios:
        for v in (
            sc.baseline_total_extraction_ham, sc.revised_total_extraction_ham,
            sc.baseline_official_extraction_ham, sc.revised_official_extraction_ham,
            sc.baseline_official_stage_pct, sc.simulated_official_stage_pct,
            sc.baseline_total_stage_pct, sc.simulated_total_stage_pct,
            sc.reduction_achieved_ham, sc.reduction_achieved_pct,
            sc.remaining_reduction_to_safe_ham, sc.remaining_reduction_to_safe_pct,
            sc.inputs.irrigation_pct_change, sc.inputs.domestic_pct_change, sc.inputs.industrial_pct_change,
            abs(sc.inputs.irrigation_pct_change), abs(sc.inputs.domestic_pct_change), abs(sc.inputs.industrial_pct_change),
        ):
            if v is not None:
                vals.append(float(v))
                vals.append(abs(float(v)))

    # Standard static constants referenced in statements (e.g. 0/726)
    vals.extend([0.0, 726.0, 2025.0])
    return vals


def resolve_district_or_raise(db: Session, state: str, district: str) -> GroundwaterData:
    """Resolve district using Phase 1 exact -> normalized -> unambiguous partial matching."""
    record, ambiguous = crud.get_whatif_lookup_result(db, state, district)
    if ambiguous:
        raise ValueError(
            f"AMBIGUOUS:Ambiguous district '{district}' in state '{state}'. "
            f"Matching districts: {', '.join(ambiguous)}"
        )
    if not record:
        raise LookupError(f"No data found for district '{district}' in state '{state}'")
    return record


def run_multi_scenario_whatif(db: Session, req: MultiScenarioRequest) -> MultiScenarioResponse:
    """Run multi-sector What-If scenario comparison for a verified district."""
    record = resolve_district_or_raise(db, req.state, req.district)
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
    results = simulate_sector_scenarios(record, req.scenarios)
    return MultiScenarioResponse(
        state=record.state,
        district=record.district,
        assessment_year=str(data_processor.ASSESSMENT_YEAR),
        data_source=data_processor.DATA_SOURCE,
        official_cgwb_metrics=official,
        scenarios=results,
    )


def run_diagnostic(db: Session, req: DiagnosticRequest) -> DiagnosticResponse:
    """Execute full evidence-based groundwater diagnosis for a district."""
    record = resolve_district_or_raise(db, req.state, req.district)

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

    # ── Sectoral extraction breakdown ────────────────────────────────────────
    total_ext = record.gw_extraction
    fresh_ext = official.get("fresh_extraction_ham")

    sector_defs = [
        ("Irrigation", record.extraction_irrigation_ham, record.extraction_irrigation_c_ham, record.extraction_irrigation_nc_ham),
        ("Domestic", record.extraction_domestic_ham, record.extraction_domestic_c_ham, record.extraction_domestic_nc_ham),
        ("Industrial", record.extraction_industrial_ham, record.extraction_industrial_c_ham, record.extraction_industrial_nc_ham),
    ]
    sectors: List[SectorBreakdownItem] = []
    sector_shares: Dict[str, Optional[float]] = {}
    for label, tot_v, c_v, nc_v in sector_defs:
        fresh_v = ((c_v or 0.0) + (nc_v or 0.0)) if (c_v is not None or nc_v is not None) else (
            tot_v if not official.get("has_pq_zone") else None
        )
        sh_tot = _pct(tot_v, total_ext)
        sh_fresh = _pct(fresh_v, fresh_ext) if fresh_v is not None and fresh_ext else None
        sector_shares[label.lower()] = sh_tot
        sectors.append(
            SectorBreakdownItem(
                sector=label,
                total_ham=round(tot_v, 2) if tot_v is not None else None,
                fresh_cnc_ham=round(fresh_v, 2) if fresh_v is not None else None,
                share_of_total_pct=sh_tot,
                share_of_fresh_pct=sh_fresh,
            )
        )

    sectors_sorted = sorted(sectors, key=lambda s: s.total_ham if s.total_ham is not None else -1.0, reverse=True)
    dominant_sector = (
        sectors_sorted[0].sector
        if sectors_sorted and (sectors_sorted[0].total_ham or 0.0) > 0
        else None
    )

    # ── Recharge source breakdown ────────────────────────────────────────────
    total_rech = record.ground_water_recharge
    recharge_defs = [
        ("rainfall_recharge", "Rainfall Recharge", record.recharge_rainfall_ham),
        ("surface_water_irrigation", "Surface Water Irrigation", record.recharge_sw_irrigation_ham),
        ("ground_water_irrigation", "Groundwater Irrigation", record.recharge_gw_irrigation_ham),
        ("canals", "Canals", record.recharge_canals_ham),
        ("tanks_and_ponds", "Tanks and Ponds", record.recharge_tanks_ponds_ham),
        ("water_conservation_structures", "Water Conservation Structures", record.recharge_wcs_ham),
        ("pipelines", "Pipelines", record.recharge_pipelines_ham),
        ("sewages_flash_flood", "Sewages & Flash Flood Channels", record.recharge_sewages_flash_flood_ham),
    ]
    recharge_sources: List[RechargeBreakdownItem] = []
    recharge_shares: Dict[str, Optional[float]] = {}
    for key, label, amt in recharge_defs:
        sh = _pct(amt, total_rech)
        recharge_shares[key] = sh
        recharge_sources.append(
            RechargeBreakdownItem(
                source=label,
                amount_ham=round(amt, 2) if amt is not None else None,
                share_pct=sh,
            )
        )

    # ── Current condition statements ─────────────────────────────────────────
    off_stage = official.get("reported_official_stage_pct") or official.get("computed_official_stage_pct")
    off_cat = (official.get("official_category") or {}).get("category") or "UNKNOWN"

    current_statements: List[TaggedStatement] = [
        TaggedStatement(
            text=(
                f"{record.district.title()}, {record.state.title()} is officially classified by CGWB as "
                f"{off_cat} with an official Stage of Groundwater Extraction of {off_stage:.2f}% "
                f"(Freshwater C+NC extraction {official['fresh_extraction_ham']:.2f} ham / extractable "
                f"{official['fresh_extractable_ham']:.2f} ham)."
                if off_stage is not None else
                f"Official extraction stage is unavailable in the INGRES dataset for {record.district.title()}."
            ),
            classification="VERIFIED_FACT",
            evidence_refs=["stage_of_gw_extraction", "extractable_c_ham", "extractable_nc_ham", "extraction_c_ham", "extraction_nc_ham"],
        ),
        TaggedStatement(
            text=(
                f"Total groundwater extraction across all uses is {total_ext:.2f} ham against "
                f"total annual extractable resource of {record.annual_extractable_gw_resource:.2f} ham "
                f"(Net availability for future use: {record.net_gw_availability:.2f} ham)."
                if total_ext is not None and record.annual_extractable_gw_resource is not None and record.net_gw_availability is not None else
                "Partial total water-balance fields are unavailable in the INGRES dataset."
            ),
            classification="VERIFIED_FACT",
            evidence_refs=["gw_extraction", "annual_extractable_gw_resource", "net_gw_availability"],
        ),
    ]

    # ── Major contributors statements ────────────────────────────────────────
    contrib_statements: List[TaggedStatement] = []
    if dominant_sector:
        top = sectors_sorted[0]
        contrib_statements.append(
            TaggedStatement(
                text=(
                    f"{top.sector} is the largest groundwater consumer at {top.total_ham:.2f} ham "
                    f"({top.share_of_total_pct:.2f}% of total extraction)."
                    if top.share_of_total_pct is not None else
                    f"{top.sector} is the largest groundwater consumer at {top.total_ham:.2f} ham."
                ),
                classification="DERIVED_CALCULATION",
                evidence_refs=[f"extraction_{top.sector.lower()}_ham", "gw_extraction"],
            )
        )
        for sec in sectors_sorted[1:]:
            if sec.total_ham is not None:
                contrib_statements.append(
                    TaggedStatement(
                        text=(
                            f"{sec.sector} accounts for {sec.total_ham:.2f} ham "
                            f"({sec.share_of_total_pct:.2f}% of total extraction)."
                            if sec.share_of_total_pct is not None else
                            f"{sec.sector} accounts for {sec.total_ham:.2f} ham."
                        ),
                        classification="DERIVED_CALCULATION",
                        evidence_refs=[f"extraction_{sec.sector.lower()}_ham", "gw_extraction"],
                    )
                )

    # ── Required improvement to reach Safe (<= 70%) ──────────────────────────
    req_ham = official.get("required_reduction_to_safe_ham")
    req_pct = official.get("required_reduction_to_safe_pct")
    safe_target_ham = official.get("safe_target_extraction_ham")
    already_safe = off_stage is not None and off_stage <= CGWB_SAFE_THRESHOLD

    req_statements: List[TaggedStatement] = []
    if off_stage is None or safe_target_ham is None:
        req_statements.append(
            TaggedStatement(
                text="Safe-threshold target calculation cannot be completed because official C+NC extractable data is missing or zero.",
                classification="DATA_MISSING",
                evidence_refs=["extractable_c_ham", "extractable_nc_ham"],
            )
        )
    elif already_safe:
        req_statements.append(
            TaggedStatement(
                text=(
                    f"District is already within the CGWB Safe threshold (<= {CGWB_SAFE_THRESHOLD:.0f}%) at "
                    f"{off_stage:.2f}%. Target ceiling extraction is {safe_target_ham:.2f} ham; "
                    "required reduction is 0.00 ham (0.00%)."
                ),
                classification="DERIVED_CALCULATION",
                evidence_refs=["stage_of_gw_extraction", "extractable_c_ham", "extractable_nc_ham"],
            )
        )
    else:
        req_statements.append(
            TaggedStatement(
                text=(
                    f"To reach the CGWB Safe threshold (<= {CGWB_SAFE_THRESHOLD:.0f}%), official Freshwater (C+NC) "
                    f"extraction must fall from {official['fresh_extraction_ham']:.2f} ham to <= {safe_target_ham:.2f} ham, "
                    f"requiring a reduction of {req_ham:.2f} ham ({req_pct:.2f}%)."
                ),
                classification="DERIVED_CALCULATION",
                evidence_refs=["extraction_c_ham", "extraction_nc_ham", "extractable_c_ham", "extractable_nc_ham"],
            )
        )

    # ── Interventions, hypotheses, limitations, next steps ───────────────────
    analysis = analyze_interventions(record, official, sector_shares, recharge_shares)

    # ── Multi-sector What-If Scenarios ───────────────────────────────────────
    default_used = req.scenarios is None
    scenario_inputs = req.scenarios or build_default_scenarios(
        official_stage_pct=off_stage,
        required_reduction_pct=req_pct,
        dominant_sector=dominant_sector,
        uniform_pct_change=req.pct_change,
    )
    scenario_results = simulate_sector_scenarios(record, scenario_inputs)

    impact_statements: List[TaggedStatement] = [
        TaggedStatement(
            text=(
                f"Evaluated {len(scenario_results)} mathematical extraction scenario(s) on the "
                f"{'exact C+NC official basis' if all(s.simulation_basis == 'EXACT_CGWB_C_NC' for s in scenario_results) else 'estimated mathematical basis'}. "
                "Scenarios show mathematical stage outcomes only and do not verify real-world adoptability."
            ),
            classification="DERIVED_CALCULATION",
        )
    ]
    for s in scenario_results:
        if s.simulated_official_stage_pct is not None and s.simulated_official_category:
            if (s.reduction_achieved_ham or 0.0) >= 0:
                change_txt = (
                    f"reduction achieved = {s.reduction_achieved_ham:.2f} ham "
                    f"({s.reduction_achieved_pct:.2f}%)"
                )
            else:
                change_txt = (
                    f"extraction increase = {abs(s.reduction_achieved_ham):.2f} ham "
                    f"({abs(s.reduction_achieved_pct):.2f}%)"
                )
            impact_statements.append(
                TaggedStatement(
                    text=(
                        f"{s.name}: simulated official stage = {s.simulated_official_stage_pct:.2f}% "
                        f"({s.simulated_official_category['category']}); {change_txt}; "
                        f"remaining reduction to Safe = {s.remaining_reduction_to_safe_ham:.2f} ham."
                    ),
                    classification="DERIVED_CALCULATION",
                    assumption=s.assumption_note,
                )
            )

    # ── Evidence registry ────────────────────────────────────────────────────
    evidence: List[TaggedStatement] = (
        current_statements
        + contrib_statements
        + req_statements
        + analysis["hypotheses"]
    )

    # ── Numeric verification via verifier.py ─────────────────────────────────
    all_text_chunks = [st.text for st in evidence + impact_statements + analysis["limitations"]] + [
        f"{it.rationale} {' '.join(it.supporting_evidence)}"
        for it in analysis["interventions"]
    ]
    extra_allowed = _collect_record_numeric_values(record, official, scenario_results)
    ver = verify_response("\n".join(all_text_chunks), [], extra_allowed=extra_allowed)

    return DiagnosticResponse(
        location={
            "state": record.state,
            "district": record.district,
            "assessment_year": str(data_processor.ASSESSMENT_YEAR),
            "data_source": data_processor.DATA_SOURCE,
            "geo_resolution": "district",
            "source_s_no": record.s_no,
        },
        current_condition={
            "official_cgwb": official,
            "total_summary": {
                "rainfall_mm": record.rainfall_mm,
                "total_geographical_area_ha": record.total_geographical_area,
                "recharge_worthy_area_ha": record.recharge_worthy_area_ha,
                "hilly_area_ha": record.hilly_area_ha,
                "ground_water_recharge_ham": record.ground_water_recharge,
                "env_flows_ham": record.env_flows_ham,
                "annual_extractable_gw_resource_ham": record.annual_extractable_gw_resource,
                "gw_extraction_ham": record.gw_extraction,
                "net_gw_availability_ham": record.net_gw_availability,
                "domestic_alloc_2025_ham": record.domestic_alloc_2025_ham,
            },
            "statements": current_statements,
        },
        major_contributors={
            "dominant_sector": dominant_sector,
            "sectors": sectors_sorted,
            "recharge_sources": recharge_sources,
            "statements": contrib_statements,
        },
        required_improvement={
            "safe_threshold_pct": CGWB_SAFE_THRESHOLD,
            "official_basis": official.get("official_basis"),
            "current_official_stage_pct": off_stage,
            "current_official_extraction_ham": official.get("fresh_extraction_ham"),
            "target_safe_extraction_ham": safe_target_ham,
            "required_reduction_ham": req_ham,
            "required_reduction_pct": req_pct,
            "already_safe": already_safe,
            "statements": req_statements,
        },
        recommended_interventions=analysis["interventions"],
        evidence=evidence,
        expected_impact={
            "default_scenarios_evaluated": default_used,
            "scenarios": scenario_results,
            "statements": impact_statements,
        },
        limitations=analysis["limitations"],
        next_steps=analysis["next_steps"],
        data_gaps_summary=analysis["data_gaps_summary"],
        verified=ver["verified"],
        verification_issues=ver["issues"],
    )
