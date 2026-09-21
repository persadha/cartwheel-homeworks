# HW4 progress

Last updated: 2026-09-21. Branch `hw-4`. Part A complete. Steps 0 to 3 DONE
(preparation, stock-view review, layout proposal, interface fork), including the
verified Langfuse score write.

**Part B (open coding) is IN PROGRESS.** All four batches are built — 100
conversations, 127 raw traces — and **60 of 100 are reviewed**. Six failure modes
are drafted, two confirmed. `SPEC.md` has been revised (RESP-6). Part C has not
started.

**Start here tomorrow: 40 conversations to review and 13 suggestions to decide.**
See "Session 2026-09-21" at the end of this file for the exact list and the
recommended verdict on each.

Nothing is running. The review server was stopped at the end of the session and
the Docker/Langfuse stack is down. No volume was destroyed.

Working style: student drives. The agent proposes each step in plain language
and waits for an explicit "go" before running or changing anything. Every
judgment about what counts as a failure is the student's. The agent organizes,
computes and scales; the human notices and decides. Assessments and the
<=5 minute video are the student's own work.

## Settled 2026-09-19

Three decisions the student made when resuming; none is open any more.

| Question | Decision |
| --- | --- |
| Recording a clean conversation | Add a "No failure observed" button to the interface (built, see Step 4b) |
| Langfuse during Part B | Review offline, `--no-langfuse`. Docker is needed only from Part E |
| What "100 traces" counts | **Conversations.** 100 conversations is roughly 128 raw traces, clearing the bar either way. State the convention in `review_summary.md` |

## Restarting after the pause

```bash
# optional: only needed for turn permalinks and the Part E score writes
docker compose -f observability/docker-compose.yml start

# the review app; samples.json is self-contained, so this works with the stack down
uv run python analysis/review_app/server.py --port 8021 --no-langfuse
```

NEVER `docker compose down -v` — it destroys the volumes holding every trace.

## Settings fixed for this assignment

- **Trace source: live Langfuse.** Self-hosted stack in Docker,
  http://localhost:3000, project `cartwheel-dev`. Sign in as
  widianto.persadha@iea-hamburg.de. Start with
  `docker compose -f observability/docker-compose.yml start`. NEVER `down -v`
  — it destroys the volumes holding every trace.
- **Review population: the 308 `support-*` traces = 250 conversations.** The
  project holds 362 traces in total; the pilot (37), preflight (3) and
  untagged (14) records are excluded. `langfuse_io.fetch_traces` already drops
  records with no `cartwheel.scenario_id`; the `support-` prefix filter is
  ours on top of that.
- **Grouping key: `cartwheel.scenario_id`, not `cartwheel.session_id`.**
  See "Deviation from the handout" below.
- **Interface: fork the reference, then adapt.** `analysis/server.py` and
  `analysis/ui/index.html` are copied into `analysis/review_app/` and changed
  there. The handout forbids submitting the reference unchanged, so every
  adaptation must be real and must be argued in
  `analysis/report/interface_comparison.md`.
- **Progress notes: this file.** Not a graded deliverable.
- This machine has NO `sqlite3` CLI and NO `jq` (carried over from HW3). Every
  handout command using them is substituted with `uv run python -c "..."`.
- Offline fallback, if Langfuse ever goes down mid-assignment:
  `traces/support_traces.json` (308 traces, exported 2026-09-15, identical
  population). The handout requires recording the reason in
  `interface_comparison.md` if it is used.

## Deviation from the handout: the session grouping key

The handout requires the review interface to group traces by
`cartwheel.session_id`. **That attribute is absent from all 308 HW3 traces.**
Verified three ways on 2026-09-19: the Langfuse `sessionId` field is null on
all 362 traces; the only trace-level Cartwheel attributes recorded are
`cartwheel.prompt_version`, `cartwheel.scenario_id`, `cartwheel.user_id` and
`cartwheel.user_role`; no observation-level attribute carries a session id
either.

Cause: `server/app.py:193` does set `cartwheel.session_id`, but that line is an
uncommitted working-tree change made after the HW3 run completed, so it could
not tag traces recorded on 2026-09-15.

