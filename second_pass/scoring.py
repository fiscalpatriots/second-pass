"""Scoring one reviewer's session.

The numbers, and what each one is for.

    catch_rate_unaided       what the reviewer found on their own, supported
    catch_rate_aided         their FINAL position after the challenge list
    lift                     the difference, in points, and it can be negative
    precision_unaided        share of their own findings that hit a planted
                             defect, measured AGAINST THE ANSWER KEY
    findings_outside_key     findings that matched no planted defect, counted
                             on their own and listed verbatim for a facilitator
    findings_for_adjudication findings that named a planted account without
                             asserting anything wrong with it, or that accepted
                             the commentary outright. Never a catch, never
                             discarded, always handed to a person
    confidence_gap_unaided   stated expectation minus what they actually caught
    confidence_gap_aided     the same measurement after the tool ran
    seconds_phase_1 / _2     time, recorded and reported, never led with
    teachback_completion     share of challenges answered at all, measured by
                             verdict plus a reason of at least the minimum
                             length. A COMPLETION metric and nothing more
    disposition_accuracy     share of challenges whose VERDICT was right
    reasoning_score          the human rubric, three dimensions of 0 to 2, and
                             None until a person scores it
    distractors_rejected     weak challenges the reviewer refused to accept

Three of those names changed on 13 September 2026, after an external audit, and
the old names are gone rather than aliased, because a stale name on a repaired
number is how the wrong number gets quoted.

**Completion is not reasoning.** `teachback_completeness` used to be read as a
quality measure and it never was one: it counts words. The audit submitted the
reason "The blue umbrella is waiting outside beside the garden fence." against a
real defect and the tool returned full marks, because the words were numerous
and the verdict happened to be right. So the word count is now called completion
and says so on every surface that prints it, verdict correctness is called
disposition accuracy, and reasoning quality is a separate structure a person
fills in. Nothing in this module infers a rubric score from a length, a verdict,
or any other machine-readable property of the text.

**The final outcome is the final position.** The aided catch used to be the
union of what the reviewer found first with what the challenge list added, so a
reviewer who raised a real defect and then withdrew it under challenge still
counted as catching it, and the arithmetic could never show the assistance doing
harm. A defect the reviewer raised unaided and then rejected when the challenge
list put it back to them is withdrawn from the final count. The original and the
changed decisions are both preserved: `caught_unaided_ids` is what they had
first, `withdrawn_ids` is what they gave up, `added_via_challenge_ids` is what
the list added, and `caught_final_ids` is where they finished.

**Matching is not correctness.** A finding that names an account and its
movement and then accepts the commentary is not a detected defect. See
matching.py; the statuses it returns are carried through into the trail and into
the adjudication queue here.

Precision is measured against the answer key and is labelled that way wherever
it is printed. Pilot one taught the reason. Three reviewers wrote findings that
were real accounting problems and were not in the key: a rebate presentation
that flipped the margin conclusion, a capitalisation question against a flat
depreciation charge, and shrink sitting outside the margin definition. Each of
those scored as "matched nothing" and pulled the reviewer's precision down, so
the arithmetic rewarded writing fewer and narrower findings. A tool that
punishes a reviewer for seeing something its author did not is training the
wrong reflex. Those findings are now counted on their own, listed verbatim in
the session log for a facilitator to adjudicate, and they never touch a catch
rate.

The confidence gap is the one that carries the entry. A reviewer states, before
they start, what share of the problems they expect to find. The tool then
measures what share they found. The distance between those two numbers is the
thing nobody measures and everybody assumes. Every number this module has
produced so far came from a simulated reviewer. No human pilot has run, so
nothing here has been measured on a person, and no surface may say otherwise.

Accepting a machine challenge without a reason is not a catch. A reviewer who
waves the list through scores zero on teach-back completion for that item and
does not get credit for the defect, which is the whole point of the exercise.
Answering at length is not a catch either: the credit a challenge carries is
disposition credit, it is labelled that way, and a facilitator who wants to know
whether the reviewer understood the defect reads the rubric a person scored.
"""

