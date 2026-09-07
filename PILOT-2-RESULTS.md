# Pilot two, the simulated run of 5 September 2026

This file is the frozen record of the second pass, the one that ran on the
refined instrument. It is the output of

```
python -m second_pass results --dir sessions --only simulated --markdown
```

run from this folder on the eighteen session logs in `sessions/`, after every
pilot one finding had been acted on. Pilot one's logs were moved into
`sessions/pilot-1/` before this pass opened, so `sessions/` holds pilot two and
nothing else and the same command reproduces this file exactly.

**Every session below was run by a simulated reviewer, not by a person.** No
figure here is a human catch rate, a human confidence gap or a human lift. The
limits of that claim are in SIMULATION.md, and pilot two's own reviewers added to
that list rather than removing anything from it. PILOT-2-FINDINGS.md carries what
they reported and what was done about each item.

## Who ran it

| Reviewer | Level | Model |
|---|---|---|
| R1 | novice | Claude Sonnet 5 |
| R2 | novice | Claude Sonnet 5 |
| R3 | intermediate | Claude Sonnet 5 |
| R4 | intermediate | Claude Sonnet 5 |
| R5 | experienced | Claude Opus 5 |
| R6 | experienced | Claude Opus 5 |

Six agents, two at each of three instruction levels, each holding one persona
file from `sim/personas/` and nothing else. The novice and intermediate levels
ran on Claude Sonnet 5 and the experienced level on Claude Opus 5, so a
difference between the level rows below is a difference of instruction and model
together rather than of instruction alone. That sentence has to travel with any
figure quoted by level.

## The counterbalanced order

Every case sits in every position twice, and the two reviewers at each level run
the reverse of each other's order, so no level meets any case systematically
first. The order below was read back out of the eighteen session logs rather than
from the plan.

| Reviewer | Level | First | Second | Third |
|---|---|---|---|---|
| R1 | novice | case-01-june | case-02-july | case-03-august |
| R2 | novice | case-03-august | case-02-july | case-01-june |
| R3 | intermediate | case-02-july | case-03-august | case-01-june |
| R4 | intermediate | case-01-june | case-03-august | case-02-july |
| R5 | experienced | case-03-august | case-01-june | case-02-july |
| R6 | experienced | case-02-july | case-01-june | case-03-august |

Eighteen sessions over 32 planted defects and 9 planted weak challenges per pass,
against the rebuilt pack and `prompts/challenger.v2.md`. The AI layer was the
deterministic challenger throughout, so every challenge list came from each
case's own answer key with no key and no network in the loop.

## By instruction level

Pooled, every defect over every defect shown. The confidence gaps are the mean of
the session gaps.

| Level | Sessions | Unaided | Aided | Lift | Gap unaided | Gap aided | Weak refused |
|---|---|---|---|---|---|---|---|
| novice | 6 | 40.6% (26 of 64) | 95.3% (61 of 64) | 54.7 | 18.6 | -36.1 | 15 of 18 |
| intermediate | 6 | 50.0% (32 of 64) | 93.8% (60 of 64) | 43.8 | 8.3 | -35.8 | 18 of 18 |
| experienced | 6 | 89.1% (57 of 64) | 98.4% (63 of 64) | 9.3 | -10.4 | -19.6 | 16 of 18 |
| **All eighteen** | 18 | 59.9% (115 of 192) | 95.8% (184 of 192) | 35.9 | 5.5 | -30.5 | 49 of 54 |

Teach-back accuracy over the eighteen sessions is 94.4 percent and teach-back
completeness is 100 percent. Seventeen findings fell outside the answer key, six
of which matched no planted weak lead either and are listed verbatim in the
session logs for a facilitator to adjudicate. None of them reduced a catch rate.

The experienced row still carries the ceiling. An unaided rate of 89.1 percent
leaves under eleven points of lift on the table, so the 9.3 points the aided
phase produced there is most of what was available rather than a weak result, and
`results` prints a ceiling note beside any unaided rate at or above 90 percent.

## What moved between the two passes, and the caution that goes with it

The two passes did not run the same material. Pilot one worked 33 planted defects
in six weak-challenge slots and pilot two worked 32 in nine, because the refine
step rebuilt the pack so that kinds, key order and accounts rotate. This is a
comparison between two instruments, not a controlled before-and-after on the same
memos, and it should be quoted that way.

| Measurement | Pilot one | Pilot two |
|---|---|---|
| Catch rate, unaided | 58.6% (116 of 198) | 59.9% (115 of 192) |
| Catch rate, aided | 84.3% (167 of 198) | 95.8% (184 of 192) |
| Lift | 25.7 points | 35.9 points |
| Confidence gap, unaided | 7.0 points | 5.5 points |
| Confidence gap, aided | -18.6 points | -30.5 points |
| Teach-back accuracy | 79.2% | 94.4% |
| Weak challenges refused | 24 of 36 | 49 of 54 |
| Precision, against the key | 86.9% | 88.9% |
| Memo soundness, 1 to 5 | 1.9 | 3 |
| Lift at the intermediate level | 12.1 points | 43.8 points |

