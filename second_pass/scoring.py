"""Scoring one reviewer's session.

The numbers, and what each one is for.

    catch_rate_unaided       what the reviewer found on their own
    catch_rate_aided         what they held after the challenge list
    lift                     the difference, in points
    precision_unaided        share of their own findings that hit a planted
                             defect, measured AGAINST THE ANSWER KEY
    findings_outside_key     findings that matched no planted defect, counted
                             on their own and listed verbatim for a facilitator
    confidence_gap_unaided   stated expectation minus what they actually caught
    confidence_gap_aided     the same measurement after the tool ran
    seconds_phase_1 / _2     time, recorded and reported, never led with
    teachback_completeness   share of challenges answered with a real reason
    teachback_accuracy       share of challenges judged correctly
    distractors_rejected     weak challenges the reviewer refused to accept

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
thing nobody measures and everybody assumes, and it is measured here on real
people rather than asserted.

Accepting a machine challenge without a reason is not a catch. A reviewer who
waves the list through scores zero on teach-back completeness for that item and
does not get credit for the defect, which is the whole point of the exercise.
"""

from . import matching

MIN_REASON_WORDS = 8

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
    "teachback_accuracy": "Teach-back accuracy: of the challenges judged, the share judged "
                          "correctly. Accepting a real challenge with a reason of at least eight "
                          "words counts, and so does refusing a weak one with a reason.",
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


def score_session(session, case, challenges, min_reason_words=MIN_REASON_WORDS):
    """Score one completed session. Pure function, no I/O, no clock.

    session is the dict the state machine built. challenges are the internal
    challenge records, with their truth blocks, as the challenger produced them.
    """
    defects_present = len(case["answer_key"])

    unaided = matching.score_findings(session.get("findings_unaided", []), case)
    caught_unaided = list(unaided["caught"])
    false_unaided = len(unaided["false_challenges"])
    outside_key = _outside_key(unaided["false_challenges"])

    challenge_by_id = dict((challenge["id"], challenge) for challenge in challenges)
    teachbacks = session.get("teachbacks", {})

    answered = 0
    complete = 0
    judged = 0
    correct = 0
    distractors_shown = 0
    distractors_rejected = 0
    caught_via_challenge = []
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

        truth = challenge.get("truth", {})
        kind = truth.get("kind")
        record = {
            "challenge_id": challenge_id,
            "line": challenge["line"],
            "truth_kind": kind,
            "truth_ref": truth.get("ref"),
            "verdict": verdict or None,
            "reason_words": words,
            "complete": is_complete,
            "correct": None,
        }
        if kind == "defect":
            judged += 1
            if verdict == "accept" and is_complete:
                correct += 1
                record["correct"] = True
                if truth.get("ref") not in caught_unaided and truth.get("ref") not in caught_via_challenge:
                    caught_via_challenge.append(truth.get("ref"))
            else:
                record["correct"] = False
        elif kind == "distractor":
            judged += 1
            distractors_shown += 1
            if verdict == "reject" and is_complete:
                correct += 1
                distractors_rejected += 1
                record["correct"] = True
            else:
                record["correct"] = False
        teachback_detail.append(record)

    extra = matching.score_findings(session.get("findings_aided", []), case)
    caught_extra = [d for d in extra["caught"] if d not in caught_unaided and d not in caught_via_challenge]

    caught_aided = list(caught_unaided) + caught_via_challenge + caught_extra

    rate_unaided = _rate(len(caught_unaided), defects_present)
    rate_aided = _rate(len(caught_aided), defects_present)

    confidence_unaided = session.get("confidence_unaided")
    confidence_aided = session.get("confidence_aided")

    scores = {
        "case_id": case["id"],
        "reviewer": session.get("reviewer"),
        "defects_present": defects_present,
        "caught_unaided": len(caught_unaided),
        "caught_aided": len(caught_aided),
        "caught_unaided_ids": caught_unaided,
        "caught_aided_ids": caught_aided,
        "missed_ids": [d["id"] for d in case["answer_key"] if d["id"] not in caught_aided],
        "catch_rate_unaided": rate_unaided,
        "catch_rate_aided": rate_aided,
        "lift": None if rate_unaided is None or rate_aided is None else round(rate_aided - rate_unaided, 1),
        "false_challenges_unaided": false_unaided,
        "findings_outside_key": false_unaided,
        "findings_outside_key_matched_weak": len(
            [row for row in outside_key if row["matched_planted_weak"]]),
        "findings_outside_key_unadjudicated": len(
            [row for row in outside_key if not row["matched_planted_weak"]]),
        "precision_unaided": _rate(len(caught_unaided), len(caught_unaided) + false_unaided),
        "precision_basis": "against the answer key",
        "catch_ceiling_unaided": (rate_unaided is not None and rate_unaided >= CEILING_PERCENT),
        "confidence_unaided": confidence_unaided,
        "confidence_aided": confidence_aided,
        "confidence_gap_unaided": None if confidence_unaided is None or rate_unaided is None
        else round(confidence_unaided - rate_unaided, 1),
        "confidence_gap_aided": None if confidence_aided is None or rate_aided is None
        else round(confidence_aided - rate_aided, 1),
        "soundness_rating": session.get("soundness_rating"),
        "seconds_phase_1": session.get("seconds_phase_1"),
        "seconds_phase_2": session.get("seconds_phase_2"),
        "challenges_shown": len(challenge_by_id),
        "teachbacks_answered": answered,
        "teachback_completeness": _rate(complete, len(challenge_by_id)),
        "teachback_accuracy": _rate(correct, judged),
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
    }


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
    lines.append("  Catch rate, aided        %s   (%d of %d)" % (
        _pct(scores["catch_rate_aided"]), scores["caught_aided"], scores["defects_present"]))
    lines.append("  Lift                     %s points" % _num(scores["lift"]))
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
    lines.append("  Teach-back completeness  %s" % _pct(scores["teachback_completeness"]))
    lines.append("  Teach-back accuracy      %s" % _pct(scores["teachback_accuracy"]))
    lines.append("  Weak challenges refused  %d of %d" % (
        scores["distractors_rejected"], scores["distractors_shown"]))
    lines.append("  Time, phase 1 / phase 2  %s / %s seconds" % (
        _num(scores["seconds_phase_1"]), _num(scores["seconds_phase_2"])))
    lines.append("")
    lines.append("What the numbers are")
    for key in ("lift", "confidence_gap", "teachback_accuracy", "precision"):
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
