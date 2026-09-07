"""The simulation driver: language-model reviewers through the real machine.

The pilot in PILOT.md puts people in a room. This module puts model agents
through the same state machine, one process per step, so that a reviewer who is
a model can be held to exactly the rule a reviewer who is a person is held to:
commit your own findings before the tool shows you anything it produced.

Three commands, three files, in this order.

    sim start   creates the session and writes view.md, the reviewer-safe view
    (the reviewer writes findings.json)
    sim commit  seals the findings, releases the challenge list, writes challenges.md
    (the reviewer writes teachback.json)
    sim finish  records the teach-back, scores, writes the session log

Nothing here is a shortcut around session.py. Every transition goes through
ReviewSession, the same object the web page and the terminal runner go through,
and the refusals below are the state machine's refusals with a clearer message
in front of them.

How the withholding rule survives being split across three processes.

    view.md holds cases.reviewer_view() and nothing else, so the answer key has
    never been written to the reviewer's folder.

    The challenge list does not exist at sim start. It is generated inside
    sim commit, after commit_findings() has returned, and challenges.md is
    written from challenger.public_challenges(), which drops the truth block.

    state.json carries the session across processes and holds the public copy
    of the challenges only. The truth blocks live in truth.json, which is a
    facilitator file in the same sense the answer key is, and which the persona
    files forbid the reviewer from opening along with everything else in the
    folder that is not view.md or challenges.md.

The one honest simplification, stated here and in SIMULATION.md: a person states
their confidence on the screen that shows the memo and before they write
anything, and a model agent states it in the file it writes its findings in.
The two are the same question asked at the same point in the sequence, but the
model writes the answer after it has done the work rather than before, so a
simulated confidence gap is a weaker claim than a human one.
"""

import json
import os
import time

from . import cases, challenger, scoring, session as session_mod

STATE_FILE = "state.json"
VIEW_FILE = "view.md"
FINDINGS_FILE = "findings.json"
CHALLENGES_FILE = "challenges.md"
TEACHBACK_FILE = "teachback.json"
TRUTH_FILE = "truth.json"

PERSONAS = ("novice", "intermediate", "experienced")

SIM_SCHEMA = "second-pass/sim-state/v1"

# The whole shape of each file the reviewer writes, printed in full at the step
# that asks for it. Pilot one printed a shortened version that left out the
# soundness field and left out the eight word rule, and reviewers wrote files
# missing a field the scoring reads.
#
# Pilot two, finding 4. The examples below used to be real. They named
# case-01-june's accounts, its own movements, its direction reversal, its
# missing driver and the correct reject for one of its weak challenges, so a
# reviewer who read the prompt before working that case had three answers handed
# to them by the tool that was supposed to be withholding them. Every account,
# name and figure in the examples is now invented and appears in no case file.
# EXAMPLE_ACCOUNTS below is the whole invented set, and
# tests/test_sim.py::test_the_printed_schema_example_leaks_no_case walks the
# pack and proves none of it is there.
EXAMPLE_ACCOUNTS = (
    ("9200", "Groundskeeping contract", 61300),
    ("9250", "Waste removal", 38200),
    ("9280", "Site security", 14900),
)

FINDINGS_SCHEMA = """{
  "findings": [
    "Account 9200 groundskeeping contract rose $61,300 and sentence S3 says it fell",
    "Account 9250 waste removal moved $38,200 with no driver anywhere in the memo"
  ],
  "confidence": 65,
  "soundness": 3
}"""

FINDINGS_RULES = (
    "findings: a list of strings, one challenge per entry, each naming the account. Free text "
    "is fine and it is read by a published matching rule, not by a model.",
    "confidence: a number from 0 to 100. It is measured against one thing and one thing only: "
    "the share of the planted defects in this memo that you believe you have caught. It is not "
    "how confident you feel, and it is not how sound the memo is.",
    "soundness: a whole number from 1 to 5, 1 poor and 5 sound, for how sound the memo looked "
    "to you before you read it closely. Optional, and it feeds the memo soundness figure.",
)

