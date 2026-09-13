# Governance

Second Pass is a training tool that puts an AI output in front of a human and
asks the human to defend it. That makes governance the product rather than the
paperwork around it, so every rule below is either running code or a file the
tool writes. Where a rule is only a promise, it says so.

## 1. The non-delegation rule

**The human commits first, and the tool never approves anything.**

The reviewer writes their own findings and seals them before the machine's
challenge list exists. After that the tool raises challenges, and the reviewer
accepts or rejects each one in their own words. It does not rewrite the memo, it
does not score the memo, and it does not conclude that anything is acceptable.
The only conclusion in the process belongs to the person.

How each half is enforced.

| The rule | Where it lives | What happens if it is broken |
|---|---|---|
| The reviewer commits before the AI layer runs | `second_pass/session.py`, one state machine both surfaces go through | The challenge list is not generated. `reveal_challenges()` raises, and the HTTP route answers 409 with the reason and no content |
| A sealed commitment cannot be reopened | `commit_findings()` accepts one call per session | Second commit refused, first list stands |
| The tool never approves | `challenger.contains_approval_language()`, twelve patterns, applied to every challenge and every evidence bar from every source | The challenge is dropped before a reviewer sees it, and the drop is written to the session log with the offending phrase |
| The tool never hands over the answer | Challenge templates name the problem and ask the reviewer to explain it | A reviewer who cannot explain it scores zero on that item, and does not get credit for the defect |
| A cited amount is the named account's own movement | `challenger.deterministic_challenges()` reads it from the table; `cases.validate_challenge_bindings()` enforces it on every challenge from every provider; `cases.validate_case()` enforces it on the pack | A challenge whose figure ties to neither the account it names nor the other account its text names is dropped, with the reason in the log. A case file that does it will not load |
| Every identifier a challenge binds resolves against the case | `cases.validate_challenge_bindings()`: the account is in the table, the sentence id is in the commentary, the tag is one of the eight, and every evidence reference is in the case's `sources` inventory | The challenge is dropped before a reviewer sees it, and each broken binding is named separately in the log |
| A request for evidence is not a claim that a document exists | `evidence_requested` is free prose and is never resolved; `evidence_refs` are checked against `sources` | A challenge that points at a document the case does not hold is dropped |
| Naming an account is not finding a defect | `matching.match_finding()` returns a status: supported, unsupported, or accepts the position | Only a supported finding counts as a catch. The other two go to the adjudication queue with the reviewer's words intact |
| Accepting without a reason is not review | Scoring requires a verdict plus a reason of at least eight words, and that measure is called completion | The challenge counts as unanswered, and the defect counts as missed |
| A word count never stands in for reasoning | `scoring.RUBRIC_DIMENSIONS`, three dimensions of 0 to 2, entered by a named person | The reasoning score is blank until a person signs it, and a defect credited from the disposition alone is counted in `defect_credit_pending_rubric` |
| The final outcome is the final position | `scoring.score_session()` withdraws a defect the reviewer raised unaided and then rejected under challenge | The final catch rate falls, the lift can go negative, and the original decision stays in `caught_unaided_ids` |
| A weak challenge is not identifiable except by reading it | `cases.validate_case()` refuses a repeated distractor shape in one case, and refuses a distractor tag no defect in that case carries | The case file will not load |

The last row is the one that matters most. A tool that credited a reviewer for
clicking accept would be measuring compliance and calling it judgment. The
smoke test contains a reviewer who waves the entire list through, and asserts
that they score zero.

## 2. Acceptable use, over three data tiers

The three-tier structure is adapted from the acceptable use policy the AI Native
Accounting Foundation published in its case study of Financial Optics, which
sets rules by data sensitivity tier and requires human review before anything
reaches a client. The structure is theirs and the credit is theirs. The wording
below is ours, and the tiers are defined for this tool rather than for their
practice.

Source: https://ainativeaccounting.org/casestudy-financialoptics/

