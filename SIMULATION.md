# The simulated pilot

Second Pass measures the distance between what a reviewer thinks they caught and
what they caught. To measure that at all, somebody has to sit the session. The
human pilot in PILOT.md is scheduled, and the reviewers in it are people. This
document covers the runs that came first: six language-model agents, at three
instruction levels, put through the same state machine the people will go
through, on the same three cases, with the same withholding rule enforced by the
same code.

That is a different measurement from the human one, and it is written up as a
different measurement. It is here because it tests the instrument on reviewers
who can be run in parallel and repeated exactly, before an hour of five people's
evening is spent on it.

Two passes have run, both on 5 September 2026. Pilot one is frozen in
PILOT-1-RESULTS.md and everything it found is in PILOT-1-FINDINGS.md. The refine
step is between them. Pilot two is frozen in PILOT-2-RESULTS.md and everything it
found is in PILOT-2-FINDINGS.md. Neither pass is pooled into the other.

## The method

Six simulated reviewers, R1 to R6, two at each of three instruction levels. Each
runs all three cases, so the design produces eighteen sessions in a pass. Pilot
one ran over 33 planted defects and 6 planted weak challenges. The refine step
rebuilt the pack, so pilot two ran over 32 planted defects and 9 planted weak
challenges. That is why the two passes are reported as two instruments rather
than as a controlled before and after on the same memos.

The three levels are instruction files in `sim/personas/`, written to the
reviewer in the second person.

| Level | Model | The reviewer |
|---|---|---|
| `novice` | Claude Sonnet 5 | First-year associate, two months in, has never closed a month. Reads fast, treats fluent prose as correct, accepts challenges without checking the arithmetic |
| `intermediate` | Claude Sonnet 5 | One year in, three closes behind them. Recomputes the big movements, misses cutoff and reclassification |
| `experienced` | Claude Opus 5 | Senior with several dozen closes. Recomputes every cited amount and rejects the challenges that do not hold |

The model is part of the level and not a detail beneath it. The novice and
intermediate reviewers ran on Claude Sonnet 5 and the experienced reviewers on
Claude Opus 5, so a difference between the level rows is a difference of
instruction and model together. Any figure quoted by level has to be quoted with
that sentence attached to it.

Case order is counterbalanced across the six. Every case sits in every position
twice, and the two reviewers at each level run the reverse of each other's order,
so no level meets any case systematically first.

| Reviewer | Level | First | Second | Third |
|---|---|---|---|---|
| R1 | novice | case-01-june | case-02-july | case-03-august |
| R2 | novice | case-03-august | case-02-july | case-01-june |
| R3 | intermediate | case-02-july | case-03-august | case-01-june |
| R4 | intermediate | case-01-june | case-03-august | case-02-july |
| R5 | experienced | case-03-august | case-01-june | case-02-july |
| R6 | experienced | case-02-july | case-01-june | case-03-august |

Each reviewer is a separate agent holding one persona file and nothing else. The
orchestrator runs the six in parallel and never tells any of them what the
planted defects are, how many there are, or which challenges are weak.

## What the numbers measure, and what they do not

They measure the effect of the withholding rule and the cited challenge list on
language-model reviewers at three instruction levels. Within that population,
they say whether committing first and then working a cited challenge list moves
the catch rate, whether the stated confidence exceeds the actual catch rate, and
whether a weak challenge gets refused or waved through.

They do not measure anything about people. A model reviewer is not a junior
associate with an instruction file attached, and no figure in this run should be
read as a human catch rate, a human confidence gap or a human lift. Where a
number from this run appears anywhere, it appears with the words simulated
reviewers next to it, which is why `results` puts those words in its title, in
every heading and on the table rather than leaving it to whoever quotes the
output.

The measurements themselves are the ones in README.md, unchanged. Scoring is the
same function, the matcher is the same matcher, and the answer key is the same
answer key.

## How the withholding rule was enforced

The rule is that the reviewer commits their own findings before the tool shows
them anything it produced. Splitting a session across three processes is exactly
the kind of change that quietly breaks a rule like that, so here is where it
holds.

**`sim start` never writes the key.** `view.md` is built from
`cases.reviewer_view()`, the same function the web page and the terminal runner
call, which strips the answer key and the distractors. The defect count is not in
it either, because the web page does not show that at the Read step. The test
searches `view.md` for the first forty characters of every planted defect's claim
and correction and every weak challenge's text, and finds none of it.

