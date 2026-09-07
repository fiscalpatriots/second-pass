"""The state machine, and the reason this file exists at all.

Second Pass makes one promise: the reviewer commits their own findings before
they see anything the machine produced. A promise like that cannot live in the
user interface, because a user interface is a suggestion. It lives here, in one
object that both surfaces have to go through, and it is enforced by refusing to
produce the challenge list at all until the commitment is sealed.

The order is fixed and the transitions are one way.

    briefing              the non-delegation rule is on screen
    phase_1_open          case revealed, confidence stated, clock running
    phase_1_committed     findings sealed, no edits, ever
    confidence_2_set      confidence stated for the second phase
    challenges_revealed   the challenge list is generated and shown
    teachback_done        every challenge has a verdict and a reason
    finished              scored, logged, key revealed

Calling anything out of order raises WithholdingError. The challenge list is
not generated early and hidden, it does not exist until the reviewer has
committed, so there is nothing in the process, in memory, or on the wire for a
determined reviewer to look at ahead of time.

Anonymity is enforced here too. A reviewer is R1 to R99 and nothing else. The
pilot promises that no name appears anywhere in the entry, and a field that
accepts free text is a field that eventually holds somebody's name.
"""

import datetime
import json
import os
import re
import time
import uuid

from . import cases, challenger, scoring

REVIEWER_PATTERN = re.compile(r"^R([1-9][0-9]?)$")

STATES = (
    "briefing",
    "phase_1_open",
    "phase_1_committed",
    "confidence_2_set",
    "challenges_revealed",
    "teachback_done",
    "finished",
)


class WithholdingError(Exception):
    """Raised whenever something asks for the challenge list too early."""


class ReviewerError(Exception):
    """Raised when a reviewer label could identify a person."""


def sessions_dir(root=None):
    if root:
        return root
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(os.path.dirname(here), "sessions")


def validate_reviewer(alias):
    if not alias or not REVIEWER_PATTERN.match(str(alias).strip()):
        raise ReviewerError(
            "Reviewer must be R1 to R99. Names, initials and email addresses are refused here "
            "because the pilot promises that no name appears anywhere in the entry."
        )
    return str(alias).strip()


def next_reviewer_alias(case_id=None, root=None):
    """Lowest R number not already used by a session file on disk."""
    directory = sessions_dir(root)
    used = set()
    if os.path.isdir(directory):
        for name in os.listdir(directory):
            if not name.endswith(".json"):
                continue
            found = re.search(r"_(R[1-9][0-9]?)_", name)
            if found:
                used.add(found.group(1))
    for number in range(1, 100):
        alias = "R%d" % number
        if alias not in used:
            return alias
    return "R99"


def _utc_now():
    return datetime.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