### Tier 1, synthetic data. Permitted, and this is what ships.

Invented companies, invented account balances, invented commentary. The three
cases in `cases/` are tier 1 and nothing else is. Halyard Provisioning Group
does not exist, no figure in the pack came from any real company, engagement or
dataset, and every case file carries that statement in its own `notice` field.
Anyone may run the tool on tier 1 data, publish the results, and share the logs.

### Tier 2, internal non-client data. Permitted with two changes.

A firm's own budget variance memos, internal management reporting, training
material written in house. Before running tier 2 data through the tool:

1. Confirm the AI layer. With `ANTHROPIC_API_KEY` or `OPENAI_API_KEY` set, the
   case text is sent to that provider. Read that provider's data handling terms
   and confirm they meet the firm's standard, or run with
   `--provider deterministic`, which sends nothing anywhere.
2. Decide where session logs live. They contain the memo, the challenges and
   every word the reviewer wrote. Point `--sessions-dir` at a location the firm
   controls.

### Tier 3, client data and client financial data. Not permitted without written approval.

Real client trial balances, real client commentary, anything identifying a
client. This tool was not built for tier 3 and nothing in it has been assessed
for that use. Running tier 3 data through it requires the firm's own approval
under its own AI policy, its own confidentiality review, and the client's
consent where the engagement terms require one. If that approval has not been
given in writing, the answer is no.

**What the tool must never be used for.** Client data without approval, in any
tier 3 form, is the line. Also never as a control that signs anything: Second
Pass produces no conclusion, no approval and no sign-off, and no firm should
record its output as evidence that a memo was reviewed. The review is the person.

## 3. Traceability

Every session writes one JSON file to `sessions/`, named for the case, the
reviewer label and a random suffix. It holds the entire session, and it holds
enough to recompute every number without the tool.

    case_id, case_file        which memos were reviewed
    challenger                which AI layer ran, which prompt and version,
                              key presence as present or absent, every dropped
                              challenge with the reason it was dropped
    challenges                every challenge, with its account line, amount,
                              citation and text
    commitments               the reviewer's own findings, as written, sealed
    teachbacks                every verdict and every reason, timestamped
    confidence                stated before each phase, and the soundness rating
    timing                    seconds per phase
    scores                    every metric
    match_trail               for each finding, which defect it matched, which
                              alias and which keyword matched it, and why an
                              unmatched finding did not match
    findings_outside_key      findings the answer key does not carry, in the
                              reviewer's own words, kept whole for a facilitator
                              to adjudicate
    events                    an append-only list, each with a cause

The match trail exists so that a scored session can be argued with. The tool
maps a reviewer's words onto the answer key using published rules, and it shows
its working. A facilitator who disagrees with a match can say so, and the log
holds everything needed to re-score by hand. The tool does not get the last word
on a human's reasoning either.

`findings_outside_key` is the same principle applied to the other direction. A
finding that matched no planted defect is not a wrong finding; it is a finding
the answer key does not carry, and only a person can tell those two apart. So
the words go into the log intact, they are counted on their own, they are never
allowed to reduce a catch rate, and precision is labelled "against the answer
key" everywhere it prints so that nobody reads it as a judgment about the
reviewer's accounting.

**Keys are never recorded.** Key presence is read with `os.environ` and reported
as present or absent. No key value, prefix or length is written to a log, a
console line or an error message.

**Names are never recorded, and that is pseudonymity rather than anonymity.** A
reviewer is R1 to R99, enforced in code at the point a session is created. Free
text labels are refused, including at the API, because a field that accepts a
name eventually holds one. What that produces is a codename. In a live room the
facilitator can see who is at which laptop, and a reviewer can recognise their
own answers, so the honest promise is that no name is stored and only aggregate
figures are reported. Until 13 September 2026 PILOT.md promised anonymous
results and this section did not correct it. It does now, and the consent script
the facilitator reads out says the same thing in the room.

