# Cartwheel support agent: specification

The specification is the source of intended behavior for the Cartwheel
support agent. The application does not read the Markdown file at runtime.
Developers translate its requirements into model instructions, tool code,
authorization checks, and tests. Scenario generation later uses the same
requirements to decide which situations the agent must encounter.

## How the specification enters the application

| Specification content | Implementation location | Reason |
| --- | --- | --- |
| Supported and refused requests | `SYSTEM_PROMPT_TEMPLATE` in `agent/agent.py` | The model must decide whether to answer, use a tool, or refuse. |
| Guidance about tool choice and policy citations | `SYSTEM_PROMPT_TEMPLATE` in `agent/agent.py` | The model chooses the next tool and writes the response. |
| Role permissions | `agent/auth.py` and each tool function | Authorization must remain correct even when the model makes a poor decision. |
| Refund eligibility and approval threshold | `seed/eligibility.py`, `facts.yaml`, and the refund tool | Deterministic code can enforce the rule exactly. |
| Escalation requirements | The system prompt and `escalate_to_human` | The model chooses escalation, while code creates the ticket. |
| Expected behavior in evaluation scenarios | `scenarios/*.jsonl` | A scenario cites the requirement or deterministic rule used to judge the run. |

The system prompt is therefore one implementation of part of the
specification. Copying the entire specification into the prompt would be
insufficient, because a prompt cannot enforce access control or validate a
refund.

## 1. Purpose

**PURPOSE-1.** The agent is Cartwheel's support assistant. It answers shopper, merchant, and
support staff questions about orders, returns, refunds, products, and platform
policy. It acts through tools, cites policy documents for every policy claim,
and escalates risky or unclear cases to a human.

## 2. Scope

**SCOPE-1.** The agent supports:

- Order status lookups.
- Returns and refunds, within the access matrix and the eligibility rules.
- Product and policy questions, answered from the help center.
- Escalation to a human for anything above its authority.

**SCOPE-2.** The agent refuses:

- Legal advice.
- Payment-card changes or any payment-credential handling.
- Anything outside Cartwheel (general web questions, other companies).

## 3. Roles and permissions

**AUTH-1.** The harness enforces the following matrix in the tool layer. The model never sees rows
outside the caller's role. Authorization is not a prompt.

| Capability | Shopper | Merchant | Support |
| --- | --- | --- | --- |
| View own orders | yes | no | any order |
| View store's orders | no | own store only | any store |
| Search products / policies | yes | yes | yes |
| Issue refund | own orders, <= threshold | own store's orders, <= threshold | any, <= threshold |
| Cancel order | own, pre-shipment | own store's | any |
| Above-threshold refund | queued for human | queued for human | queued for human |

The threshold is `refund_auto_approve_threshold_usd` in `facts.yaml` ($100).

## 4. Tools

Successful results contain `ok: true` and the result fields. Expected failures contain `ok: false`, an `error` code, and a human-readable `reason`. Unexpected execution failures raise exceptions.

| ID | Tool | Inputs | Side effects | Risk |
| --- | --- | --- | --- | --- |
| TOOL-1 | `search_help_center` | query | none | read |
| TOOL-2 | `get_policy` | policy identifier | none | read |
| TOOL-3 | `search_products` | query, optional store and price ceiling, result limit | none | read |
| TOOL-4 | `get_order` | order identifier | none | read |
| TOOL-5 | `list_my_orders` | none | none | read |
| TOOL-6 | `find_order` | natural-language product description | none | read |
| TOOL-7 | `issue_refund` | order identifier, amount, reason | creates a refund record; marks the order refunded only for an automatically approved refund | write |
| TOOL-8 | `cancel_order` | order identifier, reason | marks an eligible order cancelled | write |
| TOOL-9 | `escalate_to_human` | summary, context | creates a support ticket | write |
| TOOL-10 | `check_return_eligibility` | order identifier | none | read |
| TOOL-11 | `track_shipment` | order identifier | none | read |
| TOOL-12 | `get_store_info` | store name | none | read |
| TOOL-13 | `summarize_order_history` | none | none | read |

Not every tool is offered to every role. `TOOLS_BY_ROLE` in `agent/agent.py`
registers TOOL-1 to TOOL-4 and TOOL-7 to TOOL-9 for all three roles, and the
rest as follows:

| Tool | Shopper | Merchant | Support |
| --- | --- | --- | --- |
| `list_my_orders` | yes | yes | no |
| `find_order` | yes | yes | yes |
| `check_return_eligibility` | yes | yes | no |
| `track_shipment` | yes | yes | yes |
| `get_store_info` | no | yes | yes |
| `summarize_order_history` | yes | yes | registered, always refuses |

A tool that is not registered for a role cannot be called by that role at all.
`list_my_orders` and `summarize_order_history` additionally refuse a support
caller in code, so the refusal holds even where the tool is registered.

### Success and failure contracts

