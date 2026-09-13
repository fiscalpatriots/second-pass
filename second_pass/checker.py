"""The Second Pass checker, in Python.

This is a port of the contract published at ``checker.html`` and documented in
``CHECKER.md``: the same six steps, the same four statuses, the same reviewer
queue.  The browser runs it on a paste; this module runs it on two files, in a
script, on a build server, or inside the trainer in this repository.

Where the browser and this module could disagree, the browser's contract wins,
and any divergence that could not be closed is written down in
``CONTRACT-DIVERGENCE.md`` at the repository root.

The public surface is small:

    result = run_check(ledger_text, memo_text, ratios="", dollar_floor=25000,
                       percent_floor=10, rule="both", zero_prior="owing")
    result.stats        the coverage counts
    result.sents        one record per sentence, each carrying its one status
    result.rows         the findings table, in the order the page prints it
    result.queue        the reviewer's queue
    result.csv()        the CSV export, same column order as the page
    result.json_record()  the machine readable record
    result.reviewer_prompt()  Prompt 2 for this run

Nothing here reads a file, prints anything or touches the network.
"""

from __future__ import annotations

import json
import math
import re
from datetime import datetime, timezone

__all__ = [
    "run_check",
    "CheckResult",
    "parse_ledger",
    "split_sentences",
    "figures",
    "CONTRACT_VERSION",
]

# The contract this file implements, as published in the browser.
CONTRACT_VERSION = "second-pass-checker/1.0 (checker.html, 13 September 2026)"


# ============================================================ helpers

def _js_round(x: float) -> float:
    """JavaScript's Math.round: ties go toward positive infinity."""
    return math.floor(x + 0.5)


def _fixed(x: float, digits: int) -> str:
    """Number.prototype.toFixed for the values this module produces."""
    if digits == 0:
        return str(int(_js_round(x))) if x >= 0 else str(-int(_js_round(-x)))
    q = 10 ** digits
    scaled = _js_round(abs(x) * q) / q
    s = f"{scaled:.{digits}f}"
    return ("-" + s) if x < 0 else s


_COMMA_RE = re.compile(r"\B(?=(\d{3})+(?!\d))")


def money(v):
    if v is None or not isinstance(v, (int, float)) or not math.isfinite(v):
        return "n/a"
    neg = v < 0
    a = abs(v)
    rounded = _js_round(a * 100) / 100
    digits = 0 if abs(a - _js_round(a)) < 0.005 else 2
    s = _fixed(rounded, digits)
    s = _COMMA_RE.sub(",", s)
    return ("-$" if neg else "$") + s


def pct_txt(v):
    if v is None or not isinstance(v, (int, float)) or not math.isfinite(v):
        return "n/a"
    return _fixed(_js_round(v * 10) / 10, 1) + "%"


_NUM_OK = re.compile(r"^\d*\.?\d+\Z")


def parse_num(s):
    """NaN is returned as None, which is how a missing number reads here."""
    if s is None:
        return None
    t = str(s).strip()
    if not t:
        return None
    neg = False
    if t.startswith("(") and t.endswith(")") and "\n" not in t:
        neg = True
        t = t[1:-1]
    t = re.sub(r"[$ \s,]", "", t)
    t = re.sub(r"%\Z", "", t)
    if t[:1] == "-":
        neg = not neg
        t = t[1:]
    elif t[:1] == "+":
        t = t[1:]
    if not _NUM_OK.match(t):
        return None
    try:
        v = float(t)
    except ValueError:
        return None
    if not math.isfinite(v):
        return None
    return -v if neg else v


def _is_num(s) -> bool:
    return parse_num(s) is not None


def split_fields(line: str):
    out = []
    if "\t" in line:
        out = line.split("\t")
    else:
        cur = ""
        q = False
        i = 0
        while i < len(line):
            ch = line[i]
            if ch == '"':
                if q and i + 1 < len(line) and line[i + 1] == '"':
                    cur += '"'
                    i += 1
                else:
                    q = not q
            elif ch == "," and not q:
                out.append(cur)
                cur = ""
            else:
                cur += ch
            i += 1
        out.append(cur)
    out = [x.strip() for x in out]
    if len(out) < 3:
        alt = [x.strip() for x in re.split(r"\s{2,}", line)]
        alt = [x for x in alt if x != ""]
        if len(alt) > len(out):
            out = alt
    return out


# ============================================================ ledger

STOP = {"and", "the", "for", "its", "per", "from", "with", "into", "that", "this",
        "all", "but", "not", "other", "total", "net"}


def de_smart(s: str) -> str:
    """Word's curly quotes, its dashes and its ellipsis, flattened first."""
    s = str(s)
    s = re.sub(r"[\u2018\u2019\u201a\u201b\u2032]", "'", s)
    s = re.sub(r"[\u201c\u201d\u201e\u201f\u2033]", '"', s)
    s = re.sub(r"[\u2013\u2014\u2212]", "-", s)
    s = s.replace("\u2026", "...")
    s = re.sub(r"[\u00a0\u2007\u202f]", " ", s)
    return s


SECTION_ONLY = re.compile(
    r"^(?:less\s+)?(income|revenue|sales|trading income|other income|operating income|"
    r"cost of goods sold|cost of sales|cogs|direct costs|expenses|operating expenses|"
    r"overheads|administrative expenses|payroll expenses|other expenses|"
    r"other income and expenses|assets|liabilities|equity)\b[\s:.\-]*\Z", re.I)
TOTALWORD = re.compile(r"^total\b", re.I)
GRAND = re.compile(
    r"^(gross profit|gross margin|net profit|net income|net loss|net operating income|"
    r"net other income|net earnings|operating profit|profit before tax|"
    r"profit for the (month|period|year)|net movement)\b", re.I)
HEADERWORD = re.compile(
    r"(^|\W)(prior|current|previous|prev|last|this|py|pp|comparative|change|variance|var|"
    r"budget|actual|ytd|period|amount|balance|jan(uary)?|feb(ruary)?|mar(ch)?|apr(il)?|may|"
    r"jun(e)?|jul(y)?|aug(ust)?|sep(t|tember)?|oct(ober)?|nov(ember)?|dec(ember)?|q[1-4]|fy)"
    r"(\W|\Z)|%|\b(19|20)\d{2}\b", re.I | re.A)
DERIVEDCOL = re.compile(
    r"(change|variance|\bvar\b|%|percent|\bpct\b|diff|movement|\bfav\b|\bunfav\b)", re.I | re.A)
MONTHNUM = {"jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6, "jul": 7,
            "aug": 8, "sep": 9, "sept": 9, "oct": 10, "nov": 11, "dec": 12}


def month_key(s):
    t = str(s).lower()
    y = re.search(r"\b(19|20)\d{2}\b", t)
    year = int(y.group(0)) if y else None
    m = re.search(r"\b(jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\b", t)
    if not m and year is None:
        return None
    if not m:
        return year * 12
    return (2000 if year is None else year) * 12 + MONTHNUM[m.group(1)]


def guess_cols(labels):
    """The reader's own guess at which numeric column is prior and which current."""
    total = len(labels)
    cand = [i for i in range(total) if not DERIVEDCOL.search(labels[i])]
    if len(cand) < 2:
        cand = list(range(total))
    pi = -1
    ci = -1
    for j in cand:
        low = str(labels[j]).lower()
        if pi < 0 and re.search(
                r"(prior|previous|\bprev\b|last month|last year|last period|\bpy\b|\bpp\b|"
                r"comparative|budget)", low):
            pi = j
        if ci < 0 and re.search(r"(current|this month|this year|this period|\bactual\b|\bytd\b)", low):
            ci = j
    if pi > -1 and ci > -1 and pi != ci:
        return {"p": pi, "c": ci}
    keyed = []
    for j in cand:
        k = month_key(labels[j])
        if k is not None:
            keyed.append({"i": j, "k": k})
    distinct = {x["k"] for x in keyed}
    if len(keyed) >= 2 and len(distinct) >= 2:
        keyed.sort(key=lambda x: x["k"])
        return {"p": keyed[0]["i"], "c": keyed[-1]["i"]}
    if pi > -1:
        for c in cand:
            if c != pi:
                return {"p": pi, "c": c}
    if ci > -1:
        for c in reversed(cand):
            if c != ci:
                return {"p": c, "c": ci}
    return {"p": cand[0], "c": cand[1] if len(cand) > 1 else cand[0]}


_ACCT_SPLIT = re.compile(r"^(\d{2,8}[A-Za-z]?)\s*[\s.:\u00b7-]\s*(\S.*)\Z", re.S)


def acct_shape(name, row):
    num = ""
    nm = name
    mm = _ACCT_SPLIT.match(nm)
    if mm:
        num = mm.group(1)
        nm = mm.group(2)
    nm = re.sub(r"\s+", " ", nm)
    nm = re.sub(r"^[,\s]+", "", nm)
    nm = re.sub(r"[,\s]+\Z", "", nm)
    lowered = re.sub(r"[^a-z0-9\s]", " ", nm.lower())
    words = [w for w in re.split(r"\s+", lowered) if len(w) >= 3 and w not in STOP]
    flat = re.sub(r"\s+", " ", lowered).strip(" ")
    return {"num": num, "name": nm, "words": words, "flat": flat,
            "two": " ".join(flat.split(" ")[:2]), "row": row}


class Account:
    """One ledger line, and everything the run learns about it."""

    __slots__ = ("num", "name", "prior", "cur", "change", "pct", "words", "flat",
                 "two", "row", "section", "sent", "legs", "clears", "dup")

    def __init__(self, **kw):
        for k in self.__slots__:
            setattr(self, k, kw.get(k))
        self.sent = []
        self.legs = {"d": False, "p": False}
        self.clears = False
        self.dup = False


def acct_id(a) -> str:
    return (a.num + " " if a.num else "") + a.name


def parse_ledger(text, choice=None):
    """The account lines, the section totals, the column labels, and every row
    the reader could not use, with the reason."""
    lines = de_smart(text).split("\n")
    lines = [ln[:-1] if ln.endswith("\r") else ln for ln in lines]
    raws = []
    for idx, raw in enumerate(lines):
        line = raw.strip()
        if not line:
            continue
        if re.match(r"^[-=_~\s|+*.]+\Z", line):
            continue
        f = split_fields(line)
        while f and (f[-1] == "" or f[-1] == "*"):
            f.pop()
        if not f:
            continue
        # "100,000" split on commas is indistinguishable from two columns holding
        # 100 and 000. The row is refused rather than read on a guess.
        amb = False
        if "\t" not in line and "," in line:
            for z in range(1, len(f)):
                if re.match(r"^\$?\d{3}\Z", f[z]) and re.match(r"^\$?[-(]?\d+\)?\Z", f[z - 1]):
                    amb = True
        k = -1
        tail = 0
        for j in range(len(f) - 1, -1, -1):
            if f[j] != "" and _is_num(f[j]):
                k = j
                tail += 1
            else:
                break
        raws.append({"n": idx + 1, "line": line, "f": f, "k": k, "tail": tail, "amb": amb})

    # how many numeric columns this ledger runs: the most common trailing run
    counts = {}
    for r in raws:
        if not r["amb"] and r["tail"] >= 2 and r["k"] >= 1:
            counts[r["tail"]] = counts.get(r["tail"], 0) + 1
    best = 0
    total_cols = 0
    for t in sorted(counts):
        n = counts[t]
        if n > best or (n == best and t > total_cols):
            best = n
            total_cols = t

    skipped = []
    accounts = []
    totals = []
    sections = []
    header_cells = None
    header_line = 0
    seen_data = False
    ambig = []
    state = {"open": None}

    # the header row: no numbers of its own, more than one cell, cells that read like periods
    if total_cols >= 2:
        for r in raws:
            if r["tail"] > 0:
                break
            if len(r["f"]) < 2:
                continue
            hits = sum(1 for c in r["f"] if c and HEADERWORD.search(c))
            if hits >= 1:
                header_cells = r["f"]
                header_line = r["n"]
                break

    labels = []
    if header_cells and len(header_cells) >= total_cols:
        labels = list(header_cells[len(header_cells) - total_cols:])
    for i in range(total_cols):
        if i >= len(labels) or not labels[i] or not re.sub(r"\s", "", str(labels[i])):
            while len(labels) <= i:
                labels.append("")
            labels[i] = "column " + str(i + 1)

    guess = guess_cols(labels) if total_cols >= 2 else {"p": 0, "c": 1}
    pick = {"p": guess["p"], "c": guess["c"]}
    if (choice and isinstance(choice.get("p"), int) and isinstance(choice.get("c"), int)
            and 0 <= choice["p"] < total_cols and 0 <= choice["c"] < total_cols
            and choice["p"] != choice["c"]):
        pick = {"p": choice["p"], "c": choice["c"]}

    def field(r, i):
        return r["f"][i] if 0 <= i < len(r["f"]) else None

    def pair_of(r):
        base = len(r["f"]) - total_cols
        a = parse_num(field(r, base + pick["p"]))
        b = parse_num(field(r, base + pick["c"]))
        if (base + pick["p"] < r["k"] or base + pick["c"] < r["k"]
                or a is None or b is None):
            a = parse_num(field(r, r["k"]))
            b = parse_num(field(r, r["k"] + 1))
        return [a, b]

    def head_of(r):
        head = list(r["f"][:r["k"]])
        while head and head[0] == "":
            head.pop(0)
        while head and head[-1] == "":
            head.pop()
        if len(head) > 1 and re.match(r"^\d{2,8}[a-z]?\Z", head[0], re.I):
            return head[0] + " " + ", ".join(head[1:])
        return ", ".join(head)

    def open_section(nm, n):
        state["open"] = {"name": nm, "lines": [], "n": n}
        sections.append(state["open"])

    for r in raws:
        if header_cells and r["n"] == header_line:
            skipped.append({"n": r["n"], "t": r["line"], "benign": 1,
                            "why": "header row, read for the period columns and then ignored"})
            continue
        if r["amb"]:
            ambig.append(
                "Line " + str(r["n"]) + " splits on commas into a three digit field standing after a "
                "numeric field, which is what an unquoted thousands separator looks like.")
            skipped.append({"n": r["n"], "t": r["line"],
                            "why": "the commas on this row cannot be told from an unquoted thousands "
                                   "separator, so the row was refused rather than read on a guess"})
            continue
        if r["tail"] >= 2 and r["k"] >= 1:
            label = head_of(r)
        else:
            label = re.sub(r"\s+", " ", " ".join(r["f"])).strip()
        if r["tail"] >= 2 and r["k"] >= 1:
            pr = pair_of(r)
            if TOTALWORD.search(label) or GRAND.search(label):
                is_grand = bool(GRAND.search(label)) and not TOTALWORD.search(label)
                tr = {"n": r["n"], "label": label, "prior": pr[0], "cur": pr[1],
                      "grand": is_grand, "sec": None}
                if not is_grand and state["open"] and state["open"]["lines"]:
                    tr["sec"] = state["open"]
                    state["open"] = None
                elif is_grand:
                    state["open"] = None
                totals.append(tr)
                skipped.append({"n": r["n"], "t": label, "keep": 1,
                                "why": ("a computed total across sections, kept for the totals tie and "
                                        "left out of the line checks") if is_grand else
                                       ("a section total, kept for the totals tie and left out of the "
                                        "line checks")})
                continue
            sh = acct_shape(label, r["n"])
            if not sh["name"]:
                skipped.append({"n": r["n"], "t": r["line"], "why": "no account name"})
                continue
            prior, cur = pr[0], pr[1]
            change = cur - prior
            a = Account(num=sh["num"], name=sh["name"], prior=prior, cur=cur, change=change,
                        pct=(None if prior == 0 else (change / abs(prior)) * 100),
                        words=sh["words"], flat=sh["flat"], two=sh["two"], row=r["n"],
                        section=state["open"]["name"] if state["open"] else "")
            accounts.append(a)
            if state["open"]:
                state["open"]["lines"].append(a)
            seen_data = True
            continue
        # no pair of numbers on this row
        if SECTION_ONLY.match(label):
            open_section(label, r["n"])
            continue
        if GRAND.search(label):
            state["open"] = None
            skipped.append({"n": r["n"], "t": label, "why": "a total with no figures beside it"})
            continue
        if seen_data and label and r["tail"] == 0 and len(r["f"]) <= 2:
            open_section(label, r["n"])
            continue
        skipped.append({"n": r["n"], "t": r["line"], "benign": 0 if seen_data else 1,
                        "why": "could not read a prior and a current balance on this row" if seen_data
                               else "title or heading above the report, ignored"})

    seen_num = {}
    dups = []
    for a in accounts:
        if not a.num:
            continue
        if a.num in seen_num and a.num not in dups:
            dups.append(a.num)
        seen_num[a.num] = seen_num.get(a.num, 0) + 1

    discarded = [i for i in range(total_cols) if i != pick["p"] and i != pick["c"]]
    named = sum(1 for l in labels if not re.match(r"^column \d+\Z", str(l)))
    cols_unconfirmed = (total_cols > 2 and named < total_cols
                        and not (choice and isinstance(choice.get("p"), int)))

    return {"accounts": accounts, "skipped": skipped, "totals": totals, "sections": sections,
            "labels": labels, "T": total_cols, "pick": pick, "guess": guess,
            "header": bool(header_cells), "dups": dups, "ambig": ambig,
            "discarded": discarded, "colsUnconfirmed": cols_unconfirmed}


