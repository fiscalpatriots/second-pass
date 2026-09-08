"""One simulated reviewer, end to end, and the four refusals that hold it in order.

The simulation driver splits a session across three processes, and a state
machine that only holds inside one process is not a state machine. This file
runs the whole thing through the command line the way a reviewer agent runs it,
with hand-written findings and teach-back files, and then tries every way there
is to get the challenge list early or to score something that was never worked.

What is proved here.

    1. A full simulated session runs: start writes the reviewer-safe view,
       commit seals the findings and releases the challenge list, finish scores
       it and writes a session log carrying simulated: true and the persona.
    2. view.md holds no answer key, no distractor text and no challenge text.
       The challenge list does not exist on disk until the commitment is sealed.
    3. Commit before findings.json exists is refused.
    4. A second commit is refused, so a reviewer cannot commit, read the
       challenge list, and then improve their own findings.
    5. Finish before commit is refused.
    6. A reviewer label that could identify a person is refused, and nothing is
       written when it is.
    7. Aggregation labels the set as simulated reviewers, and --only splits the
       two populations.
    8. The schema example the two commands print is invented. No account, name,
       figure, defect or weak challenge from any case in the pack is in it, and
       nothing the pack plants is in what the commands print.

Run it: python tests/test_sim.py
"""

import json
import os
import re
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from second_pass import cases, cli, results, sim  # noqa: E402

CASE_ID = "case-01-june"
LONG_REASON = (
    "I recomputed the cited amount against the movement table and the sentence that claims to "
    "explain it, and the memo does not survive that check."
)
PRINTED = []


def emit(line=""):
    PRINTED.append(line)
    print(line)


def read(path):
    with open(path, "r", encoding="utf-8") as handle:
        return handle.read()


def run(argv):
    """The command line, exactly as a reviewer agent invokes it."""
    return cli.main(argv)


