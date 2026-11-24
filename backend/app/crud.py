from sqlalchemy.orm import Session
from sqlalchemy import func, or_
from . import models
from typing import List, Optional, Dict, Any


def get_data_by_state(db: Session, state: str) -> List[models.GroundwaterData]:
    """Get all data for a specific state (case-insensitive)."""
    return db.query(models.GroundwaterData).filter(
        func.upper(models.GroundwaterData.state) == state.upper()
    ).all()


def get_data_by_district(db: Session, district: str) -> List[models.GroundwaterData]:
    """Get data for a specific district (case-insensitive, partial match)."""
    return db.query(models.GroundwaterData).filter(
        func.upper(models.GroundwaterData.district).contains(district.upper())
    ).all()


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
    districts = db.query(models.GroundwaterData.district).filter(
        func.upper(models.GroundwaterData.state) == state.upper()
    ).distinct().all()
    return sorted([district[0] for district in districts if district[0]])


def get_statistics(db: Session, state: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Get aggregate statistics for a state or all India."""
    query = db.query(models.GroundwaterData)
    if state:
        query = query.filter(func.upper(models.GroundwaterData.state) == state.upper())

    data = query.all()
    if not data:
        return None

    rainfall_data    = [d.rainfall_mm              for d in data if d.rainfall_mm]
    extraction_data  = [d.stage_of_gw_extraction   for d in data if d.stage_of_gw_extraction]
    recharge_data    = [d.ground_water_recharge     for d in data if d.ground_water_recharge]
    availability_data = [d.net_gw_availability      for d in data if d.net_gw_availability]

    return {
        'total_records':          len(data),
        'avg_rainfall':           sum(rainfall_data)   / len(rainfall_data)   if rainfall_data   else 0,
        'avg_extraction_stage':   sum(extraction_data) / len(extraction_data) if extraction_data else 0,
        'avg_recharge':           sum(recharge_data)   / len(recharge_data)   if recharge_data   else 0,
        'avg_net_availability':   sum(availability_data) / len(availability_data) if availability_data else 0,
    }


def get_data_for_whatif(
    db: Session,
    state: str,
    district: str,
) -> Optional[models.GroundwaterData]:
    """
    Fetch a single record with gw_extraction + annual_extractable_gw_resource
    for the What-If simulation.  Returns the first matching record.
    """
    record = db.query(models.GroundwaterData).filter(
        func.upper(models.GroundwaterData.state) == state.upper(),
        func.upper(models.GroundwaterData.district).contains(district.upper()),
    ).first()
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
