import pandas as pd
from sqlalchemy.orm import Session
from .models import GroundwaterData
from .database import engine, SessionLocal
import logging
import re

logger = logging.getLogger(__name__)

# ─── Assessment Year Detection ────────────────────────────────────────────────
# The standard INGRES GEC-2022 dataset is from the 2022 assessment cycle.
# We try to detect the year from the Excel file name or sheet metadata;
# fall back to the GEC-2022 standard.
ASSESSMENT_YEAR: int = 2022
DATA_SOURCE: str = "INGRES / CGWB (GEC-2022)"


def _detect_assessment_year(file_path: str) -> int:
    """Try to detect assessment year from filename; fall back to 2022."""
    match = re.search(r'(20\d{2})', file_path)
    if match:
        return int(match.group(1))
    return ASSESSMENT_YEAR


def clean_numeric(value):
    """Convert value to float; return None if not possible."""
    try:
        if pd.isna(value):
            return None
        return float(value)
    except (ValueError, TypeError):
        return None


def load_ingres_data_to_db(file_path: str = "ingres-data.xlsx") -> int:
    """
    Load INGRES Excel data into PostgreSQL database.
    Returns the number of records loaded.
    """
    global ASSESSMENT_YEAR
    detected_year = _detect_assessment_year(file_path)
    ASSESSMENT_YEAR = detected_year
    logger.info(f"Assessment year detected/set: {ASSESSMENT_YEAR}")

    try:
        logger.info(f"Loading data from {file_path}")

        df = pd.read_excel(file_path, sheet_name='GEC', skiprows=7)

        # Clean: drop rows missing both STATE and DISTRICT
        df = df.dropna(subset=['STATE', 'DISTRICT'], how='all')
        df = df[df['STATE'].notna()]
        df = df[df['STATE'].astype(str).str.strip() != '']

        records = []
        for _, row in df.iterrows():
            try:
                record = {
                    's_no':                         str(row.get('S.No', '')),
                    'state':                        str(row.get('STATE', '')).strip().upper(),
                    'district':                     str(row.get('DISTRICT', '')).strip().upper(),
                    'assessment_unit':              str(row.get('ASSESSMENT UNIT', '')),
                    'rainfall_mm':                  clean_numeric(row.get('Rainfall (mm)')),
                    'total_geographical_area':      clean_numeric(row.get('Total Geographical Area (ha)')),
                    'ground_water_recharge':        clean_numeric(row.get('Ground Water Recharge (ham)')),
                    'annual_extractable_gw_resource': clean_numeric(
                        row.get('Annual Extractable Ground water Resource (ham)')
                    ),
                    'gw_extraction':                clean_numeric(
                        row.get('Ground Water Extraction for all uses (ha.m)')
                    ),
                    'stage_of_gw_extraction':       clean_numeric(
                        row.get('Stage of Ground Water Extraction (%)')
                    ),
                    'net_gw_availability':          clean_numeric(
                        row.get('Net Annual Ground Water Availability for Future Use (ham)')
                    ),
                }
                if record['state'] and record['district']:
                    records.append(record)
            except Exception as exc:
                logger.warning(f"Error processing row: {exc}")
                continue

        db = SessionLocal()
        try:
            db.query(GroundwaterData).delete()
            for record in records:
                db.add(GroundwaterData(**record))
            db.commit()
            logger.info(f"Successfully loaded {len(records)} records (year={ASSESSMENT_YEAR})")
            return len(records)
        except Exception as exc:
            db.rollback()
            logger.error(f"Database error: {exc}")
            raise
        finally:
            db.close()

    except Exception as exc:
        logger.error(f"Error loading data: {exc}")
        raise
