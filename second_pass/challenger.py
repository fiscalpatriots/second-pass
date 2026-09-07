"""The AI layer: the thing that produces the challenge list.

Three providers, chosen in this order and reported honestly in the log.

    ANTHROPIC_API_KEY present -> Anthropic Messages API
    OPENAI_API_KEY present    -> OpenAI Chat Completions API
    neither                   -> the deterministic challenger

The deterministic challenger is not a stub. It builds the same shape of
challenge list from the case's own answer key, with the same citation rule and
the same refusal to state the full answer, so a pilot can be run on a plane with
no network and produce numbers that mean the same thing. That matters more than
it sounds: a scholarship reviewer, a firm, or a facilitator on a hotel wifi
should be able to open this and have it work.

Key presence is detected with os.environ and reported as present or absent.
The value of a key is never read into a log, a session file, a console line or
an error message.

Whatever produced the list, every challenge is validated before a reviewer sees
it: the account must exist, the amount must be a number, and the text must not
approve anything. Approval language is the one output this tool is built to
refuse, so it is checked in code rather than trusted to a prompt.
"""

import json
import os
import random
import re
import urllib.error
import urllib.request

from . import cases

PROMPT_ID = "second-pass/challenger"
PROMPT_VERSION = 2
PROMPT_FILE = "challenger.v2.md"

ANTHROPIC_MODEL = os.environ.get("SECOND_PASS_ANTHROPIC_MODEL", "claude-sonnet-4-5")
OPENAI_MODEL = os.environ.get("SECOND_PASS_OPENAI_MODEL", "gpt-4o-mini")
REQUEST_TIMEOUT = 60

# The words this tool must never send to a reviewer as part of a challenge.
# Checked against the model's output, not only asked for in the prompt.
APPROVAL_PATTERNS = [
    r"\blooks (good|fine|correct|reasonable)\b",
    r"\bappears (correct|reasonable|accurate|fine)\b",
    r"\bno (issues|concerns|exceptions|problems) (found|noted|identified)\b",
    r"\bnothing (further|else) to (raise|note)\b",
    r"\b(i |we )?approve\b",
    r"\bapproved\b",
    r"\bsign(ed)? off\b",
    r"\bready (for|to) (release|issue|sign)",
    r"\bacceptable as (written|drafted|stated)\b",
    r"\bcorrect as (written|drafted|stated)\b",
    r"\bconcur with management\b",
    r"\bno further (review|work) (is )?(required|needed)\b",
]

_APPROVAL_RE = [re.compile(pattern, re.IGNORECASE) for pattern in APPROVAL_PATTERNS]


class ChallengerError(Exception):
    pass


def contains_approval_language(text):
    """Return the offending phrase, or None. The governance control, in code."""
    for pattern in _APPROVAL_RE:
        found = pattern.search(text or "")
        if found:
            return found.group(0)
    return None


def key_status():
    """Present or absent. Never the value, never a prefix, never a length."""
    return {
        "ANTHROPIC_API_KEY": "present" if os.environ.get("ANTHROPIC_API_KEY") else "absent",
        "OPENAI_API_KEY": "present" if os.environ.get("OPENAI_API_KEY") else "absent",
    }


def select_provider(preferred=None):
    """Which layer will actually run, given the environment right now."""
    if preferred and preferred != "auto":
        return preferred
    if os.environ.get("ANTHROPIC_API_KEY"):
        return "anthropic"
    if os.environ.get("OPENAI_API_KEY"):
        return "openai"
    return "deterministic"


def prompts_dir():
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(os.path.dirname(here), "prompts")


def load_prompt():
    """Read the versioned prompt file and return (system, user_template)."""
    path = os.path.join(prompts_dir(), PROMPT_FILE)
    with open(path, "r", encoding="utf-8") as handle:
        text = handle.read()
    blocks = {}
    current = None
    buffer = []
    in_fence = False
    for line in text.splitlines():
        if line.startswith("## "):
            current = line[3:].strip().lower()
            buffer = []
            in_fence = False
            continue
        if current in ("system", "user template"):
            if line.strip().startswith("```"):
                if in_fence:
                    blocks[current] = "\n".join(buffer).strip()
                    in_fence = False
                    current = None
                else:
                    in_fence = True
                    buffer = []
                continue
            if in_fence:
                buffer.append(line)
    if "system" not in blocks or "user template" not in blocks:
        raise ChallengerError("prompts/%s is missing a SYSTEM or USER TEMPLATE block" % PROMPT_FILE)
    return blocks["system"], blocks["user template"]