def tie_totals(ledger):
    """Every section total recomputed from the lines standing under it."""
    out = []
    for t in ledger["totals"]:
        if t["grand"] or not t["sec"]:
            out.append({"label": t["label"], "ok": None, "det":
                        "Kept out of the line checks. This is a total computed across sections, so the "
                        "checker does not recompute it from lines." if t["grand"] else
                        "Kept out of the line checks. No section lines sit above this total, so there is "
                        "nothing to recompute it from."})
            continue
        sp = sum(a.prior for a in t["sec"]["lines"])
        sc = sum(a.cur for a in t["sec"]["lines"])
        ok_p = abs(sp - t["prior"]) < 0.01
        ok_c = abs(sc - t["cur"]) < 0.01
        n = len(t["sec"]["lines"])
        word = ("The " + str(n) + " line" + ("" if n == 1 else "s") + " under \"" + t["sec"]["name"]
                + "\" " + ("adds" if n == 1 else "add") + " to ")
        out.append({"label": t["label"], "ok": bool(ok_p and ok_c), "n": n, "det":
                    (word + money(sp) + " prior and " + money(sc) + " current, which is what the total "
                     "row says.") if (ok_p and ok_c) else
                    (word + money(sp) + " prior and " + money(sc) + " current, but the total row says "
                     + money(t["prior"]) + " and " + money(t["cur"]) + ". Something on this statement is "
                     "missing from the paste or double counted.")})
    return out


def legs_of(a, floor_d, floor_p, zp):
    """The dollar rule is MORE THAN the floor; the percent rule is AT LEAST it."""
    d = abs(a.change) > floor_d
    if a.pct is None:
        p = False if zp == "exclude" else (a.change != 0)
    else:
        p = abs(a.pct) >= floor_p
    return {"d": d, "p": p}


def clears_rule(a, floor_d, floor_p, rule, zp):
    if a.pct is None and zp == "exclude":
        return False
    lg = legs_of(a, floor_d, floor_p, zp)
    return (lg["d"] or lg["p"]) if rule == "either" else (lg["d"] and lg["p"])


def pct_cell(a):
    return "new line" if a.pct is None else pct_txt(a.pct)


# ============================================================ memo

def split_sentences(text):
    """A labelled line is kept whole; anything else is split at sentence boundaries."""
    out = []
    auto = 0
    for raw in de_smart(text).split("\n"):
        line = raw[:-1] if raw.endswith("\r") else raw
        line = line.strip()
        if not line:
            continue
        if re.match(r"^[-=_~\s|+*]{4,}\Z", line):
            continue
        line = re.sub(r"^[\u2022\u00b7\u25cf\u25aa\u2023\u2043*>]+\s+", "", line)
        line = re.sub(r"^-\s+", "", line)
        line = re.sub(r"^\s+", "", line)
        if not line:
            continue
        mp = re.match(r"^\(\s*([A-Za-z]{1,2}|\d{1,3})\s*\)\s*(\S.*)\Z", line, re.S)
        if mp and mp.group(2):
            out.append({"label": mp.group(1).upper(), "text": re.sub(r"\s+", " ", mp.group(2))})
            continue
        ml = re.match(r"^([a-z])\s*[.)\]]\s+(\S.*)\Z", line, re.S)
        if ml and ml.group(2):
            out.append({"label": ml.group(1).upper(), "text": re.sub(r"\s+", " ", ml.group(2))})
            continue
        m = re.match(r"^([A-Za-z]{1,2}\s?\d{1,3}|\d{1,2})\s*[.)\]:-]\s+(.*)\Z", line, re.S)
        if m and m.group(2):
            out.append({"label": re.sub(r"\s+", "", m.group(1)).upper(),
                        "text": re.sub(r"\s+", " ", m.group(2))})
            continue
        buf = ""
        i = 0
        while i < len(line):
            ch = line[i]
            buf += ch
            if ch in ".!?":
                nx = line[i + 1:]
                if re.match(r"^\s+[\"\u201c(]?[A-Z0-9]", nx) and not re.search(r"\d\.\Z", buf):
                    out.append({"label": None, "text": re.sub(r"\s+", " ", buf.strip())})
                    buf = ""
                    i += 1
                    while i < len(line) and line[i].isspace():
                        i += 1
                    i -= 1
            i += 1
        if buf.strip():
            out.append({"label": None, "text": re.sub(r"\s+", " ", buf.strip())})
    for s in out:
        if not s["label"]:
            auto += 1
            s["label"] = "S" + str(auto)
        else:
            digits = re.sub(r"\D", "", s["label"])
            if digits:
                n = int(digits)
                if n > auto:
                    auto = n
    return out


def parse_fig(raw):
    t = str(raw).strip()
    mult = 1
    sm = re.search(r"([kKmMbB])\s*\)?\s*\Z", t)
    if sm:
        c = sm.group(1).lower()
        mult = 1e3 if c == "k" else (1e6 if c == "m" else 1e9)
        t = re.sub(r"[kKmMbB](\s*\)?\s*)\Z", r"\1", t)
    v = parse_num(t)
    if v is None:
        return None
    return v * mult


# ---------- 0. what the accepted grammar does not read ----------------------
_CURRENCY = r"\u20ac\u00a3\u00a5\u20b9\u20bd\u20a9\u20aa\u20ba\u0e3f\u00a2"
_CODES = (r"EUR|GBP|JPY|CHF|CAD|AUD|NZD|CNY|RMB|INR|MXN|BRL|ZAR|SEK|NOK|DKK|SGD|HKD|USD")
FOREIGN_BEFORE = re.compile(r"(?:[" + _CURRENCY + r"]|\b(?:" + _CODES + r")\s)\s*\Z", re.I)
FOREIGN_AFTER = re.compile(r"^\s*(?:[" + _CURRENCY + r"]|\b(?:" + _CODES + r")\b)", re.I)
SCALE_AFTER = re.compile(
    r"^[\s-]*(?:thousands?|millions?|billions?|trillions?|mn|bn|basis\s+points?|bps|times|"
    r"multiples?)\b", re.I)
_NW = ("one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen|"
       "sixteen|seventeen|eighteen|nineteen|twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety|"
       "hundred|thousand|million|billion")
NUMWORD_RE = re.compile(r"\b(?:" + _NW + r")(?:[\s-]+(?:" + _NW + r"))*\b", re.I)
UNIT_AFTER = re.compile(
    r"^[\s,-]*(?:percent|per\s?cent|pct|%|percentage\s+points?|basis\s+points?|points?|dollars?)\b",
    re.I)


FRACTION_AFTER = re.compile(
    r"^[\s-]*(?:half|halves|third|thirds|quarter|quarters|fifth|fifths|sixth|sixths|seventh|"
    r"sevenths|eighth|eighths|ninth|ninths|tenth|tenths|twelfth|twelfths|hundredth|hundredths|"
    r"thousandth|thousandths)\b", re.I)
WORD_UNIT = re.compile(
    r"^[\s,-]*(?:(percentage\s+points?|pp)|(percent|per\s?cent|pct|%)|(dollars?))\b", re.I)
NW_SMALL = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
            "six": 6, "seven": 7, "eight": 8, "nine": 9}
