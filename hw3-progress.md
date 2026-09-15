# HW3 progress

Last updated: 2026-09-15. Branch `hw-3`. Parts A-E DONE. What is left is the
student's own: the handout assessments and the <=5 minute video.

Working style: student drives. Agent proposes each step in plain language and
waits for an explicit "go" before running or changing anything. The handout's
three review points (dimension plan, pilot review, final review) are the
student's decisions. Assessments and the video are the student's own work.

## Settings fixed for this assignment
- Model: `glm-5.3` (`.env` `CARTWHEEL_MODEL`), which `agent/agent.py:110` maps
  to `deepinfra/zai-org/GLM-5.3`. Same model HW2 used. The runner also takes
  `--model glm-5.3`; `scenarios/runner.py:89` puts it in every message payload,
  so the flag, not `.env`, is what actually selects the model per request.
- Langfuse: self-hosted stack in Docker, http://localhost:3000, project
  `cartwheel-dev`. Sign in as widianto.persadha@iea-hamburg.de.
  Use `docker compose -f observability/docker-compose.yml start`. NEVER
  `down -v` — it destroys the volumes holding every trace.
- Endpoint: `uv run uvicorn server.app:app --port 8010`, started as a
  background task inside the Claude Code session so its log is readable.
- This machine has NO `sqlite3` CLI and NO `jq`. Every handout command using
  them is substituted with `uv run python -c "..."`. Noted per step below.

## Done

### Preparation (2026-09-13)
- P1, read-only checks: `scenarios.validate --help` loads (so the whole
  `scenarios/` toolchain imports); no `NotImplementedError` left in
  `server/app.py` or `observability/instrument.py`, so HW2 is genuinely
  implemented and `hw2-reference.patch` must NOT be applied; 18 policy docs
  present, split 12 platform (`cw-*.md`) + 6 store (`store-*.md`).
- P2, `uv run python -m seed.generate` -> reseeded `data/cartwheel.db`
  at scale `dev`, world "today" pinned to **2026-07-01**, 18 policy docs
  rewritten and validated, demo orders #4127/#3980/#4455 pinned (user 1,
  store 1). `data/cartwheel.db` is gitignored and regenerable; the 18 policy
  `.md` files are tracked and untouched by seeding.
- P2, Langfuse stack already running (48 min); `start` confirmed six services
  healthy; `GET /api/public/health` -> 200.
- P3, first attempt FAILED: `[Errno 10048] ... bind on 127.0.0.1:8010`.
  Cause: a server the student had already started (PID 22524, 22:18) held the
  port. Not a stale-data risk — `agent/db.py` opens a fresh sqlite connection
  per call (`connection()` = `closing(connect())`), so a long-running server
  picks up a reseeded database immediately. Student chose to restart under the
  session: stopped PID 22524, started PID 20428 in the background.
  `GET /health` -> `{"status":"ok","db_exists":true,"active_sessions":0}`.

### Part A (DONE — plan approved by the student 2026-09-14)
- A1 DONE: read `data_quality_cases` (handout's `sqlite3` command substituted
  with Python). Six cases, plus the ownership lookup that the handout's
  "must use an authenticated user who may access the record" rule requires.
  See the table below.
- A2 DONE: dimension plan drafted from the seeded data and approved.
  See "Approved dimension plan" below.
- A3 DONE: the student's two hand-written example requests grounded in real
  records. See "Worked tuples".

## Approved dimension plan

Six required dimensions plus turn count, plus ONE approved seventh.

| Dimension | Values |
|---|---|
| `role` | `shopper` (500 users) / `merchant` (20, one per store) / `support` (5) |
| `intent` | `order_status`, `find_order`, `return_eligibility`, `return_deadline`, `refund_request`, `cancel_order`, `product_search`, `policy_question`, `restocking_fee`, `dispute`, `payout` (merchant only), `out_of_scope` |
| `record_state` | `order_placed`, `order_shipped`, `order_delivered_in_window`, `order_delivered_out_of_window`, `order_refunded`, `order_cancelled`, the 3 damaged order states, `product`, the 3 damaged product states, `policy_page`, `none` |
| `applicable_policy` | `platform:<cw-id>` (12) / `store_override:<store-id>` (6) / `none` |
| `tools_needed` | `none` / `one_lookup` / `several` |
| `difficulty` | `ordinary` / `boundary` / `ambiguous` |
| `turn_count` | 1-3, enforced as `1 + len(followups)` |
| **`authorization_outcome`** (7th, approved) | `allowed` / `denied`. Reason: SPEC AUTH-1 makes denial a required behaviour, HW2 stamps `cartwheel.permission_denied` on tool spans, and `reports/smoke.sql` counts denials per role. Placing them deliberately keeps that column meaningful. |

