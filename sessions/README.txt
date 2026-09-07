Session logs land in this folder, one JSON file per completed session, named
case_reviewer_suffix.json.

Each file holds the case, the reviewer's sealed findings, the challenge list
with its citations, every teach-back verdict and reason, the confidence ratings,
the timings, the scores, and the match trail showing why each finding was scored
the way it was. It is enough to recompute every number without the tool.

No name is in any of these files. A reviewer is R1 to R99.

python -m second_pass results --dir sessions

aggregates everything here into the pilot numbers. Files in subfolders are
ignored by that command, which is why the worked example sits in example/ rather
than beside the real ones.

example/case-01-june_R3_6c58a567.json is a real session run through the command
line during the build. It is there to show the log format, and it predates the
refine step, so its scores block has fewer fields than one written now.

pilot-1/ holds the eighteen session logs from the simulated pilot of
5 September 2026, moved there whole after that pass closed. They were produced
against the pilot one case pack and prompt version 1, both of which the refine
step replaced, so they are not comparable with anything written here afterwards
and they are kept out of this folder for exactly that reason.

    python -m second_pass results --dir sessions/pilot-1 --only simulated

reproduces pilot one's numbers, which are also frozen in PILOT-1-RESULTS.md.
PILOT-1-FINDINGS.md says what each of its findings changed.
