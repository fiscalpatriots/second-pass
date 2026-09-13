"""Case loading, validation and the reviewer-safe view of a case.

A case file is JSON. The full format is written out in README.md under
"Swapping in your own memos". This module is the enforcing copy of that spec:
if a file does not match, loading fails here with a message naming the field.

Two rules matter more than the rest.

1. Variance and percent are computed, never stored. A case file that carried
   its own variance column could disagree with its own prior and current
   columns, and the tool would then be teaching a defect it did not plant.
2. reviewer_view() is the only function allowed to build the payload that
   reaches a reviewer before they commit. It strips the answer key and the
   distractors. Nothing else in the package sends a case anywhere.

Three rules were added after pilot one, and each of them exists because a
reviewer was misled by the old behaviour. They are enforced here rather than
trusted to a case author.

3. A defect's cited amount has to be the movement of the account it names. A
   challenge that tells a reviewer to recompute, and then cites the other
   side's figure against the named account, teaches the reviewer that
   recomputing is pointless. Where the memo puts a different figure in play,
   the defect declares it in `focus` and the challenge text says so out loud.
   Where the point is the other side of an entry, the defect declares
   `counterparty` and the challenge names that account and its movement.
4. Weak challenges carry a `shape`, and no case may plant the same shape
   twice. In pilot one every weak challenge was a below-threshold document
   ask, so after one case a reviewer could refuse them without arithmetic.
5. Every challenge carries a one-word category tag, and a weak challenge's tag
   has to be one that a real defect in the same case also carries. A tag that
   only ever appeared on the planted weak leads would give them away.

A sixth was added on 13 September 2026, after an external audit put a challenge
through validation carrying an amount of 999,999,999, a sentence id of
NONEXISTENT and the evidence reference "Imaginary document page 999", and the
tool kept it because the question text happened to name a second real account.
Output formatting was standing in for substantive validation.

6. Every identifier and every amount a challenge binds has to resolve against
   this case. The account exists in the table; the amount is the movement of
   the account it is cited against, or of another account the text names; the
   sentence id exists in the commentary; and every evidence reference resolves
   to an entry in the case's `sources` inventory. `validate_challenge_bindings`
   is the enforcing copy and it runs on every challenge from every provider,
   deterministic and model alike.

The inventory matters for a reason that is easy to miss. A challenge may ask
for a *type* of evidence that does not exist yet, which is the whole point of
asking: "a volume schedule tying to this account and this month" is a bar, not a
document. What a challenge may not do is cite a document as though the case
carried it. So the two are separate fields. `evidence_requested` is prose about
what would count and is never resolved against anything. `evidence_refs` are
references to documents this case actually holds, and each one has to be in
`sources` or the challenge is dropped.
"""

import json
import os

CASE_SCHEMA = "second-pass/case/v1"

DEFECT_TYPES = (
    "wrong_sign",
    "wrong_period",
    "unsupported_driver",
    "mismatched_amount",
    "missing_driver_material",
    "cutoff",
    "reclass_as_growth",
    "percent_as_absolute",
    "contradiction",
    "immaterial_over_explained",
    "rounding_flips_conclusion",
    "driver_wrong_account",
)

# The one-word category tag every challenge carries, real and weak alike. It
# tells a reviewer what kind of test to run before they read the sentence, and
# because a weak challenge's tag has to match a tag a real defect in the same
# case carries, it never says which is which.
CHALLENGE_TAGS = (
    "amount",
    "direction",
    "period",
    "driver",
    "contradiction",
    "threshold",
    "classification",
    "transfer",
)

DEFAULT_TAG_BY_TYPE = {
    "wrong_sign": "direction",
    "wrong_period": "period",
    "cutoff": "period",
    "unsupported_driver": "driver",
    "missing_driver_material": "driver",
    "driver_wrong_account": "classification",
    "mismatched_amount": "amount",
    "percent_as_absolute": "amount",
    "rounding_flips_conclusion": "amount",
    "contradiction": "contradiction",
    "immaterial_over_explained": "threshold",
    "reclass_as_growth": "transfer",
}

