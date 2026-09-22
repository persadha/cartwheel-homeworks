"""HW5: build and evaluate an LLM judge for one HW4 failure mode.

Run from the repository root:

    uv run python analysis/run_judges.py seed-labels
    uv run python analysis/run_judges.py prepare-inputs
    uv run python analysis/run_judges.py split
    uv run python analysis/run_judges.py develop --prompt analysis/prompts/<mode>-v0.txt
    uv run python analysis/run_judges.py test --judge-id <judge_id>

Label convention. HW4 stored ``1 = failure present`` in
``analysis/state/labels/<mode>.jsonl``. HW5 stores ``1 = Pass`` (failure absent)
in ``analysis/state/hw5_labels/<mode>.jsonl``, so that Pass is the positive class
in TPR/TNR. ``analysis.helpers.tools._load_labels`` prefers the HW5 file once it
exists and flips it back to the internal failure flag, so every downstream helper
keeps working unchanged. The HW4 files are never modified.

Granularity. Cartwheel emits one Langfuse trace per user turn, so a multi-turn
conversation has several trace ids. HW5 evaluates one record per conversation
(hw5.md, "Use one evaluation record per conversation"), so each conversation is
keyed by a single canonical trace id -- the one ``analysis/state/samples.json``
already uses -- and its judge input holds every turn.
"""

from __future__ import annotations

import argparse
import json
import random
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

MODE = "unrequested_information"
ROOT = Path(__file__).resolve().parent.parent
STATE = ROOT / "analysis" / "state"
HW4_LABELS = STATE / "labels"
HW5_LABELS = STATE / "hw5_labels"
SAMPLES = STATE / "samples.json"
TRACE_INPUTS = STATE / "hw5_trace_inputs.json"
HW5_SAMPLES = STATE / "hw5_samples.json"
REPORT = ROOT / "analysis" / "report"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _hw5_live_rows(mode: str = MODE) -> list[dict]:
    """The live HW5 label per conversation, superseded rows dropped."""
    path = HW5_LABELS / f"{mode}.jsonl"
    if not path.exists():
        return []
    live: dict[str, dict] = {}
    for row in _read_jsonl(path):
        if row.get("superseded_by"):
            continue
        live[str(row["conversation_id"])] = row
    return list(live.values())


def _load_samples() -> dict[str, dict]:
    """Conversation id -> the HW4 sample record (canonical trace id, messages)."""
    return {rec["conversation_id"]: rec for rec in json.loads(SAMPLES.read_text(encoding="utf-8"))}


def seed_labels(mode: str = MODE) -> dict:
    """Convert the HW4 turn-level labels into HW5 conversation-level labels.

    Rolls the HW4 rows up per conversation, keys each conversation by its
    canonical trace id, and flips ``1 = failure`` to ``1 = Pass``. Refuses to
    overwrite an existing HW5 file, because that file accumulates the student's
    own labels once mining starts.
    """
    out_path = HW5_LABELS / f"{mode}.jsonl"
    if out_path.exists():
        raise SystemExit(
            f"{out_path} already exists. Seeding would discard labels made since. "
            "Delete it deliberately if you really mean to start over."
        )

    samples = _load_samples()
    rows = _read_jsonl(HW4_LABELS / f"{mode}.jsonl")

    # HW4 fanned one conversation-level judgment out to every turn. Collect the
    # turn labels per conversation so a disagreement between them is reported
    # rather than silently resolved.
    per_conversation: dict[str, list[dict]] = {}
    for row in rows:
        if row.get("superseded_by"):
            continue
        per_conversation.setdefault(row["conversation_id"], []).append(row)

    conflicts = [
        cid for cid, group in per_conversation.items()
        if len({r["label"] for r in group}) > 1
    ]
    if conflicts:
        raise SystemExit(f"turn labels disagree within these conversations: {conflicts}")

    missing = sorted(set(per_conversation) - set(samples))
    if missing:
        raise SystemExit(f"no sample record for: {missing}")

    HW5_LABELS.mkdir(parents=True, exist_ok=True)
    out: list[dict] = []
    for cid in sorted(per_conversation):
        group = per_conversation[cid]
        hw4_label = group[0]["label"]          # 1 = failure present
        comments = [r.get("comment") for r in group if r.get("comment")]
        out.append({
            "trace_id": samples[cid]["trace_id"],   # canonical: one per conversation
            "conversation_id": cid,
            "mode": mode,
            "label": 1 - int(hw4_label),            # HW5: 1 = Pass, 0 = Fail
            "source": group[0].get("source", "hw4_import"),
            "hw4_source": group[0].get("source"),
            "turn_trace_ids": samples[cid]["turn_trace_ids"],
            "comment": comments[0] if comments else "",
            "ts": _now(),
        })

    out_path.write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in out), encoding="utf-8"
    )

    n_pass = sum(r["label"] for r in out)
    return {
        "path": str(out_path.relative_to(ROOT)),
        "conversations": len(out),
        "pass": n_pass,
        "fail": len(out) - n_pass,
        "hw4_rows_in": len(rows),
    }