def render_user_prompt(case, max_challenges):
    _system, template = load_prompt()
    rows = cases.movement_table(case)
    table_lines = ["Line | Account | Prior | Current | Variance | Percent"]
    for row in rows:
        table_lines.append("%s | %s | %s | %s | %s | %s" % (
            row["line"], row["name"],
            cases.format_amount(row["prior"]), cases.format_amount(row["current"]),
            cases.format_amount(row["variance"]), cases.format_percent(row["percent"]),
        ))
    subtotal_lines = []
    for row in cases.subtotal_table(case):
        subtotal_lines.append("%s (%s) | %s | %s | %s | %s" % (
            row["label"], " + ".join(row["lines"]),
            cases.format_amount(row["prior"]), cases.format_amount(row["current"]),
            cases.format_amount(row["variance"]), cases.format_percent(row["percent"])))
    commentary_lines = []
    for sentence in case["commentary"]["sentences"]:
        commentary_lines.append("%s: %s" % (sentence["id"], sentence["text"]))
    materiality_text = "%s %s" % (
        cases.materiality_rule(case), case["materiality"].get("basis", ""))
    replacements = {
        "{{COMPANY}}": case["company"]["name"] + " (fictional, synthetic training data)",
        "{{PERIOD_CURRENT}}": case["period"]["current"],
        "{{PERIOD_PRIOR}}": case["period"]["prior"],
        "{{MATERIALITY}}": materiality_text.strip(),
        "{{MARGIN_DEFINITION}}": case.get("margin_definition", ""),
        "{{TABLE}}": "\n".join(table_lines),
        "{{SUBTOTALS}}": "\n".join(subtotal_lines) or "None supplied for this case.",
        "{{COMMENTARY}}": "\n".join(commentary_lines),
        "{{TAGS}}": ", ".join(cases.CHALLENGE_TAGS),
        "{{MAX_CHALLENGES}}": str(max_challenges),
    }
    rendered = template
    for placeholder, value in replacements.items():
        rendered = rendered.replace(placeholder, value)
    return rendered


# ---------------------------------------------------------------- deterministic

