"""The command-line runner.

    python -m second_pass check LEDGER MEMO            run the Second Pass contract
    python -m second_pass check --sample halyard       one of the four bundled cases
    python -m second_pass preflight                    what the AI layer will do here
    python -m second_pass cases                       list the defect pack
    python -m second_pass show --case case-01-june     print a case, no scoring
    python -m second_pass run --case case-01-june      run one review session
    python -m second_pass serve --port 8765            the local web interface
    python -m second_pass sim start|commit|finish      one simulated reviewer, step by step
    python -m second_pass results --dir sessions       aggregate a pilot

The command line is the fallback surface for the pilot. If a reviewer's browser
or the shared screen misbehaves on the night, the session still runs in a
terminal with the same state machine and the same log format, and the numbers
land in the same place.
"""

import argparse
import os
import re
import sys
import textwrap

from . import (__version__, NON_DELEGATION_RULE, cases, challenger, checker, results,
               session as session_mod, sim as sim_mod)


def _wrap(text, width=88, indent=""):
    return "\n".join(textwrap.fill(line, width=width, initial_indent=indent,
                                   subsequent_indent=indent) if line.strip() else ""
                     for line in text.splitlines())


def _bullet(text, width=88):
    """A hanging-indent bullet, so a wrapped rule still reads as one rule."""
    return textwrap.fill(text, width=width, initial_indent="  - ", subsequent_indent="    ")


def _print_rule():
    print("")
    print("SECOND PASS, a teach-back review trainer for month-end flux commentary")
    print("-" * 88)
    print(_wrap(NON_DELEGATION_RULE))
    print(_wrap("You will commit your own findings before this tool shows you anything it "
                "produced. That order is enforced and cannot be skipped."))
    print("-" * 88)


def _print_case(case):
    view = cases.reviewer_view(case)
    print("")
    print("%s, %s against %s" % (view["company"]["name"], view["period"]["current"], view["period"]["prior"]))
    print(_wrap(view["company"]["profile"]))
    print("")
    print(_wrap(view["materiality_rule"]))
    if view["materiality"].get("basis"):
        print(_wrap(view["materiality"]["basis"]))
    if view.get("margin_definition"):
        print(_wrap(view["margin_definition"]))
    print("")
    header = "%-6s %-42s %14s %14s %14s %9s" % ("Line", "Account", "Prior", "Current", "Variance", "Percent")
    print(header)
    print("-" * len(header))
    for row in view["accounts"]:
        flag = " *" if row["material"] else "  "
        print("%-6s %-42s %14s %14s %14s %9s%s" % (
            row["line"], row["name"][:42],
            cases.format_amount(row["prior"]), cases.format_amount(row["current"]),
            cases.format_amount(row["variance"]), cases.format_percent(row["percent"]), flag))
    print("")
    print("  * passes both legs of the threshold")
    print(_wrap(view["materiality_rule"], indent="  "))
    if view.get("subtotals"):
        print("")
        print(_wrap("Subtotals, computed from the balances above, so a ratio test does not "
                    "require adding the lines up by hand."))
        print("")
        for row in view["subtotals"]:
            print("%-6s %-42s %14s %14s %14s %9s" % (
                "", row["label"][:42],
                cases.format_amount(row["prior"]), cases.format_amount(row["current"]),
                cases.format_amount(row["variance"]), cases.format_percent(row["percent"])))
            print(_wrap("%s: %s" % (" + ".join(row["lines"]), row.get("note", "")), indent="       "))
    print("")
    print("Draft commentary from management")
    print("-" * 88)
    for sentence in view["commentary"]["sentences"]:
        print(_wrap("%s. %s" % (sentence["id"], sentence["text"]), indent=""))
    print("-" * 88)


def _ask(prompt, default=None):
    suffix = " [%s]: " % default if default is not None else ": "
    answer = input(prompt + suffix).strip()
    if not answer and default is not None:
        return str(default)
    return answer


def _ask_number(prompt, low, high, default=None):
    while True:
        raw = _ask(prompt, default)
        try:
            value = float(raw)
        except ValueError:
            print("  Enter a number between %s and %s." % (low, high))
            continue
        if value < low or value > high:
            print("  Enter a number between %s and %s." % (low, high))
            continue
        return value