**The challenge list is generated after the seal, not before.** At `sim start`
the challenge list does not exist. It is produced inside `sim commit`, after
`commit_findings()` has returned, by the same `reveal_challenges()` gate the web
route goes through. The test asserts that `challenges.md` and `truth.json` are
absent on disk after start, and that `state.json` carries no challenges.

**A second commit is refused.** The commitment is sealed once. A reviewer cannot
commit, read the challenge list, and then improve their own findings, and the
test proves the sealed findings and the released challenge list are both
unchanged after the refusal.

**Nothing in `challenges.md` says which challenges are weak.** The file is
rendered from `challenger.public_challenges()`, which drops the truth block. The
weak challenges are in the list, unmarked, in the same shape as the rest.

**The truth blocks and the state file are facilitator files.** Scoring needs the
truth blocks back at `sim finish`, so they are written to `truth.json` in the
session folder. Each persona names `truth.json` and `state.json` alongside the
cases folder, the answer key, the prompts folder and the tests as files the
reviewer never opens, and the reviewer's own instructions say it opens `view.md`
and `challenges.md` and nothing else.

**The score block withholds the key.** A person finishing a session sees the
answer key on the debrief screen, and that is right, because their session is
over. A simulated reviewer runs three cases, so `sim finish` prints the metrics
without the key and a facilitator gets it with `--debrief` or with
`show --case <id> --key`.

## Pilot one findings and the refine step

Pilot one ran on 5 September 2026 and is finished. Its numbers are frozen in
**PILOT-1-RESULTS.md**, its eighteen session logs sit in `sessions/pilot-1/`,
its eighteen reviewer working folders sit in `sim/runs/pilot-1/`, and the prompt
that produced its challenges is kept as `prompts/challenger.v1.md`.

The six reviewers reported ten findings about the instrument. Every one of them
was acted on the same night, and **PILOT-1-FINDINGS.md** lists each finding, the
change made because of it, and the file and test the change lives in. The
headline four:

- Challenges cited amounts that did not tie to the account they named, six times
  across the pack. A challenge now cites the movement of the account it names,
  and where the point is the other side of an entry it names that account, its
  own movement and its direction, in words.
- Every weak challenge in pilot one had the same shape, so after one case the
  reviewers could refuse them without arithmetic. Weak challenges now come in
  four shapes and no case plants a shape twice.
- Defect kinds sat in the same slots in all three cases. The pack was rebuilt:
  kinds, key order and accounts all rotate, no two cases carry the same set of
  kinds, and the percent-into-dollar defect is planted in one case only.
- Precision punished a reviewer for finding a real problem the answer key did not
  carry. Findings outside the key are now counted on their own, kept verbatim in
  the log for a facilitator, and never reduce a catch rate.

**Pilot two aggregates separately.** `sessions/` is empty of pilot one, so
`results --dir sessions` reports pilot two alone and
`results --dir sessions/pilot-1` still reproduces pilot one exactly. The two are
not mixed, because the instrument that produced the case for refining is not the
refined instrument, and averaging them would hide the only thing this pass has
to show: whether the refinement moved anything.

That sequence is the sponsor's own, in the sponsor's own words. This pass is the
refine step, recorded as one, with the before, the findings and the after each in
its own file.

## Pilot two results and the refine step

Pilot two ran on 5 September 2026 against the rebuilt pack and
`prompts/challenger.v2.md`, with the same six reviewers, the same three
instruction levels and the same counterbalanced order. Its numbers are frozen in
**PILOT-2-RESULTS.md** and its eighteen session logs sit in `sessions/`.

**Every figure below was produced by simulated reviewers, not by people.**

| Measurement | Pilot one | Pilot two |
|---|---|---|
| Catch rate, unaided | 58.6% (116 of 198) | 59.9% (115 of 192) |
| Catch rate, aided | 84.3% (167 of 198) | 95.8% (184 of 192) |
| Lift | 25.7 points | 35.9 points |
| Confidence gap, unaided | 7.0 points | 5.5 points |
| Confidence gap, aided | -18.6 points | -30.5 points |
| Teach-back accuracy | 79.2% | 94.4% |
| Weak challenges refused | 24 of 36 | 49 of 54 |

