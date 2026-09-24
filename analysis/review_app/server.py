"""Review server for Homework 4.

Forked from ``analysis/server.py`` (the instructor's reference interface) and
adapted. What changed and why:

* ``STATE_DIR`` points at ``analysis/state/``, the committed state the handout
  asks for, rather than a directory beside this file.
* A new ``/api/labels`` endpoint. The reference has no structured labeling
  surface at all: it stores free-text annotations and writes a Langfuse score
  only when an annotation happens to carry both a ``mode`` and a 0/1 ``label``.
  Part E needs a present/absent judgment for every trace and mode pair, mirrored
  under ``analysis/state/labels/`` as one file per mode, so labeling gets its
  own endpoint and its own files.
* A judgment is made against a *conversation* but written against every one of
  its turn trace identifiers, because Cartwheel opens one Langfuse trace per
  user turn. Labeling per turn would hide the failures that only exist across
  turns; scoring only the first turn would leave the later turns of 51
  conversations unscored. See ``build_samples.py`` for the grouping.
* The demo ``--replay`` path is gone. It replayed the course's canned
  ``state/demo_annotations.json`` on a timer for a stage demonstration; this
  server is for real review, and the canned notes are not the student's.

Unchanged from the reference: the file-backed JSON API contract, the atomic
writes, the permissive local CORS, and the quiet access log, so the same UI
conventions and the ``review-loop.md`` watcher keep working.

API:

    GET  /                    the HTML review app
    GET  /api/samples         current sample set
    POST /api/samples         push a new or updated sample set
    GET  /api/annotations     current human annotations (free-text open codes)
    POST /api/annotations     save annotations (the app posts on every change)
    GET  /api/graph           the 2D projection for the map view
    GET  /api/patterns        the taxonomy as the agent currently holds it
    POST /api/patterns        push the updated taxonomy
    GET  /api/suggestions     agent depth-scan suggestions awaiting a decision
    POST /api/suggestions     push suggestions
    GET  /api/labels          {mode: {conversation_id: 0|1}}
    POST /api/labels          record one binary judgment, mirror + Langfuse score

Run it:

    python analysis/review_app/server.py
    python analysis/review_app/server.py --port 8021 --no-langfuse
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
STATE_DIR = HERE.parent / "state"
LABELS_DIR = STATE_DIR / "labels"
UI_DIR = HERE / "ui"

# HW5. The judge is calibrated against a label set that differs from HW4's in
# three ways, so it lives in its own files rather than extending Part E's grid:
# one row per conversation instead of one per turn, a larger sample (the 105
# HW4 conversations plus newly mined candidates), and the inverted convention
# the handout mandates -- 1 = Pass, 0 = Fail, so that Pass is the positive
# class in TPR/TNR. Writing any of that into analysis/state/labels/ would
# change HW4's committed counts and silently flip the meaning of its rows.
HW5_LABELS_DIR = STATE_DIR / "hw5_labels"
HW5_SAMPLES = STATE_DIR / "hw5_samples.json"
HW5_JUDGMENTS = STATE_DIR / "hw5_judge_view.json"
HW5_MODE = "unrequested_information"
HW5_ENABLED = False

# Set by --no-langfuse, so a review session can run with the stack down and
# still keep a complete local mirror.
LANGFUSE_ENABLED = True

API_FILES: dict[str, Path] = {
    "/api/samples": STATE_DIR / "samples.json",
    "/api/annotations": STATE_DIR / "annotations.json",
    "/api/graph": STATE_DIR / "graph.json",
    "/api/patterns": STATE_DIR / "patterns.json",
    "/api/suggestions": STATE_DIR / "suggestions.json",
}

API_DEFAULTS: dict[str, Any] = {
    "/api/samples": [],
    "/api/annotations": [],
    "/api/graph": {"nodes": [], "clusters": []},
    "/api/patterns": {},
    "/api/suggestions": [],
}


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_json(path: Path, default: Any) -> Any:
    """Return the parsed JSON at ``path``, or ``default`` if missing or bad."""
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return default


def _write_json(path: Path, data: Any) -> None:
    """Write ``data`` to ``path`` atomically (write temp, then replace)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)


# ---------------------------------------------------------------------------
# labels
# ---------------------------------------------------------------------------


def _label_path(mode: str) -> Path:
    safe = "".join(ch for ch in mode if ch.isalnum() or ch in "._-")
    if not safe:
        raise ValueError("a mode name must contain at least one usable character")
    return LABELS_DIR / (safe + ".jsonl")