class SimDriverTest(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="secondpass-sim-")
        self.dir = os.path.join(self.tmp, "R1-case-01-june")
        self.sessions = os.path.join(self.tmp, "sessions")
        self.case = cases.load_case(CASE_ID)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    # ------------------------------------------------------------- the helpers

    def start(self, reviewer="R1", persona="experienced", directory=None):
        return run(["sim", "start", "--case", CASE_ID, "--reviewer", reviewer,
                    "--dir", directory or self.dir, "--persona", persona,
                    "--allow-any-dir",
                    "--sessions-dir", self.sessions, "--provider", "deterministic"])

    def write_findings(self, findings, confidence=70, soundness=3):
        with open(os.path.join(self.dir, "findings.json"), "w", encoding="utf-8") as handle:
            json.dump({"findings": findings, "confidence": confidence,
                       "soundness": soundness}, handle, indent=2)

    def write_teachback(self, verdict_for, confidence=85):
        text = read(os.path.join(self.dir, "challenges.md"))
        ids = re.findall(r"^## (C\d+)", text, re.M)
        responses = [{"id": cid, "verdict": verdict_for(cid), "reason": LONG_REASON} for cid in ids]
        with open(os.path.join(self.dir, "teachback.json"), "w", encoding="utf-8") as handle:
            json.dump({"responses": responses, "confidence": confidence}, handle, indent=2)
        return ids

    def finding_for(self, defect):
        return "Account %s %s, %s, %s" % (
            defect["line"], defect["match"]["aliases"][0],
            defect["match"]["keywords"][0], int(abs(defect["amount"])))

    # --------------------------------------------------------------- the tests

    def test_full_simulated_session(self):
        emit("A full simulated session, run through the command line")
        emit("-" * 78)
        self.assertEqual(self.start(), 0)

        view = read(os.path.join(self.dir, "view.md"))
        self.assertIn("| Line | Account | Prior | Current | Variance | Percent |", view)
        self.assertIn("Draft commentary from management", view)
        for defect in self.case["answer_key"]:
            self.assertNotIn(defect["correct"][:40], view, "view.md leaked the answer key")
            self.assertNotIn(defect["claim"][:40], view)
        for distractor in self.case.get("distractors", []):
            self.assertNotIn(distractor["text"][:40], view, "view.md leaked a weak challenge")
        self.assertFalse(os.path.isfile(os.path.join(self.dir, "challenges.md")),
                         "the challenge list existed before the commitment was sealed")
        self.assertFalse(os.path.isfile(os.path.join(self.dir, "truth.json")))
        state = json.loads(read(os.path.join(self.dir, "state.json")))
        self.assertIsNone(state["challenges"], "state.json carried challenges before the seal")
        emit("start   view.md written, %d characters, no key and no challenge list on disk" % len(view))

        key = self.case["answer_key"]
        self.write_findings([self.finding_for(defect) for defect in key[:3]], confidence=75)
        self.assertEqual(run(["sim", "commit", "--dir", self.dir, "--allow-any-dir"]), 0)

        challenges = read(os.path.join(self.dir, "challenges.md"))
        ids = re.findall(r"^## (C\d+)", challenges, re.M)
        self.assertEqual(len(ids), len(key) + len(self.case.get("distractors", [])))
        for distractor in self.case.get("distractors", []):
            self.assertIn(distractor["text"][:40], challenges,
                          "the weak challenges must be in the list the reviewer sees")
            self.assertNotIn(distractor["why_wrong"][:40], challenges,
                             "challenges.md revealed which challenge is weak")
        for defect in key:
            self.assertNotIn(defect["correct"][:40], challenges,
                             "challenges.md handed over the answer")
        self.assertNotIn("distractor", challenges.lower(),
                         "challenges.md named the planted weak leads")
        self.assertNotIn("weak", challenges.lower(),
                         "challenges.md told the reviewer that some challenges are weak")
        self.assertNotIn("truth", challenges.lower())
        emit("commit  %d challenges written, weak ones included and unmarked" % len(ids))

        # This reviewer accepts everything, including the weak challenges, so
        # teach-back accuracy has to fall short of 100 percent.
        self.write_teachback(lambda cid: "accept", confidence=90)
        self.assertEqual(run(["sim", "finish", "--dir", self.dir, "--allow-any-dir"]), 0)

        logs = [name for name in os.listdir(self.sessions) if name.endswith(".json")]
        self.assertEqual(len(logs), 1)
        log = json.loads(read(os.path.join(self.sessions, logs[0])))
        self.assertEqual(log["schema"], "second-pass/session/v1")
        self.assertIs(log["simulated"], True)
        self.assertEqual(log["persona"], "experienced")
        self.assertEqual(log["reviewer"], "R1")
        self.assertEqual(log["state"], "finished")
        self.assertEqual(len(log["commitments"]), 3)
        self.assertEqual(log["confidence"]["post_teachback"], 90.0)
        for field in ("challenger", "challenges", "teachbacks", "confidence", "timing",
                      "scores", "match_trail", "events"):
            self.assertIn(field, log, "the simulated log is not the same shape as a real one")
        scores = log["scores"]
        self.assertEqual(scores["caught_unaided"], 3)
        self.assertEqual(scores["distractors_rejected"], 0,
                         "a reviewer who accepts the weak challenges refuses none of them")
        self.assertLess(scores["teachback_accuracy"], 100.0)
        emit("finish  simulated: true, persona experienced, caught %d of %d unaided and %d of %d "
             "aided, teach-back accuracy %s%%" % (
                 scores["caught_unaided"], scores["defects_present"],
                 scores["caught_aided"], scores["defects_present"], scores["teachback_accuracy"]))
        emit()

    def test_commit_before_findings_is_refused(self):
        self.assertEqual(self.start(), 0)
        self.assertEqual(run(["sim", "commit", "--dir", self.dir, "--allow-any-dir"]), 2,
                         "commit without findings.json must be refused")
        self.assertFalse(os.path.isfile(os.path.join(self.dir, "challenges.md")),
                         "a refused commit still produced a challenge list")
        with self.assertRaises(sim.SimError):
            sim.commit(self.dir)
        emit("Refused: commit before findings.json exists, and no challenge list was written.")

    def test_second_commit_is_refused(self):
        self.assertEqual(self.start(), 0)
        self.write_findings(["Account 5100 inbound freight rose and the memo says it declined"])
        self.assertEqual(run(["sim", "commit", "--dir", self.dir, "--allow-any-dir"]), 0)
        first = read(os.path.join(self.dir, "challenges.md"))
        self.write_findings(["Account 5100 inbound freight rose and the memo says it declined",
                             "Account 6400 bad debt does not tie to the memo at 42000"])
        self.assertEqual(run(["sim", "commit", "--dir", self.dir, "--allow-any-dir"]), 2,
                         "a second commit must be refused")
        state = json.loads(read(os.path.join(self.dir, "state.json")))
        self.assertEqual(len(state["data"]["findings_unaided"]), 1,
                         "the sealed findings were reopened by a second commit")
        self.assertEqual(read(os.path.join(self.dir, "challenges.md")), first,
                         "a second commit regenerated the challenge list")
        emit("Refused: a second commit. The first commitment of 1 finding stands and the "
             "challenge list is unchanged.")

    def test_finish_before_commit_is_refused(self):
        self.assertEqual(self.start(), 0)
        with open(os.path.join(self.dir, "teachback.json"), "w", encoding="utf-8") as handle:
            json.dump({"responses": [{"id": "C1", "verdict": "accept", "reason": LONG_REASON}],
                       "confidence": 80}, handle)
        self.assertEqual(run(["sim", "finish", "--dir", self.dir, "--allow-any-dir"]), 2,
                         "finish before commit must be refused")
        self.assertFalse(os.path.isdir(self.sessions) and
                         [n for n in os.listdir(self.sessions) if n.endswith(".json")],
                         "a refused finish still wrote a session log")
        with self.assertRaises(sim.SimError):
            sim.finish(self.dir)
        emit("Refused: finish before commit, and no session log was written.")

    def test_a_named_reviewer_is_refused(self):
        directory = os.path.join(self.tmp, "named")
        self.assertEqual(self.start(reviewer="Alex", directory=directory), 2,
                         "a name must be refused as a reviewer label")
        self.assertFalse(os.path.isdir(directory),
                         "a refused session still created its folder")
        for bad in ("R0", "R100", "alex@example.edu", "AR", ""):
            self.assertEqual(self.start(reviewer=bad, directory=directory), 2,
                             "'%s' should not be accepted as a reviewer label" % bad)
        emit("Refused: a personal name, R0, R100, an email address, initials and an empty label. "
             "R1 to R99 only, and nothing is written when a label is refused.")

    def test_finish_twice_is_refused(self):
        self.assertEqual(self.start(), 0)
        self.write_findings(["Account 5100 inbound freight rose when the memo says it declined"])
        self.assertEqual(run(["sim", "commit", "--dir", self.dir, "--allow-any-dir"]), 0)
        self.write_teachback(lambda cid: "reject")
        self.assertEqual(run(["sim", "finish", "--dir", self.dir, "--allow-any-dir"]), 0)
        self.assertEqual(run(["sim", "finish", "--dir", self.dir, "--allow-any-dir"]), 2,
                         "a scored session must not be scored twice")
        logs = [name for name in os.listdir(self.sessions) if name.endswith(".json")]
        self.assertEqual(len(logs), 1, "the second finish wrote another log")
        emit("Refused: finishing a session that is already scored. One log, not two.")

    def test_start_into_a_used_folder_is_refused(self):
        self.assertEqual(self.start(), 0)
        self.assertEqual(self.start(reviewer="R2"), 2,
                         "starting a second session in the same folder must be refused")
        emit("Refused: a second session in a folder that already holds one.")

    def test_the_answer_key_stays_out_of_the_score_block(self):
        self.assertEqual(self.start(), 0)
        self.write_findings([])
        self.assertEqual(run(["sim", "commit", "--dir", self.dir, "--allow-any-dir"]), 0)
        self.write_teachback(lambda cid: "reject")
        review, result, _path, _log = sim.finish(self.dir)
        block = sim.score_block(result, review.case, debrief=False)
        self.assertGreater(len(result["scores"]["missed_ids"]), 0)
        for defect in self.case["answer_key"]:
            self.assertNotIn(defect["correct"][:40], block,
                             "the score block handed the answer key to the reviewer")
        debrief = sim.score_block(result, review.case, debrief=True)
        self.assertIn("Still missed at the end of the session:", debrief)
        emit("The score block withholds the key from the reviewer and prints it under --debrief, "
             "so an agent running all three cases does not learn the taxonomy from case one.")

    def test_a_dir_outside_sim_runs_is_refused(self):
        """Finding 10. Pilot one lost its backslashes to bash and wrote a folder
        called simrunsR6-case-02-july at the repository root, then echoed the
        mangled path back as though it had been asked for."""
        stray = os.path.join(self.tmp, "simrunsR6-case-02-july")
        code = run(["sim", "start", "--case", CASE_ID, "--reviewer", "R6", "--dir", stray,
                    "--sessions-dir", self.sessions, "--provider", "deterministic"])
        self.assertEqual(code, 2, "a --dir outside sim/runs must be refused")
        self.assertFalse(os.path.isdir(stray), "a refused --dir still created its folder")
        with self.assertRaises(sim.SimError) as caught:
            sim.check_dir(stray)
        message = str(caught.exception)
        self.assertIn("outside", message)
        self.assertIn("forward slashes", message)
        self.assertIn("working directory does not persist", message)
        self.assertIn("--allow-any-dir", message)
        self.assertIn(os.path.abspath(stray), message,
                      "the refusal has to echo the path it actually resolved to")
        inside = os.path.join(sim.sim_runs_root(), "R9-case-01-june")
        self.assertEqual(sim.check_dir(inside), inside, "a path inside sim/runs is accepted")
        self.assertEqual(sim.check_dir(stray, allow_any=True), stray)
        emit("Refused: a --dir outside sim/runs, with the resolved path echoed back, the "
             "forward slash advice, and the note that the working directory does not persist.")

    def test_the_printed_prompts_carry_the_whole_schema_and_the_rules(self):
        """Finding 8. Pilot one printed a schema missing soundness, never printed
        the eight word rule at the step that needed it, and never said what
        confidence is measured against."""
        import io as _io
        import contextlib

        buffer = _io.StringIO()
        with contextlib.redirect_stdout(buffer):
            self.assertEqual(self.start(), 0)
        started = buffer.getvalue()
        for needle in ('"findings"', '"confidence"', '"soundness"', "0 to 100", "1 to 5",
                       "share of the planted defects"):
            self.assertIn(needle, started, "sim start did not print: %s" % needle)

        self.write_findings(["Account 5100 inbound freight rose when the memo says it declined"])
        buffer = _io.StringIO()
        with contextlib.redirect_stdout(buffer):
            self.assertEqual(run(["sim", "commit", "--dir", self.dir, "--allow-any-dir"]), 0)
        committed = buffer.getvalue()
        for needle in ('"responses"', '"verdict"', '"reason"', '"findings"', '"confidence"',
                       "eight words", "share of the planted defects", "do not hold"):
            self.assertIn(needle, committed, "sim commit did not print: %s" % needle)
        emit("Printed prompts: both schemas in full, the soundness field, the eight word rule, "
             "and what confidence is measured against.")

    def test_the_printed_schema_example_leaks_no_case(self):
        """Pilot two, finding 4. The schema printed by sim start and sim commit
        used to be written from case-01-june: its accounts, its own movements,
        its direction reversal, its missing driver, and the correct reject for
        one of its weak challenges. A reviewer who read the prompt before working
        that case was handed three answers by the tool that exists to withhold
        them. The example is now invented, and this walks the whole pack to prove
        it."""
        import io as _io
        import contextlib

        buffer = _io.StringIO()
        with contextlib.redirect_stdout(buffer):
            self.assertEqual(self.start(), 0)
            self.write_findings(["Account 5100 moved and the sentence that claims to explain it "
                                 "does not survive a recomputation"])
            self.assertEqual(run(["sim", "commit", "--dir", self.dir, "--allow-any-dir"]), 0)
        printed = buffer.getvalue()

        schemas = sim.FINDINGS_SCHEMA + "\n" + sim.TEACHBACK_SCHEMA
        self.assertIn(schemas.splitlines()[1], printed,
                      "the example printed is not the example under test")

        # Forward. Every account code, account name and dollar figure the example
        # carries is invented, and none of it is anywhere in the pack.
        codes = set(re.findall(r"Account (\d{3,5})", schemas))
        amounts = set(re.findall(r"\$(\d{1,3}(?:,\d{3})*)", schemas))
        self.assertTrue(codes, "the example stopped naming an account")
        self.assertTrue(amounts, "the example stopped carrying a dollar figure")

        def absent(needle, haystack, message):
            # assertNotIn prints the whole haystack, and a case file is 16,000
            # characters. The reader needs the needle and the file, not the pack.
            self.assertFalse(needle in haystack, message)

        checked = 0
        for case_id, _title, path in cases.list_cases():
            raw = read(path)
            for code in sorted(codes):
                absent(code, raw,
                       "%s carries account %s, which the printed example names" % (case_id, code))
            for amount in sorted(amounts):
                absent(amount, raw,
                       "%s carries %s, which the printed example cites" % (case_id, amount))
                absent(amount.replace(",", ""), raw,
                       "%s carries %s unformatted, which the printed example cites" %
                       (case_id, amount))
            for _code, name, _amount in sim.EXAMPLE_ACCOUNTS:
                absent(name.lower(), raw.lower(),
                       "%s carries an account called %s" % (case_id, name))
            checked += 1

        # Backward. Nothing the pack actually plants is anywhere in what the two
        # commands print: not an account name, not a defect's cited movement, and
        # not the text of a weak challenge or its reason for being wrong.
        low = printed.lower()
        movements = 0
        for case_id, _title, _path in cases.list_cases():
            case = cases.load_case(case_id)
            index = cases.account_index(case)
            for account in case["accounts"]:
                absent(account["name"].lower(), low,
                       "the printed prompt names %s, an account in %s" %
                       (account["name"], case_id))
            for defect in case["answer_key"]:
                account = index[defect["line"]]
                movement = abs(account["current"] - account["prior"])
                if movement:
                    absent("$" + "{:,}".format(movement), printed,
                           "the printed prompt cites the movement on line %s of %s" %
                           (defect["line"], case_id))
                    movements += 1
                absent(defect["correct"][:40], printed,
                       "the printed prompt carries %s of %s, verbatim" % (defect["id"], case_id))
                absent(defect["claim"][:40], printed,
                       "the printed prompt carries the claim behind %s of %s" %
                       (defect["id"], case_id))
            for distractor in case.get("distractors", []):
                absent(distractor["text"][:40], printed,
                       "the printed prompt carries weak challenge %s of %s" %
                       (distractor["id"], case_id))
                absent(distractor["why_wrong"][:40], printed,
                       "the printed prompt carries the reject for %s of %s" %
                       (distractor["id"], case_id))

        # And the invented set is declared in one place, so a future example
        # cannot quietly stop being the set this test walked.
        self.assertEqual(codes, set(code for code, _n, _a in sim.EXAMPLE_ACCOUNTS))
        self.assertEqual(amounts, set("{:,}".format(a) for _c, _n, a in sim.EXAMPLE_ACCOUNTS))

        emit("Printed example: %d invented account(s) and %d invented figure(s), checked against "
             "all %d case files. %d planted movements, every account name, every defect claim and "
             "every weak challenge checked against what the two commands print." %
             (len(codes), len(amounts), checked, movements))

    def test_results_label_the_population(self):
        self.assertEqual(self.start(persona="novice"), 0)
        self.write_findings(["Account 5100 inbound freight rose when the memo says it declined"])
        self.assertEqual(run(["sim", "commit", "--dir", self.dir, "--allow-any-dir"]), 0)
        self.write_teachback(lambda cid: "accept")
        self.assertEqual(run(["sim", "finish", "--dir", self.dir, "--allow-any-dir"]), 0)

        aggregated = results.aggregate(results.load_logs(self.sessions))
        self.assertTrue(aggregated["summary"]["any_simulated"])
        report = results.format_report(aggregated)
        markdown = results.format_markdown(aggregated)
        self.assertIn("simulated reviewers", report.splitlines()[0])
        for heading in ("Pooled over simulated reviewers",
                        "Mean of simulated reviewer rates",
                        "Confidence against accuracy over simulated reviewers",
                        "Teach-back and time over simulated reviewers"):
            self.assertIn(heading, report, "a heading was not labelled: %s" % heading)
        self.assertIn("| Reviewer | Persona | Case |", markdown)
        self.assertIn("Pooled, simulated reviewers", markdown)
        self.assertIn("novice", markdown)

        self.assertEqual(len(results.load_logs(self.sessions, only="simulated")), 1)
        self.assertEqual(len(results.load_logs(self.sessions, only="human")), 0)
        emit("Aggregation: title, four headings and the markdown table all say simulated "
             "reviewers, and --only human returns nothing from a simulated set.")
        emit()


if __name__ == "__main__":
    print("SECOND PASS SIMULATION DRIVER TEST")
    print("=" * 78)
    print("AI layer under test: deterministic")
    print("")
    unittest.main(verbosity=2)