Substitute: group on `cartwheel.scenario_id`, which every trace carries.
`analysis/helpers/normalization.py:290` already implements exactly this
("Merge traces that share a scenario_id into one conversation"), and
`analysis/helpers/selection.py:41` `load_traces` applies it and sorts
observations by start time. This delivers the behaviour the handout is asking
for — every turn of a multi-turn conversation on one screen, in order — under a
different attribute name. 51 of the 250 conversations span more than one turn;
the longest are `support-0221`, `support-0212` and `support-0205` at 3 turns.

Keep the `server/app.py` line: new runs (including the Part C replays) will
then carry both identifiers. Record the substitution in
`analysis/report/interface_comparison.md`.

## Open decisions

- **What counts as "a trace" for the 100-trace minimum.** Turns are merged into
  conversations for review, so one reviewed item = one conversation = 1 to 3
  raw traces. Reviewing 100 conversations covers 100 to ~130 raw traces, which
  clears the bar either way. Proposal: count conversations, and state the
  convention explicitly in `analysis/report/review_summary.md`.
  **DECIDED 2026-09-19: count conversations.**
- **Trace source while Docker is down.** Open coding needs nothing from Langfuse:
  `analysis/state/samples.json` already carries every conversation's text, tool
  calls and tool results. Running `--no-langfuse` costs only the turn permalinks,
  which will not open. Docker becomes necessary again at Part E, for the score
  writes. **DECIDED 2026-09-19: review offline.**

## Done

### Step 0, preparation (2026-09-19)
All checks read-only. No secret values were read or printed.

1. Containers: all six up (`langfuse-web`, `langfuse-worker`, `postgres`,
   `clickhouse`, `redis`, `minio`).
2. Health: `GET http://localhost:3000/api/public/health` -> 200.
3. `.env`: `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_HOST`
   present (names only).
4. `analysis.helpers.langfuse_io.is_configured()` -> True, host
   `http://localhost:3000`.
5. Project inventory: 362 traces, all named `cartwheel.session_message`;
   348 carry `cartwheel.scenario_id`; 281 distinct scenarios
   (308 `support-*` / 37 `pilot-*` / 3 `preflight-*` traces).
   The live project and `traces/support_traces.json` agree exactly on the
   support population.
6. Loader keys on Module 1 scenario identifiers, not a demonstration tag —
   confirmed, with the session-key deviation recorded above.

Pre-existing files under `analysis/state/` (`store_traces.json`,
`demo_annotations.json`, `splits.json`, `judges/`,
`labels/unsupported_policy_claim.jsonl`) are shipped course sample data, not
student work. `analysis/state/annotations.json`, `patterns.json` and
`suggestions.json` are empty. `analysis/review_app/show_trace.py` is terminal
scaffolding for reading conversations, explicitly not the Part A deliverable.

### Step 1, Part A.1, read traces in the stock Langfuse view (2026-09-19)

Selection: 8 conversations (17 raw traces) chosen to span the dimensions that
stress a review interface, not to predict failures. All 17 trace ids verified
against the live stack. No annotation queue was created; the traces were opened
by URL, because the critique concerns trace rendering rather than queue
mechanics.

| Scenario | Role | Turns | Obs | Why chosen |
| --- | --- | --- | --- | --- |
| support-0080 | shopper | 3 | 19 | multi-turn: one conversation or three orphans? |
| support-0128 | shopper | 3 | 20 | multi-turn |
| support-0170 | support | 3 | 29 | `issue_refund`, RESP-2 territory |
| support-0125 | shopper | 2 | 27 | `escalate_to_human`, RESP-2 territory |
| support-0187 | shopper | 2 | 46 | tool-heavy: density and scrolling |
| support-0075 | shopper | 2 | 24 | real permission denial, AUTH-1 / RESP-4 |
| support-0196 | merchant | 1 | 23 | merchant role |
| support-0250 | merchant | 1 | 4 | short baseline: what "nothing wrong" looks like |

Student's observations on the stock Langfuse view, verbatim (2026-09-19):