TEACHBACK_SCHEMA = """{
  "responses": [
    {"id": "C1",
     "verdict": "accept",
     "reason": "Account 9200 groundskeeping contract rose $61,300 and sentence S3 has it falling, so the memo states the direction backwards."},
    {"id": "C2",
     "verdict": "reject",
     "reason": "Account 9280 site security moved $14,900, which fails the dollar leg of the threshold, so no driver is required and this challenge does not hold."}
  ],
  "findings": [
    "anything the challenge list did not raise that you still want to challenge"
  ],
  "confidence": 80
}"""

TEACHBACK_RULES = (
    "One entry per challenge. A challenge with no entry counts as unanswered and the defect "
    "behind it counts as missed.",
    "verdict: exactly \"accept\" or \"reject\". Nothing else is recorded.",
    "reason: your own words, and a reason under eight words scores zero. A verdict without a "
    "real reason is not review, it is a click, and it earns no credit for the defect.",
    "Refusing a weak challenge with a reason scores exactly as highly as accepting a real one "
    "with a reason. Some of the challenges in the list do not hold.",
    "findings: optional, for anything the list did not raise that you still want to challenge. "
    "A finding here that the answer key does not carry is counted on its own and listed in the "
    "session log for a facilitator, and it never reduces your catch rate.",
    "confidence: a number from 0 to 100, and it means the same thing it meant before: the share "
    "of the planted defects in this memo you believe you have now caught.",
)


class SimError(Exception):
    """A simulated session was asked to do something out of order, or without its input."""


def sim_runs_root():
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.abspath(os.path.join(os.path.dirname(here), "sim", "runs"))


def check_dir(directory, allow_any=False, must_exist=False):
    """Refuse a --dir that would write outside sim/runs, and explain the shell.

    Pilot one lost this argument to a shell. A reviewer on bash typed
    --dir sim\\runs\\R6-case-02-july, the backslashes were eaten as escapes, and
    the tool created a folder called simrunsR6-case-02-july at the repository
    root and reported that path back as though it were what had been asked for.
    Nothing was corrupted and everything was confusing.

    So the path is checked before anything is created. Forward slashes work in
    every shell on every platform, which is why the message says to use them.
    """
    if not directory:
        raise SimError("--dir is required and names the session folder for this reviewer and case.")
    resolved = os.path.abspath(directory)
    root = sim_runs_root()
    inside = resolved == root or resolved.startswith(root + os.sep)
    if inside or allow_any:
        if must_exist and not os.path.isdir(resolved):
            raise SimError(
                "No folder at %s. Run 'python -m second_pass sim start' for this reviewer and "
                "case first, and pass the same --dir." % resolved)
        return directory
    hint = ""
    # On Windows a backslash is a separator, so its presence proves nothing. The
    # signature of the pilot one accident is a single path segment that begins
    # with the folder names run together.
    mangled = os.path.basename(str(directory)).lower()
    if mangled.startswith("simruns") or mangled.startswith("simrun"):
        hint = (" That looks like a path whose separators were eaten by the shell. Backslashes "
                "are escape characters in bash, so sim\\runs\\R1-case-01-june arrives as "
                "simrunsR1-case-01-june. Use forward slashes: sim/runs/R1-case-01-june.")
    raise SimError(
        "--dir %s resolves to %s, which is outside %s. A simulated session writes six files, and "
        "writing them somewhere unexpected is how pilot one ended up with a folder called "
        "simrunsR6-case-02-july at the repository root.%s Point --dir inside sim/runs, or pass "
        "--allow-any-dir if you meant it. Note also that the working directory does not persist "
        "between shell invocations, so every command carries its own --dir."
        % (directory, resolved, root, hint))


# ------------------------------------------------------------------ state file


def _state_path(directory):
    return os.path.join(directory, STATE_FILE)


def _read_json(path, what):
    if not os.path.isfile(path):
        raise SimError("%s not found at %s. %s" % (os.path.basename(path), path, what))
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except ValueError as error:
        raise SimError("%s is not valid JSON: %s" % (os.path.basename(path), error))


def _write_json(path, payload):
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)


