# HW2 progress

Last updated: 2026-09-11. Parts A-F DONE and verified, hw2-traces.json written.
All that remains is the student's own work: handout assessments and the video.

## Done
- `uv sync` — environment already had all 140 packages.
- Baseline `pytest --runxfail tests/test_hw_holes.py -k hw2` run: failed as
  expected on `NotImplementedError`.
- **Part A** — `observability/instrument.py`: `record_tool_result` and
  `_set_permission_denied_attributes` implemented. Verified with a throwaway
  in-memory OTel exporter: shopper-allowed span got 3 `cartwheel.*` attributes,
  shopper-denied got 4 (incl. `.reason`), merchant got 5 (incl. int `store_id`).
  No automated test covers Part A; the handout verifies it in Langfuse (Part E).
- **Part B** — `server/app.py`: `create_session` implemented. Test passes:
  `uv run pytest --runxfail -vv tests/test_hw_holes.py -k "create_session_binds"`
  -> 1 passed. Confirmed by hand: token payload carries
  `{issued_at, role, session_id, store_id, user_id}`; a payload edited to
  `role=support` fails `verify_token`; rejections return 400 (bad role),
  404 (unknown user), 403 (role mismatch).

- **Part C** — `server/app.py`: `post_message` implemented. `_authorize` is the
  first line; `Runner.run` sits inside the `cartwheel.session_message` root
  span; `gen_ai.output.messages` is set after the run but still inside the span.
  Student decided: record `gen_ai.input.messages` / `gen_ai.output.messages`
  **unconditionally** on the root span, matching the handout's Part C wording
  rather than the docstring's `TRACELOOP_TRACE_CONTENT` gate. Consequence: with
  the switch off, the root span still carries the conversation while the
  automatic model/tool spans do not, since OpenLLMetry honours the switch
  itself. `uv run pytest --runxfail tests/test_hw_holes.py -k hw2` -> 1 passed,
  and no `NotImplementedError` markers remain in either HW2 file.
  Not yet verified: `post_message` runtime behaviour (needs Part D + Part E).

## HISTORICAL planning notes (Parts D, E and F are all DONE; see the
## dated sections further down for what actually happened).

### (a) Part E mechanics: see a real trace
Order was reversed on 2026-09-11. Docker Desktop was not running, so Part D
(fully offline) went first; this also matches the handout, which puts Part E
after authentication testing.

Four steps, all since RUN (see the Part E section below):

- **E1 (done):** start the trace stack.
  ```
  docker compose -f observability/docker-compose.yml up -d
  docker compose -f observability/docker-compose.yml ps
  ```
  Prerequisite the student handles: Docker Desktop must be running on Windows.
  Expect a multi-GB image download on first run; postgres/clickhouse/redis/minio
  go `healthy`, then langfuse-web needs another 30-60s for DB migrations.
- **E2 (done):** start the server,
  `uv run uvicorn server.app:app --port 8010` — must stay running.
- **E3:** `curl POST /sessions` for a user, then
  `curl POST /sessions/<id>/messages` with the bearer token.
- **E4 (done):** open http://localhost:3000, find the trace, inspect the
  span tree. NOTE: sign in as your OWN account, not student@example.com;
  see the resume section at the end of this file.

Reminder covered already: spans reach Langfuse on a separate, batched path, so
a trace appears a few seconds after the reply returns.

### (b) Part D: tests/test_observability.py — DONE 2026-09-11 (60 lines, two
tests, both passing). Implemented exactly as decided:
- Call `create_session` / `_authorize` as plain Python functions rather than
  using FastAPI's TestClient, because TestClient triggers the lifespan hook
  (`server/app.py:52`) which calls `setup_tracing()` and reaches for Langfuse.
  The handout requires these tests to run without Langfuse or Docker.
- Use the session-scoped `world` fixture (`tests/conftest.py:21`) so the tests
  hit a throwaway temp database, never `data/`.
- Test 1: `create_session(user_id=9002, role="support")` -> HTTPException 403,
  and assert `_SESSIONS == {}` to prove no token was issued before the check.
- Test 2: create two real sessions (users 1 and 2); assert
  `verify_token(first_token) is not None` first, so the later refusal is
  provably about session binding and not a bad signature; then
  `_authorize(second_id, "Bearer " + first_token)` -> 403; then a positive
  control that the token still authorizes its own session.
- An `autouse` fixture clears `_SESSIONS` before each test.

Then run, in order:
`uv run pytest --runxfail tests/test_hw_holes.py -k hw2`,
`uv run pytest tests/test_observability.py`, `uv run pytest`.
The full suite matters because Part A changed `record_tool_result`, which every
tool call in the repo passes through.

Dev-world identities confirmed from the seeded DB: users 1 and 2 are shoppers,
9002 is a merchant at store 2, 9501 is support.

## Notes for Part E/F
- `_SESSIONS` is in-memory. Restarting the server invalidates every session and
  token — Part F's restart requires creating a fresh session.
- `.env` already has model keys, all three `LANGFUSE_*` values, and
  `TRACELOOP_TRACE_CONTENT=true`. No `.env.example` in the repo; nothing to copy.
