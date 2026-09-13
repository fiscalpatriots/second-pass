"""The September 2026 audit, turned into assertions.

An external audit of this trainer on 12 September 2026 ran two offline probes
against the frozen source and found four scoring defects. Each probe is
reproduced here against the same fixtures, with the INTENDED behaviour as the
assertion rather than the behaviour that was found.

    1  "Account 6000 has movement 72500. I accept the commentary as written."
       counted as a detected defect, because the alias hit and the case author
       had listed the amount among the defect keywords. Matching was standing
       in for correctness.
    2  Correct verdicts plus eight unrelated words scored full marks on what
       was called teach-back accuracy. A word count was standing in for
       reasoning.
    3  A defect the reviewer raised and then withdrew under challenge stayed in
       the aided count, because that count was a union. The arithmetic could
       not show the assistance doing harm.
    4  A challenge citing 999,999,999 against an account that moved 372,000,
       sentence id NONEXISTENT and "Imaginary document page 999" survived
       validation, because the question text happened to name a second real
       account. Formatting was standing in for validation.

Two more sit beside them: the session export dropped the challenge tag and the
evidence bar, kept no prompt and no provider response, and had no attempt
record; and the repository's own documents disagreed with each other about
whether a human pilot had run, how many cases the pilot scores, and whether a
codename is anonymity.

Run it: python tests/test_audit_repairs.py
"""

import io
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from second_pass import cases, challenger, matching, scoring, session  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

IRRELEVANT_REASON = "The blue umbrella is waiting outside beside the garden fence."
WITHDRAWAL_REASON = "I withdraw my original concern and accept this commentary as written now."


def read(name):
    with io.open(os.path.join(ROOT, name), encoding="utf-8") as handle:
        return handle.read()


class MatchingIsNotCorrectness(unittest.TestCase):
    """Probe 1. Naming the account and the figure is not finding the defect."""

    def setUp(self):
        self.case = cases.load_case("case-01-june")
        self.defect = self.case["answer_key"][0]

    def test_an_acceptance_statement_is_not_a_detected_defect(self):
        text = "Account %s has movement %s. I accept the commentary as written." % (
            self.defect["line"], self.defect["amount"])
        defect_id, evidence = matching.match_finding(text, self.case)
        self.assertEqual(defect_id, self.defect["id"],
                         "the text does point at the defect's account, and the log should say so")
        self.assertFalse(evidence["counts_as_detection"],
                         "a response that rejects the defect must not count as detecting it")
        self.assertEqual(evidence["status"], matching.STATUS_ACCEPTS)
        self.assertTrue(evidence["needs_adjudication"])
        self.assertEqual(evidence["acceptance_matched"], "accept the commentary")

        result = scoring.score_session(
            {"findings_unaided": [text], "teachbacks": {}}, self.case, [])
        self.assertEqual(result["scores"]["caught_unaided"], 0)
        self.assertEqual(result["scores"]["findings_for_adjudication"], 1)
        self.assertEqual(result["scores"]["findings_accepting_the_position"], 1)
        self.assertEqual(result["findings_for_adjudication"][0]["text"], text,
                         "the reviewer's words go to a person intact")

    def test_a_bare_restatement_of_the_figure_is_not_a_detected_defect(self):
        text = "Account %s has movement %s." % (self.defect["line"], self.defect["amount"])
        _defect_id, evidence = matching.match_finding(text, self.case)
        self.assertEqual(evidence["status"], matching.STATUS_UNSUPPORTED)
        self.assertFalse(evidence["counts_as_detection"])
        result = scoring.score_session(
            {"findings_unaided": [text], "teachbacks": {}}, self.case, [])
        self.assertEqual(result["scores"]["caught_unaided"], 0)
        self.assertEqual(result["scores"]["findings_unsupported"], 1)

    def test_a_supported_finding_still_counts(self):
        text = "Account 6000 warehouse wages moved 72,500 and there is no commentary on it at all."
        defect_id, evidence = matching.match_finding(text, self.case)
        self.assertEqual(defect_id, "D1")
        self.assertTrue(evidence["counts_as_detection"])
        self.assertEqual(evidence["status"], matching.STATUS_SUPPORTED)
        self.assertEqual(evidence["assertion_matched"], "no commentary")

    def test_a_numeric_keyword_is_identification_and_never_an_assertion(self):
        self.assertTrue(matching.is_numeric_keyword("72,500"))
        self.assertTrue(matching.is_numeric_keyword("23.5"))
        self.assertFalse(matching.is_numeric_keyword("no commentary"))
        for case in (self.case, cases.load_case("case-02-july"), cases.load_case("case-03-august")):
            for defect in case["answer_key"]:
                self.assertTrue(matching.assertion_keywords(defect),
                                "%s %s has only numeric keywords, so no finding can ever be "
                                "supported against it" % (case["id"], defect["id"]))


