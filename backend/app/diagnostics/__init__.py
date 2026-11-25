"""
Groundwater Diagnostic & Recommendation Module for INGRES_UPD.
"""

from .engine import run_diagnostic
from .schemas import (
    DiagnosticRequest,
    DiagnosticResponse,
    MultiScenarioRequest,
    MultiScenarioResponse,
    ScenarioInput,
    ScenarioResult,
    StatementType,
    TaggedStatement,
)
from .scenario_simulator import build_default_scenarios, simulate_sector_scenarios

__all__ = [
    "run_diagnostic",
    "DiagnosticRequest",
    "DiagnosticResponse",
    "MultiScenarioRequest",
    "MultiScenarioResponse",
    "ScenarioInput",
    "ScenarioResult",
    "StatementType",
    "TaggedStatement",
    "build_default_scenarios",
    "simulate_sector_scenarios",
]
