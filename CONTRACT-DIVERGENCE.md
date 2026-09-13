# Contract divergence, browser against Python

The Second Pass contract now exists in two places: `checker.html` in the
beat-the-machine repository, and `second_pass/checker.py` here. They are meant
to be one thing. This file records where they are not, by fixture id, so nobody
has to discover it during a close.

**Where the two disagree, the browser wins.** `CHECKER.md` is the contract; this
module is an implementation of it.

## How they were compared, 13 September 2026

Both were run over all fifty-nine fixtures in `tests/checker-fixtures.json`,
and the full probe was compared field by field, not just the assertions the
fixtures carry. The probe is the one the browser's own runner builds:

| Field | What it holds |
| --- | --- |
| `stats` | the nine coverage counts |
| `status` | one status per sentence |
| `role` | every figure's raw text, unit and numeric role |
| `finding` | every row's check, result, finding and question, per sentence |
| `account` | every ledger line recomputed, with both legs and whether it clears |
| `flags` | unconfirmed columns, ambiguous rows, discarded columns, duplicates, skipped rows |
| `queue` | the reviewer's queue, serialised whole |
| `queueKinds` | the queue in order, by kind |
| `survivors` | the sentences that reached the reviewer list |
| `csv` | the CSV export, every column |
| `json` | the JSON record, every field |
| `prompt` | Prompt 2, the reviewer prompt |
| `tsv` | the copy-table export |

## The result

**No divergence on any fixture, on any of those fields.** The two agree byte for
byte, including the run identifier and the source version, which are hashes of
the inputs and would move if any input were read differently.

Two things differ by construction and are not contract:

1. **The rendered page text.** The browser probe reads the text content of the
   results DOM; Python assembles the same facts as plain text in a different
   order and without the markup. Every fixture clause written against
   `pageText` (T07, T08, T10, T10b, T13, T14, T15, T15b, T18, T19) passes in
   both, because every one asserts that a phrase is present, and the phrases
   come from the findings rather than from the layout.
2. **The run timestamp.** Two runs at different moments carry different stamps.
   The comparison normalises it.

## Where the two fixture files differ, 13 September 2026

Two ids, and neither is a contract divergence:

| Id | Why |
| --- | --- |
| `T18` | the end-to-end Halyard sample. beat-the-machine asserts against `halyard-v4`; `cases/shared/halyard.json` here is still `halyard-v3`, so the fixture here asserts against v3. Same assertions, older memo |
| `T18b` | the same, Brightwater. There, `brightwater-v4`; here, `brightwater-v2` |

The shared sample files here are hand-kept, while beat-the-machine regenerates
its inline copies with `build-checker-cases.cjs`. Bringing them to v4 is a case
change, not a checker change, and it is not made here on a QA pass. Every other
fixture, `T01` to `T54`, is byte for byte the same file in both repositories.

## Quantities written in words, added 13 September 2026

`T21` and the six new fixtures `T49` to `T54` carry rule 1c of `CHECKER.md`:
units through millions are parsed to a figure where the parser resolves the run
and the words give it a unit, and everything else in words either reaches the
reviewer's queue or, where it is a count standing beside no claim, is left
alone. Both implementations were changed in the same commit and both suites run
clean: `node tests/run-checker-tests.cjs` 59/59, `python -m pytest tests/ -q`
138 passed.

## Things the Python side does not carry

These are page behaviours, not contract steps, and they have no command-line
meaning. They are listed so that nobody reads their absence as a divergence:

- the parse preview's two column dropdowns and the re-run on changing one
  (the `cols` argument to `run_check` does the same job non-interactively)
- the numeric-role dropdown beside a row, and re-stamping a run with a
  reviewer's confirmation
- the Yes / No / Not on file ticks that ride into the CSV's human conclusion
  column; the column is written, and it is blank, which is what an untouched
  question means
- **Previous runs**, the print stylesheet, the clipboard actions and the
  stacked coverage bar
- Prompt 1, which is drafted before a memo exists and reads the panes rather
  than a finished run

## How to re-run the comparison

The browser suite:

```
node tests/run-checker-tests.cjs          # in the beat-the-machine repository
```

The Python suite:

```
python -m pytest tests/test_checker_contract.py -q
```

Both read the same `checker-fixtures.json`. If the file in this repository ever
falls behind the one that guards the page, copy it across and run the suite
again before anything else.