class CompletionIsNotReasoning(unittest.TestCase):
    """Probe 2. A word count measures completion and nothing else."""

    def setUp(self):
        self.case = cases.load_case("case-01-june")
        defect = self.case["answer_key"][0]
        self.challenge = {"id": "C1", "line": defect["line"],
                          "truth": {"kind": "defect", "ref": defect["id"]}}
        self.session = {"findings_unaided": [],
                        "teachbacks": {"C1": {"verdict": "accept", "reason": IRRELEVANT_REASON}}}

    def test_an_irrelevant_reason_earns_no_reasoning_score(self):
        scores = scoring.score_session(self.session, self.case, [self.challenge])["scores"]
        self.assertEqual(scores["teachback_completion"], 100.0,
                         "the item was completed, and completion is all the word count knows")
        self.assertEqual(scores["disposition_accuracy"], 100.0,
                         "the verdict was right, and that is a decision measure")
        self.assertIsNone(scores["reasoning_score"],
                          "eleven unrelated words must not produce a reasoning score")
        self.assertEqual(scores["reasoning_rubrics_scored"], 0)
        self.assertEqual(scores["defect_credit_pending_rubric"], 1,
                         "a defect credited from the disposition alone is marked as waiting on a "
                         "person")

    def test_the_old_metric_names_are_gone_rather_than_aliased(self):
        scores = scoring.score_session(self.session, self.case, [self.challenge])["scores"]
        self.assertNotIn("teachback_completeness", scores)
        self.assertNotIn("teachback_accuracy", scores)
        self.assertIn("word count", scores["teachback_completion_basis"])
        self.assertIn("verdict only", scores["disposition_accuracy_basis"])

    def test_the_rubric_has_three_dimensions_scored_zero_to_two(self):
        names = [name for name, _text in scoring.RUBRIC_DIMENSIONS]
        self.assertEqual(names, ["records_establish", "evidence_supports", "next_action"])
        self.assertEqual(scoring.RUBRIC_SCALE, (0, 1, 2))
        self.assertEqual(scoring.RUBRIC_MAX, 6)
        blank = scoring.blank_rubric()
        self.assertFalse(blank["scored"])
        self.assertIsNone(blank["total"])
        self.assertIsNone(blank["scorer_id"])
        self.assertEqual(sorted(blank["dimensions"]), sorted(names))

    def test_a_human_rubric_is_carried_and_needs_a_named_scorer(self):
        scored = dict(self.session)
        scored["reasoning_rubrics"] = {"C1": {"records_establish": 2, "evidence_supports": 1,
                                              "next_action": 1, "scorer_id": "F1",
                                              "adjudication": "credit stands"}}
        result = scoring.score_session(scored, self.case, [self.challenge])
        self.assertEqual(result["scores"]["reasoning_score"], 4)
        self.assertEqual(result["scores"]["reasoning_score_max"], 6)
        self.assertEqual(result["scores"]["reasoning_scored_by"], ["F1"])
        self.assertEqual(result["scores"]["defect_credit_pending_rubric"], 0)
        self.assertEqual(result["teachback_detail"][0]["reasoning_rubric"]["adjudication"],
                         "credit stands")

        unsigned = dict(self.session)
        unsigned["reasoning_rubrics"] = {"C1": {"records_establish": 2}}
        self.assertRaises(scoring.ScoringError, scoring.score_session,
                          unsigned, self.case, [self.challenge])

        off_scale = dict(self.session)
        off_scale["reasoning_rubrics"] = {"C1": {"records_establish": 3, "scorer_id": "F1"}}
        self.assertRaises(scoring.ScoringError, scoring.score_session,
                          off_scale, self.case, [self.challenge])