# The four shapes a planted weak challenge may take. Pilot one used one shape
# for all six, and the reviewers learned to refuse it on sight.
DISTRACTOR_SHAPES = {
    "below_threshold_document":
        "asks for a document on a movement that fails one leg of the two-part threshold",
    "bad_recomputation":
        "does its own arithmetic on the account and gets it wrong, so the table refutes it",
    "restates_correct_explanation":
        "asks back, as a question, an explanation the memo already gives and the table supports",
    "wrong_period_named":
        "names a period the schedule does not carry, or states a prior figure the table refutes",
}

DEFECT_TYPE_LABELS = {
    "wrong_sign": "Wrong sign",
    "wrong_period": "Wrong period",
    "unsupported_driver": "Unsupported driver",
    "mismatched_amount": "Mismatched amount",
    "missing_driver_material": "Missing driver for a material swing",
    "cutoff": "Cutoff",
    "reclass_as_growth": "Reclassification presented as growth",
    "percent_as_absolute": "Percent stated as an absolute",
    "contradiction": "Contradictory sentences",
    "immaterial_over_explained": "Immaterial item over-explained",
    "rounding_flips_conclusion": "Rounding that flips a conclusion",
    "driver_wrong_account": "Driver explains the wrong account",
}


# What a case's source inventory may hold. A source is a document the case
# says exists and a reviewer could ask for. It is not a document this repository
# ships, and nothing here produces one: the inventory exists so that a challenge
# citing a document can be checked against the documents the case claims.
SOURCE_KINDS = (
    "ledger_detail",
    "schedule",
    "journal_entry",
    "contract",
    "invoice",
    "reconciliation",
    "count_sheet",
    "system_report",
    "management_representation",
)


class CaseError(Exception):
    """A case file is missing something the tool needs, or contradicts itself."""


def cases_dir(root=None):
    if root:
        return root
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(os.path.dirname(here), "cases")


def list_cases(root=None):
    """Return [(case_id, title, path)] for every case file found, sorted."""
    directory = cases_dir(root)
    found = []
    if not os.path.isdir(directory):
        return found
    for name in sorted(os.listdir(directory)):
        if not name.endswith(".json"):
            continue
        path = os.path.join(directory, name)
        with open(path, "r", encoding="utf-8") as handle:
            raw = json.load(handle)
        found.append((raw.get("id", name), raw.get("title", ""), path))
    return found


def load_case(case_id, root=None):
    """Load one case by id or by file path, validated."""
    if os.path.isfile(case_id):
        path = case_id
    else:
        path = None
        for cid, _title, candidate in list_cases(root):
            if cid == case_id or os.path.basename(candidate) == case_id:
                path = candidate
                break
        if path is None:
            known = ", ".join(cid for cid, _t, _p in list_cases(root)) or "none found"
            raise CaseError("No case named '%s'. Known cases: %s" % (case_id, known))
    with open(path, "r", encoding="utf-8") as handle:
        raw = json.load(handle)
    validate_case(raw, path)
    raw["_path"] = path
    return raw


