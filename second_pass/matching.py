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

Every match carries its evidence into the session log, so a facilitator reading
the log afterwards can see exactly why a finding was scored the way it was, and
can overrule it. Overrides are part of the design, not a workaround: the tool
does not get the last word on a human's reasoning either.
"""

import re

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


def _keyword_hit(normalized_text, keywords):
    for keyword in keywords:
        needle = normalize(keyword)
        if _contains(normalized_text, needle):
            return keyword
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

    Where a finding could match more than one defect, the one with the most
    evidence wins, and ties break toward the defect appearing first in the key.
    """
    normalized = normalize(finding_text)
    if not normalized:
        return None, {"reason": "empty finding"}

    best = None
    for defect in case["answer_key"]:
        aliases = defect["match"]["aliases"]
        keywords = defect["match"]["keywords"]
        alias = _alias_hit(normalized, aliases)
        if not alias:
            continue
        keyword = _keyword_hit(normalized, keywords)
        amount = _amount_hit(normalized, defect.get("amount"))
        if not keyword and not amount:
            continue
        score = (1 if keyword else 0) + (1 if amount else 0)
        evidence = {
            "defect_id": defect["id"],
            "defect_type": defect["type"],
            "alias_matched": alias,
            "keyword_matched": keyword,
            "amount_matched": amount,
            "score": score,
        }
        if best is None or score > best["score"]:
            best = evidence
    if best is None:
        return None, {"reason": "no defect matched", "normalized": normalized}
    return best["defect_id"], best


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

    Returns caught defect ids, the per-finding audit trail, and the findings
    that matched nothing, which are the reviewer's false challenges.
    """
    caught = []
    trail = []
    false_challenges = []
    for index, text in enumerate(findings):
        defect_id, evidence = match_finding(text, case)
        record = {
            "index": index,
            "text": text,
            "matched_defect": defect_id,
            "evidence": evidence,
        }
        if defect_id and defect_id not in caught:
            caught.append(defect_id)
        elif defect_id and defect_id in caught:
            record["note"] = "duplicate of a defect already caught, not counted twice"
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
    }
