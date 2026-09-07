# Pilot two findings, and what was done about each one

The sponsor's rubric is measurable outcomes, governance and replicability, and
its own four words for the method are pilot, measure, refine, replicate. Pilot two
ran on 5 September 2026 against the rebuilt case pack and
`prompts/challenger.v2.md`: six simulated reviewers, three instruction levels,
eighteen sessions, 192 planted defects worked. Its numbers are frozen in
PILOT-2-RESULTS.md and the logs behind them are in `sessions/`.

Pilot one asked ten questions of the build and every one of them turned into a
change. Pilot two asked six, and the balance is different. One was a defect in the
instrument and it was fixed the same night. The other five are limits of what this
instrument can measure or of what this pack can teach, and the answer to a limit
is to print it, which is what this file and SIMULATION.md do. Nothing here was
argued away, and where a limit could have been dressed up as a feature it is
written as the limit instead.

---

## 1. Weak challenges are still sortable by shape once a reviewer has seen a case

**What the reviewers found.** Pilot one planted every weak challenge in one shape,
a line below the threshold with a document request attached, and the refine step
replaced that with four shapes and a rule that no case plants a shape twice. The
refusal rate went from 24 of 36 to 49 of 54. Pilot two's reviewers said the tell
had moved rather than gone. A challenge that carries the line
"What would count as evidence: ..." has never once been a weak challenge, and
after one case a reviewer knows it.

**What is actually true, counted.** Across the pack there are 41 challenges. Twelve
of the 32 real challenges carry an evidence line and none of the nine weak ones
does. So the evidence line marks twelve challenges as real for free. It marks
nothing as weak, because twenty real challenges do not carry one either, which
leaves twenty-nine challenges the reviewer still has to sort on the arithmetic,
nine of them weak.

**Why this is printed rather than fixed.** The evidence line is not decoration.
It is the answer to pilot one's finding 9, which was that a challenge saying "name
a driver" has to say what would count, and removing it to hide a tell would be
paying for the measurement with the thing the tool is for. Adding an evidence line
to the weak challenges was considered and rejected for the same reason: a weak
challenge that names the artefact it wants is a better weak challenge, but writing
one for every shape means writing plausible evidence asks for challenges that do
not hold, which is a defect pack teaching a reviewer that the evidence bar means
nothing.

**The limit as it stands.** The weak challenge refusal rate of 49 of 54 is a
partial measurement. Some share of it is reading and some share of it is a
reviewer who has learned that the challenges without an evidence line are the ones
worth recomputing, and this pass cannot separate the two. A facilitator running
the human pilot should read the reject reasons in the session logs, which are kept
verbatim, and see whether they cite arithmetic or shape.

---

## 2. Precision against the answer key still marks down real findings

**What the reviewers found.** The same objection pilot one raised, raised again by
a different pass. A reviewer who writes a finding a senior would put in a memo,
and which the case author did not plant, does not get credit for it. Pilot two
logged seventeen findings outside the key across eighteen sessions, six of which
matched no planted weak lead either.

**What was already done, in pilot one's finding 6.** Out-of-key findings are
counted on their own as `findings_outside_key`, split into
`findings_outside_key_matched_weak` and `findings_outside_key_unadjudicated`.
They are listed verbatim in the session log with the reviewer's own words kept
whole. They have never touched a catch rate and
`tests/test_smoke.py::test_precision_is_against_the_key_and_out_of_key_findings_are_counted_apart`
says so. Precision carries the string "against the answer key" wherever it prints,
and `precision_basis` carries it in the scores block.

**Why it is still a limit.** Labelling the number correctly does not make it a
measure of review quality, and the honest reading of a precision figure here is
narrow: it is agreement with one author's key on one pack, and nothing more. A
reviewer can lower it by being right about something the author missed. The tool
does not get to call that wrong, and neither does the write-up. Six unadjudicated
findings from this pass are sitting in the logs for a facilitator, and adjudicating
them is a person's job, not the scorer's.

---

## 3. The lift at the senior level is small, and it is small because of the ceiling

**What the reviewers found.** The experienced level came in at 89.1 percent
unaided and 98.4 percent aided, a lift of 9.3 points against 54.7 at the novice
level. Read without its denominator that looks like the challenge list doing
almost nothing for a senior.

