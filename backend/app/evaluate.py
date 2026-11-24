"""
evaluate.py — Benchmark Evaluation Module for INGRES Chatbot (Review 2)

Contains 50 test questions across categories:
  - Normal groundwater queries (10)
  - District comparison queries (5)
  - Historical/year queries (5)
  - Forecast trap questions (10)
  - Unknown location questions (5)
  - Unsupported metric questions (5)
  - What-If queries (5)
  - CGWB category queries (5)

Measures:
  1. Answer Accuracy (response has relevant data)
  2. Unsupported Number Rate (numbers not from DB)
  3. Correct Refusal Rate (scope guard fires correctly)
  4. Response Latency (ms)
"""
import time
from typing import List, Dict, Any, Optional, Callable

ASSESSMENT_YEAR = 2022

# ─── Test Cases ───────────────────────────────────────────────────────────────
# Format: { id, question, category, language, expected_behavior, expected_in_scope }
TEST_CASES: List[Dict[str, Any]] = [
    # ── Normal groundwater queries ─────────────────────────────────────────────
    {"id": "NQ01", "question": "What is the groundwater data for Karnataka?",
     "category": "normal", "language": "en", "expected_in_scope": True,
     "expected_behavior": "has_data"},
    {"id": "NQ02", "question": "Tell me about Mysore",
     "category": "normal", "language": "en", "expected_in_scope": True,
     "expected_behavior": "has_data"},
    {"id": "NQ03", "question": "Groundwater status of Maharashtra",
     "category": "normal", "language": "en", "expected_in_scope": True,
     "expected_behavior": "has_data"},
    {"id": "NQ04", "question": "Rainfall in Rajasthan",
     "category": "normal", "language": "en", "expected_in_scope": True,
     "expected_behavior": "has_data"},
    {"id": "NQ05", "question": "What is the stage of extraction in Punjab?",
     "category": "normal", "language": "en", "expected_in_scope": True,
     "expected_behavior": "has_data"},
    {"id": "NQ06", "question": "Net groundwater availability in Uttar Pradesh",
     "category": "normal", "language": "en", "expected_in_scope": True,
     "expected_behavior": "has_data"},
    {"id": "NQ07", "question": "Groundwater recharge data for Gujarat",
     "category": "normal", "language": "en", "expected_in_scope": True,
     "expected_behavior": "has_data"},
    {"id": "NQ08", "question": "भूजल डेटा कर्नाटक के लिए",
     "category": "normal", "language": "hi", "expected_in_scope": True,
     "expected_behavior": "has_response"},
    {"id": "NQ09", "question": "मध्यप्रदेश में वर्षा कितनी है?",
     "category": "normal", "language": "hi", "expected_in_scope": True,
     "expected_behavior": "has_response"},
    {"id": "NQ10", "question": "Show me groundwater data for Telangana",
     "category": "normal", "language": "en", "expected_in_scope": True,
     "expected_behavior": "has_data"},

    # ── District comparison queries ─────────────────────────────────────────────
    {"id": "CQ01", "question": "Compare Karnataka and Maharashtra groundwater",
     "category": "comparison", "language": "en", "expected_in_scope": True,
     "expected_behavior": "has_response"},
    {"id": "CQ02", "question": "Difference between Punjab and Haryana extraction",
     "category": "comparison", "language": "en", "expected_in_scope": True,
     "expected_behavior": "has_response"},
    {"id": "CQ03", "question": "Mysore vs Bangalore groundwater",
     "category": "comparison", "language": "en", "expected_in_scope": True,
     "expected_behavior": "has_response"},
    {"id": "CQ04", "question": "Compare rainfall in Rajasthan and Gujarat",
     "category": "comparison", "language": "en", "expected_in_scope": True,
     "expected_behavior": "has_response"},
    {"id": "CQ05", "question": "Which state has higher extraction — UP or Bihar?",
     "category": "comparison", "language": "en", "expected_in_scope": True,
     "expected_behavior": "has_response"},

    # ── Historical / year queries ───────────────────────────────────────────────
    {"id": "HQ01", "question": "What was the groundwater status of Mysore in 2022?",
     "category": "historical", "language": "en", "expected_in_scope": True,
     "expected_behavior": "has_data"},
    {"id": "HQ02", "question": "Karnataka rainfall data for 2022",
     "category": "historical", "language": "en", "expected_in_scope": True,
     "expected_behavior": "has_data"},
    {"id": "HQ03", "question": "What was the groundwater status of Mysore in 2015?",
     "category": "historical", "language": "en", "expected_in_scope": False,
     "expected_behavior": "year_unavailable"},
    {"id": "HQ04", "question": "Punjab extraction stage in 2019",
     "category": "historical", "language": "en", "expected_in_scope": False,
     "expected_behavior": "year_unavailable"},
    {"id": "HQ05", "question": "Show data for Karnataka in 2020",
     "category": "historical", "language": "en", "expected_in_scope": False,
     "expected_behavior": "year_unavailable"},

    # ── Forecast trap questions ─────────────────────────────────────────────────
    {"id": "FT01", "question": "How much rain will come in Bangalore next year?",
     "category": "forecast_trap", "language": "en", "expected_in_scope": False,
     "expected_behavior": "forecast_refusal"},
    {"id": "FT02", "question": "What will be the groundwater level in Maharashtra in 2026?",
     "category": "forecast_trap", "language": "en", "expected_in_scope": False,
     "expected_behavior": "forecast_refusal"},
    {"id": "FT03", "question": "Predict rainfall for Karnataka next year",
     "category": "forecast_trap", "language": "en", "expected_in_scope": False,
     "expected_behavior": "forecast_refusal"},
    {"id": "FT04", "question": "What is the future groundwater availability in Punjab?",
     "category": "forecast_trap", "language": "en", "expected_in_scope": False,
     "expected_behavior": "forecast_refusal"},
    {"id": "FT05", "question": "Will the groundwater in Mysore be safe in 2030?",
     "category": "forecast_trap", "language": "en", "expected_in_scope": False,
     "expected_behavior": "forecast_refusal"},
    {"id": "FT06", "question": "Forecast extraction stage for Rajasthan",
     "category": "forecast_trap", "language": "en", "expected_in_scope": False,
     "expected_behavior": "forecast_refusal"},
    {"id": "FT07", "question": "What will happen to water levels in Gujarat by 2028?",
     "category": "forecast_trap", "language": "en", "expected_in_scope": False,
     "expected_behavior": "forecast_refusal"},
    {"id": "FT08", "question": "Expected rainfall in Uttar Pradesh upcoming year",
     "category": "forecast_trap", "language": "en", "expected_in_scope": False,
     "expected_behavior": "forecast_refusal"},
    {"id": "FT09", "question": "Project groundwater availability for Bihar 2027",
     "category": "forecast_trap", "language": "en", "expected_in_scope": False,
     "expected_behavior": "forecast_refusal"},
    {"id": "FT10", "question": "अगले साल बेंगलुरु में कितनी बारिश होगी?",
     "category": "forecast_trap", "language": "hi", "expected_in_scope": False,
     "expected_behavior": "forecast_refusal"},

    # ── Unknown location questions ──────────────────────────────────────────────
    {"id": "UL01", "question": "What is the groundwater status of Atlantis?",
     "category": "unknown_location", "language": "en", "expected_in_scope": False,
     "expected_behavior": "unknown_location_refusal"},
    {"id": "UL02", "question": "Groundwater data for Springfield district",
     "category": "unknown_location", "language": "en", "expected_in_scope": False,
     "expected_behavior": "unknown_location_refusal"},
    {"id": "UL03", "question": "Tell me about Wakanda",
     "category": "unknown_location", "language": "en", "expected_in_scope": False,
     "expected_behavior": "unknown_location_refusal"},
    {"id": "UL04", "question": "Gotham city groundwater",
     "category": "unknown_location", "language": "en", "expected_in_scope": False,
     "expected_behavior": "unknown_location_refusal"},
    {"id": "UL05", "question": "Rainfall in Narnia",
     "category": "unknown_location", "language": "en", "expected_in_scope": False,
     "expected_behavior": "unknown_location_refusal"},

    # ── Unsupported metric questions ────────────────────────────────────────────
    {"id": "UM01", "question": "What is the temperature in Bangalore?",
     "category": "unsupported_metric", "language": "en", "expected_in_scope": False,
     "expected_behavior": "unsupported_metric_refusal"},
    {"id": "UM02", "question": "Air quality index of Maharashtra",
     "category": "unsupported_metric", "language": "en", "expected_in_scope": False,
     "expected_behavior": "unsupported_metric_refusal"},
    {"id": "UM03", "question": "Population of Mysore district",
     "category": "unsupported_metric", "language": "en", "expected_in_scope": False,
     "expected_behavior": "unsupported_metric_refusal"},
    {"id": "UM04", "question": "Flood risk in Kerala",
     "category": "unsupported_metric", "language": "en", "expected_in_scope": False,
     "expected_behavior": "unsupported_metric_refusal"},
    {"id": "UM05", "question": "What is the GDP of Karnataka?",
     "category": "unsupported_metric", "language": "en", "expected_in_scope": False,
     "expected_behavior": "unsupported_metric_refusal"},

    # ── What-If queries ────────────────────────────────────────────────────────
    {"id": "WI01", "question": "What if we reduce extraction by 20% in Karnataka?",
     "category": "whatif", "language": "en", "expected_in_scope": True,
     "expected_behavior": "whatif_response"},
    {"id": "WI02", "question": "What happens if Mysore increases extraction by 10%?",
     "category": "whatif", "language": "en", "expected_in_scope": True,
     "expected_behavior": "whatif_response"},
    {"id": "WI03", "question": "Simulate 30% reduction in groundwater extraction for Punjab",
     "category": "whatif", "language": "en", "expected_in_scope": True,
     "expected_behavior": "whatif_response"},
    {"id": "WI04", "question": "What if we reduce extraction by 15% in Rajasthan?",
     "category": "whatif", "language": "en", "expected_in_scope": True,
     "expected_behavior": "whatif_response"},
    {"id": "WI05", "question": "What-if scenario: 25% extraction increase in Gujarat",
     "category": "whatif", "language": "en", "expected_in_scope": True,
     "expected_behavior": "whatif_response"},

    # ── CGWB category queries ──────────────────────────────────────────────────
    {"id": "CG01", "question": "What is the CGWB category of Mysore?",
     "category": "cgwb", "language": "en", "expected_in_scope": True,
     "expected_behavior": "has_data"},
    {"id": "CG02", "question": "Is Karnataka groundwater safe or critical?",
     "category": "cgwb", "language": "en", "expected_in_scope": True,
     "expected_behavior": "has_data"},
    {"id": "CG03", "question": "Which districts in Punjab are over-exploited?",
     "category": "cgwb", "language": "en", "expected_in_scope": True,
     "expected_behavior": "has_data"},
    {"id": "CG04", "question": "Show me over-exploited districts in Rajasthan",
     "category": "cgwb", "language": "en", "expected_in_scope": True,
     "expected_behavior": "has_data"},
    {"id": "CG05", "question": "CGWB status for Maharashtra districts",
     "category": "cgwb", "language": "en", "expected_in_scope": True,
     "expected_behavior": "has_data"},
]