def validate_case(case, path="<memory>"):
    """Raise CaseError on anything that would make a pilot unscoreable."""

    def require(condition, message):
        if not condition:
            raise CaseError("%s: %s" % (os.path.basename(str(path)), message))

    require(case.get("schema") == CASE_SCHEMA, "schema must be '%s'" % CASE_SCHEMA)
    for field in ("id", "title", "company", "period", "materiality", "accounts", "commentary", "answer_key"):
        require(field in case, "missing required field '%s'" % field)
    require(case["company"].get("fictional") is True,
            "company.fictional must be true. Second Pass ships synthetic cases only.")
    require("current" in case["period"] and "prior" in case["period"],
            "period needs 'current' and 'prior'")

    accounts = case["accounts"]
    require(10 <= len(accounts) <= 20, "a case needs 10 to 20 accounts, found %d" % len(accounts))
    seen_lines = set()
    for account in accounts:
        for field in ("line", "name", "prior", "current"):
            require(field in account, "account is missing '%s'" % field)
        require(account["line"] not in seen_lines, "duplicate account line '%s'" % account["line"])
        seen_lines.add(account["line"])
        require(isinstance(account["prior"], (int, float)), "account %s prior must be numeric" % account["line"])
        require(isinstance(account["current"], (int, float)), "account %s current must be numeric" % account["line"])

    sentences = case["commentary"].get("sentences", [])
    require(8 <= len(sentences) <= 14, "commentary needs 8 to 14 sentences, found %d" % len(sentences))
    sentence_ids = set()
    for sentence in sentences:
        require("id" in sentence and "text" in sentence, "every commentary sentence needs 'id' and 'text'")
        require(sentence["id"] not in sentence_ids, "duplicate sentence id '%s'" % sentence["id"])
        sentence_ids.add(sentence["id"])

    movements = dict((account["line"], round(float(account["current"]) - float(account["prior"]), 2))
                     for account in accounts)

    for subtotal in case.get("subtotals", []):
        for field in ("key", "label", "lines"):
            require(field in subtotal, "subtotal %s is missing '%s'" % (subtotal.get("key", "?"), field))
        require(isinstance(subtotal["lines"], list) and subtotal["lines"],
                "subtotal %s needs a non-empty 'lines' list" % subtotal["key"])
        for line in subtotal["lines"]:
            require(line in seen_lines,
                    "subtotal %s names line '%s', which is not in the account table" % (subtotal["key"], line))

    sources = case.get("sources")
    require(isinstance(sources, list) and sources,
            "a case needs a 'sources' inventory: the documents a reviewer could ask for. A "
            "challenge may only cite a document this list carries.")
    source_ids = set()
    for source in sources:
        for field in ("id", "name", "kind"):
            require(field in source, "source %s is missing '%s'" % (source.get("id", "?"), field))
        require(source["id"] not in source_ids, "duplicate source id '%s'" % source["id"])
        source_ids.add(source["id"])
        require(source["kind"] in SOURCE_KINDS,
                "source %s has kind '%s', which is not one of: %s"
                % (source["id"], source["kind"], ", ".join(SOURCE_KINDS)))
        for line in source.get("lines", []):
            require(line in seen_lines,
                    "source %s names line '%s', which is not in the account table"
                    % (source["id"], line))

    key = case["answer_key"]
    require(8 <= len(key) <= 12, "the answer key needs 8 to 12 defects, found %d" % len(key))
    defect_ids = set()
    types_used = set()
    tags_used = set()
    for defect in key:
        for field in ("id", "type", "line", "amount", "claim", "correct", "match"):
            require(field in defect, "defect %s is missing '%s'" % (defect.get("id", "?"), field))
        require(defect["id"] not in defect_ids, "duplicate defect id '%s'" % defect["id"])
        defect_ids.add(defect["id"])
        require(defect["type"] in DEFECT_TYPES,
                "defect %s has unknown type '%s'" % (defect["id"], defect["type"]))
        require(defect["type"] not in types_used,
                "defect type '%s' appears twice in one case; each case uses distinct kinds" % defect["type"])
        types_used.add(defect["type"])
        require(defect["line"] in seen_lines,
                "defect %s cites line '%s', which is not in the account table" % (defect["id"], defect["line"]))
        if defect.get("sentence"):
            require(defect["sentence"] in sentence_ids,
                    "defect %s cites sentence '%s', which is not in the commentary" % (defect["id"], defect["sentence"]))
        require(isinstance(defect["match"].get("aliases"), list) and defect["match"]["aliases"],
                "defect %s needs match.aliases" % defect["id"])
        require(isinstance(defect["match"].get("keywords"), list) and defect["match"]["keywords"],
                "defect %s needs match.keywords" % defect["id"])

        tag = defect_tag(defect)
        require(tag in CHALLENGE_TAGS,
                "defect %s has tag '%s', which is not one of: %s" % (
                    defect["id"], tag, ", ".join(CHALLENGE_TAGS)))
        tags_used.add(tag)

        # Rule 3. The challenge cites the named account's movement, so the
        # answer key's own amount either is that movement or says what it is.
        movement = abs(movements[defect["line"]])
        amount = abs(float(defect["amount"]))
        focus = defect.get("focus")
        if round(amount, 2) != round(movement, 2):
            require(isinstance(focus, dict) and "amount" in focus and focus.get("what"),
                    "defect %s cites %s against account %s, which moved %s. A defect whose amount is "
                    "not the account's own movement must carry focus.amount and focus.what naming "
                    "what that figure is, so the challenge can say it out loud."
                    % (defect["id"], format_amount(amount), defect["line"], format_amount(movement)))
            require(round(abs(float(focus["amount"])), 2) == round(amount, 2),
                    "defect %s has focus.amount %s and amount %s; they must agree"
                    % (defect["id"], focus["amount"], defect["amount"]))
        for reference in defect.get("evidence_refs", []):
            require(resolve_source(case, reference) is not None,
                    "defect %s cites evidence '%s', which is not in this case's sources inventory"
                    % (defect["id"], reference))

        counterparty = defect.get("counterparty")
        if counterparty:
            require(isinstance(counterparty, dict) and counterparty.get("line"),
                    "defect %s has a counterparty without a line" % defect["id"])
            require(counterparty["line"] in seen_lines,
                    "defect %s names counterparty line '%s', which is not in the account table"
                    % (defect["id"], counterparty["line"]))
            require(counterparty["line"] != defect["line"],
                    "defect %s names itself as its own counterparty" % defect["id"])

    shapes_used = set()
    for distractor in case.get("distractors", []):
        for field in ("id", "line", "text", "why_wrong", "shape"):
            require(field in distractor, "distractor %s is missing '%s'" % (distractor.get("id", "?"), field))
        require(distractor["line"] in seen_lines,
                "distractor %s cites line '%s', which is not in the account table" % (distractor["id"], distractor["line"]))
        require(distractor["id"] not in defect_ids, "distractor id '%s' collides with a defect id" % distractor["id"])
        if distractor.get("sentence"):
            require(distractor["sentence"] in sentence_ids,
                    "distractor %s cites sentence '%s', which is not in the commentary"
                    % (distractor["id"], distractor["sentence"]))
        shape = distractor["shape"]
        require(shape in DISTRACTOR_SHAPES,
                "distractor %s has shape '%s', which is not one of: %s"
                % (distractor["id"], shape, ", ".join(sorted(DISTRACTOR_SHAPES))))
        require(shape not in shapes_used,
                "shape '%s' is planted twice in one case. Pilot one used one shape for every weak "
                "challenge and the reviewers learned to refuse it on sight, so a case now plants "
                "each shape at most once." % shape)
        shapes_used.add(shape)

        tag = distractor.get("tag")
        require(tag in CHALLENGE_TAGS,
                "distractor %s needs a tag from: %s" % (distractor["id"], ", ".join(CHALLENGE_TAGS)))
        require(tag in tags_used,
                "distractor %s carries tag '%s', which no defect in this case carries. A tag that "
                "appears only on the planted weak challenges gives them away."
                % (distractor["id"], tag))

        movement = abs(movements[distractor["line"]])
        amount = abs(float(distractor.get("amount") or 0))
        if shape == "bad_recomputation":
            require(round(amount, 2) != round(movement, 2),
                    "distractor %s is shaped as a wrong recomputation but cites the account's real "
                    "movement of %s, so there is nothing for a reviewer to recompute"
                    % (distractor["id"], format_amount(movement)))
        else:
            require(round(amount, 2) == round(movement, 2),
                    "distractor %s cites %s against account %s, which moved %s. Only a "
                    "bad_recomputation weak challenge may cite an amount that does not tie."
                    % (distractor["id"], format_amount(amount), distractor["line"], format_amount(movement)))
    return True