class TheFinalOutcomeIsTheFinalPosition(unittest.TestCase):
    """Probe 3. A withdrawn finding is not a final hit."""

    def setUp(self):
        self.case = cases.load_case("case-01-june")
        self.defect = self.case["answer_key"][0]
        self.challenge = {"id": "C1", "line": self.defect["line"],
                          "truth": {"kind": "defect", "ref": self.defect["id"]}}
        self.finding = ("Account 6000 warehouse wages moved 72,500 and there is no commentary on "
                        "it at all.")

    def _score(self, verdict, reason):
        return scoring.score_session(
            {"findings_unaided": [self.finding],
             "teachbacks": {"C1": {"verdict": verdict, "reason": reason}}},
            self.case, [self.challenge])["scores"]

    def test_a_withdrawn_unaided_finding_leaves_the_final_count(self):
        scores = self._score("reject", WITHDRAWAL_REASON)
        self.assertEqual(scores["caught_unaided"], 1, "the original decision is preserved")
        self.assertEqual(scores["caught_final"], 0, "the final position is that it is not a defect")
        self.assertEqual(scores["caught_aided"], scores["caught_final"],
                         "the aided figure every report quotes is the final figure")
        self.assertEqual(scores["withdrawn_ids"], [self.defect["id"]])
        self.assertLess(scores["lift"], 0,
                        "assistance that talked a reviewer out of a real finding has to be able "
                        "to show as harm")
        self.assertIn(self.defect["id"], scores["missed_ids"])

    def test_holding_the_finding_keeps_it(self):
        scores = self._score("accept", WITHDRAWAL_REASON.replace("I withdraw my original concern "
                                                                 "and accept", "I hold"))
        self.assertEqual(scores["caught_unaided"], 1)
        self.assertEqual(scores["caught_final"], 1)
        self.assertEqual(scores["withdrawn_ids"], [])
        self.assertEqual(scores["lift"], 0.0)

    def test_the_original_and_the_changed_decisions_are_both_kept(self):
        scores = self._score("reject", WITHDRAWAL_REASON)
        for field in ("caught_unaided_ids", "withdrawn_ids", "added_via_challenge_ids",
                      "caught_final_ids", "final_outcome_basis"):
            self.assertIn(field, scores)
        card = scoring.format_scorecard(
            scoring.score_session(
                {"findings_unaided": [self.finding],
                 "teachbacks": {"C1": {"verdict": "reject", "reason": WITHDRAWAL_REASON}}},
                self.case, [self.challenge]), self.case)
        self.assertIn("Withdrawn under challenge", card)
        self.assertIn("Catch rate, final", card)


class EveryBindingIsValidated(unittest.TestCase):
    """Probe 4. Identifiers and amounts have to resolve against the case."""

    def setUp(self):
        self.case = cases.load_case("case-01-june")

    def test_an_untied_amount_a_dead_sentence_and_invented_evidence_all_fail(self):
        raw = [{"line": "4000", "amount": 999999999, "sentence": "NONEXISTENT", "tag": "amount",
                "evidence": "Imaginary document page 999",
                "question": ("Account 4100 is also relevant. Please reconcile this amount to "
                             "account 4000.")}]
        kept, dropped = challenger.validate_challenges(raw, self.case, "offline diagnostic")
        self.assertEqual(kept, [], "naming a second real account must not launder a fake figure")
        self.assertEqual(len(dropped), 1)
        failures = dropped[0]["failures"]
        self.assertEqual(len(failures), 3, "each broken binding is reported on its own")
        joined = " ".join(failures)
        self.assertIn("999,999,999", joined)
        self.assertIn("ties to neither account", joined)
        self.assertIn("NONEXISTENT", joined)
        self.assertIn("sources inventory", joined)

    def test_each_binding_fails_on_its_own(self):
        base = {"line": "6000", "amount": 72500, "tag": "driver",
                "question": "Warehouse wages moved and the memo is silent. Explain it."}
        self.assertEqual(cases.validate_challenge_bindings(base, self.case), [])

        dead_sentence = dict(base, sentence="S99")
        self.assertEqual(len(cases.validate_challenge_bindings(dead_sentence, self.case)), 1)

        bad_tag = dict(base, tag="vibes")
        self.assertEqual(len(cases.validate_challenge_bindings(bad_tag, self.case)), 1)

        invented = dict(base, evidence_refs=["SRC-NOWHERE"])
        self.assertEqual(len(cases.validate_challenge_bindings(invented, self.case)), 1)

        real = dict(base, evidence_refs=["SRC-PAYROLL"])
        self.assertEqual(cases.validate_challenge_bindings(real, self.case), [])

    def test_an_amount_tied_to_the_other_named_account_is_kept(self):
        raw = [{"line": "4000", "amount": 65000, "tag": "transfer",
                "question": ("Distribution revenue carries $65,000 that account 4200 freight "
                             "billed to customers lost. Say what is left.")}]
        kept, dropped = challenger.validate_challenges(raw, self.case, "openai")
        self.assertEqual(len(kept), 1, "the figure is account 4200's own movement, so it ties")
        self.assertEqual(dropped, [])

    def test_requested_evidence_is_kept_apart_from_actual_sources(self):
        challenges, _meta = challenger.generate_challenges(self.case, provider="deterministic")
        drivers = [c for c in challenges
                   if c["truth"].get("type") in ("unsupported_driver", "missing_driver_material",
                                                 "driver_wrong_account", "reclass_as_growth")]
        self.assertTrue(drivers)
        for challenge in drivers:
            self.assertTrue(challenge["evidence_requested"],
                            "a driver challenge says what would count as evidence")
            self.assertEqual(challenge["evidence_refs"], [],
                             "a bar is not a document reference and is never resolved as one")
            self.assertIn(challenge["evidence_requested"], challenge["evidence"])
        self.assertIsNotNone(cases.resolve_source(self.case, "SRC-PAYROLL"))
        self.assertIsNotNone(cases.resolve_source(self.case, "the payroll register for June"))
        self.assertIsNone(cases.resolve_source(self.case, "Imaginary document page 999"))

    def test_every_case_declares_a_source_inventory(self):
        for case_id, _title, _path in cases.list_cases():
            case = cases.load_case(case_id)
            self.assertTrue(case["sources"], "%s has no sources inventory" % case_id)
            for source in case["sources"]:
                self.assertIn(source["kind"], cases.SOURCE_KINDS)

    def test_the_whole_pack_binds_to_itself(self):
        for case_id, _title, _path in cases.list_cases():
            case = cases.load_case(case_id)
            challenges, _meta = challenger.generate_challenges(case, provider="deterministic")
            for challenge in challenges:
                self.assertEqual(cases.validate_challenge_bindings(challenge, case), [],
                                 "%s %s does not bind to its own case" % (case_id, challenge["id"]))


