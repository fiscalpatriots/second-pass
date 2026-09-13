"""Matching a reviewer's own words to the planted defects.

A reviewer writes findings in free text. Scoring needs to know which planted
defect each finding refers to, and the answer has to be reproducible: the same
finding text against the same case gives the same match tomorrow, on somebody
else's machine, with no model in the loop.

The rule is deliberately strict and deliberately explainable.

    A finding matches a defect when it points at the account
    AND says something about what is wrong with it.

"Points at the account" means the text carries one of the defect's aliases: the
account code, the account name, or a phrase the case author listed. "Says
something about what is wrong" means the text carries one of the defect's
keywords, or cites the defect amount. Naming an account and nothing else is not
a finding, it is a shrug.

Matching is not correctness, and the two are now separated in the return value.
The external audit of 12 September 2026 wrote "Account 6000 has movement 72500.
I accept the commentary as written." into the finding box and the tool scored it
as a detected defect: the alias hit on 6000, and the case author had listed the
amount itself among the defect keywords, so a sentence that explicitly refuses
the defect satisfied both legs of the rule. Naming the account and restating its
movement is identification. Saying the commentary is fine is the opposite of a
finding.

So a match now carries a `status` alongside its evidence.

    supported            the text identifies the account and asserts something
                         is wrong with it. This is the only status that counts
                         as a detected defect.
    accepts_the_position the text identifies the account and then accepts the
                         commentary, or withdraws. Never a detected defect.
    unsupported          the text identifies the account and restates a figure
                         and nothing else. Not a detected defect; it goes to a
                         person to adjudicate, because a reviewer may have meant
                         a challenge that the words do not carry.

Numeric keywords are the reason the third status exists. Several case files list
the defect amount among the keywords, which is useful for finding the account
but says nothing about whether anything is wrong, so a numeric keyword is
counted as identification and never as an assertion.

Every match carries its evidence into the session log, so a facilitator reading
the log afterwards can see exactly why a finding was scored the way it was, and
can overrule it. Overrides are part of the design, not a workaround: the tool
does not get the last word on a human's reasoning either.
"""

import re

# A keyword that is only a number, a thousands separator, a decimal point or a
# 'k' suffix. It identifies the movement; it does not assert a defect.
_NUMERIC_KEYWORD = re.compile(r"^[0-9][0-9,\.]*k?$")

# Phrases that accept the commentary, or withdraw a position already taken. A
# finding carrying one of these and no contradicting assertion is not a finding.
ACCEPTANCE_PATTERNS = (
    r"accepts? (?:the |this )?(?:commentary|memo|sentence|explanation|wording|disclosure|as written)",
    r"accepts? (?:it|this|that) as written",
    r"as written and (?:i|we) (?:accept|agree)",
    r"(?:i|we) accept(?:s)? (?:it|this|that)?$",
    r"(?:i|we) agree with (?:the )?(?:commentary|memo|sentence|explanation|wording)",
    r"(?:i|we) withdraw",
    r"withdraw (?:my|our|the) (?:original )?(?:concern|finding|challenge|point|position)",
    r"no exception(?:s)? (?:taken|noted|here)?",
    r"nothing to challenge",
    r"no (?:issue|problem|concern)(?:s)? (?:here|with this|noted)?",
    r"looks (?:fine|correct|right|reasonable|ok|okay)",
    r"(?:is|are|seems|appears) (?:fine|correct|reasonable|adequate|supported and fine)",
    r"no change (?:is )?(?:needed|required)",
    r"(?:i|we) (?:am|are) satisfied",
    r"stands as written",
)
_ACCEPTANCE_RE = [re.compile(pattern) for pattern in ACCEPTANCE_PATTERNS]

STATUS_SUPPORTED = "supported"
STATUS_ACCEPTS = "accepts_the_position"
STATUS_UNSUPPORTED = "unsupported"

