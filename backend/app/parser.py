"""
parser.py — Query Parser, Intent Detector & Scope Guard for INGRES Chatbot (Review 2)

Pipeline:
  User Query → parse_query() → {intent, locations, is_in_scope, out_of_scope_reason, ...}
"""
import re
from typing import Optional, List, Dict, Any, Tuple

# ─── Assessment year (GEC-2022 standard dataset) ─────────────────────────────
ASSESSMENT_YEAR = 2022

# ─── Forecast / future-tense patterns ────────────────────────────────────────
FORECAST_PATTERNS = [
    r'\bwill\b', r'\bnext year\b', r'\bfuture\b', r'\bpredict\b',
    r'\bforecast\b', r'\btomorrow\b', r'\bcoming year\b', r'\bupcoming\b',
    r'\bin 20[2-9]\d\b', r'\bby 20[2-9]\d\b',
    r'\b202[5-9]\b', r'\b203\d\b', r'\b204\d\b',
    r'\bprojection\b', r'\bexpect\b', r'\bwhen will\b', r'\bhow much rain.*come\b',
    # Hindi future markers
    r'\bhoga\b', r'\bkya hoga\b', r'\bआएगा\b', r'\bहोगा\b', r'\bमिलेगा\b',
]

# ─── Unsupported metric patterns ──────────────────────────────────────────────
UNSUPPORTED_METRICS = [
    'temperature', 'flood risk', 'air quality', 'pollution', 'population',
    'crime', 'gdp', 'economy', 'climate change', 'drought index',
    'soil moisture', 'humidity', 'wind speed', 'evaporation',
    'crop yield', 'agriculture production', 'stock',
]

# ─── City / district canonical aliases ────────────────────────────────────────
LOCATION_ALIASES: Dict[str, str] = {
    'bangalore': 'BENGALURU URBAN',
    'bengaluru': 'BENGALURU URBAN',
    'bengalore': 'BENGALURU URBAN',
    'bangaluru': 'BENGALURU URBAN',
    'mysore': 'MYSURU',
    'maisuru': 'MYSURU',
    'bombay': 'MUMBAI SUBURBAN',
    'madras': 'CHENNAI',
    'calcutta': 'KOLKATA',
    'trivandrum': 'THIRUVANANTHAPURAM',
    'cochin': 'ERNAKULAM',
    'baroda': 'VADODARA',
    'poona': 'PUNE',
    'vizag': 'VISAKHAPATNAM',
    'visakha': 'VISAKHAPATNAM',
    'vizag': 'VISAKHAPATNAM',
    'new delhi': 'DELHI',
    'dilli': 'DELHI',
}

# ─── Intent patterns ─────────────────────────────────────────────────────────
INTENT_PATTERNS: Dict[str, List[str]] = {
    'greet': [
        r'\bhello\b', r'\bhi\b', r'\bhey\b', r'\bnamaste\b', r'\bnamaskar\b',
        r'नमस्ते', r'नमस्कार', r'\bgood morning\b', r'\bgood afternoon\b',
        r'\bgood evening\b', r'\bstart\b',
    ],
    'ask_state_list': [
        r'\bshow states\b', r'\blist states\b', r'\ball states\b',
        r'\bavailable states\b', r'\bwhich states\b', r'\bshow all\b',
    ],
    'ask_rainfall': [
        r'\brainfall\b', r'\brain\b', r'\bprecipitation\b', r'\bbarish\b',
        r'\bवर्षा\b', r'\bबारिश\b', r'\b\.mm\b', r'\bmillimeter\b',
    ],
    'ask_extraction': [
        r'\bextraction\b', r'\bstage of\b', r'\bover.exploit\b',
        r'\bover exploit\b', r'\bnिष्कर्षण\b', r'\bexploitation\b',
        r'\bpumping\b', r'\bdraft\b',
    ],
    'ask_recharge': [
        r'\brecharge\b', r'\bरिचार्ज\b', r'\breplenish\b',
        r'\bgroundwater recharge\b', r'\bgw recharge\b',
    ],
    'ask_availability': [
        r'\bavailability\b', r'\bnet availability\b', r'\bfuture use\b',
        r'\bउपलब्धता\b', r'\bnet annual\b', r'\bremaining\b',
    ],
    'compare': [
        r'\bcompare\b', r'\bvs\.?\b', r'\bversus\b', r'\bdifference between\b',
        r'\btulna\b', r'\bतुलना\b', r'\bwhich is (better|worse|higher|lower)\b',
        r'\bbetween\b.*\band\b',
    ],
    'ask_whatif': [
        r'\bwhat.if\b', r'\bwhat if\b',
        r'\bif (?:i |we )?reduce\b', r'\bif (?:i |we )?increase\b',
        r'\bif extraction\b', r'\bsimulat\b', r'\bscenario\b',
        r'\bwhat happens\b', r'\bif we\b', r'\bif the\b.*\bextraction\b',
        r'\bक्या होगा\b', r'\breduce extraction\b', r'\bincrease extraction\b',
        r'\bchange extraction\b',
    ],
    'ask_category': [
        r'\bcategory\b', r'\bcgwb\b', r'\bsafe\b', r'\bcritical\b',
        r'\bover.exploit\b', r'\bsemi.critical\b', r'\bstatus\b',
        r'\bclassif\b',
    ],
    'ask_groundwater': [
        r'\bgroundwater\b', r'\bground water\b', r'\bbhujal\b',
        r'\bभूजल\b', r'\bwater table\b', r'\baquifer\b',
        r'\bdata\b', r'\binfo\b', r'\btell me about\b', r'\bshow me\b',
        r'\bwhat is\b', r'\bहालत\b', r'\bस्थिति\b',
    ],
}


