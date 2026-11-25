import os
import sys
import unittest

# Ensure backend directory is importable regardless of working directory
BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from app import database, evaluate, main, models, schemas, translation  # noqa: E402
from app.diagnostics.schemas import DiagnosticRequest, MultiScenarioRequest, ScenarioInput  # noqa: E402


def sync_await(coro):
    """Run fast in-memory FastAPI async endpoint coroutines synchronously inside sandbox."""
    try:
        coro.send(None)
    except StopIteration as exc:
        return exc.value
    raise RuntimeError("Coroutine yielded unexpectedly inside synchronous test runner")


class TestChatAssistantUpgrade(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Disable live GoogleTranslator network calls inside offline unit tests
        translation.HAS_DEEP_TRANSLATOR = False
        cls.db = database.SessionLocal()
        last_row = cls.db.query(models.ChatHistory).order_by(models.ChatHistory.id.desc()).first()
        cls.initial_max_history_id = last_row.id if last_row else 0
        main._SESSION_CONTEXT.clear()

    @classmethod
    def tearDownClass(cls):
        try:
            cls.db.query(models.ChatHistory).filter(
                models.ChatHistory.id > cls.initial_max_history_id
            ).delete(synchronize_session=False)
            cls.db.commit()
        finally:
            cls.db.close()
            main._SESSION_CONTEXT.clear()

    def _chat(self, message: str, session_id: str | None = None, context: dict | None = None):
        payload = schemas.ChatMessage(
            message=message,
            language="en",
            session_id=session_id,
            context=context,
        )
        return sync_await(main.chat(payload, db=self.db))

    def test_01_to_05_and_10_multi_turn_context_flow(self):
        sid = "test_multi_turn_session_1"

        # 1. "What is the groundwater status of Mysuru?"
        r1 = self._chat("What is the groundwater status of Mysuru?", session_id=sid)
        self.assertEqual(r1.scope_status, "in_scope")
        self.assertTrue(r1.verified, f"Verification issues: {r1.verification_issues}")
        self.assertIn("MYSURU", r1.response.upper())
        self.assertIsNotNone(r1.context)
        self.assertEqual(r1.context.get("last_district"), "MYSURU")
        self.assertEqual(r1.context.get("last_state"), "KARNATAKA")

        # 2. Follow-up: "Is it good to grow mango crops there?"
        r2 = self._chat("Is it good to grow mango crops there?", session_id=sid)
        self.assertEqual(r2.scope_status, "in_scope")
        self.assertTrue(r2.verified, f"Verification issues: {r2.verification_issues}")
        self.assertNotIn("not found in the INGRES groundwater dataset", r2.response)
        self.assertIn("MYSURU", r2.response.upper())
        self.assertIn("Mango", r2.response)
        self.assertIn("Verified INGRES", r2.response)
        self.assertIn("Information Unavailable in INGRES", r2.response)
        self.assertEqual(r2.context.get("last_crop"), "mango")
        self.assertEqual(r2.context.get("last_district"), "MYSURU")

        # 3. Follow-up: "What about rice?" (reuses Mysuru + updates crop to rice)
        r3 = self._chat("What about rice?", session_id=sid)
        self.assertEqual(r3.scope_status, "in_scope")
        self.assertTrue(r3.verified, f"Verification issues: {r3.verification_issues}")
        self.assertIn("MYSURU", r3.response.upper())
        self.assertIn("Rice", r3.response)
        self.assertEqual(r3.context.get("last_crop"), "rice")
        self.assertEqual(r3.context.get("last_district"), "MYSURU")

        # 4. Follow-up: "Which crops require less water?"
        r4 = self._chat("Which crops require less water?", session_id=sid)
        self.assertEqual(r4.scope_status, "in_scope")
        self.assertTrue(r4.verified, f"Verification issues: {r4.verification_issues}")
        self.assertIn("Millets", r4.response)
        self.assertIn("MYSURU", r4.response.upper())

        # 5. Follow-up: "Would increasing irrigation put pressure on groundwater?"
        r5 = self._chat("Would increasing irrigation put pressure on groundwater?", session_id=sid)
        self.assertEqual(r5.scope_status, "in_scope")
        self.assertTrue(r5.verified, f"Verification issues: {r5.verification_issues}")
        self.assertIn("MYSURU", r5.response.upper())
        self.assertIn("Irrigation", r5.response)

        # 10. Follow-up changing location: "What about Bengaluru Urban?"
        r10 = self._chat("What about Bengaluru Urban?", session_id=sid)
        self.assertEqual(r10.scope_status, "in_scope")
        self.assertTrue(r10.verified, f"Verification issues: {r10.verification_issues}")
        self.assertTrue(
            "BENGALURU" in r10.response.upper(),
            f"Expected Bengaluru Urban in response, got: {r10.response}",
        )
        self.assertIn("BENGALURU", (r10.context.get("last_district") or "").upper())

    def test_06_state_level_query_and_context_switch(self):
        sid = "test_state_session_6"
        r = self._chat("What is the groundwater status of Karnataka?", session_id=sid)
        self.assertEqual(r.scope_status, "in_scope")
        self.assertTrue(r.verified, f"Verification issues: {r.verification_issues}")
        self.assertIn("KARNATAKA", r.response.upper())
        self.assertEqual(r.context.get("last_state"), "KARNATAKA")
        self.assertIsNone(r.context.get("last_district"))
        self.assertEqual(r.context.get("last_location_type"), "state")

    def test_07_crop_question_without_context_asks_clarification_then_resolves(self):
        sid = "test_clarify_session_7"
        r_ask = self._chat("Is mango cultivation suitable?", session_id=sid)
        self.assertEqual(r_ask.scope_status, "in_scope")
        self.assertTrue(r_ask.verified)
        self.assertIn("Which district or location", r_ask.response)
        self.assertIsNotNone(r_ask.context.get("pending_clarification"))

        # Follow up with bare district name "Mysuru" using returned context
        r_follow = self._chat("Mysuru", context=r_ask.context)
        self.assertEqual(r_follow.scope_status, "in_scope")
        self.assertTrue(r_follow.verified, f"Verification issues: {r_follow.verification_issues}")
        self.assertIn("MYSURU", r_follow.response.upper())
        self.assertIn("Mango", r_follow.response)
        self.assertIsNone(r_follow.context.get("pending_clarification"))

    def test_08_unknown_location_extracts_entity_only(self):
        r = self._chat("What is the groundwater status of Atlantis?")
        self.assertEqual(r.scope_status, "out_of_scope")
        self.assertEqual(r.out_of_scope_reason, "unknown_location")
        self.assertIn("Atlantis", r.response)
        self.assertNotIn("What is the groundwater status of", r.response)

    def test_09_unsupported_metric_rejected(self):
        r = self._chat("What is the GDP of Karnataka?")
        self.assertEqual(r.scope_status, "out_of_scope")
        self.assertEqual(r.out_of_scope_reason, "unsupported_metric")

    def test_general_groundwater_and_existing_district_lookup(self):
        # Known location lookup regression
        r_anak = self._chat("What is the groundwater status of Anakapalli?")
        self.assertEqual(r_anak.scope_status, "in_scope")
        self.assertTrue(r_anak.verified, f"Verification issues: {r_anak.verification_issues}")
        self.assertIn("ANAKAPALLI", r_anak.response.upper())

        # General groundwater sustainability & concept questions without location
        r_gen = self._chat("What does stage of groundwater extraction mean?")
        self.assertEqual(r_gen.scope_status, "in_scope")
        self.assertTrue(r_gen.verified, f"Verification issues: {r_gen.verification_issues}")
        self.assertIn("Stage of Groundwater Extraction", r_gen.response)

        r_trend = self._chat("Why is groundwater stressed in Mysuru?", session_id="test_trend_session")
        self.assertEqual(r_trend.scope_status, "in_scope")
        self.assertTrue(r_trend.verified, f"Verification issues: {r_trend.verification_issues}")
        self.assertIn("MYSURU", r_trend.response.upper())

        r_sust = self._chat("How can groundwater sustainability be improved?", session_id="test_trend_session")
        self.assertEqual(r_sust.scope_status, "in_scope")
        self.assertTrue(r_sust.verified, f"Verification issues: {r_sust.verification_issues}")
        self.assertIn("MYSURU", r_sust.response.upper())

    def test_exposed_state_whatif_and_rainfall_comparison_regressions(self):
        # State-level What-If query must NOT arbitrarily pick first alphabetical district (Bagalkot)
        r_state_wi = self._chat("What if we reduce extraction by 20% in Karnataka?")
        self.assertEqual(r_state_wi.scope_status, "in_scope")
        self.assertTrue(r_state_wi.verified, f"Verification issues: {r_state_wi.verification_issues}")
        self.assertNotIn("I FOUND GROUNDWATER DATA FOR **BAGALKOT**", r_state_wi.response.upper())
        self.assertIn("STATE OVERVIEW — KARNATAKA", r_state_wi.response.upper())
        self.assertIn("district level", r_state_wi.response.lower())
        self.assertIsNotNone(r_state_wi.data)
        self.assertGreater(len(r_state_wi.data), 1)

        # District-level What-If continues to return exact district metrics
        r_dist_wi = self._chat("What happens if Mysore increases extraction by 10%?")
        self.assertEqual(r_dist_wi.scope_status, "in_scope")
        self.assertTrue(r_dist_wi.verified, f"Verification issues: {r_dist_wi.verification_issues}")
        self.assertIn("MYSURU", r_dist_wi.response.upper())

        # Rainfall comparison query includes rainfall-specific wording and mm values for both states
        r_rain_cmp = self._chat("Compare rainfall in Rajasthan and Gujarat")
        self.assertEqual(r_rain_cmp.scope_status, "in_scope")
        self.assertTrue(r_rain_cmp.verified, f"Verification issues: {r_rain_cmp.verification_issues}")
        self.assertIn("rainfall comparison", r_rain_cmp.response.lower())
        self.assertIn("RAJASTHAN", r_rain_cmp.response.upper())
        self.assertIn("GUJARAT", r_rain_cmp.response.upper())
        self.assertIn("mm", r_rain_cmp.response)

    def test_benchmark_evaluate_and_diagnostic_whatif_regressions(self):
        # Benchmark evaluation suite (50 questions)
        async def _eval_chat(msg: str, lang: str = "en") -> dict:
            resp = await main.chat(schemas.ChatMessage(message=msg, language=lang), db=self.db)
            return resp.__dict__

        report = sync_await(evaluate.run_evaluation(_eval_chat))
        print(
            f"\n[EVALUATE] total={report['total_tests']}, "
            f"accuracy={report['overall_accuracy_pct']}%, "
            f"refusal={report['correct_refusal_rate_pct']}%, "
            f"unsupported={report['unsupported_number_rate_pct']}%"
        )
        self.assertGreaterEqual(report["overall_accuracy_pct"], 90.0, f"Benchmark regression: {report}")
        self.assertEqual(report["correct_refusal_rate_pct"], 100.0, f"Refusal rate regression: {report}")
        self.assertEqual(report["unsupported_number_rate_pct"], 0.0, f"Hallucination regression: {report}")

        # What-If single simulation
        whatif_resp = sync_await(
            main.run_whatif(
                schemas.WhatIfRequest(state="KARNATAKA", district="MYSURU", pct_change=-20.0),
                db=self.db,
            )
        )
        self.assertEqual(whatif_resp.district, "MYSURU")
        self.assertIn("new_stage", whatif_resp.result)
        self.assertAlmostEqual(whatif_resp.result["new_stage"], 37.55, places=2)

        # Multi-sector scenario simulation
        scen_resp = sync_await(
            main.run_whatif_scenarios(
                MultiScenarioRequest(
                    state="KARNATAKA",
                    district="MYSURU",
                    scenarios=[ScenarioInput(name="Irrigation -20%", irrigation_pct_change=-20.0)],
                ),
                db=self.db,
            )
        )
        self.assertEqual(len(scen_resp.scenarios), 1)

        # Diagnostic endpoint
        diag_resp = sync_await(
            main.diagnose_groundwater(
                DiagnosticRequest(state="KARNATAKA", district="MYSURU"),
                db=self.db,
            )
        )
        self.assertEqual(diag_resp.location.get("district"), "MYSURU")
        self.assertTrue(diag_resp.verified)


if __name__ == "__main__":
    unittest.main()
