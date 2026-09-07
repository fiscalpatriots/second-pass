"""The withholding rule cannot be bypassed from the interface.

The claim Second Pass makes to a reviewer is that the machine's challenge list
is unavailable until they have committed their own findings. This file is the
evidence for that claim, and it tests the wire rather than the screen, because
a user interface can be edited by anybody with a browser and a keyboard.

What is proved here.

    1. The state machine refuses to produce a challenge list in any state
       before the commitment is sealed.
    2. The HTTP route returns 409 rather than data, and the refusal body
       carries no challenge text and no answer key.
    3. Every response a reviewer can obtain before committing is searched for
       the exact text of every planted defect and every challenge the tool
       would have raised. None of it is there. The list is not generated early
       and hidden. It does not exist yet.
    4. A commitment cannot be reopened, so a reviewer cannot commit, look, and
       then improve their own list.
    5. The reviewer's copy of a challenge never carries the answer, so nobody
       can tell a real challenge from a weak one except by reading it.
    6. A reviewer label that could identify a person is refused.

Run it: python tests/test_withholding.py
"""

import json
import os
import shutil
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from second_pass import cases, challenger, server, session as session_mod  # noqa: E402

CASE_ID = "case-01-june"
PRINTED = []


def emit(line=""):
    PRINTED.append(line)
    print(line)


class StateMachineTest(unittest.TestCase):

    def setUp(self):
        self.case = cases.load_case(CASE_ID)
        self.tmp = tempfile.mkdtemp(prefix="secondpass-")
        self.review = session_mod.ReviewSession(self.case, "R1", provider="deterministic", root=self.tmp)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_challenges_withheld_in_every_early_state(self):
        blocked = []
        with self.assertRaises(session_mod.WithholdingError):
            self.review.reveal_challenges()
        blocked.append(self.review.state)

        self.review.open_phase_1(confidence=50, soundness=3)
        with self.assertRaises(session_mod.WithholdingError):
            self.review.reveal_challenges()
        blocked.append(self.review.state)

        self.review.commit_findings(["Account 5100 inbound freight rose 73800 and the memo says it fell"])
        with self.assertRaises(session_mod.WithholdingError):
            self.review.reveal_challenges()
        blocked.append(self.review.state)

        self.assertIsNone(self.review.challenges, "no challenge list existed before the gate opened")
        self.review.set_confidence_aided(60)
        opened = self.review.reveal_challenges()
        self.assertTrue(len(opened) > 0)
        emit("Withheld in states: %s. Released in state: %s, %d challenges." % (
            ", ".join(blocked), self.review.state, len(opened)))

    def test_a_commitment_cannot_be_reopened(self):
        self.review.open_phase_1(confidence=50, soundness=3)
        self.review.commit_findings(["Account 6000 warehouse wages moved 62500 and is unexplained"])
        with self.assertRaises(session_mod.WithholdingError):
            self.review.commit_findings(["a better list, written after thinking about it more"])
        self.assertEqual(len(self.review.data["findings_unaided"]), 1)
        emit("Second commit refused. The sealed list is still the one that was sealed.")

    def test_confidence_cannot_be_restated_after_the_fact(self):
        self.review.open_phase_1(confidence=50, soundness=3)
        with self.assertRaises(session_mod.WithholdingError):
            self.review.open_phase_1(confidence=95, soundness=5)
        self.assertEqual(self.review.data["confidence_unaided"], 50.0)
        emit("Confidence cannot be restated once the phase is open.")

    def test_reviewer_label_refuses_a_name(self):
        for label in ("Sebastian", "S. Campos", "khaled", "R1 (Khaled)", ""):
            with self.assertRaises(session_mod.ReviewerError):
                session_mod.validate_reviewer(label)
        self.assertEqual(session_mod.validate_reviewer("R5"), "R5")
        emit("Reviewer labels: names refused, R1 to R99 accepted.")


class HttpWithholdingTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="secondpass-http-")
        cls.httpd = server.make_server(port=0, sessions_root=cls.tmp, provider="deterministic")
        cls.port = cls.httpd.server_address[1]
        cls.thread = threading.Thread(target=cls.httpd.serve_forever)
        cls.thread.daemon = True
        cls.thread.start()
        cls.case = cases.load_case(CASE_ID)
        challenges, _meta = challenger.generate_challenges(cls.case, provider="deterministic")
        cls.secret_strings = [challenge["question"] for challenge in challenges]
        cls.secret_strings += [defect["correct"] for defect in cls.case["answer_key"]]
        cls.secret_strings += [defect["claim"] for defect in cls.case["answer_key"]]
        cls.secret_strings += [d["why_wrong"] for d in cls.case.get("distractors", [])]

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def call(self, method, path, payload=None):
        url = "http://127.0.0.1:%d%s" % (self.port, path)
        data = json.dumps(payload).encode("utf-8") if payload is not None else None
        request = urllib.request.Request(url, data=data, method=method,
                                         headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                body = response.read().decode("utf-8")
                return response.status, body
        except urllib.error.HTTPError as error:
            return error.code, error.read().decode("utf-8")

    def assert_no_leak(self, body, where):
        for secret in self.secret_strings:
            probe = secret[:60]
            self.assertNotIn(probe, body,
                             "%s leaked withheld content: %s" % (where, probe[:40]))

    def test_full_route_sequence(self):
        status, body = self.call("GET", "/api/config")
        self.assertEqual(status, 200)
        self.assert_no_leak(body, "GET /api/config")

        status, body = self.call("POST", "/api/session", {"case_id": CASE_ID, "reviewer": "R1"})
        self.assertEqual(status, 200)
        self.assert_no_leak(body, "POST /api/session")
        session_id = json.loads(body)["session_id"]
        base = "/api/session/" + session_id

        status, body = self.call("GET", base + "/case")
        self.assertEqual(status, 200)
        self.assert_no_leak(body, "GET case")
        payload = json.loads(body)["case"]
        self.assertNotIn("answer_key", payload)
        self.assertNotIn("distractors", payload)
        self.assertEqual(len(payload["accounts"]), len(self.case["accounts"]))

        status, body = self.call("GET", base + "/challenges")
        self.assertEqual(status, 409, "the challenge route must refuse before any commitment")
        self.assertTrue(json.loads(body)["withheld"])
        self.assert_no_leak(body, "GET challenges before phase one")
        emit("GET challenges before phase one: 409, body carries the reason and nothing else.")

        self.call("POST", base + "/phase1", {"confidence": 55, "soundness": 4})
        status, body = self.call("GET", base + "/challenges")
        self.assertEqual(status, 409, "still refused while the reviewer is working")
        self.assert_no_leak(body, "GET challenges during phase one")
        emit("GET challenges during phase one: 409.")

        status, body = self.call("POST", base + "/commit", {
            "findings": ["Account 5100 inbound freight rose 73800 and the memo says it declined"]})
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["committed"], 1)

        status, body = self.call("GET", base + "/challenges")
        self.assertEqual(status, 409, "confidence for phase two is still outstanding")
        self.assert_no_leak(body, "GET challenges after commit, before confidence")
        emit("GET challenges after commit but before the second confidence question: 409.")

        status, body = self.call("POST", base + "/commit", {"findings": ["a second, better list"]})
        self.assertEqual(status, 409, "a sealed commitment must not reopen over HTTP either")
        emit("Second POST commit: 409.")

        status, body = self.call("POST", base + "/finish", {})
        self.assertEqual(status, 409, "nothing can be scored before the challenge list is worked")

        self.call("POST", base + "/confidence2", {"confidence": 65})
        status, body = self.call("GET", base + "/challenges")
        self.assertEqual(status, 200, "the gate opens once, and only once, in the right order")
        challenges = json.loads(body)["challenges"]
        self.assertTrue(len(challenges) >= 10)
        emit("GET challenges after the commitment is sealed: 200, %d challenges." % len(challenges))

        for challenge in challenges:
            self.assertNotIn("truth", challenge, "the reviewer's copy carries the answer")
            self.assertIn("citation", challenge)
            self.assertTrue(challenge["citation"].startswith("Account "))
            self.assertIsInstance(challenge["amount"], (int, float))
        emit("Every challenge carries a line and an amount, and none carries its own truth flag.")

        for challenge in challenges:
            status, _body = self.call("POST", base + "/teachback", {
                "challenge_id": challenge["id"], "verdict": "accept",
                "reason": "The account moves the other way and the amount ties to the schedule, so this stands."})
            self.assertEqual(status, 200)

        status, body = self.call("POST", base + "/finish", {})
        self.assertEqual(status, 200)
        finished = json.loads(body)
        self.assertIn("scores", finished)
        self.assertIn("answer_key", finished, "the key is released only at the end")
        self.assertEqual(len(finished["answer_key"]),
                         len(self.case["answer_key"]) + len(self.case.get("distractors", [])))
        log_path = os.path.join(self.tmp, finished["log_file"])
        self.assertTrue(os.path.isfile(log_path), "a session log must be written for traceability")
        with open(log_path, "r", encoding="utf-8") as handle:
            log = json.load(handle)
        for field in ("case_id", "commitments", "challenges", "teachbacks", "confidence", "scores", "events"):
            self.assertIn(field, log)
        emit("Finish: scored, key released, session log written with %d events." % len(log["events"]))

    def test_a_second_session_cannot_read_the_first(self):
        _status, body = self.call("POST", "/api/session", {"case_id": CASE_ID, "reviewer": "R2"})
        session_id = json.loads(body)["session_id"]
        status, body = self.call("GET", "/api/session/" + session_id + "/challenges")
        self.assertEqual(status, 409)
        status, body = self.call("GET", "/api/session/not-a-real-session/challenges")
        self.assertEqual(status, 404)
        self.assert_no_leak(body, "unknown session")
        emit("A fresh session starts closed, and an unknown session id returns nothing.")

    def test_named_reviewer_refused_over_http(self):
        status, body = self.call("POST", "/api/session", {"case_id": CASE_ID, "reviewer": "Sebastian"})
        self.assertEqual(status, 409)
        self.assertIn("R1 to R99", json.loads(body)["error"])
        emit("A named reviewer is refused at the API, not only in the dropdown.")


if __name__ == "__main__":
    print("SECOND PASS WITHHOLDING TEST")
    print("=" * 78)
    unittest.main(verbosity=2)