class TheExportPreservesWhatHappened(unittest.TestCase):
    """The session log carries what was shown, what produced it, and the attempt."""

    def _finished_session(self, tmpdir):
        case = cases.load_case("case-01-june")
        review = session.ReviewSession(case, "R1", provider="deterministic", root=tmpdir,
                                       consent_version="v1-2026-09-13", mode="practice",
                                       form="A", first_attempt=True)
        review.open_phase_1(60, soundness=3)
        review.commit_findings(["Account 6000 warehouse wages moved 72,500 and there is no "
                                "commentary on it at all."])
        review.set_confidence_aided(70)
        shown = review.reveal_challenges()
        first = shown[0]["id"]
        review.record_teachback(first, "accept",
                                "The account moves against the sentence and the amount ties to "
                                "the schedule, so the memo needs correcting.")
        review.finish(write_log=False)
        return review, shown

    def test_the_export_keeps_everything_the_participant_saw(self):
        review, shown = self._finished_session(None)
        log = review.to_log()
        self.assertEqual(log["schema"], "second-pass/session/v2")
        self.assertEqual(log["shown_to_participant"], shown,
                         "the export must carry the participant's copy exactly")
        for item in log["shown_to_participant"]:
            self.assertIn("tag", item)
            self.assertIn("evidence", item)
            self.assertIn("evidence_requested", item)
            self.assertIn("evidence_refs", item)
            self.assertNotIn("truth", item, "the participant's copy never carries a truth block")
        for challenge in log["challenges"]:
            self.assertIn("truth", challenge)
            self.assertIn("tag", challenge)
            self.assertIn("evidence", challenge)

    def test_the_export_keeps_the_prompt_the_case_version_and_the_raw_output(self):
        review, _shown = self._finished_session(None)
        log = review.to_log()
        self.assertEqual(log["case"]["schema"], cases.CASE_SCHEMA)
        self.assertEqual(log["case"]["sources_declared"], len(review.case["sources"]))
        self.assertIn("prompt", log)
        for field in ("id", "version", "file", "system_prompt", "user_prompt"):
            self.assertIn(field, log["prompt"])
        for field in ("requested", "used", "model", "raw_response", "fallback_reason", "dropped"):
            self.assertIn(field, log["provider"])
        self.assertEqual(log["provider"]["used"], "deterministic")
        self.assertIsNone(log["provider"]["raw_response"],
                          "the deterministic provider has no response, and the field says so "
                          "rather than being absent")
        self.assertIn("no provider response", log["provider"]["raw_response_note"])

    def test_the_export_carries_the_minimum_attempt_record(self):
        review, _shown = self._finished_session(None)
        log = review.to_log()
        for field in ("attempt_id", "participant_pseudonym", "consent_version", "role",
                      "product_version", "case_version", "form", "mode", "first_attempt",
                      "assistance_source", "started", "completed", "submission_state",
                      "test_attempt"):
            self.assertIn(field, log["attempt"])
        self.assertEqual(log["attempt"]["participant_pseudonym"], "R1")
        self.assertEqual(log["attempt"]["consent_version"], "v1-2026-09-13")
        self.assertEqual(log["attempt"]["mode"], "practice")
        self.assertIn("not anonymity", log["attempt"]["pseudonym_note"])

        self.assertEqual(len(log["responses"]), len(log["challenges"]))
        for field in ("item_id", "original_decision", "actual_reason", "evidence_references",
                      "confidence", "assistance_revealed", "final_decision", "final_reason",
                      "elapsed_active_seconds", "skipped_or_missing_reason",
                      "feedback_revealed_at"):
            self.assertIn(field, log["responses"][0])
        for field in ("key_version", "decision_result", "human_rubric_scores", "scorer_id",
                      "out_of_key_findings", "adjudication", "exclusion_reason",
                      "final_resolution"):
            self.assertIn(field, log["scoring"])

    def test_a_missing_question_stays_missing(self):
        review, _shown = self._finished_session(None)
        log = review.to_log()
        unanswered = [row for row in log["responses"] if row["final_decision"] is None]
        self.assertTrue(unanswered, "this session deliberately leaves items unanswered")
        for row in unanswered:
            self.assertIsNone(row["final_reason"])
            self.assertIsNone(row["actual_reason"])
            self.assertEqual(row["skipped_or_missing_reason"], "not answered")
        self.assertIn("attempt.role", log["missing"])
        self.assertTrue(any(item.startswith("response.confidence") for item in log["missing"]))
        self.assertTrue(any("human_rubric_scores" in item for item in log["missing"]))
        for item in log["missing"]:
            self.assertTrue(item.startswith(("attempt.", "response.", "scoring.")),
                            "a missing field is named by its path, never given a placeholder "
                            "value: %r" % item)
        json.dumps(log)