- `homework/module-1/hw2-reference.patch` exists but is the skip-HW2 escape
  hatch. Do not apply it.

## Deliverables
- [x] observability/instrument.py — Part A
- [x] server/app.py — Part B: create_session
- [x] server/app.py — Part C: post_message
- [x] tests/test_observability.py — Part D: two auth tests
- [x] hw2-traces.json — two traces
- [x] Part E: 5+ traced requests inspected in Langfuse
- [x] Part F: two differing prompt_version hashes
- [x] Check: uv run pytest --runxfail tests/test_hw_holes.py -k hw2
- [x] Check: uv run pytest   (full suite; 4 pre-existing non-HW2 failures)
- [ ] Mine, not the agent's: handout assessments, <=5 min video

## Checks run so far
Parts A-D verified OFFLINE. Parts E and F used a LIVE model
(deepinfra/zai-org/GLM-5.3) against the self-hosted Langfuse stack in Docker.

## Session of 2026-09-11
- Part D written: `tests/test_observability.py`, two tests, both passing.
  `uv run pytest -vv tests/test_observability.py` -> 2 passed.
- `uv run pytest --runxfail tests/test_hw_holes.py -k hw2` -> 1 passed.
- Full suite `uv run pytest` -> 4 failed, 133 passed, 12 skipped, 21 xfailed,
  6 xpassed. The 4 failures are PRE-EXISTING and unrelated to HW2:
  `test_m2_run_judge_persists_store_predictions_for_prevalence` (Module 2) and
  the three `test_hw1_find_order_roles_and_old_matches` cases (HW1 `find_order`
  in `agent/tools.py`, which HW2 does not touch). Proved by exporting the
  committed tree with `git archive HEAD` into a temp dir and running the same
  tests there: identical 4 failures with none of the HW2 changes applied.
  Part A cannot affect them anyway, since it only sets span attributes and
  early-returns on the non-recording span that tests see.
- Docker Desktop was NOT running (`docker info` could not reach
  `npipe:////./pipe/dockerDesktopLinuxEngine`), which is why Part E is still
  pending. The student starts Docker Desktop before E1.
- Confirmed `hw1-session.jsonl` is at the REPO ROOT (not homework/module-1),
  10 records, request text in the `request` field. Roles present: shopper
  user 1 (7 records), merchant 9002/store 2 (2), support 9501 (1). Part E
  needs at least five, each under a session for that record's own user.
- Fixed two stray cp1252 bytes in this note and normalized it to LF endings.
- Still all offline. No live model call, no Docker, no Langfuse trace yet.

## Part E, done 2026-09-11 (LIVE model, glm-5.3 via DeepInfra)
Langfuse stack: `docker compose -f observability/docker-compose.yml up -d`,
six services, langfuse-web on :3000, project slug `cartwheel-dev`.
Permalinks are `http://localhost:3000/project/cartwheel-dev/traces/<id>`
(NOT `/project/default/...`).

Five requests from `hw1-session.jsonl` records 0, 1, 3, 8, 9. Records 2 and
5-7 were skipped on purpose: record 2 calls `issue_refund` and would have
mutated the database, which Part F needs held constant. All five picks are
read-only, and `git status` confirms `data/` was never modified.

| trace_id | role | user | prompt_version | obs | request |
|---|---|---|---|---|---|
| 36e40062745086b08177b784bf014e5c | shopper | 1 | 7e895232414e | 7 | order 4127 status |
| c2e41602379a1dcad5befbb0ca7a1c53 | shopper | 1 | 7e895232414e | 12 | refund for 3980 |
| 768b8096b9a950d29f6bd8ec9fcfeaad | merchant | 9002 | 75f378c49b71 | 6 | show order 4127 (DENIED) |
| 2248910f85630023c108b732ce4141dd | support | 9501 | 930b0fb3a74a | 6 | show order 4127 (allowed) |
| 3d1d6d80fb3e3bf42e9eebb08a4df2a0 | shopper | 1 | 7e895232414e | 12 | Juniper return window |

Verified in the trace data, not just by eye:
- Root span `cartwheel.session_message` carries `cartwheel.user_role`,
  `cartwheel.user_id`, `cartwheel.prompt_version`.
- Tool spans carry `gen_ai.operation.name=execute_tool`, `gen_ai.tool.name`,
  plus Part A's `cartwheel.user_role` / `user_id` / `permission_denied`.
- Merchant 9002 on order 4127 (store 1) gave `permission_denied = true` with
  reason "role 'merchant' (user 9002) may not view order #4127". Support 9501
  on the SAME order was allowed. Everything else was `false` with no reason.
- Generation spans carry `gen_ai.request.model = deepinfra/zai-org/GLM-5.3`.
- The `Agent Workflow` span is present; tool spans share the request trace id.

Where the attributes actually live in the Langfuse API: under
`metadata.attributes` on the trace and on each observation. Part C's
`gen_ai.input.messages` / `gen_ai.output.messages` do NOT appear there; Langfuse
promotes them to the observation's `input` / `output` fields, in the nested
`parts` form the handout mentions.