def _save(directory, review, extra):
    """Write state.json. The public challenges only; the truth goes elsewhere."""
    state = {
        "schema": SIM_SCHEMA,
        "session_id": review.session_id,
        "case_id": review.case["id"],
        "reviewer": review.reviewer,
        "persona": extra.get("persona"),
        "provider": review.provider,
        "cases_root": extra.get("cases_root"),
        "sessions_root": extra.get("sessions_root"),
        "state": review.state,
        "started_at": review.started_at,
        "epoch_start": extra.get("epoch_start"),
        "epoch_commit": extra.get("epoch_commit"),
        "data": review.data,
        "challenger": review.challenger_meta,
        "challenges": challenger.public_challenges(review.challenges) if review.challenges else None,
        "events": review.events,
    }
    _write_json(_state_path(directory), state)
    return state


def _restore(directory):
    """Rebuild the ReviewSession the earlier process left behind."""
    state = _read_json(_state_path(directory),
                       "Run 'python -m second_pass sim start' in this folder first.")
    if state.get("schema") != SIM_SCHEMA:
        raise SimError("%s is not a Second Pass simulated session state file." % STATE_FILE)
    case = cases.load_case(state["case_id"], state.get("cases_root"))
    review = session_mod.ReviewSession(
        case, state["reviewer"], provider=state.get("provider", "auto"),
        root=state.get("sessions_root"))
    review.session_id = state["session_id"]
    review.state = state["state"]
    review.started_at = state["started_at"]
    review.events = state["events"]
    review.data = state["data"]
    review.challenger_meta = state.get("challenger")
    review.challenges = _rehydrate_challenges(directory, state)
    return review, state


def _rehydrate_challenges(directory, state):
    """Public challenges plus their truth blocks, which scoring needs back."""
    public = state.get("challenges")
    if not public:
        return None
    truth = _read_json(os.path.join(directory, TRUTH_FILE),
                       "The challenge list was released but its truth file is missing, so this "
                       "session can no longer be scored.")
    rebuilt = []
    for challenge in public:
        record = dict(challenge)
        record["truth"] = truth.get(challenge["id"], {"kind": "model", "ref": None, "type": None})
        rebuilt.append(record)
    return rebuilt


# ---------------------------------------------------------------- the two files


def render_view(case):
    """view.md: exactly what the web page shows at the Read step.

    Header, profile, the materiality rule, the movement table with prior,
    current, variance and percent, the threshold marker, and the draft
    commentary. The answer key, the distractors and the defect count are not
    here, because reviewer_view() does not carry them and nothing else in this
    function reads the case directly.
    """
    view = cases.reviewer_view(case)
    out = []
    out.append("# %s, %s against %s" % (
        view["company"]["name"], view["period"]["current"], view["period"]["prior"]))
    out.append("")
    out.append(view["company"]["profile"])
    out.append("")
    out.append("## The commentary threshold")
    out.append("")
    out.append(view["materiality_rule"])
    basis = view["materiality"].get("basis", "")
    margin = view.get("margin_definition") or ""
    extra = " ".join(part for part in (basis, margin) if part)
    if extra:
        out.append("")
        out.append(extra)
    out.append("")
    out.append("| Line | Account | Prior | Current | Variance | Percent |")
    out.append("|---|---|---|---|---|---|")
    for row in view["accounts"]:
        name = row["name"] + (" *" if row["material"] else "")
        out.append("| %s | %s | %s | %s | %s | %s |" % (
            row["line"], name,
            cases.format_amount(row["prior"]), cases.format_amount(row["current"]),
            cases.format_amount(row["variance"]), cases.format_percent(row["percent"])))
    out.append("")
    out.append("Lines marked * pass both legs of the threshold. %s" % view["materiality_rule"])
    if view.get("subtotals"):
        out.append("")
        out.append("Subtotals, computed from the balances above, so a ratio test does not require "
                   "adding the lines up by hand.")
        out.append("")
        out.append("| Subtotal | Lines | Prior | Current | Variance | Percent |")
        out.append("|---|---|---|---|---|---|")
        for row in view["subtotals"]:
            out.append("| %s | %s | %s | %s | %s | %s |" % (
                row["label"], " + ".join(row["lines"]),
                cases.format_amount(row["prior"]), cases.format_amount(row["current"]),
                cases.format_amount(row["variance"]), cases.format_percent(row["percent"])))
        for row in view["subtotals"]:
            if row.get("note"):
                out.append("")
                out.append("%s: %s" % (row["label"], row["note"]))
    out.append("")
    out.append("## Draft commentary from management")
    out.append("")
    for sentence in view["commentary"]["sentences"]:
        out.append("%s. %s" % (sentence["id"], sentence["text"]))
        out.append("")
    return "\n".join(out).rstrip() + "\n"