# Every template names what is wrong and asks the reviewer to explain it. None
# of them supplies the explanation, and none of them concludes anything.
#
# Where a type has two entries, the second is a fit variant. Pilot one fired one
# template per type without checking whether it fitted the sentence in front of
# it, and produced a challenge asking which of two numbers was a percentage
# against a sentence that had already labelled its percentage. A challenge that
# does not fit its own sentence teaches a reviewer that the list is not read
# before it is sent.
_TEMPLATES = {
    "wrong_sign": (
        "Account {line} {account} moved {amount} over the month, and {sentence_ref} states that "
        "movement in the other direction. Recompute it from the table, say which way the account "
        "actually went, and say what that does to the sentence."
    ),
    "wrong_period": (
        "{sentence_ref} ties activity on account {line} {account} to a period other than the one "
        "the {amount} movement was recorded in. Say which period the amount belongs in and what "
        "the entry should have been."
    ),
    "unsupported_driver": (
        "{sentence_ref} names a driver for the {amount} movement on account {line} {account} "
        "without citing anything that supports it. Say whether you have seen that support, and "
        "what you would ask for before the memo is released."
    ),
    "mismatched_amount": (
        "The amount in {sentence_ref} does not agree with account {line} {account}, which moved "
        "{amount}. State the difference and say where the figure in the memo came from."
    ),
    "missing_driver_material": (
        "Account {line} {account} moved {amount} and the commentary never mentions it. Test that "
        "movement against both legs of the threshold, then say why a movement of that size cannot "
        "be released without a driver and what you would ask for."
    ),
    "cutoff": (
        "{sentence_ref} places activity on account {line} {account} in a later month than the one "
        "it relates to. The account moved {amount} in total. State the correct period and the "
        "entry that should have been posted."
    ),
    "reclass_as_growth": (
        "The movement of {amount} on account {line} {account} may be a transfer between accounts "
        "rather than the operating change {sentence_ref} describes. Identify the other side of it "
        "and say what the underlying movement really was."
    ),
    "reclass_as_growth.counterparty": (
        "Account {line} {account} moved {amount}, and {sentence_ref} presents that as an operating "
        "change. Say how much of it is a transfer between the two accounts named in this challenge "
        "and what is left once you take the transfer out."
    ),
    "percent_as_absolute": (
        "{sentence_ref} reports a figure for account {line} {account} that reads as a dollar "
        "amount while the account moved {amount}. Say which of the two numbers is a percentage "
        "and restate the sentence correctly."
    ),
    "percent_as_absolute.labelled": (
        "{sentence_ref} states a percentage for account {line} {account} and then restates the "
        "same movement as a dollar figure. The account moved {amount}. Recompute the dollar "
        "movement and say where the figure in the sentence came from."
    ),
    "contradiction": (
        "Two sentences in this memo cannot both be true about account {line} {account} and its "
        "movement of {amount}. Name the pair, say which one you believe, and say why the "
        "difference matters to the close."
    ),
    "immaterial_over_explained": (
        "Account {line} {account} moved {amount}. Test that movement against both legs of the "
        "threshold, then say whether {sentence_ref} should be in the memo at all and what it "
        "displaced."
    ),
    "rounding_flips_conclusion": (
        "{sentence_ref} reaches a conclusion from rounded figures, and account {line} {account} "
        "moved {amount} in the period it covers. Recompute the ratio unrounded for both months "
        "and say whether the conclusion survives."
    ),
    "driver_wrong_account": (
        "{sentence_ref} explains the {amount} movement on account {line} {account} using a driver "
        "that belongs to a different account. Name the account the driver actually affects and say "
        "what is left unexplained."
    ),
}

# Finding 9 from pilot one: a challenge that says "name a driver" has to say
# what would count. Reviewers were asked for evidence and had to guess the bar,
# and one of them offered a second management assertion as the answer.
_EVIDENCE_BY_TYPE = {
    "unsupported_driver": (
        "Sufficient evidence is something that ties to this account and this month: a volume or "
        "unit schedule, a customer or channel split, a rate change with its effective date, or a "
        "signed contract. A management assertion restated in a second sentence is not evidence."
    ),
    "missing_driver_material": (
        "Sufficient evidence is the detail behind the movement: the transactions that produced it, "
        "a headcount or rate schedule, or the journal entries posted in the month. Naming the "
        "department the cost sits in is not a driver."
    ),
    "driver_wrong_account": (
        "Sufficient evidence is a driver whose amount and account both tie to the line it is "
        "offered for. A driver that moves a different account explains that account, not this one."
    ),
    "reclass_as_growth": (
        "Sufficient evidence is the journal entry or the recharge schedule showing both sides of "
        "the transfer, with the amount on each side agreeing to the movement on its account."
    ),
}


def account_movements(case):
    """Line -> current less prior. The only amount a challenge may cite."""
    return dict((account["line"], round(float(account["current"]) - float(account["prior"]), 2))
                for account in case["accounts"])


def _percent_is_labelled(sentence_text):
    """Does the sentence already say the word percent next to its figure?

    If it does, asking the reviewer which of the two numbers is a percentage is
    a question the sentence has already answered, and the reviewer learns that
    the list fires templates without reading them.
    """
    text = (sentence_text or "").lower()
    return "percent" in text or "%" in text


def _sentence_text(case, sentence_id):
    for sentence in case["commentary"]["sentences"]:
        if sentence["id"] == sentence_id:
            return sentence["text"]
    return ""


