"""The trainer's mechanical challenges come from the checker, not from a hand.

The four kinds the published contract settles on its own — arithmetic,
direction, threshold and silence — are read out of a run of
``second_pass.checker`` over the case's own ledger and its own commentary.
The authored key still carries the two the contract cannot settle: whether a
driver is real, and whether the period is right.

These tests hold that line in both directions. The mechanical challenges have
to come from the run, and the driver and timing challenges have to keep coming
from the key.
"""

import unittest

from second_pass import cases, challenger, checker, session


CASE_IDS = [case_id for case_id, _title, _path in cases.list_cases()]


class TheCaseGoesIntoTheChecker(unittest.TestCase):

    def test_the_ledger_the_checker_reads_is_the_case_table(self):
        for case_id in CASE_IDS:
            case = cases.load_case(case_id)
            result = challenger.run_checker(case)
            self.assertEqual(len(result.accounts), len(case["accounts"]),
                             "%s: the checker read a different number of lines" % case_id)
            by_line = dict((a.num, a) for a in result.accounts)
            for account in case["accounts"]:
                read = by_line[account["line"]]
                self.assertEqual(read.prior, float(account["prior"]))
                self.assertEqual(read.cur, float(account["current"]))
                self.assertEqual(read.name, account["name"])
            self.assertEqual(result.stats["rowsSkipped"], 0,
                             "%s: a row of the case table was not read at all" % case_id)

    def test_the_memo_the_checker_reads_is_the_case_commentary(self):
        for case_id in CASE_IDS:
            case = cases.load_case(case_id)
            result = challenger.run_checker(case)
            labels = [s["label"] for s in result.sents]
            self.assertEqual(labels, [s["id"] for s in case["commentary"]["sentences"]],
                             "%s: the sentence identifiers did not survive the read" % case_id)

    def test_the_threshold_is_the_case_threshold(self):
        case = cases.load_case(CASE_IDS[0])
        result = challenger.run_checker(case)
        self.assertEqual(result.floorD, float(case["materiality"]["amount"]))
        self.assertEqual(result.floorP, float(case["materiality"]["percent"]))
        self.assertEqual(result.rule, "both")


class TheMechanicalChallengesComeFromTheRun(unittest.TestCase):

    def test_every_case_produces_mechanical_findings(self):
        for case_id in CASE_IDS:
            case = cases.load_case(case_id)
            findings = challenger.checker_findings(case)
            self.assertTrue(findings, "%s: the checker found nothing mechanical" % case_id)
            for finding in findings:
                self.assertIn(finding["kind"], challenger.MECHANICAL_KINDS)
                self.assertIn(finding["line"], cases.account_index(case))

    def test_the_planted_mechanical_defects_are_rediscovered_without_the_key(self):
        """A wrong sign and a line with no commentary are found by the contract,
        on every case, with the answer key never consulted."""
        for case_id in CASE_IDS:
            case = cases.load_case(case_id)
            found = set((f["kind"], f["line"]) for f in challenger.checker_findings(case))
            for defect in case["answer_key"]:
                kind = challenger.MECHANICAL_BY_DEFECT_TYPE.get(defect["type"])
                if kind in ("direction", "silence"):
                    self.assertIn((kind, defect["line"]), found,
                                  "%s %s (%s) was planted and the checker did not find it"
                                  % (case_id, defect["id"], defect["type"]))

    def test_a_substituted_challenge_says_the_checker_settled_it(self):
        for case_id in CASE_IDS:
            case = cases.load_case(case_id)
            built = challenger.deterministic_challenges(case)
            substituted = [c for c in built if c["template"].startswith("checker.")]
            self.assertTrue(substituted,
                            "%s: no mechanical challenge came out of the run" % case_id)
            for challenge in substituted:
                truth = challenge["truth"]
                self.assertEqual(truth["settled_by"], "checker")
                self.assertTrue(truth["checker_finding"],
                                "a challenge the checker settled carries no finding to show for it")
                self.assertIn(challenge["truth"]["type"], challenger.MECHANICAL_BY_DEFECT_TYPE)

    def test_driver_and_timing_challenges_stay_with_the_authored_key(self):
        """The contract does not know whether a driver is real or whether a
        month is the right one, and it must not pretend to."""
        judgment = ("unsupported_driver", "cutoff", "wrong_period", "reclass_as_growth",
                    "contradiction", "rounding_flips_conclusion", "driver_wrong_account",
                    "percent_as_absolute")
        for case_id in CASE_IDS:
            case = cases.load_case(case_id)
            for challenge in challenger.deterministic_challenges(case):
                if challenge["truth"].get("type") in judgment:
                    self.assertFalse(challenge["template"].startswith("checker."),
                                     "%s %s is a judgment call and the checker took it"
                                     % (case_id, challenge["id"]))
                    self.assertEqual(challenge["truth"].get("settled_by"), "answer key")

    def test_an_unscored_case_loads_and_a_short_key_is_still_refused(self):
        """An empty key means the case is not scored. A key that exists is a
        scored pack and still has to carry between eight and twelve defects."""
        import json
        import os
        import tempfile
        case = cases.load_case(CASE_IDS[0])
        folder = tempfile.mkdtemp(prefix="secondpass-unscored-")

        unscored = dict(case)
        unscored["id"] = "case-90-unscored"
        unscored["answer_key"] = []
        unscored["distractors"] = []
        with open(os.path.join(folder, "case-90-unscored.json"), "w", encoding="utf-8") as handle:
            json.dump(unscored, handle)
        loaded = cases.load_case("case-90-unscored", folder)
        built = challenger.deterministic_challenges(loaded)
        self.assertTrue(built, "an unscored case produced no mechanical challenges")

        short = dict(case)
        short["id"] = "case-91-short"
        short["answer_key"] = case["answer_key"][:2]
        with open(os.path.join(folder, "case-91-short.json"), "w", encoding="utf-8") as handle:
            json.dump(short, handle)
        with self.assertRaises(cases.CaseError):
            cases.load_case("case-91-short", folder)

    def test_a_case_with_no_answer_key_still_produces_a_list(self):
        """The point of the wiring: the trainer runs on any case."""
        case = cases.load_case(CASE_IDS[0])
        keyless = dict(case)
        keyless["answer_key"] = []
        keyless["distractors"] = []
        built = challenger.deterministic_challenges(keyless)
        self.assertTrue(built, "a case with no key produced no challenges at all")
        for challenge in built:
            self.assertEqual(challenge["truth"]["kind"], "checker")
            self.assertEqual(challenge["source"], "checker")
            self.assertEqual(cases.validate_challenge_bindings(challenge, keyless), [])

    def test_a_mechanical_challenge_binds_and_never_approves(self):
        for case_id in CASE_IDS:
            case = cases.load_case(case_id)
            built, _result = challenger.checker_challenges(case)
            movements = challenger.account_movements(case)
            for challenge in built:
                self.assertEqual(cases.validate_challenge_bindings(challenge, case), [],
                                 "%s %s does not bind to its own case" % (case_id, challenge["id"]))
                self.assertEqual(round(challenge["amount"], 2),
                                 round(abs(movements[challenge["line"]]), 2),
                                 "a mechanical challenge cited something other than the movement")
                self.assertIsNone(challenger.contains_approval_language(challenge["question"]))
                self.assertIn(challenge["tag"], cases.CHALLENGE_TAGS)

    def test_a_mechanical_challenge_asks_rather_than_answers(self):
        """The finding is what produced the challenge; it is not what a reviewer
        is handed. The checker's own wording stays in the log."""
        case = cases.load_case(CASE_IDS[0])
        built, _result = challenger.checker_challenges(case)
        for challenge in built:
            self.assertNotIn(challenge["truth"]["finding"], challenge["question"])
            public = challenger.public_challenges([challenge])[0]
            self.assertNotIn("truth", public)


