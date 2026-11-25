import math
import os
import re
import logging
from typing import Dict, List, Optional, Tuple

import openpyxl
from sqlalchemy import inspect, text

from .models import GroundwaterData
from .database import engine, SessionLocal

logger = logging.getLogger(__name__)

# ─── Assessment Year Detection ────────────────────────────────────────────────
# Dynamically extracted from the Excel workbook metadata (row 3: Assessment Year).
# Falls back to 2024-2025 if metadata is absent.
ASSESSMENT_YEAR: str = "2024-2025"
ASSESSMENT_YEARS: Tuple[int, ...] = (2024, 2025)
DATA_SOURCE: str = "INGRES / CGWB (GEC-2024-2025)"


def _parse_assessment_years(label: str) -> Tuple[int, ...]:
    """Extract all 4-digit years from an assessment year label like '2024-2025'."""
    years = tuple(int(y) for y in re.findall(r'(20\d{2})', str(label)))
    return years if years else (2024, 2025)


def _detect_assessment_metadata(ws, file_path: str) -> Tuple[str, Tuple[int, ...], str]:
    """Read Assessment Year from Excel metadata rows (rows 1..7), fallback to filename."""
    for r in range(1, min(8, ws.max_row + 1)):
        key = str(ws.cell(r, 1).value or "").strip().lower()
        val = ws.cell(r, 2).value
        if "assessment year" in key and val is not None and str(val).strip():
            label = str(val).strip()
            years = _parse_assessment_years(label)
            return label, years, f"INGRES / CGWB (GEC-{label})"

    match = re.search(r'(20\d{2})', os.path.basename(file_path))
    if match:
        yr = match.group(1)
        return yr, (int(yr),), f"INGRES / CGWB (GEC-{yr})"
    return ASSESSMENT_YEAR, ASSESSMENT_YEARS, DATA_SOURCE


def get_assessment_metadata() -> Dict[str, object]:
    """Return current assessment metadata without stale import-time bindings."""
    return {
        "assessment_year": ASSESSMENT_YEAR,
        "assessment_years": ASSESSMENT_YEARS,
        "data_source": DATA_SOURCE,
    }


def clean_numeric(value) -> Optional[float]:
    """
    Convert value to float, explicitly preserving valid 0 / 0.0 values.
    Returns None only when missing, blank, NaN/Inf, or non-numeric.
    """
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, str):
        stripped = value.strip()
        if stripped == "" or stripped.lower() in {"nan", "na", "n/a", "null", "none", "-"}:
            return None
        value = stripped
    try:
        num = float(value)
        if not math.isfinite(num):
            return None
        return num
    except (ValueError, TypeError):
        return None


def _clean_text(value) -> str:
    """Convert cell value to trimmed string; empty string if None."""
    if value is None:
        return ""
    s = str(value).strip()
    return "" if s.lower() == "nan" else s