# ---------------------------------------------------------------------------
# Part A: grow the label pool
# ---------------------------------------------------------------------------

# HW4 reviewed 105 of the 250 conversations and confirmed 11 instances of this
# mode. HW5 needs at least 30 Fail labels, and split_labels(min_per_class=10)
# refuses below 25 per class, so the pool has to grow from the 145 conversations
# HW4 never read.
#
# Reading all 145 is the honest baseline but expensive, and ranking them by
# helpers.next_to_label's bag-of-words similarity did not separate them: it
# returned all 145 with one undifferentiated signal. These regexes rank instead,
# using the mode's own decision rule. They are a READING ORDER, not a label --
# every candidate they surface is still read and judged by the reviewer.
#
# The one subtlety that matters: RESP-6 permits a clearly labelled offer of a
# next step, so a closing "Want me to check its return eligibility?" is a Pass.
# Scoring therefore drops every sentence ending in a question mark before it
# looks for volunteered facts. Without that the screen fires on nearly every
# conversation, exactly as the mode itself would without RESP-6's third sentence.

ELIGIBILITY = re.compile(
    r"refund[- ]?eligib|return window|eligible for (a )?(refund|return)|"
    r"not (currently )?(refund[- ]?)?eligible|refund eligibility|still within", re.I)
ASKED_ABOUT = re.compile(r"refund|return|eligib|money back|cancel|send .* back", re.I)
ORDER_REF = re.compile(r"#\s*(\d{3,5})|order\s*#?\s*(\d{3,5})", re.I)
SALES_TALK = re.compile(r"\b(sales|revenue|payout|recent orders|order history|top[- ]sell)", re.I)
PRICE = re.compile(r"\$\s?\d")
DATED_EVENT = re.compile(r"\b(placed|delivered|shipped|ordered)\s+(on\s+)?[A-Z][a-z]{2,8}\s+\d{1,2}", re.I)


def _order_ids(text: str) -> set[str]:
    return {a or b for a, b in ORDER_REF.findall(text)}


def screen_conversation(messages: list[dict]) -> list[str]:
    """Name the RESP-6 signals a conversation carries. Ordering only."""
    user = " ".join(m.get("text", "") for m in messages if m["role"] == "user")
    reply = " ".join(m.get("text", "") for m in messages if m["role"] == "assistant")
    # Offers are permitted, so score declarative sentences only.
    declarative = " ".join(
        s for s in re.split(r"(?<=[.!?])\s+", reply) if not s.strip().endswith("?")
    )

    signals: list[str] = []
    if ELIGIBILITY.search(declarative) and not ASKED_ABOUT.search(user):
        signals.append("states-eligibility-unasked")
    extra = _order_ids(declarative) - _order_ids(user)
    if len(extra) >= 2:
        signals.append(f"extra-orders:{len(extra)}")
    elif len(extra) == 1 and _order_ids(user):
        signals.append("extra-order:1")
    if SALES_TALK.search(declarative) and not SALES_TALK.search(user):
        signals.append("sales-history")
    if len(DATED_EVENT.findall(declarative)) >= 2:
        signals.append("volunteered-dates")
    if len(PRICE.findall(declarative)) >= 3 and not PRICE.findall(user):
        signals.append("many-prices")
    return signals