> support-0080/0128/0170: I could see all tool's result on the left pane. But I
> need to click on the tool's name to see details such as output and metadata.
> And I have to scroll to see its metadata. I could tell that it was a 3-turn
> conversation by inspecting the user_id and the time.
> In a long agent interaction, such as support-0170 I had to scroll down the
> left pane to see all tool's name.
>
> I need to hold off the timestamp from multi-turn conversations, since I have
> to click different tabs.
> I think I did not need all metadata information. The metadata attributes
> misght be usefulm but resourceAttributes, scope could be ignored

Derived design requirements (the brief for Step 2):

| # | Observation | Requirement |
| --- | --- | --- |
| R1 | Tool output and metadata need a click on the tool name | Render tool arguments and tool results inline, no click for anything needed to judge a reply |
| R2 | Metadata needs scrolling to reach | Promote the four useful attributes to a header row that is always visible |
| R3 | Long interactions force scrolling a separate pane to see tool names | One reading column, chronological; no second pane holding essential content |
| R4 | Multi-turn identity had to be reconstructed from `user_id` plus timestamps, across tabs | Merge all turns of a `scenario_id` onto one page in time order, with explicit turn separators carrying the timestamp |
| R5 | `resourceAttributes` and `scope` are noise; `attributes` may be useful | Drop `resourceAttributes` and `scope` from the reading view; surface only the four `cartwheel.*` attributes |

R4 is the leading candidate for the "design I changed after inspecting my
traces" line in `analysis/report/interface_comparison.md`.

### Step 2, Part A.2, layout proposal (2026-09-19)

Field inventory over all 250 conversations. Four message roles only
(`user` 308, `assistant` 308, `tool_call` 890, `tool_result` 890); no system
messages and no reasoning blocks, so four hues suffice. `tool_call` and
`tool_result` counts are equal and adjacent, which is what makes the
call-plus-result container work. 13 tools; the writes are rare
(`escalate_to_human` 34, `issue_refund` 28, `cancel_order` 10), and those 72
spans are the only places a RESP-2 failure can exist.

Encoding approved by the student: hue = message role; one container per tool
call and its result; turn separator with number, timestamp and per-turn trace
link; sticky header; red badge on write tools; `resourceAttributes` and `scope`
not rendered; opacity reduced only for content identical across traces.

### Step 3, Part A.3, fork and adapt the interface (2026-09-19)

Files, all new, under `analysis/review_app/`:

| File | What it is |
| --- | --- |
| `server.py` | fork of `analysis/server.py`; state dir repointed at `analysis/state/`, new `/api/labels`, demo `--replay` removed |
| `ui/index.html` | fork of `analysis/ui/index.html`; the seven adaptations below |
| `build_samples.py` | own grouping and batch selection (new, no reference equivalent) |
| `show_trace.py` | pre-existing terminal reader, kept as scaffolding |

Adaptations:

1. Tool arguments and tool results render open. The reference hid arguments in
   `<details>` and any result over 240 chars in `<details>`, reproducing the
   Langfuse click-to-expand problem (R1). Results over 2000 chars are clipped
   with a control stating how much is hidden; 26 of 890 results are affected,
   all `list_my_orders` or `search_products`, never a write result.
2. Turn separators with turn number, timestamp, tool count, write tools and a
   Langfuse permalink for that turn (R4).
3. Red `write` badge on `issue_refund`, `cancel_order`, `escalate_to_human`.
4. New Label view: conversations x modes grid, Fail / Pass / clear per cell.
5. Progress view gained review coverage per batch and labeling completeness
   per mode; the reference had only a treemap and the suggestion queue.
6. Judgments write to Langfuse as scores and mirror to
   `analysis/state/labels/<mode>.jsonl`.
7. Sticky header leading with `scenario_id`; `store` dropped (no Cartwheel
   trace carries it at trace level).

Retained unchanged: role hues, the call-plus-result container, the single
reading column, margin-note annotation by text selection, suggestion
accept/dismiss, the file-backed API contract and its atomic writes.

Also changed: a decided suggestion is kept in `suggestions.json` with its
`decision` recorded rather than deleted, because the handout requires the saved
state to contain at least one rejected suggestion.

Outlier flags are capped at two per conversation. Tool calls, tokens and turns
are correlated, so a long conversation tripped all three tests and arrived
wearing three near-identical badges, against the skill's "most records should
have zero or one flag". Distribution now: 192 conversations with no flag, 36
with one, 22 with two.

