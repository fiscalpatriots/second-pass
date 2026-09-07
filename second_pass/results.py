"""Aggregating a pilot into the numbers the write-up prints.

Reads every session log in a directory and produces one table of per-reviewer
rows plus the pooled figures. Reviewers are R1 to Rn throughout, because that is
what the log files hold: no name reaches this stage, so none can leak out of it.

Two statistics are reported for catch rate, on purpose.

    Mean of rates   the average reviewer's result
    Pooled          every defect caught over every defect shown

With five reviewers the two can differ, and quoting only the flattering one is
the sort of thing that gets an entry disbelieved. Both are printed, and the
write-up should quote the pooled figure with the denominator beside it.

Nothing here estimates, extrapolates or projects. If four people show up, the
report says four.

A session log written by the simulation driver carries `simulated: true` and the
persona the reviewer was given. Where any log in the set carries it, the report
says "simulated reviewers" in its title and in every heading, and the table
carries a persona column, because a number produced by a model reviewer is not a
number produced by a person and nothing here is allowed to let the two be read
as the same thing. `--only simulated` and `--only human` split them.
"""

import json
import os
import statistics

from . import scoring


def load_logs(directory, only=None):
    """Read every scored session log. `only` is None, 'simulated' or 'human'."""
    if only not in (None, "simulated", "human"):
        raise ValueError("only must be None, 'simulated' or 'human'")
    logs = []
    if not os.path.isdir(directory):
        return logs
    for name in sorted(os.listdir(directory)):
        if not name.endswith(".json"):
            continue
        path = os.path.join(directory, name)
        try:
            with open(path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
        except ValueError:
            continue
        if data.get("schema") != "second-pass/session/v1":
            continue
        if not data.get("scores"):
            continue
        simulated = bool(data.get("simulated"))
        if only == "simulated" and not simulated:
            continue
        if only == "human" and simulated:
            continue
        data["_file"] = name
        logs.append(data)
    return logs


def _mean(values):
    values = [value for value in values if value is not None]
    if not values:
        return None
    return round(statistics.mean(values), 1)


def aggregate(logs):
    rows = []
    for log in logs:
        scores = log["scores"]
        rows.append({
            "reviewer": log["reviewer"],
            "case": log["case_id"],
            "defects": scores["defects_present"],
            "caught_unaided": scores["caught_unaided"],
            "caught_aided": scores["caught_aided"],
            "catch_rate_unaided": scores["catch_rate_unaided"],
            "catch_rate_aided": scores["catch_rate_aided"],
            "lift": scores["lift"],
            "precision_unaided": scores["precision_unaided"],
            "false_challenges": scores["false_challenges_unaided"],
            "outside_key": scores.get("findings_outside_key", scores["false_challenges_unaided"]),
            "outside_key_unadjudicated": scores.get("findings_outside_key_unadjudicated", 0),
            "confidence_unaided": scores["confidence_unaided"],
            "confidence_gap_unaided": scores["confidence_gap_unaided"],
            "confidence_gap_aided": scores["confidence_gap_aided"],
            "soundness_rating": scores["soundness_rating"],
            "teachback_completeness": scores["teachback_completeness"],
            "teachback_accuracy": scores["teachback_accuracy"],
            "distractors_rejected": scores["distractors_rejected"],
            "distractors_shown": scores["distractors_shown"],
            "seconds_phase_1": scores["seconds_phase_1"],
            "seconds_phase_2": scores["seconds_phase_2"],
            "provider": (log.get("challenger") or {}).get("provider_used"),
            "simulated": bool(log.get("simulated")),
            "persona": log.get("persona"),
        })
    rows.sort(key=lambda row: (_reviewer_number(row["reviewer"]), row["case"]))

    total_defects = sum(row["defects"] for row in rows)
    total_unaided = sum(row["caught_unaided"] for row in rows)
    total_aided = sum(row["caught_aided"] for row in rows)

    simulated_rows = [row for row in rows if row["simulated"]]

    summary = {
        "sessions": len(rows),
        "simulated_sessions": len(simulated_rows),
        "human_sessions": len(rows) - len(simulated_rows),
        "any_simulated": bool(simulated_rows),
        "all_simulated": bool(simulated_rows) and len(simulated_rows) == len(rows),
        "personas": sorted(set(row["persona"] for row in simulated_rows if row["persona"])),
        "reviewers": sorted(set(row["reviewer"] for row in rows), key=_reviewer_number),
        "cases": sorted(set(row["case"] for row in rows)),
        "providers": sorted(set(row["provider"] for row in rows if row["provider"])),
        "defects_total": total_defects,
        "caught_unaided_total": total_unaided,
        "caught_aided_total": total_aided,
        "pooled_catch_rate_unaided": _pooled(total_unaided, total_defects),
        "pooled_catch_rate_aided": _pooled(total_aided, total_defects),
        "mean_catch_rate_unaided": _mean([row["catch_rate_unaided"] for row in rows]),
        "mean_catch_rate_aided": _mean([row["catch_rate_aided"] for row in rows]),
        "mean_lift": _mean([row["lift"] for row in rows]),
        "mean_precision_unaided": _mean([row["precision_unaided"] for row in rows]),
        "mean_confidence_unaided": _mean([row["confidence_unaided"] for row in rows]),
        "mean_confidence_gap_unaided": _mean([row["confidence_gap_unaided"] for row in rows]),
        "mean_confidence_gap_aided": _mean([row["confidence_gap_aided"] for row in rows]),
        "mean_soundness_rating": _mean([row["soundness_rating"] for row in rows]),
        "mean_teachback_completeness": _mean([row["teachback_completeness"] for row in rows]),
        "mean_teachback_accuracy": _mean([row["teachback_accuracy"] for row in rows]),
        "distractors_rejected_total": sum(row["distractors_rejected"] for row in rows),
        "distractors_shown_total": sum(row["distractors_shown"] for row in rows),
        "outside_key_total": sum(row["outside_key"] for row in rows),
        "outside_key_unadjudicated_total": sum(row["outside_key_unadjudicated"] for row in rows),
        "mean_seconds_phase_1": _mean([row["seconds_phase_1"] for row in rows]),
        "mean_seconds_phase_2": _mean([row["seconds_phase_2"] for row in rows]),
        "by_level": _by_level(rows),
    }
    if summary["pooled_catch_rate_unaided"] is not None and summary["pooled_catch_rate_aided"] is not None:
        summary["pooled_lift"] = round(
            summary["pooled_catch_rate_aided"] - summary["pooled_catch_rate_unaided"], 1)
    else:
        summary["pooled_lift"] = None
    return {"rows": rows, "summary": summary}


LEVEL_ORDER = ("novice", "intermediate", "experienced")


def _by_level(rows):
    """One row per instruction level, pooled. Only where a persona is recorded.

    Pilot one's three levels behaved so differently that the pooled figure hid
    both ends of it: an unaided rate of 34.8 percent at one level and 89.4 at
    another averaged to something no reviewer produced. A facilitator quoting
    one number should be able to see the spread it came from.
    """
    levels = []
    present = [level for level in LEVEL_ORDER if any(row["persona"] == level for row in rows)]
    present += sorted(set(row["persona"] for row in rows
                          if row["persona"] and row["persona"] not in LEVEL_ORDER))
    for level in present:
        subset = [row for row in rows if row["persona"] == level]
        defects = sum(row["defects"] for row in subset)
        unaided = sum(row["caught_unaided"] for row in subset)
        aided = sum(row["caught_aided"] for row in subset)
        pooled_unaided = _pooled(unaided, defects)
        pooled_aided = _pooled(aided, defects)
        levels.append({
            "level": level,
            "sessions": len(subset),
            "defects": defects,
            "caught_unaided": unaided,
            "caught_aided": aided,
            "catch_rate_unaided": pooled_unaided,
            "catch_rate_aided": pooled_aided,
            "lift": None if pooled_unaided is None or pooled_aided is None
            else round(pooled_aided - pooled_unaided, 1),
            "confidence_gap_unaided": _mean([row["confidence_gap_unaided"] for row in subset]),
            "confidence_gap_aided": _mean([row["confidence_gap_aided"] for row in subset]),
            "distractors_rejected": sum(row["distractors_rejected"] for row in subset),
            "distractors_shown": sum(row["distractors_shown"] for row in subset),
            "at_ceiling": pooled_unaided is not None and pooled_unaided >= scoring.CEILING_PERCENT,
        })
    return levels


def _pooled(numerator, denominator):
    if not denominator:
        return None
    return round(100.0 * numerator / denominator, 1)


def _reviewer_number(alias):
    try:
        return int(str(alias)[1:])
    except (ValueError, TypeError):
        return 999


def _population(summary):
    """The words that go in the title and in every heading. Never decorative."""
    return "simulated reviewers" if summary.get("any_simulated") else "reviewers"


def format_report(aggregated, title="Second Pass pilot results"):
    rows = aggregated["rows"]
    summary = aggregated["summary"]
    who = _population(summary)
    out = []
    if summary.get("any_simulated"):
        title = "%s, simulated reviewers" % title
    out.append(title)
    out.append("=" * len(title))
    out.append("")
    if not rows:
        out.append("No scored sessions found. Run a session first, or point --dir at the right folder.")
        return "\n".join(out)

    out.append("Sessions: %d over %d %s(s), cases %s. AI layer: %s." % (
        summary["sessions"], len(summary["reviewers"]), who.rstrip("s"),
        ", ".join(summary["cases"]), ", ".join(summary["providers"]) or "not recorded"))
    if summary.get("any_simulated"):
        out.append(_mix_line(summary))
    out.append("")
    simulated = summary.get("any_simulated")
    header = (("Reviewer", "Persona", "Case") if simulated else ("Reviewer", "Case")) + (
        "Defects", "Unaided", "Aided", "Lift", "Precision", "Conf", "Gap", "Teach", "Sec 1", "Sec 2")
    widths = ((9, 14, 16) if simulated else (9, 16)) + (8, 8, 7, 7, 10, 6, 7, 7, 7, 7)
    out.append("".join(name.ljust(width) for name, width in zip(header, widths)))
    out.append("-" * sum(widths))
    for row in rows:
        lead = ((row["reviewer"], row["persona"] or "-", row["case"]) if simulated
                else (row["reviewer"], row["case"]))
        cells = lead + (
            str(row["defects"]),
            _p(row["catch_rate_unaided"]),
            _p(row["catch_rate_aided"]),
            _n(row["lift"]),
            _p(row["precision_unaided"]),
            _p(row["confidence_unaided"]),
            _n(row["confidence_gap_unaided"]),
            _p(row["teachback_completeness"]),
            _n(row["seconds_phase_1"]),
            _n(row["seconds_phase_2"]),
        )
        out.append("".join(str(cell).ljust(width) for cell, width in zip(cells, widths)))
    out.append("")
    if summary.get("by_level"):
        out.append("By instruction level, pooled")
        header = "%-16s%-10s%-10s%-9s%-8s%-14s%-13s%s" % (
            "Level", "Sessions", "Unaided", "Aided", "Lift", "Gap unaided", "Gap aided",
            "Weak refused")
        out.append(header)
        out.append("-" * len(header))
        for level in summary["by_level"]:
            out.append("%-16s%-10d%-10s%-9s%-8s%-14s%-13s%d of %d" % (
                level["level"], level["sessions"],
                _p(level["catch_rate_unaided"]), _p(level["catch_rate_aided"]),
                _n(level["lift"]), _n(level["confidence_gap_unaided"]),
                _n(level["confidence_gap_aided"]),
                level["distractors_rejected"], level["distractors_shown"]))
        for level in summary["by_level"]:
            if level["at_ceiling"]:
                out.append("  Ceiling: %s reviewers caught %s unaided, so at most %s points of "
                           "lift were available to them." % (
                               level["level"], _p(level["catch_rate_unaided"]),
                               _n(round(100.0 - level["catch_rate_unaided"], 1))))
        out.append("")
    out.append("Pooled over %s, every defect over every defect shown" % who)
    out.append("  Catch rate unaided        %s   (%d of %d)" % (
        _p(summary["pooled_catch_rate_unaided"]), summary["caught_unaided_total"], summary["defects_total"]))
    out.append("  Catch rate aided          %s   (%d of %d)" % (
        _p(summary["pooled_catch_rate_aided"]), summary["caught_aided_total"], summary["defects_total"]))
    out.append("  Lift                      %s points" % _n(summary["pooled_lift"]))
    if _at_ceiling(summary["pooled_catch_rate_unaided"]):
        out.append("  Ceiling: unaided catch was %s, so at most %s points of lift were available. "
                   "A small lift here is a ceiling, not a phase that did nothing." % (
                       _p(summary["pooled_catch_rate_unaided"]),
                       _n(round(100.0 - summary["pooled_catch_rate_unaided"], 1))))
    out.append("")
    out.append("Mean of %s rates" % who.rstrip("s"))
    out.append("  Catch rate unaided        %s" % _p(summary["mean_catch_rate_unaided"]))
    out.append("  Catch rate aided          %s" % _p(summary["mean_catch_rate_aided"]))
    out.append("  Lift                      %s points" % _n(summary["mean_lift"]))
    out.append("  Precision against the key %s" % _p(summary["mean_precision_unaided"]))
    out.append("  Findings outside the key  %d, of which %d matched no planted weak lead and "
               "await facilitator adjudication" % (
                   summary["outside_key_total"], summary["outside_key_unadjudicated_total"]))
    out.append("")
    out.append("Confidence against accuracy over %s, the headline measurement" % who)
    out.append("  Stated expectation        %s" % _p(summary["mean_confidence_unaided"]))
    out.append("  Actual, unaided           %s" % _p(summary["mean_catch_rate_unaided"]))
    out.append("  Gap, unaided              %s points" % _n(summary["mean_confidence_gap_unaided"]))
    out.append("  Gap, aided                %s points" % _n(summary["mean_confidence_gap_aided"]))
    out.append("  Memo soundness, 1 to 5    %s" % _n(summary["mean_soundness_rating"]))
    out.append("")
    out.append("Teach-back and time over %s" % who)
    out.append("  Completeness              %s" % _p(summary["mean_teachback_completeness"]))
    out.append("  Accuracy                  %s" % _p(summary["mean_teachback_accuracy"]))
    out.append("  Weak challenges refused   %d of %d" % (
        summary["distractors_rejected_total"], summary["distractors_shown_total"]))
    out.append("  Mean seconds, phase 1     %s" % _n(summary["mean_seconds_phase_1"]))
    out.append("  Mean seconds, phase 2     %s" % _n(summary["mean_seconds_phase_2"]))
    out.append("")
    out.append("What the numbers are")
    for key in ("lift", "confidence_gap", "teachback_accuracy", "precision"):
        out.append("  " + scoring.DEFINITIONS[key])
    return "\n".join(out)


def _at_ceiling(rate):
    return rate is not None and rate >= scoring.CEILING_PERCENT


def _mix_line(summary):
    """Never let a mixed set be read as one population."""
    if summary.get("all_simulated"):
        return "Every session in this set was run by a simulated reviewer, not by a person."
    return ("This set mixes populations: %d session(s) run by simulated reviewers and %d by "
            "people. Split them with --only simulated and --only human before quoting a figure."
            % (summary["simulated_sessions"], summary["human_sessions"]))


def format_markdown(aggregated):
    """The table that goes into the write-up and into PILOT.md."""
    rows = aggregated["rows"]
    summary = aggregated["summary"]
    simulated = summary.get("any_simulated")
    lines = []
    if simulated:
        lines.append("**Simulated reviewers.** %s" % _mix_line(summary))
        lines.append("")
    if simulated:
        lines.append("| Reviewer | Persona | Case | Defects | Caught unaided | Caught aided | "
                     "Confidence stated | Gap |")
        lines.append("|---|---|---|---|---|---|---|---|")
    else:
        lines.append("| Reviewer | Case | Defects | Caught unaided | Caught aided | "
                     "Confidence stated | Gap |")
        lines.append("|---|---|---|---|---|---|---|")
    for row in rows:
        lead = ("| %s | %s | %s " % (row["reviewer"], row["persona"] or "-", row["case"])
                if simulated else "| %s | %s " % (row["reviewer"], row["case"]))
        lines.append(lead + "| %d | %d (%s) | %d (%s) | %s | %s |" % (
            row["defects"],
            row["caught_unaided"], _p(row["catch_rate_unaided"]),
            row["caught_aided"], _p(row["catch_rate_aided"]),
            _p(row["confidence_unaided"]), _n(row["confidence_gap_unaided"])))
    pooled_lead = ("| **Pooled, simulated reviewers** | %d persona(s) | %d session(s) "
                   % (len(summary.get("personas") or []), summary["sessions"])
                   if simulated else "| **Pooled** | %d session(s) " % summary["sessions"])
    lines.append(pooled_lead + "| %d | %d (%s) | %d (%s) | %s | %s |" % (
        summary["defects_total"],
        summary["caught_unaided_total"], _p(summary["pooled_catch_rate_unaided"]),
        summary["caught_aided_total"], _p(summary["pooled_catch_rate_aided"]),
        _p(summary["mean_confidence_unaided"]), _n(summary["mean_confidence_gap_unaided"])))
    if summary.get("by_level"):
        lines.append("")
        lines.append("By instruction level, pooled. Catch rates are every defect over every "
                     "defect shown; the confidence gaps are the mean of the session gaps.")
        lines.append("")
        lines.append("| Level | Sessions | Unaided | Aided | Lift | Gap unaided | Gap aided | "
                     "Weak challenges refused |")
        lines.append("|---|---|---|---|---|---|---|---|")
        for level in summary["by_level"]:
            lines.append("| %s | %d | %s (%d of %d) | %s (%d of %d) | %s | %s | %s | %d of %d |" % (
                level["level"], level["sessions"],
                _p(level["catch_rate_unaided"]), level["caught_unaided"], level["defects"],
                _p(level["catch_rate_aided"]), level["caught_aided"], level["defects"],
                _n(level["lift"]), _n(level["confidence_gap_unaided"]),
                _n(level["confidence_gap_aided"]),
                level["distractors_rejected"], level["distractors_shown"]))
        ceilings = [level for level in summary["by_level"] if level["at_ceiling"]]
        if ceilings:
            lines.append("")
            for level in ceilings:
                lines.append("Ceiling note: %s reviewers caught %s of the planted defects unaided, "
                             "so at most %s points of lift were available to them. A small lift on "
                             "that row is a ceiling, not a phase that did nothing." % (
                                 level["level"], _p(level["catch_rate_unaided"]),
                                 _n(round(100.0 - level["catch_rate_unaided"], 1))))
    lines.append("")
    for key in ("lift", "confidence_gap", "teachback_accuracy", "precision"):
        lines.append(scoring.DEFINITIONS[key])
        lines.append("")
    return "\n".join(lines).rstrip()


def _p(value):
    return "n/a" if value is None else "{:.1f}%".format(value)


def _n(value):
    return "n/a" if value is None else str(value)