from . import matching

MIN_REASON_WORDS = 8

# The reasoning rubric. Three dimensions, each scored 0, 1 or 2, by a person.
# Nothing in this package writes a value into any of them. A blank rubric is the
# honest state of an unscored session and it stays blank until a scorer signs.
RUBRIC_DIMENSIONS = (
    ("records_establish",
     "What the records establish: does the response state what the ledger and the schedule "
     "actually show, correctly and without adding to it?"),
    ("evidence_supports",
     "What the evidence supports or leaves unresolved: does the response separate what the "
     "supplied evidence carries from what is still open?"),
    ("next_action",
     "The next proportionate action: is the step the response asks for the right size for the "
     "money and the risk in front of it?"),
)
RUBRIC_SCALE = (0, 1, 2)
RUBRIC_MAX = len(RUBRIC_DIMENSIONS) * max(RUBRIC_SCALE)

# At or above this, the unaided phase has almost nothing left to find, and a
# lift near zero is a ceiling rather than a phase that did no work. Every
# surface that prints a lift prints the ceiling note beside it.
CEILING_PERCENT = 90.0

# One line each, printed beside the numbers rather than kept in a manual.
# Pilot one had reviewers reading "Lift 0.0 points" as the aided phase being
# worthless, and asking what teach-back accuracy was measured over.
DEFINITIONS = {
    "lift": "Lift: aided catch rate minus unaided catch rate, in points. It is what the "
            "challenge list added to what the reviewer already had.",
    "confidence_gap": "Confidence gap: the share of the planted defects the reviewer said they "
                      "would find, minus the share they actually found. Positive means they "
                      "believed they caught more than they caught.",
    "teachback_completion": "Teach-back completion: the share of challenges answered with a "
                            "verdict and a reason of at least the minimum length. It counts "
                            "words, so it measures whether the item was completed and says "
                            "nothing about the quality of the reasoning.",
    "disposition_accuracy": "Disposition accuracy: of the challenges judged, the share whose "
                            "VERDICT was right, accept on a real defect and reject on a weak "
                            "one. It is a decision measure and it does not read the reason.",
    "reasoning_score": "Reasoning score: three dimensions scored 0 to 2 by a named person, out "
                       "of 6. What the records establish, what the evidence supports or leaves "
                       "unresolved, and the next proportionate action. It is blank until a "
                       "person scores it, and no part of this tool fills it in.",
    "precision": "Precision, against the answer key: findings that matched a planted defect over "
                 "all findings written. Findings outside the key are counted separately and never "
                 "reduce a catch rate.",
}


def _rate(numerator, denominator):
    if not denominator:
        return None
    return round(100.0 * numerator / denominator, 1)


def _word_count(text):
    return len([word for word in (text or "").split() if word.strip()])


class ScoringError(Exception):
    """A rubric arrived in a shape the scorer cannot stand behind."""


def blank_rubric():
    """The honest state of a session nobody has scored yet."""
    return {
        "scored": False,
        "scorer_id": None,
        "scored_at": None,
        "dimensions": dict((name, None) for name, _text in RUBRIC_DIMENSIONS),
        "total": None,
        "max": RUBRIC_MAX,
        "adjudication": None,
        "adjudication_note": None,
        "basis": ("three dimensions of 0 to 2, entered by a named person; never inferred from "
                  "word count, verdict, or any other property of the text"),
    }


