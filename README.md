# Second Pass

A teach-back review trainer for month-end flux commentary.

The first review a new associate performs is now a review of something a machine
wrote. It arrives fluent, formatted and confident, and it is the easiest thing in
the world to approve. Second Pass sits on that handoff. It shows a reviewer the
account movements and the draft commentary, makes them write down what they would
challenge, and only then produces its own challenge list, in which every item
cites the account line and the dollar amount so it can be recomputed. The reviewer
has to accept or reject each challenge in their own words. The tool then measures
the distance between what they thought they caught and what they caught.

It never rewrites the memo, never approves it, and never issues a conclusion.

## Results

Two pilots have run, both on 5 September 2026, and **both were run by simulated
reviewers rather than by people**: six language-model agents at three instruction
levels, each working all three cases through this code with the answer keys
withheld. No figure below is a human catch rate or a human confidence gap.

| Pass | Sessions | Catch rate unaided | Catch rate aided | Lift | Weak challenges refused |
|---|---|---|---|---|---|
| Pilot one, build v1 | 18 | 58.6% (116 of 198) | 84.3% (167 of 198) | 25.7 points | 24 of 36 |
| Pilot two, build v2 | 18 | 59.9% (115 of 192) | 95.8% (184 of 192) | 35.9 points | 49 of 54 |

Pilot one's numbers are frozen in **PILOT-1-RESULTS.md** and every finding it
produced, with the change made for it, is in **PILOT-1-FINDINGS.md**. Pilot two
ran on the rebuilt pack those changes produced, and sits in
**PILOT-2-RESULTS.md** and **PILOT-2-FINDINGS.md**. The two passes ran different
material, so read the pair as two instruments rather than as a controlled before
and after. **SIMULATION.md** holds the method, the model behind each instruction
level, and every stated limit in one place.

**The human pilot is the next step and it has not run.** The protocol is in
**PILOT.md**, and nothing in this repository stands in for it.

## What you need

Python 3.7 or later. Nothing else. No pip install, no virtual environment, no
packages, no account and no network. An API key makes the challenge list come
from a model instead of from the case file, and the tool works the same either
way.

## The commands

Run these from this folder.

```
python -m second_pass check                      # what will run here, and why
python -m second_pass cases                      # the defect pack
python -m second_pass show --case case-01-june   # print a case
python -m second_pass show --case case-01-june --key    # add the answer key
python -m second_pass serve --port 8765          # the web interface
python -m second_pass run --case case-01-june    # the same session in a terminal
python -m second_pass results --dir sessions     # aggregate a pilot
python tests/test_smoke.py                       # three cases against the key
python tests/test_withholding.py                 # the withholding rule holds
python tests/test_sim.py                         # the simulated reviewer driver
```

A reviewer can also be a language-model agent. The simulation driver puts one
through the same state machine, one command per step, writing the reviewer-safe
view and the challenge list to files instead of to a screen.

```
python -m second_pass sim start --case case-01-june --reviewer R1 \
    --dir sim/runs/R1-case-01-june --persona novice   # writes view.md
python -m second_pass sim commit --dir sim/runs/R1-case-01-june   # writes challenges.md
python -m second_pass sim finish --dir sim/runs/R1-case-01-june   # scores and logs
python -m second_pass results --dir sessions --only simulated     # or --only human
```

The reviewer writes `findings.json` between start and commit, and
`teachback.json` between commit and finish. SIMULATION.md holds the method, the
persona files, the counterbalanced case order and the exact JSON shapes, and
each command prints the full shape of the file it is waiting for.

**Two things about the shell, both learned the hard way in pilot one.**

Write `--dir` with forward slashes: `sim/runs/R1-case-01-june`. Backslashes are
escape characters in bash, so `sim\runs\R1-case-01-june` arrives at the tool as
`simrunsR1-case-01-june` and creates a folder of that name wherever you happen
to be standing. Forward slashes work in every shell on Windows, macOS and Linux.
A `--dir` that would land outside `sim/runs` is now refused before anything is
written, and `--allow-any-dir` is the way to say you meant it.

The working directory does not persist between separate shell invocations, so
every one of the three commands carries its own `--dir`, and all three carry the
same one.

For the pilot, one command is enough:

```
python -m second_pass serve --port 8765
```

