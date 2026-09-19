"""Read Cartwheel conversations from the terminal.

Scaffolding for Homework 4 open coding, not the Part A deliverable. The graded
review interface adds annotation, taxonomy, labeling, progress and Langfuse
sync; this module only renders.

Everything is loaded through ``analysis.helpers.selection.load_traces``, which
normalizes records, merges traces sharing a ``scenario_id`` into one
conversation, and sorts observations by start time. The raw export stores
observations in an unreliable order, so reading it directly misleads.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from analysis.helpers.selection import load_traces  # noqa: E402

DEFAULT_SOURCE = "traces/support_traces.json"

# Writes are where RESP-2 failures live, so they are called out while reading.
WRITE_TOOLS = {"issue_refund", "cancel_order", "escalate_to_human"}

RULE = "\u2500" * 78


def _scalar(value: object, width: int = 60) -> str:
    if isinstance(value, str):
        flat = value.replace("\n", " ")
        return flat[:width] + "\u2026" if len(flat) > width else flat
    return str(value)


def summarize(content: object, full: bool = False) -> str:
    """Condense a tool result to one line, or return it whole with ``full``."""
    if full:
        return json.dumps(content, indent=2, ensure_ascii=False, default=str)
    if not isinstance(content, dict):
        return _scalar(content, 200)

    keys = sorted(content, key=lambda k: (k not in ("ok", "error", "reason"), k))
    parts = []
    for key in keys:
        value = content[key]
        if isinstance(value, (str, int, float, bool)) or value is None:
            parts.append(f"{key}={_scalar(value)}")
        elif isinstance(value, list):
            parts.append(f"{key}=[{len(value)} items]")
        elif isinstance(value, dict):
            inner = ", ".join(
                f"{k}={_scalar(v, 30)}"
                for k, v in list(value.items())[:6]
                if isinstance(v, (str, int, float, bool))
            )
            parts.append(f"{key}{{{inner}}}")
    return "  ".join(parts)


def render(record: dict, full: bool = False) -> None:
    meta = record.get("meta") or {}
    feat = record.get("features") or {}
    print(RULE)
    print(
        f"{meta.get('scenario_id')}   role={meta.get('role')}   "
        f"turns={feat.get('turn_count')}   tools={feat.get('tool_call_count')}   "
        f"distinct={feat.get('distinct_tools')}"
    )
    if record.get("permalink"):
        print(record["permalink"])
    print(RULE)

    first = True
    for message in record.get("trace") or []:
        role = message.get("role")
        if role == "user":
            if not first:
                print()
                print("\u00b7" * 78)
            first = False
            print(f"USER   {message.get('text', '')}")
            print()
        elif role == "tool_call":
            name = message.get("name", "")
            mark = "  \u26a0 write" if name in WRITE_TOOLS else ""
            args = json.dumps(message.get("arguments"), ensure_ascii=False, default=str)
            print(f"  \u2192 {name:<24}{args[:120]}{mark}")
        elif role == "tool_result":
            body = summarize(message.get("content"), full=full)
            if full:
                print("  \u2190 " + body.replace("\n", "\n    "))
            else:
                print(f"  \u2190 {body[:200]}")
            print()
        elif role == "assistant":
            text = (message.get("text") or "").replace("\n", "\n       ")
            print(f"AGENT  {text}")


def matches(record: dict, args: argparse.Namespace) -> bool:
    meta = record.get("meta") or {}
    feat = record.get("features") or {}
    if args.role and meta.get("role") != args.role:
        return False
    if args.min_tools and (feat.get("tool_call_count") or 0) < args.min_tools:
        return False
    if args.multi_turn and (feat.get("turn_count") or 0) <= 2:
        return False
    if args.has:
        names = {m.get("name") for m in record.get("trace") or []}
        if args.has not in names:
            return False
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("scenario", nargs="*", help="scenario ids to print in full")
    parser.add_argument("--source", default=DEFAULT_SOURCE)
    parser.add_argument("--list", action="store_true", help="print a summary table")
    parser.add_argument("--random", type=int, metavar="N", help="pick N at random")
    parser.add_argument("--role", choices=("shopper", "merchant", "support"))
    parser.add_argument("--has", metavar="TOOL", help="only conversations calling TOOL")
    parser.add_argument("--min-tools", type=int, metavar="N")
    parser.add_argument("--multi-turn", action="store_true")
    parser.add_argument("--full", action="store_true", help="expand tool results")
    args = parser.parse_args()

    records = load_traces(args.source)
    by_id = {(r.get("meta") or {}).get("scenario_id"): r for r in records}

    if args.scenario:
        for sid in args.scenario:
            if sid in by_id:
                render(by_id[sid], full=args.full)
            else:
                print(f"no conversation with scenario_id {sid}", file=sys.stderr)
        return

    hits = [r for r in records if matches(r, args)]
    if args.random:
        hits = random.sample(hits, min(args.random, len(hits)))

    if args.list or args.random:
        print(f"{'scenario':16}{'role':10}{'turns':>6}{'tools':>7}{'distinct':>10}  writes")
        print(RULE)
        for record in sorted(hits, key=lambda r: (r.get("meta") or {}).get("scenario_id") or ""):
            meta, feat = record.get("meta") or {}, record.get("features") or {}
            writes = sorted(
                {m.get("name") for m in record.get("trace") or []} & WRITE_TOOLS
            )
            print(
                f"{meta.get('scenario_id',''):16}{meta.get('role',''):10}"
                f"{feat.get('turn_count',0):>6}{feat.get('tool_call_count',0):>7}"
                f"{feat.get('distinct_tools',0):>10}  {','.join(writes)}"
            )
        print(f"\n{len(hits)} conversations")
        return

    parser.print_help()


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