def render_challenges(public, provider_used, min_reason_words):
    """challenges.md: exactly what the web page shows at the Challenges step.

    Id, the account line, the amount cited, and the challenge text. The weak
    challenges are in this list and nothing marks them, which is the point.
    """
    out = []
    out.append("# The challenge list")
    out.append("")
    out.append("%d challenges, produced by the %s layer." % (len(public), provider_used))
    out.append("")
    out.append("Not all of these are worth accepting. The tool is not entitled to your "
               "agreement. Accept the ones that hold and reject the ones that do not, and "
               "give a reason either way in your own words. A reason under %d words does not "
               "count as a teach-back, and a verdict without one counts as unanswered."
               % min_reason_words)
    out.append("")
    out.append("Each challenge carries a one-word tag saying what kind of test to run first: "
               "%s. The tag says nothing about whether the challenge holds." % ", ".join(
                   cases.CHALLENGE_TAGS))
    out.append("")
    out.append("The amount in a citation is the movement of the account named, current less "
               "prior. Check it against the table before you answer, on every challenge.")
    out.append("")
    for challenge in public:
        out.append("## %s" % challenge["id"])
        out.append("")
        out.append("%s" % challenge["citation"])
        out.append("")
        out.append(challenge["question"])
        out.append("")
        if challenge.get("evidence"):
            out.append("What would count as evidence: %s" % challenge["evidence"])
            out.append("")
    return "\n".join(out).rstrip() + "\n"


# ------------------------------------------------------------------- the steps


def start(case_id, reviewer, directory, cases_root=None, sessions_root=None,
          provider="auto", persona=None):
    """Create the session, write view.md and state.json. No challenge list exists yet."""
    if persona and persona not in PERSONAS:
        raise SimError("Persona must be one of: %s." % ", ".join(PERSONAS))
    if os.path.isfile(_state_path(directory)):
        raise SimError(
            "%s already holds a simulated session. A session directory is used once, so that a "
            "reviewer cannot restart after seeing the challenge list. Point --dir somewhere new."
            % directory)
    case = cases.load_case(case_id, cases_root)
    review = session_mod.ReviewSession(case, reviewer, provider=provider, root=sessions_root)
    if not os.path.isdir(directory):
        os.makedirs(directory)
    with open(os.path.join(directory, VIEW_FILE), "w", encoding="utf-8") as handle:
        handle.write(render_view(case))
    review._log("simulated_session_opened",
                "a simulated reviewer opened the case through the sim driver",
                {"persona": persona, "dir": os.path.abspath(directory)})
    state = _save(directory, review, {
        "persona": persona,
        "cases_root": cases_root,
        "sessions_root": sessions_root,
        "epoch_start": time.time(),
        "epoch_commit": None,
    })
    return review, state