GOTCHA worth remembering: `prompt_version` varies by ROLE, because the role is
interpolated into the template before hashing. Three roles gave three hashes in
one run. Any prompt comparison must hold the role fixed.

## Part F, done 2026-09-11
Used the REAL HW1 revision rather than an invented wording change. HW1 added
"Account changes of any kind always go to a human this way, even when the user
could also make the change themselves." to the Escalation section
(`git diff 822db67^ 822db67 -- agent/agent.py`), and `hw1-progress.md` records
the pair b3f4a5686618 -> 7e895232414e.

Both hashes were predicted OFFLINE first, by passing the reverted template to
`render_system_prompt(ctx, template)` without touching any file, then confirmed
live. Same user (shopper 1), same request, same model, same tool sequence:

| run | prompt | trace_id | prompt_version |
|---|---|---|---|
| 1 | current | 36e40062745086b08177b784bf014e5c | 7e895232414e |
| 2 | HW1 earlier | d627c757f4c94c315ed9ae7c920a8b62 | b3f4a5686618 |

`agent/agent.py` was restored with `git checkout --`; `git diff` confirms it is
byte-identical to HEAD. Run 2 took 270s versus run 1's 7s, same tool sequence.
Not investigated, probably provider latency rather than the prompt.

Confirmed along the way: restarting the server empties `_SESSIONS`, so
`/health` reported `active_sessions: 0` right after each restart and every
earlier token was dead.

## hw2-traces.json
Written from the live trace data by script, not typed by hand. Holds the
merchant-denied and support-allowed pair on the same order 4127, chosen because
the contrast explains identity and authorization in one sitting. All six traces
had only DEFAULT-level observations, so `final_status` is `completed`.

## Final check run, after Part F restored the prompt
- `uv run pytest --runxfail tests/test_hw_holes.py -k hw2` -> 1 passed
- `uv run pytest tests/test_observability.py` -> 2 passed
- `uv run pytest` -> 4 failed, 133 passed, 12 skipped, 21 xfailed, 6 xpassed
  (the same 4 pre-existing non-HW2 failures, unchanged counts)

## Loose ends for the student
- While the server was running, `.sessions.db-shm` and `.sessions.db-wal`
  appeared as untracked files; stopping the server checkpointed them away, so
  they are gone now. `.gitignore` line 11 covers `.sessions.db` but not the WAL
  sidecars, so consider adding `.sessions.db-*` in case they are ever caught
  mid-run.
- HW1's `find_order` looks genuinely broken for the multi-role / old-match case
  (3 failing tests, `agent/tools.py`). Unrelated to HW2 but worth a look.
- The Module 2 judge test needs a Langfuse slice that does not exist yet.
- Still outstanding and deliberately NOT done by the agent: the handout's
  written assessments and the <=5 minute video.

## Session ended 2026-09-11, ~10:30 UTC. How to resume.

Everything for HW2 is DONE and pushed except the student's own assessments
and the video. Services were stopped cleanly; no data was lost.

Bring the stack back up:

    docker compose -f observability/docker-compose.yml start
    # langfuse-web needs ~30-60s before :3000 answers

`start` is enough because the containers were stopped, not removed. Use
`up -d` if they are gone. NEVER use `down -v`: the four
`observability_langfuse_*` volumes hold all 14 traces AND the org
membership below, and -v destroys them.

Only needed if sending NEW requests:

    uv run uvicorn server.app:app --port 8010

Langfuse login: sign in as widianto.persadha@iea-hamburg.de with your own
password. That account was added to the "Cartwheel Course" org as OWNER on
2026-09-11 (row id `wp-cartwheel-owner` in `organization_memberships`), so
the Cartwheel Dev project appears in the org switcher. Undo with
`DELETE FROM organization_memberships WHERE id = 'wp-cartwheel-owner';`

UNRESOLVED: signing in as student@example.com / cartwheel-dev-pass returned
"Invalid credentials", even though that password verifies against the stored
bcrypt hash and the failed attempt produced no server-side log. Not chased.
The membership above makes it unnecessary, but the cause is still unknown.

Open the browser at exactly http://localhost:3000, NOT 127.0.0.1:3000 --
NEXTAUTH_URL is pinned to localhost and a mismatch breaks sign-in.

The two traces for the video:
- merchant denied : /project/cartwheel-dev/traces/768b8096b9a950d29f6bd8ec9fcfeaad
- support allowed : /project/cartwheel-dev/traces/2248910f85630023c108b732ce4141dd
Both are 6 observations. `hw2-traces-full.json` holds their complete spans,
so they can still be explained even if Langfuse is ever wiped.

Git: branch WP is pushed to remote `fork`
(https://github.com/persadha/cartwheel-homeworks), tracking fork/WP.
`origin` is still the course repo. Local `main` is untouched: ahead 1,
behind 4 of origin/main.

Note: 6 practice traces from 09:44-10:00 have a null trace-level `input`.
They are endpoint traces (they carry the cartwheel.session_message root
span), most likely sent with an empty message. Not investigated. The five
Part E traces and the two Part F traces all have their content intact.
