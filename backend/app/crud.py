import re
from sqlalchemy.orm import Session
from sqlalchemy import func, or_
from . import models
from typing import List, Optional, Dict, Any, Tuple


def _normalize_location_key(name: str) -> str:
    """Normalize state/district strings for reliable matching (strip punctuation/spaces)."""
    if not name:
        return ""
    cleaned = re.sub(r'[()\[\],.\-_]+', ' ', name.upper())
    return re.sub(r'\s+', ' ', cleaned).strip()


def _match_state_records(db: Session, state: str) -> List[models.GroundwaterData]:
    """Match state by exact uppercase first, then normalized key (e.g. 'TAMIL NADU' -> 'TAMILNADU')."""
    state_clean = (state or "").strip()
    if not state_clean:
        return []

    exact = db.query(models.GroundwaterData).filter(
        func.upper(models.GroundwaterData.state) == state_clean.upper()
    ).all()
    if exact:
        return exact

    target_norm = _normalize_location_key(state_clean)
    target_compact = target_norm.replace(" ", "")
    all_rows = db.query(models.GroundwaterData).all()
    return [
        r for r in all_rows
        if r.state and (
            _normalize_location_key(r.state) == target_norm
            or _normalize_location_key(r.state).replace(" ", "") == target_compact
        )
    ]


def get_data_by_state(db: Session, state: str) -> List[models.GroundwaterData]:
    """Get all data for a specific state (case-insensitive, exact then normalized)."""
    return _match_state_records(db, state)


def resolve_district_records(
    db: Session,
    district: str,
    state: Optional[str] = None,
) -> Tuple[List[models.GroundwaterData], Optional[List[str]]]:
    """
    Resolve district records using deterministic precedence:
      1. Exact uppercase match
      2. Normalized match (ignores parentheses/punctuation/whitespace differences)
      3. Partial substring match ONLY when unambiguous (resolves to 1 district)

    Returns:
        (matched_records, ambiguous_candidates)
        If ambiguous_candidates is not None, matched_records is empty.
    """
    dist_clean = (district or "").strip()
    if not dist_clean:
        return [], None

    pool = _match_state_records(db, state) if state else db.query(models.GroundwaterData).all()
    if not pool:
        return [], None

    dist_upper = dist_clean.upper()
    # 1. Exact match
    exact = [r for r in pool if r.district and r.district.strip().upper() == dist_upper]
    if exact:
        return exact, None

    # 2. Normalized match
    target_norm = _normalize_location_key(dist_clean)
    normalized = [
        r for r in pool
        if r.district and _normalize_location_key(r.district) == target_norm
    ]
    if normalized:
        return normalized, None

    # 3. Partial match only when unambiguous
    partial = [
        r for r in pool
        if r.district and (
            dist_upper in r.district.upper()
            or target_norm in _normalize_location_key(r.district)
        )
    ]
    if not partial:
        return [], None

    distinct_pairs = sorted({(r.state, r.district) for r in partial})
    if len(distinct_pairs) == 1:
        return partial, None

    # If no state was given, check if it's the exact same district name across states
    distinct_dists = sorted({r.district for r in partial})
    if not state and len(distinct_dists) == 1:
        return partial, None

    candidates = [f"{d} ({s})" if not state else d for s, d in distinct_pairs]
    return [], candidates


def get_data_by_district(db: Session, district: str) -> List[models.GroundwaterData]:
    """
    Get data for a specific district:
    exact match first, then normalized match, then unambiguous partial match.
    """
    records, ambiguous = resolve_district_records(db, district)
    if records:
        return records
    if ambiguous:
        # Preserve backward-compatible list return for chat when user asks e.g. 'Bengaluru'
        dist_upper = (district or "").strip().upper()
        target_norm = _normalize_location_key(district)
        return [
            r for r in db.query(models.GroundwaterData).all()
            if r.district and (
                dist_upper in r.district.upper()
                or target_norm in _normalize_location_key(r.district)
            )
        ]
    return []


def search_data(db: Session, query: str) -> List[models.GroundwaterData]:
    """Search data by state or district."""
    search_term = f"%{query.upper()}%"
    return db.query(models.GroundwaterData).filter(
        or_(
            func.upper(models.GroundwaterData.state).like(search_term),
            func.upper(models.GroundwaterData.district).like(search_term)
        )
    ).limit(20).all()


def get_all_states(db: Session) -> List[str]:
    """Get list of all unique states."""
    states = db.query(models.GroundwaterData.state).distinct().all()
    return sorted([state[0] for state in states if state[0]])


def get_districts_by_state(db: Session, state: str) -> List[str]:
    """Get all districts in a state."""
    rows = _match_state_records(db, state)
    return sorted({r.district for r in rows if r.district})


def get_statistics(db: Session, state: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Get aggregate statistics for a state or all India (preserving valid 0.0 values)."""
    if state:
        data = _match_state_records(db, state)
    else:
        data = db.query(models.GroundwaterData).all()

    if not data:
        return None

    rainfall_data     = [d.rainfall_mm            for d in data if d.rainfall_mm is not None]
    extraction_data   = [d.stage_of_gw_extraction for d in data if d.stage_of_gw_extraction is not None]
    recharge_data     = [d.ground_water_recharge  for d in data if d.ground_water_recharge is not None]
    availability_data = [d.net_gw_availability    for d in data if d.net_gw_availability is not None]

    return {
        'total_records':          len(data),
        'avg_rainfall':           sum(rainfall_data)     / len(rainfall_data)     if rainfall_data     else 0.0,
        'avg_extraction_stage':   sum(extraction_data)   / len(extraction_data)   if extraction_data   else 0.0,
        'avg_recharge':           sum(recharge_data)     / len(recharge_data)     if recharge_data     else 0.0,
        'avg_net_availability':   sum(availability_data) / len(availability_data) if availability_data else 0.0,
    }


def get_whatif_lookup_result(
    db: Session,
    state: str,
    district: str,
) -> Tuple[Optional[models.GroundwaterData], Optional[List[str]]]:
    """
    Resolve a single district record for What-If simulation using:
    exact match -> normalized match -> unambiguous partial match.
    Returns (record, ambiguous_candidates).
    """
    records, ambiguous = resolve_district_records(db, district=district, state=state)
    if ambiguous:
        return None, ambiguous
    return (records[0] if records else None), None


def get_data_for_whatif(
    db: Session,
    state: str,
    district: str,
) -> Optional[models.GroundwaterData]:
    """
    Fetch a single record with gw_extraction + annual_extractable_gw_resource
    for the What-If simulation using exact -> normalized -> unambiguous partial match.
    """
    record, _ = get_whatif_lookup_result(db, state, district)
    return record


def get_cgwb_distribution(db: Session, state: str) -> Dict[str, int]:
    """
    Count how many districts fall into each CGWB category for a state.
    Returns { 'SAFE': n, 'SEMI-CRITICAL': n, 'CRITICAL': n, 'OVER-EXPLOITED': n }
    """
    data = get_data_by_state(db, state)
    dist = {'SAFE': 0, 'SEMI-CRITICAL': 0, 'CRITICAL': 0, 'OVER-EXPLOITED': 0}
    for d in data:
        stage = d.stage_of_gw_extraction
        if stage is None:
            continue
        if stage <= 70:
            dist['SAFE'] += 1
        elif stage <= 90:
            dist['SEMI-CRITICAL'] += 1
        elif stage <= 100:
            dist['CRITICAL'] += 1
        else:
            dist['OVER-EXPLOITED'] += 1
    return dist