def read_rubric(entry):
    """Turn one human-entered rubric into the stored block, or refuse it.

    `entry` is whatever a facilitator supplied for one challenge. Every score
    has to be 0, 1 or 2, and a rubric carrying any score has to carry the
    identifier of the person who gave it. An unscored rubric is not an error.
    """
    rubric = blank_rubric()
    if not entry:
        return rubric
    given = {}
    for name, _text in RUBRIC_DIMENSIONS:
        value = entry.get(name)
        if value is None:
            continue
        if isinstance(value, bool) or value not in RUBRIC_SCALE:
            raise ScoringError(
                "rubric dimension '%s' must be one of %s, got %r" % (name, list(RUBRIC_SCALE), value))
        given[name] = int(value)
    rubric["dimensions"].update(given)
    rubric["adjudication"] = entry.get("adjudication")
    rubric["adjudication_note"] = entry.get("adjudication_note")
    rubric["scorer_id"] = entry.get("scorer_id")
    rubric["scored_at"] = entry.get("scored_at")
    if given and not rubric["scorer_id"]:
        raise ScoringError("a rubric score needs a scorer_id; an unsigned score is not evidence")
    if len(given) == len(RUBRIC_DIMENSIONS):
        rubric["scored"] = True
        rubric["total"] = sum(given.values())
    return rubric


