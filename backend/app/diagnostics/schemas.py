"""
Pydantic schemas for the Groundwater Diagnostic & Recommendation Module.
"""

import math
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field, field_validator


StatementType = Literal[
    "VERIFIED_FACT",
    "DERIVED_CALCULATION",
    "HYPOTHESIS_UNVERIFIED",
    "DATA_MISSING",
    "RECOMMENDATION",
]


class TaggedStatement(BaseModel):
    text: str
    classification: StatementType
    evidence_refs: List[str] = Field(default_factory=list)
    assumption: Optional[str] = None


class SectorBreakdownItem(BaseModel):
    sector: str
    total_ham: Optional[float] = None
    fresh_cnc_ham: Optional[float] = None
    share_of_total_pct: Optional[float] = None
    share_of_fresh_pct: Optional[float] = None


class RechargeBreakdownItem(BaseModel):
    source: str
    amount_ham: Optional[float] = None
    share_pct: Optional[float] = None


class InterventionItem(BaseModel):
    id: str
    title: str
    sector: str
    relevance: str  # "high" | "moderate" | "preventive"
    classification: StatementType = "RECOMMENDATION"
    rationale: str
    supporting_evidence: List[str] = Field(default_factory=list)
    required_feasibility_data: List[str] = Field(default_factory=list)
    caveats: List[str] = Field(default_factory=list)


class ScenarioInput(BaseModel):
    name: str = "Custom Scenario"
    irrigation_pct_change: float = 0.0
    domestic_pct_change: float = 0.0
    industrial_pct_change: float = 0.0

    @field_validator("name")
    @classmethod
    def _clean_name(cls, v: str) -> str:
        s = (v or "").strip()
        return s or "Custom Scenario"

    @field_validator("irrigation_pct_change", "domestic_pct_change", "industrial_pct_change")
    @classmethod
    def _valid_pct(cls, v: float) -> float:
        if not math.isfinite(v):
            raise ValueError("Percentage change must be finite")
        if v < -100.0 or v > 500.0:
            raise ValueError("Percentage change must be between -100 and 500")
        return float(v)


class ScenarioResult(BaseModel):
    name: str
    inputs: ScenarioInput
    simulation_basis: Literal["EXACT_CGWB_C_NC", "ESTIMATE_MATHEMATICAL_SCENARIO"]
    simulation_status_label: str
    practical_feasibility_label: str = "MATHEMATICAL_SCENARIO_ONLY"
    assumption_note: str
    limitation_note: str

    baseline_sector_total_ham: Dict[str, Optional[float]]
    revised_sector_total_ham: Dict[str, Optional[float]]
    baseline_sector_fresh_ham: Dict[str, Optional[float]]
    revised_sector_fresh_ham: Dict[str, Optional[float]]

    baseline_total_extraction_ham: Optional[float] = None
    revised_total_extraction_ham: Optional[float] = None
    baseline_official_extraction_ham: Optional[float] = None
    revised_official_extraction_ham: Optional[float] = None

    baseline_official_stage_pct: Optional[float] = None
    simulated_official_stage_pct: Optional[float] = None
    simulated_official_category: Optional[Dict[str, str]] = None

    baseline_total_stage_pct: Optional[float] = None
    simulated_total_stage_pct: Optional[float] = None
    simulated_total_category: Optional[Dict[str, str]] = None

    reduction_achieved_ham: Optional[float] = None
    reduction_achieved_pct: Optional[float] = None
    remaining_reduction_to_safe_ham: Optional[float] = None
    remaining_reduction_to_safe_pct: Optional[float] = None
    reaches_safe: Optional[bool] = None


class DiagnosticRequest(BaseModel):
    state: str
    district: str
    scenarios: Optional[List[ScenarioInput]] = None
    pct_change: Optional[float] = None  # optional uniform What-If % change

    @field_validator("state", "district")
    @classmethod
    def _non_empty(cls, v: str) -> str:
        s = (v or "").strip()
        if not s:
            raise ValueError("State and district must be non-empty")
        return s

    @field_validator("pct_change")
    @classmethod
    def _valid_uniform_pct(cls, v: Optional[float]) -> Optional[float]:
        if v is None:
            return None
        if not math.isfinite(v) or v < -100.0 or v > 500.0:
            raise ValueError("pct_change must be a finite number between -100 and 500")
        return float(v)


class MultiScenarioRequest(BaseModel):
    state: str
    district: str
    scenarios: List[ScenarioInput] = Field(min_length=1, max_length=10)

    @field_validator("state", "district")
    @classmethod
    def _non_empty(cls, v: str) -> str:
        s = (v or "").strip()
        if not s:
            raise ValueError("State and district must be non-empty")
        return s


class MultiScenarioResponse(BaseModel):
    state: str
    district: str
    assessment_year: str
    data_source: str
    official_cgwb_metrics: Dict[str, Any]
    scenarios: List[ScenarioResult]


class DiagnosticResponse(BaseModel):
    location: Dict[str, Any]
    current_condition: Dict[str, Any]
    major_contributors: Dict[str, Any]
    required_improvement: Dict[str, Any]
    recommended_interventions: List[InterventionItem]
    evidence: List[TaggedStatement]
    expected_impact: Dict[str, Any]
    limitations: List[TaggedStatement]
    next_steps: List[TaggedStatement]
    data_gaps_summary: Dict[str, str]
    verified: bool
    verification_issues: List[str] = Field(default_factory=list)