def _read_label_rows(mode: str) -> list[dict[str, Any]]:
    path = _label_path(mode)
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def _write_label_rows(mode: str, rows: list[dict[str, Any]]) -> None:
    path = _label_path(mode)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows),
        encoding="utf-8",
    )
    tmp.replace(path)


def _all_labels() -> dict[str, dict[str, int]]:
    """Return ``{mode: {conversation_id: label}}`` for the labeling grid.

    Keyed by conversation because that is the unit a human judges; the
    per-trace rows stay in the files for Part E reporting.
    """
    out: dict[str, dict[str, int]] = {}
    if not LABELS_DIR.exists():
        return out
    for path in sorted(LABELS_DIR.glob("*.jsonl")):
        mode = path.stem
        by_conversation: dict[str, int] = {}
        for row in _read_label_rows(mode):
            cid = row.get("conversation_id")
            if cid is not None and row.get("label") in (0, 1):
                by_conversation[str(cid)] = int(row["label"])
        out[mode] = by_conversation
    return out


def _hw5_label_path(mode: str) -> Path:
    safe = "".join(ch for ch in mode if ch.isalnum() or ch in "._-")
    if not safe:
        raise ValueError("a mode name must contain at least one usable character")
    return HW5_LABELS_DIR / (safe + ".jsonl")


def _hw5_rows(mode: str) -> list[dict[str, Any]]:
    path = _hw5_label_path(mode)
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def _hw5_live(mode: str) -> dict[str, dict[str, Any]]:
    """Collapse the append-only HW5 label log to the live row per conversation.

    Mirrors ``analysis.helpers.tools._load_labels``: a row carrying
    ``superseded_by`` is dead, and among the survivors for one conversation the
    last written wins.
    """
    live: dict[str, dict[str, Any]] = {}
    for row in _hw5_rows(mode):
        if row.get("superseded_by"):
            continue
        cid = row.get("conversation_id")
        if cid is not None and row.get("label") in (0, 1):
            live[str(cid)] = row
    return live


def _hw5_record(payload: dict[str, Any]) -> dict[str, Any]:
    """Record one HW5 conversation judgment, append-only.

    ``label`` is 1 for Pass and 0 for Fail, the handout's convention. A flip
    appends a new row and stamps ``superseded_by`` on the row it replaces, so
    the file keeps the full history -- which is the evidence for the Part C
    "your label was wrong" branch. ``label: null`` retires the current row
    without writing a replacement.
    """
    mode = str(payload.get("mode") or HW5_MODE).strip()
    cid = str(payload.get("conversation_id") or "").strip()
    if not cid:
        raise ValueError("conversation_id is required")
    label = payload.get("label")
    if label not in (0, 1, None):
        raise ValueError("label must be 1 (Pass), 0 (Fail) or null")

    rows = _hw5_rows(mode)
    stamp = _utcnow()
    new_id = f"{cid}:{stamp}"
    superseded = 0
    for row in rows:
        if str(row.get("conversation_id")) == cid and not row.get("superseded_by"):
            row["superseded_by"] = new_id
            superseded += 1

    if label is not None:
        rows.append({
            "row_id": new_id,
            "trace_id": str(payload.get("trace_id") or ""),
            "conversation_id": cid,
            "mode": mode,
            "label": int(label),
            "source": "human",
            "turn_trace_ids": payload.get("turn_trace_ids") or [],
            "comment": str(payload.get("comment") or ""),
            "ts": stamp,
        })

    HW5_LABELS_DIR.mkdir(parents=True, exist_ok=True)
    path = _hw5_label_path(mode)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8"
    )
    tmp.replace(path)

    live = _hw5_live(mode)
    n_pass = sum(1 for r in live.values() if r["label"] == 1)
    return {
        "ok": True,
        "conversation_id": cid,
        "label": label,
        "superseded": superseded,
        "labelled": len(live),
        "pass": n_pass,
        "fail": len(live) - n_pass,
    }