def defect_tag(defect):
    """The one-word category a defect's challenge carries. Explicit, or by type."""
    return defect.get("tag") or DEFAULT_TAG_BY_TYPE.get(defect["type"], "amount")


def movement_table(case):
    """Prior, current, variance and percent for every account. Computed here."""
    rows = []
    for account in case["accounts"]:
        prior = float(account["prior"])
        current = float(account["current"])
        variance = round(current - prior, 2)
        if prior == 0:
            percent = None
        else:
            percent = round((variance / abs(prior)) * 100.0, 1)
        rows.append({
            "line": account["line"],
            "name": account["name"],
            "prior": prior,
            "current": current,
            "variance": variance,
            "percent": percent,
            "material": is_material(case, variance, prior),
        })
    return rows


def subtotal_table(case):
    """The subtotals a ratio test needs, computed from the same balances.

    Pilot one asked reviewers to test a ratio claim and then made them add up
    seven expense lines by hand to do it. A reviewer who will not do that
    arithmetic in their head simply takes the memo's word for the ratio, which
    is the failure the tool is supposed to be measuring rather than causing.
    """
    index = account_index(case)
    rows = []
    for subtotal in case.get("subtotals", []):
        prior = round(sum(float(index[line]["prior"]) for line in subtotal["lines"]), 2)
        current = round(sum(float(index[line]["current"]) for line in subtotal["lines"]), 2)
        variance = round(current - prior, 2)
        percent = None if prior == 0 else round((variance / abs(prior)) * 100.0, 1)
        rows.append({
            "key": subtotal["key"],
            "label": subtotal["label"],
            "lines": list(subtotal["lines"]),
            "note": subtotal.get("note", ""),
            "prior": prior,
            "current": current,
            "variance": variance,
            "percent": percent,
        })
    return rows