def _choose_template(defect, case):
    """The template, after checking that it fits the sentence it is aimed at."""
    kind = defect["type"]
    if kind == "percent_as_absolute":
        if _percent_is_labelled(_sentence_text(case, defect.get("sentence"))):
            return _TEMPLATES["percent_as_absolute.labelled"], "percent_as_absolute.labelled"
    if kind == "reclass_as_growth" and defect.get("counterparty"):
        return _TEMPLATES["reclass_as_growth.counterparty"], "reclass_as_growth.counterparty"
    return _TEMPLATES.get(kind, _TEMPLATES["unsupported_driver"]), kind


def _direction_word(mine, other):
    if mine == 0 or other == 0:
        return "over the same month"
    return "in the opposite direction" if (mine > 0) != (other > 0) else "in the same direction"


def _counterparty_clause(defect, movements, account_by_line):
    """Name the other account and its own movement, out loud.

    Pilot one attached the other side's figure to the named account with no
    signal at all, so a reviewer who recomputed the named account found the
    challenge wrong and stopped recomputing anything.
    """
    counterparty = defect.get("counterparty")
    if not counterparty:
        return ""
    line = counterparty["line"]
    other = movements[line]
    clause = "Account %s %s moved %s %s." % (
        line, account_by_line[line]["name"], cases.format_amount(abs(other)),
        _direction_word(movements[defect["line"]], other))
    if counterparty.get("note"):
        clause += " " + counterparty["note"]
    return clause


def _focus_clause(defect, movements):
    """Say what a figure is when it is not the account's own movement."""
    focus = defect.get("focus")
    if not focus:
        return ""
    movement = abs(movements[defect["line"]])
    amount = abs(float(focus["amount"]))
    if round(amount, 2) == round(movement, 2):
        return ""
    relation = ("larger than the movement recorded on the account" if amount > movement
                else "inside the movement recorded on the account")
    return "The memo puts %s in play as %s, which is %s." % (
        cases.format_amount(amount), focus["what"], relation)


def deterministic_challenges(case, max_challenges=None):
    """Build the challenge list from the case's own answer key and distractors.

    The distractors are in the list on purpose. A challenge list a reviewer can
    accept wholesale teaches nothing, and the tool is trying to build judgment
    rather than obedience. Rejecting a weak challenge with a reason is scored
    exactly as highly as accepting a good one.

    Every challenge cites the movement of the account it names, read from the
    table rather than from the answer key, so a reviewer who recomputes the
    cited figure always finds it. Where the point is the other side of an entry,
    or a figure the memo puts in play that is not the account's own movement,
    the challenge text says so in words.
    """
    account_by_line = cases.account_index(case)
    movements = account_movements(case)
    built = []
    for defect in case["answer_key"]:
        account = account_by_line[defect["line"]]
        movement = abs(movements[defect["line"]])
        template, variant = _choose_template(defect, case)
        sentence_ref = "Sentence %s" % defect["sentence"] if defect.get("sentence") else "The commentary"
        question = template.format(
            line=defect["line"],
            account=account["name"],
            amount=cases.format_amount(movement),
            sentence_ref=sentence_ref,
        )
        for clause in (_counterparty_clause(defect, movements, account_by_line),
                       _focus_clause(defect, movements)):
            if clause:
                question = question + " " + clause
        built.append({
            "line": defect["line"],
            "account": account["name"],
            "amount": float(movement),
            "sentence": defect.get("sentence"),
            "tag": cases.defect_tag(defect),
            "evidence": defect.get("evidence") or _EVIDENCE_BY_TYPE.get(defect["type"], ""),
            "question": question,
            "template": variant,
            "truth": {"kind": "defect", "ref": defect["id"], "type": defect["type"]},
        })
    for distractor in case.get("distractors", []):
        account = account_by_line[distractor["line"]]
        built.append({
            "line": distractor["line"],
            "account": account["name"],
            "amount": float(abs(distractor.get("amount") or 0)),
            "sentence": distractor.get("sentence"),
            "tag": distractor.get("tag") or "amount",
            "evidence": distractor.get("evidence", ""),
            "question": distractor["text"],
            "template": "distractor.%s" % distractor.get("shape", "unshaped"),
            "truth": {"kind": "distractor", "ref": distractor["id"],
                      "type": "weak_challenge", "shape": distractor.get("shape")},
        })
    # Deterministic order: seeded by case id, so the distractors are not always
    # last and every reviewer of a given case sees the same sequence.
    random.Random(case["id"]).shuffle(built)
    if max_challenges:
        built = built[:max_challenges]
    for index, challenge in enumerate(built, start=1):
        challenge["id"] = "C%d" % index
        challenge["citation"] = _citation(challenge)
        challenge["source"] = "deterministic"
    return built


