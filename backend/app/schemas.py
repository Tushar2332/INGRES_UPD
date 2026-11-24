from pydantic import BaseModel
from typing import Optional, List, Dict, Any


class GroundwaterDataSchema(BaseModel):
    state: str
    district: str
    rainfall_mm: Optional[float] = None
    ground_water_recharge: Optional[float] = None
    gw_extraction: Optional[float] = None
    stage_of_gw_extraction: Optional[float] = None
    net_gw_availability: Optional[float] = None
    annual_extractable_gw_resource: Optional[float] = None

    class Config:
        from_attributes = True


class ChatMessage(BaseModel):
    message: str
    language: str = "en"


class ChatResponse(BaseModel):
    response: str
    data: Optional[List[dict]] = None
    suggestions: Optional[List[str]] = None
    chart_data: Optional[Dict[str, Any]] = None
    # ── Review 2 additions ──────────────────────────────────────────────────
    verified: Optional[bool] = None
    verification_issues: Optional[List[str]] = None
    scope_status: Optional[str] = None           # "in_scope" | "out_of_scope"
    out_of_scope_reason: Optional[str] = None    # "forecast" | "unknown_location" | ...
    assessment_year: Optional[str] = None        # e.g. "2022"
    data_source: Optional[str] = None            # "INGRES / CGWB (GEC-2022)"
    data_confidence: Optional[str] = None        # "Latest Available Assessment" | "Historical Data"
    cgwb_category: Optional[str] = None          # "SAFE" | "SEMI-CRITICAL" | ...
    cgwb_color: Optional[str] = None             # hex colour for the category


class WhatIfRequest(BaseModel):
    state: str
    district: str
    pct_change: float  # negative = reduction, positive = increase


class WhatIfResponse(BaseModel):
    response: str
    result: Dict[str, Any]
    chart_data: Optional[Dict[str, Any]] = None
    assessment_year: Optional[str] = None
    data_source: Optional[str] = None
    district: Optional[str] = None
    state: Optional[str] = None