def materiality_rule(case):
    """The two-part threshold in one sentence, with the word 'both' in it.

    Pilot one wrote it as "exceeds $25,000 and 10 percent" and every reviewer
    had to guess whether the and was conjunctive. It is. This sentence is the
    only wording any surface prints, so the guess cannot come back.
    """
    materiality = case.get("materiality", {})
    return (
        "Commentary is required only where a movement passes BOTH tests: more than %s AND at "
        "least %s percent of the prior balance. Both, not either. A line that clears one test and "
        "fails the other does not require commentary."
        % (format_amount(materiality.get("amount")), materiality.get("percent"))
    )


def is_material(case, variance, prior):
    """The case's own two-part threshold: dollars and percent, both required."""
    threshold_amount = float(case["materiality"].get("amount", 0))
    threshold_percent = float(case["materiality"].get("percent", 0))
    if abs(variance) < threshold_amount:
        return False
    if prior == 0:
        return True
    return abs(variance / abs(prior)) * 100.0 >= threshold_percent


def account_index(case):
    return dict((account["line"], account) for account in case["accounts"])


def source_index(case):
    """Source id -> the source entry."""
    return dict((source["id"], source) for source in case.get("sources", []))


def resolve_source(case, reference):
    """Return the source id a reference points at, or None.

    A reference resolves on the source's id, or on its name appearing in the
    reference text. Anything else is a document this case does not carry, and a
    challenge citing one is dropped rather than shown to a reviewer who would
    then go looking for it.
    """
    if not reference:
        return None
    text = str(reference).strip().lower()
    if not text:
        return None
    for source in case.get("sources", []):
        if text == str(source["id"]).strip().lower():
            return source["id"]
    for source in case.get("sources", []):
        name = str(source["name"]).strip().lower()
        if name and (name in text or text in name):
            return source["id"]
    return None


def account_movements(case):
    """Line -> current less prior. The only amount a challenge may cite."""
    return dict((account["line"], round(float(account["current"]) - float(account["prior"]), 2))
                for account in case["accounts"])


def sentence_ids(case):
    return set(sentence["id"] for sentence in case["commentary"].get("sentences", []))


def _amount_ties(amount, movement):
    return round(abs(float(amount)), 2) == round(abs(float(movement)), 2)