That opens a browser at `http://127.0.0.1:8765/`. It binds to localhost only, so
it is reachable from that machine and nowhere else. Share the screen, or have
each reviewer run the same command on their own laptop.

Useful options, accepted before or after the subcommand:

```
--provider deterministic     ignore any key and use the built-in challenger
--cases-dir path             a different defect pack
--sessions-dir path          where session logs are written
--reviewer R3                fix the reviewer label instead of auto-assigning
--no-browser                 do not open a browser window
```

## Running without a key

This is the normal case, and nothing is degraded.

`check` reports key presence and tells you which layer will run. With no key
present, the challenge list is built by the deterministic challenger from the
case file's own answer key, using the same twelve challenge templates, the same
citation rule and the same refusal to state the answer. It also includes the
weak challenges the case author planted, so the reviewer still has to reject
something. The session log records `provider_used: deterministic`.

With `ANTHROPIC_API_KEY` set, the tool calls the Anthropic Messages API. With
`OPENAI_API_KEY` set and no Anthropic key, it calls OpenAI. Either way it sends
the prompt in `prompts/challenger.v2.md`, then checks every challenge that comes
back: the account line has to exist in the table, the amount has to be a number,
and the text must not contain approval language. Anything that fails is dropped
with the reason recorded. If nothing survives, the run falls back to the
deterministic challenger and the log says why.

Key presence is read with `os.environ` and reported as present or absent. The
value is never printed and never logged.

A simulated session uses exactly the same challenger. `sim commit` calls the same
`reveal_challenges()` gate the web route calls, so with no key present the
challenge list a model reviewer works is the deterministic one built from the
case's own answer key, weak challenges included, and with a key present it is the
one the provider returned after the same validation. Nothing about the simulation
path chooses a different AI layer, and the session log records which layer ran in
the same field either way.

## What is in the box

```
second_pass/            the package
  session.py            the state machine that enforces commit-before-reveal
  challenger.py         the AI layer, three providers, and the approval ban
  cases.py              case loading, validation, and the reviewer-safe view
  matching.py           mapping a reviewer's words onto the answer key
  scoring.py            one reviewer's numbers
  results.py            a pilot's numbers
  server.py             the local web interface
  sim.py                the simulated reviewer driver
  cli.py                the command line
  web/index.html        the single page
prompts/                the versioned prompts, and their changelog
cases/                  three cases, 32 defects, 9 weak challenges
sim/personas/           three instruction levels for a simulated reviewer
sessions/               session logs land here
tests/                  the smoke test, the withholding test, the sim test
GOVERNANCE.md           the non-delegation rule, data tiers, traceability
PILOT.md                how to run the hour
SIMULATION.md           the simulated pilot, its method and its limits
PILOT-1-RESULTS.md      pilot one's numbers, frozen
PILOT-1-FINDINGS.md     every finding from pilot one and the fix applied to it
PILOT-2-RESULTS.md      pilot two's numbers, frozen
PILOT-2-FINDINGS.md     every finding from pilot two, fixed or stated as a limit
BUILD-LOG.txt           test output from the build and from both refine steps
```

The defect pack:

| Case | Period | Accounts | Sentences | Defects | Weak challenges |
|---|---|---|---|---|---|
| case-01-june | June 2026 against May | 14 | 12 | 11 | 3 |
| case-02-july | July 2026 against June | 16 | 12 | 11 | 3 |
| case-03-august | August 2026 against July | 17 | 12 | 10 | 3 |

All twelve defect kinds appear across the pack and no two cases carry the same
set of them, so a reviewer working three cases in a row cannot pattern match by
kind. The percent-into-dollar defect is planted in one case only. The nine weak
challenges come in four shapes and no case plants a shape twice.

The three cases are consecutive months of the same invented company, so a firm
can run one cohort across a quarter. Every figure, name and sentence is
invented. Halyard Provisioning Group does not exist.

## The measurements