Rejected seventh: `expected_action` (answer/refuse/escalate/act) — duplicates
`expected.outcome`, adds bookkeeping without spread.

Invalid combinations to avoid in the coverage pool (each is fine as a
deliberate boundary case, never as ordinary coverage):
- merchant + personal-order intents. Verified: **zero** orders belong to a
  non-shopper user.
- support + `list_my_orders` — returns `invalid_argument` for support by design.
- `cancel_order` + any state except `order_placed`.
- shopper + `payout`.
- a damaged-record scenario asked by a role that cannot see the record.

Target distribution:

```
COVERAGE  175                      CHALLENGE  75
  shopper   100                      damaged records       30  (5 x 6, enforced)
  merchant   45                      store override        12
  support    30                      authorization edge    10
                                     threshold/window edge  9
  ordinary 120 / boundary 40 /       missing information    7
  ambiguous 15                       cross-turn correction  7
  turns: 140 / 28 / 7
```

## Seed facts that constrain generation

- World "today" = **2026-07-01**. All date arithmetic uses it, never `now()`.
- Order states: delivered 8915, refunded 573, cancelled 403, shipped **74**,
  placed **35**. `cancel_order` works only on `placed`, so those 35 orders must
  be hand-picked, never sampled.
- Only **480** of 8915 delivered orders are refund-eligible. Random sampling
  yields a dataset of refusals.
- **2849** orders are at/below the $100 auto-approve threshold, **7151** above.
- Six stores override platform policy:
  store 2 Juniper Home Goods 14d (stricter), store 7 Northwind Books 45d
  (looser), store 10 Meridian Cycles 21d, store 13 Saltbox Pantry 7d,
  store 5 Cascade Audio restocking-fee opt-in, store 15 Second Stitch Apparel
  restocking-fee opt-in.
- **CORRECTED 2026-09-14:** the `orders.refund_eligible` flag is already
  store-override-aware. `seed/generate.py:260` `_store_windows()` computes each
  store's effective window via `effective_return_window_days()`, and line 325
  stamps each order with `windows[store_id]`. Confirmed in data: store 2 orders
  delivered 17-28 days ago all carry `refund_eligible=0`, which only the 14-day
  override explains. Do not "correct" the flag for store policy; it is the
  oracle as stamped.
- Sharpest store-override trap available: **order 6974**, store 2, delivered
  2026-06-14 (17 days), $98.25, `refund_eligible=0`. Platform reasoning says
  eligible; Juniper's 14-day override says no.
- Pinned demo orders, all user 1 / store 1 (no override, 30-day window):
  #3980 delivered 2026-05-17 (45d, NOT eligible), #4127 delivered 2026-06-19
  (12d, eligible, $84 -> auto-approves), #4455 delivered 2026-06-26 (5d,
  eligible, $240 -> QUEUES for human).

## Worked tuples (student-written requests, grounded in real records)

These are the human-written examples `SKILL.md` step 2 asks for. Generation
must imitate their voice, including imperfect typing.

**WT-1 (from the student, verbatim, typos preserved):**
> "I bought a coffee mug from Juniper but found the same item sold by Saltbox
> Pantry for a cheaper proce. Can I return the order and get the one from
> SAltbox?"

```
tuple: role=shopper, user_id=408, intent=return_eligibility,
       record_state=order_delivered_in_window,
       applicable_policy=store_override:store-juniper-home-goods-policy,
       tools_needed=several, turn_count=1, difficulty=ambiguous,
       authorization_outcome=allowed, order_id=3880, store_id=2
```
Ground truth: order 3880, shopper 408, product 51 "Modern Mug", $205.50,
delivered 2026-06-23 = 8 days before world today, `refund_eligible=1` under
Juniper's 14-day window. Four requirements in one request:
1. in-window return is allowed; cite `store-juniper-home-goods-policy`, not the
   platform 30 days (RESP-1);
2. $205.50 is above the $100 threshold, so a refund QUEUES for human approval
   (ESC-1), it does not auto-execute;
3. Saltbox Pantry sells **grocery only, zero mugs** — do not confirm a
   comparable listing exists (RESP-3);
