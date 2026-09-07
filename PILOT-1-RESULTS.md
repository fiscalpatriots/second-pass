# Pilot one, the simulated run of 5 September 2026

This file is the frozen record of the first pass. It is the output of

```
python -m second_pass results --dir sessions --only simulated --markdown
```

run on the eighteen session logs written that night, before any of the pilot one
findings were acted on. The logs it aggregates now sit in `sessions/pilot-1/`,
so that pilot two aggregates on its own and neither run is quietly mixed into
the other. To reproduce this table exactly:

```
python -m second_pass results --dir sessions/pilot-1 --only simulated --markdown
```

**Every session below was run by a simulated reviewer, not by a person.** No
figure here is a human catch rate, a human confidence gap or a human lift. The
limits of that claim are in SIMULATION.md and they have not moved.

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
ran on Claude Sonnet 5 and the experienced level on Claude Opus 5, so the level
separation in the numbers below is a separation of instruction and model
together rather than of instruction alone. That is stated here because it
changes what the level rows are evidence of.

## The counterbalanced order

Every case sits in every position twice, and the two reviewers at each level run
the reverse of each other's order, so no level meets any case systematically
first.

| Reviewer | Level | First | Second | Third |
|---|---|---|---|---|
| R1 | novice | case-01-june | case-02-july | case-03-august |
| R2 | novice | case-03-august | case-02-july | case-01-june |
| R3 | intermediate | case-02-july | case-03-august | case-01-june |
| R4 | intermediate | case-01-june | case-03-august | case-02-july |
| R5 | experienced | case-03-august | case-01-june | case-02-july |
| R6 | experienced | case-02-july | case-01-june | case-03-august |

Eighteen sessions over 33 planted defects and 6 planted weak challenges per
pass. The AI layer was the deterministic challenger throughout, so the challenge
list every reviewer worked came from each case's own answer key with no key and
no network in the loop.

## By instruction level

Computed from the same eighteen logs. The catch rates are pooled, every defect
over every defect shown; the confidence gaps are the mean of the session gaps.
This block did not exist when the report below was printed. It was one of the
things pilot one asked for, so `results` now prints it, and running the command
at the top of this file against `sessions/pilot-1` reproduces exactly this table
along with everything in the verbatim section.

| Level | Sessions | Unaided | Aided | Lift | Gap unaided | Gap aided | Weak refused |
|---|---|---|---|---|---|---|---|
| novice | 6 | 34.8% (23 of 66) | 95.5% (63 of 66) | 60.7 | 21.3 | -38.9 | 8 of 12 |
| intermediate | 6 | 51.5% (34 of 66) | 63.6% (42 of 66) | 12.1 | 6.4 | -5.7 | 9 of 12 |
| experienced | 6 | 89.4% (59 of 66) | 93.9% (62 of 66) | 4.5 | -6.8 | -11.2 | 7 of 12 |
| **All eighteen** | 18 | 58.6% (116 of 198) | 84.3% (167 of 198) | 25.7 | 7.0 | -18.6 | 24 of 36 |

The experienced rows are the reason finding 7 exists. An unaided catch rate of
89.4 percent leaves four and a half points of headroom, so a lift near zero is
what a ceiling looks like rather than a phase that did no work. Pilot two prints
a ceiling note beside any unaided rate at or above 90 percent.

The weak challenge column is the reason finding 3 exists. Twenty-four refusals
out of thirty-six is not a reviewer reading each challenge on its merits; it is
a reviewer learning after one case that a challenge shaped like "line below the
threshold, go obtain a document" is the planted one. Pilot two plants the weak
challenges in four shapes and never repeats a shape inside a case.

## The output, verbatim

Everything below is the command's own output on 5 September 2026, unedited.

