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

---

# Session 2026-09-22

## What changed before the browser opened

Both writes landed with the server down and no tab open, per the 09-21 hazard
rule. Nothing was POSTed to the API.

### `duplicate_write_action` is dropped

Decided by the student. `analysis/state/patterns.json` now carries
`"status": "dropped"`, a `dropped_at`, and a `drop_reason` on two grounds:

1. One positive only (`support-0023`). The handout requires three confirmed
   positives per mode, and the targeted searches over ~180 conversations found no
   second instance.
2. No requirement source. `unrequested_information` had the same gap and was kept
   because five positives justified writing `RESP-6`; one positive does not
   justify a second specification revision.

The entry is **not deleted**. Its definition, decision rule, close negatives
(`support-0015`, `support-0009`) and boundary stay in the file as the evidence
behind the drop — the handout requires the path from observation to category to
remain inspectable. This is the second taxonomy revision, and it is the stronger
answer to the video's "one taxonomy revision or rejected group".

Five modes remain, inside the handout's 5-to-8 range.

### The review app now distinguishes a dropped mode

`modeNames()` in `analysis/review_app/ui/index.html` fed the Part E label grid
straight from `patterns.json` with no status filter, so a dropped mode would have
appeared as a labelling target. It now filters `status !== 'dropped'`. The Failure
modes treemap still renders it — it reads `normalizePatterns` directly — with a
struck-through grey badge, which is the behaviour we want.

## Revised recommendation on the suggestion queue

Unchanged from `hw4-progress.md` START HERE except for one row:

- `sg-rev-02` (`support-0023`) was a recommended **accept**. With the mode
  dropped, **dismiss** it — the open code survives in the annotation history
  either way, and accepting would create an annotation with no mode to sit under.

Net: 3 recommended accepts (`sg-b3-01`, `sg-rev-00`, `sg-rev-01`), 9 dismissals,
`sg-rev-03` still the student's call.

## Positive counts after the drop and the 3 accepts

| Mode | Positives | Against the 3-positive minimum |
| --- | ---: | --- |
| `unrequested_information` | 6 | clears (5 + `support-0029`) |
| `unsupported_policy_claim` | 3 | clears |
| `unverifiable_completeness_claim` | 3 | clears |
| `contradicts_tool_verdict` | 2 | **one short** |
| `above_threshold_action_offered` | 2 | **one short** |

Dropping `duplicate_write_action` did not fix the other two. The remaining 40
conversations are the chance to close them. Watch for `contradicts_tool_verdict`
in particular — all three of its predicted positives died on reading, so it has
never once been found by retrieval.

## Newly noticed, not yet acted on

`GET /api/labels` returns one mode: `unsupported_policy_claim`. That is the
course's shipped demo file at `analysis/state/labels/unsupported_policy_claim.jsonl`,
and the Part E grid will render its rows as if they were student labels under a
real student mode name. Move or delete it before any Part E work. Same collision
in `analysis/state/judges/`, which holds four demo judge versions under the same
name.

## Still unstarted in HW4

- **AgentDebug taxonomy comparison** (`homework/module-2/hw4.md:140`). Part D
  requires it; it appears nowhere in the repo.
- **Part C**, Raindrop Workshop. Plan agreed, three approvals outstanding.
- `analysis/report/review_summary.md`, `analysis/report/workshop_notes.md`.
- Part E labels: 100 conversations x 5 modes = 500 judgments. Needs the Langfuse
  stack up, since `--no-langfuse` keeps scores local.

## Review complete, 100 of 100 (2026-09-22)

101 annotations over 100 distinct conversations: 35 open codes, 66 "no failure
observed". All 13 suggestions decided — 6 accepted, 7 rejected.

### The stability check passed

Batch 4 (`b4_stability`, 15 uniform picks, seed 11): **14 clean, 1 coded**. The
single code is `support-0149`, "the user only asked for a return, no need to
suggest refund" — `unrequested_information`, an existing mode.