class TheSessionCarriesTheRun(unittest.TestCase):

    def _finished(self):
        case = cases.load_case(CASE_IDS[0])
        review = session.ReviewSession(case, "R1", provider="deterministic", root=None)
        review.open_phase_1(60, soundness=3)
        review.commit_findings(["Account 6000 warehouse wages moved and nothing explains it."])
        review.set_confidence_aided(70)
        shown = review.reveal_challenges()
        review.record_teachback(shown[0]["id"], "accept",
                                "The account moves against the sentence and the amount does not "
                                "tie, so the memo needs correcting before release.")
        review.finish(write_log=False)
        return review

    def test_nothing_about_the_run_exists_before_the_gate(self):
        case = cases.load_case(CASE_IDS[0])
        review = session.ReviewSession(case, "R2", provider="deterministic", root=None)
        self.assertIsNone(review.checker_run)
        review.open_phase_1(50, soundness=3)
        review.commit_findings(["Nothing yet."])
        self.assertIsNone(review.checker_run,
                          "the checker ran before the participant's findings were sealed")

    def test_the_log_names_the_run_that_produced_the_mechanical_half(self):
        review = self._finished()
        log = review.to_log()
        block = log["checker"]
        self.assertIsNotNone(block, "the session log does not say which run produced the list")
        self.assertEqual(block["contract"], checker.CONTRACT_VERSION)
        self.assertTrue(block["run_id"].startswith("run-"))
        self.assertTrue(block["source_version"].startswith("src-"))
        self.assertEqual(block["policy"]["dollar_rule"], "more than")
        self.assertEqual(block["policy"]["percent_rule"], "at least")
        self.assertEqual(block["coverage"]["sent"],
                         len(review.case["commentary"]["sentences"]))
        self.assertEqual(log["challenger"]["checker"], block)

    def test_the_run_is_reproducible_from_the_log(self):
        """Same case, same contract, same source version. A reader can rerun it."""
        review = self._finished()
        again = challenger.run_checker(review.case)
        self.assertEqual(again.srcV, review.checker_run["source_version"])
        self.assertEqual(again.runId, review.checker_run["run_id"])


if __name__ == "__main__":
    unittest.main()