# Canonical multi-row header paths (row 8 > row 9 > row 10) -> DB column
HEADER_PATH_TO_FIELD: Dict[Tuple[str, ...], str] = {
    ("S.No", "S.No", "S.No"): "s_no",
    ("STATE", "STATE", "STATE"): "state",
    ("DISTRICT", "DISTRICT", "DISTRICT"): "district",
    ("ASSESSMENT UNIT", "ASSESSMENT UNIT", "ASSESSMENT UNIT"): "assessment_unit",
    ("Rainfall (mm)", "Rainfall (mm)", "Total"): "rainfall_mm",
    ("Total Geographical Area (ha)", "Recharge Worthy Area (ha)", "Total"): "recharge_worthy_area_ha",
    ("Total Geographical Area (ha)", "Hilly Area", "Hilly Area"): "hilly_area_ha",
    ("Total Geographical Area (ha)", "Total", "Total"): "total_geographical_area",
    ("Ground Water Recharge (ham)", "Rainfall Recharge", "Total"): "recharge_rainfall_ham",
    ("Ground Water Recharge (ham)", "Canals", "Total"): "recharge_canals_ham",
    ("Ground Water Recharge (ham)", "Surface Water Irrigation", "Total"): "recharge_sw_irrigation_ham",
    ("Ground Water Recharge (ham)", "Ground Water Irrigation", "Total"): "recharge_gw_irrigation_ham",
    ("Ground Water Recharge (ham)", "Tanks and Ponds", "Total"): "recharge_tanks_ponds_ham",
    ("Ground Water Recharge (ham)", "Water Conservation Structure", "Total"): "recharge_wcs_ham",
    ("Ground Water Recharge (ham)", "Pipelines", "Total"): "recharge_pipelines_ham",
    ("Ground Water Recharge (ham)", "Sewages and Flash Flood Channels", "Total"): "recharge_sewages_flash_flood_ham",
    ("Annual Ground water Recharge (ham)", "Annual Ground water Recharge (ham)", "Total"): "ground_water_recharge",
    ("Environmental Flows (ham)", "Environmental Flows (ham)", "Total"): "env_flows_ham",
    ("Annual Extractable Ground water Resource (ham)", "Annual Extractable Ground water Resource (ham)", "C"): "extractable_c_ham",
    ("Annual Extractable Ground water Resource (ham)", "Annual Extractable Ground water Resource (ham)", "NC"): "extractable_nc_ham",
    ("Annual Extractable Ground water Resource (ham)", "Annual Extractable Ground water Resource (ham)", "PQ"): "extractable_pq_ham",
    ("Annual Extractable Ground water Resource (ham)", "Annual Extractable Ground water Resource (ham)", "Total"): "annual_extractable_gw_resource",
    ("Ground Water Extraction for all uses (ha.m)", "Domestic", "C"): "extraction_domestic_c_ham",
    ("Ground Water Extraction for all uses (ha.m)", "Domestic", "NC"): "extraction_domestic_nc_ham",
    ("Ground Water Extraction for all uses (ha.m)", "Domestic", "Total"): "extraction_domestic_ham",
    ("Ground Water Extraction for all uses (ha.m)", "Industrial", "C"): "extraction_industrial_c_ham",
    ("Ground Water Extraction for all uses (ha.m)", "Industrial", "NC"): "extraction_industrial_nc_ham",
    ("Ground Water Extraction for all uses (ha.m)", "Industrial", "Total"): "extraction_industrial_ham",
    ("Ground Water Extraction for all uses (ha.m)", "Irrigation", "C"): "extraction_irrigation_c_ham",
    ("Ground Water Extraction for all uses (ha.m)", "Irrigation", "NC"): "extraction_irrigation_nc_ham",
    ("Ground Water Extraction for all uses (ha.m)", "Irrigation", "Total"): "extraction_irrigation_ham",
    ("Ground Water Extraction for all uses (ha.m)", "C", "C"): "extraction_c_ham",
    ("Ground Water Extraction for all uses (ha.m)", "NC", "NC"): "extraction_nc_ham",
    ("Ground Water Extraction for all uses (ha.m)", "PQ", "PQ"): "extraction_pq_ham",
    ("Ground Water Extraction for all uses (ha.m)", "Total", "Total"): "gw_extraction",
    ("Stage of Ground Water Extraction (%)", "Stage of Ground Water Extraction (%)", "C"): "stage_c_pct",
    ("Stage of Ground Water Extraction (%)", "Stage of Ground Water Extraction (%)", "NC"): "stage_nc_pct",
    ("Stage of Ground Water Extraction (%)", "Stage of Ground Water Extraction (%)", "PQ"): "stage_pq_pct",
    ("Stage of Ground Water Extraction (%)", "Stage of Ground Water Extraction (%)", "Total"): "stage_of_gw_extraction",
    ("Allocation of Ground Water Resource for Domestic Utilisation for projected year 2025 (ham)", "Allocation of Ground Water Resource for Domestic Utilisation for projected year 2025 (ham)", "Total"): "domestic_alloc_2025_ham",
    ("Net Annual Ground Water Availability for Future Use (ham)", "Net Annual Ground Water Availability for Future Use (ham)", "C"): "net_availability_c_ham",
    ("Net Annual Ground Water Availability for Future Use (ham)", "Net Annual Ground Water Availability for Future Use (ham)", "NC"): "net_availability_nc_ham",
    ("Net Annual Ground Water Availability for Future Use (ham)", "Net Annual Ground Water Availability for Future Use (ham)", "PQ"): "net_availability_pq_ham",
    ("Net Annual Ground Water Availability for Future Use (ham)", "Net Annual Ground Water Availability for Future Use (ham)", "Total"): "net_gw_availability",
    ("Additional Potential Resources Under Specific Conditions(ham)", "Additional Potential Resources Under Specific Conditions(ham)", "Waterlogged and shallow water Table"): "potential_waterlogged_ham",
    ("Additional Potential Resources Under Specific Conditions(ham)", "Additional Potential Resources Under Specific Conditions(ham)", "Flood Prone"): "potential_flood_prone_ham",
    ("Additional Potential Resources Under Specific Conditions(ham)", "Additional Potential Resources Under Specific Conditions(ham)", "Spring Discharge"): "potential_spring_discharge_ham",
    ("In-Storage Unconfined Ground Water Resources(ham)", "In-Storage Unconfined Ground Water Resources(ham)", "Fresh"): "in_storage_unconfined_fresh_ham",
    ("In-Storage Unconfined Ground Water Resources(ham)", "In-Storage Unconfined Ground Water Resources(ham)", "Saline"): "in_storage_unconfined_saline_ham",
    ("Total Ground Water Availability in Unconfined Aquifier (ham)", "Total Ground Water Availability in Unconfined Aquifier (ham)", "Fresh"): "total_unconfined_fresh_ham",
    ("Total Ground Water Availability in Unconfined Aquifier (ham)", "Total Ground Water Availability in Unconfined Aquifier (ham)", "Saline"): "total_unconfined_saline_ham",
    ("Dynamic Confined Ground Water Resources(ham)", "Dynamic Confined Ground Water Resources(ham)", "Fresh"): "dynamic_confined_fresh_ham",
    ("In-Storage Confined Ground Water Resources(ham)", "In-Storage Confined Ground Water Resources(ham)", "Fresh"): "in_storage_confined_fresh_ham",
    ("Total Confined Ground Water Resources (ham)", "Total Confined Ground Water Resources (ham)", "Fresh"): "total_confined_fresh_ham",
    ("Total Ground Water Availability in the area (ham)", "Total Ground Water Availability in the area (ham)", "Fresh"): "total_gw_availability_fresh_ham",
    ("Total Ground Water Availability in the area (ham)", "Total Ground Water Availability in the area (ham)", "Saline"): "total_gw_availability_saline_ham",
}