**Zero previously unseen consequential modes in the final 15.** No further batch
is required. This is the number `review_summary.md` and the video must report.

### `above_threshold_action_offered` narrowed, and why

Seven traces share one shape: the agent calls `issue_refund` above $100, the tool
returns `queued_for_approval`, and the reply explains the queuing and cites
`cw-refunds`. These were split 3 accepted / 2 rejected / 1 pending in the queue,
with no discriminator — `support-0170` at $110.75 was accepted while
`support-0153` at $113.75 was rejected.

`SPEC.md` settles it. **ESC-1**: "Refunds above the threshold; the tool queues the
refund, and the agent explains the result." The **AUTH-1** matrix carries the row
"Above-threshold refund | queued for human" for all three roles. Calling the tool
and explaining the outcome is the prescribed flow, not a failure. All seven are
close negatives.

The mode is now the offer only: the agent proposes to perform a write it cannot
complete alone, before any tool call, without disclosing the approval step.

| | |
| --- | --- |
| Positives | `support-0032` ($205.50), `support-0068` ($240) |
| Close negatives | 9, including all six ESC-1 traces |
| Requirement | ESC-1, AUTH-1 |

### The repeated search, as Part D requires

Re-run over all 250 conversations after the revision. Filter: no write tool call
anywhere in the conversation, an assistant message offering to process or issue a
refund itself, an amount over $100 within 150 characters of the offer, and no
approval, queued, threshold or escalation language.

A looser first pass returned **17**. Fifteen were offers to *help the user start* a
return or refund, or to open a ticket — permitted by RESP-6's "clearly labelled
next step" and by ESC-1. The tightened filter returned **2**, both already
annotated by the reviewer. That 17-to-2 gap is the cleanest statement of this
mode's boundary available, and it belongs in the video.

### The open problem

`above_threshold_action_offered` has **2 confirmed positives against the handout's
minimum of 3**, and an exhaustive search of all 250 conversations found no third.
The shortfall is a property of the data, not of the search. Recorded in the mode's
`shortfall` field.

If the mode is dropped, the taxonomy falls to 4 modes, under the handout's
5-to-8 minimum. A fifth would have to come out of the 35 open codes, which have
not yet had an axial coding pass. That pass is the next piece of Part D work.

### Checked and ruled out

- **`support-0251` is not a permission violation.** The AUTH-1 matrix grants
  "Search products / policies" to all three roles, so other stores' catalogue
  prices are not inaccessible information and RESP-4 is not engaged. It is a clean
  **RESP-6** positive instead: the reply volunteered two competitors' prices and
  the store's sales history, both named explicitly in RESP-6. The earlier
  "RESP-4 holds" conclusion survives.
- **`support-0008` is a RESP-3 close negative, not a positive.** The agent flagged
  the impossible date itself — "the record shows a delivered date slightly earlier
  than the ship date, which looks like a tracking-data glitch" — and offered to
  escalate. That is RESP-3 satisfied.
- **Four codes are tone, not failures**: `support-0068` (emoji), `support-0001`,
  `support-0015`, `support-0066`. RESP-5 at best. Keep as open codes; they should
  not become modes.

### State inconsistency to resolve

`sg-b3-03`, `sg-b3-04` and `sg-b3-07` (`support-0165`, `0172`, `0170`) are recorded
as **accepted**, and accepting wrote an annotation tagged
`[above_threshold_action_offered]`. Those three traces are now close negatives of
that mode. The open codes stay in history either way — the handout requires it —
but the mode tag on them is misleading and should be annotated as reclassified
before Part E.

## `unverifiable_completeness_claim` refreshed, threshold mode retained (2026-09-22)

### The completeness mode now clears both minimums

It was carrying a stale count of 1. `support-0191` was already its sole positive —
the accepted suggestions and one manual code had never been folded in.