Smoke test, offline, no model and no Langfuse write (`--no-langfuse`):

- `build_samples.py --stats` -> 250 conversations, 308 raw traces, matching
  the live project exactly.
- `node --check` on the extracted script block -> clean.
- `GET /` 200, 55 KB. `GET /api/samples` returns conversations carrying
  `turn_trace_ids`, per-turn timestamps and permalinks.
- `POST /api/labels` on the 2-turn `support-0002` -> 2 rows, one per turn trace
  id. Re-labelling replaces rather than duplicates (still 2 rows). `label:
  null` clears to 0 rows. A payload missing `conversation_id` is rejected 400.
- Smoke state then reset; `analysis/state/` holds only the `preview` batch.

**Langfuse score write verified end to end (2026-09-19), with the student's
approval.** One judgment posted through the running server for `support-0250`
(mode `_smoke_check`, label 0, one turn):
`POST /api/labels` -> `{"ok": true, "rows": 1, "langfuse_scores_written": 1}`,
and `read_label_scores` returned
`{'name': '_smoke_check', 'value': 0.0, 'comment': 'Part A verification ...'}`
against trace `ed1e3b3199ababc0d5fb7f9a0f023076`. The test score was then
deleted (`lf.api.score.delete`) and the local `_smoke_check.jsonl` removed;
both verified empty afterwards, so the project carries no test data.

Finding for Part E: **Langfuse score ingestion is asynchronous.** The first
read-back immediately after the write returned an empty list; the score
appeared on the retry. This does not affect the interface, because the Label
view reads `/api/labels`, which is served from the local JSONL mirror rather
than from Langfuse. It does mean any verification of Part E counts *against
Langfuse* must retry rather than read once and conclude the write was lost.

`analysis/report/interface_comparison.md` written: retained design, changed
design, the session-key substitution, the trace-source note, and the remaining
limitation (the interface cannot check a tool result against the database).

**Leftover to resolve before Part E:** `analysis/state/labels/` still holds the
course's demo file `unsupported_policy_claim.jsonl`, which is sample data, not
student work. The handout asks for one label file per *final* mode, so it
should be moved or deleted before the deliverables are committed.

### Step 4, Part B, open coding (IN PROGRESS, paused 2026-09-19)

Batch 1 was built and the review app was driven against it. What exists on disk:

| File | State |
| --- | --- |
| `analysis/state/sample_manifest.json` | two batches, 30 conversations / 39 raw traces |
| `analysis/state/samples.json` | the same 30 conversations, self-contained |
| `analysis/state/annotations.json` | 1 open code |
| `analysis/state/patterns.json` | 1 candidate mode |

The two batches, both seed 7:

- `b1_uniform`, strategy `random`, k=15. The handout's "15 uniformly sampled".
- `b1_cluster`, strategy `diversity`, k=15. Five cluster representatives drawn
  twice (clusters 0 to 4) plus 5 random picks. The handout's "15 cluster
  representatives".

`samples.json` carries, per conversation, the full text, every tool call and tool
result, `turn_trace_ids`, per-turn timestamps and per-turn Langfuse permalinks.
It is self-contained, so **open coding needs no Langfuse connection**; only the
permalinks and the Part E score writes do.

