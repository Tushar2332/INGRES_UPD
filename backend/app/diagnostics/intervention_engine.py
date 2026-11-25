"""
Evidence-gated Intervention & Hypothesis Analyzer.

Selects practical candidate interventions strictly from verified 2024-2025 INGRES
records for the selected district. Never fabricates missing MI Census, electricity,
crop, or piezometer values, and never hardcodes district names.
"""

from typing import Any, Dict, List, Optional
from ..models import GroundwaterData
from ..whatif import CGWB_SAFE_THRESHOLD
from .schemas import InterventionItem, TaggedStatement


def _pct(part: Optional[float], whole: Optional[float]) -> Optional[float]:
    if part is None or whole is None or whole <= 0:
        return None
    return round((part / whole) * 100.0, 2)


def analyze_interventions(
    record: GroundwaterData,
    official: Dict[str, Any],
    sector_shares: Dict[str, Optional[float]],
    recharge_shares: Dict[str, Optional[float]],
) -> Dict[str, Any]:
    """
    Generate evidence-backed candidate interventions, unverified hypotheses,
    explicit DATA_MISSING limitations, and actionable next steps.
    """
    stage = official.get("reported_official_stage_pct") or official.get("computed_official_stage_pct")
    stressed = stage is not None and stage > CGWB_SAFE_THRESHOLD
    critical_or_over = stage is not None and stage > 90.0

    irr_ham = record.extraction_irrigation_ham
    dom_ham = record.extraction_domestic_ham
    ind_ham = record.extraction_industrial_ham
    irr_share = sector_shares.get("irrigation")
    dom_share = sector_shares.get("domestic")
    ind_share = sector_shares.get("industrial")

    interventions: List[InterventionItem] = []
    hypotheses: List[TaggedStatement] = []

    # ── 1. Irrigation Interventions ──────────────────────────────────────────
    if irr_ham is not None and irr_ham > 0 and (
        (irr_share is not None and irr_share >= 40.0) or (stressed and irr_ham >= 2000.0)
    ):
        relevance = "high" if (stressed and (irr_share or 0) >= 50.0) else ("moderate" if stressed else "preventive")
        ev = [
            f"Irrigation extraction = {irr_ham:.2f} ham ({irr_share:.2f}% of total extraction)"
            if irr_share is not None else f"Irrigation extraction = {irr_ham:.2f} ham",
        ]
        if record.recharge_gw_irrigation_ham is not None:
            ev.append(f"GW irrigation return-flow recharge = {record.recharge_gw_irrigation_ham:.2f} ham")
        if record.recharge_sw_irrigation_ham is not None:
            ev.append(f"SW irrigation recharge = {record.recharge_sw_irrigation_ham:.2f} ham")
        if record.recharge_canals_ham is not None:
            ev.append(f"Canal seepage recharge = {record.recharge_canals_ham:.2f} ham")

        if stressed:
            title = "Irrigation Demand Management, Scheduling & Micro-Irrigation Audit"
            rationale = (
                f"Irrigation is a major extraction consumer ({irr_share:.2f}% of total draft, "
                f"{irr_ham:.2f} ham) in an area above the {CGWB_SAFE_THRESHOLD:.0f}% Safe threshold. "
                "Reducing avoidable over-irrigation, improving irrigation scheduling, and evaluating "
                "drip/sprinkler conversion are primary candidates for lowering net consumptive groundwater draft."
                if irr_share is not None else
                f"Irrigation extracts {irr_ham:.2f} ham in a stressed district."
            )
        else:
            title = "Preventive Irrigation Efficiency & Conjunctive-Use Monitoring"
            rationale = (
                f"Although current official stage ({stage:.2f}%) is within Safe limits, "
                f"irrigation accounts for {irr_share:.2f}% ({irr_ham:.2f} ham) of total groundwater draft. "
                "Tracking irrigation efficiency and conjunctive surface-water use helps prevent future stress."
                if irr_share is not None else
                f"Irrigation accounts for {irr_ham:.2f} ham within Safe limits."
            )

        interventions.append(
            InterventionItem(
                id="irr_demand_management",
                title=title,
                sector="Irrigation",
                relevance=relevance,
                rationale=rationale,
                supporting_evidence=ev,
                required_feasibility_data=[
                    "6th/7th Minor Irrigation Census (dug well, shallow/deep tube-well counts & current drip/sprinkler adoption)",
                    "District crop-area & crop-water requirement records (DES / Agriculture Dept)",
                    "Sub-district (Block/Taluk) INGRES assessment-unit extraction hotspots",
                ],
                caveats=[
                    "INGRES records total irrigation draft only; crop mix and current micro-irrigation coverage are DATA_MISSING.",
                    "Improving pump/energy efficiency alone saves kWh but does not reduce groundwater extraction unless pumped hours/volumes are reduced.",
                    "Return-flow reduction from drip/sprinkler conversion can also reduce irrigation return-flow recharge; net basin balance must be checked.",
                ],
            )
        )

        hypotheses.append(
            TaggedStatement(
                text=(
                    "High irrigation extraction may involve water-intensive crops or flood irrigation "
                    "inefficiencies, which cannot be confirmed until district crop-area and MI Census "
                    "drip/sprinkler records are integrated."
                ),
                classification="HYPOTHESIS_UNVERIFIED",
                evidence_refs=ev[:1],
                assumption="Crop type and irrigation application method are not present in INGRES 2024-2025.",
            )
        )

    # ── 2. Domestic Interventions ────────────────────────────────────────────
    dom_alloc_2025 = record.domestic_alloc_2025_ham
    dom_growth_pressure = (
        dom_alloc_2025 is not None and dom_ham is not None and dom_ham > 0 and dom_alloc_2025 > dom_ham * 1.1
    )
    if dom_ham is not None and dom_ham > 0 and (
        (dom_share is not None and dom_share >= 15.0) or (stressed and dom_ham >= 2000.0) or dom_growth_pressure
    ):
        relevance = "high" if (stressed and (dom_share or 0) >= 25.0) else ("moderate" if stressed else "preventive")
        ev = [
            f"Domestic extraction = {dom_ham:.2f} ham ({dom_share:.2f}% of total extraction)"
            if dom_share is not None else f"Domestic extraction = {dom_ham:.2f} ham",
        ]
        if dom_alloc_2025 is not None:
            ev.append(f"Projected 2025 domestic allocation = {dom_alloc_2025:.2f} ham")
        if record.rainfall_mm is not None:
            ev.append(f"District rainfall = {record.rainfall_mm:.2f} mm")

        interventions.append(
            InterventionItem(
                id="dom_urban_water_mgmt",
                title="Domestic Leakage Reduction, Treated Wastewater Reuse & Urban Conjunctive Supply",
                sector="Domestic",
                relevance=relevance,
                rationale=(
                    f"Domestic groundwater extraction is significant at {dom_ham:.2f} ham "
                    f"({dom_share:.2f}% share), with projected 2025 domestic allocation at "
                    f"{dom_alloc_2025:.2f} ham. Investigating distribution network losses (NRW), "
                    "treated wastewater reuse for non-potable uses, and alternative surface supply "
                    "is directly relevant to domestic groundwater pressure."
                    if dom_alloc_2025 is not None and dom_share is not None else
                    f"Domestic groundwater extraction is {dom_ham:.2f} ham."
                ),
                supporting_evidence=ev,
                required_feasibility_data=[
                    "Municipal water utility Non-Revenue Water (NRW) / leakage audit & piped supply share",
                    "Sewage treatment plant (STP) capacity and treated-water reuse potential",
                    "Local aquifer & water-quality suitability for urban rooftop rainwater harvesting",
                ],
                caveats=[
                    "Population density, per-capita municipal supply, and borewell counts are DATA_MISSING.",
                    "Water quality tagging is completely blank (0/726) in the current INGRES workbook; quality testing is mandatory before recharge or potable reuse.",
                ],
            )
        )

    # ── 3. Industrial Interventions ──────────────────────────────────────────
    if ind_ham is not None and ind_ham > 0 and (
        (ind_share is not None and ind_share >= 10.0) or (stressed and ind_ham >= 1000.0)
    ):
        relevance = "high" if (stressed and (ind_share or 0) >= 20.0) else ("moderate" if stressed else "preventive")
        ev = [
            f"Industrial extraction = {ind_ham:.2f} ham ({ind_share:.2f}% of total extraction)"
            if ind_share is not None else f"Industrial extraction = {ind_ham:.2f} ham",
        ]
        if official.get("has_pq_zone"):
            ev.append(f"Poor Quality (PQ) extractable resource = {official['extractable_pq_ham']:.2f} ham")

        interventions.append(
            InterventionItem(
                id="ind_audit_and_reuse",
                title="Industrial Water Audits, Closed-Loop Recycling & Non-Freshwater Substitution",
                sector="Industrial",
                relevance=relevance,
                rationale=(
                    f"Industrial extraction reaches {ind_ham:.2f} ham ({ind_share:.2f}% of total draft). "
                    "Mandating water audits, closed-loop cooling/process recycling, and substituting "
                    "treated municipal effluent for industrial processes can reduce freshwater draft."
                    if ind_share is not None else
                    f"Industrial extraction reaches {ind_ham:.2f} ham."
                ),
                supporting_evidence=ev,
                required_feasibility_data=[
                    "State Pollution Control Board (SPCB) / CGWA NOC industrial groundwater abstraction permits",
                    "Sectoral industrial water-use intensity and Zero Liquid Discharge (ZLD) / CETP reuse records",
                ],
                caveats=[
                    "Sub-sector industrial breakdown and CGWA abstraction permit limits are DATA_MISSING.",
                ],
            )
        )

    # ── 4. Pumping & Energy Efficiency Guardrail (When Irrigation Is Significant) ──
    if irr_ham is not None and irr_ham > 0 and stressed:
        interventions.append(
            InterventionItem(
                id="pump_energy_audit_caution",
                title="Agricultural Pumping Audit & Hours/Volume Control (Not Energy Efficiency Alone)",
                sector="Energy / Pumping",
                relevance="moderate" if critical_or_over else "preventive",
                rationale=(
                    f"With {irr_ham:.2f} ham extracted for irrigation under stressed conditions "
                    f"(official stage {stage:.2f}%), pumping controls and feeder/pump audits should be "
                    "evaluated—specifically pairing any pump-efficiency or solarization intervention with "
                    "volumetric or pumping-hour limits."
                ),
                supporting_evidence=[
                    f"Irrigation extraction = {irr_ham:.2f} ham",
                    f"Official CGWB extraction stage = {stage:.2f}%",
                ],
                required_feasibility_data=[
                    "6th Minor Irrigation Census electric/diesel/solar pump counts",
                    "State DISCOM agricultural feeder consumption & pump-set energisation records",
                ],
                caveats=[
                    "CRITICAL DISTINCTION: Higher pump efficiency or solar pumps can reduce grid kWh or cost per m3 without reducing total groundwater extracted (and can even increase extraction if unthrottled). Energy savings must NOT be equated to groundwater savings.",
                ],
            )
        )

    # ── 5. Hydrogeology-Gated Recharge Evaluation (Never Blindly Recommended) ──
    rain = record.rainfall_mm
    rw_area = record.recharge_worthy_area_ha
    geo_area = record.total_geographical_area
    rw_ratio = _pct(rw_area, geo_area)
    wcs_ham = record.recharge_wcs_ham
    wcs_share = recharge_shares.get("water_conservation_structures")
    tanks_ham = record.recharge_tanks_ponds_ham

    if stressed and rain is not None and rw_area is not None and rw_area > 0:
        if rain >= 600.0 and (rw_ratio is None or rw_ratio >= 50.0):
            ev = [
                f"Rainfall = {rain:.2f} mm",
                f"Recharge-worthy area = {rw_area:.2f} ha ({rw_ratio:.1f}% of {geo_area:.2f} ha total area)"
                if rw_ratio is not None else f"Recharge-worthy area = {rw_area:.2f} ha",
                f"Annual GW recharge = {record.ground_water_recharge:.2f} ham"
                if record.ground_water_recharge is not None else "Annual GW recharge = N/A",
            ]
            if wcs_ham is not None:
                ev.append(
                    f"Water conservation structure recharge = {wcs_ham:.2f} ham ({wcs_share:.2f}% of total recharge)"
                    if wcs_share is not None else f"WCS recharge = {wcs_ham:.2f} ham"
                )
            if tanks_ham is not None:
                ev.append(f"Tanks & ponds recharge = {tanks_ham:.2f} ham")

            interventions.append(
                InterventionItem(
                    id="recharge_feasibility_eval",
                    title="Hydrogeology-Screened Artificial Recharge & Tank/WCS Rehabilitation Study",
                    sector="Recharge / Supply",
                    relevance="moderate",
                    rationale=(
                        f"Rainfall ({rain:.2f} mm) and recharge-worthy area ({rw_area:.2f} ha) indicate "
                        "potential physical opportunity for rainwater/runoff harvesting or rehabilitating "
                        "tanks/WCS, subject to aquifer storage capacity and surplus monsoon runoff verification."
                    ),
                    supporting_evidence=ev,
                    required_feasibility_data=[
                        "CGWB NAQUIM aquifer lithology, specific yield, and unsaturated thickness (currently DATA_MISSING)",
                        "IMD long-term rainfall normals & surplus runoff availability",
                        "CGWB piezometer water-level depth & seasonal recovery trends (currently DATA_MISSING)",
                    ],
                    caveats=[
                        "High extraction stage alone does NOT justify artificial recharge; hard-rock areas with limited storage or already-allocated downstream surface flows require NAQUIM hydrogeological clearance.",
                        "Single-year rainfall (2024-2025) cannot establish multi-year surplus runoff.",
                    ],
                )
            )
        else:
            hypotheses.append(
                TaggedStatement(
                    text=(
                        f"Artificial recharge potential appears constrained by low rainfall ({rain:.2f} mm) "
                        f"and/or terrain limits (recharge-worthy share {rw_ratio if rw_ratio is not None else 'N/A'}%); "
                        "demand reduction should take precedence over supply-side recharge unless NAQUIM reports confirm otherwise."
                    ),
                    classification="HYPOTHESIS_UNVERIFIED",
                    evidence_refs=[f"rainfall_mm={rain:.2f}", f"recharge_worthy_area_ha={rw_area:.2f}"],
                    assumption="NAQUIM aquifer storage and IMD runoff surplus data are not yet loaded.",
                )
            )

    # ── 6. Missing-Data Limitations & Next Steps ─────────────────────────────
    data_gaps_summary = {
        "well_and_borewell_counts": "DATA_MISSING",
        "pump_types_and_energy_sources": "DATA_MISSING",
        "drip_and_sprinkler_adoption": "DATA_MISSING",
        "crop_area_and_water_requirements": "DATA_MISSING",
        "agricultural_electricity_consumption": "DATA_MISSING",
        "groundwater_level_decline_trend": "DATA_MISSING",
        "naquim_aquifer_hydrogeology": "DATA_MISSING",
        "water_quality_tagging": "DATA_MISSING",
        "sub_district_assessment_units": "DATA_MISSING",
    }

    limitations: List[TaggedStatement] = [
        TaggedStatement(
            text=(
                "Groundwater extraction stress (Stage %) is NOT equivalent to actual groundwater-level decline: "
                "multi-year CGWB piezometer / DWLR water-level trends (m bgl/yr) are DATA_MISSING."
            ),
            classification="DATA_MISSING",
            evidence_refs=["stage_of_gw_extraction"],
        ),
        TaggedStatement(
            text=(
                "Well inventory (dug wells, shallow/medium/deep tube wells), pump energy sources "
                "(electric/diesel/solar), and micro-irrigation adoption (drip/sprinkler) from the 6th Minor "
                "Irrigation Census are DATA_MISSING (deferred until downloadable schema is verified)."
            ),
            classification="DATA_MISSING",
        ),
        TaggedStatement(
            text=(
                "District crop patterns, crop-water requirements, and agricultural electricity feeder "
                "consumption are DATA_MISSING; crop diversification or pump-efficiency savings cannot be quantified."
            ),
            classification="DATA_MISSING",
        ),
        TaggedStatement(
            text=(
                "CGWB NAQUIM aquifer lithology/transmissivity and IMD multi-year rainfall normals are DATA_MISSING; "
                "artificial recharge suitability cannot be confirmed from INGRES water-balance tables alone."
            ),
            classification="DATA_MISSING",
        ),
        TaggedStatement(
            text=(
                "Water quality tagging columns in INGRES 2024-2025 are empty (0/726 districts populated), "
                "and data is aggregated at district resolution rather than individual assessment units (blocks/taluks/mandals)."
            ),
            classification="DATA_MISSING",
        ),
    ]

    if official.get("has_pq_zone"):
        limitations.append(
            TaggedStatement(
                text=(
                    f"Poor Quality (PQ) groundwater zone present (extractable PQ={official['extractable_pq_ham']:.2f} ham, "
                    f"extraction PQ={official['extraction_pq_ham']:.2f} ham). Official CGWB stage "
                    f"({official['reported_official_stage_pct']:.2f}%) reflects Freshwater (C+NC) zones only, "
                    f"whereas total-extraction stage is {official['total_based_stage_pct']:.2f}%."
                ),
                classification="VERIFIED_FACT",
                evidence_refs=["extractable_pq_ham", "extraction_pq_ham", "stage_of_gw_extraction"],
            )
        )

    next_steps: List[TaggedStatement] = [
        TaggedStatement(
            text=(
                "Integrate verified 6th Minor Irrigation Census district/block data to identify well density, "
                "electric vs. diesel pump mix, and existing drip/sprinkler coverage before sizing irrigation interventions."
            ),
            classification="RECOMMENDATION",
        ),
        TaggedStatement(
            text=(
                "Obtain sub-district (Block/Taluk/Mandal) CGWB INGRES assessment-unit breakdown to pinpoint "
                "Over-Exploited pockets masked by district-wide averages."
            ),
            classification="RECOMMENDATION",
        ),
        TaggedStatement(
            text=(
                "Cross-check CGWB India-WRIS monitoring well water-level time series and NAQUIM aquifer management "
                "plans to confirm actual water-table trends and physical recharge suitability."
            ),
            classification="RECOMMENDATION",
        ),
        TaggedStatement(
            text=(
                "Verify district crop statistics (DES / Agriculture Dept) and local CGWA/state groundwater "
                "notifications before finalizing crop or regulatory interventions."
            ),
            classification="RECOMMENDATION",
        ),
    ]

    return {
        "interventions": interventions,
        "hypotheses": hypotheses,
        "limitations": limitations,
        "next_steps": next_steps,
        "data_gaps_summary": data_gaps_summary,
    }