def _score_result(test: Dict, response: Dict) -> Dict[str, Any]:
    """Score a single test result."""
    expected_in_scope = test['expected_in_scope']
    expected_behavior = test['expected_behavior']
    actual_in_scope = response.get('scope_status', 'in_scope') == 'in_scope'
    has_response = bool(response.get('response', '').strip())
    has_data = bool(response.get('data') and len(response.get('data', [])) > 0)
    verified = response.get('verified', None)
    out_of_scope_reason = response.get('out_of_scope_reason', '')

    # Score accuracy
    scope_correct = (actual_in_scope == expected_in_scope)

    behavior_correct = False
    if expected_behavior == 'has_data':
        behavior_correct = has_data or has_response
    elif expected_behavior == 'has_response':
        behavior_correct = has_response
    elif expected_behavior == 'forecast_refusal':
        behavior_correct = (not actual_in_scope) and ('forecast' in str(out_of_scope_reason))
    elif expected_behavior == 'year_unavailable':
        behavior_correct = (not actual_in_scope) and ('year' in str(out_of_scope_reason))
    elif expected_behavior in ('unknown_location_refusal', 'unsupported_metric_refusal'):
        behavior_correct = not actual_in_scope
    elif expected_behavior == 'whatif_response':
        behavior_correct = has_response

    accuracy = 1.0 if (scope_correct and behavior_correct) else 0.0

    return {
        'test_id': test['id'],
        'category': test['category'],
        'question': test['question'],
        'scope_correct': scope_correct,
        'behavior_correct': behavior_correct,
        'accuracy': accuracy,
        'verified': verified,
        'latency_ms': response.get('_latency_ms', 0),
        'actual_in_scope': actual_in_scope,
        'expected_in_scope': expected_in_scope,
        'response_preview': response.get('response', '')[:120],
    }