def _collect_findings(label):
    print("")
    print(label)
    print("  One finding per line. Name the account and say what is wrong with it.")
    print("  Press Enter on an empty line when you are done.")
    findings = []
    while True:
        line = input("  %d> " % (len(findings) + 1)).strip()
        if not line:
            break
        findings.append(line)
    return findings


SAMPLE_KEYS = ["halyard", "brightwater", "kestrel", "ridgeline"]


def shared_cases_dir():
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "cases", "shared")


def load_sample(key):
    """One of the four bundled cases, the same inputs the browser loads."""
    path = os.path.join(shared_cases_dir(), key + ".json")
    if not os.path.exists(path):
        raise cases.CaseError("No bundled case named %s. There are four: %s."
                              % (key, ", ".join(SAMPLE_KEYS)))
    import json as _json
    with open(path, encoding="utf-8") as handle:
        return _json.load(handle)


def _read_text(path, what):
    if not os.path.exists(path):
        raise cases.CaseError("No %s file at %s." % (what, path))
    with open(path, encoding="utf-8") as handle:
        return handle.read()


def cmd_check(args):
    """Run the Second Pass contract over a ledger and a memo."""
    if args.sample:
        s = load_sample(args.sample)
        ledger, memo, ratios = s["ledger"], s["memo"], s["ratios"]
        th = s["thresholds"]
        dollar, percent = th["dollar"], th["percent"]
        rule, zero = th["rule"], th["zeroPrior"]
        period = args.period or s["period"]
        memo_version = args.memo_version or s["memoVersion"]
        company = args.company or s["company"]
        case_version = s["caseVersion"]
    else:
        if not args.ledger or not args.memo:
            raise cases.CaseError(
                "check takes a ledger file and a memo file, or --sample with one of: %s."
                % ", ".join(SAMPLE_KEYS))
        ledger = _read_text(args.ledger, "ledger")
        memo = _read_text(args.memo, "memo")
        ratios = _read_text(args.ratios, "ratios") if args.ratios else ""
        dollar, percent = args.dollar, args.percent
        rule = args.rule
        zero = "exclude" if args.zero_prior == "exclude" else "owing"
        period, memo_version = args.period or "", args.memo_version or ""
        company, case_version = args.company or "", ""

    try:
        result = checker.run_check(
            ledger, memo, ratios=ratios, dollar_floor=dollar, percent_floor=percent,
            rule=rule, zero_prior=zero, period=period, memo_version=memo_version,
            company=company, reviewer=args.reviewer or "", case_version=case_version)
    except checker.CheckerInputError as error:
        print("")
        print(_wrap(str(error)))
        return 2

    if args.format == "csv":
        sys.stdout.write(result.csv())
        sys.stdout.write("\n")
        return _exit_code(result, args)
    if args.format == "json":
        print(result.json_record())
        return _exit_code(result, args)
    if args.format == "prompt":
        print(result.reviewer_prompt())
        return _exit_code(result, args)

    for line in result.header_lines():
        print(_wrap(line))
    print("")
    print(_wrap(result.coverage_line()))
    print(_wrap("Coverage, not a verdict. \"Checked within scope\" means each figure carried a role "
                "the words gave it and the unrounded comparison with the ledger agreed. It does not "
                "mean the sentence is true."))
    for note in result.notes:
        print("")
        print(_wrap(re.sub(r"<[^>]+>", "", note)))
    print(result.table())
    print("")
    print("4. The reviewer's queue, what a person still has to answer")
    print("-" * 58)
    print(result.queue_list())
    return _exit_code(result, args)


def _exit_code(result, args):
    """A non-zero exit when a finding failed, so a firm can gate a close on it."""
    if not getattr(args, "fail_on_findings", False):
        return 0
    st = result.stats
    return 1 if (st["failed"] or st["silent"]) else 0