NW_TEEN = {"ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14,
           "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19}
NW_TENS = {"twenty": 20, "thirty": 30, "forty": 40, "fifty": 50,
           "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90}


def nw_lead(w):
    for table in (NW_SMALL, NW_TEEN, NW_TENS):
        if w in table:
            return table[w]
    return None


def nw_group(tk, i):
    """One group below a thousand: "one hundred twenty-five", "nineteen", "thirty"."""
    v = 0
    any_ = False
    if i + 1 < len(tk) and tk[i + 1] == "hundred" and nw_lead(tk[i]) is not None:
        v = nw_lead(tk[i]) * 100
        any_ = True
        i += 2
    if i < len(tk) and tk[i] in NW_TENS:
        v += NW_TENS[tk[i]]
        any_ = True
        i += 1
        if i < len(tk) and tk[i] in NW_SMALL:
            v += NW_SMALL[tk[i]]
            i += 1
    elif i < len(tk) and (tk[i] in NW_SMALL or tk[i] in NW_TEEN):
        v += NW_SMALL[tk[i]] if tk[i] in NW_SMALL else NW_TEEN[tk[i]]
        any_ = True
        i += 1
    return (v, i) if any_ else None


def words_to_number(run):
    """The value of the whole run, or None where the parser cannot resolve it.
    "billion" is deliberately out of range: the grammar reads units through
    millions, and anything above that goes to the reviewer rather than being
    guessed at."""
    tk = [w for w in re.split(r"[\s-]+", str(run).lower()) if w]
    i = 0
    total = 0
    last = float("inf")
    got = False
    while i < len(tk):
        g = nw_group(tk, i)
        if not g:
            return None
        v, i = g
        sc = 1
        if i < len(tk) and tk[i] in ("thousand", "million"):
            sc = 1000 if tk[i] == "thousand" else 1000000
            i += 1
        if sc >= last:
            return None
        if sc == 1 and i < len(tk):
            return None
        last = sc
        total += v * sc
        got = True
    return total if got else None


def word_numbers(text, taken):
    """Every run of number words, split into the ones that become figures and the
    ones that have to reach the reviewer.  ``always`` marks a span that goes to
    the queue wherever it stands; the rest go only where the words put a claim."""
    figs = []
    pending = []
    for m in NUMWORD_RE.finditer(text):
        i, j = m.start(), m.end()
        if any(i < t[1] and j > t[0] for t in taken):
            continue
        after = text[j:j + 30]
        if re.search(r"\d\s*\Z", text[max(0, i - 14):i]):
            pending.append({"raw": m.group(0), "at": i, "end": j,
                            "why": "a figure written in words", "always": True})
            continue
        fm = FRACTION_AFTER.match(after)
        if fm:
            pending.append({"raw": text[i:j + len(fm.group(0))], "at": i, "end": j + len(fm.group(0)),
                            "why": "a quantity in words the checker cannot resolve", "always": True})
            continue
        v = words_to_number(m.group(0))
        if v is None:
            pending.append({"raw": m.group(0), "at": i, "end": j,
                            "why": "a quantity in words the checker cannot resolve", "always": True})
            continue
        u = WORD_UNIT.match(after)
        if u:
            unit = ("percentage points" if u.group(1)
                    else ("percent" if u.group(2) else "dollars"))
            figs.append({"raw": text[i:j + len(u.group(0))].strip(), "v": float(v), "at": i,
                         "end": j + len(u.group(0)), "unit": unit, "signed": False,
                         "plain": False, "words": True})
            continue
        if UNIT_AFTER.match(after):
            pending.append({"raw": m.group(0), "at": i, "end": j,
                            "why": "a quantity in words the checker cannot resolve", "always": True})
            continue
        pending.append({"raw": m.group(0), "at": i, "end": j,
                        "why": "a figure written in words with no unit", "always": False})
    return figs, pending


def stray_numbers(text, taken):
    """A run of digits standing where the words put a claim, or wearing a unit
    the grammar does not read."""
    out = []
    for m in re.finditer(r"-?\d[\d,]*(?:\.\d+)?", text):
        i, j = m.start(), m.end()
        if any(i < t[1] and j > t[0] for t in taken):
            continue
        after = text[j:j + 26]
        sm = SCALE_AFTER.match(after)
        fm = FOREIGN_AFTER.match(after)
        unit = bool(sm or fm)
        r = role_of(text, {"at": i, "end": j, "unit": "dollars"}, 0, [])
        if not unit and r["role"] == "unknown":
            continue
        out.append({"raw": m.group(0) + ((sm or fm).group(0) if unit else ""), "at": i, "end": j,
                    "why": "a unit the checker does not read" if unit
                           else "a number standing where the words put a claim"})
    return out


# ---------- 1. extraction ---------------------------------------------------
class FigureList(list):
    rejected = ()


_RE_PCT = re.compile(
    r"([-(]?\s?\$?\s?\d[\d,]*(?:\.\d+)?\s?\)?)\s*(percentage points?|percent|per cent|pct|pp|%)", re.I)
_RE_DOL = re.compile(
    r"\(\s?\$?\s?\d(?:[\d,]*\d)?(?:\.\d+)?\s?[kKmMbB]?\s?\)|"
    r"-?\$\s?\d(?:[\d,]*\d)?(?:\.\d+)?(?:\s?[kKmMbB]\b)?|"
    r"\b\d{1,3}(?:,\d{3})+(?:\.\d+)?\b|"
    r"\b\d+(?:\.\d+)?[kKmMbB]\b")
_RE_BARE = re.compile(r"(?:-\s?)?\b\d{4,}(?:\.\d+)?\b")


def figures(text, skip_nums=None):
    """Every figure with the span it came from, its value and its unit.  Nothing
    here binds an account and nothing here decides what a figure means."""
    out = []
    taken = []

    def overlaps(i, j):
        return any(i < t[1] and j > t[0] for t in taken)

    def has_sign(raw):
        return bool(re.match(r"^\s*-", raw)) or (
            bool(re.match(r"^\s*\(", raw)) and bool(re.search(r"\)\s*\Z", raw)))

    for m in _RE_PCT.finditer(text):
        ptxt = m.group(1)
        neg = has_sign(ptxt)
        if re.match(r"^\s*\(", ptxt) and not re.search(r"\)\s*\Z", ptxt):
            ptxt = re.sub(r"^\s*\(", "", ptxt)
        pv = parse_num(ptxt)
        if pv is not None:
            raw = re.sub(r"^\s*\(", "", m.group(0)).strip()
            unit = ("percentage points"
                    if re.search(r"point", m.group(2), re.I) or re.match(r"^pp\Z", m.group(2), re.I)
                    else "percent")
            out.append({"raw": raw, "v": pv, "at": m.start(), "end": m.end(),
                        "unit": unit, "signed": neg, "plain": False})
        taken.append([m.start(), m.end()])

    for m in _RE_DOL.finditer(text):
        if overlaps(m.start(), m.end()):
            continue
        dv = parse_fig(m.group(0))
        if dv is None:
            continue
        out.append({"raw": m.group(0).strip(), "v": dv, "at": m.start(), "end": m.end(),
                    "unit": "dollars", "signed": has_sign(m.group(0)), "plain": False})
        taken.append([m.start(), m.end()])

    for m in _RE_BARE.finditer(text):
        if overlaps(m.start(), m.end()):
            continue
        bare = re.sub(r"[^0-9.]", "", m.group(0))
        if re.match(r"^(19|20)\d\d\Z", bare):
            continue
        if skip_nums and bare in skip_nums:
            continue
        out.append({"raw": re.sub(r"\s+", "", m.group(0)),
                    "v": float(bare) * (-1 if m.group(0).startswith("-") else 1),
                    "at": m.start(), "end": m.end(), "unit": "dollars",
                    "signed": m.group(0).startswith("-"), "plain": True})
        taken.append([m.start(), m.end()])

    # a quantity in words that the parser resolved and the words gave a unit is
    # an ordinary figure from here on.
    word_figs, word_pending = word_numbers(text, taken)
    for f in word_figs:
        if overlaps(f["at"], f["end"]):
            continue
        out.append(f)
        taken.append([f["at"], f["end"]])

    out.sort(key=lambda f: f["at"])

    rejected = []
    keep = []
    for f in out:
        before = text[:f["at"]]
        after = text[f["end"]:]
        if f["unit"] == "dollars":
            mm = FOREIGN_BEFORE.search(before)
            if mm:
                lead = re.sub(r"^\s+", "", mm.group(0))
                rejected.append({"raw": lead + f["raw"], "at": f["at"] - len(lead), "end": f["end"],
                                 "why": "a currency the checker does not read"})
                continue
            mm = FOREIGN_AFTER.match(after)
            if mm:
                rejected.append({"raw": f["raw"] + mm.group(0), "at": f["at"],
                                 "end": f["end"] + len(mm.group(0)),
                                 "why": "a currency the checker does not read"})
                continue
            mm = SCALE_AFTER.match(after)
            if mm:
                rejected.append({"raw": f["raw"] + mm.group(0), "at": f["at"],
                                 "end": f["end"] + len(mm.group(0)),
                                 "why": "a scale word the checker does not carry"})
                continue
        keep.append(f)

    for i, f in enumerate(keep):
        r = role_of(text, f, i, keep)
        f["role"] = r["role"]
        f["side"] = r.get("side") or ""
        f["roleFrom"] = r.get("from") or ""

    spans = [[f["at"], f["end"]] for f in keep] + [[r["at"], r["end"]] for r in rejected]
    for w in word_pending:
        if any(w["at"] < sp[1] and w["end"] > sp[0] for sp in spans):
            continue
        if not w["always"] and role_of(
                text, {"at": w["at"], "end": w["end"], "unit": "dollars"}, 0, [])["role"] == "unknown":
            continue
        rejected.append({"raw": w["raw"], "at": w["at"], "end": w["end"], "why": w["why"]})
        spans.append([w["at"], w["end"]])
    rejected.extend(stray_numbers(text, spans))
    rejected.sort(key=lambda r: r["at"])

    result = FigureList(keep)
    result.rejected = rejected
    return result


def dollars_in(figs):
    return [f for f in figs if f["unit"] == "dollars"]


def pcts_in(figs):
    return [f for f in figs if f["unit"] != "dollars"]


# ---------- 2. numeric role -------------------------------------------------
CUE_PRIOR = {"from"}
CUE_CURRENT = {"to", "at", "now", "reached", "reaching", "stands", "standing", "hit", "hits"}
CUE_MOVE = {"by"}
MOVE_NOUN = {"increase", "increases", "decrease", "decreases", "rise", "rises", "fall", "falls",
             "drop", "drops", "gain", "gains", "growth", "decline", "declines", "movement",
             "change", "variance", "swing", "reduction", "uptick"}
SKIPW = {"a", "an", "the", "is", "was", "were", "are", "be", "been", "which", "that", "of", "in",
         "about", "roughly", "approximately", "some", "only", "just", "another", "total", "net",
         "this", "its"}

UP = ["rose", "rise", "rises", "risen", "rising", "increased", "increase", "increases", "increasing",
      "grew", "grow", "grows", "growth", "growing", "up", "higher", "climbed", "climb", "climbs",
      "gained", "jumped", "added", "advanced", "advance", "advances", "expanded", "expand",
      "expands", "expansion", "surged", "surge", "surges", "accelerated", "accelerate", "accelerates"]
DOWN = ["fell", "fall", "falls", "fallen", "falling", "declined", "decline", "declines", "declining",
        "decreased", "decrease", "decreases", "decreasing", "down", "lower", "dropped", "drop",
        "drops", "reduced", "shrank", "eased", "ease", "eases", "easing", "softened", "soften",
        "softens", "softening", "slipped", "slip", "slips", "receded", "recede", "recedes"]
_DIRSET = set(UP) | set(DOWN)


def role_of(text, f, idx, all_figs):
    pre = text[:f["at"]]
    post = text[f["end"]:]
    pct = f["unit"] != "dollars"
    if f["unit"] == "percentage points":
        return {"role": "rate change in points", "from": "the words \"percentage points\""}
    if pct and re.match(r"^\s*of\s+(the\s+)?(prior|previous|last|opening|jan|feb|mar|apr|may|jun|"
                        r"jul|aug|sep|oct|nov|dec)", post, re.I):
        return {"role": "relative movement", "from": "\"of\" naming the period it is a share of"}
    nx = re.split(r"[^a-z]", re.sub(r"^[^A-Za-z]*", "", post).lower())[0]
    if nx and nx in MOVE_NOUN:
        return {"role": "relative movement" if pct else "absolute movement",
                "from": "the word \"" + nx + "\" standing after it"}
    words = [w for w in re.sub(r"\s+", " ", re.sub(r"[^a-z\s]", " ", pre.lower())).split(" ") if w]
    win = words[-6:]
    for i in range(len(win) - 1, -1, -1):
        w = win[i]
        if w in CUE_PRIOR:
            return {"role": "ratio" if pct else "prior balance", "side": "prior",
                    "from": "the word \"" + w + "\""}
        if w in CUE_CURRENT:
            return {"role": "ratio" if pct else "current balance", "side": "current",
                    "from": "the word \"" + w + "\""}
        if w in CUE_MOVE:
            return {"role": "relative movement" if pct else "absolute movement",
                    "from": "the word \"" + w + "\""}
        if w in MOVE_NOUN:
            return {"role": "relative movement" if pct else "absolute movement",
                    "from": "the word \"" + w + "\""}
        if w in _DIRSET:
            return {"role": "relative movement" if pct else "absolute movement",
                    "from": "the direction word \"" + w + "\""}
        if (w == "or" or w == "and") and idx > 0:
            prev = all_figs[idx - 1] if idx - 1 < len(all_figs) else None
            if prev and prev.get("role") and prev.get("role") != "unknown":
                r = prev["role"]
                if pct and r == "absolute movement":
                    r = "relative movement"
                if not pct and r == "relative movement":
                    r = "absolute movement"
                return {"role": r, "side": prev.get("side") or "",
                        "from": "\"" + w + "\", restating the figure before it"}
            return {"role": "unknown", "from": ""}
        if w in SKIPW:
            continue
        break
    return {"role": "unknown", "from": ""}


# ---------- 3. account binding ----------------------------------------------
TOL_P = 0.05
TOL_D = 0.005


def near(a, b, t):
    return abs(abs(a) - abs(b)) <= t


def exactly(a, b, t):
    return abs(a - b) <= t


def _num_in(num, text):
    return bool(re.search(r"(?:^|[^0-9])" + re.escape(num) + r"(?:[^0-9]|\Z)", text))


def bind_sentence(s, accounts, figs, spent):
    text = " " + re.sub(r"\s+", " ", re.sub(r"[^a-z0-9$.,%\s-]", " ", s["text"].lower())) + " "
    tokens = set(re.findall(r"[a-z]+", s["text"].lower()))
    by_num, by_name, by_word, by_fig, conflicts = [], [], [], [], []

    for a in accounts:
        if spent and a.num in spent:
            continue
        if a.num and _num_in(a.num, s["text"]):
            by_num.append(a)
    for a in accounts:
        if a in by_num:
            continue
        if a.flat and (" " + a.flat + " ") in text:
            by_name.append(a)
            continue
        if a.two and " " in a.two and (" " + a.two + " ") in text:
            by_name.append(a)

    named = by_num + by_name
    named_words = set()
    for a in named:
        named_words.update(a.words)

    for f in dollars_in(figs):
        f["ties"] = [a for a in accounts
                     if near(f["v"], a.prior, TOL_D) or near(f["v"], a.cur, TOL_D)
                     or near(f["v"], a.change, TOL_D)]
        for a in f["ties"]:
            if a in named or a in by_fig:
                continue
            distinct = [w for w in a.words if w not in named_words and w in tokens]
            if distinct:
                by_fig.append(a)
            else:
                conflicts.append({"a": a, "f": f})

    bound = named + by_fig
    if not bound:
        for a in accounts:
            for w in a.words:
                if w in tokens:
                    by_word.append(a)
                    break
        bound = list(by_word)

    how = []
    if by_num:
        how.append("by account number")
    if by_name:
        how.append("by account name")
    if by_fig:
        how.append("by an exact figure with a word from the name beside it")
    if not by_num and not by_name and not by_fig and by_word:
        how.append("by a word in the account name")
    return {"bound": bound, "byNum": by_num, "byName": by_name, "byFig": by_fig,
            "byWord": by_word, "conflicts": conflicts, "how": ", ".join(how)}


def clause_bind(s):
    """A sentence naming more than one account only binds a figure to one of them
    when the clause the figure stands in names that one and no other."""
    spans = spans_of(s["text"], RE_FINE)
    distinct = {}
    for a in s["bound"]:
        distinct[acct_id(a)] = [w for w in a.words
                                if not any(o is not a and w in o.words for o in s["bound"])]
    for f in s["figs"]:
        cl = None
        hits = []
        for sp in spans:
            if sp["at"] <= f["at"] < sp["end"]:
                cl = sp
        if cl:
            ct = " " + re.sub(r"\s+", " ", re.sub(r"[^a-z0-9\s]", " ", cl["text"].lower())) + " "
            for a in s["bound"]:
                got = False
                if a.num and _num_in(a.num, cl["text"]):
                    got = True
                if not got and a.flat and (" " + a.flat + " ") in ct:
                    got = True
                if not got and a.two and " " in a.two and (" " + a.two + " ") in ct:
                    got = True
                if not got:
                    for w in distinct.get(acct_id(a), []):
                        if (" " + w + " ") in ct:
                            got = True
                if got:
                    hits.append(a)
        f["clause"] = cl["text"] if cl else s["text"]
        f["bind"] = hits if len(hits) == 1 else None


# ---------- 4. units and calculation ----------------------------------------
def qty_of(a, which):
    return a.prior if which == "prior" else (a.cur if which == "cur" else a.change)


def qty_name(which):
    return "prior balance" if which == "prior" else ("current balance" if which == "cur" else "change")


ROLE_QTY = {"prior balance": "prior", "current balance": "cur", "absolute movement": "change"}


def check_dollar(f, bound, all_bound):
    if not all_bound:
        all_bound = bound
    want = ROLE_QTY.get(f["role"])
    hit = None
    alts = []
    best = None
    for a in bound:
        for k in ("prior", "cur", "change"):
            v = qty_of(a, k)
            gap = abs(abs(f["v"]) - abs(v))
            if near(f["v"], v, TOL_D):
                if want == k and not hit:
                    hit = {"a": a, "k": k}
                else:
                    alts.append(qty_name(k) + " on " + acct_id(a))
            if best is None or gap < best["gap"]:
                best = {"gap": gap, "txt": qty_name(k) + " on " + acct_id(a) + " is " + money(v)}
    plain = (" Read as an ordinary number with no currency punctuation, so the unit is assumed to be "
             "dollars.") if f.get("plain") else ""
    if hit:
        if f["signed"] and abs(f["v"] - qty_of(hit["a"], hit["k"])) > TOL_D:
            return {"st": "failed", "txt": f["raw"] + " is written with a sign of its own and the "
                    + qty_name(hit["k"]) + " on " + acct_id(hit["a"]) + " is "
                    + money(qty_of(hit["a"], hit["k"])) + ", so the signs disagree." + plain,
                    "ask": "Which sign is right on this figure?"}
        return {"st": "checked", "txt": f["raw"] + " is the " + f["role"] + " on " + acct_id(hit["a"])
                + ", " + money(qty_of(hit["a"], hit["k"])) + " unrounded, and the role was read from "
                + f["roleFrom"] + "." + plain, "ask": ""}
    if not want:
        if len(alts) == 1:
            return {"st": "review", "txt": f["raw"] + ": the words around it do not say what it is, and "
                    "it equals the " + alts[0] + ". Confirm the role before this figure counts as "
                    "checked." + plain,
                    "ask": "What is " + f["raw"] + " in this sentence: a prior balance, a current "
                           "balance, a movement or a ratio?"}
        if len(alts) > 1:
            return {"st": "review", "txt": f["raw"] + ": the words around it do not say what it is, and "
                    "it equals more than one ledger figure (" + "; ".join(alts) + ")." + plain,
                    "ask": "What is " + f["raw"] + " in this sentence, and on which line?"}
        return {"st": "failed", "txt": f["raw"] + ": the words around it do not say what it is and it "
                "equals nothing on the bound line. Nearest is "
                + (best["txt"] if best else "nothing at all") + "." + plain,
                "ask": "Where did " + f["raw"] + " come from?"}
    if alts:
        return {"st": "failed", "txt": f["raw"] + " is written as the " + f["role"] + " (read from "
                + f["roleFrom"] + "), but on " + acct_id(bound[0]) + " the " + f["role"] + " is "
                + money(qty_of(bound[0], want)) + ". " + f["raw"] + " is the " + alts[0] + "." + plain,
                "ask": "Is the figure wrong or is the wording wrong?"}
    combo = None
    if len(all_bound) > 1:
        for a in all_bound:
            for b in all_bound:
                if combo or a is b:
                    continue
                for k in ("prior", "cur", "change"):
                    if combo:
                        continue
                    if exactly(f["v"], qty_of(a, k) - qty_of(b, k), TOL_D):
                        combo = ("the " + qty_name(k) + " on " + acct_id(a) + " less the "
                                 + qty_name(k) + " on " + acct_id(b))
                    elif exactly(f["v"], qty_of(a, k) + qty_of(b, k), TOL_D):
                        combo = ("the " + qty_name(k) + " on " + acct_id(a) + " plus the "
                                 + qty_name(k) + " on " + acct_id(b))
    if combo:
        return {"st": "review", "txt": f["raw"] + " is written as the " + f["role"] + ", read from "
                + f["roleFrom"] + ", and it is not a " + f["role"] + " on any line this sentence binds. "
                "It is " + combo + ". The checker was not told that is what it is, so it is left open."
                + plain,
                "ask": "Is " + f["raw"] + " a figure computed across two lines, and where is that "
                       "computation set out?"}
    expected = "; ".join("the " + f["role"] + " on " + acct_id(a) + " is " + money(qty_of(a, want))
                         for a in bound)
    return {"st": "failed", "txt": "memo says " + f["raw"] + " as the " + f["role"] + "; " + expected
            + ". Nearest ledger figure: "
            + (best["txt"] if best else "nothing on the bound line comes close") + "." + plain,
            "ask": "Which figure is right, the memo or the ledger, and where did the memo's number "
                   "come from?"}


def check_percent(f, bound, ratios, zp_text):
    cands = []
    for a in bound:
        if a.pct is not None:
            cands.append({"lab": acct_id(a) + " percent change", "v": a.pct,
                          "kind": "relative movement"})
    for r in ratios:
        cands.append({"lab": r["name"] + ", prior month", "v": r["prior"], "kind": "ratio",
                      "side": "prior"})
        cands.append({"lab": r["name"] + ", current month", "v": r["cur"], "kind": "ratio",
                      "side": "current"})
        cands.append({"lab": r["name"] + ", change in points", "v": r["change"],
                      "kind": "rate change in points"})

    def wanted(c):
        if f["role"] == "relative movement":
            return c["kind"] == "relative movement"
        if f["role"] == "ratio":
            return c["kind"] == "ratio" and (not f.get("side") or c.get("side") == f.get("side"))
        if f["role"] == "rate change in points":
            return c["kind"] == "rate change in points"
        return True

    if f["role"] == "unknown":
        cands.sort(key=lambda c: abs(abs(f["v"]) - abs(c["v"])))
        eq = [c for c in cands if near(f["v"], c["v"], TOL_P)]
        sc = [c for c in eq if f["signed"] and abs(f["v"] - c["v"]) > TOL_P]
        if sc and len(sc) == len(eq):
            return {"st": "failed", "txt": f["raw"] + " is written with a sign of its own; "
                    + sc[0]["lab"] + " is " + pct_txt(sc[0]["v"]) + ", so the magnitudes agree and the "
                    "signs do not.",
                    "ask": "Which way did this move, and is the sign in the memo right?"}
        return {"st": "review", "txt": f["raw"] + ": the words around it do not say what it measures"
                + ((", and it equals "
                    + "; ".join(c["lab"] + " at " + pct_txt(c["v"]) for c in eq)
                    + ". Equalling a figure is not the same as being that figure") if eq
                   else ", and it equals nothing the checker holds")
                + ". Confirm the role beside this row before it counts as checked.",
                "ask": "What is " + f["raw"] + " in this sentence: the movement on the line, a ratio, "
                       "or something else?"}

    hit = None
    sign_clash = None
    for c in cands:
        if not wanted(c):
            continue
        if near(f["v"], c["v"], TOL_P):
            if f["signed"] and abs(f["v"] - c["v"]) > TOL_P:
                sign_clash = c
                continue
            hit = c
            break
    if sign_clash and not hit:
        return {"st": "failed", "txt": f["raw"] + " is written with a sign of its own; "
                + sign_clash["lab"] + " is " + pct_txt(sign_clash["v"]) + ", so the magnitudes agree "
                "and the signs do not.",
                "ask": "Which way did this move, and is the sign in the memo right?"}
    if hit:
        return {"st": "checked", "via": "line" if hit["kind"] == "relative movement" else "ratio",
                "txt": f["raw"] + " is the " + f["role"] + ", " + hit["lab"] + " at "
                + pct_txt(hit["v"]) + " unrounded, and the role was read from " + f["roleFrom"] + ".",
                "ask": ""}
    if f["unit"] == "percentage points" and not ratios:
        return {"st": "review", "txt": f["raw"] + " is written in percentage points, which measure a "
                "change in a rate. The bound line is a dollar balance and no ratio was supplied, so "
                "there is nothing to compare it with.",
                "ask": "What rate is moving by these points, and where is it computed?"}
    if f["role"] == "relative movement" and bound and bound[0].pct is None:
        return {"st": "review", "txt": f["raw"] + " is written as the relative movement, and "
                + acct_id(bound[0]) + " has a zero prior balance, so no percentage exists to compare "
                "it with. Zero prior balance policy in force: " + zp_text + ".",
                "ask": "What is this percent measured against?"}
    if f["role"] == "ratio" and not ratios:
        return {"st": "review", "txt": f["raw"] + " is written as a ratio for the "
                + (f.get("side") or "period") + ", and no ratio was supplied in the ratio pane, so the "
                "checker has nothing to compute it from.",
                "ask": "Which ratio is this, and how is it computed from the ledger?"}
    cands.sort(key=lambda c: abs(abs(f["v"]) - abs(c["v"])))
    three = [c["lab"] + " " + pct_txt(c["v"]) for c in cands[:3]]
    if f["role"] == "relative movement" and bound and bound[0].pct is not None:
        return {"st": "failed", "txt": f["raw"] + " is written as the relative movement, read from "
                + f["roleFrom"] + ", and the relative movement on " + acct_id(bound[0]) + " is "
                + pct_txt(bound[0].pct) + " unrounded. Nearest values: "
                + ("; ".join(three) if three else "nothing else on the bound line") + ".",
                "ask": "Is this percent the movement on the line, or a ratio the checker was not told "
                       "about? Confirm the role beside this row if it is a ratio."}
    return {"st": "review", "txt": f["raw"] + " ties to nothing the checker holds"
            + (", and the words around it do not say what it measures" if f["role"] == "unknown"
               else " as a " + f["role"])
            + ". Nearest values: "
            + ("; ".join(three) if three else "nothing on the bound line and no ratio supplied") + ".",
            "ask": "What is this percent measuring, and where is it computed?"}


# ---------- 5. threshold policy claims --------------------------------------
def policy_claims(text):
    t = " " + re.sub(r"\s+", " ", text.lower()) + " "
    out = []
    if re.search(r"fails (both legs|the threshold on both)|clears neither leg|meets neither leg|"
                 r"neither leg (of the threshold )?is met", t):
        out.append({"leg": "both", "met": False})
    else:
        if re.search(r"fails the dollar leg|fails the dollar test|below the dollar leg", t):
            out.append({"leg": "dollar", "met": False})
        if re.search(r"fails the percent(age)? leg|fails the percent(age)? test|"
                     r"below the percent(age)? leg", t):
            out.append({"leg": "percent", "met": False})
    if re.search(r"carries no driver|carries no commentary|owes no commentary|"
                 r"no commentary (is )?owed|owes no explanation|this line carries no driver", t):
        out.append({"owes": False})
    return out


# ============================================================ ratios
def tokenize_expr(x):
    s = " " + x.lower() + " "
    for pat, rep in ((r"\bdivided by\b", " / "), (r"\bdivide by\b", " / "), (r"\bdivide\b", " / "),
                     (r"\bover\b", " / "), (r"\btimes\b", " * "), (r"\bmultiplied by\b", " * "),
                     (r"\bplus\b", " + "), (r"\bminus\b", " - "), (r"\bless\b", " - ")):
        s = re.sub(pat, rep, s)
    toks = re.findall(r"\d+|[()+\-*/]", s)
    junk = re.sub(r"\d+|[()+\-*/\s]", "", s)
    return {"toks": toks, "junk": junk}


class RatioError(Exception):
    pass


def eval_toks(toks, by_num, month):
    pos = {"i": 0}

    def peek():
        return toks[pos["i"]] if pos["i"] < len(toks) else None

    def factor():
        if pos["i"] >= len(toks):
            raise RatioError("the expression stops early")
        t = toks[pos["i"]]
        pos["i"] += 1
        if t == "(":
            v = expr()
            nxt = toks[pos["i"]] if pos["i"] < len(toks) else None
            pos["i"] += 1
            if nxt != ")":
                raise RatioError("a bracket is not closed")
            return v
        if t == "-":
            return -factor()
        if t == "+":
            return factor()
        if re.match(r"^\d+\Z", t):
            a = by_num.get(t)
            if not a:
                raise RatioError("no account " + t + " in the ledger")
            return a.prior if month == "prior" else a.cur
        raise RatioError("cannot read \"" + t + "\"")

    def term():
        v = factor()
        while peek() in ("*", "/"):
            op = toks[pos["i"]]
            pos["i"] += 1
            r = factor()
            if op == "/":
                if r == 0:
                    raise RatioError("that ratio divides by zero")
                v = v / r
            else:
                v = v * r
        return v

    def expr():
        v = term()
        while peek() in ("+", "-"):
            op = toks[pos["i"]]
            pos["i"] += 1
            v = v + term() if op == "+" else v - term()
        return v

    val = expr()
    if pos["i"] < len(toks):
        raise RatioError("there is something extra after the expression")
    return val


def parse_ratios(text, by_num):
    out = []
    errs = []
    for raw in str(text).split("\n"):
        line = (raw[:-1] if raw.endswith("\r") else raw).strip()
        if not line:
            continue
        i = line.find("=")
        name = line[:i].strip() if i > -1 else "Ratio " + str(len(out) + 1)
        expr_txt = line[i + 1:] if i > -1 else line
        tk = tokenize_expr(expr_txt)
        if tk["junk"]:
            errs.append(name + ": cannot read \"" + re.sub(r"\s+", " ", tk["junk"]) + "\"")
            continue
        if not tk["toks"]:
            errs.append(name + ": nothing to compute")
            continue
        vals = {}
        ok = True
        said = set()
        for mo in ("prior", "cur"):
            try:
                vals[mo] = eval_toks(list(tk["toks"]), by_num, mo) * 100
            except RatioError as e:
                ok = False
                if str(e) not in said:
                    said.add(str(e))
                    errs.append(name + ": " + str(e))
            except ZeroDivisionError:
                ok = False
        if not ok:
            continue
        if not math.isfinite(vals["prior"]) or not math.isfinite(vals["cur"]):
            errs.append(name + ": the ratio does not compute on these balances")
            continue
        out.append({"name": name, "expr": re.sub(r"\s+", " ", expr_txt).strip(),
                    "prior": vals["prior"], "cur": vals["cur"],
                    "change": vals["cur"] - vals["prior"]})
    return {"ratios": out, "errs": errs}


# ============================================================ direction
FLATW = ["held flat", "held steady", "held level", "held at", "no change", "no movement", "flat",
         "unchanged", "steady", "level with", "unmoved"]
FLAT_TOL = 0.5


def dir_words(txt):
    t = " " + re.sub(r"\s+", " ", re.sub(r"[^a-z\s]", " ", txt.lower())) + " "
    out = []
    for w in UP:
        if (" " + w + " ") in t:
            out.append({"w": w, "d": 1})
    for w in DOWN:
        if (" " + w + " ") in t:
            out.append({"w": w, "d": -1})
    return out


def flat_word(txt):
    t = " " + re.sub(r"\s+", " ", re.sub(r"[^a-z\s]", " ", txt.lower())) + " "
    found = None
    for w in FLATW:
        if (" " + w + " ") in t and (not found or len(w) > len(found)):
            found = w
    return found


def is_flat(a):
    if a.pct is None:
        return a.change == 0
    return abs(a.pct) <= FLAT_TOL


RE_COARSE = re.compile(r"[,;:]|\bso\b|\bbecause\b|\bwhile\b|\bbut\b|\bas\b|\bafter\b|\bbefore\b|"
                       r"\bwhich\b|\bthough\b", re.I)
RE_FINE = re.compile(r"[,;:]|\bso\b|\bbecause\b|\bwhile\b|\bwhereas\b|\bbut\b|\bas\b|\bafter\b|"
                     r"\bbefore\b|\bwhich\b|\bthough\b|\band\b|\bor\b|\bagainst\b|\bversus\b|"
                     r"\bcompared\s+(?:with|to)\b|\brelative\s+to\b|\boffset\s+by\b|\balongside\b|"
                     r"\brather\s+than\b|\binstead\s+of\b", re.I)


def spans_of(txt, rx):
    """Clauses, with the offsets kept so a figure can be placed in the clause it
    was written in.  A comma inside a figure is part of the figure."""
    t = re.sub(r"(\d),(\d)", "\\1\u0001\\2", str(txt))
    out = []
    last = 0
    for m in rx.finditer(t):
        if m.start() > last:
            out.append([last, m.start()])
        last = m.end()
    if last < len(t):
        out.append([last, len(t)])
    return [{"at": p[0], "end": p[1], "text": str(txt)[p[0]:p[1]]} for p in out
            if re.sub(r"\s", "", str(txt)[p[0]:p[1]]) != ""]


def clauses_of(txt):
    return [c["text"] for c in spans_of(txt, RE_COARSE)]


NEG_RE = re.compile(
    r"\b(?:did|do|does|was|were|is|are|has|have|had|could|would|will|can|shall|should|may|might|must)"
    r"\s+not\b|\bnot\b|\bnever\b|\bnor\b|\bneither\b|\bwithout\b|\brather\s+than\b|\binstead\s+of\b|"
    r"\bfailed\s+to\b|\bno\b|n['\u2019]t\b", re.I)


def negation_in(t):
    x = " " + re.sub(r"\s+", " ", str(t)) + " "
    x = re.sub(r"\bno\s+(?:commentary|drivers?|explanations?|reasons?|comments?|such)\b", " ", x, flags=re.I)
    x = re.sub(r"\bno\s+(?:change|movement)\b", " ", x, flags=re.I)
    x = re.sub(r"\bneither\s+leg\b", " ", x, flags=re.I)
    x = re.sub(r"\bnot\s+(?:listed|supplied|broken\s+out|yet)\b", " ", x, flags=re.I)
    m = NEG_RE.search(x)
    return m.group(0).strip() if m else None


def claim_in(t):
    return bool(len(figures(t)) or dir_words(t) or flat_word(t))


def direction_on(s):
    if not s["bound"]:
        return None
    bad, good, anchored, voided = [], [], [], []
    for c in clauses_of(s["text"]):
        cf = figures(c, s["numset"])
        anchor = None
        neg = negation_in(c)
        for d in dollars_in(cf):
            if anchor:
                break
            for a in s["bound"]:
                if anchor:
                    break
                if (near(d["v"], a.prior, TOL_D) or near(d["v"], a.cur, TOL_D)
                        or near(d["v"], a.change, TOL_D)):
                    anchor = a
        if neg and (flat_word(c) or dir_words(c)):
            voided.append("the words negate this clause (\u201c" + neg + "\u201d), so what it claims "
                          "about the direction of "
                          + (acct_id(anchor) if anchor else "; ".join(acct_id(a) for a in s["bound"]))
                          + " is not settled by the checker")
            if anchor:
                anchored.append(c)
            continue
        if not anchor:
            continue
        anchored.append(c)
        sign = 1 if anchor.change > 0 else (-1 if anchor.change < 0 else 0)
        anm = acct_id(anchor)
        fw = flat_word(c)
        if fw:
            if is_flat(anchor):
                good.append("\"" + fw + "\" agrees with " + anm + ", which moved " + money(anchor.change)
                            + ("" if anchor.pct is None else ", " + pct_txt(anchor.pct))
                            + ", inside half a percent of no movement")
            else:
                bad.append("the memo says \"" + fw + "\" but " + anm + " "
                           + ("rose " if sign > 0 else "fell ") + money(abs(anchor.change))
                           + ("" if anchor.pct is None else " (" + pct_txt(anchor.pct) + ")"))
        for w in dir_words(c):
            if sign == 0:
                bad.append("the memo says \"" + w["w"] + "\" but " + anm + " did not move at all")
                continue
            if w["d"] == sign:
                good.append("\"" + w["w"] + "\" agrees with " + anm)
            else:
                bad.append("the memo says \"" + w["w"] + "\" but " + anm + " "
                           + ("rose " if sign > 0 else "fell ") + money(abs(anchor.change))
                           + ("" if anchor.pct is None else " (" + pct_txt(anchor.pct) + ")"))
    if not anchored:
        if voided:
            return {"bad": bad, "good": good, "voided": voided}
        sneg = negation_in(s["text"])
        if sneg and (flat_word(s["text"]) or dir_words(s["text"])):
            voided.append("the words negate this sentence (\u201c" + sneg + "\u201d), so what it claims "
                          "about the direction is not settled by the checker")
            return {"bad": bad, "good": good, "voided": voided}
        sfw = flat_word(s["text"])
        if sfw:
            fok = False
            fnames = []
            for a in s["bound"]:
                fnames.append(acct_id(a) + " moved " + money(a.change)
                              + ("" if a.pct is None else ", " + pct_txt(a.pct)))
                if is_flat(a):
                    fok = True
            if fok:
                good.append("\"" + sfw + "\" agrees with the bound line")
            elif fnames:
                bad.append("the memo says \"" + sfw + "\" but " + " and ".join(fnames))
        for w in dir_words(s["text"]):
            agrees = False
            names = []
            for a in s["bound"]:
                sign = 1 if a.change > 0 else (-1 if a.change < 0 else 0)
                if sign == 0:
                    continue
                names.append(acct_id(a) + " " + ("rose" if sign > 0 else "fell"))
                if w["d"] == sign:
                    agrees = True
            if not names:
                continue
            if agrees:
                good.append("\"" + w["w"] + "\" agrees with the bound line")
            else:
                bad.append("the memo says \"" + w["w"] + "\" but " + " and ".join(names))
    return {"bad": bad, "good": good, "voided": voided}


# ============================================================ the run
RANK = {"checked within scope": 0, "not checked": 1, "needs review": 2, "failed": 3}
BADGE = {"checked within scope": "pass", "not checked": "info", "needs review": "review",
         "failed": "fail"}


def worse(a, b):
    return b if RANK[b] > RANK[a] else a


def zero_policy_text(zp):
    return ("a line with a zero prior balance is excluded from the rule" if zp == "exclude"
            else "a line with a zero prior balance is treated as owing commentary on any movement "
                 "(the default)")


def src_version(sig):
    h = 5381
    for ch in sig:
        h = ((h << 5) + h + ord(ch)) & 0xFFFFFFFF
        if h >= 0x80000000:
            h -= 0x100000000
    return "src-" + _base36(h & 0xFFFFFFFF) + "-" + str(len(sig))


def _base36(n):
    if n == 0:
        return "0"
    digits = "0123456789abcdefghijklmnopqrstuvwxyz"
    out = ""
    while n:
        n, r = divmod(n, 36)
        out = digits[r] + out
    return out


CSV_COLS = ["run id", "run timestamp", "close period", "reviewed memo version", "source version",
            "evidence id", "sentence id", "sentence text", "line", "account", "check", "status",
            "finding", "proposed conclusion", "human conclusion", "unresolved issue", "action owner",
            "review time"]


def _neutralise(v):
    v = "" if v is None else str(v)
    return ("'" + v) if re.match(r"^[=+\-@\t\r]", v) else v


def _strip_tags(html):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", str(html))).strip()


class CheckResult:
    """Everything one run produced: the same object the browser holds."""

    def __init__(self, **kw):
        self.__dict__.update(kw)

    # ---- coverage ----------------------------------------------------------
    def coverage_line(self):
        st = self.stats
        return (f"{st['sent']} sentence" + ("" if st["sent"] == 1 else "s") + " read \u00b7 "
                f"{st['checked']} checked within scope \u00b7 {st['review']} needs review \u00b7 "
                f"{st['notchecked']} not checked \u00b7 {st['failed']} failed \u00b7 "
                f"{st['rowsUsed']} ledger row" + ("" if st["rowsUsed"] == 1 else "s") + " used \u00b7 "
                f"{st['rowsSkipped']} row" + ("" if st["rowsSkipped"] == 1 else "s") + " skipped \u00b7 "
                f"{st['silent']} silent line" + ("" if st["silent"] == 1 else "s") + " \u00b7 "
                f"{st['queue']} in the reviewer queue.")

    def status_of(self, label):
        for s in self.sents:
            if s["label"] == label:
                return s["st"]
        return None

    # ---- the page's own text, for a contract test --------------------------
    def page_text(self):
        parts = [_strip_tags(n) for n in self.notes]
        st = self.stats
        parts.append("Sentences read " + str(st["sent"]))
        parts.append("Checked within scope " + str(st["checked"]))
        parts.append("Needs review " + str(st["review"]))
        parts.append("Not checked " + str(st["notchecked"]))
        parts.append("Failed " + str(st["failed"]))
        parts.append("Ledger rows used " + str(st["rowsUsed"]))
        parts.append("Rows skipped " + str(st["rowsSkipped"]))
        parts.append("Silent lines " + str(st["silent"]))
        parts.append("In the reviewer queue " + str(st["queue"]))
        if st["rowsSkipped"]:
            parts.append(str(st["rowsSkipped"]) + " ledger row"
                         + (" was" if st["rowsSkipped"] == 1 else "s were")
                         + " skipped, so the statement was not covered in full.")
        for r in self.rows:
            if r.get("grp"):
                parts.append(r["grp"])
                continue
            ask = " ".join(r["ask"]) if isinstance(r.get("ask"), list) else (r.get("ask") or "")
            parts.append(" ".join(str(x) for x in [r.get("line"), r.get("subj"), r.get("check"),
                                                   r.get("result"), r.get("det"), ask]))
        parts.extend(self.preview_facts)
        parts.extend(self.preview_body)
        return re.sub(r"\s+", " ", " ".join(parts))

    # ---- exports -----------------------------------------------------------
    def tsv(self):
        lines = ["\t".join(["Run", "Sentence id", "Line", "Sentence or account", "Check", "Status",
                            "Result", "Finding", "Ask the controller"])]
        for r in self.rows:
            if r.get("grp"):
                lines.append(r["grp"])
                continue
            ask = " | ".join(r["ask"]) if isinstance(r.get("ask"), list) else (r.get("ask") or "")
            cells = [self.runId, r.get("label") or r.get("id"), r.get("line"),
                     (r["label"] + ". " if r.get("label") else "") + str(r.get("subj") or ""),
                     r.get("check"), r.get("status") or "", r.get("result"), r.get("det"), ask]
            lines.append("\t".join(re.sub(r"[\t\r\n]+", " ", "" if c is None else str(c))
                                   for c in cells))
        return "\n".join(lines)

    def csv(self):
        def qq(v):
            return '"' + re.sub(r"[\r\n]+", " ", _neutralise(v).replace('"', '""')) + '"'

        def account_of(r):
            line = r.get("line")
            if not line or line == "none" or line == "total":
                return r.get("subj") if line == "total" else ""
            parts = []
            for t in re.split(r",\s*", str(line)):
                hit = None
                for a in self.accounts:
                    if not hit and (a.num == t or a.name == t):
                        hit = a
                parts.append(hit.name if hit else t)
            return "; ".join(parts)

        stamp = _iso(self.runAt)
        lines = [",".join('"' + c + '"' for c in CSV_COLS)]
        for r in self.rows:
            if r.get("grp"):
                continue
            ask = " ".join(r["ask"]) if isinstance(r.get("ask"), list) else (r.get("ask") or "")
            owner = ""
            if r.get("status") in ("failed", "needs review"):
                owner = "Controller" if "Silence" in str(r.get("check")) else "Preparer"
            cells = [self.runId, stamp, self.period, self.version, self.srcV,
                     r.get("ev") or r.get("id"), r.get("label") or "",
                     r.get("subj") if r.get("label") else "", r.get("line"), account_of(r),
                     r.get("check"), r.get("status") or "", r.get("det"), r.get("result"),
                     "", ask, owner, ""]
            lines.append(",".join(qq(c) for c in cells))
        return "\r\n".join(lines)

    def source_list(self):
        out = ["the ledger pasted into this page (" + str(len(self.ledger["accounts"]))
               + " account rows read, " + str(self.stats["rowsSkipped"]) + " skipped)",
               "the memo pasted into this page (" + str(len(self.sents)) + " sentences)"]
        if self.ratioText and re.sub(r"\s", "", self.ratioText):
            out.append("the ratio definitions typed into the ratio pane")
        if self.period:
            out.append("the close period as typed: " + self.period)
        if self.version:
            out.append("the memo version as typed: " + self.version)
        if self.company:
            out.append("the company or file name as typed: " + self.company)
        return out

    def json_record(self):
        return json.dumps({
            "runId": self.runId,
            "runAt": _iso(self.runAt),
            "sourceVersion": self.srcV,
            "period": self.period, "memoVersion": self.version,
            "caseVersion": self.caseVersion or "", "company": self.company,
            "reviewer": self.reviewer,
            "policy": {"dollarFloor": _num(self.floorD), "dollarRule": "more than",
                       "percentFloor": _num(self.floorP), "percentRule": "at least",
                       "legs": self.rule, "zeroPriorBalance": self.zero,
                       "displayTolerance": {"dollars": TOL_D, "percentagePoints": TOL_P}},
            "sourcesSupplied": self.source_list(),
            "coverage": self.stats,
            "sentences": [{
                "id": s["label"], "text": s["text"], "status": s["st"],
                "boundTo": [acct_id(a) for a in s["bound"]], "binding": s["how"],
                "conflicts": [{"figure": c["f"]["raw"], "account": acct_id(c["a"])}
                              for c in s["conflicts"]],
                "figures": [{"text": f["raw"], "value": _num(f["v"]), "unit": f["unit"],
                             "role": f["role"], "roleReadFrom": f["roleFrom"],
                             "span": [f["at"], f["end"]], "result": f.get("st"),
                             "finding": f.get("txt")} for f in s["figs"]],
            } for s in self.sents],
            "ledgerRowsSkipped": [x for x in self.ledger["skipped"]
                                  if not x.get("keep") and not x.get("benign")],
            "queue": self.queue,
            "rows": [{"evidenceId": r.get("ev") or r.get("id"), "sentenceId": r.get("label") or "",
                      "line": r.get("line"), "subject": r.get("subj"), "check": r.get("check"),
                      "status": r.get("status") or "", "result": r.get("result"),
                      "finding": r.get("det"),
                      "ask": " ".join(r["ask"]) if isinstance(r.get("ask"), list) else (r.get("ask") or ""),
                      "reviewerAnswer": ""} for r in self.rows if not r.get("grp")],
        }, indent=2, ensure_ascii=False)

    # ---- the table, as the page prints it ---------------------------------
    def header_lines(self):
        who = " · ".join(x for x in [self.company, self.period, self.version] if x)
        first = "Second Pass" + (" · " + who if who else "")
        return [first,
                "Run " + self.runId + ", source " + self.srcV + ".",
                "Rule as set: a movement owes an explanation when the change is more than "
                + money(self.floorD) + " (more than, not at least) and the percent of the prior "
                "balance is at least " + _plain(self.floorP) + " percent (at least, not more than), "
                + ("both legs" if self.rule == "both" else "either leg") + ", and "
                + zero_policy_text(self.zero) + ". Every threshold decision is unrounded."]

    def table(self, width=100):
        """The findings table the page draws, in plain text: the same rows, the
        same order, the same four marks, the same one imperative per row."""
        out = []
        for r in self.rows:
            if r.get("grp"):
                if r["grp"].startswith("4."):
                    break
                out.append("")
                out.append(r["grp"])
                out.append("-" * min(width, len(r["grp"]) + 4))
                continue
            mark = _MARK_WORD.get(r.get("status") or "", "   ")
            line = str(r.get("line") or "")
            subj = str(r.get("subj") or "")
            if r.get("label"):
                subj = r["label"] + ". " + subj
            head = "%-5s %-6s %-28s %-22s %s" % (mark, line[:6], subj[:28], str(r.get("check"))[:22],
                                                 r.get("result"))
            out.append(head)
            for wrapped in _wrap_to(str(r.get("det") or ""), width - 6):
                out.append("      " + wrapped)
            ask = _ask_short(r)
            if ask:
                out.append("      -> " + ask)
        return "\n".join(out)

    def queue_list(self, width=100):
        """The reviewer's queue, below the table, as a numbered list."""
        if not self.queue:
            return "The reviewer queue is empty."
        out = []
        for i, item in enumerate(self.queue, 1):
            out.append("%2d. [%s] %s — %s" % (i, item["kind"], item["ref"], item["subject"]))
            for wrapped in _wrap_to(item["issue"], width - 6):
                out.append("      " + wrapped)
            if item["ask"]:
                for wrapped in _wrap_to("Question: " + item["ask"], width - 6):
                    out.append("      " + wrapped)
            out.append("      Owner: " + item["owner"] + ".   Yes / No / Not on file: ______")
        return "\n".join(out)

    def reviewer_prompt(self):
        st = self.stats
        p = ["Second pass. Reviewer questions, and the mechanical work that was NOT done.",
             "Run " + self.runId + ", source version " + self.srcV + ", produced "
             + _iso(self.runAt) + ".",
             "Close period: " + (self.period or "not stated") + ". Memo version: "
             + (self.version or "not stated") + ".",
             "Commentary rule as set on this run: a movement owes an explanation when the change is "
             "more than " + money(self.floorD) + " (more than, not at least) and the percent of the "
             "prior balance is at least " + _plain(self.floorP) + " percent (at least, not more than), "
             + ("both legs" if self.rule == "both" else "either leg") + ", and "
             + zero_policy_text(self.zero) + ". Every threshold decision was made on unrounded values.",
             "",
             "COVERAGE OF THIS RUN. Do not read it as a clean bill.",
             "Sentences read: " + str(st["sent"]) + ".",
             "Checked within scope: " + str(st["checked"]) + ". Needs review: " + str(st["review"])
             + ". Not checked: " + str(st["notchecked"]) + ". Failed: " + str(st["failed"]) + ".",
             "Ledger rows read: " + str(st["rowsUsed"]) + ". Ledger rows skipped and never checked: "
             + str(st["rowsSkipped"]) + ".",
             "Lines clearing the rule with no sentence about them: " + str(st["silent"]) + ".",
             "\"Checked within scope\" means only this: each figure in the sentence carried a role the "
             "words gave it, and the unrounded comparison with the pasted ledger agreed. It does not "
             "mean the sentence is true, and it does not mean every figure in the memo was checked. "
             "Recompute anything you doubt.",
             "",
             "SOURCES ACTUALLY SUPPLIED TO THIS RUN. Nothing else was available to the checker, and no "
             "close binder, trial balance, invoice or contract was seen by it."]
        p.extend("- " + x for x in self.source_list())
        p.extend(["", "LEDGER AS PASTED", self.ledgerText.strip(),
                  "", "MEMO AS PASTED", self.memoText.strip(),
                  "", "UNRESOLVED ITEMS, VERBATIM. Every one of these is open."])
        if not self.queue:
            p.append("(none)")
        for item in self.queue:
            p.append("- [" + item["kind"] + "] " + item["ref"] + " \u2014 " + item["issue"]
                     + ((" Question: " + item["ask"]) if item["ask"] else "")
                     + " Owner: " + item["owner"] + ".")
        p.extend(["", "SENTENCES CHECKED WITHIN SCOPE. For each one, answer only these two questions:",
                  "1. Is the driver named here supported by anything on file?",
                  "2. Is the period right (nothing pulled forward or deferred)?"])
        if not self.survivors:
            p.append("(none reached this list)")
        for s in self.survivors:
            p.append(s["label"] + " (" + "; ".join(acct_id(a) for a in s["bound"]) + "): " + s["text"])
        dup = [acct_id(a) + ": " + ", ".join(x["label"] for x in a.sent)
               for a in self.accounts if len(a.sent) > 1]
        if dup:
            p.extend(["", "READ TOGETHER. More than one sentence lands on each of these accounts, and "
                      "the checker does not test them against each other: " + "; ".join(dup) + "."])
        p.extend(["", "Answer only from a document you can name and open. Where nothing you hold "
                  "supports a driver, say \"not on file\" and name what you would ask the controller "
                  "to produce. Do not treat any status above as evidence."])
        return "\n".join(p)


def _iso(dt):
    """toISOString: UTC, milliseconds, a trailing Z."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    dt = dt.astimezone(timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%S.") + "%03dZ" % (dt.microsecond // 1000)


_MARK_WORD = {"checked within scope": "ok", "needs review": "rev", "not checked": "n/c",
              "failed": "FAIL"}


def _wrap_to(text, width):
    """Wrap on spaces, never mid-word, and never lose a line."""
    words = str(text).split()
    if not words:
        return []
    lines = []
    cur = words[0]
    for w in words[1:]:
        if len(cur) + 1 + len(w) <= width:
            cur += " " + w
        else:
            lines.append(cur)
            cur = w
    lines.append(cur)
    return lines


def _ask_short(r):
    """The table carries the instruction as one imperative; the queue asks the
    question in full, which is where it gets answered."""
    a = " ".join(r["ask"]) if isinstance(r.get("ask"), list) else (r.get("ask") or "")
    if not a:
        return ""
    if r.get("check") == "Reviewer":
        return "Confirm the driver and the period."
    if r.get("check") == "Read together":
        return "Decide which sentence holds."
    if "Silen" in str(r.get("check")):
        return "Ask the controller what drove this line."
    if r.get("status") == "failed":
        return "Send it back to the preparer."
    return "Settle it before sign-off."


def _num(v):
    """A float that is a whole number prints as an integer, the way JSON.stringify does."""
    if isinstance(v, float) and v.is_integer() and abs(v) < 1e15:
        return int(v)
    return v


def _plain(v):
    return str(_num(v))


def run_check(ledger_text, memo_text, ratios="", dollar_floor=25000, percent_floor=10,
              rule="both", zero_prior="owing", period="", memo_version="", company="",
              reviewer="", case_version="", cols=None, run_seq=1, run_at=None):
    """Run the whole contract over one ledger and one memo.

    Raises ``CheckerInputError`` where the page would refuse the input and print
    a message instead of a table.
    """
    notes = []

    def note(cls, html):
        notes.append(html)

    floor_d = parse_num(dollar_floor)
    floor_p = parse_num(percent_floor)
    if floor_d is None or floor_d < 0:
        floor_d = 0
    if floor_p is None or floor_p < 0:
        floor_p = 0
    zp = "exclude" if str(zero_prior) == "exclude" else "owing"
    rule = "either" if str(rule) == "either" else "both"

    led_empty = not re.sub(r"\s", "", ledger_text or "")
    mem_empty = not re.sub(r"\s", "", memo_text or "")
    if led_empty and mem_empty:
        raise CheckerInputError(
            "Both panes are empty. Paste a ledger on the left and the drafted commentary on the "
            "right, or pick a case from Samples to see the shapes the reader expects.")
    if led_empty:
        raise CheckerInputError(
            "The memo is there but the ledger pane is empty. There is nothing to check a figure "
            "against until a ledger is pasted.")

    L = parse_ledger(ledger_text, cols)
    preview_facts, preview_body = _preview(L)
    if not L["accounts"]:
        if L["ambig"]:
            raise CheckerInputError("The ledger was refused rather than guessed at. "
                                    + " ".join(L["ambig"])
                                    + " Quote the fields, use tabs, or name the columns, and run it "
                                      "again.")
        if L["T"] < 2:
            raise CheckerInputError(
                "The ledger reader found " + str(len(L["skipped"])) + " row"
                + ("" if len(L["skipped"]) == 1 else "s") + " but no numeric columns. Every account "
                "line needs two numbers on it, a prior balance and a current balance, separated by "
                "tabs, commas or two or more spaces.")
        raise CheckerInputError(
            "Nothing to check yet. Rows were read, but none of them carried an account name beside a "
            "prior and a current balance.")

    sents = split_sentences(memo_text)
    if not sents:
        raise CheckerInputError(
            "The ledger read fine, but the memo pane is empty. Paste the commentary you want checked.")

    by_num = {}
    for a in L["accounts"]:
        if a.num and a.num not in by_num:
            by_num[a.num] = a
    R = parse_ratios(ratios or "", by_num)

    # The page joins these with U+0001, so the same inputs fingerprint the same
    # way in both places.
    sig = "".join([ledger_text or "", memo_text or "", ratios or "", str(dollar_floor),
                         str(percent_floor), rule, zp, period or "", memo_version or "",
                         company or "", "{}", "null" if cols is None else json.dumps(cols)])
    src_v = src_version(sig)
    run_id = "run-" + str(run_seq) + "-" + src_v[4:10]
    ev_seq = {"n": 0}

    def evid():
        ev_seq["n"] += 1
        return run_id + "/e" + str(ev_seq["n"])

    queue = []

    def q(kind, ref, subject, issue, owner="Preparer", ask=""):
        queue.append({"kind": kind, "ref": ref, "subject": subject, "issue": issue,
                      "owner": owner or "Preparer", "ask": ask or "", "ev": evid()})

    dropped = [s for s in L["skipped"] if not s.get("keep")]
    real_drops = [s for s in dropped if not s.get("benign")]
    for s in dropped:
        if s.get("benign"):
            continue
        q("Skipped source row", "line " + str(s["n"]), re.sub(r"\s+", " ", str(s["t"])),
          s["why"] + ", so this row was not checked at all", "Preparer",
          "Is this a real account line, and if it is, what are its two balances?")
    if real_drops:
        note("bad", str(len(real_drops)) + " ledger row" + ("" if len(real_drops) == 1 else "s")
             + " could not be read and " + ("was" if len(real_drops) == 1 else "were")
             + " left out of every check: "
             + "; ".join("line " + str(s["n"]) + " (" + s["why"] + ")" for s in real_drops)
             + ". The coverage counts below are counts of what was read, not of the statement.")
    for t in L["ambig"]:
        q("Ambiguous source", "ledger", t,
          "the reader refused to guess at this rather than proceed on a guess", "Preparer",
          "Repaste this ledger with tabs, or quote the fields that carry commas.")
    if L["discarded"]:
        dtxt = ", ".join('"' + L["labels"][i] + '"' for i in L["discarded"])
        q("Discarded column", "ledger", dtxt,
          "this ledger carries " + str(L["T"]) + " numeric columns and only two were read; " + dtxt
          + " " + ("was" if len(L["discarded"]) == 1 else "were") + " discarded", "Reviewer",
          "Are the prior and current columns the two the checker took?")
        note("bad" if L["colsUnconfirmed"] else "",
             ("This ledger has no header row and carries " + str(L["T"]) + " numeric columns. Columns "
              + str(L["pick"]["p"] + 1) + " and " + str(L["pick"]["c"] + 1)
              + " were read as prior and current and " + dtxt + " "
              + ("was" if len(L["discarded"]) == 1 else "were")
              + " discarded. Confirm the mapping in the parse preview before the statuses below mean "
                "anything; until you do, no sentence on this ledger reads better than needs review.")
             if L["colsUnconfirmed"] else
             ("Numeric columns not read as periods: " + dtxt + "."))
    if L["dups"]:
        q("Ambiguity", "ledger", "account " + ", ".join(L["dups"]),
          "the same account number appears on more than one row and no consolidation decision has "
          "been made", "Preparer", "Are these separate lines or one line to be consolidated?")
        note("bad", "Account " + ("number " if len(L["dups"]) == 1 else "numbers ")
             + ", ".join(L["dups"]) + (" appears" if len(L["dups"]) == 1 else " appear")
             + " on more than one row. A sentence naming that number cannot be tied to one line, so it "
               "is held at needs review until the duplicate is resolved.")
    for e in R["errs"]:
        q("Malformed ratio", "ratio pane", e,
          "the ratio could not be read, so every percent that depends on it was left uncomputed",
          "Preparer", "How is this ratio computed from the ledger?")
    if R["errs"]:
        note("bad", "Ratios that could not be read, so they were left out: " + "; ".join(R["errs"]) + ".")

    rows = []
    stats = {"sent": len(sents), "checked": 0, "review": 0, "notchecked": 0, "failed": 0,
             "rowsUsed": len(L["accounts"]), "rowsSkipped": len(real_drops), "silent": 0,
             "queue": 0, "totalsFail": 0}

    # ---- 1. recompute every line, and tie the section totals
    rows.append({"grp": "1. Recompute every line, and tie the section totals"})
    for a in L["accounts"]:
        lg = legs_of(a, floor_d, floor_p, zp)
        a.legs = lg
        a.clears = clears_rule(a, floor_d, floor_p, rule, zp)
        a.dup = a.num in L["dups"]
        rows.append({
            "id": run_id + "/L" + (a.num or str(a.row)), "ev": evid(),
            "line": a.num or ("row " + str(a.row)), "subj": a.name, "check": "Recompute",
            "badge": "clears" if a.clears else "below", "status": "checked within scope",
            "result": "CLEARS THE RULE" if a.clears else "BELOW THE RULE",
            "det": "Prior " + money(a.prior) + ", current " + money(a.cur) + ", change "
                   + money(a.change) + ", "
                   + (("percent undefined on a zero prior balance (" + zero_policy_text(zp) + ")")
                      if a.pct is None else (pct_txt(a.pct) + " of the prior balance"))
                   + ". Dollar leg (more than " + money(floor_d) + "): "
                   + ("met" if lg["d"] else "not met") + ". Percent leg (at least "
                   + _plain(floor_p) + " percent): " + ("met" if lg["p"] else "not met") + ".",
            "ask": ""})
    ties = tie_totals(L)
    tiefail = 0
    for t in ties:
        if t["ok"] is False:
            tiefail += 1
            q("Failure", "total row", t["label"], t["det"], "Preparer",
              "Which is right, the total row or the lines under it?")
        rows.append({"id": run_id + "/T" + t["label"], "ev": evid(), "line": "total",
                     "subj": t["label"], "check": "Totals tie",
                     "badge": "info" if t["ok"] is None else ("pass" if t["ok"] else "fail"),
                     "status": "failed" if t["ok"] is False else
                               ("not checked" if t["ok"] is None else "checked within scope"),
                     "result": "KEPT OUT" if t["ok"] is None else ("TIES" if t["ok"] else "DOES NOT TIE"),
                     "det": t["det"],
                     "ask": "Which is right, the total row or the lines under it, and what is missing "
                            "from the paste?" if t["ok"] is False else ""})
    stats["totalsFail"] = tiefail
    if tiefail:
        note("bad", str(tiefail) + " section total" + (" does" if tiefail == 1 else "s do")
             + " not tie to the lines under " + ("it" if tiefail == 1 else "them")
             + ". Check the ledger paste before reading anything else: a line may have been left out "
               "of the copy.")

    # ---- 2. every sentence
    rows.append({"grp": "2. Every sentence: account binding, numeric role, units, calculation, "
                        "conclusion"})
    numset = {a.num for a in L["accounts"] if a.num}
    for s in sents:
        s["figs"] = figures(s["text"], numset)
        s["residue"] = list(s["figs"].rejected)
        s["numset"] = numset
        spent = {}
        for r in s["residue"]:
            d = re.sub(r"[^0-9]", "", str(r["raw"]))
            if d not in numset:
                continue
            seen = str(s["text"]).count(d)
            used = sum(1 for o in s["residue"] if re.sub(r"[^0-9]", "", str(o["raw"])) == d)
            if used >= seen:
                spent[d] = 1
        b = bind_sentence(s, L["accounts"], s["figs"], spent)
        s["bound"] = b["bound"]
        s["how"] = b["how"]
        s["conflicts"] = b["conflicts"]
        s["multi"] = len(s["bound"]) > 1
        if s["multi"]:
            clause_bind(s)
        negs = {}
        for c in spans_of(s["text"], RE_COARSE):
            n = negation_in(c["text"]) if claim_in(c["text"]) else None
            if n:
                negs[(c["at"], c["end"])] = n
        s["negs"] = negs

        def neg_of(at, _negs=negs):
            hit = None
            for (lo, hi), v in _negs.items():
                if lo <= at < hi:
                    hit = v
            return hit

        for a in s["bound"]:
            a.sent.append(s)
        s["st"] = ("checked within scope" if s["figs"] else "not checked") if s["bound"] \
            else "not checked"

        if not s["bound"]:
            bt = ("No account number, no account name and no exact figure in this sentence ties to a "
                  "ledger line.")
            q("Unmatched sentence", s["label"], s["text"],
              "nothing in this sentence binds it to a ledger line, so none of it was checked",
              "Reviewer", "Which account is this sentence about, and what amount does it rest on?")
        else:
            bt = "; ".join(acct_id(a) for a in s["bound"]) + " (" + s["how"] + ")"
        if s["conflicts"]:
            s["st"] = worse(s["st"], "needs review")
            bt += " Unresolved: " + "; ".join(
                c["f"]["raw"] + " is also exactly a figure on " + acct_id(c["a"])
                + ", which this sentence does not name" for c in s["conflicts"]) \
                + ". The checker does not settle that by the coincidence."
            for c in s["conflicts"]:
                q("Binding conflict", s["label"], s["text"],
                  c["f"]["raw"] + " binds " + acct_id(c["a"]) + " by figure while the sentence names "
                  + ("; ".join(acct_id(a) for a in s["bound"]) if s["bound"] else "no account")
                  + "; the binding is unresolved", "Reviewer", "Which line is this sentence about?")
        dup_hit = [a for a in s["bound"] if a.dup]
        if dup_hit:
            s["st"] = worse(s["st"], "needs review")
            bt += (" Account " + dup_hit[0].num + " appears on more than one row, so this sentence "
                   "cannot be tied to one line.")
        if L["colsUnconfirmed"]:
            s["st"] = worse(s["st"], "needs review")
        rows.append({"id": run_id + "/" + s["label"] + "/bind", "ev": evid(), "line": _acct_line(s),
                     "subj": s["text"], "label": s["label"], "check": "Binding",
                     "badge": ("review" if s["conflicts"] else "pass") if s["bound"] else "review",
                     "status": ("needs review" if s["conflicts"] else "checked within scope")
                               if s["bound"] else "not checked",
                     "result": ("BOUND, WITH A CONFLICT" if s["conflicts"] else "BOUND")
                               if s["bound"] else "UNMATCHED, REVIEW BY HAND",
                     "det": bt,
                     "ask": "" if s["bound"] else
                            "Which account is this sentence about, and what amount does it rest on?"})

        for r in s["residue"]:
            s["st"] = worse(s["st"], "not checked")
            q("Unparsed figure", s["label"], s["text"],
              "\u201c" + r["raw"] + "\u201d is " + r["why"] + ", so the checker did not read it and "
              "this sentence is not checked", "Preparer",
              "What is \u201c" + r["raw"] + "\u201d, and in what unit?")
            rows.append({"id": run_id + "/" + s["label"] + "/u" + str(r["at"]), "ev": evid(),
                         "line": _acct_line(s), "subj": s["text"], "label": s["label"],
                         "check": "Unparsed " + r["raw"], "badge": "info", "status": "not checked",
                         "result": "NOT READ",
                         "det": "\u201c" + r["raw"] + "\u201d is " + r["why"] + ". The accepted "
                                "grammar does not cover it, so it was neither compared nor discarded: "
                                "the sentence stays unchecked and the span is in the queue.",
                         "ask": "What is \u201c" + r["raw"] + "\u201d, and in what unit?"})

        for f in s["figs"]:
            bset = f["bind"] if (s["multi"] and f.get("bind")) else s["bound"]
            if not s["bound"]:
                res = {"st": "review", "txt": f["raw"] + " (" + f["unit"] + ", role " + f["role"]
                       + "): no account is bound, so there is nothing to compare it with.",
                       "ask": "Which line does this figure belong to?"}
            elif f["unit"] == "dollars":
                res = check_dollar(f, bset, s["bound"])
            else:
                res = check_percent(f, bset, R["ratios"], zero_policy_text(zp))
            if s["multi"] and not f.get("bind") and res["st"] == "checked" and res.get("via") != "ratio":
                q("Binding conflict", s["label"], s["text"],
                  f["raw"] + " agrees with " + "; ".join(acct_id(a) for a in s["bound"])
                  + " read together, and its own clause names no one of them, so which line it is the "
                    "figure for is unresolved", "Reviewer",
                  "Which account is " + f["raw"] + " the figure for?")
                res = {"st": "review",
                       "txt": f["raw"] + ": this sentence names " + str(len(s["bound"]))
                              + " accounts (" + "; ".join(acct_id(a) for a in s["bound"])
                              + ") and the clause it stands in binds it to none of them on its own. "
                              + res["txt"] + " A figure is not bound by agreeing with the sentence "
                              "read as a whole.",
                       "ask": "Which account is " + f["raw"] + " the figure for?"}
            nw = neg_of(f["at"])
            if nw and res["st"] != "review":
                q("Negated claim", s["label"], s["text"],
                  f["raw"] + " stands in a clause the words negate (\u201c" + nw + "\u201d), so what "
                  "it asserts is not settled", "Reviewer",
                  "What does this sentence say happened about " + f["raw"] + ", once the negation is "
                  "read?")
                res = {"st": "review",
                       "txt": f["raw"] + " stands in a clause the words negate (\u201c" + nw
                              + "\u201d). " + res["txt"] + " A negation is not read as the claim "
                              "without it and not as its opposite, so this figure is left open.",
                       "ask": "What does this sentence say happened about " + f["raw"]
                              + ", once the negation is read?"}
            f["st"] = res["st"]
            f["txt"] = res["txt"]
            st = ("checked within scope" if res["st"] == "checked"
                  else ("failed" if res["st"] == "failed" else "needs review"))
            s["st"] = worse(s["st"], st)
            if st != "checked within scope":
                q("Failure" if st == "failed"
                  else ("Unsupported numeric form" if f.get("plain") else "Unresolved figure"),
                  s["label"], s["text"], res["txt"], "Preparer", res["ask"])
            rows.append({"id": run_id + "/" + s["label"] + "/f" + str(f["at"]), "ev": evid(),
                         "line": _acct_line(s), "subj": s["text"], "label": s["label"],
                         "check": "Figure " + f["raw"], "badge": BADGE[st], "status": st,
                         "result": ("DOLLARS" if f["unit"] == "dollars"
                                    else ("PERCENT" if f["unit"] == "percent" else "PERCENTAGE POINTS"))
                                   + ", ROLE " + f["role"].upper(),
                         "det": res["txt"], "ask": res["ask"]})

        dirn = direction_on(s)
        if dirn:
            if dirn["bad"]:
                s["st"] = worse(s["st"], "failed")
                q("Failure", s["label"], s["text"], "; ".join(dirn["bad"]), "Preparer",
                  "Which way did this account actually move, and does the driver still hold once the "
                  "sign is right?")
            if dirn["voided"]:
                s["st"] = worse(s["st"], "needs review")
                q("Negated claim", s["label"], s["text"], "; ".join(dirn["voided"]), "Reviewer",
                  "Which way does this sentence say the account moved, once the negation is read?")
            dst = ("failed" if dirn["bad"] else
                   ("needs review" if dirn["voided"] else
                    ("checked within scope" if dirn["good"] else "not checked")))
            rows.append({"id": run_id + "/" + s["label"] + "/dir", "ev": evid(),
                         "line": _acct_line(s), "subj": s["text"], "label": s["label"],
                         "check": "Direction", "badge": BADGE[dst], "status": dst,
                         "result": "FAIL" if dirn["bad"] else
                                   ("NEGATED, NOT SETTLED" if dirn["voided"] else
                                    ("PASS" if dirn["good"] else "NOT STATED")),
                         "det": ("; ".join(dirn["bad"]) + ".") if dirn["bad"] else
                                (("; ".join(dirn["voided"]) + ".") if dirn["voided"] else
                                 (("; ".join(dirn["good"]) + ".") if dirn["good"] else
                                  "This sentence makes no claim about which way the account moved.")),
                         "ask": ("Which way did this account actually move, and does the driver still "
                                 "hold once the sign is right?") if dirn["bad"] else
                                (("Which way does this sentence say the account moved, once the "
                                  "negation is read?") if dirn["voided"] else "")})

        pc = policy_claims(s["text"])
        if pc and s["bound"]:
            a0 = s["bound"][0]
            pbad, pgood = [], []
            for c in pc:
                if c.get("leg") == "both":
                    if not a0.legs["d"] and not a0.legs["p"]:
                        pgood.append("neither leg is met on " + acct_id(a0))
                    else:
                        pbad.append("the memo says neither leg is met, but on " + acct_id(a0) + " the "
                                    + ("dollar" if a0.legs["d"] else "percent") + " leg is met")
                elif c.get("leg") == "dollar":
                    if not a0.legs["d"]:
                        pgood.append("the dollar leg is not met on " + acct_id(a0) + " ("
                                     + money(abs(a0.change)) + " is not more than " + money(floor_d)
                                     + ")")
                    else:
                        pbad.append("the memo says the dollar leg fails, but " + money(abs(a0.change))
                                    + " is more than " + money(floor_d))
                elif c.get("leg") == "percent":
                    if not a0.legs["p"]:
                        pgood.append("the percent leg is not met on " + acct_id(a0) + " ("
                                     + pct_cell(a0) + " is not at least " + _plain(floor_p)
                                     + " percent)")
                    else:
                        pbad.append("the memo says the percent leg fails, but " + pct_cell(a0)
                                    + " is at least " + _plain(floor_p) + " percent")
                elif c.get("owes") is False:
                    if not a0.clears:
                        pgood.append("no commentary is owed on " + acct_id(a0) + " under the rule as set")
                    else:
                        pbad.append("the memo says no commentary is owed, but " + acct_id(a0)
                                    + " clears the rule")
            if pbad:
                s["st"] = worse(s["st"], "failed")
                q("Failure", s["label"], s["text"], "; ".join(pbad), "Preparer",
                  "Is the threshold claim in this sentence right?")
            if s["st"] == "not checked" and not pbad:
                s["st"] = "checked within scope"
            rows.append({"id": run_id + "/" + s["label"] + "/pol", "ev": evid(),
                         "line": _acct_line(s), "subj": s["text"], "label": s["label"],
                         "check": "Threshold claim", "badge": "fail" if pbad else "pass",
                         "status": "failed" if pbad else "checked within scope",
                         "result": "FAIL" if pbad else "PASS",
                         "det": ("; ".join(pbad) if pbad else "; ".join(pgood)) + ".",
                         "ask": "Is the threshold claim in this sentence right?" if pbad else ""})

        if s["st"] == "checked within scope" and not s["figs"] and not pc:
            s["st"] = "not checked"
        if s["st"] in ("needs review", "not checked"):
            if s["bound"] and s["st"] == "not checked" and not s["figs"]:
                q("Unchecked sentence", s["label"], s["text"],
                  "this sentence carries no figure and makes no threshold claim, so nothing in it was "
                  "checked against the ledger", "Reviewer",
                  "Is this claim supported, and by which document?")
        key = ("checked" if s["st"] == "checked within scope" else
               ("review" if s["st"] == "needs review" else
                ("failed" if s["st"] == "failed" else "notchecked")))
        stats[key] += 1
        rows.append({"id": run_id + "/" + s["label"] + "/status", "ev": evid(),
                     "line": _acct_line(s), "subj": s["text"], "label": s["label"],
                     "check": "Sentence status", "badge": BADGE[s["st"]], "status": s["st"],
                     "result": s["st"].upper(), "det": _status_why(s), "ask": ""})

    # ---- 3. threshold and silence
    rows.append({"grp": "3. Threshold and silence"})
    for a in L["accounts"]:
        if a.clears and not a.sent:
            stats["silent"] += 1
            q("Silent line", a.num or ("row " + str(a.row)), a.name,
              "change " + money(a.change) + ", " + pct_cell(a)
              + ", clears the rule and no sentence in the memo explains it", "Controller",
              "What drove " + acct_id(a) + " this month, and what supports it?")
            rows.append({"id": run_id + "/S" + (a.num or str(a.row)), "ev": evid(),
                         "line": a.num or ("row " + str(a.row)), "subj": a.name, "check": "Silence",
                         "badge": "silent", "status": "failed", "result": "SILENT",
                         "det": "Change " + money(a.change) + ", " + pct_cell(a) + ", clears the rule "
                                "and no sentence in the memo explains it. This line owes an "
                                "explanation.",
                         "ask": "What drove " + acct_id(a) + " this month, and what supports it?"})
    for s in sents:
        if not s["bound"]:
            continue
        if any(a.clears for a in s["bound"]):
            continue
        rows.append({"id": run_id + "/" + s["label"] + "/thr", "ev": evid(), "line": _acct_line(s),
                     "subj": s["text"], "label": s["label"], "check": "Threshold", "badge": "info",
                     "status": s["st"], "result": "NO COMMENTARY OWED",
                     "det": "No commentary owed; fine if correct. "
                            + "; ".join(acct_id(a) + " moved " + money(a.change) + ", " + pct_cell(a)
                                        for a in s["bound"])
                            + ", which does not clear the rule.", "ask": ""})

    # ---- 4. the reviewer's queue
    rows.append({"grp": "4. The reviewer's queue, what a person still has to answer"})
    survivors = []
    for s in sents:
        if s["st"] != "checked within scope":
            continue
        survivors.append(s)
        rows.append({"id": run_id + "/" + s["label"] + "/rev", "ev": evid(), "line": _acct_line(s),
                     "subj": s["text"], "label": s["label"], "check": "Reviewer", "badge": "review",
                     "status": s["st"], "result": "FOR THE REVIEWER",
                     "det": "Every figure in this sentence was checked within the scope above and the "
                            "direction agrees with the sign. What is left is judgment, and the checker "
                            "does not make it.",
                     "ask": ["Is the driver named here supported by anything on file?",
                             "Is the period right (nothing pulled forward or deferred)?"]})
    for a in L["accounts"]:
        if len(a.sent) < 2:
            continue
        q("Read together", a.num or ("row " + str(a.row)), a.name,
          str(len(a.sent)) + " sentences land on this line ("
          + ", ".join(x["label"] for x in a.sent)
          + ") and the checker does not test them against each other", "Reviewer",
          "Do these sentences agree with one another, and if not, which one holds?")
        rows.append({"id": run_id + "/R" + (a.num or str(a.row)), "ev": evid(),
                     "line": a.num or ("row " + str(a.row)), "subj": a.name,
                     "check": "Read together", "badge": "review", "status": "needs review",
                     "result": "REVIEW",
                     "det": "Read together: " + str(len(a.sent)) + " sentences on this account ("
                            + ", ".join(x["label"] for x in a.sent)
                            + "). The checker does not test them against each other.",
                     "ask": "Do these sentences agree with one another, and if not, which one holds?"})
    for item in queue:
        rows.append({"id": run_id + "/Q" + item["ev"], "ev": item["ev"], "line": item["ref"],
                     "subj": item["subject"], "check": "Queue: " + item["kind"],
                     "badge": "fail" if item["kind"] in ("Failure", "Silent line") else "review",
                     "status": "failed" if item["kind"] in ("Failure", "Silent line")
                               else "needs review",
                     "result": item["kind"].upper(),
                     "det": re.sub(r"\.\s*\Z", "", str(item["issue"])) + ". Owner: " + item["owner"] + ".",
                     "ask": item["ask"]})
    stats["queue"] = len(queue)

    if not any(s["figs"] for s in sents):
        note("", "No dollar figure and no percent anywhere in the memo. Every sentence is therefore "
                 "not checked unless it makes a threshold claim, and the coverage strip says so rather "
                 "than reporting a clean run.")

    return CheckResult(runId=run_id, runAt=run_at or datetime.now(timezone.utc), srcV=src_v, sig=sig,
                       caseVersion=case_version, rows=rows, stats=stats, accounts=L["accounts"],
                       sents=sents, survivors=survivors, queue=queue, ratios=R["ratios"], ledger=L,
                       ledgerText=ledger_text, memoText=memo_text, ties=ties, ratioText=ratios or "",
                       period=period or "", version=memo_version or "", company=company or "",
                       reviewer=reviewer or "", floorD=floor_d, floorP=floor_p, rule=rule, zero=zp,
                       notes=notes, preview_facts=preview_facts, preview_body=preview_body)


class CheckerInputError(ValueError):
    """The page would refuse this input and print a message instead of a table."""


def _acct_line(s):
    return ", ".join((a.num or a.name) for a in s["bound"]) if s.get("bound") else "none"


def _status_why(s):
    if s["st"] == "failed":
        return "At least one check on this sentence failed. Nothing later in the run lifts that."
    if s["st"] == "needs review":
        return ("Something here is unresolved: a role the words do not give, a binding the checker "
                "will not settle, a percent it cannot compute, or a ledger question above it. It "
                "cannot be called checked until a person answers it.")
    if s["st"] == "not checked":
        return ("Nothing in this sentence could be tied to the ledger and tested. That is not the "
                "same as a sentence that was checked and found true.")
    return ("Every figure in this sentence carries a role read from the words, a unit, and an "
            "unrounded comparison with the ledger, and each one agreed. That is the whole of what "
            "was checked; the judgment is not.")


def _preview(L):
    """The parse preview the page writes as you type: the shape, the counts, and
    every row it did not treat as an account line."""
    facts = []
    body = []
    shape = ("Profit and loss with sections and totals, the shape QuickBooks Online and Xero export"
             if L["sections"] and L["totals"]
             else ("A plain ledger with a header row" if L["header"] else "A plain ledger, no header row"))
    dropped = [s for s in L["skipped"] if not s.get("keep")]
    kept = [s for s in L["skipped"] if s.get("keep")]
    facts.append(shape)
    facts.append(str(len(L["accounts"])) + " account line" + ("" if len(L["accounts"]) == 1 else "s")
                 + " found")
    if L["T"] >= 2:
        facts.append(str(L["T"]) + " numeric column" + ("" if L["T"] == 1 else "s") + ", prior is \""
                     + str(L["labels"][L["pick"]["p"]]) + "\" and current is \""
                     + str(L["labels"][L["pick"]["c"]]) + "\"")
    else:
        facts.append("no pair of numeric columns")
    if kept:
        facts.append(str(len(kept)) + " total row" + ("" if len(kept) == 1 else "s")
                     + " held back for the totals tie")
    if L["sections"]:
        facts.append(str(len(L["sections"])) + " section" + ("" if len(L["sections"]) == 1 else "s")
                     + ": " + ", ".join(s["name"] for s in L["sections"]))
    if dropped:
        facts.append(str(len(dropped)) + " row" + ("" if len(dropped) == 1 else "s") + " ignored")
    if L["dups"]:
        facts.append("duplicate account number" + ("" if len(L["dups"]) == 1 else "s") + ": "
                     + ", ".join(L["dups"]))
    if L["ambig"]:
        facts.append(str(len(L["ambig"])) + " row" + ("" if len(L["ambig"]) == 1 else "s")
                     + " refused as ambiguous, not read")
    if L["discarded"]:
        facts.append(str(len(L["discarded"])) + " numeric column"
                     + ("" if len(L["discarded"]) == 1 else "s") + " discarded: "
                     + ", ".join(str(L["labels"][i]) for i in L["discarded"]))
    if L["colsUnconfirmed"]:
        facts.append("column mapping not confirmed, confirm the two periods before reading a status")
    if dropped or kept:
        body.append("Rows the reader did not treat as account lines:")
        for s in sorted(dropped + kept, key=lambda x: x["n"]):
            t = re.sub(r"\s+", " ", str(s["t"]))
            if len(t) > 90:
                t = t[:88] + "\u2026"
            body.append("Line " + str(s["n"]) + ", \u201c" + t + "\u201d \u2014 " + s["why"] + ".")
    return facts, body
