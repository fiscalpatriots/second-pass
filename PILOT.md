# Pilot protocol

One hour on Zoom, about five reviewers. The reviewers are fraud examiners from
the student chapter, gathered through its president. Everyone runs the tool
themselves. The facilitator runs the clock and says as little as possible.

**This has not run.** It was first written for a date before 12 September 2026,
that date passed without a room, and the protocol carries no date until one is
confirmed with the chapter president. Every number this repository holds came
from a simulated reviewer.

**Two scored cases per reviewer**, counterbalanced, plus an unscored walkthrough
on case three. That is the design and it is the design SIMULATION.md describes,
which it did not before 13 September 2026: the two documents disagreed, and the
hour below is what the tool is built to run. It costs something, and the cost is
stated rather than hidden. A reviewer meeting a second case has already met most
of the twelve failure modes once, so the second case is not a clean first
encounter and the write-up has to say which case came first for each reviewer.

The hour produces four numbers: catch rate unaided, catch rate final, the gap
between stated confidence and actual accuracy, and time per phase. Nothing else
is collected, and nobody's name is recorded.

**A codename is pseudonymity, not anonymity.** A reviewer is R1 to R99 and no
name is stored anywhere. In a live room the facilitator can still see who is
sitting at which laptop, and a reviewer can recognise their own answers, so the
promise that can honestly be made is that no name is recorded and only aggregate
figures are reported. It is not a promise that nobody could ever work out whose
row is whose, and nothing in this protocol may say that it is.

## Before the day

- [ ] Confirm the room with the chapter president: how many people, and that each has a laptop
      with Python and can run one command. Five is the target, three is enough,
      and the write-up reports whatever number turns up.
- [ ] Send the one-paragraph invitation below at least two days ahead.
- [ ] Run `python -m second_pass check` on the facilitator machine and confirm it
      loads three cases.
- [ ] Run `python tests/test_smoke.py` and `python tests/test_withholding.py`.
      Both should end with OK.
- [ ] Decide the AI layer and keep it the same for everyone. If any reviewer
      lacks a key, run the whole room with `--provider deterministic` so the
      numbers are comparable.
- [ ] Print or open `python -m second_pass show --case case-01-june --key` for
      the debrief. Do not share that screen before the debrief.
- [ ] Have the paper fallback ready. See Contingencies.

**The invitation, to be sent by whoever is gathering the room.**

> I am testing a review trainer for month-end variance commentary and I need
> about five people for one hour on Zoom. You review two short memos that a
> machine drafted, write down what you would challenge, and then compare that
> against what the tool challenges. It is voluntary, it is not graded, it has
> nothing to do with any course, and no names are recorded. You work under a
> codename like R1, and the results are reported as aggregate numbers only.

## The consent line, read out at the start

Read this verbatim before anything else, then pause and ask whether anyone would
rather not take part.

> Before we start. This is voluntary and you can stop at any point without
> saying why. It is not graded, it is not connected to any course, and it is not
> connected to the chapter's standing. The data in the cases is invented and no
> real company is involved. The tool records what you write and how long you
> take, under a label like R1 or R2. It does not record your name, your email or
> anything that identifies you. I will not try to work out whose row is whose,
> but I am in the room, so I am not going to tell you it would be impossible: a
> codename is a codename, not anonymity. I will report aggregate numbers only,
> so no name appears anywhere in what I write up. If you would rather watch than
> take part, that is completely fine, say so now or just leave the tool
> closed.

## The hour

| Time | What happens | Who talks |
|---|---|---|
| 0 to 10 | Brief, consent, and a two-minute walkthrough of the interface using case three, which is never scored | Facilitator |
| 10 to 28 | Case one, run in full. Confidence, unaided findings, commit, then the challenge list and teach-back | Nobody |
| 28 to 46 | Case two, run in full, same shape | Nobody |
| 46 to 56 | Debrief on the answer key, one defect at a time, with the group | Everyone |
| 56 to 60 | What happens to the data, and thanks | Facilitator |

Half the room starts with case one and half with case two, so that any
difference between the two cases does not sit entirely on one phase. Tell people
which case to open, do not let them choose.

## The facilitator script

**Opening, two minutes.** The lines to say, in this order. Do not explain the
purpose of the measurement before the measurement, because a room told it is
being tested on overconfidence will not be overconfident.

> You are a controller and it is close week. Someone has handed you a variance
> memo explaining why each account moved, and the memo was drafted with AI. Your
> job is the job you would actually have: decide what you would challenge before
> you sign it.
>
> The tool will ask you two questions before you start, then give you the memo.
> Write down what you would challenge, one finding per box, and name the account
> in each one. When you commit, the list is sealed. Only then does the tool show
> you what it produced, and some of what it produced is not worth accepting.
> Accept or reject each one in your own words. A one-word reason does not count.
>
> There is no passing score. I built the memos, so I know where the problems are
> and that tells you nothing about how good you are at your job. What I am
> measuring is the tool, not you.