def cmd_preflight(args):
    status = challenger.key_status()
    chosen = challenger.select_provider(args.provider)
    print("Second Pass %s" % __version__)
    print("")
    print("API keys in this environment, presence only")
    for name, state in sorted(status.items()):
        print("  %-20s %s" % (name, state))
    print("")
    print("AI layer that will run: %s" % chosen)
    if chosen == "deterministic":
        print(_wrap("No key is present, so the challenge list is built by the deterministic "
                    "challenger from each case's own answer key, with the same citation rule and "
                    "the same refusal to hand over the explanation. The pilot does not depend on "
                    "a key, a network or an account."))
    else:
        print(_wrap("A key is present, so the challenge list is generated from the versioned "
                    "prompt in prompts/%s. Every returned challenge is checked for a real "
                    "account line, a numeric amount that ties to that account's own movement, "
                    "and the absence of approval language before a reviewer sees it. If nothing "
                    "survives, the run falls back to the deterministic challenger and the log "
                    "says so." % challenger.PROMPT_FILE))
    print("")
    print("Prompt: %s version %s, file prompts/%s" % (
        challenger.PROMPT_ID, challenger.PROMPT_VERSION, challenger.PROMPT_FILE))
    found = cases.list_cases(args.cases_dir)
    print("Cases loaded: %d" % len(found))
    for case_id, title, _path in found:
        case = cases.load_case(case_id, args.cases_dir)
        print("  %-18s %-44s %2d defects, %d weak challenges" % (
            case_id, title, len(case["answer_key"]), len(case.get("distractors", []))))
    return 0


def cmd_cases(args):
    for case_id, title, path in cases.list_cases(args.cases_dir):
        case = cases.load_case(path)
        kinds = ", ".join(sorted(set(defect["type"] for defect in case["answer_key"])))
        print("%s  %s" % (case_id, title))
        print("  accounts %d, sentences %d, defects %d, weak challenges %d" % (
            len(case["accounts"]), len(case["commentary"]["sentences"]),
            len(case["answer_key"]), len(case.get("distractors", []))))
        print("  kinds: %s" % kinds)
        print("")
    return 0


def cmd_show(args):
    case = cases.load_case(args.case, args.cases_dir)
    _print_case(case)
    if args.key:
        print("")
        print("ANSWER KEY, facilitator only. Do not show this to a reviewer before they finish.")
        print("-" * 88)
        for defect in case["answer_key"]:
            print("%s  %s  account %s  %s" % (
                defect["id"], cases.DEFECT_TYPE_LABELS[defect["type"]],
                defect["line"], cases.format_amount(defect["amount"])))
            print(_wrap(defect["correct"], indent="    "))
        for distractor in case.get("distractors", []):
            print("%s  Weak challenge, should be rejected  account %s" % (distractor["id"], distractor["line"]))
            print(_wrap(distractor["why_wrong"], indent="    "))
    return 0


def cmd_run(args):
    case = cases.load_case(args.case, args.cases_dir)
    reviewer = args.reviewer or session_mod.next_reviewer_alias(case["id"], args.sessions_dir)
    review = session_mod.ReviewSession(case, reviewer, provider=args.provider, root=args.sessions_dir)

    _print_rule()
    print("Case %s. You are reviewer %s. No name is recorded anywhere." % (case["id"], reviewer))
    _print_case(case)

    print("")
    print("Before you start, two questions. Answer them on instinct.")
    soundness = _ask_number("  How sound does this memo look to you, 1 poor to 5 sound", 1, 5)
    confidence = _ask_number("  Of the problems in it, what percent do you expect to find, 0 to 100", 0, 100)
    review.open_phase_1(confidence, soundness)

    findings = _collect_findings("PHASE ONE, unaided. What would you challenge?")
    count = review.commit_findings(findings)
    print("")
    print("  Committed %d finding(s). They are sealed and cannot be edited." % count)
    print("  Phase one took %s seconds." % review.data["seconds_phase_1"])

    print("")
    confidence_2 = _ask_number(
        "  Before the tool speaks: what percent of the problems do you now think you found, 0 to 100",
        0, 100, default=int(confidence))
    review.set_confidence_aided(confidence_2)

    challenges = review.reveal_challenges()
    print("")
    print("PHASE TWO, the challenge list. %d challenge(s), produced by the %s layer." % (
        len(challenges), review.challenger_meta["provider_used"]))
    print(_wrap("Not all of these are right. Accept the ones that hold and reject the ones that "
                "do not, and give a reason either way in your own words. A verdict without a "
                "reason of at least %d words does not count." % review.min_reason_words))
    print(_wrap("Each one carries a one-word tag saying what kind of test to run first: %s. The "
                "tag says nothing about whether the challenge holds. The amount in a citation is "
                "the movement of the account named, current less prior, so check it against the "
                "table before you answer." % ", ".join(cases.CHALLENGE_TAGS)))
    for challenge in challenges:
        print("")
        print("-" * 88)
        print("%s  %s" % (challenge["id"], challenge["citation"]))
        print(_wrap(challenge["question"]))
        if challenge.get("evidence"):
            print(_wrap("What would count as evidence: %s" % challenge["evidence"], indent="  "))
        while True:
            verdict = _ask("  accept or reject").strip().lower()
            if verdict in ("accept", "reject", "a", "r"):
                verdict = "accept" if verdict.startswith("a") else "reject"
                break
            print("    Type accept or reject.")
        reason = _ask("  why, in your own words")
        review.record_teachback(challenge["id"], verdict, reason)
        words = len(reason.split())
        if words < review.min_reason_words:
            print("    Recorded, but that reason is %d words and the threshold is %d, so it does "
                  "not count as a teach-back." % (words, review.min_reason_words))

    extra = _collect_findings("Anything the list did not raise that you still want to challenge?")
    review.add_aided_findings(extra)

    result = review.finish()
    path = os.path.join(session_mod.sessions_dir(args.sessions_dir), review.session_id + ".json")
    print("")
    print("=" * 88)
    from . import scoring
    print(scoring.format_scorecard(result, case))
    print("")
    print("Session log written to %s" % path)
    return 0