def commit(directory, min_reason_words=scoring.MIN_REASON_WORDS):
    """Seal findings.json, release the challenge list, write challenges.md."""
    review, state = _restore(directory)
    if review.state != "briefing":
        raise SimError(
            "This session has already committed. A commitment is sealed once and cannot be "
            "reopened, so a reviewer cannot commit, read the challenge list, and then improve "
            "their own findings. Current state: '%s'." % review.state)
    payload = _read_json(
        os.path.join(directory, FINDINGS_FILE),
        "Write your own findings first. The challenge list is withheld until they are sealed.")
    findings = payload.get("findings")
    if not isinstance(findings, list):
        raise SimError("%s needs a 'findings' list, one challenge per entry." % FINDINGS_FILE)
    if "confidence" not in payload:
        raise SimError("%s needs a 'confidence' from 0 to 100." % FINDINGS_FILE)
    confidence = payload["confidence"]
    soundness = payload.get("soundness")

    review.open_phase_1(confidence, soundness)
    if state.get("epoch_start"):
        # Phase one is the wall clock between sim start and sim commit, not the
        # microsecond this process has been alive.
        review._clock_1 = state["epoch_start"]
    review.commit_findings([str(text) for text in findings])
    review.set_confidence_aided(confidence)
    public = review.reveal_challenges()

    truth = dict((challenge["id"], challenge.get("truth") or {}) for challenge in review.challenges)
    _write_json(os.path.join(directory, TRUTH_FILE), truth)
    with open(os.path.join(directory, CHALLENGES_FILE), "w", encoding="utf-8") as handle:
        handle.write(render_challenges(
            public, review.challenger_meta["provider_used"], min_reason_words))
    _save(directory, review, {
        "persona": state.get("persona"),
        "cases_root": state.get("cases_root"),
        "sessions_root": state.get("sessions_root"),
        "epoch_start": state.get("epoch_start"),
        "epoch_commit": time.time(),
    })
    return review, public


def finish(directory, min_reason_words=scoring.MIN_REASON_WORDS):
    """Record teachback.json, score, and write the session log."""
    review, state = _restore(directory)
    if review.state != "challenges_revealed":
        if review.state == "finished":
            raise SimError("This session is already scored and its log is written.")
        raise SimError(
            "There is nothing to score yet. Commit your findings and work the challenge list "
            "first. Current state: '%s'." % review.state)
    review.min_reason_words = min_reason_words
    payload = _read_json(
        os.path.join(directory, TEACHBACK_FILE),
        "Answer the challenge list first, one verdict and one reason per challenge.")
    responses = payload.get("responses")
    if not isinstance(responses, list):
        raise SimError("%s needs a 'responses' list of {id, verdict, reason}." % TEACHBACK_FILE)
    for entry in responses:
        if not isinstance(entry, dict) or "id" not in entry:
            raise SimError("every entry in %s needs an 'id' naming a challenge." % TEACHBACK_FILE)
        review.record_teachback(entry["id"], entry.get("verdict"), entry.get("reason"))
    if payload.get("findings"):
        review.add_aided_findings([str(text) for text in payload["findings"]])

    post_confidence = payload.get("confidence")
    if post_confidence is not None:
        post_confidence = session_mod._as_percent(post_confidence, "confidence")
        review.data["confidence_post_teachback"] = post_confidence
        review._log("confidence_post_teachback_recorded",
                    "simulated reviewer restated confidence after working the challenge list",
                    {"confidence": post_confidence})

    if state.get("epoch_commit"):
        review._clock_2 = state["epoch_commit"]
    result = review.finish(write_log=False)

    log = review.to_log()
    log["simulated"] = True
    log["persona"] = state.get("persona")
    log["confidence"]["post_teachback"] = review.data.get("confidence_post_teachback")
    log["sim_dir"] = os.path.abspath(directory)
    path = _write_session_log(log, state.get("sessions_root"))
    _save(directory, review, {
        "persona": state.get("persona"),
        "cases_root": state.get("cases_root"),
        "sessions_root": state.get("sessions_root"),
        "epoch_start": state.get("epoch_start"),
        "epoch_commit": state.get("epoch_commit"),
    })
    return review, result, path, log


def _write_session_log(log, sessions_root):
    directory = session_mod.sessions_dir(sessions_root)
    if not os.path.isdir(directory):
        os.makedirs(directory)
    path = os.path.join(directory, log["session_id"] + ".json")
    _write_json(path, log)
    return path


def score_block(result, case, debrief=False):
    """The metrics. The answer key stays out unless the facilitator asks for it.

    A simulated reviewer runs all three cases, so printing the key at the end of
    case one would hand the same agent the defect taxonomy before case two.
    """
    text = scoring.format_scorecard(result, case)
    marker = "\nStill missed at the end of the session:"
    if not debrief and marker in text:
        text = text.split(marker)[0].rstrip()
        text += ("\n\nThe answer key is withheld from this output. A facilitator can see it with "
                 "sim finish --debrief, or with show --case %s --key." % case["id"])
    return text