**Session files land where they were meant to land.** A simulated session writes
six files, and a `--dir` that resolves outside `sim/runs` is refused before any
of them is created. In pilot one a shell ate the separators out of a path and the
tool wrote a folder called `simrunsR6-case-02-july` at the repository root and
reported that path back as though it had been asked for. Nothing leaked and
nothing was lost, but a tool that holds a firm's memo text should not be capable
of putting it somewhere nobody chose. `--allow-any-dir` is the deliberate
override, and the refusal names both the path as typed and the path it resolved
to.

## 3a. Changing the instrument, and saying so

Second Pass is measured, so a change to it changes what the numbers mean, and
that has to be visible rather than tidy.

A prompt is a versioned file and a new version is a new file with a changelog
row, never an edit to one that has already run a session. Every session log
records the prompt id and version that produced its challenges, so a log always
points at an instruction that still exists.

The same rule now covers a pass. Pilot one's numbers are frozen in
PILOT-1-RESULTS.md, its logs are in `sessions/pilot-1/`, its reviewer working
folders are in `sim/runs/pilot-1/`, and PILOT-1-FINDINGS.md records every finding
it produced against the change made because of it. Pilot two runs against a
rebuilt case pack and prompt version 2, and it aggregates into `sessions/` on its
own. The two sets are never averaged, because a refined instrument and the
instrument that produced the case for refining it are not the same measurement,
and a pooled figure across them would hide the only thing the second pass has to
show.

## 3b. Change log

Every entry names the date, what changed, why, and what it does to a number that
was already published. A repaired metric under an unchanged name is how the
wrong number gets quoted, so a rename is listed as a rename.

### 13 September 2026, one contract in two places

The checks that had existed only in the browser, at `checker.html`, are now also
a module here, and the mechanical half of the trainer's challenge list is read
out of a run of them rather than written by hand.

| What changed | Where | Why | Effect on a number |
|---|---|---|---|
| The published contract is implemented in Python: extraction, account binding, numeric roles, units, the unrounded comparison, negation, ratios, the totals tie, the threshold policy and the four statuses | `second_pass/checker.py` | The entry claims any firm can run these checks on any ledger and any memo. A check that exists only as a paste into a web page cannot be scripted over a close, and a second implementation that drifts from the first is worse than none | No scored figure moves. The two implementations were compared field by field on all fifty-nine fixtures and agree byte for byte, run identifier and source version included |
| `secondpass check LEDGER MEMO` and `secondpass check --sample`; the old `check` is renamed `preflight` | `second_pass/cli.py` | A renamed command is listed as a rename. `preflight` reports key presence, the AI layer and the loaded cases, exactly as `check` did | Nothing computed changes. The old verb no longer does the old thing, which is why it is named here rather than aliased |
| The browser's fifty-nine fixtures run against the Python checker, and the comparison is written down | `tests/checker-fixtures.json`, `tests/test_checker_contract.py`, `CONTRACT-DIVERGENCE.md` | One suite, two implementations. A change in either place that moves a status fails the suite | No figure moves. Where the two could ever disagree the browser's contract wins, and nothing was found that needed that ruling |
| The arithmetic, direction, threshold and silence challenges are read out of a checker run instead of fired from a template at an authored defect | `second_pass/challenger.py` | The four kinds the contract settles do not need an answer key, and a trainer that cannot run without one cannot run on a firm's own close | Scoring is unchanged: a substituted challenge keeps the defect's identifier, tag and amount. Its truth block now records that the checker settled it and what the finding was |
| Driver and timing challenges stay with the authored key, and a test holds that line in both directions | `second_pass/challenger.py`, `tests/test_checker_wiring.py` | Whether a driver is real and whether a period is right are not mechanical, and a checker that took them would be asserting what it cannot know | No figure moves |
| An empty answer key is allowed and means the case is not scored; a key that exists still needs eight to twelve defects | `second_pass/cases.py` | A firm running its own close through the trainer has no key to write first | No figure moves. The three shipped cases are unaffected |
| The session log names the run behind the mechanical half: contract version, run identifier, source version, coverage counts and the policy in force | `second_pass/session.py` | A challenge list nobody can reproduce is an assertion | No figure moves. The block is produced at the moment the list is released and never before |