**Starting a case.** Everyone types the same command:

```
python -m second_pass serve --port 8765
```

Then in the browser: pick the case you were told to open, pick your reviewer
label, and press `Open the case`. Reviewer labels are assigned by the
facilitator at the start, R1 through R5, one each, so no two people pick the
same one.

**During the work, say nothing.** If someone asks whether something counts as a
finding, the answer is "write down what you would raise with the person who
drafted it". If someone asks how many problems are in the memo, the answer is
"the tool will tell you at the end". Do not confirm or deny a finding, ever,
because the moment you do the numbers stop meaning anything.

**Two-minute warning** before each phase ends. People will not finish, and that
is a result rather than a problem.

**The debrief, ten minutes.** Share the answer key screen and go through the
defects that were most missed, using each case's own `correct` text. Ask the
group two questions and let the silence sit.

> Which of these would you have caught if you had drafted the memo yourself?
>
> What would you have had to see, in a supporting schedule, before you would sign
> this?

**Closing.** Say where the logs live, that they contain no names, that only
aggregate numbers will be reported, and that anyone who wants their session
deleted can say so now or by message afterwards.

## What to record

Almost nothing by hand. The tool records the findings, the challenges, the
teach-backs, the confidence ratings, the timings and the scores, one JSON file
per session in `sessions/`.

The facilitator records four things on paper:

1. How many people took part, and how many watched.
2. Which reviewer label went with case one first and which with case two first.
3. Anything that went wrong technically, and for whom, because a session that
   was cut short by a laptop is not a low catch rate.
4. Any request to delete a session.

Not recorded, at all: names, email addresses, employers, courses, or which
person held which label.

At the end of the hour, collect the session files into one folder. If reviewers
ran on their own machines, ask each of them to send the files from their
`sessions/` folder. The files carry no names.

## Producing the numbers

```
python -m second_pass results --dir sessions --markdown --out pilot-results.txt
```

That prints the per-reviewer table, the pooled catch rates with their
denominators, and the confidence gap. Quote the pooled figure with the
denominator beside it, always.

## The results template

Fill this in from the output. Every blank is a number the tool produced.

> **Pilot.** ___ reviewers, ___ September 2026, one hour, remote. Each reviewer
> worked ___ cases from a pack of three, each carrying 10 to 12 planted defects
> of distinct kinds across a synthetic trial balance and an AI-drafted
> commentary. Reviewers committed their own findings before the tool would show
> them anything, and stated in advance what share of the problems they expected
> to find.
>
> **Catch rate.** Unaided, reviewers found ___ of ___ planted defects, or ___
> percent. After working the challenge list and defending each item in their own
> words, they held ___ of ___, or ___ percent. Lift of ___ points.
>
> **Confidence against accuracy.** Before starting, reviewers expected to find
> ___ percent of the problems. They found ___ percent. The gap is ___ points.
> They rated the memos ___ out of 5 for soundness, memos which carried ___
> defects each.
>
> **Precision, against the answer key.** ___ percent of the findings reviewers
> raised pointed at a planted defect. ___ findings sat outside the answer key
> and were adjudicated by the facilitator rather than scored; they are listed in
> the session logs verbatim and they reduced nobody's catch rate. Weak
> challenges refused: ___ of ___, over ___ shapes.
>
> **Time.** Median ___ minutes unaided and ___ minutes with the tool. Reported
> because it was measured, and not the point.

If any reviewer's unaided catch rate came in at 90 percent or better, the report
prints a ceiling note beside their lift, and the write-up quotes it. A lift of
two points against an unaided rate of 92 is not the tool failing to add
anything; it is a reviewer with eight points of room. Say which one it was.

| Reviewer | Case | Defects | Caught unaided | Caught aided | Confidence stated | Gap |
|---|---|---|---|---|---|---|
| R1 | | | | | | |
| R2 | | | | | | |
| R3 | | | | | | |
| R4 | | | | | | |
| R5 | | | | | | |
| **Pooled** | | | | | | |

## Contingencies

**Somebody cannot run Python.** They watch, or they use the paper fallback. Print
the case with `python -m second_pass show --case case-01-june`, have them write
findings on paper, and type those findings into a terminal session afterwards
under their label with `python -m second_pass run --case case-01-june --reviewer
R4`. The measurement survives. Say in the write-up how many rows came from paper.

**Fewer people than expected.** Report the number that turned up. Three reviewers
honestly reported beats five implied.

**Nobody turns up.** The tool, the defect pack and the answer key stand on their
own. Run the bench measurement instead: run each case through the challenger and
report how many planted defects the challenge protocol surfaces against how many
an unaided pass over the same memo surfaces. Say plainly that the pilot is
scheduled rather than complete.

**Someone asks for their session to be deleted.** Delete the file. Say in the
write-up that one session was withdrawn at the participant's request, and report
the smaller denominator.