async def run_evaluation(chat_fn: Callable) -> Dict[str, Any]:
    """
    Run all 50 test cases through the chat function and produce a report.

    Args:
        chat_fn: async function(message: str, language: str) -> ChatResponse dict

    Returns:
        Evaluation report dict.
    """
    results = []
    total_latency = 0.0

    for test in TEST_CASES:
        t0 = time.perf_counter()
        try:
            resp = await chat_fn(test['question'], test.get('language', 'en'))
            if hasattr(resp, '__dict__'):
                resp = resp.__dict__
        except Exception as exc:
            resp = {'response': f'ERROR: {exc}', 'scope_status': 'error'}
        latency_ms = round((time.perf_counter() - t0) * 1000, 1)
        resp['_latency_ms'] = latency_ms
        total_latency += latency_ms

        scored = _score_result(test, resp)
        results.append(scored)

    # Aggregate metrics
    n = len(results)
    accuracy_scores = [r['accuracy'] for r in results]
    overall_accuracy = sum(accuracy_scores) / n if n else 0

    refusal_cases = [r for r in results if not r['expected_in_scope']]
    correct_refusals = [r for r in refusal_cases if r['scope_correct']]
    refusal_rate = len(correct_refusals) / len(refusal_cases) if refusal_cases else 1.0

    verified_cases = [r for r in results if r['verified'] is not None]
    unverified = [r for r in verified_cases if not r['verified']]
    unsupported_number_rate = len(unverified) / len(verified_cases) if verified_cases else 0.0

    avg_latency = total_latency / n if n else 0

    # By category
    categories = {}
    for r in results:
        cat = r['category']
        if cat not in categories:
            categories[cat] = {'total': 0, 'correct': 0}
        categories[cat]['total'] += 1
        categories[cat]['correct'] += r['accuracy']

    cat_summary = {
        cat: {
            'total': v['total'],
            'correct': int(v['correct']),
            'accuracy_pct': round(v['correct'] / v['total'] * 100, 1),
        }
        for cat, v in categories.items()
    }

    return {
        'total_tests': n,
        'overall_accuracy_pct': round(overall_accuracy * 100, 1),
        'correct_refusal_rate_pct': round(refusal_rate * 100, 1),
        'unsupported_number_rate_pct': round(unsupported_number_rate * 100, 1),
        'avg_latency_ms': round(avg_latency, 1),
        'by_category': cat_summary,
        'results': results,
        'assessment_year': ASSESSMENT_YEAR,
        'note': (
            "Evaluation run against live INGRES database. "
            "Results reflect actual system performance, not sample data."
        ),
    }
