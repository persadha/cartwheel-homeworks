# HW4 progress

Last updated: 2026-09-19. Branch `hw-4`. Steps 0 to 3 DONE (preparation,
stock-view review, layout proposal, interface fork). Part A complete, including the
verified Langfuse score write.

**Step 4 (Part B, open coding) is IN PROGRESS and PAUSED.** Batch 1 is built
(30 conversations) and 1 of those 30 is open-coded. Nothing is running: the review
app server has no live process and the Docker/Langfuse stack is stopped. No volume
was destroyed. Before open coding can resume, read "Blocker found 2026-09-19"
below — the interface cannot currently record "no failure observed".

Working style: student drives. The agent proposes each step in plain language
and waits for an explicit "go" before running or changing anything. Every
judgment about what counts as a failure is the student's. The agent organizes,
computes and scales; the human notices and decides. Assessments and the
<=5 minute video are the student's own work.

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
  **Still open** — put to the student on 2026-09-19, not yet answered. The
  alternative is counting raw traces, which would stop the review at roughly 78
  conversations.
- **Trace source while Docker is down.** Open coding needs nothing from Langfuse:
  `analysis/state/samples.json` already carries every conversation's text, tool
  calls and tool results. Running `--no-langfuse` costs only the turn permalinks,
  which will not open. Docker becomes necessary again at Part E, for the score
  writes. **Still open** — put to the student on 2026-09-19, not yet answered.

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

## Blocker found 2026-09-19, resolve before open coding resumes

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

Proposed fix, needing the student's approval: a "No failure observed" button in the
trace header that pushes an annotation with `quote: null`,
`note: "no failure observed"`, `source: "clean"`. No server change is needed, and
no renderer change either — `layoutMargin` already guards on `it.quote`
(line ~641) and `applyHighlights` already skips quote-less items (line ~599), so
the note lands in the margin column without a highlight. Optional companion: a
"jump to next unreviewed" control beside the existing prev/next buttons.

This fix would itself be a further honest adaptation of the reference interface,
and belongs in `analysis/report/interface_comparison.md` if it is made.

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