def _citation(challenge):
    parts = ["Account %s %s" % (challenge["line"], challenge["account"])]
    if challenge.get("amount") is not None:
        # $0 is printed rather than dropped. A challenge on a line that did not
        # move is still a challenge with a figure a reviewer can check.
        parts.append("movement %s" % cases.format_amount(challenge["amount"]))
    if challenge.get("sentence"):
        parts.append("sentence %s" % challenge["sentence"])
    if challenge.get("tag"):
        parts.append("tag %s" % challenge["tag"])
    return ", ".join(parts)


# ------------------------------------------------------------------- providers


def _post_json(url, payload, headers):
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url, data=data, headers=headers, method="POST")
    with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT) as response:
        return json.loads(response.read().decode("utf-8"))


def _call_anthropic(system_prompt, user_prompt):
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise ChallengerError("ANTHROPIC_API_KEY is absent")
    payload = {
        "model": ANTHROPIC_MODEL,
        "max_tokens": 2000,
        "temperature": 0,
        "system": system_prompt,
        "messages": [{"role": "user", "content": user_prompt}],
    }
    headers = {
        "content-type": "application/json",
        "x-api-key": key,
        "anthropic-version": "2023-06-01",
    }
    body = _post_json("https://api.anthropic.com/v1/messages", payload, headers)
    chunks = [block.get("text", "") for block in body.get("content", []) if block.get("type") == "text"]
    return "".join(chunks)


def _call_openai(system_prompt, user_prompt):
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        raise ChallengerError("OPENAI_API_KEY is absent")
    payload = {
        "model": OPENAI_MODEL,
        "temperature": 0,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    }
    headers = {
        "content-type": "application/json",
        "authorization": "Bearer " + key,
    }
    body = _post_json("https://api.openai.com/v1/chat/completions", payload, headers)
    return body["choices"][0]["message"]["content"]