class ReviewSession(object):
    def __init__(self, case, reviewer, provider="auto", root=None, min_reason_words=scoring.MIN_REASON_WORDS):
        self.case = case
        self.reviewer = validate_reviewer(reviewer)
        self.provider = provider
        self.root = root
        self.min_reason_words = min_reason_words
        self.session_id = "%s_%s_%s" % (
            case["id"], self.reviewer, uuid.uuid4().hex[:8]
        )
        self.state = "briefing"
        self.started_at = _utc_now()
        self.events = []
        self.data = {
            "confidence_unaided": None,
            "confidence_aided": None,
            "soundness_rating": None,
            "findings_unaided": [],
            "findings_aided": [],
            "teachbacks": {},
            "seconds_phase_1": None,
            "seconds_phase_2": None,
        }
        self.challenges = None
        self.challenger_meta = None
        self._clock_1 = None
        self._clock_2 = None
        self.result = None
        self._log("session_opened", "reviewer opened case %s" % case["id"])

    # ------------------------------------------------------------- transitions

    def _log(self, event, cause, detail=None):
        entry = {"at": _utc_now(), "event": event, "state": self.state, "cause": cause}
        if detail:
            entry["detail"] = detail
        self.events.append(entry)

    def _require(self, expected, action):
        if self.state != expected:
            raise WithholdingError(
                "%s is not available in state '%s'. Second Pass requires the reviewer to "
                "commit their own findings first, and the order cannot be skipped." % (action, self.state)
            )

    def case_for_reviewer(self):
        """The stripped case. Available from the start, key and all."""
        return cases.reviewer_view(self.case)

    def open_phase_1(self, confidence, soundness=None):
        """Confidence before the phase, per the instrument. Starts the clock."""
        self._require("briefing", "Opening phase one")
        confidence = _as_percent(confidence, "confidence")
        self.data["confidence_unaided"] = confidence
        if soundness is not None:
            self.data["soundness_rating"] = _as_rating(soundness)
        self.state = "phase_1_open"
        self._clock_1 = time.time()
        self._log("confidence_unaided_recorded", "reviewer stated expectation before working",
                  {"confidence": confidence, "soundness": self.data["soundness_rating"]})
        return True

    def commit_findings(self, findings):
        """Seal the reviewer's own work. One way, no edits, no second bite."""
        self._require("phase_1_open", "Committing findings")
        cleaned = [text.strip() for text in findings if text and text.strip()]
        self.data["findings_unaided"] = cleaned
        self.data["seconds_phase_1"] = int(round(time.time() - self._clock_1)) if self._clock_1 else None
        self.state = "phase_1_committed"
        self._log("findings_committed", "reviewer sealed their unaided findings",
                  {"count": len(cleaned), "seconds": self.data["seconds_phase_1"]})
        return len(cleaned)

    def set_confidence_aided(self, confidence):
        self._require("phase_1_committed", "Stating confidence for phase two")
        confidence = _as_percent(confidence, "confidence")
        self.data["confidence_aided"] = confidence
        self.state = "confidence_2_set"
        self._log("confidence_aided_recorded", "reviewer stated expectation before the challenge list",
                  {"confidence": confidence})
        return True

    def reveal_challenges(self):
        """The gate. Nothing above this line can produce a challenge list."""
        if self.state in ("challenges_revealed", "teachback_done", "finished"):
            return challenger.public_challenges(self.challenges)
        if self.state != "confidence_2_set":
            raise WithholdingError(
                "The challenge list is withheld until the reviewer has committed their own "
                "findings and stated their confidence. Current state: '%s'." % self.state
            )
        self.challenges, self.challenger_meta = challenger.generate_challenges(
            self.case, provider=self.provider
        )
        self.state = "challenges_revealed"
        self._clock_2 = time.time()
        self._log("challenges_revealed", "commitment sealed, AI layer released", {
            "provider_used": self.challenger_meta["provider_used"],
            "challenge_count": self.challenger_meta["challenge_count"],
            "dropped": len(self.challenger_meta.get("dropped", [])),
            "fallback_reason": self.challenger_meta.get("fallback_reason"),
        })
        return challenger.public_challenges(self.challenges)

    def record_teachback(self, challenge_id, verdict, reason):
        if self.state not in ("challenges_revealed", "teachback_done"):
            raise WithholdingError("Teach-back is not open in state '%s'." % self.state)
        known = set(challenge["id"] for challenge in self.challenges)
        if challenge_id not in known:
            raise WithholdingError("No challenge '%s' in this session." % challenge_id)
        verdict = (verdict or "").strip().lower()
        if verdict not in ("accept", "reject"):
            raise WithholdingError("A teach-back verdict is 'accept' or 'reject', with a reason.")
        self.data["teachbacks"][challenge_id] = {
            "verdict": verdict,
            "reason": (reason or "").strip(),
            "at": _utc_now(),
        }
        self._log("teachback_recorded", "reviewer defended or refused a challenge in their own words",
                  {"challenge_id": challenge_id, "verdict": verdict,
                   "reason_words": len((reason or "").split())})
        return True

    def add_aided_findings(self, findings):
        """Anything the reviewer spots after the list that the list did not raise."""
        if self.state not in ("challenges_revealed", "teachback_done"):
            raise WithholdingError("Phase two findings are not open in state '%s'." % self.state)
        cleaned = [text.strip() for text in findings if text and text.strip()]
        self.data["findings_aided"] = cleaned
        self._log("aided_findings_recorded", "reviewer added findings the challenge list did not raise",
                  {"count": len(cleaned)})
        return len(cleaned)

    def outstanding_teachbacks(self):
        if not self.challenges:
            return []
        return [challenge["id"] for challenge in self.challenges
                if challenge["id"] not in self.data["teachbacks"]]

    def finish(self, write_log=True):
        if self.state == "finished":
            return self.result
        if self.state not in ("challenges_revealed", "teachback_done"):
            raise WithholdingError("Nothing to score in state '%s'." % self.state)
        if self._clock_2:
            self.data["seconds_phase_2"] = int(round(time.time() - self._clock_2))
        session_data = dict(self.data)
        session_data["reviewer"] = self.reviewer
        self.result = scoring.score_session(
            session_data, self.case, self.challenges, min_reason_words=self.min_reason_words
        )
        self.state = "finished"
        self._log("session_scored", "phase two closed and the session was scored",
                  {"catch_rate_unaided": self.result["scores"]["catch_rate_unaided"],
                   "catch_rate_aided": self.result["scores"]["catch_rate_aided"]})
        if write_log:
            self.write_log()
        return self.result

    # -------------------------------------------------------------------- log

    def to_log(self):
        """Everything a third party needs to recompute the scores from scratch."""
        return {
            "schema": "second-pass/session/v1",
            "session_id": self.session_id,
            "tool_version": __import__("second_pass").__version__,
            "case_id": self.case["id"],
            "case_file": os.path.basename(str(self.case.get("_path", ""))),
            "reviewer": self.reviewer,
            "started_at": self.started_at,
            "ended_at": _utc_now(),
            "state": self.state,
            "challenger": self.challenger_meta,
            "challenges": [
                {
                    "id": challenge["id"],
                    "line": challenge["line"],
                    "account": challenge["account"],
                    "amount": challenge["amount"],
                    "sentence": challenge.get("sentence"),
                    "citation": challenge["citation"],
                    "question": challenge["question"],
                    "source": challenge.get("source"),
                    "truth": challenge.get("truth"),
                }
                for challenge in (self.challenges or [])
            ],
            "commitments": self.data["findings_unaided"],
            "aided_findings": self.data["findings_aided"],
            "teachbacks": self.data["teachbacks"],
            "confidence": {
                "unaided": self.data["confidence_unaided"],
                "aided": self.data["confidence_aided"],
                "soundness_rating": self.data["soundness_rating"],
            },
            "timing": {
                "seconds_phase_1": self.data["seconds_phase_1"],
                "seconds_phase_2": self.data["seconds_phase_2"],
            },
            "scores": (self.result or {}).get("scores"),
            "match_trail": {
                "unaided": (self.result or {}).get("unaided_trail"),
                "aided": (self.result or {}).get("aided_trail"),
            },
            "teachback_detail": (self.result or {}).get("teachback_detail"),
            # Findings the answer key does not carry, in the reviewer's own
            # words. They are here so a facilitator can adjudicate them rather
            # than have the tool file them as wrong, and nothing in this block
            # reduces a catch rate.
            "findings_outside_key": (self.result or {}).get("findings_outside_key"),
            "events": self.events,
        }

    def write_log(self, root=None):
        directory = sessions_dir(root or self.root)
        if not os.path.isdir(directory):
            os.makedirs(directory)
        path = os.path.join(directory, self.session_id + ".json")
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(self.to_log(), handle, indent=2)
        return path


def _as_percent(value, field):
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise WithholdingError("%s must be a number between 0 and 100." % field)
    if number < 0 or number > 100:
        raise WithholdingError("%s must be between 0 and 100." % field)
    return round(number, 1)


def _as_rating(value):
    try:
        number = int(value)
    except (TypeError, ValueError):
        raise WithholdingError("Soundness rating must be a whole number from 1 to 5.")
    if number < 1 or number > 5:
        raise WithholdingError("Soundness rating must be from 1 to 5.")
    return number