def score_session(session, case, challenges, min_reason_words=MIN_REASON_WORDS):
    """Score one completed session. Pure function, no I/O, no clock.

    session is the dict the state machine built. challenges are the internal
    challenge records, with their truth blocks, as the challenger produced them.
    `session["reasoning_rubrics"]`, where present, maps a challenge id to a
    rubric a person entered. Nothing here creates a score for one.
    """
    defects_present = len(case["answer_key"])

    unaided = matching.score_findings(session.get("findings_unaided", []), case)
    caught_unaided = list(unaided["caught"])
    false_unaided = len(unaided["false_challenges"])
    outside_key = _outside_key(unaided["false_challenges"])
    adjudication_queue = _adjudication_queue(unaided["for_adjudication"])

    challenge_by_id = dict((challenge["id"], challenge) for challenge in challenges)
    teachbacks = session.get("teachbacks", {})
    rubric_input = session.get("reasoning_rubrics") or {}

    answered = 0
    complete = 0
    judged = 0
    disposition_correct = 0
    distractors_shown = 0
    distractors_rejected = 0
    caught_via_challenge = []
    withdrawn = []
    credit_pending_rubric = 0
    rubrics_scored = 0
    rubric_totals = []
    teachback_detail = []

    for challenge_id, challenge in challenge_by_id.items():
        entry = teachbacks.get(challenge_id) or {}
        verdict = (entry.get("verdict") or "").strip().lower()
        reason = entry.get("reason") or ""
        words = _word_count(reason)
        is_complete = verdict in ("accept", "reject") and words >= min_reason_words
        if verdict:
            answered += 1
        if is_complete:
            complete += 1

        rubric = read_rubric(rubric_input.get(challenge_id))
        if rubric["scored"]:
            rubrics_scored += 1
            rubric_totals.append(rubric["total"])

        truth = challenge.get("truth", {})
        kind = truth.get("kind")
        record = {
            "challenge_id": challenge_id,
            "line": challenge["line"],
            "truth_kind": kind,
            "truth_ref": truth.get("ref"),
            "verdict": verdict or None,
            "reason": reason,
            "reason_words": words,
            "complete": is_complete,
            "completion_basis": "verdict plus a reason of at least %d words" % min_reason_words,
            "disposition_correct": None,
            "reasoning_rubric": rubric,
        }
        if kind == "defect":
            judged += 1
            ref = truth.get("ref")
            if verdict == "accept" and is_complete:
                disposition_correct += 1
                record["disposition_correct"] = True
                if ref not in caught_unaided and ref not in caught_via_challenge:
                    caught_via_challenge.append(ref)
                    record["credit"] = "defect credited from the disposition only"
                    record["credit_basis"] = (
                        "the verdict was right and the item was completed. Whether the reviewer "
                        "understood the defect is the reasoning rubric's question, and it is "
                        "unscored until a person scores it.")
                    if not rubric["scored"]:
                        credit_pending_rubric += 1
            else:
                record["disposition_correct"] = False
                if verdict == "reject" and ref in caught_unaided and ref not in withdrawn:
                    withdrawn.append(ref)
                    record["position_change"] = "withdrawn"
                    record["position_change_note"] = (
                        "the reviewer raised this defect unaided and then rejected the challenge "
                        "that put it back to them, so their final position is that it is not a "
                        "defect. The original finding is preserved; the final count does not "
                        "carry it.")
        elif kind == "distractor":
            judged += 1
            distractors_shown += 1
            if verdict == "reject" and is_complete:
                disposition_correct += 1
                distractors_rejected += 1
                record["disposition_correct"] = True
            else:
                record["disposition_correct"] = False
        teachback_detail.append(record)

    extra = matching.score_findings(session.get("findings_aided", []), case)
    caught_extra = [d for d in extra["caught"]
                    if d not in caught_unaided and d not in caught_via_challenge]

    held = [defect_id for defect_id in caught_unaided if defect_id not in withdrawn]
    caught_final = held + caught_via_challenge + caught_extra

    rate_unaided = _rate(len(caught_unaided), defects_present)
    rate_final = _rate(len(caught_final), defects_present)

    confidence_unaided = session.get("confidence_unaided")
    confidence_aided = session.get("confidence_aided")

    scores = {
        "case_id": case["id"],
        "reviewer": session.get("reviewer"),
        "defects_present": defects_present,
        "caught_unaided": len(caught_unaided),
        "caught_aided": len(caught_final),
        "caught_final": len(caught_final),
        "caught_unaided_ids": caught_unaided,
        "caught_aided_ids": caught_final,
        "caught_final_ids": caught_final,
        "withdrawn_ids": withdrawn,
        "added_via_challenge_ids": caught_via_challenge,
        "added_in_aided_findings_ids": caught_extra,
        "decisions_changed": len(withdrawn) + len(caught_via_challenge) + len(caught_extra),
        "final_outcome_basis": ("final positions: an unaided finding the reviewer later rejected "
                                "under challenge is withdrawn from the final count, and the "
                                "original decision is preserved in caught_unaided_ids"),
        "missed_ids": [d["id"] for d in case["answer_key"] if d["id"] not in caught_final],
        "catch_rate_unaided": rate_unaided,
        "catch_rate_aided": rate_final,
        "catch_rate_final": rate_final,
        "lift": None if rate_unaided is None or rate_final is None else round(rate_final - rate_unaided, 1),
        "false_challenges_unaided": false_unaided,
        "findings_outside_key": false_unaided,
        "findings_outside_key_matched_weak": len(
            [row for row in outside_key if row["matched_planted_weak"]]),
        "findings_outside_key_unadjudicated": len(
            [row for row in outside_key if not row["matched_planted_weak"]]),
        "findings_for_adjudication": len(adjudication_queue),
        "findings_accepting_the_position": len(
            [row for row in adjudication_queue if row["status"] == matching.STATUS_ACCEPTS]),
        "findings_unsupported": len(
            [row for row in adjudication_queue if row["status"] == matching.STATUS_UNSUPPORTED]),
        "precision_unaided": _rate(len(caught_unaided), len(caught_unaided) + false_unaided),
        "precision_basis": "against the answer key",
        "catch_ceiling_unaided": (rate_unaided is not None and rate_unaided >= CEILING_PERCENT),
        "confidence_unaided": confidence_unaided,
        "confidence_aided": confidence_aided,
        "confidence_gap_unaided": None if confidence_unaided is None or rate_unaided is None
        else round(confidence_unaided - rate_unaided, 1),
        "confidence_gap_aided": None if confidence_aided is None or rate_final is None
        else round(confidence_aided - rate_final, 1),
        "soundness_rating": session.get("soundness_rating"),
        "seconds_phase_1": session.get("seconds_phase_1"),
        "seconds_phase_2": session.get("seconds_phase_2"),
        "challenges_shown": len(challenge_by_id),
        "teachbacks_answered": answered,
        "teachback_completion": _rate(complete, len(challenge_by_id)),
        "teachback_completion_basis": ("word count. It measures completion of the item and says "
                                       "nothing about the quality of the reasoning"),
        "disposition_accuracy": _rate(disposition_correct, judged),
        "disposition_accuracy_basis": "the verdict only; the reason is not read",
        "reasoning_rubrics_scored": rubrics_scored,
        "reasoning_rubrics_expected": len(challenge_by_id),
        "reasoning_score": None if not rubric_totals else sum(rubric_totals),
        "reasoning_score_max": None if not rubric_totals else len(rubric_totals) * RUBRIC_MAX,
        "reasoning_score_mean": None if not rubric_totals
        else round(sum(rubric_totals) / float(len(rubric_totals)), 2),
        "reasoning_scored_by": sorted(set(
            row["reasoning_rubric"]["scorer_id"] for row in teachback_detail
            if row["reasoning_rubric"]["scorer_id"])),
        "defect_credit_pending_rubric": credit_pending_rubric,
        "distractors_shown": distractors_shown,
        "distractors_rejected": distractors_rejected,
        "min_reason_words": min_reason_words,
    }
    return {
        "scores": scores,
        "teachback_detail": teachback_detail,
        "unaided_trail": unaided["trail"],
        "aided_trail": extra["trail"],
        "findings_outside_key": outside_key,
        "findings_for_adjudication": adjudication_queue,
    }