| Name | What it is |
|---|---|
| `catch_rate_unaided` | Defects the reviewer found on their own, over defects planted |
| `catch_rate_aided` | What they held after working the challenge list |
| `lift` | The difference, in points. Read it with the ceiling note below |
| `precision_unaided` | Findings that matched a planted defect, over all findings written. **Measured against the answer key**, and labelled that way everywhere it prints |
| `findings_outside_key` | Findings the answer key does not carry, counted on their own and listed verbatim in the log for a facilitator. They never reduce a catch rate |
| `confidence_gap_unaided` | What they said they would find, minus what they found. The headline number |
| `confidence_gap_aided` | The same measurement after the tool ran |
| `soundness_rating` | How sound they judged the memo, 1 to 5, before reading closely |
| `seconds_phase_1`, `seconds_phase_2` | Time. Recorded, reported, not led with |
| `teachback_completeness` | Challenges answered with a verdict and a real reason |
| `teachback_accuracy` | Challenges judged correctly, including weak ones refused |
| `distractors_rejected` | Weak challenges the reviewer would not accept |
| `catch_ceiling_unaided` | True where unaided catch was 90 percent or better, so only a few points of lift were available |

Every scorecard and every report prints a one-line definition of lift, the
confidence gap, teach-back accuracy and precision beside the numbers, because a
figure a reader has to look up is a figure they will guess at instead.

`results` prints per-reviewer rows as R1 to Rn, a block by instruction level
where personas are recorded, the mean of reviewer rates, and the pooled figure
with its denominator. Quote the pooled figure with the denominator beside it,
and quote the level rows with it when the levels differ, because a pooled figure
between two very different populations is a number nobody produced.

**Precision is against the key, and that is a limit rather than a verdict.** A
reviewer who raises a real problem the case author did not plant loses precision
and nothing else. That finding is counted separately, kept verbatim in the log,
and put in front of a facilitator to adjudicate. The tool does not get to call
it wrong.

## Swapping in your own memos and defect pack

This is the part a firm actually needs. A case is one JSON file in `cases/`.
Drop yours in, run `python -m second_pass cases`, and it either loads or tells
you exactly which field is wrong.

```json
{
  "schema": "second-pass/case/v1",
  "id": "case-04-september",
  "title": "September close, western region",
  "notice": "Say here that the data is invented, or say whose it is.",
  "company": { "name": "...", "fictional": true, "profile": "one or two sentences" },
  "period": { "current": "September 2026", "prior": "August 2026" },
  "materiality": { "amount": 25000, "percent": 10, "basis": "anything else about the schedule" },
  "margin_definition": "how any ratio in the commentary is computed",

  "accounts": [
    { "line": "9200", "name": "Groundskeeping contract", "prior": 152000, "current": 213300 }
  ],

  "subtotals": [
    {
      "key": "operating_expense",
      "label": "Operating expense",
      "lines": ["9200", "9250", "9280"],
      "note": "what it is and what it excludes"
    }
  ],

  "commentary": {
    "author": "who drafted it",
    "sentences": [ { "id": "S1", "text": "one sentence" } ]
  },

  "answer_key": [
    {
      "id": "D1",
      "type": "wrong_sign",
      "tag": "direction",
      "sentence": "S3",
      "line": "9200",
      "amount": 61300,
      "claim": "what the memo says",
      "correct": "what is actually true, in full, for the debrief",
      "counterparty": { "line": "9250", "note": "one clause the challenge adds after naming it" },
      "focus": { "amount": 38200, "what": "the figure the memo puts in play, in words" },
      "evidence": "what would count, if the default for this defect kind is wrong here",
      "match": {
        "aliases": ["9200", "groundskeeping contract"],
        "keywords": ["rose", "increase", "wrong direction"]
      }
    }
  ],

  "distractors": [
    {
      "id": "X1",
      "shape": "below_threshold_document",
      "tag": "threshold",
      "sentence": null,
      "line": "9280",
      "amount": 14900,
      "text": "a challenge that looks reasonable and does not hold",
      "why_wrong": "why a good reviewer rejects it"
    }
  ]
}
```

`tag`, `counterparty`, `focus`, `evidence` and `subtotals` are optional.
`shape` and `tag` are required on a distractor.

Rules the loader enforces, so that a broken case cannot quietly produce a wrong
score:

- 10 to 20 accounts, each with a unique `line`, numeric `prior` and `current`.
  **Variance and percent are computed, never stored.** A stored variance column
  can disagree with the balances beside it, and then the tool is teaching a
  defect nobody planted.
