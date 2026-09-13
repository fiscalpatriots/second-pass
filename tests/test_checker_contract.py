"""The browser's regression suite, run against the Python checker.

``tests/checker-fixtures.json`` is the suite that guards ``checker.html`` at
beat-the-machine, copied here byte for byte.  The browser runs it with
``node tests/run-checker-tests.cjs``; this file runs the same fifty-three
fixtures through ``second_pass.checker`` and asserts the same required
behaviour, clause for clause.

One suite, two implementations.  A change to either that moves a status fails
here.  Where the two could ever disagree, the browser's contract in ``CHECKER.md``
wins, and anything that could not be closed is written down in
``CONTRACT-DIVERGENCE.md``.
"""

import json
import os

import pytest

from second_pass import checker

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
FIXTURE_FILE = os.path.join(HERE, "checker-fixtures.json")
SHARED = os.path.join(ROOT, "cases", "shared")

DEFAULTS = {"ledger": "", "memo": "", "ratios": "", "dollar": "25000", "pct": "10",
            "rule": "both", "zerobase": "owing", "period": "Regression fixture",
            "memover": "fixture", "company": "", "reviewer": ""}


def load_fixtures():
    with open(FIXTURE_FILE, encoding="utf-8") as handle:
        return json.load(handle)


FIXTURES = load_fixtures()
FIXTURE_IDS = [fx["id"] for fx in FIXTURES]


def load_sample(key):
    with open(os.path.join(SHARED, key + ".json"), encoding="utf-8") as handle:
        return json.load(handle)


def run_fixture(fx):
    """The inputs the browser harness sets, and the run they produce."""
    if fx.get("sample"):
        case = load_sample(fx["sample"])
        th = case["thresholds"]
        return checker.run_check(
            case["ledger"], case["memo"], ratios=case["ratios"],
            dollar_floor=th["dollar"], percent_floor=th["percent"], rule=th["rule"],
            zero_prior=th["zeroPrior"], period=case["period"],
            memo_version=case["memoVersion"], company=case["company"],
            case_version=case["caseVersion"])
    inputs = dict(DEFAULTS)
    inputs.update(fx.get("inputs") or {})
    return checker.run_check(
        inputs["ledger"], inputs["memo"], ratios=inputs["ratios"],
        dollar_floor=inputs["dollar"], percent_floor=inputs["pct"], rule=inputs["rule"],
        zero_prior=inputs["zerobase"], period=inputs["period"],
        memo_version=inputs["memover"], company=inputs["company"], reviewer=inputs["reviewer"])


def probe(fx):
    """The same probe the browser harness builds, so an assertion written for one
    reads the same against the other."""
    try:
        result = run_fixture(fx)
    except checker.CheckerInputError as error:
        return {"ran": False, "pageText": str(error), "stats": {}, "status": {}, "role": {},
                "finding": {}, "account": {}, "accounts": [], "flags": {}, "queue": "",
                "queueKinds": "", "csv": "", "prompt": "", "json": "", "tsv": "", "survivors": ""}

    out = {
        "ran": True,
        "pageText": result.page_text(),
        "stats": result.stats,
        "runId": result.runId,
        "status": {s["label"]: s["st"] for s in result.sents},
        "role": {s["label"]: " | ".join(f["raw"] + "=" + f["unit"] + "/" + f["role"]
                                        for f in s["figs"]) for s in result.sents},
        "finding": {},
        "survivors": ",".join(s["label"] for s in result.survivors),
        "flags": {"colsUnconfirmed": bool(result.ledger["colsUnconfirmed"]),
                  "ambig": len(result.ledger["ambig"]),
                  "discarded": len(result.ledger["discarded"]),
                  "dups": len(result.ledger["dups"]),
                  "skipped": result.stats["rowsSkipped"]},
        "queue": json.dumps(result.queue, separators=(",", ":"), ensure_ascii=False),
        "queueKinds": ",".join(q["kind"] for q in result.queue),
        "csv": result.csv(),
        "prompt": result.reviewer_prompt(),
        "json": result.json_record(),
        "tsv": result.tsv(),
    }
    for sentence in result.sents:
        out["finding"][sentence["label"]] = " || ".join(
            row["check"] + ": " + row["result"] + " " + row["det"] + " "
            + (" ".join(row["ask"]) if isinstance(row.get("ask"), list) else (row.get("ask") or ""))
            for row in result.rows if row.get("label") == sentence["label"])
    out["accounts"] = [{"num": a.num, "name": a.name, "prior": a.prior, "cur": a.cur,
                        "change": a.change, "pct": a.pct, "clears": a.clears,
                        "legD": a.legs["d"], "legP": a.legs["p"], "sentences": len(a.sent)}
                       for a in result.accounts]
    out["account"] = {}
    for a in out["accounts"]:
        out["account"].setdefault(a["num"], a)
    out["accountCount"] = len(out["accounts"])
    return out


