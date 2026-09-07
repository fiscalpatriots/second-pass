# Pilot one findings, and what was done about each one

The sponsor's rubric is measurable outcomes, governance and replicability, and
its own four words for the method are pilot, measure, refine, replicate. Pilot
one ran on 5 September 2026: six simulated reviewers, three instruction levels,
eighteen sessions, 198 planted defects worked. The numbers it produced are
frozen in PILOT-1-RESULTS.md and the logs behind them are in `sessions/pilot-1/`.

This file is the refine step. It lists every finding the six reviewers reported,
what was changed because of it, and where the change lives, so that the claim
"we refined it" can be checked line by line rather than believed.

Ten findings came back. Ten were acted on. Nothing was deferred and nothing was
argued away. Where a fix went further than the finding asked, the extra is
stated as extra.

---

## 1. Cited amounts did not tie to the account they named

**What the reviewers found.** July C7 cited $98,900 against warehouse wages,
which moved $79,400. July C9 cited $38,000 against service revenue, which moved
$55,000. June C10 cited $65,000 against product revenue, which is account 4200's
movement, not 4000's. June and August both labelled gross profit, $1,334,000 and
$1,293,000, as the movement on cost of product sold. August C5 and C8 both cited
account 7300 at $185,000, and one July list cited account 6000 twice with two
different amounts. Every one of these is a transfer-style challenge attaching the
other side's figure to the named account with no signal that it had done so.

**Why it mattered more than the arithmetic.** A tool whose whole instruction is
"recompute this" cannot be wrong about the figure it hands over. A reviewer who
recomputes the named account, finds the cited figure absent, and is right to be
suspicious learns that recomputing is a waste of time. That is the opposite of
the behaviour the instrument exists to build.

**The fix.** A challenge now cites the movement of the account it names, read
from the table rather than from the answer key, on every path.

- `second_pass/challenger.py`, `deterministic_challenges()` computes the cited
  amount from `account_movements()`. The answer key's own `amount` is no longer
  the cited figure; it stays as the pedagogical figure the matcher recognises.
- Where the point of a defect is the other side of an entry, the case file
  carries a `counterparty` and the challenge text names that account, its own
  movement and its direction. The June transfer now reads: "Account 4000 Product
  revenue, distribution moved $372,000, and Sentence S4 presents that as an
  operating change. ... Account 4200 Freight billed to customers moved $65,000
  in the opposite direction."
- Where the memo puts a figure in play that is not the account's own movement,
  the case file carries a `focus` and the challenge says so out loud. The June
  cutoff now reads: "The account moved $5,200 in total. ... The memo puts
  $19,400 in play as June fuel invoices the memo defers into July, which is
  larger than the movement recorded on the account." That reads better than the
  old version did, because the mismatch is the point.
- `cases.validate_case()` refuses a case file whose defect amount is neither the
  account's movement nor a declared `focus`, and refuses a counterparty line
  that is not in the table.
- The model path enforces the same rule. `validate_challenges()` drops a
  challenge whose amount does not tie to the named account unless the text names
  another account from the table, and the drop is recorded in the session log
  with its reason, alongside the approval-language drops.
- `tests/test_smoke.py::test_every_cited_amount_ties_to_the_named_account` walks
  all 41 challenges in the pack.
  `test_a_counterparty_is_named_in_words_not_just_implied` asserts that every
  counterparty appears in the text by line and by its own movement.

**Beyond the finding.** The citation line now reads "movement $73,800" rather
than "$73,800", and a nil movement prints as `$0` instead of being dropped, so a
challenge on a line that did not move still carries a figure to check.

---

## 2. Templates fired without checking whether they fitted

**What the reviewers found.** A challenge asked which of two numbers was a
percentage against a sentence that had already labelled its percentage. A
transfer challenge asked for the other side of a figure that was itself the other
side.

**The fix.** `_choose_template()` in `second_pass/challenger.py` picks a variant
after reading the sentence it is aimed at.

- `percent_as_absolute` has two forms. Where `_percent_is_labelled()` finds the
  word percent in the sentence, the challenge instead says the sentence states a
  percentage and then restates the same movement as a dollar figure, gives the
  account's real movement, and asks where the memo's figure came from.