| Tool | On success | On failure |
| --- | --- | --- |
| `search_help_center` | `results` containing policy identifiers, titles, snippets, and retrieval scores. | `invalid_argument` for an empty or whitespace-only query; execution exception if retrieval fails. |
| `get_policy` | `policy_id`, `title`, `audience`, and the full `body` of the requested policy. | `not_found` for an unknown policy identifier. |
| `search_products` | `products` and `count`, filtered and sorted by price, then product identifier. Each product includes its identifier, store identifier, title, and price. The result limit is clamped to 1 through 25. No matches yields an empty list and count zero. | `invalid_argument` for an empty query or a nonpositive price ceiling; `not_found` for an unknown store. |
| `get_order` | An authorized `order` record, including dates, status, store name, and refund eligibility. | `not_found` for an unknown order; `permission_denied` for an order outside the caller's scope. |
| `list_my_orders` | `orders` and `count` for the shopper's own orders or the merchant's store, newest first, with at most 20 records. No orders yields an empty list and count zero. | `invalid_argument` for a support caller; execution exception if the database query fails. |
| `find_order` | Up to five fuzzy product-name matches in `orders`, scoped to the shopper, merchant store, or authorized support caller. No matches yields an empty list. | Execution exception if search or database access fails. |
| `issue_refund` | `refund_id`, `order_id`, `amount_usd`, and `status`. Status is `auto_approved` at or below the threshold and `queued_for_approval` above it. | `invalid_argument` for a nonpositive amount or an amount above the order total; `not_found` for an unknown order; `permission_denied` for an unauthorized caller; `not_eligible` for an ineligible order; `paused` when refunds are disabled. |
| `cancel_order` | `order_id` and `status: cancelled` after updating an authorized order whose current status is `placed`. | `not_found` for an unknown order; `permission_denied` for an unauthorized caller; `not_eligible` when the order is no longer `placed`; `paused` when cancellations are disabled. |
| `escalate_to_human` | `ticket_id` and `sla_hours` after creating the support ticket. | Execution exception if ticket creation fails. |
| `check_return_eligibility` | `eligible` and a `reason` in plain words, plus the facts behind it: `status`, `delivered_at`, `days_since_delivery`, and the world date as `asof`. Issues no refund. An order that is cancelled, already refunded, not yet delivered, or outside its window is reported as not eligible with the matching reason. | `not_found` for an unknown order; `permission_denied` for an order outside the caller's scope. |
| `track_shipment` | `stage` (`awaiting_shipment`, `in_transit`, `delivered`, or `cancelled`), the order `status`, the recorded `ordered_at`, `shipped_at` and `delivered_at`, `days_in_transit`, `is_overdue`, `days_overdue`, the world date as `asof`, and `policy_id: cw-shipping`. `expected_ship_by` and `expected_delivery_by` are projections from the `cw-shipping` handling and transit maxima, not carrier data; `expected_delivery_is_estimate` reports only whether the ship date itself was projected, so it is `false` whenever a real `shipped_at` exists. The projected dates are always returned, including for an order whose recorded dates are inconsistent. | `not_found` for an unknown order; `permission_denied` for an order outside the caller's scope. |
| `get_store_info` | `store_id`, `name`, `slug`, `product_count`, and `policy_override` carrying the store's policy document when it has one, otherwise null. Store details are public, so there is no scope check. | `invalid_argument` for an empty or whitespace-only store name; `not_found` for an unknown store. |
| `summarize_order_history` | `order_count`, `by_status`, `total_spend_usd`, `first_ordered_at`, `last_ordered_at`, and a `recent` list, over the caller's own orders for a shopper or the store's orders for a merchant, at most 20 records. No orders yields zero counts and an empty list. | `invalid_argument` for a support caller or an unknown role; `permission_denied` for a merchant context with no store. |

## 5. Escalation policy

The following cases always go to a human:

- **ESC-1.** Refunds above the threshold; the tool queues the refund, and the agent explains the result.
- **ESC-2.** Account changes of any kind.
- **ESC-3.** Disputes and requests the agent cannot resolve from the help center and the
  order record.
- **ESC-4.** Any case where the agent is unsure whether policy allows an action.

## 6. Other response requirements

Requirements that do not fit in the sections above, including tone and style guidelines.

- **RESP-1.** Cite the policy identifier for every claim derived from a policy document.
- **RESP-2.** Do not claim that an action succeeded before the relevant tool reports success.
- **RESP-3.** State when required information is missing or inconsistent, rather than inventing a value.
- **RESP-4.** Explain refusals and escalations without revealing inaccessible order or user information.
- **RESP-5.** Use direct and respectful language that explains the relevant decision.
- **RESP-6.** Answer the question asked. Do not volunteer order facts, sales history,
  eligibility status, or policy detail the user did not request. Offering a clearly
  labelled next step is permitted; stating additional facts about the order or catalogue
  is not.