### 13 September 2026, external audit repairs

An external audit dated 12 September 2026 ran two offline probes against commit
`b4581c8` and found four scoring defects, a thin session export, and a set of
documents that contradicted each other. All seven repairs below are in this
commit, and the probes are now regression tests in
`tests/test_audit_repairs.py` with the intended behaviour as the assertion.

| What changed | Where | Why | Effect on a number |
|---|---|---|---|
| A finding that names an account and its movement and then accepts the commentary no longer counts as a detected defect | `second_pass/matching.py`, `second_pass/scoring.py` | The audit wrote "Account 6000 has movement 72500. I accept the commentary as written." and scored a catch, because the case author had listed the amount among the defect keywords. Matching was standing in for correctness | Catch rates can only fall. Findings that identify a line without asserting anything go to a new adjudication queue instead |
| `teachback_completeness` renamed `teachback_completion`; `teachback_accuracy` renamed `disposition_accuracy`; a separate human reasoning rubric added | `second_pass/scoring.py` | Eleven unrelated words scored full marks on a measure everyone read as reasoning quality. The word count only ever measured completion | The figures are unchanged and the names are not. The old names are gone rather than aliased. The reasoning score is new and is blank until a person scores it |
| The final catch is computed from final positions, with the original and the changed decisions kept apart | `second_pass/scoring.py`, `second_pass/results.py` | The aided catch was a union, so a defect a reviewer raised and then withdrew under challenge stayed counted and the assistance could never show as harm | A withdrawal now lowers the final rate and the lift can go negative. Logs written before today cannot report a withdrawal, and the report says so rather than printing a zero |
| Every identifier and amount binding in a challenge is validated | `second_pass/cases.py` (`validate_challenge_bindings`), `second_pass/challenger.py` | An amount of 999,999,999, a sentence id of NONEXISTENT and the evidence reference "Imaginary document page 999" all survived because the question text named a second real account | More model challenges are dropped, and each broken binding is named separately in the log |
| Requested evidence types are kept apart from actual sources, and every case declares a `sources` inventory | `second_pass/cases.py`, `cases/*.json` | A challenge may ask for a kind of evidence that does not exist yet. It may not cite a document the case does not hold | No scored figure moves. The three case files gained a `sources` block and nothing else |
| The session export is schema v2: it keeps the participant's exact copy including tag and evidence, the whole prompt, the case version, the provider's raw answer, and the minimum attempt record | `second_pass/session.py` | A log that omits what the participant saw cannot be recomputed by anyone else | No scored figure moves. Missing questions are present and null and are named in `missing`, never filled with a default |
| Documents reconciled: the human pilot has not run and no module implies otherwise; PILOT.md and SIMULATION.md agree on two scored cases; the passed pilot date is removed; a codename is called pseudonymity | `README.md`, `PILOT.md`, `SIMULATION.md`, `second_pass/scoring.py`, `second_pass/session.py`, this file | The scoring module described a measurement on real people that has never happened, and the pilot promised anonymous results a facilitator in the room cannot deliver | No figure moves. The claims around them do |

Left to a person, not decided here: whether the pilot should score two cases or
one. Both documents now describe the two-case hour that PILOT.md has always
scheduled, and the cost of it, that the second case is not a clean first
encounter, is written down beside it rather than resolved by an edit.

## 4. What this tool does not do

It reviews nothing. It connects to no general ledger, no close system and no
document store. It has no opinion on whether a memo should be released. It
covers month-end flux commentary and nothing else, and the defect taxonomy comes
from twelve named failure modes rather than from a survey of practice. A firm
that wants a different scope has to write different cases, which is what the
README explains how to do.