def _adjudication_queue(records):
    """Findings that named a planted account without making a finding of it.

    Two shapes land here. One names the account and its movement and then
    accepts the commentary. The other names the account and a figure and asserts
    nothing. Neither is a detected defect and neither is a wrong finding, so
    both are handed to a person with the reviewer's words intact.
    """
    rows = []
    for record in records:
        evidence = record.get("evidence", {})
        rows.append({
            "text": record.get("text", ""),
            "matched_defect": record.get("matched_defect"),
            "status": record.get("status"),
            "why": evidence.get("why"),
            "acceptance_matched": evidence.get("acceptance_matched"),
            "adjudication": None,
            "adjudicated_by": None,
            "verdict": "not counted as a detected defect; for facilitator adjudication",
        })
    return rows


def _outside_key(false_challenges):
    """The reviewer's own words, kept whole, for a facilitator to adjudicate.

    A finding that matched nothing is not automatically a wrong finding. It is
    a finding the answer key does not carry, which is a different statement, and
    the only person who can tell the two apart is a person. So the text goes
    into the log verbatim rather than into a bucket labelled false.
    """
    rows = []
    for record in false_challenges:
        rows.append({
            "text": record.get("text", ""),
            "matched_planted_weak": record.get("matched_distractor"),
            "verdict": "matched a planted weak lead" if record.get("matched_distractor")
            else "outside the answer key, for facilitator adjudication",
        })
    return rows