def _extract_json(text):
    text = (text or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n", "", text)
        text = re.sub(r"\n```$", "", text.strip())
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1:
        raise ChallengerError("the model did not return a JSON object")
    return json.loads(text[start:end + 1])


def _names_another_account(question, line, account_by_line):
    """Does the text explicitly name a different account from the table?"""
    text = (question or "").lower()
    for other_line, account in account_by_line.items():
        if other_line == line:
            continue
        if other_line.lower() in text or account["name"].lower() in text:
            return other_line
    return None


def validate_challenges(raw_challenges, case, source):
    """Enforce the citation rule and the approval ban. Returns (kept, dropped).

    Three controls run here on every challenge from every provider.

        the account has to exist in the table
        the amount has to be a number, and it has to be that account's own
            movement unless the text names the other account it belongs to
        the text must not approve anything

    The middle one is new after pilot one. A challenge that cites the other
    side's figure against the named account is worse than no challenge, because
    a reviewer who does the arithmetic the tool asked for finds the tool wrong
    and stops doing arithmetic. Dropping it is recorded, so the count of drops
    is evidence about the model rather than a silent correction.
    """
    account_by_line = cases.account_index(case)
    movements = account_movements(case)
    kept = []
    dropped = []
    for index, item in enumerate(raw_challenges):
        line = str(item.get("line", "")).strip()
        question = (item.get("question") or "").strip()
        amount = item.get("amount")
        if line not in account_by_line:
            dropped.append({"index": index, "reason": "cites an account that is not in the table", "line": line})
            continue
        if not isinstance(amount, (int, float)):
            dropped.append({"index": index, "reason": "no numeric amount, so the challenge cannot be recomputed", "line": line})
            continue
        if not question:
            dropped.append({"index": index, "reason": "empty challenge text", "line": line})
            continue
        offending = contains_approval_language(question)
        if offending:
            dropped.append({"index": index, "reason": "approval language: '%s'" % offending, "line": line})
            continue
        movement = abs(movements[line])
        if round(abs(float(amount)), 2) != round(movement, 2):
            other = _names_another_account(question, line, account_by_line)
            if not other:
                dropped.append({
                    "index": index,
                    "reason": ("cites %s against account %s, which moved %s, and names no other "
                               "account the figure could belong to"
                               % (cases.format_amount(abs(float(amount))), line,
                                  cases.format_amount(movement))),
                    "line": line,
                })
                continue
        tag = str(item.get("tag") or "").strip().lower()
        if tag not in cases.CHALLENGE_TAGS:
            tag = "amount"
        evidence = (item.get("evidence") or "").strip()
        if evidence and contains_approval_language(evidence):
            evidence = ""
        challenge = {
            "line": line,
            "account": account_by_line[line]["name"],
            "amount": abs(float(amount)),
            "sentence": item.get("sentence"),
            "tag": tag,
            "evidence": evidence,
            "question": question,
            "source": source,
            "template": "model",
            "truth": {"kind": "model", "ref": None, "type": None},
        }
        challenge["citation"] = _citation(challenge)
        kept.append(challenge)
    for index, challenge in enumerate(kept, start=1):
        challenge["id"] = "C%d" % index
    return kept, dropped


def generate_challenges(case, provider="auto", max_challenges=None):
    """Return (challenges, meta). Meta goes into the session log verbatim."""
    if max_challenges is None:
        max_challenges = len(case["answer_key"]) + len(case.get("distractors", []))
    chosen = select_provider(provider)
    meta = {
        "prompt_id": PROMPT_ID,
        "prompt_version": PROMPT_VERSION,
        "prompt_file": "prompts/" + PROMPT_FILE,
        "keys": key_status(),
        "provider_requested": provider,
        "provider_used": chosen,
        "model": None,
        "dropped": [],
        "fallback_reason": None,
    }
    if chosen == "deterministic":
        challenges = deterministic_challenges(case, max_challenges)
        meta["challenge_count"] = len(challenges)
        return challenges, meta

    system_prompt, _template = load_prompt()
    user_prompt = render_user_prompt(case, max_challenges)
    try:
        if chosen == "anthropic":
            meta["model"] = ANTHROPIC_MODEL
            text = _call_anthropic(system_prompt, user_prompt)
        elif chosen == "openai":
            meta["model"] = OPENAI_MODEL
            text = _call_openai(system_prompt, user_prompt)
        else:
            raise ChallengerError("unknown provider '%s'" % chosen)
        parsed = _extract_json(text)
        kept, dropped = validate_challenges(parsed.get("challenges", []), case, chosen)
        meta["dropped"] = dropped
        if not kept:
            raise ChallengerError("no challenge survived validation")
        meta["challenge_count"] = len(kept)
        return kept, meta
    except (ChallengerError, urllib.error.URLError, urllib.error.HTTPError, ValueError, KeyError) as error:
        # The message is recorded, the key is not. urllib does not put the
        # header value in the exception text, and nothing here reads the key.
        meta["fallback_reason"] = "%s: %s" % (type(error).__name__, str(error)[:300])
        meta["provider_used"] = "deterministic"
        challenges = deterministic_challenges(case, max_challenges)
        meta["challenge_count"] = len(challenges)
        return challenges, meta


def public_challenges(challenges):
    """The reviewer's copy. The truth block never crosses this line.

    A reviewer who could see which challenges came from the answer key would
    accept those and reject the rest without thinking, which is the exact
    behaviour the tool exists to break.
    """
    public = []
    for challenge in challenges:
        public.append({
            "id": challenge["id"],
            "line": challenge["line"],
            "account": challenge["account"],
            "amount": challenge["amount"],
            "sentence": challenge.get("sentence"),
            "tag": challenge.get("tag"),
            "evidence": challenge.get("evidence", ""),
            "citation": challenge["citation"],
            "question": challenge["question"],
            "source": challenge.get("source", "deterministic"),
        })
    return public
