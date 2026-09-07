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
| A cited amount is the named account's own movement | `challenger.deterministic_challenges()` reads it from the table; `validate_challenges()` enforces it on model output; `cases.validate_case()` enforces it on the pack | A model challenge that cites an untied figure and names no other account is dropped, with the reason in the log. A case file that does it will not load |
| Accepting without a reason is not review | Scoring requires a verdict plus a reason of at least eight words | The challenge counts as unanswered, and the defect counts as missed |
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

**Names are never recorded.** A reviewer is R1 to R99, enforced in code at the
point a session is created. Free text labels are refused, including at the API,
because a field that accepts a name eventually holds one.

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

## 4. What this tool does not do

It reviews nothing. It connects to no general ledger, no close system and no
document store. It has no opinion on whether a memo should be released. It
covers month-end flux commentary and nothing else, and the defect taxonomy comes
from twelve named failure modes rather than from a survey of practice. A firm
that wants a different scope has to write different cases, which is what the
README explains how to do.