**Why it is a ceiling and not a weak result.** An unaided rate of 89.1 percent
leaves 10.9 points of lift available in total, so the aided phase captured 9.3 of
the 10.9 there were. Four of the six experienced sessions were at or above 90
percent unaided on their own, and two of those were at 100 percent, where no lift
is arithmetically possible.

**What was already done, in pilot one's finding 7.** `scoring.CEILING_PERCENT` is
90, any unaided catch rate at or above it prints a ceiling note naming the rate
and the points that were available, `catch_ceiling_unaided` is in the scores block
for anyone recomputing, and
`tests/test_smoke.py::test_a_ceiling_note_prints_when_unaided_catch_is_at_the_top`
holds it. The pooled experienced row sits at 89.1 percent, just under the
threshold, so no note printed on that row and the four sessions above it printed
their own.

**The limit as it stands.** A tool that trains judgment has the least to offer the
people who already have it, and that is the correct result rather than a
disappointment. Any quotation of the pooled 35.9 point lift has to carry the level
spread with it, because the pooled figure is a number no single reviewer produced.

---

## 4. The printed schema example reproduced case-01-june's answers. Fixed.

**What the reviewers found.** The JSON example printed by `sim start` and
`sim commit` was written from case-01-june. The findings example named account
5100 inbound freight rising $73,800 against a sentence that says it declined,
which is that case's direction reversal, and account 6000 warehouse wages moving
$72,500 with no driver, which is its missing driver. The teach-back example showed
an accept written on its June fuel cutoff and a reject written on its
below-threshold weak challenge, correct reason and all.

**Why it mattered.** The whole instrument is one rule: commit your own findings
before the tool shows you anything it produced. Every other surface honours it.
`view.md` is built by `cases.reviewer_view()` and strips the key, the challenge
list does not exist on disk until the commitment is sealed, a second commit is
refused, and the score block withholds the key from a reviewer running three cases
in a row. Then the command that asks for the commitment printed three of case
one's answers in the prompt. A reviewer starting on case-01-june was handed them
by the tool whose job is to withhold them, and any catch rate that reviewer
produced on that case is contaminated by an unknown amount.

**The fix.** The example is invented, and the invented set is declared in one
place so it cannot drift.

- `second_pass/sim.EXAMPLE_ACCOUNTS` holds the three accounts the examples use:
  9200 Groundskeeping contract at $61,300, 9250 Waste removal at $38,200, and
  9280 Site security at $14,900. No case in the pack carries any of those line
  codes, any of those account names, or any of those figures in either formatted
  or unformatted form.
- `sim.FINDINGS_SCHEMA` and `sim.TEACHBACK_SCHEMA` are rewritten on that set. The
  shape they teach is unchanged, including the soundness field, the eight word
  floor and what confidence is measured against, all of which were pilot one's
  finding 8.
- `tests/test_sim.py::test_the_printed_schema_example_leaks_no_case` captures
  what the two commands actually print and checks it both ways. Forward, every
  account code, account name and dollar figure in the example is looked for in
  all three case files and is not there. Backward, every account name in the pack,
  every planted defect's own movement, the first forty characters of every
  defect's claim and correction, and the text and rejection reason of every weak
  challenge are looked for in what the commands print, and none of it is there.
  Thirty-two planted movements are walked. The test fails against either half of
  the old example, which was checked by putting the old example back.
- The same invented set replaced two documentation examples that carried the same
  real figures: the case-authoring schema in README.md, which showed account 5100
  at $73,800 with case-01-june's own counterparty and focus figures, and the
  reproduction block in SIMULATION.md, which showed the same findings and
  teach-back examples the commands print.

**What the fix does not cover, said plainly.** PILOT-1-FINDINGS.md, this file,
`sessions/example/`, `sessions/pilot-1/` and the answer key itself all discuss or
contain planted defects, because that is what they are for. They are facilitator
files in the same sense the answer key is, and each persona file already names the
session folder's own state and truth files, the cases folder, the answer key, the
prompts folder and the tests as files a reviewer never opens. A facilitator running
the human pilot hands out a link to the tool, not to the repository. That is a
procedure rather than a guard rail in code, and it is written down here so nobody
mistakes it for one.

**Test count.** Thirty-two tests across the three files, up from thirty-one. All
pass, and the output is at the foot of BUILD-LOG.txt.

---

## 5. Defect kinds repeat across the three cases enough to be learnable back to back