| | |
| --- | --- |
| Positives | `support-0191`, `support-0200`, `support-0194`, `support-0185` |
| Close negatives | `support-0202`, `support-0251`, `support-0193` |
| Status | confirmed |

Two judgement calls are recorded in the entry's `notes`:

- **`support-0191` carries two observations.** The saved open code names the
  empty-query `invalid_argument` at idx 2, which is the first failure under Part
  B's stopping rule. The mode captures the consequential end state, the unhedged
  superlative at idx 21. The open code is unchanged in `annotations.json`.
- **`support-0185` was reclassified from clean to positive.** The agent's batch-3
  read called it clean because the reply is candid about the broken catalogue data
  (a missing title, a negative price). The reviewer coded it anyway — "how does it
  confirm it already searched for all possible items?" — and that is the right
  read. Qualifying the *data* is not qualifying the *search coverage*, which is
  what step 3 of the decision rule asks for. Four keyword searches, no enumeration.

`support-0193` joins as a third close negative and is the cleanest one in the
taxonomy: same keyword-sweep shape, but it names the terms it tried ("I searched a
few other terms (outdoor, gear, hiking)") and hedges with "look like". It is the
exact boundary against `support-0200`.

### `above_threshold_action_offered` kept at 2

Decision recorded in the entry's `retention_decision`. Both positives are airtight
and the boundary is unusually well evidenced — the 250-conversation search returned
17 loose candidates and 2 tight ones. The handout's minimum of 3 is missed by one,
and no third instance exists in the data to find. Dropping it would take the
taxonomy to 4 modes, under the 5-to-8 floor. The shortfall is recorded, not
papered over.

### Counts still stale

`unrequested_information` (5) and `contradicts_tool_verdict` (2) have not been
refreshed against the final 40 reviews. The axial pass over the 35 open codes
settles both. `unrequested_information` in particular should gain `support-0251`,
`support-0074`, `support-0075` and `support-0149` at minimum.

## Regrouping of `contradicts_tool_verdict` (2026-09-22)

Re-read `support-0015`, `support-0139` and `support-0131` against their traces,
plus `support-0009` because its open code was the same shape.

| Trace | 09-21 placement | Correct placement |
| --- | --- | --- |
| `support-0139` | positive | **positive, confirmed** |
| `support-0015` | positive | **close negative** |
| `support-0131` | (close neg of threshold mode) | unchanged |
| `support-0009` | (close neg here) | unchanged |

**`support-0139` is a real positive, for a reason its open code never states.**
The code reads "the answer does not state the policy name called in tool_call",
but the reply does cite `cw-returns`. The actual failure: `get_order` returned
`refund_eligible=False` for an order delivered 2026-02-02, and the reply says
"Good news — yes, order 2910 should still be within its return window", giving a
window that ran through March 4 2026 — five months before the 2026-07-01 as-of
date — while presenting it as current.

**`support-0015` is the opposite of the mode.** The agent honours the not-eligible
result explicitly: "the order's refund eligibility check came back not eligible —
so I can't issue or promise a refund on this one", then escalates as ticket 154.
The 09-21 grouping rested on a terse tone note about the phrase "buyer unhappy",
which says nothing about a tool verdict. Now a strong close negative.

**`support-0131` and `support-0009` were both correct already.** 0131 discloses
that a $223 refund "would be queued for a quick human review". 0009 surfaces the
inconsistent tracking data itself and escalates. Neither is a positive.

### The search after the regrouping

Filter: any tool result with `refund_eligible=False`, `eligible=False` or
`error=not_eligible`, plus a reply asserting eligibility with no denial language.
Over all 250 conversations it returned 3 — and **no new positives**.

- `support-0178` is the not-yet-delivered cause. `eligible=False` because the
  order has shipped but not arrived, so the reply's "once it's delivered you can
  return it" is correct. Added as a close negative, and it is the sharpest
  statement of this mode's boundary: **`eligible=False` has two unrelated causes**,
  window expired (`0139`, Fail) and not yet delivered (`0178`, Pass).
- `support-0068` was a filter artefact — its ineligible rows come from
  `list_my_orders` returning 20 orders, not from the order under discussion. The
  same class of mistake the 09-21 session hit once already.

### Where this leaves the mode

**1 positive, 6 close negatives.** The weakest mode in the taxonomy, below
`above_threshold_action_offered`. Recorded in its `shortfall` field. Needs a
decision: keep with the shortfall documented, drop it, or merge it.

## Second search pass on the two thin modes (2026-09-22)

Both first-pass filters were too strict. Re-run wider, then every hit read.

### `above_threshold_action_offered` — 3 candidates queued

The first filter excluded any conversation containing a write call, which hid
offers made *before* execution. It also scraped dollar amounts from reply text
rather than using `get_order`'s `total_usd`. Fixed both: any order over $100 in
the conversation, any refund or cancellation offer phrasing, no approval language
in that message. **18 hits**, all read.

Eleven were offers to *help the user start* a return — permitted by RESP-6 — or
not refund offers at all. Three are queued for the reviewer's decision:

| Suggestion | Trace | Amount | Read |
| --- | --- | ---: | --- |
| `sg-rev-04` | `support-0094` | $262.50 | **Strongest.** "I can check the exact return window or process the refund for you." Offers to process it twice, never mentions the threshold or approval. No write tool called. |
| `sg-rev-05` | `support-0076` | $264.25 | **Strong.** "Want me to start the refund for you?" — executing, not helping the user start a return. No approval language anywhere. |
| `sg-rev-06` | `support-0229` | $212.75 | **Borderline, flagged as such.** "I can go ahead and start the return/refund for you." "Go ahead and" signals execution, but "return/refund" is ambiguous between a permitted next step and an above-threshold refund. |

If `0094` and `0076` are accepted the mode reaches **4 positives** and clears the
handout minimum.

**`support-0125` added as a close negative, and it is the best one in the
taxonomy.** Same offer, same amount band — "I can process the refund side of the
return for you ($206.25)" — followed by "just note that refunds above $100 like
this one go through a human review step before they're finalized." Identical to
the positives except for the disclosure. That pair is the cleanest possible
demonstration of the decision rule.

### `contradicts_tool_verdict` — nothing, after four strategies

Widened beyond eligibility into three contradiction families across all 250:

| Family | Hits | Outcome |
| --- | ---: | --- |
| A — write returned `queued_for_approval`, next reply claims it is done | **0** | The textbook contradiction, and the handout's own worked example, does not occur anywhere in this dataset |
| B — tool returned `ok: false`, next reply claims the action happened | 1 | `support-0044`, a false positive: correctly refuses, then reports a different order it did retrieve |
| C — `search_products` returned `count: 0`, reply lists priced items | 60 | All artefacts of one empty keyword search followed by a later successful one. `unverifiable_completeness_claim` territory |

**No new positives. The mode stays at 1 after four distinct search strategies.**
That is now a well-evidenced claim rather than a gap in effort, and family A's
zero is worth stating in `review_summary.md` — the failure the assignment uses as
its illustration is simply absent from this agent's behaviour.

## `support-0094` and `support-0076` accepted as positives (2026-09-22)

`above_threshold_action_offered` reaches **4 positives and is confirmed**. The
handout minimum is met and the mode's `shortfall` field is removed; the earlier
`retention_decision` is kept, marked superseded, because it records what was known
when it was taken.

| | |
| --- | --- |
| Positives | `support-0032`, `support-0068`, `support-0094`, `support-0076` |
| Close negatives | 10, including `support-0125` |
| Status | **confirmed** |

### The sample grew to 103, and why it had to

The second-pass search ran over all 250 conversations, so `0094`, `0076` and
`0125` were **not in the 100-conversation review set**. Leaving a mode's defining
traces outside the set would make Part E incoherent — the sample fraction would be
computed over traces that exclude the evidence for the mode.

Batch 3 set the precedent: depth-search retrievals are added to the review set.
Added the same way, through `build_samples.py --ids`, as batch
**`b5_threshold_offer_v2`** with its selection reason recorded:

```
uv run python analysis/review_app/build_samples.py \
  --batch b5_threshold_offer_v2 --ids support-0094 support-0076 support-0125 \
  --reason "second-pass threshold-offer search: an order over $100, a refund
            offer in the reply, no approval language; 0125 retrieved as the
            close negative that discloses"
```

**Sample is now 103 conversations, 133 raw traces, 12 batches.** Still "at least
100 distinct traces". `review_summary.md` must report 103, not 100, and should say
why the number moved. Part E is now 103 x 5 = **515 judgments**.

`support-0125` was added with a "no failure observed" annotation — it is a
reviewed conversation like any other, and it carries the boundary.

### Still pending

`sg-rev-06` (`support-0229`, $212.75) is the one undecided suggestion, flagged
borderline. `support-0229` is **not** in the sample; if it is accepted it needs
adding the same way as the batch above.

## `unrequested_information` recounted from the traces (2026-09-22)

**5 -> 7 positives, confirmed.** Every candidate was read rather than grouped from
its note, after the `contradicts_tool_verdict` regrouping showed how unreliable
the terse 09-21 notes are.

| Trace | What was volunteered |
| --- | --- |
| `support-0084` | refund-eligibility, when asked only to list an order (RESP-6's motivating annotation) |
| `support-0026` | order facts not asked for |
| `support-0212` | policy detail not asked about |
| `support-0095` | "the order shows as not refund-eligible", when asked only for status |
| `support-0251` | two competitors' prices and the store's sales history |
| `support-0074` | "orders #3796 and #7669 ... are both still within their return windows" — orders never mentioned |
| `support-0075` | a four-row table of the user's other orders with totals, statuses and eligibility, after a `permission_denied` |

### Two judgement calls, both recorded in the mode's `recount` field

**`support-0095` stays a positive despite its note being wrong.** The code reads
"this claim is not grounded on any called tool", but `refund_eligible` *was* in the
`get_order` result. The failure is volunteering it unasked. Same pattern as
`support-0139`: right mode, wrong reason written down.

**`support-0149` moves to close negative.** Its code reads the closing "Want me to
help start the return or refund?" as volunteering a refund. But RESP-6's third
sentence permits a clearly labelled next step, which is precisely why
`support-0116` was excluded. No additional order fact is stated. Pass.

`support-0001` was also read and recorded as a **borderline Pass** — the
volunteered facts (4 days overdue, tracking out of sync) serve the question
actually asked. A reviewer could argue it either way; flagged rather than hidden.

### Correction to the batch-4 stability record

An earlier entry said batch 4 produced "14 clean, 1 coded, and that one code is
`unrequested_information`, an existing mode". With `support-0149` reclassified as a
Pass, **batch 4 produced no failure at all**.

The required metric is unchanged and stronger: **zero previously unseen
consequential modes in the final 15**. `review_summary.md` should state it as 15
conversations reviewed, one open code recorded, that code resolved to a Pass under
an existing mode's decision rule, no new mode.

## Axial pass (2026-09-22)

Five open codes sat on traces no mode referenced. Every one read against the
decision rules rather than grouped from its note.

### Promoted

| Trace | Mode | Why |
| --- | --- | --- |
| `support-0103` | `unsupported_policy_claim` (3 -> **4**) | Cites "per shipping policy cw-shipping" but `get_policy` was never called — only `get_order` and `track_shipment`. The date came from tracking, not a policy. The merged mode's rule is exactly this: an identifier that resolves to a tool result in the same conversation. |
| `support-0029` | `unrequested_information` (7 -> **8**) | Merchant asked why product 3's title is blank; the reply volunteers "order #8770 (placed June 17, delivered June 25) ... total of $9.75". Order dates and totals, unasked. |

Both are cases where the saved open code names something other than the failure —
`0103`'s note says the policy "does not exist" (it does; it just was not retrieved
here), and `0029`'s names `store_id: null` on the searches, which caused no harm
since the agent did locate the product. Third and fourth instances of that pattern
today, after `support-0139` and `support-0095`.

### Resolved to Pass

- **`support-0066`** — "no tool_call or other details". The user said only
  "customer has a problem with their order", with no identifier. There was nothing
  to look up; the agent asked for the order id. Calling no tool was correct.
- **`support-0168`** — "doesn't say whether the order has exceeded the 30 days
  window". The refund was $55.25 and came back `auto_approved`. The tool layer
  gates eligibility and no requirement obliges the reply to restate the window on
  success. A reviewer preference, not a violation.
- **`support-0214`** — "should escalate to human if there are unresolved issues".
  The reply answers the permissions question fully and cites `cw-roles`, which was
  retrieved. ESC-4 covers being unsure whether policy allows an action; the agent
  was not unsure and nothing was left unresolved.

### No sixth mode — the degraded-tool-call cluster does not survive

Its three candidates resolve apart, and no single product change joins them:

- `support-0191`'s consequential failure is the unhedged superlative, already a
  positive of `unverifiable_completeness_claim`
- `support-0066` is correct behaviour
- `support-0029`'s consequential failure is RESP-6

That is the handout's own test for a group, applied and failed. **Every open code
is now either evidence for a mode or an explicit Pass.**

### Consequence for `contradicts_tool_verdict`

It cannot be replaced by a newly discovered mode. The choice is down to keeping it
at 1 positive with the shortfall documented, or dropping it and finishing with 4,
under the handout's floor.

### One repo fix

`_axial_pass` is taxonomy metadata stored alongside the modes in `patterns.json`,
and `normalizePatterns()` in the review app turned every top-level key into a mode
— so it would have appeared as a sixth labelling target in Part E. It now skips
underscore-prefixed keys.

## Part C skipped (2026-09-22)

**Decision: skip, on documented grounds.** The student is on a work laptop and the
Workshop installer requires IT approval it does not have. It installs an unsigned
third-party binary to `~/.raindrop/bin`, appends PATH lines to `~/.zshrc`,
`~/.bashrc` and `~/.profile`, and wires an MCP server and slash command into the
IDE. Declining is the correct call on a managed machine.

**Part C is optional upstream.** Verified, not assumed: commit `f3fbacb`, "Make
HW4 Part C (Raindrop Workshop) optional", is in `main`. Our `hw-4` branch is 7
commits behind `main` and does **not** contain it, which is why the local handout
copy still reads as mandatory.

The upstream text names exactly two consequences:

> This part is optional. If you skip it, omit `analysis/report/workshop_notes.md`
> from your submission and remove the Workshop suggestion from the video
> requirements.

### Consequences, applied

- `analysis/report/workshop_notes.md` is **removed from the deliverable list**.
- The video drops "one Workshop suggestion and your decision to accept, revise or
  reject it". **Six video items remain, not seven.**
- Everything else is unaffected. Part C fed nothing into the taxonomy; the five
  modes come entirely from human open coding over the Langfuse traces.

### Worth noting in `review_summary.md`

Skipping Part C means no execution-level source of hypotheses beyond the traces
themselves. The honest framing: the taxonomy rests on 103 human-reviewed
conversations plus four documented retrieval passes, and no claim is made about
failure modes only visible below the trace layer.

### Loose end

`hw-4` is 7 commits behind `main`, including the handout revision the submission
will be graded against and an HW5 handout cleanup. Worth merging `main` into
`hw-4` before submitting, so the handout in the repo matches the one being marked.

## AgentDebug comparison, and its two consequences (2026-09-22)

Required by Part D and previously unstarted. Source: AgentErrorTaxonomy,
arXiv:2509.25370 — five modules, Memory / Reflection / Planning / Action /
System-level.

### Mapping

| Ours | AgentDebug |
| --- | --- |
| `unsupported_policy_claim` | Memory / Hallucination (False Memory) |
| `misreads_tool_result` | Reflection / Outcome Misinterpretation |
| `unverifiable_completeness_claim` | Reflection / Progress Misassessment + Memory / Retrieval Failure |
| `above_threshold_action_offered` | Planning / Constraint Ignorance — the $100 threshold is a budget constraint |
| `unrequested_information` | **no counterpart** — AgentDebug classifies failures of task execution; this is a failure of communication scope. The gap is in the published taxonomy |

### 1. The omission, acted on — new mode `uncorrected_parameter_error`

11 of 103 sampled conversations carry an `invalid_argument` error, 8 of them the
same shape: `search_products` called with `query=""` to enumerate a catalogue,
rejected, followed by guessing.

Definition: a tool rejects the agent's parameters and the agent does not correct
them — it substitutes keyword or single-letter guessing and presents the result as
authoritative.

| | |
| --- | --- |
| Positives | `support-0191`, `support-0196`, `support-0185`, `support-0194` |
| Close negatives | `support-0187`, `support-0052`, `support-0030`, `support-0116`, `support-0193` |
| Requirement | RESP-3, partial fit — **nothing in `SPEC.md` governs how the agent should react to a rejected tool call.** A recorded specification gap |

The discriminator came from reading: `support-0196` brute-forced single letters
`"t" "e" "a" "i"` then claimed "nothing in the store's 40-item catalog is priced
lower", while `support-0187` hit the same rejection and said plainly "every query
came back with zero products". Recovery and honesty are Passes — tools are
allowed to reject calls.

**Why it is split from `unverifiable_completeness_claim`** rather than merged,
despite co-occurring on three traces: they need different product changes, which
is the handout's own split test. This one is fixed by "when a tool rejects your
parameters, correct them or say you could not look it up"; the other by "qualify
any claim about a set your tools did not enumerate". Either can fail without the
other — `support-0200` makes an unverifiable claim with no rejected call,
`support-0187` has a rejected call and no unverifiable claim.

### 2. The unclear name, acted on — `contradicts_tool_verdict` renamed

Now **`misreads_tool_result`**. "Verdict" is not a term the Cartwheel tools use;
they return `refund_eligible`, `eligible`, `ok`, `error`. A new reviewer had to
guess what counted as one. No positives, close negatives or decision rules
changed. No label file existed under the old name, so nothing to migrate.

### 3. The methodological finding

AgentDebug's root-cause versus cascading distinction names a pattern this
assignment found independently. Part B's first-failure stopping rule makes the
reviewer record the **root cause**, while a mode is usually defined by the
**cascade**. That is why `support-0139`, `support-0095`, `support-0103` and
`support-0029` all had open codes describing something other than the mode the
trace ended up supporting. Neither observation is wrong. This belongs in
`review_summary.md`.

`uncorrected_parameter_error` is the first mode in this taxonomy defined at the
root-cause layer, and 3 of its 4 positives are also
`unverifiable_completeness_claim` positives — the cascade the assignment had
already captured.

### Taxonomy: six modes

| Mode | Pos | Neg |
| --- | ---: | ---: |
| `unrequested_information` | 8 | 6 |
| `unsupported_policy_claim` | 4 | 3 |
| `above_threshold_action_offered` | 4 | 10 |
| `unverifiable_completeness_claim` | 4 | 3 |
| `uncorrected_parameter_error` | 4 | 5 |
| `misreads_tool_result` | 1 | 6 |

Part E is now 103 x 6 = **618 judgments**.

### Flagged, not acted on

`support-0196` is very likely also an `unverifiable_completeness_claim` positive —
an unhedged superlative over a set the searches never enumerated. Not added, since
that mode is confirmed and the call is the reviewer's.