REQUIRED_FIELDS = {
    "state",
    "district",
    "rainfall_mm",
    "total_geographical_area",
    "ground_water_recharge",
    "annual_extractable_gw_resource",
    "gw_extraction",
    "stage_of_gw_extraction",
    "net_gw_availability",
}

TEXT_FIELDS = {"s_no", "state", "district", "assessment_unit"}


def _resolve_header_columns(ws) -> Tuple[int, Dict[str, int]]:
    """
    Resolve merged multi-row headers in the GEC worksheet.
    Returns (first_data_row_1based, {db_field_name: 0_based_col_idx}).
    """
    header_top_row = None
    for r in range(1, min(20, ws.max_row + 1)):
        row_texts = [str(ws.cell(r, c).value or "").strip().upper() for c in range(1, min(10, ws.max_column + 1))]
        if "STATE" in row_texts and "DISTRICT" in row_texts:
            header_top_row = r
            break

    if header_top_row is None:
        raise ValueError("Could not locate header row containing STATE and DISTRICT in worksheet")

    merged_lookup: Dict[Tuple[int, int], object] = {}
    for m in ws.merged_cells.ranges:
        top_val = ws.cell(m.min_row, m.min_col).value
        for rr in range(m.min_row, m.max_row + 1):
            for cc in range(m.min_col, m.max_col + 1):
                merged_lookup[(rr, cc)] = top_val

    def _cell(r: int, c: int):
        return merged_lookup.get((r, c), ws.cell(r, c).value)

    r8, r9, r10 = header_top_row, header_top_row + 1, header_top_row + 2
    # Data starts after the 3-row header (+ optional blank/sub-row r11)
    first_data_row = header_top_row + 3
    while first_data_row <= ws.max_row:
        st_val = _clean_text(ws.cell(first_data_row, 2).value)
        dt_val = _clean_text(ws.cell(first_data_row, 3).value)
        if st_val and dt_val:
            break
        first_data_row += 1

    normalized_targets = {
        tuple(part.strip().lower() for part in path): field
        for path, field in HEADER_PATH_TO_FIELD.items()
    }

    field_to_col: Dict[str, int] = {}
    for c in range(1, ws.max_column + 1):
        parts = tuple(
            str(x).strip().lower()
            for x in (_cell(r8, c), _cell(r9, c), _cell(r10, c))
            if x is not None and str(x).strip() != ""
        )
        if parts in normalized_targets:
            field_name = normalized_targets[parts]
            field_to_col[field_name] = c - 1  # 0-based index

    missing = REQUIRED_FIELDS - set(field_to_col.keys())
    if missing:
        raise ValueError(f"Workbook validation failed; missing required columns: {sorted(missing)}")

    return first_data_row, field_to_col


