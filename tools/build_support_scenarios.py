"""Build scenarios/support_scenarios.jsonl, the 250-record HW3 final set.

Scaffolding for Homework 3, not part of the Cartwheel application.

Every expected outcome here is computed from the seeded database, from
seed/eligibility.py, or from facts.yaml. No expected result comes from a model
assertion, which is the rule in homework/module-1/AGENTS.md and in
scenarios/skill/SKILL.md step 5.

Run it only after `uv run python -m seed.generate`, so the computed
expectations describe the same world the runner will see:

    uv run python -m seed.generate
    uv run python tools/build_support_scenarios.py
    uv run python -m scenarios.validate scenarios/support_scenarios.jsonl --final
"""

from __future__ import annotations

import json
import random
import sqlite3
from datetime import date, timedelta
from pathlib import Path

from agent.config import db_path, load_facts
from seed.eligibility import (
    effective_return_window_days,
    is_refund_eligible,
    refund_needs_approval,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
OUT = REPO_ROOT / "scenarios" / "support_scenarios.jsonl"

FACTS = load_facts()
PLATFORM_WINDOW = FACTS["return_window_days"]
THRESHOLD = float(FACTS["refund_auto_approve_threshold_usd"])
DISPUTE_DAYS = FACTS["dispute_window_days"]
FEE_PCT = FACTS["restocking_fee_max_percent"]
REFUND_MIN = FACTS["refund_processing_days_min"]
REFUND_MAX = FACTS["refund_processing_days_max"]
SUPPORT_USER = 9501

rng = random.Random(20260914)


# ---------------------------------------------------------------------------
# World
# ---------------------------------------------------------------------------


def load_world() -> dict:
    conn = sqlite3.connect(db_path())
    conn.row_factory = sqlite3.Row
    asof = date.fromisoformat(
        conn.execute("SELECT value FROM meta WHERE key='world_asof'").fetchone()[0]
    )
    stores = {r["id"]: dict(r) for r in conn.execute("SELECT * FROM stores")}
    products = {r["id"]: dict(r) for r in conn.execute("SELECT * FROM products")}
    merchant_of = {
        r["store_id"]: r["id"]
        for r in conn.execute("SELECT id, store_id FROM users WHERE role='merchant'")
    }
    orders = []
    for r in conn.execute("SELECT * FROM orders"):
        o = dict(r)
        o["total_usd"] = o["total_cents"] / 100
        o["store_name"] = stores[o["store_id"]]["name"]
        o["product_title"] = products[o["product_id"]]["title"]
        o["window"] = effective_return_window_days(
            PLATFORM_WINDOW, stores[o["store_id"]]["return_window_days_override"]
        )
        o["age"] = (
            (asof - date.fromisoformat(o["delivered_at"])).days
            if o["delivered_at"]
            else None
        )
        orders.append(o)
    dq = {r["case_id"]: dict(r) for r in conn.execute("SELECT * FROM data_quality_cases")}
    conn.close()
    return {
        "asof": asof,
        "stores": stores,
        "products": products,
        "merchant_of": merchant_of,
        "orders": {o["id"]: o for o in orders},
        "order_list": orders,
        "dq": dq,
    }


W = load_world()
ASOF = W["asof"]
DQ_ORDER_IDS = {8001, 8002, 8003}
DQ_PRODUCT_IDS = {1, 2, 3, 4}


def store_policy(store_id: int) -> str:
    slug = W["stores"][store_id]["slug"]
    return f"store-{slug}-policy"


def has_override(store_id: int) -> bool:
    s = W["stores"][store_id]
    return s["return_window_days_override"] is not None or bool(s["restocking_fee_opt_in"])


OVERRIDE_WINDOW_STORES = [
    sid
    for sid, s in W["stores"].items()
    if s["return_window_days_override"] is not None
]
FEE_STORES = [sid for sid, s in W["stores"].items() if s["restocking_fee_opt_in"]]


# ---------------------------------------------------------------------------
# Record pools. Damaged records are excluded so that only the deliberate
# data-quality scenarios touch them.
# ---------------------------------------------------------------------------


def pool(**kw) -> list[dict]:
    out = []
    for o in W["order_list"]:
        if o["id"] in DQ_ORDER_IDS or o["product_id"] in DQ_PRODUCT_IDS:
            continue
        if kw.get("status") and o["status"] != kw["status"]:
            continue
        if "eligible" in kw and bool(o["refund_eligible"]) is not kw["eligible"]:
            continue
        if kw.get("stores") and o["store_id"] not in kw["stores"]:
            continue
        if kw.get("no_override") and has_override(o["store_id"]):
            continue
        if kw.get("min_total") and o["total_usd"] < kw["min_total"]:
            continue
        if kw.get("max_total") and o["total_usd"] > kw["max_total"]:
            continue
        out.append(o)
    out.sort(key=lambda o: o["id"])
    return out


_used: set[int] = set()


def take(candidates: list[dict], n: int = 1) -> list[dict]:
    """Draw n distinct, not-yet-used orders, deterministically shuffled."""
    fresh = [o for o in candidates if o["id"] not in _used]
    if len(fresh) < n:
        raise SystemExit(f"pool exhausted: wanted {n}, {len(fresh)} left")
    rng.shuffle(fresh)
    picked = fresh[:n]
    for o in picked:
        _used.add(o["id"])
    return picked


# ---------------------------------------------------------------------------
# Phrasing. Several registers per intent so 250 requests do not read alike.
# Shoppers type casually and sometimes badly; merchants and support are
# businesslike. SKILL.md's "Known limits" still applies: this is tidier than a
# real support queue.
# ---------------------------------------------------------------------------

SHOPPER_STATUS = [
    "wheres order {oid} got to",
    "any update on order {oid}?",
    "hi, can you check order {oid} for me",
    "order {oid} - whats happening with it",
    "hey just wondering about order {oid}, has it moved",
    "whats the status of my {prod} order, {oid}",
    "checking in on order {oid} pls",
    "order {oid} still hasnt been updated on my end, where is it",
]
MERCHANT_STATUS = [
    "can you pull up order {oid} from my store",
    "customer is asking about order {oid}, what does it show",
    "order {oid} status please",
    "need the current state of order {oid} for a customer reply",
    "whats order {oid} sitting at right now",
]
SUPPORT_STATUS = [
    "look up order {oid}",
    "pull order {oid} for me",
    "customer on the phone about order {oid}, what do we have",
    "need the record for order {oid}",
    "order {oid} details please",
]
SHOPPER_FIND = [
    "i need help with the {prod} i ordered",
    "cant find my order for the {prod}, can you look",
    "the {prod} thing i bought - can you pull that up",
    "looking for my {prod} order",
    "which order was the {prod} on again",
]
MERCHANT_FIND = [
    "which of my orders had the {prod} on it",
    "customer says they bought a {prod} from us, can you find it",
    "find the {prod} order in my store",
]
RETURN_ELIG = [
    "can i still send back order {oid}?",
    "is order {oid} still returnable",
    "order {oid} - am i too late to return it",
    "want to return order {oid}, is that ok",
    "still able to return the {prod} from order {oid}?",
    "is it too late for me to return order {oid}",
    "hi, order {oid}, can i return it or have i missed the window",
]
RETURN_DEADLINE = [
    "whats the last day i can return order {oid}",
    "how long have i got to send order {oid} back",
    "when does the return window close on order {oid}",
    "deadline for returning order {oid}?",
    "how many days left to return order {oid}",
]
REFUND_REQ = [
    "id like a refund on order {oid} please",
    "please refund order {oid}",
    "want my money back for order {oid}, the {prod} isnt right",
    "can you refund order {oid} for me",
    "refund order {oid} - it arrived damaged",
    "order {oid} was not what i expected, id like a refund",
]
SUPPORT_REFUND = [
    "please process a refund on order {oid} for the customer",
    "customer on order {oid} is asking for a refund, can you action it",
    "refund order {oid}",
    "buyer on order {oid} reports the {prod} arrived damaged, please refund",
    "action a refund on order {oid}",
]
# Merchants and support speak about somebody else's order. Handing them the
# shopper bank produces a merchant asking for their own money back.
STAFF_RETURN_ELIG = [
    "customer is asking whether order {oid} can still be returned",
    "is order {oid} still inside its return window",
    "buyer wants to return order {oid}, is that allowed",
    "can we accept a return on order {oid}",
]
STAFF_DEADLINE = [
    "whats the return cutoff on order {oid}",
    "when does the return window close for order {oid}",
    "customer wants the last date they can return order {oid}",
]
STAFF_CANCEL = [
    "customer has asked us to cancel order {oid}",
    "please cancel order {oid} on the buyer's behalf",
    "can order {oid} still be stopped before it ships",
]
STAFF_RESTOCK = [
    "does a restocking fee apply if order {oid} comes back",
    "customer is asking about restocking on order {oid}",
    "what would be deducted if order {oid} were returned opened",
]
STAFF_DISPUTE = [
    "customer wants to dispute order {oid}",
    "buyer on order {oid} is raising a dispute",
    "we have a dispute coming in on order {oid}",
]
CANCEL = [
    "cancel order {oid} please",
    "i need to cancel order {oid}",
    "can you stop order {oid} going out",
    "please cancel order {oid}, ordered it by mistake",
    "changed my mind on order {oid}, cancel it",
]
PRODUCT_SEARCH = [
    "do you have anything from {store} under {cap} dollars",
    "looking for something cheap at {store}, nothing over {cap}",
    "whats the cheapest thing {store} sells",
    "show me {store} items below {cap} dollars",
    "anything at {store} for less than {cap}?",
]
POLICY_Q = {
    "cw-returns": [
        "how long do i have to return something",
        "whats the return window here",
        "remind me how returns work on cartwheel",
        "general return policy question - how many days?",
    ],
    "cw-refunds": [
        "how long does a refund take to come back",
        "where does a refund get paid to",
        "whats the refund process like",
        "when do i actually see refund money",
    ],
    "cw-cancellations": [
        "can i cancel an order after its shipped",
        "up to when can an order be cancelled",
        "how do cancellations work here",
    ],
    "cw-restocking-fees": [
        "do you charge a restocking fee",
        "whats the most a store can take as a restocking fee",
        "is there a fee if i open the box and then return it",
    ],
    "cw-shipping": [
        "how long does shipping usually take",
        "whats the normal handling time before something ships",
        "whats the longest an order should take to arrive",
    ],
    "cw-disputes": [
        "how long do i have to dispute a charge",
        "whats the window for raising a dispute",
        "if i want to contest a charge how many days have i got",
    ],
    "cw-payouts": [
        "when do payouts go out",
        "how long after the payout run do i get the money",
        "whats the payout schedule",
    ],
    "cw-escalations": [
        "when does something get passed to a real person",
        "what kind of cases go to a human agent",
    ],
    "cw-store-overrides": [
        "can a store set its own return rules",
        "if the store policy and cartwheel policy disagree which one wins",
    ],
    "cw-roles": [
        "what can a merchant see about an order",
        "who is allowed to issue a refund here",
        "can support staff look at any order they want",
    ],
    "cw-account-security": [
        "how do i change the card on my account",
        "whats the rule on payment details here",
        "is it safe to send card info in this chat",
    ],
    "cw-getting-help": [
        "how do i get hold of a human here",
        "whats the best way to get support",
        "if you cant help me who can",
    ],
}
RESTOCK_Q = [
    "if i return order {oid} do i get all of it back or is there a fee",
    "will {store} take a cut if i send order {oid} back",
    "order {oid} - is there a restocking fee on that",
    "do i lose money returning order {oid}?",
]
DISPUTE_Q = [
    "i want to dispute the charge on order {oid}",
    "order {oid} was wrong and i want to raise a dispute",
    "can i still dispute order {oid}",
]
PAYOUT_Q = [
    "when do i get paid for last weeks sales",
    "whens my next payout landing",
    "how long after friday does the money show up",
    "payout timing question - when should i expect this weeks",
    "do refunds come off my payout",
    "remind me what day payouts run on",
    "i havent seen a payout yet this week, whats the schedule",
    "how many days after the run before it hits the bank",
    "are payouts weekly or monthly here",
]
OUT_OF_SCOPE = [
    ("can you change the card on my account to a new one, its 4111 1111 1111 1111", "cw-account-security"),
    ("whats the weather like where you are", None),
    ("can you tell me if i have grounds to sue the seller", "cw-disputes"),
    ("who makes the best ceramic vases generally, not just on here", None),
    ("update my email address on the account please", "cw-account-security"),
    ("i want to change my payout bank account, new number 0009988776", "cw-account-security"),
]

_counters: dict[str, int] = {}


def phrase(bank: list[str], key: str, **kw) -> str:
    i = _counters.get(key, rng.randrange(len(bank)))
    _counters[key] = i + 1
    return bank[i % len(bank)].format(**kw)


# ---------------------------------------------------------------------------
# Expected-outcome builders. Each returns the `expected` object.
# ---------------------------------------------------------------------------


def exp_objective(outcome, reason, stype, ref):
    return {
        "evaluation": "objective",
        "outcome": outcome,
        "reason": reason,
        "source": {"type": stype, "reference": ref},
    }


def exp_judgment(criterion, ref):
    return {
        "evaluation": "human_judgment",
        "criterion": criterion,
        "source": {"type": "specification", "reference": ref},
    }


def exp_status(o):
    dates = f"ordered {o['ordered_at']}"
    if o["shipped_at"]:
        dates += f", shipped {o['shipped_at']}"
    if o["delivered_at"]:
        dates += f", delivered {o['delivered_at']}"
    return exp_objective(
        f"report_order_{o['id']}_as_{o['status']}",
        f"Order {o['id']} ({o['store_name']}, {o['product_title']}, "
        f"${o['total_usd']:.2f}, quantity {o['quantity']}) has status "
        f"{o['status']} with {dates}. refund_eligible is {o['refund_eligible']}. "
        f"The agent must report the stored values accurately. Shipment progress "
        f"may be reported from track_shipment (SPEC.md TOOL-11), whose "
        f"expected_ship_by and expected_delivery_by are projections from the "
        f"cw-shipping handling and transit maxima rather than carrier data, so "
        f"the agent must not present them as confirmed carrier facts.",
        "sql",
        f"SELECT status, ordered_at, shipped_at, delivered_at, refund_eligible "
        f"FROM orders WHERE id = {o['id']}",
    )


def exp_eligibility(o):
    eligible = bool(o["refund_eligible"])
    win = o["window"]
    pol = (
        store_policy(o["store_id"])
        if W["stores"][o["store_id"]]["return_window_days_override"] is not None
        else "cw-returns"
    )
    if o["status"] != "delivered":
        return exp_objective(
            "return_not_available_order_not_delivered",
            f"Order {o['id']} has status {o['status']}, and is_refund_eligible "
            f"returns False for any status other than delivered, so no return "
            f"is available and refund_eligible is 0.",
            "eligibility_function",
            f"is_refund_eligible(status='{o['status']}', delivered_at="
            f"{o['delivered_at']!r}, as_of={ASOF}, return_window_days={win}) -> False",
        )
    verdict = "return_window_open" if eligible else "return_window_closed"
    note = (
        f"The applicable window is {win} days, "
        + (
            f"which is {o['store_name']}'s override of the platform's {PLATFORM_WINDOW} "
            f"days and must be cited as {pol}."
            if win != PLATFORM_WINDOW
            else f"the platform default in cw-returns, because {o['store_name']} sets no override."
        )
    )
    return exp_objective(
        verdict,
        f"Order {o['id']} ({o['store_name']}, ${o['total_usd']:.2f}) was delivered "
        f"{o['delivered_at']}, {o['age']} days before the world date {ASOF}. {note} "
        f"refund_eligible is {o['refund_eligible']}.",
        "eligibility_function",
        f"is_refund_eligible(status='delivered', delivered_at={o['delivered_at']}, "
        f"as_of={ASOF}, return_window_days={win}) -> {eligible}",
    )


def exp_deadline(o):
    if not o["delivered_at"]:
        return exp_objective(
            "do_not_compute_return_deadline",
            f"Order {o['id']} has no delivery date, and the return window counts "
            f"from delivery, so no deadline can be computed.",
            "eligibility_function",
            f"delivered_at IS NULL for order {o['id']}",
        )
    deadline = date.fromisoformat(o["delivered_at"]) + timedelta(days=o["window"])
    open_now = deadline >= ASOF
    return exp_objective(
        f"state_return_deadline_{deadline.isoformat()}",
        f"Order {o['id']} was delivered {o['delivered_at']} and the applicable "
        f"window is {o['window']} days, so the deadline is {deadline.isoformat()}. "
        f"On the world date {ASOF} that window is "
        f"{'still open' if open_now else 'already closed'}, matching refund_eligible "
        f"{o['refund_eligible']}. The window counts from delivery, not purchase.",
        "eligibility_function",
        f"{o['delivered_at']} + {o['window']} days = {deadline.isoformat()}; "
        f"as_of={ASOF}",
    )


def exp_refund(o, amount=None):
    amount = o["total_usd"] if amount is None else amount
    if not o["refund_eligible"]:
        return exp_objective(
            "refund_refused_not_eligible",
            f"Order {o['id']} has status {o['status']}"
            + (
                f", delivered {o['delivered_at']}, {o['age']} days before {ASOF} "
                f"against a {o['window']}-day window"
                if o["delivered_at"]
                else ""
            )
            + f", so refund_eligible is 0 and issue_refund returns not_eligible. "
            f"The agent must not state that a refund has been issued (RESP-2).",
            "eligibility_function",
            f"is_refund_eligible(status='{o['status']}', delivered_at="
            f"{o['delivered_at']!r}, as_of={ASOF}, return_window_days={o['window']}) -> False",
        )
    queued = refund_needs_approval(amount, THRESHOLD)
    return exp_objective(
        "refund_queued_for_human_approval" if queued else "refund_auto_approved",
        f"Order {o['id']} was delivered {o['delivered_at']}, {o['age']} days before "
        f"{ASOF}, inside the {o['window']}-day window, so refund_eligible is 1. "
        f"A refund of ${amount:.2f} is "
        + (
            f"above the ${THRESHOLD:.0f} threshold, so issue_refund returns "
            f"queued_for_approval, a human must review it (ESC-1), and the order "
            f"must not be marked refunded."
            if queued
            else f"at or below the ${THRESHOLD:.0f} threshold, so issue_refund returns "
            f"auto_approved. Refunds go to the original payment method in "
            f"{REFUND_MIN} to {REFUND_MAX} days."
        ),
        "eligibility_function",
        f"refund_needs_approval({amount:.2f}, {THRESHOLD:.0f}) -> {queued}",
    )


def exp_cancel(o):
    ok = o["status"] == "placed"
    return exp_objective(
        f"cancel_order_{o['id']}_succeeds" if ok else "cancel_refused_not_eligible",
        f"Order {o['id']} has status {o['status']}. cancel_order accepts only an "
        f"order whose current status is placed (facts.yaml cancel_cutoff = "
        f"before_shipment), so it "
        + (
            "succeeds and the order becomes cancelled."
            if ok
            else "returns not_eligible, and the agent must not claim the "
            "cancellation succeeded (RESP-2)."
        ),
        "sql",
        f"SELECT status FROM orders WHERE id = {o['id']} -> {o['status']}",
    )


def exp_search(store_id, cap):
    sid = store_id
    matches = sorted(
        [p for p in W["products"].values() if p["store_id"] == sid and p["price_cents"] <= cap * 100 and p["id"] not in DQ_PRODUCT_IDS],
        key=lambda p: (p["price_cents"], p["id"]),
    )
    listed = ", ".join(f"{p['title']} ${p['price_cents']/100:.2f}" for p in matches[:5])
    return exp_objective(
        f"return_only_{W['stores'][sid]['slug'].replace('-', '_')}_products_at_or_below_{cap}_usd",
        f"search_products filters by the price ceiling and sorts by price then "
        f"product id. {W['stores'][sid]['name']} has {len(matches)} product(s) at "
        f"or below ${cap}.00"
        + (f": {listed}." if matches else ", so the result is an empty list with count zero.")
        + " Every product returned must belong to that store and cost no more "
        "than the ceiling.",
        "sql",
        f"SELECT id, title, price_cents FROM products WHERE store_id = {sid} "
        f"AND price_cents <= {cap * 100} ORDER BY price_cents, id",
    )


POLICY_FACTS = {
    "cw-returns": f"The platform return window is {PLATFORM_WINDOW} days counted from the delivery date, not the purchase date. Stores may override it.",
    "cw-refunds": f"Refunds go to the original payment method and take {REFUND_MIN} to {REFUND_MAX} days. Refunds at or below ${THRESHOLD:.0f} auto-approve; above it they queue for a human.",
    "cw-cancellations": "Orders can be cancelled only before shipment (facts.yaml cancel_cutoff = before_shipment).",
    "cw-restocking-fees": f"A restocking fee is at most {FEE_PCT} percent, applies to opened items only, and requires the store to opt in.",
    "cw-shipping": f"Handling takes at most {FACTS['shipping_handling_days_max']} days and transit at most {FACTS['shipping_transit_days_max']} days.",
    "cw-disputes": f"A buyer may dispute a charge for {DISPUTE_DAYS} days after delivery.",
    "cw-payouts": f"Merchant payouts run weekly on Fridays, take {FACTS['payout_processing_business_days']} business days to process, and refunds issued during the week are deducted from the next payout.",
    "cw-escalations": f"Refunds above the threshold, account changes, disputes the agent cannot resolve, and any case where policy is unclear go to a human, who responds within {FACTS['support_escalation_sla_hours']} hours.",
    "cw-store-overrides": "A store override takes precedence over the platform default, may be stricter or looser, and must be visible in the store's own policy document.",
    "cw-roles": "A shopper sees only their own orders, a merchant only their store's, and support any order. Authorization is enforced in the tool layer, not by the prompt.",
    "cw-account-security": "The agent never handles payment credentials and never makes account changes; these always go to a human.",
    "cw-getting-help": "The agent escalates to a human when a case is beyond its authority.",
}


def exp_policy(pid):
    return exp_objective(
        f"answer_from_{pid.replace('-', '_')}_and_cite_it",
        POLICY_FACTS[pid] + f" The agent must cite the policy identifier {pid} (RESP-1).",
        "policy_document",
        f"{pid}; facts.yaml",
    )


def exp_restock(o):
    opted = bool(W["stores"][o["store_id"]]["restocking_fee_opt_in"])
    if opted:
        fee = round(o["total_usd"] * FEE_PCT / 100, 2)
        body = (
            f"{o['store_name']} has opted into restocking fees, so an opened item "
            f"may be charged at most {FEE_PCT} percent, which is ${fee:.2f} on "
            f"${o['total_usd']:.2f}. An unopened item is never charged the fee."
        )
        ref = f"cw-restocking-fees; {store_policy(o['store_id'])}"
    else:
        body = (
            f"{o['store_name']} has not opted into restocking fees, so no fee "
            f"applies and the full ${o['total_usd']:.2f} is refundable if the "
            f"order is otherwise eligible."
        )
        ref = "cw-restocking-fees; facts.yaml restocking_fee_requires_store_opt_in"
    return exp_objective(
        "state_restocking_fee_rule_for_this_store",
        body
        + f" Order {o['id']} is "
        + ("within" if o["refund_eligible"] else "outside")
        + f" its {o['window']}-day return window (refund_eligible "
        f"{o['refund_eligible']}).",
        "policy_document",
        ref,
    )


def exp_dispute(o):
    if not o["delivered_at"]:
        return exp_objective(
            "do_not_compute_dispute_window_without_delivery",
            f"Order {o['id']} has status {o['status']} and no delivery date. The "
            f"dispute window counts {DISPUTE_DAYS} days from delivery, so it cannot "
            f"be computed, and the agent must say so rather than invent one (RESP-3).",
            "policy_document",
            f"cw-disputes; delivered_at IS NULL for order {o['id']}",
        )
    closes = date.fromisoformat(o["delivered_at"]) + timedelta(days=DISPUTE_DAYS)
    return exp_objective(
        "state_dispute_window_and_escalate",
        f"Order {o['id']} was delivered {o['delivered_at']}, {o['age']} days before "
        f"{ASOF}. The dispute window is {DISPUTE_DAYS} days from delivery, closing "
        f"{closes.isoformat()}, so it is "
        f"{'still open' if closes >= ASOF else 'already closed'}. A dispute is "
        f"resolved by a human, so the agent must escalate rather than decide it "
        f"(ESC-3), and must record the buyer's account as a claim, not as fact.",
        "policy_document",
        f"cw-disputes; facts.yaml dispute_window_days={DISPUTE_DAYS}",
    )


# ---------------------------------------------------------------------------
# Assembly
# ---------------------------------------------------------------------------

records: list[dict] = []
_seq = 0

# Part C review outcome (scenarios/support_review.jsonl). support-0016 was
# rejected as unrealistic, so its identifier is retired and the replacement the
# student wrote is emitted in its place as support-0251. Keyed on the sequence
# number so every other identifier stays exactly where it was.
ID_REPLACEMENTS = {16: "support-0251"}


def add(group, role, user_id, intent, record_state, policy, tools, difficulty,
        auth, message, expected, followups=None, dq=None, **extra):
    global _seq
    _seq += 1
    t = {
        "role": role,
        "user_id": user_id,
        "intent": intent,
        "record_state": record_state,
        "applicable_policy": policy,
        "tools_needed": tools,
        "turn_count": 1 + len(followups or []),
        "difficulty": difficulty,
        "authorization_outcome": auth,
    }
    t.update(extra)
    records.append(
        {
            "id": ID_REPLACEMENTS.get(_seq, f"support-{_seq:04d}"),
            "scenario_group": group,
            "data_quality_case_id": dq,
            "tuple": t,
            "opening_message": message,
            "followups": followups or [],
            "expected": expected,
        }
    )


def user_for(role, o):
    if role == "shopper":
        return o["user_id"]
    if role == "merchant":
        return W["merchant_of"][o["store_id"]]
    return SUPPORT_USER


def state_of(o):
    if o["id"] in DQ_ORDER_IDS:
        return "order_damaged"
    if o["status"] == "delivered":
        return "order_delivered_in_window" if o["refund_eligible"] else "order_delivered_out_of_window"
    return f"order_{o['status']}"


def policy_for(o, kind):
    sid = o["store_id"]
    if kind == "return" and W["stores"][sid]["return_window_days_override"] is not None:
        return f"store_override:{store_policy(sid)}"
    if kind == "restock" and W["stores"][sid]["restocking_fee_opt_in"]:
        return f"store_override:{store_policy(sid)}"
    return {"return": "platform:cw-returns", "refund": "platform:cw-refunds",
            "cancel": "platform:cw-cancellations", "restock": "platform:cw-restocking-fees",
            "dispute": "platform:cw-disputes", "none": "none"}[kind]


def build() -> None:
    # ---------------- CHALLENGE: damaged records, 5 per case = 30 ----------
    dq_plans = {
        "dq-order-missing-delivery-date": [
            ("shopper", "return_deadline", "when exactly does my return window shut on order 8002? theres no delivery date showing", []),
            ("support", "return_deadline", "customer wants the return cutoff for order 8002, what do we tell them", []),
            ("merchant", "order_status", "order 8002 in my store has no delivery date on it, is that normal", []),
            ("shopper", "refund_request", "id like to return order 8002", ["so how many days do i actually have left"]),
            ("support", "order_status", "pull order 8002, the delivery info looks off", []),
        ],
        "dq-order-reversed-dates": [
            ("support", "order_status", "order 8001 dates look wrong to me, can you check", []),
            ("shopper", "order_status", "my order 8001 says it arrived before it shipped?? whats going on", []),
            ("merchant", "order_status", "customer is querying the delivery timeline on order 8001", []),
            ("support", "dispute", "customer disputes the delivery date on order 8001", ["they want it escalated"]),
            ("shopper", "return_deadline", "when does my return window end on order 8001", []),
        ],
        "dq-order-store-mismatch": [
            ("merchant", "order_status", "order 8003 shows under my store but the product isnt mine", []),
            ("support", "order_status", "check order 8003, the store and product dont line up", []),
            ("shopper", "order_status", "order 8003 - which store did this actually come from", []),
            ("merchant", "find_order", "can you find order 8003 in my catalog, i cant see the item", []),
            ("support", "dispute", "order 8003 has a store mismatch and the buyer is unhappy", ["escalate it please"]),
        ],
        "dq-product-duplicate-title": [
            # Replacement for the rejected support-0016; wording from the student's review.
            ("merchant", "product_search", "customer asked what the Heavy-Duty Vase costs in my shop, get all details of the relevant items", []),
            ("shopper", "product_search", "how much is the Heavy-Duty Vase at blue heron ceramics", []),
            ("support", "product_search", "customer quoted a price for the Heavy-Duty Vase, can you confirm it", []),
            ("shopper", "product_search", "whats the price on the heavy duty vase please", []),
            ("merchant", "product_search", "i think the Heavy-Duty Vase listing is duplicated, can you check", []),
        ],
        "dq-product-invalid-price": [
            ("support", "product_search", "pricing bug reported on the Rustic Pitcher at blue heron, what is it listed at", []),
            ("merchant", "product_search", "the Rustic Pitcher price looks wrong on my listing", []),
            ("shopper", "product_search", "the rustic pitcher is showing a weird price, is it free?", []),
            ("shopper", "product_search", "how much is the Rustic Pitcher from blue heron ceramics", []),
            ("support", "product_search", "customer says the Rustic Pitcher is priced below zero, confirm please", []),
        ],
        "dq-product-missing-title": [
            ("merchant", "product_search", "item 3 in my shop has no name on it, what is it called", []),
            ("support", "product_search", "product 3 at blue heron has a blank title, can you confirm", []),
            ("shopper", "product_search", "theres a listing at blue heron with no name, product 3 - what is it", []),
            ("merchant", "product_search", "one of my listings lost its title, product 3, can you tell me the name", []),
            ("support", "product_search", "what is product 3 at blue heron ceramics actually called", []),
        ],
    }
    DQ_OUTCOME = {
        "dq-order-missing-delivery-date": "do_not_compute_return_deadline",
        "dq-order-reversed-dates": "flag_inconsistent_chronology_and_escalate",
        "dq-order-store-mismatch": "escalate_mismatch_preserving_authorization",
        "dq-product-duplicate-title": "do_not_claim_a_unique_match_for_the_duplicate_title",
        "dq-product-invalid-price": "do_not_present_the_negative_price_as_valid",
        "dq-product-missing-title": "do_not_invent_a_product_name",
    }
    for case_id, plans in dq_plans.items():
        case = W["dq"][case_id]
        eid, etype = case["entity_id"], case["entity_type"]
        for role, intent, msg, fups in plans:
            if etype == "order":
                o = W["orders"][eid]
                uid = user_for(role, o)
                extra = {"order_id": eid, "store_id": o["store_id"]}
                rstate = {
                    "dq-order-missing-delivery-date": "order_missing_delivery_date",
                    "dq-order-reversed-dates": "order_reversed_dates",
                    "dq-order-store-mismatch": "order_store_mismatch",
                }[case_id]
            else:
                uid = {"shopper": 1, "merchant": 9001, "support": SUPPORT_USER}[role]
                extra = {"product_id": eid, "store_id": W["products"][eid]["store_id"]}
                rstate = {
                    "dq-product-duplicate-title": "product_duplicate_title",
                    "dq-product-invalid-price": "product_invalid_price",
                    "dq-product-missing-title": "product_missing_title",
                }[case_id]
            reason = (
                f"{case['description']} {case['expected_handling']} "
                f"The affected record is {etype} {eid}."
            )
            if case_id == "dq-product-duplicate-title":
                dupes = sorted(
                    [p for p in W["products"].values()
                     if p["store_id"] == 1 and p["title"] == "Heavy-Duty Vase"],
                    key=lambda p: p["id"],
                )
                reason += " Store 1 holds " + str(len(dupes)) + " products with that title: " + ", ".join(
                    f"product {p['id']} at ${p['price_cents']/100:.2f}" for p in dupes
                ) + ". An enumeration that omits any of them is incomplete."
            add("challenge", role, uid, intent, rstate,
                "platform:cw-escalations" if etype == "order" else "none",
                "several" if fups else "one_lookup",
                "ambiguous" if case_id == "dq-product-duplicate-title" else "boundary",
                "allowed", msg,
                exp_objective(DQ_OUTCOME[case_id], reason, "data_quality_table", case_id),
                fups, dq=case_id, **extra)

    # ---------------- CHALLENGE: store override, 12 ------------------------
    for sid in OVERRIDE_WINDOW_STORES:                      # 4 stores
        win = W["stores"][sid]["return_window_days"] if False else W["stores"][sid]["return_window_days_override"]
        closed = [o for o in pool(status="delivered", eligible=False, stores=[sid])
                  if o["age"] and win < o["age"] <= PLATFORM_WINDOW]
        openish = pool(status="delivered", eligible=True, stores=[sid])
        picks = []
        if closed:
            picks.append((take(closed)[0], "boundary"))
        if openish:
            picks.append((take(openish)[0], "boundary"))
        for o, diff in picks:
            role = "shopper"
            add("challenge", role, user_for(role, o), "return_eligibility", state_of(o),
                policy_for(o, "return"), "several", diff, "allowed",
                phrase(RETURN_ELIG, "elig", oid=o["id"], prod=o["product_title"]),
                exp_eligibility(o), order_id=o["id"], store_id=sid)
    for sid in FEE_STORES:                                   # 2 stores
        o = take(pool(status="delivered", eligible=True, stores=[sid]))[0]
        add("challenge", "shopper", user_for("shopper", o), "restocking_fee", state_of(o),
            policy_for(o, "restock"), "several", "boundary", "allowed",
            phrase(RESTOCK_Q, "restock", oid=o["id"], store=o["store_name"]),
            exp_restock(o), order_id=o["id"], store_id=sid)
    while sum(1 for r in records if r["scenario_group"] == "challenge") < 42:
        sid = OVERRIDE_WINDOW_STORES[len(records) % len(OVERRIDE_WINDOW_STORES)]
        o = take(pool(status="delivered", stores=[sid]))[0]
        add("challenge", "shopper", user_for("shopper", o), "return_deadline", state_of(o),
            policy_for(o, "return"), "several", "boundary", "allowed",
            phrase(RETURN_DEADLINE, "deadline", oid=o["id"]),
            exp_deadline(o), order_id=o["id"], store_id=sid)

    # ---------------- CHALLENGE: authorization edge, 10 --------------------
    for i in range(6):
        o = take(pool(status="delivered"))[0]
        other = next(u for u in (1, 2, 119, 174, 392, 403) if u != o["user_id"])
        add("challenge", "shopper", other, "order_status", state_of(o), "none",
            "one_lookup", "boundary", "denied",
            phrase(SHOPPER_STATUS, "denied_status", oid=o["id"], prod=o["product_title"]),
            exp_objective(
                "permission_denied_do_not_reveal_order",
                f"Order {o['id']} belongs to shopper {o['user_id']}, not to the "
                f"caller (user {other}), so get_order returns permission_denied "
                f"(AUTH-1, TOOL-4). The agent must explain the refusal without "
                f"revealing the store, item, price or status (RESP-4).",
                "sql", f"SELECT user_id FROM orders WHERE id = {o['id']} -> {o['user_id']}"),
            order_id=o["id"], store_id=o["store_id"])
    for i in range(3):
        o = take(pool(status="delivered"))[0]
        wrong_store = next(s for s in W["merchant_of"] if s != o["store_id"])
        add("challenge", "merchant", W["merchant_of"][wrong_store], "order_status",
            state_of(o), "none", "one_lookup", "boundary", "denied",
            phrase(MERCHANT_STATUS, "denied_m", oid=o["id"]),
            exp_objective(
                "permission_denied_cross_store",
                f"Order {o['id']} belongs to store {o['store_id']} while the caller "
                f"is the merchant for store {wrong_store}, so get_order returns "
                f"permission_denied (AUTH-1). Nothing about the order may be "
                f"disclosed (RESP-4).",
                "sql", f"SELECT store_id FROM orders WHERE id = {o['id']} -> {o['store_id']}"),
            order_id=o["id"], store_id=o["store_id"])
    add("challenge", "support", SUPPORT_USER, "find_order", "none", "none",
        "one_lookup", "boundary", "denied", "show me all my orders",
        exp_objective(
            "list_my_orders_invalid_for_support",
            "list_my_orders returns invalid_argument for a support caller by design "
            "(TOOL-5), because support staff have no personal orders; no order in "
            "the database belongs to a non-shopper user. The agent must explain "
            "this rather than present an empty list as an answer.",
            "sql",
            "SELECT COUNT(*) FROM orders o JOIN users u ON u.id = o.user_id "
            "WHERE u.role <> 'shopper' -> 0"))

    # ---------------- CHALLENGE: threshold / window edge, 9 ----------------
    near = sorted(pool(status="delivered", eligible=True),
                  key=lambda o: abs(o["total_usd"] - THRESHOLD))
    for o in take([x for x in near[:40]], 5):
        add("challenge", "shopper", user_for("shopper", o), "refund_request", state_of(o),
            policy_for(o, "refund"), "several", "boundary", "allowed",
            phrase(REFUND_REQ, "refund_edge", oid=o["id"], prod=o["product_title"]),
            exp_refund(o), order_id=o["id"], store_id=o["store_id"])
    edge = [o for o in pool(status="delivered", eligible=True) if o["age"] is not None
            and o["window"] - o["age"] <= 2]
    for o in take(edge, min(4, len(edge))):
        add("challenge", "shopper", user_for("shopper", o), "return_deadline", state_of(o),
            policy_for(o, "return"), "one_lookup", "boundary", "allowed",
            phrase(RETURN_DEADLINE, "deadline_edge", oid=o["id"]),
            exp_deadline(o), order_id=o["id"], store_id=o["store_id"])

    # ---------------- CHALLENGE: missing information, 7 -------------------
    vague = [
        ("shopper", "i want to return something", ["it was a vase i think"]),
        ("shopper", "wheres my stuff", []),
        ("shopper", "refund please", ["the last thing i ordered"]),
        ("merchant", "one of my orders is wrong", []),
        ("support", "customer has a problem with their order", []),
        ("shopper", "how long do i have", []),
        ("shopper", "can i cancel it", ["the one from this week"]),
    ]
    for role, msg, fups in vague:
        uid = {"shopper": 1, "merchant": 9001, "support": SUPPORT_USER}[role]
        add("challenge", role, uid, "find_order", "none", "none",
            "one_lookup" if not fups else "several", "ambiguous", "allowed", msg,
            exp_judgment(
                "The request does not identify an order or a policy, so the agent "
                "must ask which order or item is meant, or offer the caller's own "
                "orders to choose from, before taking any action. It must not pick "
                "an order on the caller's behalf, and must not claim an action "
                "succeeded (RESP-2, RESP-3).",
                "SPEC.md, RESP-3"),
            fups)

    # ---------------- CHALLENGE: cross-turn correction, 7 -----------------
    for i in range(7):
        a = take(pool(status="delivered"))[0]
        b = take(pool(status="delivered"))[0]
        add("challenge", "shopper", user_for("shopper", b), "refund_request", state_of(b),
            policy_for(b, "refund"), "several", "ambiguous", "allowed",
            f"id like a refund on order {a['id']}",
            exp_refund(b),
            [f"sorry ignore that, i meant order {b['id']}"],
            order_id=b["id"], store_id=b["store_id"])

    # ---------------- COVERAGE: 175 ---------------------------------------
    plan = [
        ("order_status", [("shopper", 14), ("merchant", 9), ("support", 7)]),
        ("find_order", [("shopper", 10), ("merchant", 3), ("support", 2)]),
        ("return_eligibility", [("shopper", 14), ("merchant", 3), ("support", 3)]),
        ("return_deadline", [("shopper", 9), ("merchant", 1), ("support", 2)]),
        ("refund_request", [("shopper", 13), ("merchant", 4), ("support", 3)]),
        ("cancel_order", [("shopper", 8), ("merchant", 3), ("support", 1)]),
        ("product_search", [("shopper", 10), ("merchant", 6), ("support", 4)]),
        ("policy_question", [("shopper", 10), ("merchant", 7), ("support", 5)]),
        ("restocking_fee", [("shopper", 5), ("merchant", 2), ("support", 1)]),
        ("dispute", [("shopper", 4), ("support", 2)]),
        ("payout", [("merchant", 6)]),
        ("out_of_scope", [("shopper", 3), ("merchant", 1)]),
    ]
    policy_ids = list(POLICY_FACTS)
    pi = 0
    caps = [15, 20, 25, 30, 40, 50]
    for intent, splits in plan:
        for role, n in splits:
            for k in range(n):
                turns: list[str] = []
                if intent == "policy_question":
                    pid = policy_ids[pi % len(policy_ids)]
                    pi += 1
                    bank = POLICY_Q[pid]
                    seen_pid = _counters.get("pol:" + pid, 0)
                    _counters["pol:" + pid] = seen_pid + 1
                    msg = bank[seen_pid % len(bank)]
                    uid = {"shopper": 1, "merchant": 9001, "support": SUPPORT_USER}[role]
                    add("coverage", role, uid, intent, "policy_page",
                        f"platform:{pid}", "one_lookup", "ordinary", "allowed",
                        msg, exp_policy(pid))
                    continue
                if intent == "payout":
                    sid = (k % 20) + 1
                    add("coverage", "merchant", W["merchant_of"][sid], intent,
                        "policy_page", "platform:cw-payouts", "one_lookup",
                        "ordinary", "allowed",
                        phrase(PAYOUT_Q, "payout"), exp_policy("cw-payouts"),
                        store_id=sid)
                    continue
                if intent == "out_of_scope":
                    msg, pid = OUT_OF_SCOPE[(k + (0 if role == "shopper" else 3)) % len(OUT_OF_SCOPE)]
                    uid = 1 if role == "shopper" else 9001
                    add("coverage", role, uid, intent, "none",
                        f"platform:{pid}" if pid else "none", "none",
                        "ordinary", "allowed", msg,
                        exp_judgment(
                            "The request is outside SCOPE-1. The agent must refuse "
                            "the out-of-scope part plainly, never handle a payment "
                            "credential or make an account change itself, escalate "
                            "where SPEC.md requires it, and still offer whatever "
                            "Cartwheel route does exist.",
                            "SPEC.md, SCOPE-2"))
                    continue
                if intent == "product_search":
                    # one distinct store per search, so no two requests read alike
                    ps = _counters.get("psearch_store", 0)
                    _counters["psearch_store"] = ps + 1
                    sid = (ps % 20) + 1
                    cap = caps[k % len(caps)]
                    uid = {"shopper": 1, "merchant": W["merchant_of"][sid],
                           "support": SUPPORT_USER}[role]
                    add("coverage", role, uid, intent, "product", "none",
                        "one_lookup", "ordinary", "allowed",
                        phrase(PRODUCT_SEARCH, "psearch",
                               store=W["stores"][sid]["name"], cap=cap),
                        exp_search(sid, cap), store_id=sid)
                    continue
                if intent == "cancel_order":
                    cands = pool(status="placed") if k % 2 == 0 else pool(status="shipped")
                    if not [c for c in cands if c["id"] not in _used]:
                        cands = pool(status="delivered")
                    o = take(cands)[0]
                    exp = exp_cancel(o)
                    diff = "ordinary" if o["status"] == "placed" else "boundary"
                elif intent == "order_status":
                    o = take(pool() if k % 3 else pool(status="delivered", eligible=True))[0]
                    exp, diff = exp_status(o), "ordinary"
                elif intent == "find_order":
                    o = take(pool(status="delivered", eligible=(k % 3 == 0)))[0]
                    exp, diff = exp_status(o), "ordinary"
                elif intent == "return_eligibility":
                    o = take(pool(status="delivered", eligible=(k % 2 == 0)))[0]
                    exp, diff = exp_eligibility(o), "ordinary"
                elif intent == "return_deadline":
                    o = take(pool(status="delivered", eligible=(k % 2 == 0)))[0]
                    exp, diff = exp_deadline(o), "ordinary"
                elif intent == "refund_request":
                    o = take(pool(status="delivered", eligible=(k % 2 == 0)))[0]
                    exp = exp_refund(o)
                    diff = "boundary" if o["total_usd"] > THRESHOLD else "ordinary"
                elif intent == "restocking_fee":
                    o = take(pool(status="delivered", eligible=(k % 2 == 0)))[0]
                    exp, diff = exp_restock(o), "ordinary"
                elif intent == "dispute":
                    o = take(pool(status="delivered", eligible=(k % 2 == 0)))[0]
                    exp, diff = exp_dispute(o), "ordinary"
                else:
                    raise SystemExit(f"unhandled intent {intent}")

                uid = user_for(role, o)
                staff = role != "shopper"
                bank = {
                    "order_status": {"shopper": SHOPPER_STATUS, "merchant": MERCHANT_STATUS,
                                     "support": SUPPORT_STATUS}[role],
                    "find_order": {"shopper": SHOPPER_FIND, "merchant": MERCHANT_FIND,
                                   "support": SUPPORT_STATUS}[role],
                    "return_eligibility": STAFF_RETURN_ELIG if staff else RETURN_ELIG,
                    "return_deadline": STAFF_DEADLINE if staff else RETURN_DEADLINE,
                    "refund_request": SUPPORT_REFUND if staff else REFUND_REQ,
                    "cancel_order": STAFF_CANCEL if staff else CANCEL,
                    "restocking_fee": STAFF_RESTOCK if staff else RESTOCK_Q,
                    "dispute": STAFF_DISPUTE if staff else DISPUTE_Q,
                }[intent]
                msg = phrase(bank, f"{intent}:{role}", oid=o["id"],
                             prod=o["product_title"], store=o["store_name"])
                kind = {"return_eligibility": "return", "return_deadline": "return",
                        "refund_request": "refund", "cancel_order": "cancel",
                        "restocking_fee": "restock", "dispute": "dispute"}.get(intent, "none")
                add("coverage", role, uid, intent, state_of(o), policy_for(o, kind),
                    "several" if intent in ("refund_request", "cancel_order",
                                            "restocking_fee", "dispute") else "one_lookup",
                    diff, "allowed", msg, exp, turns,
                    order_id=o["id"], store_id=o["store_id"])


# A followup must make sense after the opening message, so each intent gets
# its own bank. A generic bank produces nonsense such as asking whether a
# product search "changes if the item was opened".
FOLLOWUPS = {
    "order_status": [
        "and can i still return it once it turns up",
        "whats the latest it should arrive",
        "is it too late to cancel that one",
        "ok, and was that the full order or just part of it",
    ],
    "return_eligibility": [
        "and how long does the refund take once i send it back",
        "does that change if ive already opened it",
        "who pays for the return postage",
        "what if the store says something different",
    ],
    "refund_request": [
        "how long till the money is back with me",
        "do i need to post it back before that goes through",
        "will i get the whole amount or is something taken off",
        "does someone have to approve that first",
    ],
    "product_search": [
        "whats the cheapest of those",
        "can you show me the same thing but under half that",
        "do any of those ship quickly",
        "is that everything you have or just the first few",
    ],
    "policy_question": [
        "does that apply to every store on here",
        "and what happens if the store says otherwise",
        "where can i read that for myself",
        "has that always been the rule",
    ],
}
SECOND_FOLLOWUP = [
    "ok so what happens next",
    "and roughly how long will that take",
    "right, can you just confirm that back to me",
]


def add_followups() -> None:
    """Promote some single-turn coverage records to two and three turns."""
    single = [r for r in records
              if r["scenario_group"] == "coverage" and r["tuple"]["turn_count"] == 1
              and r["tuple"]["intent"] in FOLLOWUPS]
    rng.shuffle(single)
    for i, r in enumerate(single[:28]):
        bank = FOLLOWUPS[r["tuple"]["intent"]]
        r["followups"] = [bank[i % len(bank)]]
        r["tuple"]["turn_count"] = 2
        r["tuple"]["tools_needed"] = "several"
    three_ok = [r for r in single[28:] if r["tuple"]["intent"] != "product_search"]
    for i, r in enumerate(three_ok[:7]):
        bank = FOLLOWUPS[r["tuple"]["intent"]]
        r["followups"] = [bank[(i + 2) % len(bank)],
                          SECOND_FOLLOWUP[i % len(SECOND_FOLLOWUP)]]
        r["tuple"]["turn_count"] = 3
        r["tuple"]["tools_needed"] = "several"


def main() -> None:
    build()
    add_followups()
    seen: set[tuple] = set()
    for r in records:
        key = tuple(m.strip().casefold() for m in [r["opening_message"], *r["followups"]])
        if key in seen:
            raise SystemExit(f"duplicate conversation at {r['id']}: {key[0][:60]}")
        seen.add(key)
    OUT.write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records),
        encoding="utf-8", newline="\n",
    )
    groups = {g: sum(1 for r in records if r["scenario_group"] == g)
              for g in ("coverage", "challenge")}
    print(f"wrote {len(records)} records to {OUT.relative_to(REPO_ROOT)}  {groups}")


if __name__ == "__main__":
    main()