def mine_candidates(mode: str = MODE, random_slice: int = 25, seed: int = 11) -> dict:
    """Build the HW5 reading queue and write ``state/hw5_samples.json``.

    Three batches, in reading order:

      ``hw5_screen``    every unreviewed conversation carrying at least one
                        signal, most signals first.
      ``hw5_random``    ``random_slice`` conversations drawn uniformly from the
                        unreviewed remainder that carried none. This is the
                        check that the screen is not defining the Fail class:
                        a Fail found here is one the regexes missed. HW4 used
                        the same device for its ``b4_stability`` batch.
      ``hw4_carryover`` the 105 conversations already labelled, so the
                        development and test splits can be read in the same app.

    Writes a file the review app reads. It is deliberately NOT the judge input:
    ``hw5_trace_inputs.json`` is built separately and carries no signals,
    batch names or comments, because any of those would leak the answer.
    """
    sys.path.insert(0, str(ROOT / "analysis" / "review_app"))
    from build_samples import load_conversations  # noqa: PLC0415

    labeled = {r["conversation_id"] for r in _hw5_live_rows(mode)}
    conversations = {c["conversation_id"]: c for c in load_conversations()}

    screened, clean = [], []
    for cid, conv in conversations.items():
        if cid in labeled:
            continue
        signals = screen_conversation(conv["trace"])
        (screened if signals else clean).append((cid, signals))
    screened.sort(key=lambda x: (-len(x[1]), x[0]))

    sampled = sorted(random.Random(seed).sample(
        [cid for cid, _ in clean], min(random_slice, len(clean))))

    out = []
    for cid, signals in screened:
        out.append({**conversations[cid], "hw5_batch": "hw5_screen", "hw5_signals": signals})
    for cid in sampled:
        out.append({**conversations[cid], "hw5_batch": "hw5_random", "hw5_signals": []})
    for cid in sorted(labeled):
        out.append({**conversations[cid], "hw5_batch": "hw4_carryover", "hw5_signals": []})

    HW5_SAMPLES.write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    return {
        "path": str(HW5_SAMPLES.relative_to(ROOT)),
        "unreviewed": len(screened) + len(clean),
        "hw5_screen": len(screened),
        "hw5_random": len(sampled),
        "hw4_carryover": len(labeled),
        "total": len(out),
    }


def drop_bulk_accepted(mode: str = MODE) -> dict:
    """Restrict the HW5 ground truth to labels a human read individually.

    HW4's Part E produced three kinds of label. ``human`` rows were decided by
    reading the conversation. ``code_gate`` rows were Passes a deterministic
    check made certain. ``reviewer_accepted`` rows were proposed by the agent
    and accepted **as a block rather than read individually** -- HW4's own
    report flags the distinction and says "HW5 draws its ground truth from
    these files, so how firmly each label was established is itself evidence".

    The evidence arrived. Measured against this mode, every batch a human read
    runs 52-67% Fail: 11/19 on HW4's own ``human`` rows, 20/30 on the screened
    candidates, 13/25 on a blind random slice. The ``reviewer_accepted`` rows
    are 0/86. A rate that far outside three independent readings is a property
    of the labelling, not of the traces, and 48% of those 86 carry a screen
    signal -- they look like the conversations just labelled Fail.

    Keeping them would put a large, one-directional error into the Pass class:
    the judge would call them Fail, be scored wrong for it, and the resulting
    TPR would measure the labelling rather than the judge.

    They are moved to ``_excluded_bulk_accepted.jsonl`` rather than deleted, and
    HW4's own files are not touched, so HW4's Part E stands as submitted.
    """
    path = HW5_LABELS / f"{mode}.jsonl"
    rows = _read_jsonl(path)
    # App-written rows carry no `hw4_source`; they were read one at a time.
    keep = [r for r in rows if r.get("hw4_source") != "reviewer_accepted"]
    dropped = [r for r in rows if r.get("hw4_source") == "reviewer_accepted"]
    if not dropped:
        return {"dropped": 0, "note": "nothing to exclude"}

    archive = HW5_LABELS / "_excluded_bulk_accepted.jsonl"
    with archive.open("a", encoding="utf-8") as fh:
        for row in dropped:
            fh.write(json.dumps({**row, "excluded_reason": "hw4 reviewer_accepted: "
                                 "accepted in bulk, never read individually",
                                 "excluded_at": _now()}, ensure_ascii=False) + "\n")
    path.write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in keep), encoding="utf-8"
    )

    live = _hw5_live_rows(mode)
    n_pass = sum(1 for r in live if r["label"] == 1)
    return {
        "dropped": len(dropped),
        "archived_to": str(archive.relative_to(ROOT)),
        "remaining": len(live),
        "pass": n_pass,
        "fail": len(live) - n_pass,
    }