**What the reviewers found.** Pilot one's finding 4 was that defect kinds sat in
the same key slots in all three cases, and the rebuild rotated the kinds, the key
order and the accounts, and made sure no two cases carry the same set. Pilot two's
reviewers said the rotation fixed the slot pattern and not the repertoire. A
reviewer working three cases in a row still meets most of the same failure modes
three times.

**What is actually true, counted.** Twelve defect kinds exist. Nine of them are
planted in all three cases: contradiction, cutoff, driver wrong account,
immaterial over-explained, missing driver material, reclass as growth,
unsupported driver, wrong period and wrong sign. Only three vary across the pack.
Percent as absolute is in July alone, mismatched amount is in June and July, and
rounding flips conclusion is in June and August. The validator enforces that the
sets differ, and three kinds is how much they differ.

**Why it is a limit rather than a fix.** Twelve kinds is the whole taxonomy, and
ten to twelve defects per case over three cases needs 32 slots, so the nine common
kinds are arithmetic rather than laziness. Cutting a case to eight defects to widen
the spread would cost more measurement than the repetition costs. The real answer
is more cases, which is the replicability path the tool already documents: a case
is one JSON file, the loader validates it, and a firm swapping in its own memos
gets its own kinds.

**How it should be quoted.** The three-case run measures a reviewer meeting each
kind up to three times, so the third case is not a clean first encounter. A
facilitator wanting a clean one runs one case per reviewer, which the tool supports
and which the human pilot in PILOT.md is written as.

---

## 6. The numbers measure language-model reviewers, not people

**What the reviewers found.** Stated by the reviewers themselves, and it is the
same limit SIMULATION.md opened with before pilot one ran. The eighteen sessions
measure the effect of the withholding rule and the cited challenge list on
language-model agents at three instruction levels. They do not measure people.

**Why nothing about it can be fixed here.** A persona file is an instruction, not
a skill. Telling a model to read fast and trust fluent prose produces a reviewer
that says it read fast, and the level separation is evidence about instruction and
model sensitivity rather than about seniority. Several of the planted kinds, wrong
sign, wrong period, cutoff and reclassification among them, are named failure modes
that appear in accounting training material, so a model may recognise them from
training rather than from reading the memo, and the simulated catch rates are
inflated by an unknown amount because of it. A model also writes its confidence in
the same file as its findings, so it answers the confidence question after doing
the work while a person answers it before, which makes a simulated confidence gap a
weaker claim than a human one rather than a stronger one.

**What was done.** The word simulated is enforced rather than requested. `results`
puts it in the report title, in all four block headings and on the markdown table,
`--only simulated` and `--only human` split the two populations, mixing them in one
report prints a line saying so, and
`tests/test_sim.py::test_results_label_the_population` holds every one of those
strings. Every session log carries `simulated: true` and the persona.

**The next step, and it is not a formality.** PILOT.md stands as written. The
human pilot is the measurement this one was run to protect, not a confirmation of
it, and no figure from either pass should appear anywhere without the words
simulated reviewers beside it.

---

## What was deliberately not changed

The withholding rule and every refusal are exactly as they were. The reviewer
still commits before the challenge list exists, a sealed commitment still cannot be
reopened, a second commit is still refused, a finish before a commit is still
refused, a scored session still cannot be scored twice, a folder that already holds
a session still cannot be reused, and a reviewer label that could identify a person
is still refused at the API and at the command line. The approval ban still runs
over every challenge from every source. The case pack, the challenger, the matcher
and the scorer were not touched in this pass, because none of the six findings
asked for it, and changing them would have made PILOT-2-RESULTS.md a record of an
instrument that no longer exists.

## Where the two passes live

| What | Where |
|---|---|
| Pilot one's numbers, frozen | `PILOT-1-RESULTS.md` |
| Pilot one's findings and fixes | `PILOT-1-FINDINGS.md` |
| Pilot one's eighteen session logs | `sessions/pilot-1/` |
| Pilot one's prompt | `prompts/challenger.v1.md` |
| Pilot two's numbers, frozen | `PILOT-2-RESULTS.md` |
| Pilot two's findings, this file | `PILOT-2-FINDINGS.md` |
| Pilot two's eighteen session logs | `sessions/` |
| Pilot two's prompt | `prompts/challenger.v2.md` |
| Test output from both passes | `BUILD-LOG.txt` |
| The method and every limit in one place | `SIMULATION.md` |
| The human pilot, still to run | `PILOT.md` |