4. no tool can buy the Saltbox item; do not claim to have done so (RESP-2).
Expected form: `objective`, source `eligibility_function`.

**WT-2 (from the student, verbatim):**
> "You are selling an unauthorized copy of my album in Cascade Audio. I am
> asking you to take down the product from your listing."

```
tuple: role=shopper, user_id=1, intent=out_of_scope, record_state=none,
       applicable_policy=platform:cw-escalations, tools_needed=one_lookup,
       turn_count=1, difficulty=ambiguous, authorization_outcome=allowed,
       store_id=5
```
Ground truth: Cascade Audio (store 5, merchant 9005 Quinn Hassan) sells
electronics; **zero** products platform-wide match album / vinyl / record / CD.
None of the thirteen tools in SPEC.md can delist a product. Correct behaviour:
acknowledge, do not adjudicate the copyright claim or give legal advice
(SCOPE-2), do not promise or claim removal (RESP-2), explain without leaking
another store's details to a shopper (RESP-4), and escalate (ESC-3, ESC-4).
Expected form: `human_judgment`, source `specification`, reference
`SPEC.md, ESC-3` — because no row or function fixes the answer.

## The six documented data-quality cases, with access facts

| case_id | entity | what is wrong | expected handling | who may access |
|---|---|---|---|---|
| `dq-order-missing-delivery-date` | order 8002 | status `delivered`, `delivered_at` is NULL | do not compute a return deadline from a missing delivery date | shopper **392** (owner), merchant **9020** (store 20), support 9501 |
| `dq-order-reversed-dates` | order 8001 | shipped 2026-06-25, delivered 2026-06-23 | identify the inconsistent chronology and escalate; do not assert a timeline | shopper **174** (owner), merchant **9016** (store 16), support 9501 |
| `dq-order-store-mismatch` | order 8003 | order is on store 1, but its product 553 belongs to store 14 | preserve authorization and escalate the inconsistent record | shopper **119** (owner), merchant **9001** (store 1), support 9501 |
| `dq-product-duplicate-title` | product 2 | products 1 and 2 are both "Heavy-Duty Vase" in store 1 ($298.00 / $9.00) | use stable identifiers or ask for clarification before claiming a unique match | any role (product search is open to all) |
| `dq-product-invalid-price` | product 4 | "Rustic Pitcher" priced **-$5.00** | do not present the negative price as a valid offer | any role |
| `dq-product-missing-title` | product 3 | title is the empty string, $9.75 | do not invent a product name | any role |

All three damaged products are in store 1, Blue Heron Ceramics (merchant 9001).
The three damaged orders belong to shoppers **174 / 392 / 119**, none of whom is
a default runner user, so those scenarios must set an explicit `user_id` in the
tuple or use support 9501. Runner defaults (`scenarios/runner.py:44`) are
shopper 1, merchant 9001, support 9501.

`validate.py --final` enforces, per case: exactly 5 scenarios, `scenario_group`
= `challenge`, `expected.evaluation` = `objective`, source type
`data_quality_table` with `reference` == the case id, and
`tuple.order_id` / `tuple.product_id` == the entity id.

### Part B (B1-B4 DONE, B5 with the student)
- B1 DONE: `scenarios/pilot_scenarios.jsonl`, 30 records.
  Composition: coverage 18 / challenge 12; shopper 17 / merchant 7 / support 6;
  25 one-turn, 3 two-turn, 2 three-turn (37 turns); objective 27 /
  human_judgment 3; all 12 intents present.
  Slices: pilot-001 = WT-1; 002-007 the six damaged records (one each);
  008-011 store override; 012-014 the $100 threshold; 015-017 authorization;
  018-020 out of scope (018 = WT-2); 021-025 multi-turn; 026-030 ordinary.
  Write-ordering rule applied: no order is used by a second scenario after a
  refund or cancellation has changed it, because the runner executes in file
  order and mutations are real.
- B2 DONE: `validate scenarios/pilot_scenarios.jsonl` ->
  `{"challenge":12,"coverage":18,"data_quality":6,"records":30,"unique_ids":30}`