# ---------------------------------------------------------------------------
# Part B: judge inputs and the split
# ---------------------------------------------------------------------------

# Anything in a judge input record that encodes a human decision leaks the
# answer, so records are built from a whitelist rather than by deleting fields
# from the sample: a field added to hw5_samples.json later cannot silently
# reach the judge. The check below is structural, not a substring scan --
# `reason` is a legitimate parameter of issue_refund and cancel_order
# (SPEC.md TOOL-7, TOOL-8) and the judge needs to see it.
RECORD_KEYS = {"trace_id", "trace"}
MESSAGE_KEYS = {"role", "text", "arguments"}
MESSAGE_ROLES = {"user", "assistant", "tool_call", "tool_result"}


def _judge_messages(messages: list[dict]) -> list[dict]:
    """Rewrite one conversation into what the judge will actually read.

    ``helpers.normalization._flatten`` renders the record the judge sees, and
    it prints ``tool_call`` messages from ``arguments`` alone and everything
    else from ``text``/``content`` -- the tool *name* is dropped either way.
    A judge that sees ``tool_call: {"order_id": 5453}`` cannot tell a
    ``get_order`` from a ``check_return_eligibility``, which is exactly the
    distinction this mode turns on. The name is therefore folded into the
    fields that survive flattening.
    """
    out: list[dict] = []
    for m in messages:
        role = m.get("role")
        if role in ("user", "assistant"):
            text = (m.get("text") or "").strip()
            if text:
                out.append({"role": role, "text": text})
        elif role == "tool_call":
            args = m.get("arguments") if isinstance(m.get("arguments"), dict) else {}
            out.append({"role": "tool_call", "arguments": {"tool": m.get("name"), **args}})
        elif role == "tool_result":
            out.append({"role": "tool_result",
                        "text": f"{m.get('name')} -> "
                                f"{json.dumps(m.get('content'), ensure_ascii=False)}"})
    return out