# The two statuses that are not a detected defect but are also not nothing. A
# person decides what they were, and the tool says so rather than guessing.
STATUSES_FOR_ADJUDICATION = (STATUS_ACCEPTS, STATUS_UNSUPPORTED)

_PUNCTUATION = re.compile(r"[^a-z0-9\.\- ]+")
_SPACES = re.compile(r"\s+")


def normalize(text):
    """Lowercase, strip currency and thousands separators, collapse spaces."""
    if not text:
        return ""
    lowered = str(text).lower()
    lowered = lowered.replace("$", " ").replace(",", "")
    lowered = _PUNCTUATION.sub(" ", lowered)
    return _SPACES.sub(" ", lowered).strip()


def _contains(normalized_text, needle):
    """Substring search with a word boundary on the left only.

    The left boundary stops 'up' from matching inside 'unsupported', which is
    the sort of quiet false positive that would inflate a catch rate. The right
    side is deliberately open, because several keywords are stems: 'declin' has
    to match declines, declined and declining without three entries in the file.
    """
    if not needle:
        return False
    if needle.replace(".", "").isdigit():
        pattern = r"(?<![a-z0-9])" + re.escape(needle) + r"(?![0-9])"
    else:
        pattern = r"(?<![a-z0-9])" + re.escape(needle)
    return re.search(pattern, normalized_text) is not None


def _alias_hit(normalized_text, aliases):
    for alias in aliases:
        needle = normalize(alias)
        if _contains(normalized_text, needle):
            return alias
    return None


def is_numeric_keyword(keyword):
    """A keyword that only restates a figure. Identification, not an assertion."""
    return bool(_NUMERIC_KEYWORD.match(normalize(keyword).replace(" ", "")))


def assertion_keywords(defect):
    """The keywords that actually claim something is wrong with the account."""
    return [keyword for keyword in defect["match"]["keywords"]
            if not is_numeric_keyword(keyword)]


def first_assertion_keyword(defect):
    words = assertion_keywords(defect)
    return words[0] if words else None


def _keyword_hit(normalized_text, keywords):
    for keyword in keywords:
        needle = normalize(keyword)
        if _contains(normalized_text, needle):
            return keyword
    return None


def accepts_the_position(text):
    """Does the text accept the commentary, or withdraw a position?

    Returns the phrase that matched, or None. The phrase goes into the evidence
    block so a facilitator can see exactly which words the tool read as an
    acceptance and overrule it.
    """
    normalized = normalize(text)
    if not normalized:
        return None
    for pattern in _ACCEPTANCE_RE:
        found = pattern.search(normalized)
        if found:
            return found.group(0).strip()
    return None


def _amount_hit(normalized_text, amount):
    """The amount as a bare number, with or without decimals or separators."""
    if amount in (None, 0):
        return None
    magnitude = abs(float(amount))
    candidates = set()
    candidates.add("{:.0f}".format(magnitude))
    candidates.add("{:,.0f}".format(magnitude).replace(",", ""))
    if magnitude >= 1000:
        candidates.add("{:.1f}".format(magnitude / 1000.0).rstrip("0").rstrip(".") + "k")
    for candidate in candidates:
        if candidate and re.search(r"(?<![0-9])" + re.escape(candidate) + r"(?![0-9])", normalized_text):
            return candidate
    return None