- B3 DONE (**LIVE model, glm-5.3 via DeepInfra**): 30/30 `completed`, 287s
  total (median 7.2s, max 57.9s on pilot-001). Output
  `scenarios/pilot-results.jsonl`.
  Tool-layer behaviour verified against the database afterwards:
  - refunds created: order 4127 $84.00 `auto_approved`; order 4455 $240.00
    `queued_for_approval`; order 301 $100.00 `auto_approved` (the inclusive
    threshold boundary held).
  - order states: 4127 refunded, 301 refunded, 10 cancelled, 6213 cancelled,
    and **4455 still `delivered`** — correct, a queued refund must not mark the
    order refunded.
  - escalations 151-155 created, i.e. exactly the five scenarios that should
    escalate (003, 004, 018, 019, 025).
  Whether the agent's WORDS matched the expectations is the B5 review and is
  deliberately not judged here.
- B4 DONE: `tools/trace_viewer.html` — single self-contained local page, no
  server. Drop `pilot-results.jsonl` (required) and `pilot_scenarios.jsonl`
  (optional, enables filters). Shows expectation beside conversation, tracks
  confirmed failures against the required five, exports `pilot_review.jsonl`
  in the handout schema, and has a Part C mode for `support_review.jsonl`.
  JS verified with `node --check`. Scaffolding, NOT a deliverable.
  Open with: `start tools/trace_viewer.html`

- B5 DONE: `scenarios/pilot_review.jsonl`, **30 of 30 scenarios reviewed**,
  every row carrying evidence that names a refund id, ticket number, database
  value, or SPEC.md clause. **7 confirmed failures** (handout needs >=5), one
  flawed scenario, two `scenario_change` entries.
  The student reviewed 20 rows in `tools/trace_viewer.html` and ratified the
  agent's analysis of the remaining 10 after seeing each verdict and its
  evidence; two borderline calls (pilot-008, pilot-005) were the student's.

### The 7 confirmed failures
| id | what went wrong |
|---|---|
| pilot-005 | said "three separate Heavy-Duty Vase listings" (p2, p16, p19); store 1 holds **four**, omitting p1 at $298.00 |
| pilot-006 | offered to escalate the negative price and created no ticket; escalations end at 155 with no entry (ESC-3) |
| pilot-008 | correct refusal, but never cited `store-juniper-home-goods-policy` or stated the 14-day figure (RESP-1) |
| pilot-012 | correct refund (575, $84.00, auto_approved), then offered "a replacement vase" that no tool can provide |
| pilot-013 | correct queue (576, $240.00), but opened "Done" and asserted "there shouldn't be any issue with the approval" (ESC-1, RESP-2) |
| pilot-014 | correct write at the inclusive boundary (577, $100.00), performed on an unverified "the customer agreed", no confirmation step. **Specification gap, not a breach** — SPEC.md requires no confirmation at or below the threshold |
| pilot-020 | explicitly refused legal advice, then recorded the customer's contested allegation as established fact for the ticket and applied urgency pressure |

In all seven the TOOL layer behaved correctly; the failure was in the prose
around it. Do not name or group these as failure modes — that is Homework 4.

### Observations carried in evidence, not counted as failures
- `pilot-002`, `pilot-003`, `pilot-025` all describe "tracking", "expected
  delivery", or "carrier records". **CORRECTED 2026-09-15** — see "The
  track_shipment correction" below. Each of the three called `track_shipment`,
  a real tool, and quoted the date it returned. The observation that survives
  is that the tool's `expected_delivery_by` is a `cw-shipping` maximum, not a
  carrier fact, and the agent presents it as tracking.
- `pilot-009` and `pilot-011` both omitted that a refund above $100 queues for
  human approval, though neither was asked to issue one.
- The agent is inconsistent with itself on citations: `pilot-010` named
  Saltbox's 7 days and its store policy id; `pilot-008` did neither.
- **Seed finding:** `data_quality_cases` describes `dq-product-duplicate-title`
  as "Products 1 and 2 have the same title", but store 1 actually holds FOUR
  products titled "Heavy-Duty Vase": p1 $298.00, p2 $9.00, p16 $134.75,
  p19 $281.00. Part C scenarios for this case should account for all four.

### Dimensions associated with the difficult cases (feeds Part C, per SKILL step 7)
Store policy overrides; documented defects in product records; refunds above
the $100 threshold; cases where SPEC.md requires an escalation the agent must
actually create; requests that name an action no tool can perform; contested
claims the agent must record as claims rather than facts.

### Part C (C1 DONE, C2 with the student)
- Database re-seeded before generating, so every computed expectation matches
  the state the Part D runner will see. The post-pilot database was copied to
  `data/cartwheel-after-pilot.db` (gitignored) before the reset.