def cmd_serve(args):
    from . import server
    server.serve(port=args.port, cases_root=args.cases_dir, sessions_root=args.sessions_dir,
                 provider=args.provider, open_browser=not args.no_browser)
    return 0


def cmd_sim(args):
    if not args.sim_command:
        print("Usage: python -m second_pass sim start|commit|finish --dir <session dir>")
        return 0
    return {"start": cmd_sim_start, "commit": cmd_sim_commit,
            "finish": cmd_sim_finish}[args.sim_command](args)


def cmd_sim_start(args):
    directory_arg = sim_mod.check_dir(args.dir, allow_any=args.allow_any_dir)
    review, _state = sim_mod.start(
        args.case, args.reviewer, directory_arg,
        cases_root=args.cases_dir, sessions_root=args.sessions_dir,
        provider=args.provider, persona=args.persona)
    directory = os.path.abspath(directory_arg)
    print("Simulated session %s opened." % review.session_id)
    print("  Case      %s" % review.case["id"])
    print("  Reviewer  %s%s" % (review.reviewer,
                                ", persona %s" % args.persona if args.persona else ""))
    print("  Folder    %s" % directory)
    print("")
    print("Read %s. Do not open any other file." % os.path.join(directory, sim_mod.VIEW_FILE))
    print("")
    print(_wrap("Then write %s in that folder, holding your own findings, the share of the "
                "problems you believe you found, and how sound the memo looked to you. One "
                "finding per entry, and name the account in each one."
                % sim_mod.FINDINGS_FILE))
    print("")
    for line in sim_mod.FINDINGS_SCHEMA.splitlines():
        print("  " + line)
    print("")
    for rule in sim_mod.FINDINGS_RULES:
        print(_bullet(rule))
    print("")
    print(_wrap("Then run: python -m second_pass sim commit --dir %s" % directory_arg))
    print(_wrap("The challenge list does not exist until you do. It is not written anywhere in "
                "this folder, in this process, or on any wire, so there is nothing to look at "
                "ahead of time."))
    return 0