By instruction level, pooled, pilot two:

| Level | Model | Unaided | Aided | Lift | Weak refused |
|---|---|---|---|---|---|
| novice | Claude Sonnet 5 | 40.6% (26 of 64) | 95.3% (61 of 64) | 54.7 | 15 of 18 |
| intermediate | Claude Sonnet 5 | 50.0% (32 of 64) | 93.8% (60 of 64) | 43.8 | 18 of 18 |
| experienced | Claude Opus 5 | 89.1% (57 of 64) | 98.4% (63 of 64) | 9.3 | 16 of 18 |

The model column is not a footnote. The novice and intermediate reviewers ran on
Claude Sonnet 5 and the experienced reviewers on Claude Opus 5, so a difference
between two level rows is a difference of instruction and model together, and
that sentence travels with any figure quoted by level.

The refinement moved the aided phase and left the unaided phase where it was,
which is what a fixed challenge list should do. Unaided catch went from 58.6 to
59.9 percent, which is noise across two different packs. Aided catch went from
84.3 to 95.8 percent, weak challenge refusals went from 24 of 36 to 49 of 54, and
teach-back accuracy went from 79.2 to 94.4 percent. The intermediate level is
where it shows most plainly, from a 12.1 point lift to a 43.8 point one, because
pilot one's intermediates were working around a challenge list whose cited amounts
did not tie to the accounts they named.

Pilot two's own reviewers reported six findings. One was a defect and it was
fixed the same night: the JSON example printed by `sim start` and `sim commit`
was written from case-01-june and reproduced two of its planted defects and the
correct reject for one of its weak challenges, so a reviewer starting on that case
was handed three answers by the tool that exists to withhold them. The example is
now invented, the invented accounts and figures appear in no case file, and
`tests/test_sim.py::test_the_printed_schema_example_leaks_no_case` walks the pack
in both directions to hold it. The other five findings are limits rather than
defects, they are printed below and in **PILOT-2-FINDINGS.md**, and none of them
was argued away.

## The known limits

**A model may already know these defects.** Wrong sign, wrong period, cutoff and
reclassification are named failure modes that appear in accounting training
material, so a model reviewer may recognise them from training rather than from
reading the memo. A person does not have that advantage, and the simulated catch
rates are inflated by an unknown amount because of it.

**The personas are instructions, not skill.** Telling a model to read fast and
trust fluent prose produces a reviewer that says it read fast. It does not
produce a first-year associate. The three levels separate the numbers, and that
separation is evidence about instruction sensitivity rather than about seniority.

**Confidence is stated after the work, not before.** A person answers the
confidence question on the screen that shows the memo and before writing
anything. A model agent writes its confidence in the same file as its findings,
which means it answers after it has worked. That makes the simulated confidence
gap a weaker claim than a human one, not a stronger one.

**Six reviewers is six reviewers.** Every figure is quoted with its denominator,
the pooled rate is quoted beside the mean of the rates, and nothing here is
extrapolated to a population.

**Weak challenges are still sortable by shape, and the tell moved rather than
went.** Pilot one planted every weak challenge in one shape and pilot two plants
four, which took refusals from 24 of 36 to 49 of 54. Pilot two's reviewers then
named the new tell: twelve of the 32 real challenges carry a line reading
"What would count as evidence", and none of the nine weak ones does. That marks
twelve challenges as real for free. It marks nothing as weak, because twenty real
challenges carry no evidence line either, so twenty-nine challenges still have to
be sorted on the arithmetic. The evidence line stays, because it is the answer to
pilot one's finding 9 and removing it would pay for the measurement with the thing
the tool is for. The refusal rate should therefore be read as partial, and a
facilitator should read the reject reasons in the logs to see whether they cite
arithmetic or shape.

**Precision against the answer key still marks down real findings.** A reviewer
who raises a real problem the case author did not plant loses precision for it.
Pilot two logged seventeen findings outside the key, six of which matched no
planted weak lead either. Those are counted on their own, kept verbatim in the
session log, never allowed to touch a catch rate, and labelled "against the answer
key" wherever the figure prints. Labelling it correctly does not make it a measure
of review quality, and the six unadjudicated findings are a facilitator's job
rather than the scorer's.

