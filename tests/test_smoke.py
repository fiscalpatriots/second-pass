"""Smoke test: all three cases, end to end, against the answer key.

Runs three synthetic reviewers through every case using the deterministic
challenger, and checks that the scores land where they have to land.

    Reviewer A  writes a finding for every planted defect, accepts every true
                challenge and rejects every weak one. Must score 100 percent
                unaided, 100 percent aided, and 100 percent on teach-back.
    Reviewer B  finds the first three defects only, then works the challenge
                list properly. Must show a real lift and a real confidence gap.
    Reviewer C  finds nothing and waves the whole list through with one word
                reasons. Must score zero on teach-back completeness and must
                not be credited with catching anything, because accepting a
                machine challenge without being able to explain it is the
                behaviour the tool exists to catch.

The point of reviewer C is the point of the tool. If the scoring gave C credit,
the entry would be measuring compliance rather than judgment.

Run it: python tests/test_smoke.py
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from second_pass import cases, challenger, matching, scoring  # noqa: E402

LONG_REASON = (
    "The account moves in the other direction from the sentence and the amount ties to the "
    "schedule, so the memo has to be corrected before it goes anywhere."
)
SHORT_REASON = "fine"

PRINTED = []


def emit(line=""):
    PRINTED.append(line)
    print(line)


def finding_for(defect):
    """A finding written the way a reviewer who saw the defect would write it.

    The keyword is an ASSERTION keyword, never a bare figure. Several case files
    list the defect amount among the keywords, and a reviewer who writes only an
    account and a number has identified the line without saying anything is
    wrong with it, which since 13 September 2026 is not a detected defect.
    """
    alias = defect["match"]["aliases"][0]
    keyword = matching.first_assertion_keyword(defect)
    return "Account %s %s, %s, %s" % (
        defect["line"], alias, keyword, int(abs(defect["amount"])))


def build_session(case, challenges, findings, teachback_mode, confidence):
    teachbacks = {}
    for challenge in challenges:
        truth = challenge.get("truth", {})
        if teachback_mode == "correct":
            verdict = "accept" if truth.get("kind") == "defect" else "reject"
            reason = LONG_REASON
        elif teachback_mode == "waved":
            verdict = "accept"
            reason = SHORT_REASON
        else:
            continue
        teachbacks[challenge["id"]] = {"verdict": verdict, "reason": reason}
    return {
        "reviewer": "R0",
        "confidence_unaided": confidence,
        "confidence_aided": confidence,
        "soundness_rating": 3,
        "findings_unaided": findings,
        "findings_aided": [],
        "teachbacks": teachbacks,
        "seconds_phase_1": 480,
        "seconds_phase_2": 420,
    }


class SmokeTest(unittest.TestCase):

    def setUp(self):
        self.cases = [cases.load_case(path) for _id, _title, path in cases.list_cases()]
        self.assertEqual(len(self.cases), 3, "the defect pack should carry three cases")

    def test_pack_shape(self):
        emit("Defect pack")
        emit("-" * 78)
        for case in self.cases:
            rows = cases.movement_table(case)
            material = [row for row in rows if row["material"]]
            kinds = set(defect["type"] for defect in case["answer_key"])
            emit("%-18s %-26s accounts %2d  sentences %2d  defects %2d  weak %d  material lines %2d" % (
                case["id"], case["period"]["current"], len(rows),
                len(case["commentary"]["sentences"]), len(case["answer_key"]),
                len(case.get("distractors", [])), len(material)))
            self.assertEqual(len(kinds), len(case["answer_key"]), "defect kinds must be distinct in a case")
            self.assertTrue(8 <= len(case["answer_key"]) <= 12)
            self.assertTrue(case["company"]["fictional"] is True)
        emit()

    def test_every_challenge_carries_a_citation_and_no_approval(self):
        for case in self.cases:
            challenges, meta = challenger.generate_challenges(case, provider="deterministic")
            self.assertEqual(meta["provider_used"], "deterministic")
            account_lines = set(account["line"] for account in case["accounts"])
            for challenge in challenges:
                self.assertIn(challenge["line"], account_lines,
                              "challenge cites an account that is not in the table")
                self.assertIsInstance(challenge["amount"], float)
                self.assertTrue(challenge["citation"].startswith("Account "))
                self.assertIsNone(challenger.contains_approval_language(challenge["question"]),
                                  "a challenge used approval language: %s" % challenge["question"])
            public = challenger.public_challenges(challenges)
            for item in public:
                self.assertNotIn("truth", item, "the truth block reached the reviewer's copy")

    def test_reviewer_view_hides_the_key(self):
        for case in self.cases:
            view = cases.reviewer_view(case)
            blob = repr(view)
            for defect in case["answer_key"]:
                self.assertNotIn(defect["correct"][:40], blob)
                self.assertNotIn(defect["claim"][:40], blob)
            for distractor in case.get("distractors", []):
                self.assertNotIn(distractor["text"][:40], blob)

    def test_three_reviewers_across_three_cases(self):
        emit("Scores, deterministic challenger, three synthetic reviewers")
        emit("-" * 78)
        header = "%-18s %-10s %8s %8s %7s %10s %9s %9s" % (
            "Case", "Reviewer", "Unaided", "Aided", "Lift", "Precision", "Teach", "Conf gap")
        emit(header)
        emit("-" * 78)
        for case in self.cases:
            challenges, _meta = challenger.generate_challenges(case, provider="deterministic")
            key = case["answer_key"]

            perfect = build_session(case, challenges, [finding_for(d) for d in key], "correct", 80)
            partial = build_session(case, challenges, [finding_for(d) for d in key[:3]], "correct", 70)
            waved = build_session(case, challenges, [], "waved", 90)

            for label, session in (("A perfect", perfect), ("B partial", partial), ("C waved", waved)):
                result = scoring.score_session(session, case, challenges)
                scores = result["scores"]
                emit("%-18s %-10s %7.1f%% %7.1f%% %6.1f %9.1f%% %8.1f%% %8.1f" % (
                    case["id"], label,
                    scores["catch_rate_unaided"], scores["catch_rate_aided"], scores["lift"],
                    scores["precision_unaided"] if scores["precision_unaided"] is not None else 0.0,
                    scores["teachback_completion"], scores["confidence_gap_unaided"]))

                if label == "A perfect":
                    self.assertEqual(scores["catch_rate_unaided"], 100.0,
                                     "a reviewer who names every defect must score 100 unaided")
                    self.assertEqual(scores["catch_rate_aided"], 100.0)
                    self.assertEqual(scores["disposition_accuracy"], 100.0)
                    self.assertEqual(scores["false_challenges_unaided"], 0)
                    self.assertEqual(scores["distractors_rejected"], scores["distractors_shown"])
                if label == "B partial":
                    self.assertEqual(scores["caught_unaided"], 3)
                    self.assertEqual(scores["catch_rate_aided"], 100.0,
                                     "working the challenge list properly must close the gap")
                    self.assertGreater(scores["lift"], 0)
                    self.assertGreater(scores["confidence_gap_unaided"], 0,
                                       "stated confidence must exceed what was actually caught")
                if label == "C waved":
                    self.assertEqual(scores["catch_rate_unaided"], 0.0)
                    self.assertEqual(scores["catch_rate_aided"], 0.0,
                                     "accepting challenges without a reason must not count as catching")
                    self.assertEqual(scores["teachback_completion"], 0.0)
                    self.assertEqual(scores["distractors_rejected"], 0)
        emit()

    def test_precision_is_against_the_key_and_out_of_key_findings_are_counted_apart(self):
        """Finding 6 from pilot one, in a test.

        A reviewer who writes a real accounting point the answer key does not
        carry has their precision reduced and nothing else. It must not touch a
        catch rate, and the words have to survive into the log so a facilitator
        can adjudicate them rather than have the tool file them as wrong.
        """
        case = self.cases[0]
        challenges, _meta = challenger.generate_challenges(case, provider="deterministic")
        outside = [
            "The revolver covenant headroom is not disclosed anywhere in this pack and a reader "
            "cannot tell whether the month breaches it",
            "There is no cash or working capital line in this schedule, so a reader cannot tell "
            "whether the revenue growth converted",
        ]
        findings = [finding_for(case["answer_key"][0])] + outside
        session = build_session(case, challenges, findings, "correct", 60)
        result = scoring.score_session(session, case, challenges)
        scores = result["scores"]
        self.assertEqual(scores["caught_unaided"], 1)
        self.assertEqual(scores["findings_outside_key"], 2)
        self.assertEqual(scores["findings_outside_key_unadjudicated"], 2,
                         "neither out-of-key finding matched a planted weak lead")
        self.assertEqual(scores["precision_unaided"], 33.3)
        self.assertEqual(scores["precision_basis"], "against the answer key")
        self.assertEqual(scores["catch_rate_unaided"],
                         round(100.0 / len(case["answer_key"]), 1),
                         "an out-of-key finding must not move a catch rate")
        verbatim = [row["text"] for row in result["findings_outside_key"]]
        for text in outside:
            self.assertIn(text, verbatim, "an out-of-key finding was not kept verbatim for the log")
        card = scoring.format_scorecard(result, case)
        self.assertIn("Precision, against key", card)
        self.assertIn("facilitator to adjudicate", card)
        emit("Precision: 1 finding in the key and 2 outside it gives %s against the key. Neither "
             "out-of-key finding moved the catch rate, and both are in the log verbatim."
             % scores["precision_unaided"])
        emit()

    def test_a_ceiling_note_prints_when_unaided_catch_is_at_the_top(self):
        """Finding 7. A lift of zero from a ceiling is not a lift of zero from nothing."""
        case = self.cases[0]
        challenges, _meta = challenger.generate_challenges(case, provider="deterministic")
        perfect = build_session(case, challenges, [finding_for(d) for d in case["answer_key"]],
                                "correct", 80)
        result = scoring.score_session(perfect, case, challenges)
        self.assertTrue(result["scores"]["catch_ceiling_unaided"])
        card = scoring.format_scorecard(result, case)
        self.assertIn("Ceiling:", card)
        for key in ("lift", "confidence_gap", "teachback_completion", "disposition_accuracy",
                    "reasoning_score", "precision"):
            self.assertIn(scoring.DEFINITIONS[key], card,
                          "the scorecard did not define %s beside the number" % key)
        partial = build_session(case, challenges, [finding_for(case["answer_key"][0])], "correct", 80)
        low = scoring.score_session(partial, case, challenges)
        self.assertFalse(low["scores"]["catch_ceiling_unaided"])
        self.assertNotIn("Ceiling:", scoring.format_scorecard(low, case))
        emit("Ceiling note prints at %.0f percent unaided and stays off at %.1f percent." % (
            result["scores"]["catch_rate_unaided"], low["scores"]["catch_rate_unaided"]))
        emit()

    def test_every_cited_amount_ties_to_the_named_account(self):
        """Finding 1, the one that cost pilot one the most credibility.

        A challenge cites the movement of the account it names. Where it cites
        something else, the text has to name the other account in words. The one
        sanctioned exception is a weak challenge planted as a wrong
        recomputation, where the mis-citation is the thing being tested, and the
        case file has to declare that shape for it to be allowed.
        """
        checked = 0
        for case in self.cases:
            movements = challenger.account_movements(case)
            index = cases.account_index(case)
            challenges, _meta = challenger.generate_challenges(case, provider="deterministic")
            for challenge in challenges:
                checked += 1
                movement = abs(movements[challenge["line"]])
                if round(challenge["amount"], 2) == round(movement, 2):
                    continue
                shape = (challenge.get("truth") or {}).get("shape")
                if shape == "bad_recomputation":
                    continue
                other = challenger._names_another_account(
                    challenge["question"], challenge["line"], index)
                self.assertIsNotNone(
                    other,
                    "%s %s cites %s against account %s, which moved %s, and names no other "
                    "account: %s" % (case["id"], challenge["id"], challenge["amount"],
                                     challenge["line"], movement, challenge["question"]))
        emit("Citation tie: %d challenges checked across three cases. Every cited amount is the "
             "named account's own movement, or the text names the account the figure belongs to."
             % checked)
        emit()

    def test_a_counterparty_is_named_in_words_not_just_implied(self):
        """The other half of finding 1: say it out loud, with its own movement."""
        for case in self.cases:
            movements = challenger.account_movements(case)
            challenges, _meta = challenger.generate_challenges(case, provider="deterministic")
            by_ref = dict((c["truth"]["ref"], c) for c in challenges
                          if c["truth"]["kind"] == "defect")
            for defect in case["answer_key"]:
                counterparty = defect.get("counterparty")
                if not counterparty:
                    continue
                text = by_ref[defect["id"]]["question"]
                self.assertIn(counterparty["line"], text,
                              "%s %s does not name its counterparty account" % (case["id"], defect["id"]))
                self.assertIn(cases.format_amount(abs(movements[counterparty["line"]])), text,
                              "%s %s names the counterparty without its own movement"
                              % (case["id"], defect["id"]))
        emit("Every counterparty is named by line and by its own movement in the challenge text.")
        emit()

    def test_no_case_plants_two_weak_challenges_of_the_same_shape(self):
        """Finding 3. In pilot one all six weak challenges were one shape."""
        shapes_by_case = {}
        for case in self.cases:
            shapes = [d["shape"] for d in case.get("distractors", [])]
            self.assertEqual(len(shapes), len(set(shapes)),
                             "%s plants the same weak challenge shape twice: %s"
                             % (case["id"], shapes))
            self.assertGreaterEqual(len(shapes), 3,
                                    "%s plants fewer than three weak challenges" % case["id"])
            for shape in shapes:
                self.assertIn(shape, cases.DISTRACTOR_SHAPES)
            shapes_by_case[case["id"]] = shapes
        across = set()
        for shapes in shapes_by_case.values():
            across.update(shapes)
        self.assertGreaterEqual(len(across), 3,
                                "the pack uses fewer than three weak challenge shapes")
        emit("Weak challenge shapes, %d distinct across the pack, none repeated inside a case:"
             % len(across))
        for case_id, shapes in sorted(shapes_by_case.items()):
            emit("  %-18s %s" % (case_id, ", ".join(shapes)))
        emit()

    def test_defect_kinds_and_slots_rotate_across_the_pack(self):
        """Finding 4. Pilot one put the same kind in the same slot in all three."""
        kinds = [set(d["type"] for d in case["answer_key"]) for case in self.cases]
        union = set()
        for kind_set in kinds:
            union.update(kind_set)
        self.assertEqual(union, set(cases.DEFECT_TYPES),
                         "the pack does not cover all twelve defect kinds")
        for index, kind_set in enumerate(kinds):
            for other in kinds[index + 1:]:
                self.assertNotEqual(kind_set, other,
                                    "two cases carry an identical set of defect kinds")
        percent_cases = [case["id"] for case in self.cases
                         if any(d["type"] == "percent_as_absolute" for d in case["answer_key"])]
        self.assertLessEqual(len(percent_cases), 1,
                             "the percent-into-dollar defect appears in more than one case: %s"
                             % percent_cases)
        for position in range(min(len(case["answer_key"]) for case in self.cases)):
            at_position = set(case["answer_key"][position]["type"] for case in self.cases)
            self.assertGreater(len(at_position), 1,
                               "every case carries the same defect kind in key slot %d" % (position + 1))
        emit("Kinds: all twelve across the pack, no two cases with the same set, "
             "percent-into-dollar in %d case, and no key slot holding one kind in all three."
             % len(percent_cases))
        emit()

    def test_every_challenge_carries_a_tag_that_does_not_reveal_weakness(self):
        """Finding 9. A tag only weak challenges carried would give them away."""
        for case in self.cases:
            challenges, _meta = challenger.generate_challenges(case, provider="deterministic")
            defect_tags = set()
            weak_tags = set()
            for challenge in challenges:
                self.assertIn(challenge["tag"], cases.CHALLENGE_TAGS,
                              "%s %s has no valid tag" % (case["id"], challenge["id"]))
                self.assertIn("tag %s" % challenge["tag"], challenge["citation"])
                if challenge["truth"]["kind"] == "defect":
                    defect_tags.add(challenge["tag"])
                else:
                    weak_tags.add(challenge["tag"])
            self.assertTrue(weak_tags.issubset(defect_tags),
                            "%s has tags that only weak challenges carry: %s"
                            % (case["id"], sorted(weak_tags - defect_tags)))
            for challenge in challenges:
                if challenge["truth"].get("type") in ("unsupported_driver",
                                                      "missing_driver_material",
                                                      "driver_wrong_account",
                                                      "reclass_as_growth"):
                    self.assertTrue(challenge["evidence"],
                                    "%s %s asks for a driver without saying what would count"
                                    % (case["id"], challenge["id"]))
                    self.assertIsNone(
                        challenger.contains_approval_language(challenge["evidence"]))
        emit("Tags: every challenge carries one of eight, weak challenges share tags with real "
             "ones, and every driver challenge states its evidence bar.")
        emit()

    def test_a_template_that_does_not_fit_its_sentence_is_not_used(self):
        """Finding 2. The percent template must read the sentence first."""
        labelled = "Interest expense rose 1.9 percent, or $1,900, on the revolver."
        bare = "Service revenue grew by 28,200 on contracts signed in the spring."
        self.assertTrue(challenger._percent_is_labelled(labelled))
        self.assertFalse(challenger._percent_is_labelled(bare))
        for case in self.cases:
            challenges, _meta = challenger.generate_challenges(case, provider="deterministic")
            for challenge in challenges:
                if challenge["truth"].get("type") != "percent_as_absolute":
                    continue
                sentence = challenger._sentence_text(case, challenge["sentence"])
                if challenger._percent_is_labelled(sentence):
                    self.assertEqual(challenge["template"], "percent_as_absolute.labelled")
                    self.assertNotIn("which of the two numbers is a percentage",
                                     challenge["question"],
                                     "a sentence that labels its own percentage was asked which "
                                     "of its numbers is a percentage")
                if challenge["truth"].get("type") == "reclass_as_growth":
                    self.assertEqual(challenge["template"], "reclass_as_growth.counterparty")
        emit("Template fit: the percent challenge changes shape when the sentence already labels "
             "its percentage, and a transfer with a known other side stops asking for one.")
        emit()

    def test_approval_language_and_untied_amounts_are_refused_from_a_model(self):
        case = self.cases[0]
        raw = [
            {"line": "5100", "amount": 73800, "question": "Inbound freight looks good and needs no further work."},
            {"line": "9999", "amount": 100, "question": "Account that does not exist."},
            {"line": "6000", "amount": "not a number", "question": "No amount to recompute."},
            {"line": "6000", "amount": 62500, "question": "Warehouse wages moved and the memo is silent. Explain it."},
            {"line": "4000", "amount": 65000, "question": "Distribution revenue carries $65,000 that account 4200 freight billed to customers lost. Say what is left.", "tag": "transfer"},
            {"line": "6000", "amount": 72500, "question": "Warehouse wages moved and the memo is silent. Explain it.", "tag": "driver"},
        ]
        kept, dropped = challenger.validate_challenges(raw, case, "openai")
        self.assertEqual(len(kept), 2)
        self.assertEqual(len(dropped), 4)
        reasons = " ".join(item["reason"] for item in dropped)
        self.assertIn("approval language", reasons)
        self.assertIn("not in the table", reasons)
        self.assertIn("recomputed", reasons)
        self.assertIn("names no other account", reasons)
        self.assertEqual(kept[0]["tag"], "transfer",
                         "a challenge that names the other account in words is kept")
        self.assertEqual(kept[1]["tag"], "driver")
        emit("Model output validation: 4 of 6 challenges refused. Reasons: %s" % "; ".join(
            item["reason"] for item in dropped))
        emit()


if __name__ == "__main__":
    print("SECOND PASS SMOKE TEST")
    print("=" * 78)
    print("Keys: %s" % ", ".join("%s %s" % pair for pair in sorted(challenger.key_status().items())))
    print("AI layer under test: deterministic")
    print("")
    unittest.main(verbosity=2)