- `reclass_as_growth` has two forms. With a counterparty declared, it stops
  asking the reviewer to identify the other side and asks instead how much of
  the movement is the transfer and what is left once it comes out.
- Prompt v2 carries the same instruction as rule 7, so a model challenger reads
  the sentence before firing at it.
- `tests/test_smoke.py::test_a_template_that_does_not_fit_its_sentence_is_not_used`.

---

## 3. Weak challenges were identifiable by shape

**What the reviewers found.** In all three cases the weak challenges were a line
below the $25,000-and-10-percent test followed by a document request. After one
case a reviewer could score refusals without doing any arithmetic. July C10 was
the only counterexample and it should be the pattern.

**The fix.** Weak challenges now come in four named shapes, and no case plants
the same shape twice.

| Shape | What it is |
|---|---|
| `below_threshold_document` | asks for a document on a movement that fails one leg of the two-part threshold |
| `bad_recomputation` | does its own arithmetic on the account and gets it wrong, so the table refutes it |
| `restates_correct_explanation` | asks back, as a question, an explanation the memo already gives and the table supports |
| `wrong_period_named` | names a period the schedule does not carry, or states a prior figure the table refutes |

The count went from two weak challenges per case to three, so each case carries
three different shapes and the pack uses all four.

| Case | Shapes planted |
|---|---|
| case-01-june | below_threshold_document, bad_recomputation, restates_correct_explanation |
| case-02-july | wrong_period_named, restates_correct_explanation, bad_recomputation |
| case-03-august | below_threshold_document, wrong_period_named, restates_correct_explanation |

`cases.validate_case()` refuses a case that repeats a shape, and
`tests/test_smoke.py::test_no_case_plants_two_weak_challenges_of_the_same_shape`
asserts it for the pack. A `bad_recomputation` weak challenge is the one
sanctioned exception to the citation rule in finding 1, and the validator
requires its amount to differ from the real movement, so a case cannot claim that
shape and then cite the correct figure.

---

## 4. Defect kinds repeated in the same slots

**What the reviewers found.** A direction reversal, a percent-into-dollar
mix-up, a same-account contradiction, a missing write-up on a big asterisked line
and a margin claim that fails on recompute appeared in the same positions in all
three cases, so by the third case reviewers were pattern-matching rather than
reading. The percent-into-dollar defect should appear in at most one case.

**The fix.** The three cases were rebuilt. Halyard Provisioning Group is
unchanged, June, July and August still chain, and the tie-across between months
is intact.

- Ten to twelve defects per case, and all twelve kinds across the pack:
  eleven in June, eleven in July, ten in August.
- No two cases carry the same set of kinds. June omits `percent_as_absolute`,
  July omits `rounding_flips_conclusion`, August omits `percent_as_absolute` and
  `mismatched_amount`.
- `percent_as_absolute` is now in July only, and it sits on bad debt expense
  rather than on interest, so the 28.2-to-$28,200 shape is not repeated either.
- The key order rotates. June opens on a missing driver, July on a
  percent-into-dollar and August on a margin claim; no key slot holds the same
  kind in all three cases.
- Accounts rotate with the kinds. The direction reversal moves from inbound
  freight to fleet fuel to service revenue. The over-explained immaterial line
  moves from software subscriptions to depot utilities to bad debt. The missing
  write-up moves from warehouse wages to inventory shrink to supplier rebates.
  The contradiction moves off the repairs programme in August and onto the legal
  accrual. The margin claim is no longer the last sentence of the memo in both
  cases that carry one.
- `tests/test_smoke.py::test_defect_kinds_and_slots_rotate_across_the_pack`.

---

## 5. The materiality rule read as AND-or-OR, and ratio tests needed hand arithmetic

**What the reviewers found.** "Exceeds $25,000 and 10 percent" could be read
either way. And a memo claim about an expense ratio could not be checked without
adding seven lines by hand.

**The fix.**

- `cases.materiality_rule()` is now the single wording every surface prints:
  "Commentary is required only where a movement passes BOTH tests: more than
  $25,000 AND at least 10 percent of the prior balance. Both, not either. A line
  that clears one test and fails the other does not require commentary." It
  appears above the table and again immediately beneath it, on the web page, in
  the terminal runner, in `view.md` and in the prompt sent to a model.