**Nine of the twelve defect kinds appear in all three cases.** The refine step
rotated the kinds, the key order and the accounts, and made sure no two cases carry
the same set. Only three kinds actually vary: percent as absolute is in July alone,
mismatched amount is in June and July, and rounding flips conclusion is in June and
August. Ten to twelve defects per case over three cases needs 32 slots out of a
taxonomy of twelve, so the overlap is arithmetic rather than carelessness, but it
means a reviewer working three cases back to back meets most failure modes three
times and the third case is not a clean first encounter. PILOT.md runs two scored
cases per reviewer, counterbalanced, so only the first of the two is a clean first
encounter and the write-up has to say which case each reviewer opened first. A
facilitator who wants a clean encounter on every case runs one case per reviewer
and accepts fewer observations for it. This paragraph claimed until 13 September
2026 that the human pilot ran a single case, which PILOT.md has never said.

**The lift at the senior level is small because seniors start near the ceiling.**
The experienced level came in at 89.1 percent unaided, which leaves 10.9 points of
lift available in total, and the aided phase captured 9.3 of them. Four of the six
experienced sessions were at or above 90 percent unaided on their own and two were
at 100 percent, where no lift is arithmetically possible. Any quotation of the
pooled 35.9 point lift has to carry the level spread with it, because a pooled
figure across three levels this far apart is a number no reviewer produced.

**The human pilot is the next step, not a formality.** PILOT.md stands as
written. This run tests the instrument; it does not stand in for the people.

## Reproducing it

From this folder, with no API key required. One reviewer, one case, three
commands and two files the reviewer writes.

```
python -m second_pass sim start --case case-01-june --reviewer R1 \
    --dir sim/runs/R1-case-01-june --persona novice
# the reviewer reads sim/runs/R1-case-01-june/view.md
# the reviewer writes sim/runs/R1-case-01-june/findings.json
python -m second_pass sim commit --dir sim/runs/R1-case-01-june
# the reviewer reads sim/runs/R1-case-01-june/challenges.md
# the reviewer writes sim/runs/R1-case-01-june/teachback.json
python -m second_pass sim finish --dir sim/runs/R1-case-01-june
```

`findings.json`, written by the reviewer after reading `view.md` and before the
challenge list exists. `soundness`, from 1 to 5, is optional and feeds the memo
soundness figure. `confidence` is measured against one thing: the share of the
planted defects in this memo the reviewer believes they have caught. Each
command prints this whole shape and these rules at the step that asks for the
file, so a reviewer never has to come here for it.

```json
{
  "findings": [
    "Account 9200 groundskeeping contract rose $61,300 and sentence S3 says it fell",
    "Account 9250 waste removal moved $38,200 with no driver anywhere in the memo"
  ],
  "confidence": 65,
  "soundness": 3
}
```

Accounts 9200, 9250 and 9280 do not exist. They were invented for these examples
after pilot two found the old ones were real, and a test walks the pack to prove
none of them, and none of their figures, is in any case.

`teachback.json`, written after reading `challenges.md`. One entry per challenge,
a verdict of `accept` or `reject`, and a reason in the reviewer's own words. A
reason under eight words does not count as a teach-back, and a verdict without
one earns no credit for the defect behind it. Refusing a weak challenge with a
reason scores exactly as highly as accepting a real one. An optional `findings`
list holds anything the challenge list did not raise that the reviewer still
wants to challenge; a finding there that the answer key does not carry is
counted on its own, listed verbatim in the session log for a facilitator, and
never reduces a catch rate.

```json
{
  "responses": [
    {
      "id": "C3",
      "verdict": "accept",
      "reason": "Account 9200 groundskeeping contract rose $61,300 and sentence S3 has it falling, so the memo states the direction backwards."
    },
    {
      "id": "C4",
      "verdict": "reject",
      "reason": "Account 9280 site security moved $14,900, which fails the dollar leg of the threshold, so no driver is required and this challenge does not hold."
    }
  ],
  "confidence": 80
}
```

Run all eighteen sessions, then aggregate.

```
python -m second_pass results --dir sessions --markdown --only simulated
```

The session logs land in `sessions/` in the same shape as a real session, with
`simulated: true` and the persona added. `--only human` gives the same report for
the people when PILOT.md runs, and mixing the two in one report prints a line
saying so.

Two tests cover this path.

```
python tests/test_sim.py
python tests/test_withholding.py
```