The intermediate row is where the refine step shows most plainly. Pilot one's
intermediates finished the aided phase at 63.6 percent, which is a challenge list
they were largely working around, and pilot two's finished at 93.8 percent
against a list whose every cited amount ties to the account it names.

## The output, verbatim

Everything below is the command's own output on 5 September 2026, unedited.

```
Second Pass pilot results, simulated reviewers
==============================================

Sessions: 18 over 6 simulated reviewer(s), cases case-01-june, case-02-july, case-03-august. AI layer: deterministic.
Every session in this set was run by a simulated reviewer, not by a person.

Reviewer Persona       Case            Defects Unaided Aided  Lift   Precision Conf  Gap    Teach  Sec 1  Sec 2  
-----------------------------------------------------------------------------------------------------------------
R1       novice        case-01-june    11      27.3%   100.0% 72.7   60.0%     60.0% 32.7   100.0% 226    261    
R1       novice        case-02-july    11      45.5%   100.0% 54.5   83.3%     65.0% 19.5   100.0% 104    90     
R1       novice        case-03-august  10      40.0%   100.0% 60.0   100.0%    55.0% 15.0   100.0% 100    117    
R2       novice        case-01-june    11      36.4%   90.9%  54.5   80.0%     60.0% 23.6   100.0% 94     57     
R2       novice        case-02-july    11      54.5%   90.9%  36.4   100.0%    60.0% 5.5    100.0% 92     75     
R2       novice        case-03-august  10      40.0%   90.0%  50.0   100.0%    55.0% 15.0   100.0% 188    141    
R3       intermediate  case-01-june    11      63.6%   90.9%  27.3   87.5%     65.0% 1.4    100.0% 118    94     
R3       intermediate  case-02-july    11      54.5%   90.9%  36.4   100.0%    60.0% 5.5    100.0% 150    243    
R3       intermediate  case-03-august  10      40.0%   100.0% 60.0   100.0%    50.0% 10.0   100.0% 116    114    
R4       intermediate  case-01-june    11      54.5%   100.0% 45.5   85.7%     60.0% 5.5    100.0% 173    179    
R4       intermediate  case-02-july    11      45.5%   90.9%  45.4   100.0%    55.0% 9.5    100.0% 129    121    
R4       intermediate  case-03-august  10      40.0%   90.0%  50.0   100.0%    58.0% 18.0   100.0% 127    127    
R5       experienced   case-01-june    11      72.7%   100.0% 27.3   72.7%     78.0% 5.3    100.0% 70     67     
R5       experienced   case-02-july    11      90.9%   90.9%  0.0    90.9%     80.0% -10.9  100.0% 68     63     
R5       experienced   case-03-august  10      90.0%   100.0% 10.0   75.0%     75.0% -15.0  100.0% 105    61     
R6       experienced   case-01-june    11      81.8%   100.0% 18.2   90.0%     80.0% -1.8   100.0% 61     67     
R6       experienced   case-02-july    11      100.0%  100.0% 0.0    91.7%     75.0% -25.0  100.0% 69     55     
R6       experienced   case-03-august  10      100.0%  100.0% 0.0    83.3%     85.0% -15.0  100.0% 82     50     

By instruction level, pooled
Level           Sessions  Unaided   Aided    Lift    Gap unaided   Gap aided    Weak refused
--------------------------------------------------------------------------------------------
novice          6         40.6%     95.3%    54.7    18.6          -36.1        15 of 18
intermediate    6         50.0%     93.8%    43.8    8.3           -35.8        18 of 18
experienced     6         89.1%     98.4%    9.3     -10.4         -19.6        16 of 18

Pooled over simulated reviewers, every defect over every defect shown
  Catch rate unaided        59.9%   (115 of 192)
  Catch rate aided          95.8%   (184 of 192)
  Lift                      35.9 points

Mean of simulated reviewer rates
  Catch rate unaided        59.8%
  Catch rate aided          95.9%
  Lift                      36.0 points
  Precision against the key 88.9%
  Findings outside the key  17, of which 6 matched no planted weak lead and await facilitator adjudication

Confidence against accuracy over simulated reviewers, the headline measurement
  Stated expectation        65.3%
  Actual, unaided           59.8%
  Gap, unaided              5.5 points
  Gap, aided                -30.5 points
  Memo soundness, 1 to 5    3

Teach-back and time over simulated reviewers
  Completeness              100.0%
  Accuracy                  94.4%
  Weak challenges refused   49 of 54
  Mean seconds, phase 1     115.1
  Mean seconds, phase 2     110.1

What the numbers are
  Lift: aided catch rate minus unaided catch rate, in points. It is what the challenge list added to what the reviewer already had.
  Confidence gap: the share of the planted defects the reviewer said they would find, minus the share they actually found. Positive means they believed they caught more than they caught.
  Teach-back accuracy: of the challenges judged, the share judged correctly. Accepting a real challenge with a reason of at least eight words counts, and so does refusing a weak one with a reason.
  Precision, against the answer key: findings that matched a planted defect over all findings written. Findings outside the key are counted separately and never reduce a catch rate.

**Simulated reviewers.** Every session in this set was run by a simulated reviewer, not by a person.

| Reviewer | Persona | Case | Defects | Caught unaided | Caught aided | Confidence stated | Gap |
|---|---|---|---|---|---|---|---|
| R1 | novice | case-01-june | 11 | 3 (27.3%) | 11 (100.0%) | 60.0% | 32.7 |
| R1 | novice | case-02-july | 11 | 5 (45.5%) | 11 (100.0%) | 65.0% | 19.5 |
| R1 | novice | case-03-august | 10 | 4 (40.0%) | 10 (100.0%) | 55.0% | 15.0 |
| R2 | novice | case-01-june | 11 | 4 (36.4%) | 10 (90.9%) | 60.0% | 23.6 |
| R2 | novice | case-02-july | 11 | 6 (54.5%) | 10 (90.9%) | 60.0% | 5.5 |
| R2 | novice | case-03-august | 10 | 4 (40.0%) | 9 (90.0%) | 55.0% | 15.0 |
| R3 | intermediate | case-01-june | 11 | 7 (63.6%) | 10 (90.9%) | 65.0% | 1.4 |
| R3 | intermediate | case-02-july | 11 | 6 (54.5%) | 10 (90.9%) | 60.0% | 5.5 |
| R3 | intermediate | case-03-august | 10 | 4 (40.0%) | 10 (100.0%) | 50.0% | 10.0 |
| R4 | intermediate | case-01-june | 11 | 6 (54.5%) | 11 (100.0%) | 60.0% | 5.5 |
| R4 | intermediate | case-02-july | 11 | 5 (45.5%) | 10 (90.9%) | 55.0% | 9.5 |
| R4 | intermediate | case-03-august | 10 | 4 (40.0%) | 9 (90.0%) | 58.0% | 18.0 |
| R5 | experienced | case-01-june | 11 | 8 (72.7%) | 11 (100.0%) | 78.0% | 5.3 |
| R5 | experienced | case-02-july | 11 | 10 (90.9%) | 10 (90.9%) | 80.0% | -10.9 |
| R5 | experienced | case-03-august | 10 | 9 (90.0%) | 10 (100.0%) | 75.0% | -15.0 |
| R6 | experienced | case-01-june | 11 | 9 (81.8%) | 11 (100.0%) | 80.0% | -1.8 |
| R6 | experienced | case-02-july | 11 | 11 (100.0%) | 11 (100.0%) | 75.0% | -25.0 |
| R6 | experienced | case-03-august | 10 | 10 (100.0%) | 10 (100.0%) | 85.0% | -15.0 |
| **Pooled, simulated reviewers** | 3 persona(s) | 18 session(s) | 192 | 115 (59.9%) | 184 (95.8%) | 65.3% | 5.5 |

By instruction level, pooled. Catch rates are every defect over every defect shown; the confidence gaps are the mean of the session gaps.

| Level | Sessions | Unaided | Aided | Lift | Gap unaided | Gap aided | Weak challenges refused |
|---|---|---|---|---|---|---|---|
| novice | 6 | 40.6% (26 of 64) | 95.3% (61 of 64) | 54.7 | 18.6 | -36.1 | 15 of 18 |
| intermediate | 6 | 50.0% (32 of 64) | 93.8% (60 of 64) | 43.8 | 8.3 | -35.8 | 18 of 18 |
| experienced | 6 | 89.1% (57 of 64) | 98.4% (63 of 64) | 9.3 | -10.4 | -19.6 | 16 of 18 |

Lift: aided catch rate minus unaided catch rate, in points. It is what the challenge list added to what the reviewer already had.

Confidence gap: the share of the planted defects the reviewer said they would find, minus the share they actually found. Positive means they believed they caught more than they caught.

Teach-back accuracy: of the challenges judged, the share judged correctly. Accepting a real challenge with a reason of at least eight words counts, and so does refusing a weak one with a reason.

Precision, against the answer key: findings that matched a planted defect over all findings written. Findings outside the key are counted separately and never reduce a catch rate.
```
