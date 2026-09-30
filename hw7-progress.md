# HW7 progress

Last updated: 2026-09-28. Branch `hw-7`. Not a graded deliverable. Plan: `~/.claude/plans/guide-me-through-homework-jiggly-squirrel.md`.

## Decisions (student's)

| Question | Decision |
| --- | --- |
| Judge | Own HW5 judge `unrequested_information-v2` (gpt-4o-mini, frozen, hash `41d3a59dc59d`). Test Se (failure) 16/18 = 0.8889, Sp (pass) 3/11 = 0.2727, so Se+Sp-1 = 0.162. |
| Cartwheel model | `glm-5.3` (as HW3; maps to `deepinfra/zai-org/GLM-5.3`) |
| Risk groups | `policy_lookup`, `multi_turn` (chosen 2026-09-28, before any HW7 judging) |
| Threshold | 0.15 (chosen 2026-09-28, before any HW7 judging) |

## Done

- Step 0: merged `hw-6` into `hw-7` (`746b3a2`, local, no conflicts). `judge_test_data` loads 29 test pairs.
- Langfuse (local Docker) has the HW3 run: 50/50 scenario ids, 62 traces, 2026-09-15 15:12:30.531Z to 17:34:24.053Z (trace start times), no retries among the 50. The window also contains other HW3 scenarios, so the monitor filters to the 50 ids.
- Risk-group sizes over the 50 HW3 conversations (tool names and turn counts only): policy_lookup 23, write_action 5, multi_turn 9.

## Findings to carry into Part B

- `monitoring/run_judges.py:_decode_judge_rows` is lenient (unknown verdict -> fail); HW5 `scale.py:42-60` raised. Make it strict (show diff first).
- HW5 input text = per-conversation concat of normalized `trace` messages -> `analysis/run_judges.py::_judge_messages` -> `normalization._flatten`. Not `normalize_trace()["text"]`.
- HW3 traces have no session id; group by `metadata.attributes["cartwheel.scenario_id"]`. Record id = final trace id.
- Model only on GENERATION observations.

## Part A (2026-09-28): done

- First attempt refused before any request: the course added a required `tuple.user_style` to `scenarios/validate.py`
  in `82abd6f` (2026-09-11), after the HW3 run; the 50 HW3 scenarios lack it. Nothing spent.
- Student's choice: skip only that check. Scratchpad wrapper (not committed) validates a copy with a placeholder
  `user_style` and plays the original scenarios with the unchanged `scenarios.runner` code.
- After run: 2026-09-28T21:33:48Z to 21:43:05Z, 50/50 completed, 62 turns, model `glm-5.3`, no errors.
  Durations 2.3-54 s, median 7 s (HW3 median was ~22 s).
- Langfuse check: before 62 traces / 50 ids (no session ids); after 62 traces / 50 ids / 50 session ids; every
  GENERATION model is `deepinfra/zai-org/GLM-5.3` in both.
- Fact for the write-up: the agent's system prompt changed since HW3 (course added "You MUST explain your reasoning
  in plain text before every tool call" in `agent/agent.py`), and `prompt_version` now hashes the template.
- `monitoring/config.json` written (before window padded to 15:12:00Z-17:36:00Z). Uncommitted.

## Next

**Paused 2026-09-29 in Part B, step 1.** Plan: `~/.claude/plans/resume-last-session-composed-thacker.md`.

- Decision (2026-09-29): the student writes `select_traces` themselves, and Claude reviews it (as in HW6).
- `monitoring/sample.py` is a work in progress by the student (uncommitted, don't overwrite). It has 2 lines so far:
  - the count formula (correct, but named `random_sample`)
  - `group = [g for groups in traces]` (NameError, doesn't use `risk_groups`)
- Review given, plus a walkthrough of the 5 parts using analogous examples:
  1. ValueError checks
  2. `random.Random(seed).sample` + `import random`
  3. a dict of lists per group
  4. dedupe by id with a seen-set
  5. return the dict and delete the raise
- 2026-09-30 (plan `resume-last-session-for-cozy-parasol.md`): the student had added the checks and the count. Review given:
  missing `)` on the count line (SyntaxError), `"id" not in traces` should be `item`, `.sample` stored rather than called,
  typo "musi" plus a stray `)` in the message. Parts 3-5 not written yet. Waiting for the student's next version.
- On resume: review the student's code, then run `uv run pytest --runxfail tests/test_hw_holes.py -k hw7_sampling`.
- Then: strict parser (show diff), `run.py`, free input check against `hw5_trace_inputs.json`.

**Paused again 2026-09-30.** Everything is committed and pushed to `fork/hw-7`, including the unfinished
`monitoring/sample.py` (it has a SyntaxError, so offline CI fails `hw7_sampling` until it's finished). No PR exists for `hw-7`.
Opening one would start the paid Harbor job (~$1.30 per push). Langfuse Docker left running.
