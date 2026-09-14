# Contract divergence, browser against Python

The Second Pass contract lives in two places: `checker.html` in the beat-the-machine
repository, and `second_pass/checker.py` here. They are meant to be one thing. This file
says exactly what was compared between them, on which inputs, after which normalization,
and what came out. It claims nothing beyond the comparison it describes.

**Where the two disagree, the browser wins.** `CHECKER.md` is the contract; this module is
an implementation of it.

## What was compared, 13 September 2026

**The inputs.** One file, `tests/checker-fixtures.json`, identical in both repositories once
line endings are normalized (a test here checks that). It holds 546 inputs:

| Ids | What they are |
| --- | --- |
| `T01` to `T54`, with `T10b`, `T12b`, `T14b`, `T15b` and `T18b` | the fixtures that guarded the page before the third review, including the end-to-end samples `T18` (halyard-v4), `T18b` (brightwater-v5) and `T19` (Kestrel) |
| `P01` to `P40` | the forty probes from the third independent review of 13 September 2026, entered exactly as that bundle supplied them |
| `MUL01` to `MUL22`, `STILL01` to `STILL28`, `FRAC01` to `FRAC26`, `DIGIT01` to `DIGIT16`, `COUNT01` to `COUNT15`, `ROLE01` to `ROLE06` | 113 mutations of the classes the review showed were open: multipliers, no-change claims, fractions and number words, digits outside 0 to 9, numbers that are not figures, and the Prompt 1 line shape, each class with inputs it must refuse and inputs it must accept |
| `A001` to `A139`, `B001` to `B036` | the 175 probes of the independent adversarial audit of 13 September 2026, entered as that audit supplied them |
| `CUR01` to `CUR24`, `SIGN01` to `SIGN26`, `SAME01` to `SAME28`, `PER01` to `PER33`, `ANA01` to `ANA20`, `RESP01` to `RESP14`, `QTY01` to `QTY14` | 159 mutations of the clearance grammar's classes, each with inputs it must refuse and inputs it must accept |

**How.** `tests/test_parity_shared_inputs.py` runs every input through `checker.html` under
Node, using the browser suite's own harness from `tests/run-checker-tests.cjs`, and through
`second_pass.checker` here, then compares these fields for every input:

| Field | What it holds |
| --- | --- |
| `status` | one status per sentence |
| `role` | every extracted figure as its raw text, unit and numeric role |
| `stats` | the coverage counts |
| `queueKinds` and `queue` | the reviewer's queue, by kind and in full |
| `finding` | every row's check, result, finding and question, per sentence |
| `survivors` | the sentences that reached the reviewer list |
| `csv`, `tsv`, `json` | the CSV export, the copy-table export and the JSON record |
| `prompt` | Prompt 2, the reviewer prompt |

**The normalization, all of it.** Every ISO timestamp is masked. The JSON record and the
serialized queue are parsed and compared as objects, so key order and indentation do not
count and every key and value does. Where the browser refuses an input outright, its probe
carries no role map and no queue, and both are read as empty. Nothing else is normalized.

**Not compared.** The rendered page text, which the browser reads out of a document stub and
Python assembles as plain text in its own order, and the page behaviors listed at the foot of
this file.

## The result

**All 546 inputs agree on every compared field**, `python -m pytest
tests/test_parity_shared_inputs.py -q`: 548 passed, the two extra tests being the check that
the two fixture files are the same file and the check that the clearance grammar's risk lexicon
and the patterns around it are the same in both, entry for entry. Both suites also pass on their
own: `node tests/run-checker-tests.cjs` 548 of 548 (546 fixtures, the check that the author
page's copy of the reader functions matches the page, and the check that the shared constants and
the clearance block match), and `python -m pytest tests/ -q` 1,173 passed with beat-the-machine
beside this repository, or 625 passed and 548 skipped without it.

That is agreement on these 546 inputs. It is not a proof that the two agree on inputs nobody
has written yet, and a matching test count would not prove it either; a new input is only
compared once it is added to the fixture file.

## What the comparison found on the way, and what changed

- **The review's probe P25 crashed the command line** with a `ValueError`. Python's `\d`
  matches Arabic-Indic digits and JavaScript's does not, so a run of them passed the figure
  pattern and then could not be converted. Every `\d` in `second_pass/checker.py` is now
  `0-9`, and digits outside 0 to 9 are an unparsed span in both. P25 returns **not checked**
  in both, with the span in the queue.
- **The two fixture files differed at T18 and T18b**, because the shared samples here were
  still halyard-v3 and brightwater-v2. `cases/shared/*.json` are now regenerated from the
  samples inline in `checker.html`: halyard-v4, brightwater-v5, Kestrel and Ridgeline, and
  `cases/shared/definitions/` carries halyard-v4 and brightwater-v5. The fixture files are
  now one file.
- **Prompt 2 differed on 161 of the 212 inputs.** The browser writes each queue item as
  `S1. <issue>` and Python wrote `S1 — <issue>`. This file's earlier statement that the two
  agreed byte for byte on the prompt was wrong. Python now writes the browser's form.

## The earlier comparison

The version of this file at `130b6b7` said the two agreed byte for byte on all fifty-nine
fixtures, including the prompt. The third review's forty-input comparison found 39 matching
sentence statuses and one crash (P25), and the fixture files differed at T18 and T18b. Both
of those were true of that revision, and so was the prompt difference above. The statements
in this file replace that one.

## Things the Python side does not carry

These are page behaviors, not contract steps, and they have no command-line meaning. They are
listed so that nobody reads their absence as a divergence:

- the parse preview's two column dropdowns and the re-run on changing one (the `cols`
  argument to `run_check` does the same job non-interactively)
- the numeric-role dropdown beside a row, and restamping a run with a reviewer's confirmation
- the Yes, No and Not on file ticks that ride into the CSV's human conclusion column; the
  column is written, and it is blank, which is what an untouched question means
- **Previous runs**, the print stylesheet, the clipboard actions and the stacked coverage bar
- Prompt 1, which is drafted before a memo exists and reads the panes rather than a run

## How to rerun the comparison

With beat-the-machine checked out beside this repository, or its path in `BEAT_THE_MACHINE`,
and Node on the path:

```
python -m pytest tests/test_parity_shared_inputs.py -q
```

Without Node or the sibling repository the comparison is skipped, and pytest says so; a
skipped comparison is not a passing one. The browser suite on its own:

```
node tests/run-checker-tests.cjs          # in the beat-the-machine repository
```

If the fixture file in one repository changes, copy it to the other and run both before
anything else.
