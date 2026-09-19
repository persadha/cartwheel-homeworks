"""Build review batches for Homework 4 open coding.

Why this module exists instead of calling ``analysis.helpers.tools.select_traces``
directly: the shared helper returns conversations produced by
``normalization._merge_multi_turn``, which concatenates the messages of every
turn but keeps only the *first* turn's ``trace_id``. Cartwheel opens one
Langfuse trace per user turn, so 51 of the 250 conversations lose one or two
trace identifiers that way. Part E has to write a score against every trace,
and the reading view has to show where one turn ends and the next begins, so
both need the per-turn identifiers and timestamps the merge discards.

This module therefore normalizes each trace on its own, groups the turns by
``cartwheel.scenario_id`` (the durable grouping key; ``cartwheel.session_id``
is absent from the Module 1 traces, see hw4-progress.md), and keeps every
turn's identifier, timestamp and permalink alongside the flat message list the
review app annotates.

Selection itself is delegated to ``analysis.helpers.selection.select`` so the
diversity strategy stays the instructor's.

Usage:

    python analysis/review_app/build_samples.py --batch b1_uniform --strategy random --k 15
    python analysis/review_app/build_samples.py --batch b1_cluster --strategy diversity --k 15
    python analysis/review_app/build_samples.py --batch b2_role --dimension role --k 30
    python analysis/review_app/build_samples.py --batch b3_depth --ids support-0170 support-0125
    python analysis/review_app/build_samples.py --list-batches

Batches accumulate: each run appends to ``state/samples.json`` and records the
batch in ``state/sample_manifest.json``. A conversation already present in an
earlier batch is never selected again, because the handout forbids counting one
trace toward two batches.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO))

from analysis.helpers import selection as _selection  # noqa: E402
from analysis.helpers.normalization import normalize_trace  # noqa: E402

STATE_DIR = HERE.parent / "state"
SAMPLES = STATE_DIR / "samples.json"
MANIFEST = STATE_DIR / "sample_manifest.json"

DEFAULT_SOURCE = "traces/support_traces.json"
SCENARIO_PREFIX = "support-"

# Writes are the only place a RESP-2 "claimed success before the tool confirmed
# it" failure can exist, so the reading view flags them.
WRITE_TOOLS = {"issue_refund", "cancel_order", "escalate_to_human"}


# ---------------------------------------------------------------------------
# loading and grouping
# ---------------------------------------------------------------------------


def _permalink(trace_id: str) -> str:
    host = os.environ.get("LANGFUSE_HOST", "http://localhost:3000").rstrip("/")
    project = os.environ.get("LANGFUSE_PROJECT", "cartwheel-dev")
    return host + "/project/" + project + "/traces/" + trace_id


def _raw_traces(source: str) -> list[dict[str, Any]]:
    """Return raw trace records from live Langfuse or a committed export."""
    if source == "langfuse":
        from analysis.helpers import langfuse_io

        if not langfuse_io.is_configured():
            raise SystemExit(
                "LANGFUSE_* is not configured; pass --source traces/support_traces.json"
            )
        # fetch_traces already normalizes and drops records with no scenario id.
        return langfuse_io.fetch_traces(limit=2000)
    path = Path(source)
    if not path.is_absolute():
        path = REPO / path
    raw = json.loads(path.read_text(encoding="utf-8"))
    return raw["traces"] if isinstance(raw, dict) else raw


def _normalized(source: str) -> list[dict[str, Any]]:
    records = []
    for raw in _raw_traces(source):
        # fetch_traces returns already-normalized records; an export does not.
        rec = raw if isinstance(raw.get("trace"), list) else normalize_trace(raw)
        records.append(rec)
    return records


def load_conversations(source: str = DEFAULT_SOURCE) -> list[dict[str, Any]]:
    """Group per-turn traces into conversations, preserving every turn id."""
    by_scenario: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for rec in _normalized(source):
        sid = (rec.get("meta") or {}).get("scenario_id")
        if sid and str(sid).startswith(SCENARIO_PREFIX):
            by_scenario[str(sid)].append(rec)

    conversations = []
    for sid, group in sorted(by_scenario.items()):
        group.sort(key=lambda r: r.get("timestamp") or "")
        messages: list[dict[str, Any]] = []
        turns = []
        for n, rec in enumerate(group, start=1):
            msgs = rec.get("trace") or []
            tools = [m for m in msgs if m.get("role") == "tool_call"]
            turns.append(
                {
                    "n": n,
                    "trace_id": rec["trace_id"],
                    "timestamp": rec.get("timestamp"),
                    "permalink": rec.get("permalink") or _permalink(rec["trace_id"]),
                    "start": len(messages),
                    "tool_calls": len(tools),
                    "writes": sorted({m.get("name") for m in tools} & WRITE_TOOLS),
                }
            )
            messages.extend(msgs)

        tool_calls = [m for m in messages if m.get("role") == "tool_call"]
        names = {str(m.get("name")) for m in tool_calls if m.get("name")}
        text = "\n".join(
            str(m.get("text") or m.get("content") or m.get("arguments") or "")
            for m in messages
        )
        meta = group[0].get("meta") or {}
        conversations.append(
            {
                # `id` and `trace_id` keep the shared selection helper working;
                # the first turn anchors the conversation.
                "id": sid,
                "trace_id": group[0]["trace_id"],
                "conversation_id": sid,
                "turn_trace_ids": [t["trace_id"] for t in turns],
                "turns": turns,
                "trace": messages,
                "turn_starts": [t["start"] for t in turns],
                "text": text,
                "meta": {
                    "scenario_id": sid,
                    "role": meta.get("role"),
                    "prompt_version": meta.get("prompt_version"),
                },
                "features": {
                    "turn_count": len(turns),
                    "message_count": len(messages),
                    "tool_call_count": len(tool_calls),
                    "distinct_tools": len(names),
                    "has_retrieval": int(
                        bool(names & {"search_help_center", "get_policy"})
                    ),
                    "write_tool_count": sum(
                        1 for m in tool_calls if m.get("name") in WRITE_TOOLS
                    ),
                    "tokens": len(text.split()),
                },
                "tools": sorted(names),
                "writes": sorted(names & WRITE_TOOLS),
                "flags": [],
            }
        )
    return conversations


def add_outlier_flags(convs: list[dict[str, Any]]) -> None:
    """Flag statistical outliers in the header only (skill phase 2).

    Most conversations should carry zero or one flag, so the badge stays
    informative. Flags are a prompt to read carefully, never a failure label.

    Tool calls, tokens and turns move together, so a long conversation trips
    all three tests and arrives wearing three near-identical badges. The
    features are checked in decreasing order of usefulness and each
    conversation keeps at most ``MAX_FLAGS``.
    """
    MAX_FLAGS = 2
    for field, label in (
        ("tool_call_count", "tool calls"),
        ("tokens", "tokens"),
        ("turn_count", "turns"),
    ):
        vals = sorted(c["features"][field] for c in convs)
        if not vals:
            continue
        hi = vals[int(len(vals) * 0.9)]
        lo = vals[int(len(vals) * 0.1)]
        for c in convs:
            if len(c["flags"]) >= MAX_FLAGS:
                continue
            v = c["features"][field]
            if v > hi:
                c["flags"].append(str(v) + " " + label + " (top 10%)")
            elif v < lo and field != "turn_count":
                c["flags"].append(str(v) + " " + label + " (bottom 10%)")


# ---------------------------------------------------------------------------
# state
# ---------------------------------------------------------------------------


def _read(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return default


def _write(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)


# ---------------------------------------------------------------------------
# selection strategies
# ---------------------------------------------------------------------------


def pick_dimension(
    pool: list[dict[str, Any]], dimension: str, k: int, seed: int
) -> list[dict[str, str]]:
    """Spread ``k`` picks evenly across the values of one product dimension.

    The handout requires choosing the dimension before looking at outcomes, so
    this function never reads an annotation or a label.
    """
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for c in pool:
        groups[str((c.get("meta") or {}).get(dimension))].append(c)
    rng = random.Random(seed)
    for members in groups.values():
        rng.shuffle(members)
    keys = sorted(groups)
    picks: list[dict[str, str]] = []
    i = 0
    while len(picks) < k and any(groups[key] for key in keys):
        key = keys[i % len(keys)]
        if groups[key]:
            c = groups[key].pop()
            picks.append({"trace_id": c["id"], "reason": dimension + "=" + key})
        i += 1
    return picks


def build_batch(
    convs: list[dict[str, Any]],
    batch: str,
    strategy: str,
    k: int,
    dimension: str | None,
    ids: list[str] | None,
    reason: str | None,
    seed: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    existing = _read(SAMPLES, [])
    already = {s.get("conversation_id") or s.get("id") for s in existing}
    pool = [c for c in convs if c["id"] not in already]
    by_id = {c["id"]: c for c in convs}

    if ids:
        missing = [i for i in ids if i not in by_id]
        if missing:
            raise SystemExit("unknown scenario ids: " + ", ".join(missing))
        dup = [i for i in ids if i in already]
        if dup:
            raise SystemExit(
                "already reviewed in an earlier batch, a trace may not count "
                "twice: " + ", ".join(dup)
            )
        picks = [
            {"trace_id": i, "reason": reason or "depth search candidate"} for i in ids
        ]
    elif dimension:
        picks = pick_dimension(pool, dimension, k, seed)
    else:
        picks = _selection.select(pool, k=k, strategy=strategy, exclude_ids=already)

    chosen = []
    for p in picks:
        c = dict(by_id[p["trace_id"]])
        c["reason"] = p["reason"]
        c["batch"] = batch
        chosen.append(c)

    if ids:
        strategy_label = "ids"
    elif dimension:
        strategy_label = "dimension:" + dimension
    else:
        strategy_label = strategy

    manifest_entry = {
        "batch": batch,
        "strategy": strategy_label,
        "k": len(chosen),
        "requested_k": k,
        "seed": seed,
        "picks": [{"conversation_id": c["id"], "reason": c["reason"]} for c in chosen],
    }
    return chosen, manifest_entry


# ---------------------------------------------------------------------------
# cli
# ---------------------------------------------------------------------------


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument(
        "--source",
        default=DEFAULT_SOURCE,
        help='export path, or "langfuse" for a live pull',
    )
    ap.add_argument("--batch", help="batch name recorded in the manifest")
    ap.add_argument(
        "--strategy", default="random", choices=("random", "diversity", "outlier")
    )
    ap.add_argument("--k", type=int, default=15)
    ap.add_argument("--dimension", help="spread picks across a meta field, e.g. role")
    ap.add_argument("--ids", nargs="*", help="explicit scenario ids (depth search)")
    ap.add_argument("--reason", help="reason recorded for explicit ids")
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--list-batches", action="store_true")
    ap.add_argument("--stats", action="store_true", help="describe the store and exit")
    ap.add_argument("--dry-run", action="store_true", help="print picks, write nothing")
    args = ap.parse_args()

    if args.list_batches:
        manifest = _read(MANIFEST, {"batches": []})
        samples = _read(SAMPLES, [])
        counts = Counter(s.get("batch") for s in samples)
        for entry in manifest.get("batches", []):
            print(
                "%-16s %-22s %3d conversations"
                % (entry["batch"], entry["strategy"], counts.get(entry["batch"], 0))
            )
        traces = sum(len(s.get("turn_trace_ids") or []) for s in samples)
        print("\ntotal: %d conversations, %d raw traces" % (len(samples), traces))
        return

    convs = load_conversations(args.source)
    add_outlier_flags(convs)

    if args.stats:
        print("%d conversations from %s" % (len(convs), args.source))
        print("%d raw traces" % sum(len(c["turns"]) for c in convs))
        print("roles:", Counter(c["meta"]["role"] for c in convs).most_common())
        print(
            "turns:",
            Counter(c["features"]["turn_count"] for c in convs).most_common(),
        )
        print("with write tools:", sum(1 for c in convs if c["writes"]))
        print("flagged:", sum(1 for c in convs if c["flags"]))
        return

    if not args.batch:
        raise SystemExit("--batch is required (or use --stats / --list-batches)")

    chosen, entry = build_batch(
        convs,
        args.batch,
        args.strategy,
        args.k,
        args.dimension,
        args.ids,
        args.reason,
        args.seed,
    )
    if not chosen:
        raise SystemExit("no conversations selected (pool exhausted?)")

    for c in chosen:
        print(
            "  %-16s %-9s turns=%d tools=%2d  %s"
            % (
                c["id"],
                c["meta"]["role"],
                c["features"]["turn_count"],
                c["features"]["tool_call_count"],
                c["reason"],
            )
        )
    print(
        "\n%d conversations, %d raw traces"
        % (len(chosen), sum(len(c["turn_trace_ids"]) for c in chosen))
    )

    if args.dry_run:
        print("(dry run, nothing written)")
        return

    samples = _read(SAMPLES, []) + chosen
    manifest = _read(MANIFEST, {"source": args.source, "batches": []})
    manifest["source"] = args.source
    manifest.setdefault("batches", []).append(entry)
    manifest["total_conversations"] = len(samples)
    manifest["total_raw_traces"] = sum(
        len(s.get("turn_trace_ids") or []) for s in samples
    )
    _write(SAMPLES, samples)
    _write(MANIFEST, manifest)
    print(
        "wrote %s (%d total) and %s"
        % (SAMPLES.relative_to(REPO), len(samples), MANIFEST.relative_to(REPO))
    )


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