def match_finding(finding_text, case):
    """Return (defect_id or None, evidence dict) for one written finding.

    The defect id is returned whenever the text points at that defect's account
    and carries something about it. Whether that counts as a detected defect is
    a separate question, answered by `evidence["status"]` and by the
    `counts_as_detection` flag beside it. A caller that reads the id and ignores
    the status is counting acceptances as catches, which is the defect the
    September audit found.

    Where a finding could match more than one defect, a supported match beats an
    unsupported one, then the one with the most evidence wins, and ties break
    toward the defect appearing first in the key.
    """
    normalized = normalize(finding_text)
    if not normalized:
        return None, {"reason": "empty finding", "status": None,
                      "counts_as_detection": False}

    acceptance = accepts_the_position(finding_text)

    best = None
    for defect in case["answer_key"]:
        aliases = defect["match"]["aliases"]
        keywords = defect["match"]["keywords"]
        alias = _alias_hit(normalized, aliases)
        if not alias:
            continue
        keyword = _keyword_hit(normalized, keywords)
        assertion = _keyword_hit(normalized, assertion_keywords(defect))
        amount = _amount_hit(normalized, defect.get("amount"))
        if not keyword and not amount:
            continue
        if acceptance:
            status = STATUS_ACCEPTS
        elif assertion:
            status = STATUS_SUPPORTED
        else:
            status = STATUS_UNSUPPORTED
        score = (1 if assertion else 0) + (1 if amount or keyword else 0)
        evidence = {
            "defect_id": defect["id"],
            "defect_type": defect["type"],
            "alias_matched": alias,
            "keyword_matched": keyword,
            "assertion_matched": assertion,
            "amount_matched": amount,
            "acceptance_matched": acceptance,
            "status": status,
            "counts_as_detection": status == STATUS_SUPPORTED,
            "needs_adjudication": status in STATUSES_FOR_ADJUDICATION,
            "why": _why(status, alias, assertion, acceptance),
            "score": score,
        }
        rank = (1 if status == STATUS_SUPPORTED else 0, score)
        if best is None or rank > best["_rank"]:
            evidence["_rank"] = rank
            best = evidence
    if best is None:
        return None, {"reason": "no defect matched", "normalized": normalized,
                      "status": None, "counts_as_detection": False}
    best.pop("_rank", None)
    return best["defect_id"], best


def _why(status, alias, assertion, acceptance):
    if status == STATUS_ACCEPTS:
        return ("names the account through '%s' and then accepts the commentary ('%s'), so it is "
                "not a detected defect. A person decides what the reviewer meant."
                % (alias, acceptance))
    if status == STATUS_SUPPORTED:
        return "names the account through '%s' and asserts '%s'" % (alias, assertion)
    return ("names the account through '%s' and restates a figure, but asserts nothing about it, "
            "so it is not a detected defect. A person decides what the reviewer meant." % alias)


def match_distractor(finding_text, case):
    """Did the reviewer raise one of the planted false leads on their own?"""
    normalized = normalize(finding_text)
    for distractor in case.get("distractors", []):
        aliases = [distractor["line"]]
        account = next((a for a in case["accounts"] if a["line"] == distractor["line"]), None)
        if account:
            aliases.append(account["name"])
        if _alias_hit(normalized, aliases):
            return distractor["id"]
    return None


def score_findings(findings, case):
    """Map a list of written findings onto the answer key.

    Returns the defects detected, the per-finding audit trail, the findings that
    matched nothing, and the findings that matched a defect without supporting
    it. Only the first list is a catch. The last one is the adjudication queue,
    and it exists because the tool cannot tell a reviewer who mistyped from a
    reviewer who genuinely accepted the memo.
    """
    caught = []
    trail = []
    false_challenges = []
    for_adjudication = []
    for index, text in enumerate(findings):
        defect_id, evidence = match_finding(text, case)
        record = {
            "index": index,
            "text": text,
            "matched_defect": defect_id,
            "status": evidence.get("status"),
            "counts_as_detection": bool(evidence.get("counts_as_detection")),
            "evidence": evidence,
        }
        if defect_id and evidence.get("counts_as_detection"):
            if defect_id not in caught:
                caught.append(defect_id)
            else:
                record["note"] = "duplicate of a defect already caught, not counted twice"
        elif defect_id:
            record["note"] = evidence.get("why")
            for_adjudication.append(record)
        else:
            distractor_id = match_distractor(text, case)
            if distractor_id:
                record["matched_distractor"] = distractor_id
            false_challenges.append(record)
        trail.append(record)
    return {
        "caught": caught,
        "trail": trail,
        "false_challenges": false_challenges,
        "for_adjudication": for_adjudication,
    }