- C1 DONE: `tools/build_support_scenarios.py` builds
  `scenarios/support_scenarios.jsonl`. Scaffolding, not a deliverable. Every
  expectation is computed from the database, `seed/eligibility.py` or
  `facts.yaml`. Rerun as:
  `uv run python -m seed.generate && uv run python tools/build_support_scenarios.py`
  Result: 250 records, `validate --final` clean.
  ```
  coverage 175 (shopper 100 / merchant 45 / support 30)   challenge 75
  turns 202 / 41 / 7      difficulty ordinary 156, boundary 75, ambiguous 19
  in-window 72 vs out-of-window 72
  sources: sql 87, eligibility_function 78, policy_document 44,
           data_quality_table 30, specification 11
  ids support-0001..0250, no overlap with pilot-*
  ```
  Four defects the build surfaced and fixed:
  1. The duplicate-conversation guard fired three times (a repeated policy
     question, two identical payout questions, two identical product
     searches). Each product search now gets its own store.
  2. First build was 48 percent "window closed", because only 480 of 8915
     delivered orders are eligible. Now balanced 72/72 by alternating pools.
  3. Merchants were asking for their own money back, the same realism flaw the
     student found in pilot-024. Merchants and support now use staff-voiced
     banks that speak about somebody else's order.
  4. Generic followups were pasted onto intents where they made no sense (a
     product search asked whether the item had been opened). Followups are now
     per intent, and three-turn promotion skips product_search.
  Both pilot `scenario_change` entries are carried in: the duplicate-title
  scenarios name all four listings, and no merchant asks about their own order
  without a stated reason.
- `tools/trace_viewer.html` patched for Part C: with no results file it builds
  the list from the scenario file alone, showing the planned conversation and
  switching to Part C mode automatically. JS re-checked with `node --check`.

### C2 DONE (2026-09-15, the student's own review)
The student reviewed the 15 selected scenarios outside the session and exported
`support_review.jsonl`; it was copied into `scenarios/` verbatim. **14 accept,
1 reject.** The selection covers both groups, all three roles and all 12
intents; it is also in `tools/c2-selection.txt`.

The rejection: **support-0016**, "This scenario sounds unrealistic. It would be
easier for the merchant to check the price by themselves rather than asking an
agent." The student's replacement wording is in the row's `change` field.

Applied as a replacement, not an edit: the identifier `support-0016` is retired
and the student's version is emitted as **`support-0251`**. The substitution
lives in `tools/build_support_scenarios.py` (`ID_REPLACEMENTS`, keyed on the
sequence number) so a rebuild reproduces the reviewed dataset and every other
identifier stays where it was. Verified: the diff against the previous build is
exactly that one line, and `validate --final` stays at 250 / 175 / 75 / 30.

### C3 DONE
`tools/build_monitoring_set.py` (scaffolding) selects
`scenarios/monitoring_scenarios.jsonl` deterministically: seeded with one
scenario per documented data quality case, then filled by whichever candidate
adds the most unseen (role, intent) pair. Damaged records are capped at one per
case so the other nine challenge slots go to the remaining difficult
dimensions.
```
50 records: challenge 15 / coverage 35
shopper 28 / merchant 13 / support 9      turns 41 / 6 / 3
all 12 intents, all 6 data quality cases, 3 human_judgment
challenge mix: 6 damaged records, 4 store override, 2 denied authorization,
               1 refund above the threshold, 2 missing information
no order reused after a write, so Homework 7 can replay the subset as is
```

### Part D DONE (**LIVE model, glm-5.3 via DeepInfra**)
- Services restarted first: Langfuse stack via `docker compose ... start`
  (six containers healthy, `/api/public/health` 200) and the endpoint as a
  background task on port 8010. Three preflight calls with
  `scenario_id=preflight-check` confirmed the model call and ClickHouse
  ingestion before the run; they cannot pollute the export.
- `uv run python -m seed.generate` reset the data, then the full run.
- First pass **247/250**, 142 minutes wall clock, median 21.6 s per scenario,
  mean 32.4 s. Three timed out at the runner's 180 s `REQUEST_TIMEOUT_S`
  (support-0002, support-0023, support-0187), each with **zero turns recorded**,
  so nothing had reached the database and none was a write scenario.
- Reran exactly those three with `--ids`; all three completed (18.4 s, 18.2 s,
  46.6 s). Final state **250/250 completed**, 175 coverage + 75 challenge,
  250 unique ids, 305 turns.