- The asterisk legend changed from "over the commentary threshold" to "passes
  both legs of the threshold".
- Each case now declares `subtotals`, computed by `cases.subtotal_table()` from
  the same balances: a revenue total and an operating expense subtotal, each
  with the lines that make it up and a one-line note. They render in `view.md`,
  the web page, the terminal and the model prompt.
- Each case now carries lines that deliberately pass one leg and fail the other,
  so the rule is exercised rather than only stated. June's interest expense
  clears both; June's inventory shrink is 39 percent and $2,500 and clears
  neither test that matters.

---

## 6. Precision punished real work

**What the reviewers found.** Findings that were real accounting problems and
were not in the answer key scored as "matched nothing": a rebate presentation
that flipped the margin conclusion, a capitalisation question against a flat
depreciation charge, shrink sitting outside the margin definition. A reviewer
could raise their score by writing fewer and narrower findings, which is exactly
the wrong reflex to train.

**The fix.**

- Findings outside the key are counted on their own:
  `findings_outside_key`, split into `findings_outside_key_matched_weak` and
  `findings_outside_key_unadjudicated`.
- They are listed verbatim in the session log under `findings_outside_key`, with
  the reviewer's own words kept whole, for a facilitator to adjudicate. The tool
  does not file them as wrong; it says they are outside the key and stops.
- Precision is labelled "against the answer key" wherever it prints, and
  `precision_basis` carries that string in the scores block.
- An out-of-key finding has never touched a catch rate and now there is a test
  that says so:
  `tests/test_smoke.py::test_precision_is_against_the_key_and_out_of_key_findings_are_counted_apart`.

---

## 7. "Lift 0.0 points" read as the aided phase being worthless

**What the reviewers found.** The experienced reviewers were at 89.4 percent
unaided, so there were at most 4.5 points of lift available to them, and a lift
near zero read as a phase that did nothing. The measurements also wanted
definitions beside them rather than in a manual.

**The fix.**

- `scoring.CEILING_PERCENT` is 90. Any unaided catch rate at or above it prints
  a ceiling note naming the rate and the points of lift that were available, on
  the scorecard, in the pooled block and on any instruction level that hits it.
  `catch_ceiling_unaided` is in the scores block for anyone re-computing.
- `scoring.DEFINITIONS` holds one line each for lift, confidence gap, teach-back
  accuracy and precision, printed under "What the numbers are" at the foot of
  every scorecard and every results report, and in the markdown export.
- `results` also gained a by-instruction-level block, pooled, in both the text
  and the markdown output. Pilot one's levels ran from 34.8 percent to 89.4
  percent unaided, and the pooled figure of 58.6 percent is a number no reviewer
  produced. A facilitator quoting one figure should see the spread it came from.
- `tests/test_smoke.py::test_a_ceiling_note_prints_when_unaided_catch_is_at_the_top`.

---

## 8. The printed schema was incomplete

**What the reviewers found.** The schema printed by `sim start` and `sim commit`
left out the `soundness` field and never stated the rule that a teach-back reason
under eight words scores zero. Nobody said what confidence was measured against.

**The fix.** `sim.FINDINGS_SCHEMA`, `sim.FINDINGS_RULES`, `sim.TEACHBACK_SCHEMA`
and `sim.TEACHBACK_RULES` hold the whole thing, and the command line prints them
in full at the step that asks for each file.

- The findings schema shows `findings`, `confidence` and `soundness` with a
  worked example, and the rules say what each one is and what range it takes.
- The teach-back schema shows `responses`, the optional `findings` list and
  `confidence`, with one accept and one reject example.
- The rules state the eight-word floor and what it costs: a verdict without a
  real reason is not review, it is a click, and it earns no credit for the
  defect. They also say that refusing a weak challenge with a reason scores
  exactly as highly as accepting a real one.
- Confidence is defined at both steps, in the same words: the share of the
  planted defects in this memo that you believe you have caught. Not how
  confident you feel, and not how sound the memo is.
