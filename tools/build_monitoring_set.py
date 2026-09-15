"""Select the 50 monitoring scenarios (HW3 part C3) from the final 250.

Scaffolding, not a deliverable. The records are copied verbatim from
scenarios/support_scenarios.jsonl and kept in file order, so the write ordering
that makes the final run safe also holds when Homework 7 replays this subset.

The selection is deterministic: seeded by one scenario per documented data
quality case, then filled greedily by whichever candidate adds the most unseen
(role, intent) coverage, ties broken by scenario id.

    uv run python tools/build_monitoring_set.py           # report only
    uv run python tools/build_monitoring_set.py --write   # write the file
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCE = REPO_ROOT / "scenarios" / "support_scenarios.jsonl"
TARGET = REPO_ROOT / "scenarios" / "monitoring_scenarios.jsonl"

TOTAL = 50
CHALLENGE_QUOTA = 15
COVERAGE_QUOTA = 35
# Mirrors the coverage plan's 100 / 45 / 30 split, scaled to 35.
COVERAGE_ROLE_QUOTA = {"shopper": 20, "merchant": 9, "support": 6}


def load(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def greedy_fill(
    chosen: list[dict],
    candidates: list[dict],
    quota: int,
    role_quota: dict[str, int] | None = None,
) -> None:
    """Add records one at a time, each time taking the one that adds the most
    unseen (role, intent) pairs, then the most unseen intent, then the lowest id."""
    seen_pairs = {(r["tuple"]["role"], r["tuple"]["intent"]) for r in chosen}
    seen_intents = {r["tuple"]["intent"] for r in chosen}
    role_used: Counter[str] = Counter(r["tuple"]["role"] for r in chosen)
    picked_ids = {r["id"] for r in chosen}

    while len([r for r in chosen if r["id"] in picked_ids]) < quota:
        best = None
        for record in candidates:
            if record["id"] in picked_ids:
                continue
            role = record["tuple"]["role"]
            intent = record["tuple"]["intent"]
            if role_quota is not None and role_used[role] >= role_quota[role]:
                continue
            score = (
                (role, intent) not in seen_pairs,
                intent not in seen_intents,
            )
            key = (-int(score[0]), -int(score[1]), record["id"])
            if best is None or key < best[0]:
                best = (key, record)
        if best is None:
            raise SystemExit("ran out of candidates before filling the quota")
        record = best[1]
        chosen.append(record)
        picked_ids.add(record["id"])
        seen_pairs.add((record["tuple"]["role"], record["tuple"]["intent"]))
        seen_intents.add(record["tuple"]["intent"])
        role_used[record["tuple"]["role"]] += 1


def select(records: list[dict]) -> list[dict]:
    order = {r["id"]: i for i, r in enumerate(records)}
    challenge = [r for r in records if r["scenario_group"] == "challenge"]
    coverage = [r for r in records if r["scenario_group"] == "coverage"]

    # Seed: the first scenario of each documented data quality case, so Homework
    # 7 can compare the damaged-record behaviour too.
    seeds: list[dict] = []
    seen_cases: set[str] = set()
    for record in challenge:
        case = record["data_quality_case_id"]
        if case and case not in seen_cases:
            seen_cases.add(case)
            seeds.append(record)

    # One damaged-record scenario per case and no more: the other nine challenge
    # slots belong to the remaining difficult dimensions (store overrides, denied
    # authorization, the $100 threshold, missing information, cross-turn work).
    chosen_challenge = list(seeds)
    greedy_fill(
        chosen_challenge,
        [r for r in challenge if not r["data_quality_case_id"]],
        CHALLENGE_QUOTA,
    )

    chosen_coverage: list[dict] = []
    greedy_fill(chosen_coverage, coverage, COVERAGE_QUOTA, COVERAGE_ROLE_QUOTA)

    chosen = chosen_challenge + chosen_coverage
    chosen.sort(key=lambda r: order[r["id"]])
    return chosen


def report(chosen: list[dict], records: list[dict]) -> None:
    all_intents = {r["tuple"]["intent"] for r in records}
    print(f"records: {len(chosen)}")
    print("group:  ", dict(Counter(r["scenario_group"] for r in chosen)))
    print("role:   ", dict(Counter(r["tuple"]["role"] for r in chosen)))
    print("turns:  ", dict(sorted(Counter(r["tuple"]["turn_count"] for r in chosen).items())))
    print("eval:   ", dict(Counter(r["expected"]["evaluation"] for r in chosen)))
    print("dq cases:", dict(Counter(r["data_quality_case_id"] for r in chosen if r["data_quality_case_id"])))
    print("intents:")
    counts = Counter(r["tuple"]["intent"] for r in chosen)
    for intent in sorted(all_intents):
        print(f"  {intent:<20} {counts.get(intent, 0)}")
    missing = all_intents - set(counts)
    print("missing intents:", sorted(missing) if missing else "none")

    # Replaying this subset must not reuse an order after a write changed it.
    mutating = {"refund_request", "cancel_order"}
    used: dict[int, list[tuple[str, str]]] = {}
    for record in chosen:
        oid = record["tuple"].get("order_id")
        if oid:
            used.setdefault(oid, []).append((record["id"], record["tuple"]["intent"]))
    clashes = {
        oid: uses
        for oid, uses in used.items()
        if len(uses) > 1 and any(intent in mutating for _, intent in uses[:-1])
    }
    print("orders reused after a write:", clashes or "none")


def main() -> None:
    records = load(SOURCE)
    chosen = select(records)
    report(chosen, records)
    if "--write" in sys.argv:
        TARGET.write_text(
            "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in chosen),
            encoding="utf-8",
        )
        print(f"\nwrote {len(chosen)} records to {TARGET.relative_to(REPO_ROOT)}")
    else:
        print("\n(report only; pass --write to create the file)")


if __name__ == "__main__":
    main()