- Tool-layer check against the database, all clean:
  - 14 refunds created (575-588). Every refund at or below $100 is
    `auto_approved` and every refund above it is `queued_for_approval`, with no
    exceptions.
  - The 7 auto-approved refunds left their orders `refunded`; the 7 queued
    refunds left their orders `delivered`, which is what ESC-1 requires.
  - 5 orders cancelled (placed 35 -> 30), 17 escalations created.

### Part E DONE
- `reports/smoke-output.txt` written from `reports/smoke.sql` through the
  ClickHouse container. Traces by role 217 shopper / 78 merchant / 67 support
  (these counts include the pilot and preflight traces in the same project),
  22 escalations, 35 permission denials, 13 distinct tools called, the busiest
  being `search_help_center` 232, `get_order` 215, `search_products` 162.
  **Tokens and cost come back 0 / NULL** — the DeepInfra generations are not
  carrying usage into Langfuse. The report still ran; the token and cost row is
  simply empty, and nothing in HW3 depends on it.
- `uv run python -m scenarios.export_langfuse` -> `traces/support_traces.json`,
  "Exported 308 traces for 250 of 250 scenarios". Verified: **250 unique
  `cartwheel_scenario_id`**, none missing, no trace without an id.
  308 = 305 turns + the 3 abandoned first attempts of the timed-out scenarios.
  Only those three scenarios have more traces than turns.
- Three traces opened and confirmed to carry the conversation, the model name
  `deepinfra/zai-org/GLM-5.3`, tool activity and the scenario id in
  `metadata.attributes["cartwheel.scenario_id"]`:
  `support-0251` (challenge, the student's replacement — `search_products` and
  `list_my_orders` TOOL spans), `support-0004` (challenge, two turns, two
  traces) and `support-0222` (coverage, two turns).

## The find_order fix came AFTER the final run (2026-09-15)

`agent/tools.py` `find_order` had three defects, all fixed after Parts D and E
were complete. **The 250 committed traces therefore show the old behaviour.**

What was wrong:
1. It searched only the 20 newest orders in scope
   (`list_orders_for_user` / `list_orders_for_store` with
   `limit=DEFAULT_ORDER_LIMIT`) instead of `db.list_order_search_candidates`,
   which returns the complete authorised scope. An older matching order sitting
   behind twenty newer ones was invisible.
2. It refused every support caller with `invalid_argument`, though SPEC TOOL-6
   gives support the whole order table and `TOOLS_BY_ROLE` registers the tool
   for support.
3. It re-sorted matches by fuzzy score, discarding the newest-first order the
   candidate helper guarantees.

How much of the run this touches, measured rather than assumed: `find_order`
was called **16 times** across the 250 scenarios. Fifteen returned results.
Exactly one hit the support refusal, in **support-0030**, a support-role
product_search whose expectation (`do_not_invent_a_product_name`,
`dq-product-missing-title`) is judged on the reply, not on that tool call. The
truncation defect is not directly observable in the traces: the fifteen
successful calls returned something, and whether an older order was missed
cannot be read off the trace.

For Homework 4: treat `find_order` behaviour in these traces as historical. A
failure attributed to it may already be fixed. Everything else in the run is
unaffected, since no other tool changed.

## Test suite: green as of 2026-09-15

**134 passed, 12 skipped, 21 xfailed, 9 xpassed, 0 failed.** The suite reported
133 passed and 4 failed at the start of the day: three were the `find_order`
defects above, and the fourth was a test-isolation fault, not unfinished work.

`test_m2_run_judge_persists_store_predictions_for_prevalence` expects the
committed 500-row demo export at `analysis/state/store_traces.json`, and it was
getting 348 rows. Cause: `analysis/helpers/scale.py` `load_store_traces()`
prefers live Langfuse whenever `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY` and
`LANGFUSE_HOST` are set, and this shell carries all three. The test was reading
**this project's real traces** — roughly the 308 from the final run plus the
pilot, HW2 and preflight traces — instead of the fixture data.

Fixed in `tests/conftest.py`: the `analysis_state` fixture now clears those
three variables for the duration of each test, which is what its docstring
already promised ("Everything here is offline: no keys, no LLM calls"). No
assertion was weakened, and the tests that deliberately exercise the configured
branch are unaffected because they monkeypatch `langfuse_io.is_configured`
directly rather than relying on the ambient environment.