def cmd_sim_commit(args):
    directory_arg = sim_mod.check_dir(args.dir, allow_any=args.allow_any_dir, must_exist=True)
    review, public = sim_mod.commit(directory_arg)
    directory = os.path.abspath(directory_arg)
    print("Findings sealed. %d finding(s), and they cannot be edited." % len(review.data["findings_unaided"]))
    print("Phase one took %s seconds." % review.data["seconds_phase_1"])
    print("")
    print("Challenge list released: %d challenge(s) from the %s layer." % (
        len(public), review.challenger_meta["provider_used"]))
    print("  Written to %s" % os.path.join(directory, sim_mod.CHALLENGES_FILE))
    print("")
    print(_wrap("Read that file. Some of those challenges do not hold. Accept the ones that do "
                "and reject the ones that do not, with a reason in your own words for each, and "
                "write %s in the same folder." % sim_mod.TEACHBACK_FILE))
    print("")
    for line in sim_mod.TEACHBACK_SCHEMA.splitlines():
        print("  " + line)
    print("")
    for rule in sim_mod.TEACHBACK_RULES:
        print(_bullet(rule))
    print("")
    print(_wrap("Then run: python -m second_pass sim finish --dir %s" % directory_arg))
    return 0


def cmd_sim_finish(args):
    directory_arg = sim_mod.check_dir(args.dir, allow_any=args.allow_any_dir, must_exist=True)
    review, result, path, log = sim_mod.finish(directory_arg)
    print("")
    print("=" * 88)
    print(sim_mod.score_block(result, review.case, debrief=args.debrief))
    print("")
    print("Session log written to %s" % path)
    print("It carries simulated: true and persona: %s." % (log.get("persona") or "not stated"))
    return 0


def cmd_results(args):
    directory = args.dir or session_mod.sessions_dir(args.sessions_dir)
    logs = results.load_logs(directory, only=getattr(args, "only", None))
    aggregated = results.aggregate(logs)
    print(results.format_report(aggregated))
    if args.markdown:
        print("")
        print(results.format_markdown(aggregated))
    if args.out:
        with open(args.out, "w", encoding="utf-8") as handle:
            handle.write(results.format_report(aggregated))
            handle.write("\n\n")
            handle.write(results.format_markdown(aggregated))
            handle.write("\n")
        print("")
        print("Written to %s" % args.out)
    return 0


def _add_common(parser, suppress=False):
    """The shared options, accepted before or after the subcommand.

    A facilitator typing the command on the night should not have to remember
    which side of the verb a flag goes on, so both work.
    """
    default = argparse.SUPPRESS if suppress else None
    parser.add_argument("--cases-dir", default=default, help="folder of case files (default: ./cases)")
    parser.add_argument("--sessions-dir", default=default, help="folder for session logs (default: ./sessions)")
    parser.add_argument("--provider", default=(argparse.SUPPRESS if suppress else "auto"),
                        choices=["auto", "anthropic", "openai", "deterministic"],
                        help="which AI layer to use (default: auto)")