The one open code so far, on `support-0084`: the reply volunteered
refund-eligibility information the shopper never asked for ("the order is
currently not marked as refund-eligible, which likely has to do with the return
window having passed"), when the shopper had only asked to list the order. The
student's note: "Too much details. The shopper only asked to list the order, not
asking about refund."

That note produced the single candidate mode in `patterns.json`,
`unrequested_information`: "The reply supplies substantive information the user did
not ask for and no requirement obliges, beyond what answers the question."
Its `requirement_source` is still "none yet, possible SPEC gap", so it is a
candidate for the `SPEC.md` revision the handout asks for.

Remaining work in Part B: **29 conversations left in batch 1**, then batch 2
(30 traces distributed across one product dimension chosen before looking at
outcomes), batch 3 (25 from depth searches, including close negatives) and
batch 4 (15 uniform, the stability check).

## Blocker found 2026-09-19, RESOLVED the same day (see Step 4b)

The handout requires recording "no failure observed" for a clean conversation, so
that the saved annotations distinguish a reviewed trace from an unreviewed one.
**The interface cannot currently do this.** Evidence, all in
`analysis/review_app/ui/index.html`:

- An annotation can only be created from a text selection. The `mouseup` handler
  on `#trace-body` (line ~679) returns early when the selection is collapsed, and
  `commitAnnotation` (line ~734) requires a `pendingCtx` that only that handler
  sets. A clean conversation has nothing meaningful to quote.
- "Reviewed" is derived as `new Set(state.annotations.map(convId))`, in
  `renderCoverage` (line ~894) and `updateCounts` (line ~1103). A conversation
  carrying no annotation can therefore never be counted as reviewed, and the
  coverage bars will under-report the batch.

The student approved the button and declined the optional "jump to next
unreviewed" companion. Built the same day; see Step 4b below.

### Step 4b, the "No failure observed" control (2026-09-19)

Adaptation 8 of the review interface, and the one that unblocked Part B. Three
edits to `analysis/review_app/ui/index.html`, no server change:

1. A `No failure observed` button at the right of the sticky header. It writes an
   annotation with `quote: null`, `idx: null`, `note: "no failure observed"` and
   `source: "no_failure_observed"` (the constant `CLEAN_SOURCE`). Clicking again
   removes it, so the mark is reversible.
2. A conversation that already carries a real open code shows a
   `✓ reviewed · N notes` tag instead of the button, so a conversation can never
   be marked clean and failed at once.
3. The clean marker renders in the margin column tagged `reviewed · clean`, and
   is deletable there. `renderHeader` and `updateCounts` are now also called from
   `commitAnnotation` and `deleteAnnotation`, so the header and the counter stay
   in step with the margin.

Why it was needed: the handout requires a reviewed-but-clean conversation to be
distinguishable from an unreviewed one, "reviewed" is derived from the annotation
list, and a clean conversation has no text worth quoting.

Verified offline, no model and no Langfuse write:

- the extracted script passes `node --check`;
- `const CLEAN_SOURCE` is initialised before `boot()` runs, so there is no
  temporal-dead-zone hazard despite `renderHeader` referring to it earlier in
  the file;
- `GET /` 200, 57 KB; `GET /api/samples` returns the 30 conversations;
- a clean record posted to `/api/annotations` round-trips with `quote` still
  null and lands in the reviewed set. The test record was then removed and
  `git diff` on `annotations.json` confirmed empty.

Record this as an eighth adaptation in
`analysis/report/interface_comparison.md` before the deliverables are final.

## Data gotchas found while reading the traces

- **`cartwheel.permission_denied` is a string, not a boolean.** Langfuse stores
  it as `'false'` (860 observations) or `'true'` (30). Python treats the string
  `'false'` as truthy, so `if attrs.get("cartwheel.permission_denied")` marks
  every trace as denied. Compare explicitly:
  `str(v).lower() == "true"`. Only 16 of the 250 conversations contain a real
  denial: support-0043 to 0051 and support-0069 to 0075. Any future code check
  for AUTH-1 or RESP-4 must use the string comparison.
- **Observation order in the raw export is unreliable.** Always go through
  `analysis.helpers.selection.load_traces`, which sorts by start time and
  merges turns. Never read `traces/support_traces.json` directly.

## Deliverable checklist

- [x] Review interface code under `analysis/review_app/`
- [ ] `analysis/state/sample_manifest.json`
- [ ] `analysis/state/annotations.json`
- [ ] `analysis/state/patterns.json`
- [ ] `analysis/state/suggestions.json` (must contain >=1 rejected suggestion)
- [ ] One label file per final mode under `analysis/state/labels/`
- [ ] `analysis/report/review_summary.md`
- [ ] `analysis/report/workshop_notes.md`
- [x] `analysis/report/interface_comparison.md`
- [ ] Any `SPEC.md` revision, with its motivating annotation named in the
      review summary
- [ ] Student's own: the <=5 minute video

## Which checks used a live model

- **Live model:** none yet.
- **Offline / read-only:** every Step 0 check, the Step 1 selection, the Step 2
  field inventory and the whole Step 3 smoke test. The Langfuse reads hit the
  local Docker stack, not a model provider.
- **Langfuse writes:** exactly one, the `_smoke_check` score described above,
  since deleted. No other write to `cartwheel-dev` has occurred.

## For the video

The handout asks for seven things on screen. Targets fill in as the work
proceeds.

1. One interface decision made after inspecting the traces — **turn
   separators (R4)**, see `interface_comparison.md`. Show `support-0170`,
   3 turns, `issue_refund`.
2. One Workshop suggestion and the accept/revise/reject decision — pending
   (Step 5).
3. Two failure modes and one supporting trace each — pending (Step 6).
4. One taxonomy revision or rejected group — pending (Step 6).
5. One rejected search suggestion and the boundary excluding it — pending
   (Step 6).
6. One relationship between a mode and `SPEC.md` — pending (Step 6).
7. The number of new modes found in the final 15 reviewed traces — pending
   (Step 7).

---

# Session 2026-09-21

## State at the end of the session

| | |
| --- | --- |
| Sample | **100 conversations, 127 raw traces** (all four batches built) |
| Reviewed | **60 of 100** |
| Annotations | 61 (21 open codes, 39 clean) |
| Suggestions | 13, **all pending** |
| Failure modes | **6** (2 confirmed, 4 candidate) |
| `SPEC.md` | revised, **RESP-6** added |
| Part C | not started |

Uncommitted: `SPEC.md`, `analysis/state/{annotations,patterns,samples,sample_manifest,suggestions}.json`.

## START HERE

### 1. Start the server, then do not let the agent POST while the tab is open

```bash
uv run python analysis/review_app/server.py --port 8021 --no-langfuse
```

**Workflow hazard found the hard way.** Late in the session the agent POSTed to
`/api/annotations` and `/api/suggestions` while the student's browser tab was
open. The page polls and replaces its state from the server, so a round of queue
work (13 accept/dismiss decisions plus 12 clean marks) was lost. Newest saved
annotation is `2026-09-21T20:07:46Z`; the file was rewritten by the agent at
23:15 local.

Rule for the rest of the assignment: **the agent does not write to the API while
the student is working in the browser.** Either the student closes the tab first,
or the agent waits. After any agent write, hard-reload before clicking anything.

### 2. Decide the 13 pending suggestions

The agent read all 25 batch-3 conversations. Its recommendation per suggestion —
the decision is the student's:

| Suggestion | Conversation | Agent's read |
| --- | --- | --- |
| sg-b3-01 | support-0032 | **Accept.** $205.50, "go ahead and process the refund", no approval mentioned |
| sg-rev-00 | support-0200 | **Accept.** "the cheapest option" off a keyword match |
| sg-rev-01 | support-0194 | **Accept.** "here's what Meridian Cycles has under $30" off one keyword |
| sg-rev-02 | support-0023 | **Accept.** escalated the same glitch twice, tickets #156 and #167 |
| sg-b3-00 | support-0069 | **Dismiss.** permission denial, not a refund offer |
| sg-b3-02 | support-0073 | **Dismiss.** permission denial, not a refund offer |
| sg-b3-03..08 | 0165 0172 0159 0153 0170 0057 | **Dismiss.** all six said "queued for human review" |
| sg-rev-03 | support-0027 | **Student's call.** gave up on a findable store; support-0030 answered the same question |

At least one dismissal is a hard requirement of the handout. The 0069/0073 pair is
also the natural video answer for "a rejected search suggestion and the boundary
excluding it" — a refusal to act is not an offer to act.

### 3. Review the remaining 40

**25 from batch 3.** The agent read all of these; its verdict in brackets.

- `0044 0051 0070 0075` [clean] permission refusals, none leak anything. **RESP-4 holds** — checked deliberately, no sixth mode here.
- `0178 0180` [clean] correctly refuse post-shipment cancellation, cite cw-cancellations + cw-returns.
- `0074` [clean] correctly refuses a 215-day-old order.
- `0185 0030` [clean] honest about the broken catalogue data.
- `0193` [clean] hedges its keyword search; the close negative that pairs with `0200`.
- `0245` [clean] answers from cw-payouts.
- `0029` [**likely Fail**] volunteers order #8770's dates and total unasked — same shape as `0026`. Under RESP-6 this is a positive. The agent first called it clean and corrected itself once RESP-6 was written; treat it as a positive.
- the 9 in the suggestion queue, above.

**15 from batch 4 (`b4_stability`), review these LAST.** Their only job is to answer
"does a genuinely new mode still appear?". Read them without hunting for the six
known modes. The count of new consequential modes goes in `review_summary.md` and
the video.

`0135 0077 0162 0033 0039 0216 0052 0149 0231 0035 0206 0102 0025 0047 0177`

## The taxonomy

| Mode | Pos | Neg | Requirement | Evaluator |
| --- | ---: | ---: | --- | --- |
| `unrequested_information` | 5 | 3 | **RESP-6** (new) | LLM judge |
| `unsupported_policy_claim` | 3 | 3 | RESP-1, RESP-3 | LLM judge |
| `contradicts_tool_verdict` | 2 | 4 | RESP-3 | LLM judge |
| `above_threshold_action_offered` | 1 | 3 | ESC-1, AUTH-1 | hybrid |
| `unverifiable_completeness_claim` | 1 | 2 | RESP-3 | LLM judge |
| `duplicate_write_action` | 1 | 2 | **none — spec gap** | hybrid |

Every mode carries a binary `decision_rule`, close negatives drawn from real
traces, a `boundary_vs_nearest`, and a `likely_evaluator`, all in `patterns.json`.

Positive counts for the bottom four are low only because the queue decisions have
not landed. Accepting the four recommended suggestions takes
`above_threshold_action_offered` to 2, `unverifiable_completeness_claim` to 3, and
confirms `duplicate_write_action`'s single positive.

### Taxonomy revision to write up (handout requires one)

`fabricated_policy_citation` and `missing_policy_citation` were **merged** into
`unsupported_policy_claim`. Merge test: one product change — "every policy claim
must carry an identifier that resolves to a tool result in the same conversation" —
fixes both `support-0151` (invented `store-northwind-books-policy`) and
`support-0004` (named the shipping policy with no id). Recorded in the mode's
`merged_from` and `merge_reason`.

### The SPEC.md revision (handout requires it documented)

**RESP-6**, added to section 6 on 2026-09-21:

> Answer the question asked. Do not volunteer order facts, sales history,
> eligibility status, or policy detail the user did not request. Offering a
> clearly labelled next step is permitted; stating additional facts about the
> order or catalogue is not.

Motivating annotation: `a1789840564485632` (`support-0084` — shopper asked to list
an order, reply volunteered refund-eligibility). The third sentence is load
bearing: without it, closing offers like `support-0116`'s "Want me to pull up more
details?" become violations, and since nearly every reply ends with one the mode
would fire everywhere and discriminate nothing.

`duplicate_write_action` has the same gap and no requirement yet. Either write a
second rule or drop the mode — five still clears the handout's 5-to-8 minimum.
Decide after batch 4, in case more instances appear.

## Batches, and why each was selected

| Batch | n | Selection |
| --- | ---: | --- |
| `b1_uniform` | 15 | random, seed 7 |
| `b1_cluster` | 15 | diversity, seed 7 |
| `b2_role` | 30 | balanced across role, 10/10/10 — dimension chosen before looking at outcomes |
| `b3_threshold_offer` | 3 | filter: refund offered, order over $100, no approval language |
| `b3_threshold_negative` | 6 | filter: `issue_refund` above $100 with approval language — close negatives |
| `b3_completeness` | 2 | filter: 3+ product searches with empty results, then an unhedged superlative |
| `b3_eligibility_negative` | 3 | filter: not-eligible tool result the reply handled correctly |
| `b3_permission` | 4 | filter: `permission_denied` — RESP-4 check |
| `b3_malformed_call` | 4 | filter: `invalid_argument` the agent worked around |
| `b3_lookup_failure` | 3 | filter: `not_found`, and one repeated identical call |
| `b4_stability` | 15 | random, seed 11 |

Population is 250 conversations; the role split is shopper 149 / merchant 58 /
support 43, and only 35 conversations call a write tool.

## What the searches actually taught us

Worth a line in `review_summary.md`, and honest:

- **Retrieval filters were wrong more often than right.** Of 3 predicted
  `above_threshold` positives, 1 survived reading. Of 3 predicted
  `contradicts_tool_verdict` positives, **0** survived. Two agent filter bugs were
  caught by reading traces: `json.loads` on an already-parsed dict silently
  returned "0 candidates" when the truth was 64; and `refund_eligible: false` was
  treated as one signal when it has two unrelated causes (window expired vs. not
  yet delivered).
- **The modes are rare.** Roughly 1-2 genuine positives per targeted search across
  ~180 conversations. Real signal, not search failure.
- **Review bar drifted mid-assignment.** Batch 1 produced 16 open codes from 28
  conversations; batch 2 produced 2 from 28. A 6-trace random spot-check of batch 2's
  clean marks found 2 plausible misses, both the same bug shape already coded in
  batch 1. Partly a real difference (batch 1 was half cluster representatives),
  partly a bar that tightened after five batch-1 codes were pushed back on. Worth
  stating plainly in the summary.

## Consequences for HW5

HW5 needs **>=30 Pass and >=30 Fail labels per mode**. Current positives are 1-5.
Expect to synthetically generate scenarios targeting each mode, as the handout's
prep section allows. The crisp `decision_rule` on each mode makes that generation
much easier — that is what those rules are for.

## Deliverable checklist

- [x] Review interface code under `analysis/review_app/`
- [x] `analysis/state/sample_manifest.json` (100 conversations, 11 batches, each with its selection reason)
- [~] `analysis/state/annotations.json` (61; 40 conversations still unreviewed)
- [x] `analysis/state/patterns.json` (6 modes)
- [ ] `analysis/state/suggestions.json` — 13 present but **all pending**; needs >=1 recorded rejection
- [ ] One label file per final mode under `analysis/state/labels/` (Part E)
- [ ] `analysis/report/review_summary.md`
- [ ] `analysis/report/workshop_notes.md` (Part C)
- [x] `analysis/report/interface_comparison.md`
- [x] `SPEC.md` revision (RESP-6) with its motivating annotation identified
- [ ] Video (student's own work)

**Leftover from the earlier session, still unresolved:** `analysis/state/labels/`
holds the course's demo file `unsupported_policy_claim.jsonl`. It is shipped sample
data, not student work, and the mode name now collides with a real student mode.
Delete or move it before Part E writes labels.

## Part C, when it is reached

Decided: **do Part C** (it is optional on upstream `main`, commit `f3fbacb`, but the
student chose to do it). Plan agreed, nothing executed:

1. Commit the analysis state first, so anything Workshop changes is revertible.
2. Fetch Workshop's current install instructions (read-only) and review before installing.
3. Show exactly what `/instrument-agent` will change **before** it runs. The handout
   requires preserving the existing OpenTelemetry and Langfuse instrumentation
   (`observability/instrument.py`, `agent/cli.py:128`, `server/app.py:190`), and
   those traces are the basis of both HW4 and HW5.
4. Pick 5-10 runs spanning roles and tools, biased toward write tools.
5. Draft `analysis/report/workshop_notes.md`.

Three approvals needed before anything happens: installing third-party software,
letting `/instrument-agent` modify agent code, and spending real API credit
(`replay/` makes live model calls).

Note for `review_summary.md`: Part C will have run at 60-100 conversations reviewed
rather than strictly after open coding. Record the sequence honestly.

## Notes carried forward

- Grouping key is `cartwheel.scenario_id`, not `cartwheel.session_id` — see
  "Deviation from the handout" above. Unchanged.
- "100 traces" is counted as **100 conversations** (127 raw traces). State the
  convention in `review_summary.md`.
- Reading state files in Python on this machine needs `encoding='utf-8'` and
  `PYTHONIOENCODING=utf-8`; the default cp1252 now fails on annotation text.
- Backups from the suggestion reset live in the session temp dir
  (`annotations.pre-fix.json`, `suggestions.pre-fix.json`, `patterns.backup.json`)
  and will not survive a reboot — ignore them if gone.
