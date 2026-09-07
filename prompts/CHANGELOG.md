# Prompt changelog

Prompts are versioned files, not strings inside code, because a reviewer who is
asked to defend a machine output is entitled to read the instruction that
produced it. Every session log records the prompt id and version that ran.

Changing a prompt means adding a new file and a new version number. Editing a
version that has already been used in a session breaks the log's promise, since
the log would then point at an instruction that no longer exists.

| Version | File | Date | Change |
|---|---|---|---|
| 1 | `challenger.v1.md` | 2026-09-05 | First version. Challenges only, no approval and no rewrite. Every challenge must carry the account line and the amount. The model names what is wrong and asks the reviewer to explain it, rather than supplying the explanation, so that the teach-back step still has something to do. Materiality threshold passed in from the case. |
| 2 | `challenger.v2.md` | 2026-09-05 | The refine step after pilot one, from the findings in PILOT-1-FINDINGS.md. Four changes. The cited amount must be the named account's own movement, and where the point is the other side of an entry the text has to name that account, its own movement and its direction: pilot one attached the other side's figure to the named account six times and reviewers who recomputed found the tool wrong. Every challenge carries a one-word category tag from a fixed list of eight, on weak and real challenges alike, so the tag never says which is which. A challenge that asks for a driver has to say what would count as evidence, naming the artefact rather than the adjective. And the model is told to read the sentence before firing a template, because v1 asked which of two numbers was a percentage against a sentence that had already labelled its percentage. The prompt now also receives the case's subtotals, so a ratio test does not require summing seven lines by hand. The approval ban and the refusal to hand over the explanation are unchanged. |

## If you change it

1. Copy the file to the next version number and edit that.
2. Update `PROMPT_VERSION` and `PROMPT_FILE` in `second_pass/challenger.py`.
3. Add a row above saying what changed and why.
4. Run `python tests/test_smoke.py`. The approval language test is the one that
   matters: a prompt change that lets an approval through is a governance
   failure, not a wording preference.
