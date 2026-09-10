"""Homework 1: the remaining commerce-agent tools.

The three lecture tools (`search_help_center`, `get_order`, `issue_refund`)
are implemented in agent/agent.py and are worked examples of the pattern:
check permissions first, go through agent/db.py for data, and return a
structured dict, never a prose error. The homework tools follow the same
pattern. agent/agent.py already wraps each function below as an SDK tool, so
once a function works here it works in chat with no further wiring.

Result convention (see agent/auth.py):
  - Success: a dict with "ok": True plus the payload fields named in each
    docstring.
  - Failure: {"ok": False, "error": <code>, "reason": <human-readable str>}.

Run the contract tests with: uv run pytest tests/test_hw_holes.py -k hw1
They are marked xfail and flip to passing as you implement each function.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from agent import db
from agent.auth import AuthContext, can_cancel_order, can_view_order, permission_denied
from agent.config import load_facts
from agent.helpcenter import load_policy_docs
from agent.killswitch import kill_switch

from thefuzz import fuzz


MAX_SEARCH_LIMIT = 25
DEFAULT_ORDER_LIMIT = 20


MAX_FIND_RESULTS = 5
FUZZY_THRESHOLD = 70


def get_policy(ctx: AuthContext, policy_id: str) -> dict[str, Any]:
    """Fetch one policy doc by its exact id. Risk tier: read.

    Every role may read every policy doc (the corpus is public help-center
    content), so this tool needs no permission check.

    Args:
        ctx: The caller's auth context. Unused here, but every tool takes it.
        policy_id: An exact policy id, e.g. "cw-returns" or
            "store-juniper-home-goods-policy". Matching is exact and
            case-sensitive; ids are the `policy_id` front-matter field of the
            files in data/policies/.

    Returns:
        On success: {"ok": True, "policy_id": str, "title": str,
        "audience": str, "body": str} where body is the markdown body of the
        doc without the front matter.
        If no doc has that id: {"ok": False, "error": "not_found",
        "reason": ...} naming the id that was requested.

    Implementation notes:
        agent.helpcenter.load_policy_docs() returns every parsed doc.
    """
    for doc in load_policy_docs():
        if doc.policy_id == policy_id:
            return {
                "ok": True,
                "policy_id": doc.policy_id,
                "title": doc.title,
                "audience": doc.audience,
                "body": doc.body,
            }
    return {
        "ok": False,
        "error": "not_found",
        "reason": f"No policy doc with id {policy_id!r}.",
    }


def search_products(
    ctx: AuthContext,
    query: str,
    store: str | None = None,
    max_price_usd: float | None = None,
    limit: int = 5,
) -> dict[str, Any]:
    """Search the product catalog. Risk tier: read.

    Every role may search products. Matching is deterministic keyword
    matching, not semantic search: a product matches when every whitespace
    token of `query` appears case-insensitively as a substring of the
    product's title or description.

    Args:
        ctx: The caller's auth context.
        query: Free-text query. Must be non-empty after stripping whitespace;
            otherwise return {"ok": False, "error": "invalid_argument",
            "reason": ...}.
        store: Optional store filter. Matched with
            agent.db.get_store_by_name (case-insensitive name or slug). If
            given and no store matches, return {"ok": False, "error":
            "not_found", "reason": ...} naming the store string.
        max_price_usd: Optional inclusive price ceiling. If given and not
            strictly positive, return an "invalid_argument" error.
        limit: Maximum products to return. Clamp to the range
            [1, MAX_SEARCH_LIMIT]; do not error on out-of-range values.

    Returns:
        {"ok": True, "products": [...], "count": <len(products)>} where each
        product is {"product_id": int, "store_id": int, "title": str,
        "price_usd": float}. Sort matches by price_usd ascending, then by
        product_id ascending, and truncate to `limit`. No matches is still a
        success: {"ok": True, "products": [], "count": 0}.

    Implementation notes:
        agent.db.list_products(conn, store_id) gives the candidate set.
        Use `with db.connection() as conn:` to close the database automatically.
    """
    tokens = query.split()
    if not tokens:
        return {
            "ok": False,
            "error": "invalid_argument",
            "reason": "query must be non-empty.",
        }
    if max_price_usd is not None and max_price_usd <= 0:
        return {
            "ok": False,
            "error": "invalid_argument",
            "reason": f"max_price_usd must be strictly positive, got {max_price_usd}.",
        }

    limit = max(1, min(limit, MAX_SEARCH_LIMIT))
    lowered = [t.lower() for t in tokens]

    with db.connection() as conn:
        store_id = None
        if store is not None:
            matched = db.get_store_by_name(conn, store)
            if matched is None:
                return {
                    "ok": False,
                    "error": "not_found",
                    "reason": f"No store matching {store!r}.",
                }
            store_id = matched.id

        matches = []
        for p in db.list_products(conn, store_id):
            haystack = f"{p.title} {p.description}".lower()
            if all(t in haystack for t in lowered):
                if max_price_usd is not None and p.price_cents > round(
                    max_price_usd * 100
                ):
                    continue
                matches.append(p)

    matches.sort(key=lambda p: (p.price_cents, p.id))
    products = [
        {
            "product_id": p.id,
            "store_id": p.store_id,
            "title": p.title,
            "price_usd": p.price_cents / 100,
        }
        for p in matches[:limit]
    ]
    return {"ok": True, "products": products, "count": len(products)}


def list_my_orders(ctx: AuthContext) -> dict[str, Any]:
    """List recent orders in the caller's own scope. Risk tier: read.

    Role behavior, straight from the access matrix in SPEC.md:
        - shopper: the caller's own orders.
        - merchant: the caller's store's orders (ctx.store_id).
        - support: support staff have no orders of their own and look up
          specific orders with get_order instead, so return {"ok": False,
          "error": "invalid_argument", "reason": ...} saying exactly that.

    Returns:
        For shopper and merchant: {"ok": True, "orders": [...],
        "count": <len(orders)>} where each order is
        agent.db.Order.to_public_dict() and the list holds at most
        DEFAULT_ORDER_LIMIT orders, newest first (agent.db.list_orders_for_user
        and list_orders_for_store already sort and limit this way).

    Implementation notes:
        No permission check is needed beyond the role dispatch, because the
        scope is baked into which query you run. That is the point of the
        tool: the model cannot ask for someone else's orders through it.
    """
    if ctx.role == "support":
        return {
            "ok": False,
            "error": "invalid_argument",
            "reason": (
                "Support staff have no orders of their own; "
                "look up a specific order with get_order instead."
            ),
        }

    with db.connection() as conn:
        if ctx.role == "shopper":
            orders = db.list_orders_for_user(
                conn, ctx.user_id, limit=DEFAULT_ORDER_LIMIT
            )
        elif ctx.role == "merchant":
            orders = db.list_orders_for_store(
                conn, ctx.store_id, limit=DEFAULT_ORDER_LIMIT
            )
        else:
            return {
                "ok": False,
                "error": "invalid_argument",
                "reason": f"Unknown role {ctx.role!r}.",
            }
        public = [o.to_public_dict() for o in orders]

    return {"ok": True, "orders": public, "count": len(public)}


def cancel_order(ctx: AuthContext, order_id: int, reason: str) -> dict[str, Any]:
    """Cancel an order. Risk tier: write.

    This is the homework's write tool, and it must enforce two independent
    rules in this order:

    1. The access matrix (scope): use agent.auth.can_cancel_order. Shoppers
       may cancel only their own orders, merchants only their own store's
       orders, support any order. On failure return
       agent.auth.permission_denied(...) with a reason naming the role and
       the order id. Scope is checked before the status rule so that an
       out-of-scope caller learns nothing about the order's state.
    2. The pre-shipment rule (facts.yaml `cancel_cutoff`): only orders whose
       status is exactly "placed" can be cancelled, for every role. If the
       order is in scope but its status is not "placed", return
       {"ok": False, "error": "not_eligible", "reason": ...} that names the
       current status and states that orders can be cancelled only before
       shipment.

    Args:
        ctx: The caller's auth context.
        order_id: The order to cancel.
        reason: Free-text reason from the user; not validated.

    Returns:
        If no order has this id: {"ok": False, "error": "not_found",
        "reason": ...}.
        On success: {"ok": True, "order_id": order_id, "status": "cancelled"}
        after persisting the new status with agent.db.set_order_status.

    Implementation notes:
        Fetch with agent.db.get_order. Note the argument order of
        can_cancel_order(ctx, order_user_id, order_store_id).

    The Module 4 kill switch is checked first (before the scope and
    status rules and before your code), so that a paused write tool touches
    nothing. It is provided; the default ("off") returns None and falls
    through to your implementation.
    """
    paused = kill_switch("cancel_order")
    if paused is not None:
        return {"ok": False, "error": "paused", "reason": paused}
    with db.connection() as conn:
        order = db.get_order(conn, order_id)
        if order is None:
            return {
                "ok": False,
                "error": "not_found",
                "reason": f"No order with id {order_id}.",
            }

        if not can_cancel_order(ctx, order.user_id, order.store_id):
            return permission_denied(
                f"Role {ctx.role!r} may not cancel order {order_id}."
            )

        if order.status != "placed":
            return {
                "ok": False,
                "error": "not_eligible",
                "reason": (
                    f"Order {order_id} has status {order.status!r}; orders can be "
                    "cancelled only before shipment (status 'placed')."
                ),
            }

        db.set_order_status(conn, order_id, "cancelled")

    return {"ok": True, "order_id": order_id, "status": "cancelled"}


def find_order(ctx: AuthContext, query: str) -> dict[str, Any]:
    """Search the caller's orders by product name. Risk tier: read.

    Takes a natural-language query (e.g., "earmuffs I bought last week")
    and searches the authenticated user's orders for products whose name
    matches. Use fuzzy string matching (e.g., thefuzz.fuzz.partial_ratio
    or SQLite LIKE) to find orders whose product name is close to the
    query.

    Access rules: a shopper searches only the shopper's own orders, a
    merchant searches orders from the merchant's store, and support staff
    can search any orders. Use agent.db.list_orders_for_user for shoppers
    and agent.db.list_orders_for_store for merchants. For support staff,
    use agent.db.list_orders_for_user with no user filter, or search
    across all orders.

    Args:
        ctx: The caller's auth context.
        query: A natural-language description of the product.

    Returns:
        {"ok": True, "orders": [...]} with a list of matching orders
        (at most 5), each as the dict returned by agent.db. If no orders
        match, return {"ok": True, "orders": []}.
    """
    tokens = [t for t in query.lower().split() if len(t) > 2]
    if not tokens:
        return {
            "ok": False,
            "error": "invalid_argument",
            "reason": "query must contain at least one word of three or more characters.",
        }

    with db.connection() as conn:
        if ctx.role == "shopper":
            orders = db.list_orders_for_user(conn, ctx.user_id, limit=DEFAULT_ORDER_LIMIT)
        elif ctx.role == "merchant":
            if ctx.store_id is None:
                return permission_denied(
                    "Merchant context has no store_id; cannot scope an order search."
                )
            orders = db.list_orders_for_store(conn, ctx.store_id, limit=DEFAULT_ORDER_LIMIT)
        elif ctx.role == "support":
            return {
                "ok": False,
                "error": "invalid_argument",
                "reason": (
                    "Support staff have no orders of their own; "
                    "look up a specific order with get_order instead."
                ),
            }
        else:
            return {
                "ok": False,
                "error": "invalid_argument",
                "reason": f"Unknown role {ctx.role!r}.",
            }

        titles = _titles_for(conn, {o.product_id for o in orders})

        scored = []
        for order in orders:
            title = titles.get(order.product_id, "").lower()
            best = max((fuzz.partial_ratio(t, title) for t in tokens), default=0)
            if best >= FUZZY_THRESHOLD:
                scored.append((best, order))

        scored.sort(key=lambda pair: (-pair[0], -pair[1].id))
        matches = [o.to_public_dict() for _, o in scored[:MAX_FIND_RESULTS]]

    return {"ok": True, "orders": matches}


def _titles_for(conn, product_ids: set[int]) -> dict[int, str]:
    """Map product_id -> title for the given ids, in one query."""
    if not product_ids:
        return {}
    placeholders = ",".join("?" * len(product_ids))
    rows = conn.execute(
        f"SELECT id, title FROM products WHERE id IN ({placeholders})",
        tuple(product_ids),
    ).fetchall()
    return {row["id"]: row["title"] for row in rows}


# ---------------------------------------------------------------------------
# Additional tools (HW1 Part A). Gaps noticed while running conversations.
# Same convention as above: plain functions taking AuthContext, wrapped as SDK
# tools in agent/agent.py. Authorization is checked before anything is
# returned, and all date arithmetic uses the world's fixed today
# (db.world_asof), never the real clock.
# ---------------------------------------------------------------------------


def check_return_eligibility(ctx: AuthContext, order_id: int) -> dict[str, Any]:
    """Report whether an order can still be returned or refunded, and why.

    Returns "eligible" plus the facts behind it: current status, delivery date,
    and days elapsed since delivery. Performs no refund.
    """
    with db.connection() as conn:
        order = db.get_order(conn, order_id)
        if order is None:
            return {
                "ok": False,
                "error": "not_found",
                "reason": f"no order #{order_id}",
            }
        if not can_view_order(ctx, order.user_id, order.store_id):
            return permission_denied(
                f"role '{ctx.role}' (user {ctx.user_id}) may not view order #{order_id}"
            )
        today = db.world_asof(conn)

    days_since_delivery = (
        (today - order.delivered_at).days if order.delivered_at is not None else None
    )
    if order.status == "cancelled":
        eligible, why = False, "the order was cancelled; there is nothing to return"
    elif order.status == "refunded":
        eligible, why = False, "the order has already been refunded"
    elif order.delivered_at is None:
        eligible, why = False, (
            f"the order has status '{order.status}' and has not been delivered yet; "
            f"the return window starts at delivery"
        )
    elif not order.refund_eligible:
        eligible, why = False, (
            f"the order was delivered {days_since_delivery} days ago and is outside "
            f"the return window"
        )
    else:
        eligible, why = True, (
            f"the order was delivered {days_since_delivery} days ago and is inside "
            f"the return window"
        )

    return {
        "ok": True,
        "order_id": order_id,
        "eligible": eligible,
        "reason": why,
        "status": order.status,
        "delivered_at": order.delivered_at.isoformat() if order.delivered_at else None,
        "days_since_delivery": days_since_delivery,
        "asof": today.isoformat(),
    }


def track_shipment(ctx: AuthContext, order_id: int) -> dict[str, Any]:
    """Track a shipment: where the order is now, when it is expected, and if it is late.

    Reports the shipping milestones plus the expected ship-by and delivery-by
    dates derived from the Cartwheel shipping policy (cw-shipping), days in
    transit, and whether the shipment is overdue. Use this for "where is my
    order" and "is my order late"; use get_order for the order record itself.
    """
    with db.connection() as conn:
        order = db.get_order(conn, order_id)
        if order is None:
            return {
                "ok": False,
                "error": "not_found",
                "reason": f"no order #{order_id}",
            }
        if not can_view_order(ctx, order.user_id, order.store_id):
            return permission_denied(
                f"role '{ctx.role}' (user {ctx.user_id}) may not view order #{order_id}"
            )
        today = db.world_asof(conn)

    facts = load_facts()
    handling_days = facts["shipping_handling_days_max"]
    transit_days = facts["shipping_transit_days_max"]

    # Policy cw-shipping: stores ship within `handling_days` of purchase, and
    # standard delivery takes up to `transit_days` in transit after shipment.
    expected_ship_by = order.ordered_at + timedelta(days=handling_days)
    ship_basis = order.shipped_at or expected_ship_by
    expected_delivery_by = ship_basis + timedelta(days=transit_days)

    if order.status == "cancelled":
        stage = "cancelled"
    elif order.delivered_at is not None:
        stage = "delivered"
    elif order.shipped_at is not None:
        stage = "in_transit"
    else:
        stage = "awaiting_shipment"

    days_in_transit = None
    if order.shipped_at is not None:
        end = order.delivered_at or today
        days_in_transit = (end - order.shipped_at).days

    open_shipment = stage in {"awaiting_shipment", "in_transit"}
    is_overdue = open_shipment and today > expected_delivery_by
    days_overdue = (today - expected_delivery_by).days if is_overdue else 0

    return {
        "ok": True,
        "order_id": order_id,
        "stage": stage,
        "status": order.status,
        "ordered_at": order.ordered_at.isoformat() if order.ordered_at else None,
        "shipped_at": order.shipped_at.isoformat() if order.shipped_at else None,
        "delivered_at": order.delivered_at.isoformat() if order.delivered_at else None,
        "expected_ship_by": expected_ship_by.isoformat(),
        "expected_delivery_by": expected_delivery_by.isoformat(),
        "expected_delivery_is_estimate": order.shipped_at is None,
        "days_in_transit": days_in_transit,
        "is_overdue": is_overdue,
        "days_overdue": days_overdue,
        "asof": today.isoformat(),
        "policy_id": "cw-shipping",
    }


def get_store_info(ctx: AuthContext, store: str) -> dict[str, Any]:
    """Public details for one store, plus its store-specific policy override if any.

    Store information is public to every role, so there is no scope check here.
    """
    if not store or not store.strip():
        return {
            "ok": False,
            "error": "invalid_argument",
            "reason": "store name must not be empty",
        }
    with db.connection() as conn:
        found = db.get_store_by_name(conn, store.strip())
        if found is None:
            return {
                "ok": False,
                "error": "not_found",
                "reason": f"no store named '{store}'",
            }
        product_count = len(db.list_products(conn, found.id))

    override = None
    for doc in load_policy_docs():
        if doc.policy_id == f"store-{found.slug}-policy":
            override = {
                "policy_id": doc.policy_id,
                "title": doc.title,
                "body": doc.body,
            }
            break

    return {
        "ok": True,
        "store_id": found.id,
        "name": found.name,
        "slug": found.slug,
        "product_count": product_count,
        "policy_override": override,
    }


def summarize_order_history(ctx: AuthContext) -> dict[str, Any]:
    """Summarize the caller's own recent orders: counts by status, spend, date range.

    Shoppers see their own orders, merchants their store's. Support callers have
    no orders of their own and should look up a specific order instead.
    """
    if ctx.role == "support":
        return {
            "ok": False,
            "error": "invalid_argument",
            "reason": (
                "support staff have no orders of their own; "
                "look up a specific order with get_order instead"
            ),
        }
    if ctx.role == "merchant" and ctx.store_id is None:
        return permission_denied("merchant context has no store_id; cannot scope a summary")
    if ctx.role not in {"shopper", "merchant"}:
        return {
            "ok": False,
            "error": "invalid_argument",
            "reason": f"unknown role '{ctx.role}'",
        }

    with db.connection() as conn:
        if ctx.role == "shopper":
            orders = db.list_orders_for_user(conn, ctx.user_id, limit=DEFAULT_ORDER_LIMIT)
        else:
            orders = db.list_orders_for_store(conn, ctx.store_id, limit=DEFAULT_ORDER_LIMIT)
        titles = _titles_for(conn, {o.product_id for o in orders})

    if not orders:
        return {
            "ok": True,
            "order_count": 0,
            "by_status": {},
            "total_spend_usd": 0.0,
            "first_ordered_at": None,
            "last_ordered_at": None,
            "recent": [],
        }

    by_status: dict[str, int] = {}
    for o in orders:
        by_status[o.status] = by_status.get(o.status, 0) + 1
    dates = [o.ordered_at for o in orders]

    return {
        "ok": True,
        "order_count": len(orders),
        "by_status": by_status,
        "total_spend_usd": round(sum(o.total_usd for o in orders), 2),
        "first_ordered_at": min(dates).isoformat(),
        "last_ordered_at": max(dates).isoformat(),
        "recent": [
            {
                "order_id": o.id,
                "title": titles.get(o.product_id),
                "status": o.status,
                "ordered_at": o.ordered_at.isoformat(),
                "total_usd": o.total_usd,
            }
            for o in orders[:5]
        ],
    }