def _record_label(payload: dict[str, Any]) -> dict[str, Any]:
    """Write one conversation-level judgment as one row per turn trace id.

    A judgment carries ``label`` 0 or 1. ``label: null`` clears the judgment,
    which is how a reviewer undoes a misclick; the local rows are removed and
    no Langfuse score is written, because Langfuse scores are append-only and a
    cleared judgment simply stops being mirrored.
    """
    mode = str(payload.get("mode") or "").strip()
    cid = str(payload.get("conversation_id") or "").strip()
    if not mode or not cid:
        raise ValueError("a label needs both a mode and a conversation_id")

    label = payload.get("label")
    if label not in (0, 1, None):
        raise ValueError("label must be 0, 1 or null")

    trace_ids = payload.get("turn_trace_ids") or []
    if not isinstance(trace_ids, list) or not trace_ids:
        raise ValueError("a label needs the conversation's turn_trace_ids")

    rows = [r for r in _read_label_rows(mode) if r.get("conversation_id") != cid]
    if label is None:
        _write_label_rows(mode, rows)
        return {"ok": True, "rows": 0, "cleared": True, "langfuse_scores_written": 0}

    comment = payload.get("comment") or None
    ts = _utcnow()
    new_rows = [
        {
            "conversation_id": cid,
            "trace_id": str(tid),
            "turn": n,
            "mode": mode,
            "label": int(label),
            "source": payload.get("source") or "human",
            "comment": comment,
            "ts": ts,
        }
        for n, tid in enumerate(trace_ids, start=1)
    ]
    _write_label_rows(mode, rows + new_rows)

    written = _sync_label_scores(new_rows)
    return {"ok": True, "rows": len(new_rows), "langfuse_scores_written": written}


def _sync_label_scores(rows: list[dict[str, Any]]) -> int:
    """Write each row to Langfuse as a numeric score named after the mode.

    Langfuse is the canonical store (handout, "Prepare Langfuse and the
    analysis state files"); the JSONL files are the committed mirror. Returns
    the number of scores written, or zero when Langfuse is off. A Langfuse
    error propagates so the caller can report that the canonical write failed
    while the local mirror already succeeded.
    """
    if not LANGFUSE_ENABLED:
        return 0
    try:
        from analysis.helpers import langfuse_io
    except Exception:
        return 0
    if not langfuse_io.is_configured():
        return 0

    client = langfuse_io._client()
    written = 0
    for row in rows:
        langfuse_io.write_label_score(
            trace_id=str(row["trace_id"]),
            mode=str(row["mode"]),
            label=int(row["label"]),
            comment=row.get("comment"),
            client=client,
        )
        written += 1
    return written


# ---------------------------------------------------------------------------
# annotations
# ---------------------------------------------------------------------------


def _annotation_list(data: Any) -> list[dict[str, Any]]:
    """Normalize the annotations payload (a bare list or ``{"annotations": []}``)."""
    if isinstance(data, dict):
        data = data.get("annotations", [])
    return [a for a in data if isinstance(a, dict)] if isinstance(data, list) else []


# ---------------------------------------------------------------------------
# handler
# ---------------------------------------------------------------------------