- `tests/test_sim.py::test_the_printed_prompts_carry_the_whole_schema_and_the_rules`
  captures both commands' output and asserts every field and both rules.

---

## 9. Challenges carried no category, and evidence asks had no bar

**What the reviewers found.** A one-word tag would let a reviewer know what kind
of test to run before reading the sentence. And a challenge that says "name a
driver" has to say what would count as sufficient evidence.

**The fix.**

- Eight tags: amount, direction, period, driver, contradiction, threshold,
  classification, transfer. `cases.DEFAULT_TAG_BY_TYPE` maps each defect kind to
  one and a case may override it. The tag appears in every citation line, on the
  web page, in `challenges.md` and in the terminal.
- The tag never reveals weakness. `cases.validate_case()` refuses a weak
  challenge whose tag no defect in the same case carries, so no tag is ever a
  tell. `tests/test_smoke.py::test_every_challenge_carries_a_tag_that_does_not_reveal_weakness`
  asserts the subset relation for every case.
- `_EVIDENCE_BY_TYPE` gives every driver, missing-driver, wrong-account and
  transfer challenge an evidence bar that names the artefact rather than the
  adjective: a volume or unit schedule, a customer or channel split, a rate
  change with its effective date, a signed contract, the journal entries posted
  in the month, the recharge schedule showing both sides. Each says what does not
  count, and a management assertion restated in a second sentence does not.
  A case may override the bar per defect.
- The evidence bar renders as its own line, "What would count as evidence: ...",
  and it goes through the same approval-language check the question does.
- Prompt v2 asks a model for both the tag and the evidence field, and rejects a
  tag outside the eight by replacing it rather than dropping the challenge,
  because a good challenge with a bad label is still a good challenge.

---

## 10. A `--dir` argument was eaten by the shell

**What the reviewers found.** In bash, `--dir sim\runs\R6-case-02-july` lost its
backslashes to the shell's escape rules, the tool created
`simrunsR6-case-02-july` at the folder root, and then echoed the mangled path
back as though that were what had been asked for. Separately, the working
directory does not persist between shell invocations, so every command has to
carry its own folder.

**The fix.**

- `sim.check_dir()` runs before anything is created. A `--dir` that resolves
  outside `sim/runs` is refused, and `--allow-any-dir` is the deliberate escape
  hatch. It is wired into all three sim commands.
- The refusal echoes the path as typed and the path it resolved to, names the
  root it has to sit inside, explains the escape hatch, and repeats the note
  that the working directory does not persist between shell invocations.
- Where the folder name looks like the pilot one accident, the refusal adds the
  specific explanation: backslashes are escape characters in bash, so
  `sim\runs\R1-case-01-june` arrives as `simrunsR1-case-01-june`, and forward
  slashes work everywhere.
- `commit` and `finish` also check the folder exists and say what to run first if
  it does not.
- README.md documents forward slashes and the non-persisting working directory
  in the simulation section.
- `tests/test_sim.py::test_a_dir_outside_sim_runs_is_refused`.

---

## What was deliberately not changed

The withholding rule and every refusal are exactly as they were. The reviewer
still commits before the challenge list exists, a sealed commitment still cannot
be reopened, a second commit is still refused, a finish before a commit is still
refused, a scored session still cannot be scored twice, a folder that already
holds a session still cannot be reused, and a reviewer label that could identify
a person is still refused at the API and at the command line. The approval ban
still runs over every challenge from every source. `tests/test_withholding.py`
and `tests/test_sim.py` prove all of it and neither of their refusal tests was
touched, except to add `--allow-any-dir` where they write into a temporary
folder.

## Where pilot one lives now

| What | Where |
|---|---|
| The numbers, frozen | `PILOT-1-RESULTS.md` |
| The eighteen session logs | `sessions/pilot-1/` |
| The eighteen reviewer working folders | `sim/runs/pilot-1/` |
| The prompt that produced its challenges | `prompts/challenger.v1.md` |

Pilot two aggregates on its own, into `sessions/`, against the rebuilt pack and
`prompts/challenger.v2.md`. The two are never mixed, because a refined
instrument and the instrument that produced the case for refining it are not the
same measurement.
