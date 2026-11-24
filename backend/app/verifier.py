"""
verifier.py — Number Verifier for INGRES Chatbot Responses (Review 2)

Pipeline:
  Generated text + DB records → verify_response() → {verified, issues, confidence}

Rules:
  - Extract all numeric values from response text
  - Compare against retrieved DB record values (±tolerance)
  - Allow CGWB classification thresholds (70, 90, 100)
  - Allow derived / averaged / rounded values
  - Allow small counts (number of districts, etc.)
  - If unsupported numbers found → verified=False
"""
import re
from typing import List, Dict, Optional, Any

# CGWB standard thresholds — these numbers are always valid in context
CGWB_THRESHOLDS: set = {70.0, 90.0, 100.0}

# Tolerance for float comparison (handles rounding in responses)
TOLERANCE = 0.6

# Year range to exclude from verification (they're context, not data values)
YEAR_MIN = 1990
YEAR_MAX = 2030

# Small integers that are likely counts (districts, states, records)
COUNT_THRESHOLD = 1000


def extract_numbers_from_text(text: str) -> List[float]:
    """
    Extract all numeric values (integers and decimals) from text.
    Excludes years, single digits, and purely ordinal numbers.
    """
    pattern = r'\b(\d{1,6}(?:\.\d{1,4})?)\b'
    raw = re.findall(pattern, text)
    result = []
    for m in raw:
        try:
            val = float(m)
            # Skip years
            if YEAR_MIN <= val <= YEAR_MAX and '.' not in m:
                continue
            # Skip trivially small numbers (1, 2, 3 etc.) — not meaningful data values
            if val < 2:
                continue
            result.append(val)
        except ValueError:
            continue
    return result


def _near(a: float, b: float) -> bool:
    """Return True if two floats are within TOLERANCE of each other."""
    return abs(a - b) <= TOLERANCE


def _is_cgwb_threshold(val: float) -> bool:
    return any(_near(val, t) for t in CGWB_THRESHOLDS)


def _collect_db_values(db_records: List[Dict]) -> List[float]:
    """Collect all numeric field values from DB records as a flat list."""
    numeric_fields = [
        'rainfall', 'extraction_stage', 'gw_recharge',
        'net_availability', 'gw_extraction', 'annual_extractable',
        'rainfall_mm', 'stage_of_gw_extraction', 'ground_water_recharge',
        'net_gw_availability', 'annual_extractable_gw_resource',
    ]
    vals = []
    for rec in db_records:
        for field in numeric_fields:
            v = rec.get(field)
            if v is not None:
                try:
                    vals.append(float(v))
                except (TypeError, ValueError):
                    pass
    return vals


def _build_allowed_set(db_values: List[float], n_records: int) -> List[float]:
    """
    Build a comprehensive set of "allowed" numeric values:
    - Direct DB values
    - Averages
    - Rounded versions
    - Percentage forms
    - Record counts
    """
    allowed = list(db_values)
    if db_values:
        avg = sum(db_values) / len(db_values)
        allowed.append(round(avg, 2))
        allowed.append(round(avg, 1))
        allowed.append(round(avg, 0))
        # percentage representations
        for v in db_values:
            if v > 0:
                allowed.append(round(v * 100, 2))
                allowed.append(round(v / 100, 4))
    # Record counts
    allowed.append(float(n_records))
    return allowed


def verify_response(
    response_text: str,
    db_records: List[Dict],
    extra_allowed: Optional[List[float]] = None,
) -> Dict[str, Any]:
    """
    Verify numerical values in response_text against db_records.

    Args:
        response_text: The bot's generated answer text.
        db_records: List of dicts with groundwater data fields.
        extra_allowed: Additional values known to be valid (e.g., simulation results).

    Returns:
        {
            verified: bool,
            issues: List[str],
            confidence: float,
            numbers_found: List[float],
            numbers_ok: List[float],
            numbers_bad: List[float],
        }
    """
    response_numbers = extract_numbers_from_text(response_text)
    db_values = _collect_db_values(db_records)
    n_records = len(db_records)

    # No numbers in response → trivially verified
    if not response_numbers:
        return _result(True, [], 1.0, [], [], [])

    # No DB values to compare against
    if not db_values and not (extra_allowed or []):
        return _result(
            False,
            ['No database records available to verify against'],
            0.0,
            response_numbers,
            [],
            response_numbers,
        )

    allowed = _build_allowed_set(db_values, n_records)
    if extra_allowed:
        allowed.extend(extra_allowed)

    ok: List[float] = []
    bad: List[float] = []
    issues: List[str] = []

    for num in response_numbers:
        # 1. CGWB threshold values always OK
        if _is_cgwb_threshold(num):
            ok.append(num)
            continue

        # 2. Direct DB match (with tolerance)
        if any(_near(num, av) for av in allowed):
            ok.append(num)
            continue

        # 3. Small counts are hard to verify precisely — allow if ≤ COUNT_THRESHOLD
        #    (e.g., "14 districts", "3 states")
        if num <= COUNT_THRESHOLD and num == int(num):
            ok.append(num)
            continue

        # 4. Not verified
        bad.append(num)
        issues.append(f"Value {num} could not be verified against database records")

    total = len(response_numbers)
    confidence = len(ok) / total if total > 0 else 1.0
    verified = len(bad) == 0

    return _result(verified, issues, round(confidence, 2), response_numbers, ok, bad)


def _result(verified, issues, confidence, found, ok, bad):
    return {
        'verified': verified,
        'issues': issues,
        'confidence': confidence,
        'numbers_found': found,
        'numbers_ok': ok,
        'numbers_bad': bad,
    }