- 8 to 14 commentary sentences with unique ids.
- 8 to 12 defects. Each `type` must be one of the twelve below, and each type
  may appear only once per case, so a reviewer cannot pattern match.
- Every defect and distractor must cite a `line` that exists in the table, and
  any `sentence` it cites must exist in the commentary.
- **A defect's `amount` must be the movement of the account it names**, or it
  must carry a `focus` saying what that figure is instead. The challenge cites
  the movement either way, and the text names the focus figure out loud. This is
  the rule that keeps a challenge recomputable: a reviewer who checks the cited
  amount against the account has to find it there.
- A `counterparty` names another line in the table, never the defect's own line.
  The challenge then names that account, its own movement and its direction.
- Every subtotal's `lines` must exist in the table.
- A distractor needs a `shape` from the four below, and **no case may plant the
  same shape twice.** A `bad_recomputation` distractor must cite an amount that
  does not tie to its account, because the wrong arithmetic is the thing being
  tested; every other shape must cite the real movement.
- A distractor's `tag` must be one a defect in the same case also carries, so no
  tag ever identifies the planted weak leads.
- `company.fictional` must be `true`. If you are running your own real memos,
  read GOVERNANCE.md first, and understand that you are removing a guard rail
  the tool put there on purpose.

The twelve defect kinds:

`wrong_sign`, `wrong_period`, `unsupported_driver`, `mismatched_amount`,
`missing_driver_material`, `cutoff`, `reclass_as_growth`, `percent_as_absolute`,
`contradiction`, `immaterial_over_explained`, `rounding_flips_conclusion`,
`driver_wrong_account`.

The eight challenge tags, which a reviewer sees on every challenge:

`amount`, `direction`, `period`, `driver`, `contradiction`, `threshold`,
`classification`, `transfer`.

The four weak challenge shapes:

| Shape | What it is |
|---|---|
| `below_threshold_document` | asks for a document on a movement that fails one leg of the two-part threshold |
| `bad_recomputation` | does its own arithmetic and gets it wrong, so the table refutes it |
| `restates_correct_explanation` | asks back a question the memo already answers and the table supports |
| `wrong_period_named` | names a period the schedule does not carry, or a prior figure the table refutes |

### Writing the match block

Scoring reads free text, so each defect tells the matcher how to recognise a
reviewer who found it. A finding matches when it carries **one alias and one
keyword**, or one alias and the amount. Naming an account and nothing else does
not count.

- `aliases`: the account code, the account name, and any phrase a reviewer would
  use for the line. Add the memo's wrong figure here too, because a reviewer who
  writes "the 61,300 does not tie" has found it.
- `keywords`: the words that mean they saw what was wrong. Stems are fine, so
  `declin` covers declines, declined and declining. Keep them specific to that
  defect, and put the strongest one first, because the tests use it.

Matching is substring based with a word boundary on the left only. That is why
`up` does not match inside `unsupported` and why `declin` still matches
`declined`. Every match, and every miss, is written to the session log with the
alias and keyword that fired, so a facilitator can check the scoring rather than
trust it.

### Writing good distractors

Plant three challenges that are wrong, in three different shapes. A challenge
list a reviewer can accept wholesale teaches obedience, and a set of weak
challenges that all look alike teaches a different reflex just as bad: pilot one
planted six of them and every one was a below-threshold line with a document
request attached, so after one case the reviewers were refusing on shape rather
than on arithmetic. The catch rate on weak challenges went up and the reading
that produced it went away.

The best distractors are the ones a careful reviewer nearly accepts, and they
have to differ from each other. A movement that clears the percentage leg and
fails the dollar one. A challenge whose own subtraction is wrong by a decimal
place. A question the memo has already answered in a sentence the table
supports. A comparison against a month the schedule does not carry.

## Limits, stated plainly

It covers month-end variance commentary and nothing else. It does not touch
audit workpapers, tax positions or statutory reporting. It does not connect to a
general ledger and it never will without a different design and a different
governance answer. The defect taxonomy is twelve named failure modes, chosen
because they are the ones that survive a fluent draft, not because a survey said
so. Scoring reads free text with published rules and it will occasionally
disagree with a human reader, which is why the match trail is in the log and why
a facilitator can overrule it. The pilot numbers are small sample numbers, and
they should always be quoted with their denominator.
