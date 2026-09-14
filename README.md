# Second Pass

Second Pass checks month-end flux commentary before a person reads it, and it
trains the person who has to sign it.

The first review a new associate performs is now a review of something a machine
wrote. It arrives fluent, formatted and confident, and it is the easiest thing in
the world to approve. Two things sit on that handoff here. The **checker** takes
a ledger and a drafted memo and does the mechanical work: it recomputes every
ledger line, ties each figure it can read to the line the sentence names, and
returns a status for each sentence and a short queue of questions only a person
can answer. Whatever it cannot read goes into that queue rather than being passed. The **trainer** puts a reviewer through the same memo, makes them commit
their own findings first, and then measures the distance between what they
thought they caught and what they caught.

Neither one rewrites a memo, approves a memo, or issues a conclusion. A reviewer
signs.

The checker also runs in a browser, at
[checker.html](https://fiscalpatriots.github.io/beat-the-machine/checker.html),
one HTML file with no libraries. That page and this package implement one
contract and run the same 546 fixtures, and on those 546 inputs they agree on
every field compared in [CONTRACT-DIVERGENCE.md](CONTRACT-DIVERGENCE.md). The
checks read a ledger in one of the layouts `CHECKER.md` accepts, a sentence
carrying anything the grammar cannot read comes back not checked rather than
cleared, and a sentence that leaves a word from the clearance grammar's risk
lexicon once its claims are read comes back needs review.

## The contract, in one paragraph

Every figure the grammar reads is read with the span of text it came from, its
value and its unit, and dollars, percent and percentage points are held apart.
Any other quantitative language, a multiplier, a fraction, a scale word or a
digit outside 0 to 9, is recorded as an unparsed span and leaves the sentence
not checked. Each
sentence is bound to a ledger line by the account number written in it, by the
account name written in it, or by an exact figure where the sentence also carries
a word from that account's name that no other named account shares; a figure that
ties to a line the sentence never names is a coincidence and is printed as an
unresolved conflict rather than bound. What the sentence says each figure *is*, a
prior balance, a current balance, an absolute movement, a relative movement or a
ratio, is read from the words beside it and never from the fact that it matches
something, and a figure whose role the words do not give is never counted as
checked whatever it happens to equal. Every comparison is unrounded, to half a
cent on a dollar and five hundredths of a point on a percent. A negation voids
the claim in the clause it attaches to rather than being read as its opposite.
A sentence ends on exactly one of four statuses, **checked within scope**, **needs
review**, **not checked** or **failed**, and no later step may move one upward.
The full contract, with every boundary and every exclusion, is in
[CHECKER.md](https://github.com/fiscalpatriots/beat-the-machine/blob/main/CHECKER.md).

**"Checked within scope" does not mean the sentence is true.** It means every
quantitative expression in the sentence was accounted for, and each figure
carried a role the words gave it and the unrounded comparison with the pasted
ledger agreed. Whether the driver is real and whether the period is right
are not mechanical questions, and the checker puts both of them to a person.

## Install and run

Python 3.7 or later. No pip install, no virtual environment, no packages, no
account and no network.

```
git clone https://github.com/fiscalpatriots/second-pass.git
cd second-pass
python -m second_pass check --sample halyard
python -m second_pass check my-ledger.tsv my-memo.txt
python -m pytest tests -q
```

## The command line

```
python -m second_pass check LEDGER MEMO [options]
python -m second_pass check --sample halyard|brightwater|kestrel|ridgeline
```

| Option | What it does |
| --- | --- |
| `--dollar 25000` | the dollar floor. The rule is **more than** the floor |
| `--percent 10` | the percent floor. The rule is **at least** the floor |
| `--rule both` or `either` | both legs must clear, or one is enough |
| `--zero-prior owe` or `exclude` | a line with no prior balance owes commentary on any movement, or is out of the rule |
| `--ratios FILE` | ratio definitions, one per line, `Name = (4000 - 5000) / 4000` |
| `--format table` `csv` `json` `prompt` | the table, the CSV export, the machine-readable record, or the reviewer prompt |
| `--period` `--memo-version` `--company` `--reviewer` | free text that rides into every export, so a filed log says which close it came from |
| `--fail-on-findings` | exit 1 when a sentence failed or a line is silent, for a build step |

### A bundled case

```
$ python -m second_pass check --sample halyard
```

```
12 sentences read · 4 checked within scope · 5 needs review · 0 not checked · 3 failed ·
14 ledger rows used · 0 rows skipped · 1 silent line · 13 in the reviewer queue.
```

### Your own ledger and your own memo

Two files. The ledger takes an account number, a name, a prior balance and a
current balance, separated by tabs, commas or two or more spaces. It also reads a
QuickBooks Online Profit and Loss Comparison and a Xero Income Statement as they
come out, sections, totals and all.

```
$ python -m second_pass check ledger.tsv memo.txt --ratios ratios.txt --period "June 2026"
```

```
2 sentences read · 2 checked within scope · 0 needs review · 0 not checked · 0 failed ·
3 ledger rows used · 0 rows skipped · 1 silent line · 1 in the reviewer queue.
```

### The findings, sentence by sentence

The table under the coverage line carries one row per check, with the finding
under it and one imperative beside it.

```
FAIL  5210   1. Dental supplies and lab f Direction              FAIL
      the memo says "eased" but 5210 Dental supplies and lab fees rose $52,700 (38.1%).
      -> Send it back to the preparer.
```

```
FAIL  6200   5. 6200 Software licences an Figure $25,300         DOLLARS, ROLE ABSOLUTE MOVEMENT
      memo says $25,300 as the absolute movement; the absolute movement on 6200 Software licences
      and hosting is $35,300. Nearest ledger figure: prior balance on 6200 Software licences and
      hosting is $22,600.
      -> Send it back to the preparer.
```

### The queue, which is what a person actually works

```
$ python -m second_pass check --sample ridgeline
```

```
 3. [Silent line] 6700 — Insurance
      change $52,000, 118.2%, clears the rule and no sentence in the memo explains it
      Question: What drove 6700 Insurance this month, and what supports it?
      Owner: Controller.   Yes / No / Not on file: ______
```

### The exports

`--format csv` writes one row per finding, in the column order the browser
writes, and any cell beginning with `=`, `+`, `-` or `@` is written with a
leading apostrophe so a spreadsheet reads an account named `=1+1` as text.

```
$ python -m second_pass check --sample ridgeline --format csv | head -2
```

```
"run id","run timestamp","close period","reviewed memo version","source version","evidence id",…
"run-1-ugbylm","2026-09-13T10:56:46.890Z","July 2026","Ridgeline test memo","src-ugbylm-485",…
```

`--format json` writes the same run with every cell exactly as it was typed,
plus the roles, the units, the text spans, the policy in force and the queue.

```
$ python -m second_pass check --sample ridgeline --format json | head -4
```

```json
{
  "runId": "run-1-ugbylm",
  "runAt": "2026-09-13T10:56:47.175Z",
  "sourceVersion": "src-ugbylm-485",
```

`--format prompt` writes the reviewer prompt for the run: the rule as set with
both boundary words spelled out, the coverage counts, the sources actually
supplied and nothing else, every unresolved item verbatim, and then the
sentences that were checked within scope with the two judgment questions.

## One suite, two implementations

The browser and this package are held to the same file. `tests/checker-fixtures.json`
is the suite that guards `checker.html`, and the copy here is the same file once
line endings are normalized, which a test here checks. The end-to-end samples
`T18` (halyard-v4) and `T18b` (brightwater-v5) run on the same case versions in
both repositories, as [CONTRACT-DIVERGENCE.md](CONTRACT-DIVERGENCE.md) records.

```
node tests/run-checker-tests.cjs                          # in the beat-the-machine repository
python -m pytest tests/test_parity_shared_inputs.py -q    # here, both on one input set
```

546 fixtures. Fifty-nine of them run `T01` to `T54`, five with a lettered second
case: seventeen probes from the external audit of 13 September 2026, twenty-four
from the live release review of the same day, the end-to-end sample runs, and
probes written against the repaired contract afterwards. `P01` to `P40` are the
forty probes from the third independent review of 13 September 2026, and the
other 113 are mutations of the six classes that review showed were open:
multipliers, no-change claims, fractions and number words, digits outside 0 to 9,
numbers that are not figures, and the Prompt 1 line shape. `A001` to `A139` and
`B001` to `B036` are the 175 probes of the independent audit of 13 September 2026,
and the last 159 are mutations of the clearance grammar's classes: currencies, signs,
sameness, periods and bases, claims carried to another account, "respectively", and
words that size, rank or share a movement. Each one carries the required behavior
as its own assertion, so a change in either place that moves a status fails the
suite. `python -m pytest tests/ -q` runs 1,173 tests in this repository with
beat-the-machine beside it, the parity test among them; without it, 625 pass and
the 548 that need the browser are skipped.

The two were also compared field by field, not only on the clauses the fixtures
assert: `tests/test_parity_shared_inputs.py` runs all 546 inputs through the page
under Node and through this package, and compares the statuses, roles, coverage
counts, the queue, the findings, the reviewer list, the CSV, the table export, the
JSON record and the reviewer prompt, with timestamps masked and the JSON compared
as objects. They agree on every compared field for those 546 inputs, which is not
a proof that they agree on an input nobody has added yet.
[CONTRACT-DIVERGENCE.md](CONTRACT-DIVERGENCE.md) records the method, the result,
what the comparison found and fixed on the way, and the page behaviors that have
no command-line meaning so their absence is not read as a divergence. Where the two could ever disagree, the browser's contract
wins.

The four bundled cases in `cases/shared/` are lifted verbatim from the page, and
`cases/shared/definitions/` holds the upstream case files two of them are
generated from, so the checker, the page and the game read the same ledger and
the same memo version rather than three drifting copies.

## Running it on every memo

The checker is deterministic, offline and fast, so it belongs in front of the
reviewer rather than beside them. A firm scripts it the way it scripts any other
gate.

```bash
for close in closes/*/; do
  python -m second_pass check "$close/ledger.tsv" "$close/memo.txt" \
      --period "$(basename "$close")" \
      --company "Western region" \
      --memo-version "AI draft, first pass" \
      --format csv > "$close/second-pass.csv"
done
```

`--fail-on-findings` exits 1 when a sentence failed or a line clears the rule with
no commentary, which is enough to stop a pipeline:

```bash
python -m second_pass check ledger.tsv memo.txt --fail-on-findings || echo "back to the preparer"
```

Three things worth saying to whoever owns that pipeline. The CSV is the evidence
the review protocol asks for, one row per finding with the run identifier and the
source version on every row. The JSON record is what to keep if anything later
has to be recomputed, because the CSV's spreadsheet neutralisation alters a cell
and the JSON does not. And a run that comes back clean is not a memo that is fit
to release, because the queue is where the judgment sits and the queue is never
empty of the two questions a person owes.

Editing any input invalidates the run. The source version is a hash of the ledger,
the memo, the ratios, both floors, the rule, the zero prior balance policy and the
close period, so two runs carrying the same source version were computed from the
same inputs and two that differ were not.

## The trainer

The other half of the repository puts a person through the memo before the tool
speaks. It shows the account movements and the draft commentary, makes the
reviewer write down what they would challenge, seals it, and only then produces a
challenge list in which every item cites the account line and the dollar amount so
it can be recomputed. The reviewer accepts or rejects each one in their own words.
Some of the challenges do not hold, and rejecting a weak one with a reason scores
exactly as highly as accepting a good one.

```
python -m second_pass preflight                  # which AI layer will run here, and why
python -m second_pass cases                      # the defect pack
python -m second_pass show --case case-01-june   # print a case
python -m second_pass serve --port 8765          # the web interface, localhost only
python -m second_pass run --case case-01-june    # the same session in a terminal
python -m second_pass results --dir sessions     # aggregate a pilot
```

**The mechanical challenges come out of the checker.** Four kinds are settled by
the contract without a person and without an answer key: a figure that does not
agree with the line it is written about, a direction word that disagrees with the
sign of the movement, a claim about the commentary rule that the rule refutes, and
a line that clears the rule with no sentence about it. Those are read out of a run
of `second_pass.checker` over the case's own ledger and its own commentary. On all
three cases it rediscovers every planted wrong sign and every silent line with the
answer key never consulted. Whether a driver is real and whether the period is
right are not mechanical, and those challenges still come from the authored key.
The session log names the run that produced the list, with its contract version,
its run identifier, its source version and the policy in force, so the mechanical
half can be reproduced without rerunning anything.

A case with no answer key now produces a challenge list of its own, which is what
lets the trainer run on a memo nobody wrote a key for.

A reviewer can also be a language-model agent. The simulation driver puts one
through the same state machine, one command per step, writing the reviewer-safe
view and the challenge list to files instead of to a screen. **SIMULATION.md** holds
the method, the persona files, the counterbalanced case order and the exact JSON
shapes, and each command prints the full shape of the file it is waiting for.

```
python -m second_pass sim start --case case-01-june --reviewer R1 \
    --dir sim/runs/R1-case-01-june --persona novice   # writes view.md
python -m second_pass sim commit --dir sim/runs/R1-case-01-june   # writes challenges.md
python -m second_pass sim finish --dir sim/runs/R1-case-01-june   # scores and logs
```

Write `--dir` with forward slashes. Backslashes are escape characters in bash, so
`sim\runs\R1` arrives as `simrunsR1` and creates a folder of that name wherever
you happen to be standing. A `--dir` that would land outside `sim/runs` is refused
before anything is written, and `--allow-any-dir` is the way to say you meant it.

### Running the trainer without a key

This is the normal case and nothing is degraded. With no key present, the
challenge list is built by the deterministic challenger: the mechanical half from
the checker run, the judgment half from the case file's own answer key, with the
same citation rule and the same refusal to state the answer, plus the weak
challenges the case author planted so the reviewer still has to reject something.
The session log records `provider_used: deterministic`.

With `ANTHROPIC_API_KEY` set, the tool calls the Anthropic Messages API, and with
`OPENAI_API_KEY` set and no Anthropic key it calls OpenAI. Either way it sends the
prompt in `prompts/challenger.v2.md` and then checks every challenge that comes
back: the account has to exist in the table, the amount has to be that account's
own movement or another account the text names, the sentence identifier has to be
in the commentary, every evidence reference has to be a document the case declares,
and the text must not contain approval language. Anything that fails is dropped
with the reason recorded, and if nothing survives the run falls back to the
deterministic challenger and the log says why. Key presence is read with
`os.environ` and reported as present or absent; the value is never printed and
never logged.

### The pilot results

Two pilots have run, both on 5 September 2026, and **both were run by simulated
reviewers rather than by people**: six language-model agents at three instruction
levels, each working all three cases through this code with the answer keys
withheld. No figure below is a human catch rate or a human confidence gap.

| Pass | Sessions | Catch rate unaided | Catch rate aided | Lift | Weak challenges refused |
|---|---|---|---|---|---|
| Pilot one, build v1 | 18 | 58.6% (116 of 198) | 84.3% (167 of 198) | 25.7 points | 24 of 36 |
| Pilot two, build v2 | 18 | 59.9% (115 of 192) | 95.8% (184 of 192) | 35.9 points | 49 of 54 |

Pilot one's numbers are frozen in **PILOT-1-RESULTS.md** and every finding it
produced, with the change made for it, is in **PILOT-1-FINDINGS.md**. Pilot two ran
on the rebuilt pack those changes produced and sits in **PILOT-2-RESULTS.md** and
**PILOT-2-FINDINGS.md**. The two passes ran different material, so read the pair as
two instruments rather than as a controlled before and after.

**The human pilot is the next step and it has not run.** The protocol is in
**PILOT.md**: two scored cases per reviewer, counterbalanced, about five reviewers,
no date until a room is confirmed. Nothing in this repository stands in for it.
Reviewers work under a codename, which is pseudonymity rather than anonymity.

### The measurements

| Name | What it is |
|---|---|
| `catch_rate_unaided` | Defects the reviewer found on their own, over defects planted |
| `catch_rate_aided` | What they held after working the challenge list, computed from final positions, so a withdrawal lowers it |
| `lift` | The difference, in points. Read it with the ceiling note |
| `precision_unaided` | Findings that matched a planted defect, over all findings written. Measured against the answer key, and labelled that way everywhere it prints |
| `findings_outside_key` | Findings the answer key does not carry, counted on their own and listed verbatim for a facilitator. They never reduce a catch rate |
| `confidence_gap_unaided` | What they said they would find, minus what they found. The headline number |
| `confidence_gap_aided` | The same measurement after the tool ran |
| `soundness_rating` | How sound they judged the memo, 1 to 5, before reading closely |
| `seconds_phase_1`, `seconds_phase_2` | Time. Recorded, reported, not led with |
| `teachback_completion` | Challenges answered with a verdict and a reason long enough to count. It measures completion and says nothing about quality |
| `disposition_accuracy` | Of the challenges judged, the share whose verdict was right, weak ones refused included |
| `reasoning_score` | Three dimensions scored 0 to 2 by a named person. Blank until someone scores it |
| `distractors_rejected` | Weak challenges the reviewer would not accept |
| `catch_ceiling_unaided` | True where unaided catch was 90 percent or better, so only a few points of lift were available |

Every scorecard prints a one-line definition of lift, the confidence gap,
disposition accuracy and precision beside the numbers, because a figure a reader
has to look up is a figure they will guess at instead.

**Precision is against the key, and that is a limit rather than a verdict.** A
reviewer who raises a real problem the case author did not plant loses precision
and nothing else. That finding is counted separately, kept verbatim in the log,
and put in front of a facilitator to adjudicate. The tool does not get to call it
wrong.

## Your own memos and your own defect pack

A case is one JSON file in `cases/`. Drop yours in, run `python -m second_pass
cases`, and it either loads or tells you exactly which field is wrong. The
checker needs nothing but the `accounts` block, the `commentary` block and
`materiality`, so a case whose `answer_key` is empty still loads and still
produces a mechanical challenge list. An empty key means the case is not scored;
a key that exists is a scored pack and still has to carry between eight and
twelve defects.

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

  "sources": [
    { "id": "SRC-GL", "name": "general ledger detail", "kind": "ledger_detail" },
    { "id": "SRC-CONTRACT", "name": "groundskeeping contract and rate schedule",
      "kind": "contract", "lines": ["9200"] }
  ],

  "accounts": [
    { "line": "9200", "name": "Groundskeeping contract", "prior": 152000, "current": 213300 }
  ],

  "commentary": {
    "sentences": [
      { "id": "S1", "text": "Groundskeeping rose $61,300 on the new rate schedule." }
    ]
  },

  "answer_key": [ { "id": "D1", "type": "unsupported_driver", "line": "9200", "sentence": "S1",
                    "claim": "...", "correct": "...", "match": { "aliases": [], "keywords": [] } } ],
  "distractors": [ { "id": "W1", "line": "9200", "shape": "below_threshold_document",
                     "text": "...", "why_wrong": "..." } ]
}
```

Twelve defect kinds are recognised, and the four the checker settles on its own
are `mismatched_amount`, `wrong_sign`, `immaterial_over_explained` and
`missing_driver_material`. The rest are judgment calls the key still carries. The
loader validates every identifier, every amount and every evidence reference
against the case itself, so a challenge that cites a document the case does not
hold is refused before a reviewer ever sees it.

## Governance

The non-delegation rule, the data tiers, the traceability requirements and the
change log are in [GOVERNANCE.md](GOVERNANCE.md). Every entry in that change log
names the date, what changed, why, and what it does to a number that was already
published, because a repaired metric under an unchanged name is how the wrong
number gets quoted.

The review protocol a person works from, the evidence log it fills in and the
facilitator's guide for running it with a room are in the
[beat-the-machine](https://github.com/fiscalpatriots/beat-the-machine) repository,
beside the browser checker and the training game:
[PROTOCOL.md](https://github.com/fiscalpatriots/beat-the-machine/blob/main/PROTOCOL.md),
[EVIDENCE-LOG-TEMPLATE.csv](https://github.com/fiscalpatriots/beat-the-machine/blob/main/EVIDENCE-LOG-TEMPLATE.csv)
and
[GOVERNANCE-NOTE.md](https://github.com/fiscalpatriots/beat-the-machine/blob/main/GOVERNANCE-NOTE.md).
The CSV this package writes is the evidence that protocol asks for.

## Versioning

The package version is in `second_pass/__init__.py` and prints with
`python -m second_pass --version`. Three other version strings matter more than
it does, and all three ride in every export:

| String | Where it lives | What it pins |
| --- | --- | --- |
| `CONTRACT_VERSION` | `second_pass/checker.py` | which published contract this implementation is of |
| source version, `src-…` | computed per run | the exact inputs a run was computed from |
| case version | the case file, and `cases/shared/*.json` | which version of a case a filed log came from |

The session log carries `schema: second-pass/session/v2`, and a schema change is
a rename in the change log rather than a quiet repair. Prompts are versioned in
`prompts/` with their own changelog.

## What it does not do

It reviews nothing, and it never says a memo is fit to release.

The checker carries no judgment on drivers and none on timing, because whether a
depot ramp is real is a question about contracts and shipping dates rather than
about balances. It does not detect a contradiction: two sentences that cannot both
be true can both be checked within scope, and it says only that they landed on the
same account and must be read together. It does not work out what a negation
asserts; it detects one and refuses the clause. It reads one currency, written in
whole units with a dollar sign, so `€30,000`, `USD 90000`, `$30.0 thousand` and
`30 basis points` are recorded as unparsed and the sentence is left unchecked. It
does no fuzzy matching, so "depot" does not match "depots", and a sentence that
names nothing the ledger names comes back unmatched on purpose. It rebuilds a
`Total …` row standing under a section of lines and leaves Gross Profit, Net
Operating Income, Net Income and Net Profit alone.

The trainer covers month-end flux commentary and nothing else. It does not touch
audit workpapers, tax positions or statutory reporting. It connects to no general
ledger, no close system and no document store, and it will not without a different
design and a different governance answer. The defect taxonomy is twelve named
failure modes, chosen because they survive a fluent draft rather than because a
survey said so. Scoring reads free text with published rules and will occasionally
disagree with a human reader, which is why the match trail is in the log and why a
facilitator can overrule it. The pilot numbers are small sample numbers and should
always be quoted with their denominator.

---

Built by Khaled Alkurd. Every figure, name and sentence in the case pack is
invented. Halyard Provisioning Group does not exist.