class ReviewHandler(BaseHTTPRequestHandler):
    """Serves the UI and the file-backed JSON API."""

    def log_message(self, fmt: str, *args: Any) -> None:  # noqa: A002
        return

    def _send_json(self, data: Any, status: int = 200) -> None:
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, path: Path, content_type: str) -> None:
        if not path.exists():
            self._send_json({"error": "not found: " + path.name}, status=404)
            return
        body = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_body(self) -> Any:
        length = int(self.headers.get("Content-Length", 0))
        if length == 0:
            return None
        raw = self.rfile.read(length)
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return None

    def do_OPTIONS(self) -> None:  # noqa: N802
        self._send_json({}, status=204)

    def do_GET(self) -> None:  # noqa: N802
        path = self.path.split("?", 1)[0]

        if path in ("/", "/index.html"):
            self._send_file(UI_DIR / "index.html", "text/html; charset=utf-8")
            return

        if path.startswith("/ui/"):
            asset = UI_DIR / path[len("/ui/"):]
            if asset.is_file() and UI_DIR in asset.resolve().parents:
                self._send_file(asset, _guess_type(asset))
                return

        if path == "/api/labels":
            self._send_json(_all_labels())
            return

        if path == "/api/hw5/config":
            self._send_json({
                "enabled": HW5_ENABLED,
                "mode": HW5_MODE,
                "convention": "1 = Pass (failure absent), 0 = Fail (failure present)",
            })
            return

        if path == "/api/hw5/labels":
            self._send_json({
                cid: {"label": row["label"], "comment": row.get("comment", "")}
                for cid, row in _hw5_live(HW5_MODE).items()
            })
            return

        if path == "/api/hw5/judge":
            # Part C: judge verdict + critique beside the human label. Written
            # by analysis/run_judges.py after a development batch; absent until
            # the first one runs.
            self._send_json(_read_json(HW5_JUDGMENTS, {}))
            return

        if path == "/api/samples" and HW5_ENABLED:
            self._send_json(_read_json(HW5_SAMPLES, []))
            return

        if path in API_FILES:
            self._send_json(_read_json(API_FILES[path], API_DEFAULTS[path]))
            return

        self._send_json({"error": "unknown path: " + path}, status=404)

    def do_POST(self) -> None:  # noqa: N802
        path = self.path.split("?", 1)[0]
        data = self._read_body()
        if data is None:
            self._send_json({"error": "expected a JSON body"}, status=400)
            return

        if path == "/api/hw5/labels":
            try:
                result = _hw5_record(data if isinstance(data, dict) else {})
            except ValueError as exc:
                self._send_json({"error": str(exc)}, status=400)
            else:
                self._send_json(result)
            return

        if path == "/api/labels":
            try:
                result = _record_label(data if isinstance(data, dict) else {})
            except ValueError as exc:
                self._send_json({"error": str(exc)}, status=400)
            except Exception as exc:  # pragma: no cover - network-only path
                # The local mirror is already written; say so plainly rather
                # than letting the reviewer believe the canonical write landed.
                self._send_json(
                    {
                        "error": "Langfuse score write failed: " + str(exc),
                        "cached_locally": True,
                    },
                    status=502,
                )
            else:
                self._send_json(result)
            return

        if path not in API_FILES:
            self._send_json({"error": "cannot POST to " + path}, status=404)
            return

        _write_json(API_FILES[path], data)
        self._send_json({"ok": True, "count": _count(data)})


def _count(data: Any) -> int:
    if isinstance(data, (list, dict)):
        return len(data)
    return 0


def _guess_type(path: Path) -> str:
    return {
        ".html": "text/html; charset=utf-8",
        ".css": "text/css",
        ".js": "text/javascript",
        ".json": "application/json",
        ".svg": "image/svg+xml",
    }.get(path.suffix, "application/octet-stream")


def main() -> None:
    global LANGFUSE_ENABLED, HW5_ENABLED, HW5_MODE

    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--port", type=int, default=8020)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument(
        "--no-langfuse",
        action="store_true",
        help="keep labels local only (use when the Langfuse stack is down)",
    )
    ap.add_argument(
        "--hw5",
        action="store_true",
        help="HW5 judge calibration: serve hw5_samples.json and label one mode "
             "into hw5_labels/ with 1 = Pass. HW4's Part E files are untouched.",
    )
    ap.add_argument("--mode", default=HW5_MODE, help="the HW5 failure mode to label")
    args = ap.parse_args()
    LANGFUSE_ENABLED = not args.no_langfuse
    HW5_ENABLED = args.hw5
    HW5_MODE = args.mode

    STATE_DIR.mkdir(parents=True, exist_ok=True)
    LABELS_DIR.mkdir(parents=True, exist_ok=True)
    if HW5_ENABLED:
        HW5_LABELS_DIR.mkdir(parents=True, exist_ok=True)

    sample_count = len(_read_json(
        HW5_SAMPLES if HW5_ENABLED else API_FILES["/api/samples"], []
    ))
    server = ThreadingHTTPServer((args.host, args.port), ReviewHandler)
    print("review interface on http://%s:%d/" % (args.host, args.port))
    print("state: %s" % STATE_DIR)
    print("samples loaded: %d conversations" % sample_count)
    print("langfuse scores: %s" % ("on" if LANGFUSE_ENABLED else "off (--no-langfuse)"))
    if HW5_ENABLED:
        live = _hw5_live(HW5_MODE)
        n_pass = sum(1 for r in live.values() if r["label"] == 1)
        print("HW5 mode: %s (1 = Pass, 0 = Fail) -> %s"
              % (HW5_MODE, _hw5_label_path(HW5_MODE)))
        print("HW5 labels so far: %d (%d Pass, %d Fail)"
              % (len(live), n_pass, len(live) - n_pass))
        print("read a conversation, then press p for Pass or f for Fail.")
    else:
        print("read a conversation, select the failing text, type a note, press Enter.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nshutting down")
        server.shutdown()


if __name__ == "__main__":
    main()
