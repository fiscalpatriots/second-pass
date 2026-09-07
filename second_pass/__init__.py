"""Second Pass, a teach-back review trainer for month-end flux commentary.

The tool sits on one handoff: an AI drafts the variance commentary for a
month-end close, and a human reviews it. Second Pass makes the reviewer commit
their own findings before it will show them anything the AI produced, then
requires them to defend each machine challenge in their own words, then scores
the gap between what they thought they caught and what they caught.

Nothing in this package approves a memo, rewrites a memo, or issues a
conclusion. It produces challenges that a human has to answer.

Standard library only. No third party packages are required to run a pilot.
"""

__version__ = "1.0.0"

APP_NAME = "Second Pass"

# The non-delegation rule, in one line, quoted by the CLI and the web page.
NON_DELEGATION_RULE = (
    "Second Pass never approves, rewrites or signs a memo. It raises challenges "
    "with citations, and a named human answers every one of them."
)

__all__ = ["__version__", "APP_NAME", "NON_DELEGATION_RULE"]
