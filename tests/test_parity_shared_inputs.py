"""One input set, two implementations, compared output for output.

The input set is ``tests/checker-fixtures.json``: the fixtures that guard the page,
the forty probes from the third independent review of 13 September 2026, and the
mutation classes written against them (multipliers, no-change claims, fractions,
digits outside 0 to 9, numbers that are not figures, and the Prompt 1 line shape).
The same file guards ``checker.html`` at beat-the-machine.

Every input is run through ``checker.html`` under Node, using the browser suite's
own harness, and through ``second_pass.checker`` here. The outputs are compared
after three normalizations, and nothing else is normalized:

* every ISO timestamp is masked, because two runs at two moments differ by design;
* the JSON record and the serialized queue are parsed and compared as objects, so
  key order and indentation do not count, while every key and value does;
* where the browser refuses an input outright, its probe carries no role map and no
  queue, and both are read as empty, which is what the Python probe returns.

The compared fields, per input, are the sentence statuses, every extracted figure
as ``raw=unit/role``, the coverage counts, the reviewer queue by kind and in full,
every finding row's check, result, text and question for every sentence, the
sentences that reached the reviewer list, the CSV export, the copy-table export,
the JSON record and Prompt 2. The rendered page text is not compared: the browser
reads it out of a document stub and Python assembles the same facts as plain text.

The browser side needs Node and the beat-the-machine repository beside this one, or
at ``BEAT_THE_MACHINE``. Where either is missing the test is skipped, not passed.
"""

import json
import os
import re
import shutil
import subprocess

import pytest

from tests.test_checker_contract import FIXTURES, probe

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
GAME = os.environ.get("BEAT_THE_MACHINE") or os.path.join(os.path.dirname(ROOT), "beat-the-machine")
NODE = shutil.which("node")

FIELDS = ("status", "role", "stats", "queueKinds", "finding", "survivors", "queue", "csv", "tsv",
          "json", "prompt")
ISO = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9:.]+Z")

_NODE_SCRIPT = r"""
const fs = require("fs"), path = require("path");
const game = process.argv[1], fixtures = JSON.parse(fs.readFileSync(process.argv[2], "utf8"));
let src = fs.readFileSync(path.join(game, "tests/run-checker-tests.cjs"), "utf8")
  .replace(/^#![^\n]*\n/, "").split("const only =")[0];
const execute = new Function("require", "__dirname", src + "\nreturn execute;")(require, path.join(game, "tests"));
const out = {};
for (const fx of fixtures) {
  let p;
  try { p = execute(fx); } catch (e) { out[fx.id] = { error: String(e && e.message) }; continue; }
  out[fx.id] = { status: p.status, role: p.role, stats: p.stats, queueKinds: p.queueKinds,
                 finding: p.finding, survivors: p.survivors, queue: p.queue, csv: p.csv, tsv: p.tsv,
                 json: p.json, prompt: p.prompt, consoleErrors: p.consoleErrors };
}
process.stdout.write(JSON.stringify(out));
"""


def _browser_run():
    if not NODE or not os.path.isfile(os.path.join(GAME, "checker.html")):
        return None
    fixture_file = os.path.join(HERE, "checker-fixtures.json")
    done = subprocess.run([NODE, "-e", _NODE_SCRIPT, GAME, fixture_file],
                          capture_output=True, text=True, encoding="utf-8", timeout=600)
    if done.returncode != 0:
        raise AssertionError("the browser run failed: " + done.stderr[-2000:])
    return json.loads(done.stdout)


_BROWSER = {}


def browser():
    if "run" not in _BROWSER:
        _BROWSER["run"] = _browser_run()
    return _BROWSER["run"]


def normalize(field, value):
    if value is None:
        value = {} if field in ("status", "role", "stats", "finding") else ""
    if field in ("json", "queue"):
        text = ISO.sub("<timestamp>", value) if isinstance(value, str) else value
        return json.loads(text) if isinstance(text, str) and text else text
    if isinstance(value, str):
        return ISO.sub("<timestamp>", value)
    return value


def test_the_fixture_file_is_the_browser_fixture_file():
    """Both repositories carry one fixture file, byte for byte after line endings."""
    theirs = os.path.join(GAME, "tests", "checker-fixtures.json")
    if not os.path.isfile(theirs):
        pytest.skip("beat-the-machine is not beside this repository")
    with open(theirs, encoding="utf-8") as a, open(os.path.join(HERE, "checker-fixtures.json"),
                                                   encoding="utf-8") as b:
        assert a.read().replace("\r\n", "\n") == b.read().replace("\r\n", "\n")


@pytest.mark.parametrize("fixture", FIXTURES, ids=[fx["id"] for fx in FIXTURES])
def test_both_implementations_agree(fixture):
    run = browser()
    if run is None:
        pytest.skip("Node or the beat-the-machine repository is not available")
    got_js = run[fixture["id"]]
    assert "error" not in got_js, got_js.get("error")
    assert not got_js["consoleErrors"], got_js["consoleErrors"]
    got_py = probe(fixture)
    for field in FIELDS:
        a = normalize(field, got_js.get(field))
        b = normalize(field, got_py.get(field))
        assert a == b, ("%s differs on %s\n  browser: %s\n  python:  %s"
                        % (fixture["id"], field, json.dumps(a)[:1500], json.dumps(b)[:1500]))