def prepare_inputs(mode: str = MODE) -> dict:
    """Write the judge's input file: one record per labelled conversation.

    One record per conversation, not per turn (hw5.md: "Use one evaluation
    record per conversation"), carrying every turn so a fact requested in turn
    one is not read as unrequested in turn three. Each record is
    ``{"trace_id", "trace"}`` and nothing else.

    Written once and then left alone, so every prompt version is scored against
    identical inputs.
    """
    live = _hw5_live_rows(mode)
    samples = {c["conversation_id"]: c
               for c in json.loads(HW5_SAMPLES.read_text(encoding="utf-8"))}

    records = []
    for row in live:
        conv = samples.get(row["conversation_id"])
        if conv is None:
            raise SystemExit(f"no conversation for label {row['conversation_id']}")
        messages = _judge_messages(conv["trace"])
        if not messages:
            raise SystemExit(f"{row['conversation_id']} has no renderable messages")
        records.append({"trace_id": row["trace_id"], "trace": messages})

    # Guards. Each is a way this file has a real chance of being wrong.
    ids = [r["trace_id"] for r in records]
    if len(set(ids)) != len(ids):
        raise SystemExit("duplicate trace ids in the judge inputs")
    if len(records) != len(live):
        raise SystemExit(f"{len(records)} records for {len(live)} labels")
    for record in records:
        if set(record) != RECORD_KEYS:
            raise SystemExit(f"unexpected record keys: {sorted(set(record) - RECORD_KEYS)}")
        for message in record["trace"]:
            if not set(message) <= MESSAGE_KEYS:
                raise SystemExit(
                    f"unexpected message keys: {sorted(set(message) - MESSAGE_KEYS)}")
            if message["role"] not in MESSAGE_ROLES:
                raise SystemExit(f"unexpected role: {message['role']}")

    # The decisive test: no review note the reviewer actually wrote may appear
    # in what the judge reads. Structural checks cannot catch a note that was
    # pasted into a message; this can.
    blob = json.dumps(records, ensure_ascii=False)
    for row in live:
        note = (row.get("comment") or "").strip()
        if len(note) >= 25 and note in blob:
            raise SystemExit(f"review note for {row['conversation_id']} leaked into the inputs")

    TRACE_INPUTS.write_text(json.dumps(records, indent=1, ensure_ascii=False),
                            encoding="utf-8")
    return {
        "path": str(TRACE_INPUTS.relative_to(ROOT)),
        "records": len(records),
        "labels": len(live),
        "messages_total": sum(len(r["trace"]) for r in records),
        "chars_median": sorted(len(json.dumps(r["trace"])) for r in records)[len(records) // 2],
    }


def split_data(mode: str = MODE) -> dict:
    """Split the labels 20/40/40, stratified, once.

    Run once and left unchanged: re-running after seeing development results
    would let the test split be reshaped around them.
    """
    from analysis.helpers import split_labels  # noqa: PLC0415

    records = json.loads(TRACE_INPUTS.read_text(encoding="utf-8"))
    splits = split_labels(
        mode,
        fractions=(0.20, 0.40, 0.40),
        seed=7,
        min_per_class=10,
        eligible_trace_ids=[r["trace_id"] for r in records],
    )
    labels = {r["trace_id"]: r["label"] for r in _hw5_live_rows(mode)}
    return {
        name: {
            "n": len(ids),
            "pass": sum(1 for i in ids if labels[i] == 1),
            "fail": sum(1 for i in ids if labels[i] == 0),
        }
        for name, ids in splits.items()
    }


# ---------------------------------------------------------------------------
# Parts C and D: run the judge, measure alignment
# ---------------------------------------------------------------------------

JUDGE_MODEL = "gpt-4o-mini"


def register(prompt_path: str, mode: str = MODE, judge_model: str = JUDGE_MODEL) -> dict:
    """Register a prompt version. Free -- no model is called.

    Separate from ``run_development`` so the judge id and the exact trace count
    can be shown and approved before anything is paid for.
    """
    from analysis.helpers import register_judge  # noqa: PLC0415

    text = Path(prompt_path).read_text(encoding="utf-8")
    record = register_judge(mode=mode, prompt_text=text, judge_model=judge_model)
    splits = json.loads((STATE / "splits.json").read_text(encoding="utf-8"))[mode]
    return {
        "judge_id": record["judge_id"],
        "prompt": prompt_path,
        "prompt_hash": record["prompt_hash"],
        "model": judge_model,
        "dev_traces": len(splits["dev"]),
        "test_traces": len(splits["test"]),
    }


def _judge_view(judge_id: str, mode: str = MODE) -> int:
    """Write verdict + critique per conversation for the review app.

    Part C asks for the judge's verdict and critique beside the human label in
    the review interface. The app keys on conversation id; the judge record
    keys on trace id, so this joins them.
    """
    judge = json.loads((STATE / "judges" / f"{judge_id}.json").read_text(encoding="utf-8"))
    digest = judge["prompt_hash"]
    predictions = judge.get("predictions", {}).get(digest, {})
    critiques = judge.get("critiques", {}).get(digest, {})
    by_trace = {r["trace_id"]: r["conversation_id"] for r in _hw5_live_rows(mode)}

    view = {}
    for trace_id, pred in predictions.items():
        cid = by_trace.get(trace_id)
        if cid is None:
            continue
        view[cid] = {
            "verdict": "Pass" if int(pred) == 1 else "Fail",
            "critique": critiques.get(trace_id, ""),
            "judge_id": judge_id,
        }
    (STATE / "hw5_judge_view.json").write_text(
        json.dumps(view, indent=1, ensure_ascii=False), encoding="utf-8")
    return len(view)


def _metrics(alignment: dict) -> dict:
    """Restate judge_alignment in the handout's terms, recomputed from counts.

    ``judge_alignment`` already returns TPR, TNR and 95% Wilson intervals with
    Pass as the positive class. They are recomputed here from the confusion
    counts so the saved report can be checked by hand -- which is what the
    video asks for.
    """
    tp, fn, tn, fp = (alignment[k] for k in ("tp", "fn", "tn", "fp"))
    tpr = tp / (tp + fn) if (tp + fn) else 0.0
    tnr = tn / (tn + fp) if (tn + fp) else 0.0
    if abs(tpr - alignment["tpr"]) > 1e-4 or abs(tnr - alignment["tnr"]) > 1e-4:
        raise SystemExit("recomputed TPR/TNR disagree with judge_alignment")
    return {
        "confusion": {"tp": tp, "fp": fp, "fn": fn, "tn": tn, "n": alignment["n"]},
        "human_pass": tp + fn,
        "human_fail": tn + fp,
        "tpr": round(tpr, 4),
        "tpr_interval": alignment["tpr_interval"],
        "tnr": round(tnr, 4),
        "tnr_interval": alignment["tnr_interval"],
        "agreement": alignment["agreement"],
        "disagreements": alignment["disagreements"],
    }


def run_development(judge_id: str, mode: str = MODE) -> dict:
    """Score the development split and save the metrics.

    Resumable: ``run_judge`` caches per (prompt, model) and checkpoints after
    every batch, so a rerun with the same judge id only pays for what is
    missing. Never call ``register`` again to resume.
    """
    from analysis.helpers import judge_alignment, run_judge  # noqa: PLC0415

    run_judge(judge_id, split="dev", batch_size=10)
    metrics = _metrics(judge_alignment(judge_id, split="dev"))
    metrics["judge_id"] = judge_id
    metrics["split"] = "dev"
    REPORT.mkdir(parents=True, exist_ok=True)
    (REPORT / f"dev-{judge_id}.json").write_text(
        json.dumps(metrics, indent=2, ensure_ascii=False), encoding="utf-8")
    metrics["review_rows"] = _judge_view(judge_id, mode)
    return metrics


def run_test(judge_id: str, mode: str = MODE) -> dict:
    """Freeze the chosen version, score the held-out split, save the metrics.

    ``freeze_judge`` is one-way per version and ``judge_alignment(split="test")``
    refuses to run until it has happened, so the test numbers cannot be seen
    while the prompt is still being chosen.
    """
    from analysis.helpers import freeze_judge, judge_alignment, run_judge  # noqa: PLC0415

    freeze_judge(judge_id)
    run_judge(judge_id, split="test", batch_size=10)
    metrics = _metrics(judge_alignment(judge_id, split="test"))
    metrics["judge_id"] = judge_id
    metrics["split"] = "test"
    (REPORT / f"test-{judge_id}.json").write_text(
        json.dumps(metrics, indent=2, ensure_ascii=False), encoding="utf-8")
    return metrics


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("seed-labels", help="convert HW4 labels into the HW5 file")
    p.add_argument("--mode", default=MODE)
    d = sub.add_parser("drop-bulk", help="exclude HW4 labels accepted in bulk")
    d.add_argument("--mode", default=MODE)
    rg = sub.add_parser("register", help="register a prompt version (free)")
    rg.add_argument("--prompt", required=True)
    rg.add_argument("--mode", default=MODE)
    rg.add_argument("--model", default=JUDGE_MODEL)
    dv = sub.add_parser("develop", help="score the dev split (PAID)")
    dv.add_argument("--judge-id", required=True)
    dv.add_argument("--mode", default=MODE)
    ts = sub.add_parser("test", help="freeze and score the test split (PAID, one way)")
    ts.add_argument("--judge-id", required=True)
    ts.add_argument("--mode", default=MODE)
    pi = sub.add_parser("prepare-inputs", help="write hw5_trace_inputs.json")
    pi.add_argument("--mode", default=MODE)
    sp = sub.add_parser("split", help="split the labels 20/40/40 (run once)")
    sp.add_argument("--mode", default=MODE)
    m = sub.add_parser("mine", help="build the HW5 reading queue (hw5_samples.json)")
    m.add_argument("--mode", default=MODE)
    m.add_argument("--random-slice", type=int, default=25)
    m.add_argument("--seed", type=int, default=11)

    args = parser.parse_args()
    if args.command == "seed-labels":
        print(json.dumps(seed_labels(args.mode), indent=2))
    elif args.command == "register":
        print(json.dumps(register(args.prompt, args.mode, args.model), indent=2))
    elif args.command == "develop":
        print(json.dumps(run_development(args.judge_id, args.mode), indent=2))
    elif args.command == "test":
        print(json.dumps(run_test(args.judge_id, args.mode), indent=2))
    elif args.command == "prepare-inputs":
        print(json.dumps(prepare_inputs(args.mode), indent=2))
    elif args.command == "split":
        print(json.dumps(split_data(args.mode), indent=2))
    elif args.command == "drop-bulk":
        print(json.dumps(drop_bulk_accepted(args.mode), indent=2))
    elif args.command == "mine":
        print(json.dumps(mine_candidates(args.mode, args.random_slice, args.seed), indent=2))


if __name__ == "__main__":
    main()