```
Second Pass pilot results, simulated reviewers
==============================================

Sessions: 18 over 6 simulated reviewer(s), cases case-01-june, case-02-july, case-03-august. AI layer: deterministic.
Every session in this set was run by a simulated reviewer, not by a person.

Reviewer Persona       Case            Defects Unaided Aided  Lift   Precision Conf  Gap    Teach  Sec 1  Sec 2  
-----------------------------------------------------------------------------------------------------------------
R1       novice        case-01-june    10      40.0%   100.0% 60.0   100.0%    60.0% 20.0   100.0% 144    156    
R1       novice        case-02-july    11      27.3%   90.9%  63.6   100.0%    55.0% 27.7   100.0% 93     134    
R1       novice        case-03-august  12      16.7%   100.0% 83.3   66.7%     55.0% 38.3   100.0% 100    78     
R2       novice        case-01-june    10      50.0%   100.0% 50.0   100.0%    60.0% 10.0   100.0% 73     78     
R2       novice        case-02-july    11      36.4%   90.9%  54.5   80.0%     55.0% 18.6   100.0% 88     88     
R2       novice        case-03-august  12      41.7%   91.7%  50.0   100.0%    55.0% 13.3   100.0% 157    124    
R3       intermediate  case-01-june    10      70.0%   80.0%  10.0   100.0%    62.0% -8.0   100.0% 102    48     
R3       intermediate  case-02-july    11      45.5%   54.5%  9.0    71.4%     60.0% 14.5   100.0% 223    165    
R3       intermediate  case-03-august  12      41.7%   58.3%  16.6   83.3%     55.0% 13.3   100.0% 144    96     
R4       intermediate  case-01-june    10      60.0%   80.0%  20.0   100.0%    60.0% 0.0    100.0% 128    97     
R4       intermediate  case-02-july    11      54.5%   63.6%  9.1    100.0%    55.0% 0.5    100.0% 171    86     
R4       intermediate  case-03-august  12      41.7%   50.0%  8.3    83.3%     60.0% 18.3   100.0% 102    119    
R5       experienced   case-01-june    10      90.0%   100.0% 10.0   100.0%    85.0% -5.0   100.0% 92     94     
R5       experienced   case-02-july    11      90.9%   90.9%  0.0    71.4%     88.0% -2.9   100.0% 106    105    
R5       experienced   case-03-august  12      75.0%   91.7%  16.7   81.8%     85.0% 10.0   100.0% 96     69     
R6       experienced   case-01-june    10      100.0%  100.0% 0.0    71.4%     80.0% -20.0  100.0% 99     86     
R6       experienced   case-02-july    11      90.9%   90.9%  0.0    76.9%     80.0% -10.9  100.0% 98     70     
R6       experienced   case-03-august  12      91.7%   91.7%  0.0    78.6%     80.0% -11.7  100.0% 102    120    

Pooled over simulated reviewers, every defect over every defect shown
  Catch rate unaided        58.6%   (116 of 198)
  Catch rate aided          84.3%   (167 of 198)
  Lift                      25.7 points

Mean of simulated reviewer rates
  Catch rate unaided        59.1%
  Catch rate aided          84.7%
  Lift                      25.6 points
  Precision unaided         86.9%

Confidence against accuracy over simulated reviewers, the headline measurement
  Stated expectation        66.1%
  Actual, unaided           59.1%
  Gap, unaided              7.0 points
  Gap, aided                -18.6 points
  Memo soundness, 1 to 5    1.9

Teach-back and time over simulated reviewers
  Completeness              100.0%
  Accuracy                  79.2%
  Weak challenges refused   24 of 36
  Mean seconds, phase 1     117.7
  Mean seconds, phase 2     100.7

**Simulated reviewers.** Every session in this set was run by a simulated reviewer, not by a person.

| Reviewer | Persona | Case | Defects | Caught unaided | Caught aided | Confidence stated | Gap |
|---|---|---|---|---|---|---|---|
| R1 | novice | case-01-june | 10 | 4 (40.0%) | 10 (100.0%) | 60.0% | 20.0 |
| R1 | novice | case-02-july | 11 | 3 (27.3%) | 10 (90.9%) | 55.0% | 27.7 |
| R1 | novice | case-03-august | 12 | 2 (16.7%) | 12 (100.0%) | 55.0% | 38.3 |
| R2 | novice | case-01-june | 10 | 5 (50.0%) | 10 (100.0%) | 60.0% | 10.0 |
| R2 | novice | case-02-july | 11 | 4 (36.4%) | 10 (90.9%) | 55.0% | 18.6 |
| R2 | novice | case-03-august | 12 | 5 (41.7%) | 11 (91.7%) | 55.0% | 13.3 |
| R3 | intermediate | case-01-june | 10 | 7 (70.0%) | 8 (80.0%) | 62.0% | -8.0 |
| R3 | intermediate | case-02-july | 11 | 5 (45.5%) | 6 (54.5%) | 60.0% | 14.5 |
| R3 | intermediate | case-03-august | 12 | 5 (41.7%) | 7 (58.3%) | 55.0% | 13.3 |
| R4 | intermediate | case-01-june | 10 | 6 (60.0%) | 8 (80.0%) | 60.0% | 0.0 |
| R4 | intermediate | case-02-july | 11 | 6 (54.5%) | 7 (63.6%) | 55.0% | 0.5 |
| R4 | intermediate | case-03-august | 12 | 5 (41.7%) | 6 (50.0%) | 60.0% | 18.3 |
| R5 | experienced | case-01-june | 10 | 9 (90.0%) | 10 (100.0%) | 85.0% | -5.0 |
| R5 | experienced | case-02-july | 11 | 10 (90.9%) | 10 (90.9%) | 88.0% | -2.9 |
| R5 | experienced | case-03-august | 12 | 9 (75.0%) | 11 (91.7%) | 85.0% | 10.0 |
| R6 | experienced | case-01-june | 10 | 10 (100.0%) | 10 (100.0%) | 80.0% | -20.0 |
| R6 | experienced | case-02-july | 11 | 10 (90.9%) | 10 (90.9%) | 80.0% | -10.9 |
| R6 | experienced | case-03-august | 12 | 11 (91.7%) | 11 (91.7%) | 80.0% | -11.7 |
| **Pooled, simulated reviewers** | 3 persona(s) | 18 session(s) | 198 | 116 (58.6%) | 167 (84.3%) | 66.1% | 7.0 |
```