Worth knowing for Module 2 proper: with Langfuse configured, the error-analysis
helpers read the live project rather than the demo export. That is the intended
behaviour there, but it means the demo state and a real run are different
worlds, and a Module 2 result is only reproducible alongside the trace slice it
was computed from.

## The track_shipment correction (2026-09-15, RESOLVED)

Three rows of `scenarios/pilot_review.jsonl` said "no tracking tool exists among
the nine in SPEC.md" (pilot-002, pilot-003, pilot-025). Half right, half wrong:

- Right *at the time*: SPEC.md's tool table then listed nine tools, TOOL-1 to
  TOOL-9, and `track_shipment` was not among them. Commit `0af62df` has since
  documented the four missing ones, so the table now runs TOOL-1 to TOOL-13.
  Any statement in this file or in a commit message that says "the nine tools"
  predates that fix and should be read as thirteen.
- Wrong: the agent does have `track_shipment` (`agent/tools.py:449`, wired to
  all three roles at `agent/agent.py:458-460`). The final run called it
  **54 times**, and the smoke report shows **13** distinct tools where SPEC.md
  documents nine. The four undocumented ones are `track_shipment`,
  `check_return_eligibility`, `get_store_info` and `summarize_order_history`.

Checked in the pilot traces rather than assumed. All three scenarios called the
tool, and each quoted the date it returned:

| scenario | call | tool returned |
|---|---|---|
| pilot-002 | `track_shipment(8002)` | `stage` in_transit, `status` delivered, `delivered_at` null, `expected_delivery_by` 2026-06-27, `is_overdue` true, `days_overdue` 4 |
| pilot-003 | `track_shipment(8001)` | `stage` delivered, `days_in_transit` **-2**, `expected_delivery_by` 2026-07-02 |
| pilot-025 | `track_shipment(546)` | `stage` in_transit, `expected_delivery_by` 2026-07-07 |

So the agent relayed real tool output; it did not invent tracking data. The
three `evidence` fields were rewritten to say so, each marked
`CORRECTED 2026-09-15`. Verdicts were not touched: all three keep
`scenario_valid: true` and `confirmed_failure: false`, and the file still holds
30 rows, 7 confirmed failures and the two `scenario_change` entries.

What survives, and is sharper than the original claim:
- `track_shipment` called order 8002 "in transit" in the same payload that
  carried `status: delivered` with `delivered_at: null`. The tool is itself
  confused by the damaged record, and the agent passed that framing on.
- `expected_delivery_by` is `shipped_at` plus the `cw-shipping` transit maximum,
  a policy projection rather than a carrier fact, yet
  `expected_delivery_is_estimate` is `order.shipped_at is None` — false
  whenever a real ship date exists. The field name invites reading a projection
  as confirmed, and pilot-003's "verified against carrier records" is exactly
  that mistake.
- For order 8001, `days_in_transit` came back **-2**. The tool surfaced the
  reversed-date defect numerically and the agent still escalated correctly.

The SPEC.md gap is a repository finding in its own right, separate from HW3.

### Second half of the same correction: 45 final scenarios (2026-09-15)

The pilot review rows were fixed first, but the same wrong claim had already
been generated into the final set. `exp_status()` in
`tools/build_support_scenarios.py` ended every `order_status` and `find_order`
expectation with "must not invent tracking or carrier information, which no
tool provides". That is false, and the smoke report shows `track_shipment` was
called **54 times** during the final run, so Homework 4 would have read correct
tool use as a failure in **45 coverage scenarios** (30 `order_status`,
15 `find_order`) — and, because one function generated them all, as a pattern
rather than as noise.

Fixed by rewriting `expected.reason` in those 45 records in place, and the
generator alongside them, to:

> "The agent must report the stored values accurately. Shipment progress may be
> reported from track_shipment (SPEC.md TOOL-11), whose expected_ship_by and
> expected_delivery_by are projections from the cw-shipping handling and
> transit maxima rather than carrier data, so the agent must not present them
> as confirmed carrier facts."

That keeps the check the scenario was written for — do not dress a policy
projection as carrier data — without punishing the agent for using a tool it is
given.

**No re-run was needed.** The expectation is the yardstick, not the experiment:
the requests, the agent and the traces are unchanged, and only the wording of
the yardstick was wrong. Verified afterwards, all still true:

```
validate --final          : 250 records, 175 coverage / 75 challenge, 30 dq
ids unchanged             : True
scenarios <-> results join: True   (all 250)
scenarios <-> traces join : True   (all 250)
monitoring subset         : 50, all present in the final set
stale phrase remaining    : 0
```

## The 15 reviewed scenarios

  | id | group | role | intent | why it is in the sample |
  |---|---|---|---|---|
  | support-0001 | challenge | shopper | return_deadline | dq, missing delivery date |
  | support-0016 | challenge | merchant | product_search | dq, duplicate title (all four listings) |
  | support-0011 | challenge | merchant | order_status | dq, store mismatch |
  | support-0031 | challenge | shopper | return_eligibility | store override, window CLOSED |
  | support-0032 | challenge | shopper | return_eligibility | store override, window OPEN |
  | support-0043 | challenge | shopper | order_status | authorization denied |
  | support-0004 | challenge | shopper | refund_request | cross-turn correction |
  | support-0062 | challenge | shopper | find_order | missing information, human_judgment |
  | support-0057 | challenge | shopper | refund_request | refund above the $100 threshold |
  | support-0184 | coverage | support | cancel_order | staff voice |
  | support-0232 | coverage | merchant | restocking_fee | staff voice |
  | support-0239 | coverage | support | dispute | staff voice |
  | support-0222 | coverage | support | policy_question | policy citation |
  | support-0241 | coverage | merchant | payout | merchant-only intent |
  | support-0247 | coverage | shopper | out_of_scope | refusal |

## State of the database right now
The final run mutated it (14 refunds, 5 cancellations, 17 escalations; see
Part D above). Re-seed with `uv run python -m seed.generate` before computing
any new expected result. The seed is deterministic
(`tests/test_seed_determinism.py`), so re-seeding reproduces exactly the state
every expectation in `support_scenarios.jsonl` was computed against.

## Background processes in this session
- Cartwheel endpoint: `uv run uvicorn server.app:app --port 8010`, PID 25296,
  started as a background task so its log is readable. Restarting it empties
  `_SESSIONS`; harmless between runs, never do it mid-run.
- Langfuse stack: six containers up.

## Deliverable checklist
- [x] `scenarios/pilot_scenarios.jsonl` (30) — validated
- [x] `scenarios/pilot-results.jsonl` — 30/30 completed on glm-5.3
- [x] `scenarios/pilot_review.jsonl` — 30 reviewed, 7 confirmed failures
- [x] `scenarios/support_scenarios.jsonl` (250 = 175 coverage + 75 challenge,
      5 per data-quality case, ids distinct from the pilot)
- [x] `scenarios/support_review.jsonl` (15 decisions, the one rejection
      replaced as support-0251)
- [x] `scenarios/monitoring_scenarios.jsonl` (50, both groups, all three roles)
- [x] `scenarios/final-results.jsonl` (250 `completed`)
- [x] `reports/smoke-output.txt`
- [x] `traces/support_traces.json` (250 unique `cartwheel_scenario_id`)
- [ ] Student's own: handout assessments, <=5 minute video
- [x] Optional scaffolding, not a deliverable: `tools/trace_viewer.html`,
      `tools/build_support_scenarios.py`, `tools/build_monitoring_set.py`.

## Which checks used a live model
- **Live (glm-5.3 via DeepInfra):** the B3 pilot run (30 scenarios), three
  preflight calls on 2026-09-15, the Part D run (250 scenarios) and the
  three-scenario rerun.
- **Offline:** every `validate` run, the rebuild diff, the monitoring
  selection, the write-ordering check, all database spot checks, the ClickHouse
  smoke report and the trace export.

## For the video
The handout asks for four things on screen, and all four have a concrete target:
1. A pilot scenario that failed, with its expected result and evidence — pick
   from the seven in "The 7 confirmed failures" above. pilot-002, 003 and 025
   are not among them and their evidence was corrected on 2026-09-15; the
   committed file and the traces now agree either way.
2. A final scenario revised after review — **support-0251**, next to the
   `support-0016` row in `scenarios/support_review.jsonl`.
3. One complete final trace with its scenario id and tool activity —
   support-0251's trace shows `search_products` and `list_my_orders` TOOL
   spans.
4. The identifier count. No `jq` on this machine; the substitute is:
   ```
   uv run python -c "import json;print(len({t['cartwheel_scenario_id'] for t in json.load(open('traces/support_traces.json',encoding='utf-8'))['traces']}))"
   ```