def _match_patterns(text: str, patterns: List[str]) -> bool:
    """Return True if any pattern matches in text (case-insensitive)."""
    for pat in patterns:
        if re.search(pat, text, re.IGNORECASE):
            return True
    return False


def is_forecast_query(text: str) -> bool:
    """Return True if the query asks about future/forecast data."""
    return _match_patterns(text, FORECAST_PATTERNS)


def has_unsupported_metric(text: str) -> bool:
    """Return True if the query asks about metrics not in INGRES dataset."""
    text_lower = text.lower()
    return any(m in text_lower for m in UNSUPPORTED_METRICS)


def extract_year(text: str) -> Optional[int]:
    """Extract a 4-digit year from text if present."""
    match = re.search(r'\b(19\d{2}|20\d{2})\b', text)
    return int(match.group(1)) if match else None


def apply_location_aliases(text: str) -> str:
    """Replace known city aliases with canonical forms for matching."""
    text_lower = text.lower()
    for alias, canonical in LOCATION_ALIASES.items():
        if alias in text_lower:
            text_lower = text_lower.replace(alias, canonical.lower())
    return text_lower


def normalize_location(name: str) -> str:
    """Normalize location name by resolving aliases and trimming."""
    name_clean = name.strip()
    lower = name_clean.lower()
    return LOCATION_ALIASES.get(lower, name_clean.upper())



def detect_intent(text: str) -> str:
    """Return the best-matching intent string from the query."""
    for intent, patterns in INTENT_PATTERNS.items():
        if _match_patterns(text, patterns):
            return intent
    return 'ask_groundwater'  # sensible default


def parse_query(
    text: str,
    available_states: List[str],
    district_map: Dict[str, Any],
    assessment_year: int = ASSESSMENT_YEAR,
) -> Dict[str, Any]:
    """
    Full query parse.

    Returns:
        {
            intent: str,
            locations: {states: List[str], districts: List[str]},
            is_in_scope: bool,
            out_of_scope_reason: str | None,
            year_requested: int | None,
            year_available: bool,
        }
    """
    lower = text.lower()
    aliased = apply_location_aliases(lower)

    # 1. Forecast check — highest priority
    if is_forecast_query(lower):
        return {
            'intent': 'forecast',
            'locations': {'states': [], 'districts': []},
            'is_in_scope': False,
            'out_of_scope_reason': 'forecast',
            'year_requested': None,
            'year_available': True,
        }

    # 2. Unsupported metric
    if has_unsupported_metric(lower):
        return {
            'intent': 'unsupported_metric',
            'locations': {'states': [], 'districts': []},
            'is_in_scope': False,
            'out_of_scope_reason': 'unsupported_metric',
            'year_requested': None,
            'year_available': True,
        }

    # 3. Year extraction + validation
    year_requested = extract_year(lower)
    year_available = (year_requested is None) or (year_requested == assessment_year)

    # 4. Intent detection
    intent = detect_intent(lower)

    # 5. Location extraction
    found_states: List[str] = []
    found_districts: List[str] = []

    for state in available_states:
        if state.lower() in aliased or state.lower() in lower:
            found_states.append(state)

    for dist_key, (dist_val, state_val) in district_map.items():
        if dist_key in aliased or dist_key in lower:
            if dist_val not in found_districts:
                found_districts.append(dist_val)
            if state_val not in found_states:
                found_states.append(state_val)

    return {
        'intent': intent,
        'locations': {'states': found_states, 'districts': found_districts},
        'is_in_scope': True,
        'out_of_scope_reason': None,
        'year_requested': year_requested,
        'year_available': year_available,
    }


def build_scope_refusal(
    reason: str,
    location: str = '',
    year: Optional[int] = None,
    latest_year: int = ASSESSMENT_YEAR,
    latest_value: Optional[float] = None,
    metric: str = '',
) -> str:
    """Build a human-friendly, honest refusal message for out-of-scope queries."""
    if reason == 'forecast':
        msg = (
            "⚠️ **I cannot predict future values.** The INGRES dataset contains only "
            "historically assessed groundwater data — it does not support forecasting."
        )
        if latest_value is not None and metric:
            msg += (
                f"\n\nThe latest available assessed **{metric}** is "
                f"**{latest_value:.2f}** (Assessment Year: {latest_year}, Source: INGRES/CGWB)."
            )
        return msg

    if reason == 'unknown_location':
        return (
            f"⚠️ Sorry, **{location}** is not found in the INGRES groundwater dataset. "
            "Please try a valid Indian state or district name. "
            "Use 'Show all states' to see available locations."
        )

    if reason == 'unsupported_metric':
        return (
            "⚠️ This metric is not available in the INGRES groundwater dataset.\n\n"
            "I can answer questions about:\n"
            "- 🌧️ Rainfall (mm)\n"
            "- ♻️ Groundwater Recharge (ham)\n"
            "- 📊 Stage of Groundwater Extraction (%)\n"
            "- 💦 Net Groundwater Availability (ham)\n"
            "- 🏷️ CGWB Category (Safe / Semi-Critical / Critical / Over-Exploited)"
        )

    if reason == 'year_unavailable':
        return (
            f"⚠️ Data for the year **{year}** is not available in the INGRES dataset.\n"
            f"The latest available assessment year is **{latest_year}** (GEC-2022)."
        )

    return "⚠️ This query is out of scope for the INGRES groundwater dataset."