OPS = {
    "eq": lambda got, want: got == want,
    "ne": lambda got, want: got != want,
    "gte": lambda got, want: float(got) >= float(want),
    "lte": lambda got, want: float(got) <= float(want),
    "approx": lambda got, want: abs(float(got) - float(want)) < 0.0005,
    "includes": lambda got, want: want in str(got),
    "notIncludes": lambda got, want: want not in str(got),
    "oneOf": lambda got, want: got in want,
    "isNull": lambda got, want: got is None,
}


def dig(probed, path):
    node = probed
    for key in path.split("."):
        if node is None:
            return None
        node = node.get(key) if isinstance(node, dict) else None
    return node


@pytest.mark.parametrize("fixture", FIXTURES, ids=FIXTURE_IDS)
def test_fixture_holds_in_python(fixture):
    """Every clause the browser asserts, asserted here."""
    probed = probe(fixture)
    failures = []
    for clause in fixture.get("expect", []):
        got = dig(probed, clause["get"])
        try:
            ok = OPS[clause["op"]](got, clause.get("value"))
        except (TypeError, ValueError):
            ok = False
        if not ok:
            shown = str(got)
            if len(shown) > 400:
                shown = shown[:400] + "…"
            failures.append("%s\n      %s %s %s\n      got: %s"
                            % (clause["desc"], clause["get"], clause["op"],
                               json.dumps(clause.get("value")), shown))
    assert not failures, ("%s %s\n  required: %s\n\n  %s"
                          % (fixture["id"], fixture["name"], fixture.get("required", ""),
                             "\n\n  ".join(failures)))


def test_the_suite_is_the_browser_suite():
    """Fifty-three fixtures, T01 to T48 with the lettered companions."""
    assert len(FIXTURES) == 53
    assert FIXTURE_IDS[0] == "T01"
    assert FIXTURE_IDS[-1] == "T48"
    assert len(set(FIXTURE_IDS)) == 53


# The coverage strips printed in CHECKER.md for the four samples. These are the
# numbers a reader of that file is told to expect, so they are asserted directly
# rather than through a fixture.
SAMPLE_COVERAGE = {
    "halyard": dict(sent=12, checked=4, review=5, notchecked=0, failed=3,
                    rowsUsed=14, rowsSkipped=0, silent=1, queue=13),
    "brightwater": dict(sent=5, checked=2, review=1, notchecked=0, failed=2,
                        rowsUsed=5, rowsSkipped=0, silent=0, queue=3),
    "kestrel": dict(sent=6, checked=3, review=0, notchecked=1, failed=2,
                    rowsUsed=6, rowsSkipped=0, silent=1, queue=6),
    "ridgeline": dict(sent=3, checked=1, review=0, notchecked=0, failed=2,
                      rowsUsed=5, rowsSkipped=0, silent=1, queue=3),
}


@pytest.mark.parametrize("key", sorted(SAMPLE_COVERAGE), ids=sorted(SAMPLE_COVERAGE))
def test_sample_coverage_matches_the_published_strip(key):
    case = load_sample(key)
    th = case["thresholds"]
    result = checker.run_check(case["ledger"], case["memo"], ratios=case["ratios"],
                               dollar_floor=th["dollar"], percent_floor=th["percent"],
                               rule=th["rule"], zero_prior=th["zeroPrior"],
                               period=case["period"], memo_version=case["memoVersion"],
                               company=case["company"], case_version=case["caseVersion"])
    for field, want in SAMPLE_COVERAGE[key].items():
        assert result.stats[field] == want, (
            "%s: %s is %s, CHECKER.md says %s" % (key, field, result.stats[field], want))


def test_a_status_is_never_promoted():
    """Nothing later in a run may make a sentence read better than the step that
    set it. The rank is the whole of that rule."""
    assert checker.worse("failed", "checked within scope") == "failed"
    assert checker.worse("needs review", "not checked") == "needs review"
    assert checker.worse("not checked", "needs review") == "needs review"
    assert checker.worse("checked within scope", "failed") == "failed"


def test_the_boundary_policy_is_more_than_and_at_least():
    """A change of exactly the dollar floor does not clear the dollar leg; a
    change of exactly the percent floor does clear the percent leg."""
    ledger = "6100\tRent expense\t250000\t275000"
    result = checker.run_check(ledger, "S1. Rent expense rose by $25,000.")
    account = result.accounts[0]
    assert account.change == 25000
    assert account.legs["d"] is False, "$25,000 is not more than $25,000"
    assert account.legs["p"] is True, "10.0 percent is at least 10 percent"
    assert account.clears is False


def test_an_empty_ledger_is_refused_rather_than_run():
    with pytest.raises(checker.CheckerInputError):
        checker.run_check("", "S1. Something happened.")
    with pytest.raises(checker.CheckerInputError):
        checker.run_check("", "")
