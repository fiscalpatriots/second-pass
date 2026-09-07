"""The local web interface. One page, no frameworks, standard library only.

The page is a view. Every rule that matters is enforced on this side of the
wire, because a rule enforced in a browser is a rule enforced until somebody
opens the developer console.

    The case payload is built by cases.reviewer_view(), which strips the answer
    key and the distractors. There is no route that serves a raw case.

    The challenge list does not exist until GET /api/session/<id>/challenges is
    called, and that route returns 409 until the reviewer has committed their
    findings and stated their confidence. Nothing is generated early and hidden
    in the page, so there is nothing early to find.

    Findings are sealed by POST /commit. A second commit is refused.

    The answer key is served by POST /finish and nowhere else.

Binds to 127.0.0.1. This is a tool for a room, over a screen share or on each
reviewer's own machine, and it should not be reachable from a network.
"""

import json
import os
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from . import __version__, NON_DELEGATION_RULE, cases, challenger, results, scoring, session as session_mod

_SESSIONS = {}
_LOCK = threading.Lock()

_CONFIG = {
    "cases_root": None,
    "sessions_root": None,
    "provider": "auto",
}


def web_dir():
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "web")


class Handler(BaseHTTPRequestHandler):
    server_version = "SecondPass/" + __version__

    def log_message(self, fmt, *args):
        # One line per request, quiet enough to run beside a screen share.
        print("  %s %s" % (self.command, self.path))

    # ------------------------------------------------------------- plumbing

    def _send(self, status, payload, content_type="application/json"):
        if content_type == "application/json":
            body = json.dumps(payload).encode("utf-8")
        else:
            body = payload if isinstance(payload, bytes) else str(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type + ("; charset=utf-8" if "json" not in content_type else ""))
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self):
        length = int(self.headers.get("Content-Length") or 0)
        if not length:
            return {}
        raw = self.rfile.read(length).decode("utf-8")
        try:
            return json.loads(raw)
        except ValueError:
            return {}

    def _session(self, session_id):
        with _LOCK:
            review = _SESSIONS.get(session_id)
        if review is None:
            raise KeyError("No session '%s'. Start again from the first screen." % session_id)
        return review

    # --------------------------------------------------------------- routing

    def do_GET(self):
        path = self.path.split("?")[0]
        try:
            if path in ("/", "/index.html"):
                return self._serve_page()
            if path == "/api/config":
                return self._send(200, self._config_payload())
            if path == "/api/results":
                directory = session_mod.sessions_dir(_CONFIG["sessions_root"])
                aggregated = results.aggregate(results.load_logs(directory))
                return self._send(200, {
                    "report": results.format_report(aggregated),
                    "markdown": results.format_markdown(aggregated),
                    "summary": aggregated["summary"],
                })
            if path.startswith("/api/session/"):
                parts = path.split("/")
                session_id, tail = parts[3], parts[4] if len(parts) > 4 else ""
                review = self._session(session_id)
                if tail == "case":
                    return self._send(200, {"case": review.case_for_reviewer(), "state": review.state})
                if tail == "challenges":
                    challenges = review.reveal_challenges()
                    return self._send(200, {
                        "challenges": challenges,
                        "state": review.state,
                        "provider_used": review.challenger_meta["provider_used"],
                        "min_reason_words": review.min_reason_words,
                    })
                if tail == "state":
                    return self._send(200, {"state": review.state})
            return self._send(404, {"error": "no route %s" % path})
        except session_mod.WithholdingError as error:
            # The single most important response in the program. It carries the
            # reason and nothing else: no challenge text, no defect, no key.
            return self._send(409, {"error": str(error), "withheld": True})
        except KeyError as error:
            return self._send(404, {"error": str(error)})
        except Exception as error:  # pragma: no cover, surfaced to the facilitator
            return self._send(500, {"error": "%s: %s" % (type(error).__name__, error)})

    def do_POST(self):
        path = self.path.split("?")[0]
        try:
            payload = self._read_json()
            if path == "/api/session":
                return self._create_session(payload)
            if path.startswith("/api/session/"):
                parts = path.split("/")
                session_id, tail = parts[3], parts[4] if len(parts) > 4 else ""
                review = self._session(session_id)
                if tail == "phase1":
                    review.open_phase_1(payload.get("confidence"), payload.get("soundness"))
                    return self._send(200, {"state": review.state})
                if tail == "commit":
                    count = review.commit_findings(payload.get("findings") or [])
                    return self._send(200, {
                        "state": review.state,
                        "committed": count,
                        "seconds": review.data["seconds_phase_1"],
                    })
                if tail == "confidence2":
                    review.set_confidence_aided(payload.get("confidence"))
                    return self._send(200, {"state": review.state})
                if tail == "teachback":
                    review.record_teachback(payload.get("challenge_id"),
                                            payload.get("verdict"),
                                            payload.get("reason"))
                    return self._send(200, {
                        "state": review.state,
                        "outstanding": review.outstanding_teachbacks(),
                    })
                if tail == "aided":
                    review.add_aided_findings(payload.get("findings") or [])
                    return self._send(200, {"state": review.state})
                if tail == "finish":
                    result = review.finish()
                    return self._send(200, {
                        "state": review.state,
                        "scores": result["scores"],
                        "scorecard": scoring.format_scorecard(result, review.case),
                        "teachback_detail": result["teachback_detail"],
                        "answer_key": self._key_payload(review.case),
                        "log_file": review.session_id + ".json",
                    })
            return self._send(404, {"error": "no route %s" % path})
        except (session_mod.WithholdingError, session_mod.ReviewerError) as error:
            return self._send(409, {"error": str(error), "withheld": True})
        except cases.CaseError as error:
            return self._send(400, {"error": str(error)})
        except KeyError as error:
            return self._send(404, {"error": str(error)})
        except Exception as error:  # pragma: no cover
            return self._send(500, {"error": "%s: %s" % (type(error).__name__, error)})

    # -------------------------------------------------------------- handlers

    def _serve_page(self):
        path = os.path.join(web_dir(), "index.html")
        with open(path, "rb") as handle:
            body = handle.read()
        return self._send(200, body, content_type="text/html")

    def _config_payload(self):
        found = []
        for case_id, title, _path in cases.list_cases(_CONFIG["cases_root"]):
            case = cases.load_case(case_id, _CONFIG["cases_root"])
            found.append({
                "id": case_id,
                "title": title,
                "period": case["period"]["current"],
                "defects": len(case["answer_key"]),
                "accounts": len(case["accounts"]),
                "sentences": len(case["commentary"]["sentences"]),
            })
        return {
            "version": __version__,
            "rule": NON_DELEGATION_RULE,
            "keys": challenger.key_status(),
            "provider": challenger.select_provider(_CONFIG["provider"]),
            "prompt": "prompts/" + challenger.PROMPT_FILE,
            "cases": found,
            "reviewers": ["R%d" % number for number in range(1, 9)],
            "suggested_reviewer": session_mod.next_reviewer_alias(root=_CONFIG["sessions_root"]),
        }

    def _create_session(self, payload):
        case = cases.load_case(payload.get("case_id"), _CONFIG["cases_root"])
        reviewer = payload.get("reviewer") or session_mod.next_reviewer_alias(root=_CONFIG["sessions_root"])
        review = session_mod.ReviewSession(case, reviewer,
                                           provider=_CONFIG["provider"],
                                           root=_CONFIG["sessions_root"])
        with _LOCK:
            _SESSIONS[review.session_id] = review
        return self._send(200, {
            "session_id": review.session_id,
            "reviewer": review.reviewer,
            "state": review.state,
            "case": review.case_for_reviewer(),
        })

    @staticmethod
    def _key_payload(case):
        key = []
        for defect in case["answer_key"]:
            key.append({
                "id": defect["id"],
                "type": defect["type"],
                "label": cases.DEFECT_TYPE_LABELS[defect["type"]],
                "line": defect["line"],
                "amount": defect["amount"],
                "sentence": defect.get("sentence"),
                "claim": defect["claim"],
                "correct": defect["correct"],
            })
        for distractor in case.get("distractors", []):
            key.append({
                "id": distractor["id"],
                "type": "weak_challenge",
                "label": "Weak challenge, should be rejected",
                "line": distractor["line"],
                "amount": distractor.get("amount"),
                "sentence": distractor.get("sentence"),
                "claim": distractor["text"],
                "correct": distractor["why_wrong"],
            })
        return key


def make_server(port=8765, cases_root=None, sessions_root=None, provider="auto"):
    _CONFIG["cases_root"] = cases_root
    _CONFIG["sessions_root"] = sessions_root
    _CONFIG["provider"] = provider
    return ThreadingHTTPServer(("127.0.0.1", port), Handler)


def serve(port=8765, cases_root=None, sessions_root=None, provider="auto", open_browser=True):
    httpd = make_server(port, cases_root, sessions_root, provider)
    url = "http://127.0.0.1:%d/" % port
    print("")
    print("Second Pass %s is serving at %s" % (__version__, url))
    print("AI layer: %s. Keys: %s." % (
        challenger.select_provider(provider),
        ", ".join("%s %s" % (name, state) for name, state in sorted(challenger.key_status().items()))))
    print("Sessions will be written to %s" % session_mod.sessions_dir(sessions_root))
    print("Stop with Ctrl+C.")
    print("")
    if open_browser:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("")
        print("Stopped.")
    finally:
        httpd.server_close()