def ensure_groundwater_columns() -> None:
    """
    Ensure all columns defined on GroundwaterData exist in the target DB table
    (works for both SQLite and PostgreSQL without dropping existing tables).
    """
    inspector = inspect(engine)
    if not inspector.has_table(GroundwaterData.__tablename__):
        return
    existing_cols = {col["name"] for col in inspector.get_columns(GroundwaterData.__tablename__)}
    missing_cols = [
        col for col in GroundwaterData.__table__.columns
        if col.name not in existing_cols
    ]
    if not missing_cols:
        return

    with engine.begin() as conn:
        for col in missing_cols:
            col_type = col.type.compile(dialect=engine.dialect)
            logger.info(f"Adding missing column '{col.name}' ({col_type}) to {GroundwaterData.__tablename__}")
            conn.execute(
                text(f"ALTER TABLE {GroundwaterData.__tablename__} ADD COLUMN {col.name} {col_type}")
            )


def load_ingres_data_to_db(file_path: str = "ingres-data.xlsx") -> int:
    """
    Validate and load INGRES Excel data (verified Total columns + sectoral breakdown)
    into the configured database (SQLite or PostgreSQL).
    Existing database contents are NOT replaced if workbook validation fails.
    """
    global ASSESSMENT_YEAR, ASSESSMENT_YEARS, DATA_SOURCE

    if not os.path.exists(file_path):
        raise FileNotFoundError(f"INGRES dataset not found at: {file_path}")

    wb = openpyxl.load_workbook(file_path, data_only=True)
    try:
        if "GEC" not in wb.sheetnames:
            raise ValueError(f"Expected sheet 'GEC' not found in {file_path}; found {wb.sheetnames}")

        ws = wb["GEC"]
        year_label, years_tuple, data_source = _detect_assessment_metadata(ws, file_path)
        first_data_row, field_to_col = _resolve_header_columns(ws)

        records: List[Dict[str, object]] = []
        for row_idx in range(first_data_row, ws.max_row + 1):
            row_vals = [ws.cell(row_idx, c).value for c in range(1, ws.max_column + 1)]
            s_no = _clean_text(row_vals[field_to_col["s_no"]]) if "s_no" in field_to_col else ""
            state = _clean_text(row_vals[field_to_col["state"]]).upper()
            district = _clean_text(row_vals[field_to_col["district"]]).upper()

            # Skip blank or summary Total rows
            if not state or not district or s_no.lower() == "total":
                continue

            record: Dict[str, object] = {}
            for field, col_idx in field_to_col.items():
                raw_val = row_vals[col_idx] if col_idx < len(row_vals) else None
                if field in TEXT_FIELDS:
                    cleaned = _clean_text(raw_val)
                    record[field] = cleaned.upper() if field in ("state", "district") else cleaned
                else:
                    record[field] = clean_numeric(raw_val)

            records.append(record)
    finally:
        wb.close()

    if not records:
        raise ValueError("Ingestion aborted: 0 valid district records parsed from workbook")

    # Sanity check: ensure Total extraction & extractable are actually populated
    populated_extraction = sum(1 for r in records if r.get("gw_extraction") is not None)
    if populated_extraction == 0:
        raise ValueError("Ingestion aborted: gw_extraction is null for all parsed rows")

    ensure_groundwater_columns()

    db = SessionLocal()
    try:
        db.query(GroundwaterData).delete()
        db.bulk_insert_mappings(GroundwaterData, records)
        db.commit()
        ASSESSMENT_YEAR = year_label
        ASSESSMENT_YEARS = years_tuple
        DATA_SOURCE = data_source
        logger.info(
            f"Successfully loaded {len(records)} records "
            f"(year={ASSESSMENT_YEAR}, source={DATA_SOURCE})"
        )
        return len(records)
    except Exception as exc:
        db.rollback()
        logger.error(f"Database error during ingestion (rolled back): {exc}")
        raise
    finally:
        db.close()