def validate_challenge_bindings(challenge, case):
    """Every identifier and amount a challenge binds, checked against this case.

    Returns a list of failure strings, empty when the challenge binds cleanly.
    The caller decides what to do with them; `challenger.validate_challenges`
    drops the challenge and writes the reasons into the session log.

    The amount rule is the one the audit broke. It used to be enough for the
    question text to name some other account, and then any figure at all passed,
    including 999,999,999 against a line that moved 372,000. The amount now has
    to be the movement of the account it is cited against, or the movement of
    the other account the text names. A figure tied to neither is not a
    recomputation a reviewer can run.
    """
    failures = []
    accounts = account_index(case)
    movements = account_movements(case)

    line = str(challenge.get("line", "")).strip()
    if line not in accounts:
        failures.append("cites account '%s', which is not in the table" % line)

    truth = challenge.get("truth") or {}
    # The one challenge allowed to cite a figure that does not tie: a planted
    # weak challenge whose whole shape is a wrong recomputation the table
    # refutes. A model challenge cannot claim this, because a model challenge
    # never carries a planted truth block.
    deliberate_misquote = (truth.get("kind") == "distractor"
                           and truth.get("shape") == "bad_recomputation")

    amount = challenge.get("amount")
    if isinstance(amount, bool) or not isinstance(amount, (int, float)):
        failures.append("no numeric amount, so the challenge cannot be recomputed")
    elif deliberate_misquote:
        pass
    elif line in accounts and not _amount_ties(amount, movements[line]):
        named = _other_account_named(challenge.get("question"), line, accounts)
        if not named:
            failures.append(
                "cites %s against account %s, which moved %s, and names no other account the "
                "figure could belong to" % (format_amount(abs(float(amount))), line,
                                            format_amount(abs(movements[line]))))
        elif not _amount_ties(amount, movements[named]):
            failures.append(
                "cites %s against account %s, which moved %s. The text names account %s, which "
                "moved %s, so the figure ties to neither account and there is nothing to "
                "recompute." % (format_amount(abs(float(amount))), line,
                                format_amount(abs(movements[line])), named,
                                format_amount(abs(movements[named]))))

    sentence = challenge.get("sentence")
    if sentence not in (None, "") and sentence not in sentence_ids(case):
        failures.append("cites sentence '%s', which is not in this case's commentary" % sentence)

    tag = challenge.get("tag")
    if tag not in (None, "") and tag not in CHALLENGE_TAGS:
        failures.append("carries tag '%s', which is not one of: %s" % (tag, ", ".join(CHALLENGE_TAGS)))

    for reference in challenge.get("evidence_refs") or []:
        if resolve_source(case, reference) is None:
            failures.append("cites evidence '%s', which is not in this case's sources inventory"
                            % reference)
    return failures


def _other_account_named(question, line, accounts):
    """The other account from the table that the challenge text names, if any."""
    text = (question or "").lower()
    for other_line, account in accounts.items():
        if other_line == line:
            continue
        if other_line.lower() in text or account["name"].lower() in text:
            return other_line
    return None


def reviewer_view(case):
    """The only case payload a reviewer is ever sent before they commit.

    The answer key and the distractors are removed here. Every surface, the web
    page and the command line alike, calls this function rather than handling
    the raw case, so there is one place to audit and one place to break.
    """
    return {
        "id": case["id"],
        "title": case["title"],
        "notice": case.get("notice", ""),
        "company": {
            "name": case["company"]["name"],
            "profile": case["company"].get("profile", ""),
        },
        "period": case["period"],
        "materiality": case["materiality"],
        "materiality_rule": materiality_rule(case),
        "margin_definition": case.get("margin_definition", ""),
        "accounts": movement_table(case),
        "subtotals": subtotal_table(case),
        "commentary": {
            "author": case["commentary"].get("author", ""),
            "sentences": case["commentary"]["sentences"],
        },
        "defects_present": len(case["answer_key"]),
    }


def format_amount(value):
    """$1,234 or ($1,234). Whole dollars, because the cases are whole dollars."""
    if value is None:
        return "n/a"
    negative = value < 0
    text = "${:,.0f}".format(abs(value))
    return "(%s)" % text if negative else text


def format_percent(value):
    if value is None:
        return "n/a"
    return "{:.1f}%".format(value)