class TheDocumentsAgreeWithEachOther(unittest.TestCase):
    """The sixth audit finding. A repository that contradicts itself is evidence."""

    def test_no_document_claims_a_human_pilot_has_run(self):
        self.assertIn("The human pilot is the next step and it has not run.", read("README.md"))
        source = read("second_pass/scoring.py")
        self.assertIn("No human pilot has run", source)
        self.assertNotIn("measured here on real people", source,
                         "the scoring module claimed a measurement on people that has not "
                         "happened")

    def test_the_pilot_document_and_the_simulation_document_agree_on_the_case_count(self):
        pilot = " ".join(read("PILOT.md").split()).lower()
        simulation = " ".join(read("SIMULATION.md").split()).lower()
        self.assertIn("two scored cases per reviewer", pilot)
        self.assertIn("two scored cases per reviewer", simulation,
                      "SIMULATION.md described a single-case protocol that PILOT.md does not run")
        self.assertNotIn("runs a single case per reviewer, which is how the human pilot is "
                         "written", simulation)

    def test_no_document_promises_anonymity(self):
        for name in ("README.md", "PILOT.md", "GOVERNANCE.md", "second_pass/session.py"):
            text = read(name)
            for word in ("anonymous", "anonymity", "anonymously"):
                if word in text.lower():
                    self.assertIn("pseudonym", text.lower(),
                                  "%s uses '%s' without saying that a codename is pseudonymity"
                                  % (name, word))

    def test_the_governance_change_log_records_the_reconciliation(self):
        governance = read("GOVERNANCE.md")
        self.assertIn("Change log", governance)
        self.assertIn("13 September 2026", governance)
        for marker in ("matching.py", "scoring.py", "results.py", "cases.py", "session.py"):
            self.assertIn(marker, governance,
                          "the change log does not name the module it repaired: %s" % marker)


if __name__ == "__main__":
    print("SECOND PASS AUDIT REGRESSION TESTS")
    print("=" * 78)
    unittest.main(verbosity=2)