def build_parser():
    parser = argparse.ArgumentParser(
        prog="second_pass",
        description="Second Pass, a teach-back review trainer for month-end flux commentary.")
    parser.add_argument("--version", action="version", version="Second Pass " + __version__)
    _add_common(parser)

    common = argparse.ArgumentParser(add_help=False)
    _add_common(common, suppress=True)

    subparsers = parser.add_subparsers(dest="command")

    check = subparsers.add_parser(
        "check", parents=[common],
        help="run the Second Pass contract over a ledger and a memo")
    check.add_argument("ledger", nargs="?", default=None, help="the ledger file, pasted as it comes")
    check.add_argument("memo", nargs="?", default=None, help="the drafted commentary")
    check.add_argument("--sample", default=None, choices=SAMPLE_KEYS,
                       help="run one of the four bundled cases instead of two files")
    check.add_argument("--dollar", default="25000", help="the dollar floor (default 25000)")
    check.add_argument("--percent", default="10", help="the percent floor (default 10)")
    check.add_argument("--rule", default="both", choices=["both", "either"],
                       help="both legs, or either leg (default both)")
    check.add_argument("--zero-prior", dest="zero_prior", default="owe",
                       choices=["owe", "exclude"],
                       help="a zero prior balance owes commentary on any movement, or is excluded "
                            "from the rule (default owe)")
    check.add_argument("--ratios", default=None, help="a file of ratio definitions, one per line")
    check.add_argument("--format", default="table", choices=["table", "csv", "json", "prompt"],
                       help="table (default), the CSV export, the JSON record, or Prompt 2")
    check.add_argument("--period", default=None, help="the close period, as it should be filed")
    check.add_argument("--memo-version", dest="memo_version", default=None)
    check.add_argument("--company", default=None)
    check.add_argument("--reviewer", default=None)
    check.add_argument("--fail-on-findings", dest="fail_on_findings", action="store_true",
                       help="exit 1 when a sentence failed or a line is silent, for a build step")

    subparsers.add_parser("preflight", parents=[common],
                          help="report key presence, the AI layer and the loaded cases")
    subparsers.add_parser("cases", parents=[common], help="list the defect pack")

    show = subparsers.add_parser("show", parents=[common], help="print a case as a reviewer sees it")
    show.add_argument("--case", required=True)
    show.add_argument("--key", action="store_true", help="also print the answer key, facilitator only")

    run = subparsers.add_parser("run", parents=[common], help="run one review session in the terminal")
    run.add_argument("--case", required=True)
    run.add_argument("--reviewer", default=None, help="R1 to R99. Assigned automatically if omitted.")

    serve = subparsers.add_parser("serve", parents=[common], help="serve the local web interface")
    serve.add_argument("--port", type=int, default=8765)
    serve.add_argument("--no-browser", action="store_true")

    sim = subparsers.add_parser(
        "sim", parents=[common],
        help="run one simulated reviewer through the same state machine, step by step")
    sim_sub = sim.add_subparsers(dest="sim_command")

    dir_help = ("the session folder for this reviewer and case, inside sim/runs. Use forward "
                "slashes: sim/runs/R1-case-01-june. Backslashes are eaten by bash.")
    any_dir_help = ("allow a --dir outside sim/runs. Without it, a path that would land "
                    "elsewhere is refused before anything is written.")

    sim_start = sim_sub.add_parser("start", parents=[common],
                                   help="create the session and write view.md")
    sim_start.add_argument("--case", required=True)
    sim_start.add_argument("--reviewer", required=True, help="R1 to R99. Names are refused.")
    sim_start.add_argument("--dir", required=True, help=dir_help)
    sim_start.add_argument("--allow-any-dir", action="store_true", help=any_dir_help)
    sim_start.add_argument("--persona", default=None, choices=list(sim_mod.PERSONAS),
                           help="which persona file the reviewer was given")

    sim_commit = sim_sub.add_parser("commit", parents=[common],
                                    help="seal findings.json and release the challenge list")
    sim_commit.add_argument("--dir", required=True, help=dir_help)
    sim_commit.add_argument("--allow-any-dir", action="store_true", help=any_dir_help)

    sim_finish = sim_sub.add_parser("finish", parents=[common],
                                    help="record teachback.json, score, and write the session log")
    sim_finish.add_argument("--dir", required=True, help=dir_help)
    sim_finish.add_argument("--allow-any-dir", action="store_true", help=any_dir_help)
    sim_finish.add_argument("--debrief", action="store_true",
                            help="also print the answer key, facilitator only")

    results_cmd = subparsers.add_parser("results", parents=[common],
                                        help="aggregate session logs into pilot numbers")
    results_cmd.add_argument("--dir", default=None)
    results_cmd.add_argument("--out", default=None)
    results_cmd.add_argument("--markdown", action="store_true")
    results_cmd.add_argument("--only", default=None, choices=["simulated", "human"],
                             help="keep only simulated reviewers, or only human ones")
    return parser


def main(argv=None):
    # The findings carry the page's own punctuation. A console that cannot take
    # it should print a run, not raise on the first middot.
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    parser = build_parser()
    args = parser.parse_args(argv)
    if not args.command:
        parser.print_help()
        return 0
    handlers = {
        "check": cmd_check,
        "preflight": cmd_preflight,
        "cases": cmd_cases,
        "show": cmd_show,
        "run": cmd_run,
        "serve": cmd_serve,
        "sim": cmd_sim,
        "results": cmd_results,
    }
    try:
        return handlers[args.command](args)
    except (cases.CaseError, session_mod.WithholdingError, session_mod.ReviewerError,
            challenger.ChallengerError, sim_mod.SimError) as error:
        print("")
        print("Stopped: %s" % error)
        return 2
    except KeyboardInterrupt:
        print("")
        print("Interrupted. Nothing was scored and no log was written for this session.")
        return 130


if __name__ == "__main__":
    sys.exit(main())