def format_scorecard(result, case):
    """The reviewer's debrief screen, and what the command line prints."""
    scores = result["scores"]
    lines = []
    lines.append("Case %s, reviewer %s" % (scores["case_id"], scores["reviewer"]))
    lines.append("Defects planted: %d" % scores["defects_present"])
    lines.append("")
    lines.append("  Catch rate, unaided      %s   (%d of %d)" % (
        _pct(scores["catch_rate_unaided"]), scores["caught_unaided"], scores["defects_present"]))
    lines.append("  Catch rate, final        %s   (%d of %d)" % (
        _pct(scores["catch_rate_final"]), scores["caught_final"], scores["defects_present"]))
    lines.append("  Lift                     %s points" % _num(scores["lift"]))
    if scores.get("withdrawn_ids"):
        lines.append("      Withdrawn under challenge: %s. The reviewer raised %s unaided and "
                     "then rejected the challenge that put %s back, so the final count does not "
                     "carry %s. The original finding is preserved in the log."
                     % (", ".join(scores["withdrawn_ids"]),
                        "them" if len(scores["withdrawn_ids"]) > 1 else "it",
                        "them" if len(scores["withdrawn_ids"]) > 1 else "it",
                        "them" if len(scores["withdrawn_ids"]) > 1 else "it"))
    if scores.get("catch_ceiling_unaided"):
        lines.append("      Ceiling: unaided catch was %s, so at most %s points of lift were "
                     "available. A small lift here is a ceiling, not a phase that did nothing."
                     % (_pct(scores["catch_rate_unaided"]).strip(),
                        _num(round(100.0 - scores["catch_rate_unaided"], 1))))
    lines.append("  Precision, against key   %s   (%d finding(s) outside the answer key)" % (
        _pct(scores["precision_unaided"]), scores.get("findings_outside_key", 0)))
    if scores.get("findings_outside_key_unadjudicated"):
        lines.append("      %d of those matched no planted weak lead either, and are listed in "
                     "the session log verbatim for a facilitator to adjudicate."
                     % scores["findings_outside_key_unadjudicated"])
    lines.append("  Confidence stated first  %s" % _pct(scores["confidence_unaided"]))
    lines.append("  Confidence gap, unaided  %s points" % _num(scores["confidence_gap_unaided"]))
    lines.append("  Confidence gap, aided    %s points" % _num(scores["confidence_gap_aided"]))
    lines.append("  Memo soundness, 1 to 5   %s" % _num(scores["soundness_rating"]))
    lines.append("  Teach-back completion    %s   (word count, not reasoning quality)"
                 % _pct(scores["teachback_completion"]))
    lines.append("  Disposition accuracy     %s   (the verdict only)"
                 % _pct(scores["disposition_accuracy"]))
    if scores["reasoning_score"] is None:
        lines.append("  Reasoning score          not scored   (%d of %d rubrics entered; a person "
                     "scores three dimensions of 0 to 2 and nothing here fills them in)"
                     % (scores["reasoning_rubrics_scored"], scores["reasoning_rubrics_expected"]))
    else:
        lines.append("  Reasoning score          %s of %s   (%d of %d rubrics entered by %s)" % (
            _num(scores["reasoning_score"]), _num(scores["reasoning_score_max"]),
            scores["reasoning_rubrics_scored"], scores["reasoning_rubrics_expected"],
            ", ".join(scores["reasoning_scored_by"]) or "an unnamed scorer"))
    if scores.get("defect_credit_pending_rubric"):
        lines.append("      %d defect(s) were credited from the disposition alone and are waiting "
                     "on a reasoning rubric." % scores["defect_credit_pending_rubric"])
    if scores.get("findings_for_adjudication"):
        lines.append("  For adjudication         %d finding(s) named a planted account without "
                     "making a finding of it" % scores["findings_for_adjudication"])
    lines.append("  Weak challenges refused  %d of %d" % (
        scores["distractors_rejected"], scores["distractors_shown"]))
    lines.append("  Time, phase 1 / phase 2  %s / %s seconds" % (
        _num(scores["seconds_phase_1"]), _num(scores["seconds_phase_2"])))
    lines.append("")
    lines.append("What the numbers are")
    for key in ("lift", "confidence_gap", "teachback_completion", "disposition_accuracy",
                "reasoning_score", "precision"):
        lines.append("  " + DEFINITIONS[key])
    if scores["missed_ids"]:
        lines.append("")
        lines.append("Still missed at the end of the session:")
        by_id = dict((defect["id"], defect) for defect in case["answer_key"])
        for defect_id in scores["missed_ids"]:
            defect = by_id[defect_id]
            lines.append("  %s  %s, account %s" % (defect_id, defect["type"], defect["line"]))
            lines.append("      %s" % defect["correct"])
    return "\n".join(lines)


def _pct(value):
    return "n/a" if value is None else "{:>5.1f}%".format(value)


def _num(value):
    return "n/a" if value is None else str(value)
