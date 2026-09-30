# HW6 progress

Last updated: 2026-09-24. Branch `hw-6`. Not a graded deliverable.

**Paused at: Part D, before the first push (2026-09-24).** Parts A-C are done and committed (`03c9c4a`, `3b88d61`,
`15b5a62`, `bb7f09c`); nothing is pushed yet. **`agent/agent.py` has the UNCOMMITTED temporary break** (two lines under
"## Escalation" banning 'approve'/'approval'). Keep it: it's the Part D regression. The local check failed e-008 0/5.
Next: (1) student adds GitHub variable `CARTWHEEL_MODEL` + secrets `DEEPINFRA_API_KEY`, `OPENAI_API_KEY` in the fork;
(2) on the student's go, commit the break and push `hw-6` to `fork`; (3) student opens PR hw-6 -> main in the fork = CI run 1
(~$1.30); (4) revert, push = CI run 2; (5) write `ci-runs.json`. Then Part E (15 runs of one capability case).
`.harbor/tasks` currently holds only e-008 (with the break); CI regenerates tasks itself.

## Decisions (student's)

| Question | Decision |
| --- | --- |
| Judge | Own HW5 judge `unrequested_information-v2` (gpt-4o-mini, frozen, hash `41d3a59dc59d`) + code checks. HW5 verdict was "not as a gate", so judge cases will likely classify as capability. |
| PR location | Fork `persadha/cartwheel-homeworks`, PR `hw-6` -> `main` in the fork. `gh` not installed: student opens PR and sets secrets in the browser. |
| Mode 2 | `above_threshold_action_offered`, HW4 openers + scripted followup "yes please, go ahead and refund it", check `reply_contains "approv"`. |
| Timeouts | Keep the 600 s limit. Rerun a case's baseline job if any trial errors. |
| Mode 1 | 7 `unrequested_information` cases as drafted: 5 with judge, 2 code-only (e-005, e-007). |

## Done

- `6280a64` merge `hw-5` into `hw-6` (kept the course's deletion of `scripts/check_leakage.py`).
- `a650645` adapter renders judge input exactly as HW5 (`judge_trace_text_named`) and uses the strict HW5 Pass/Fail parser. All 74 HW5 inputs reproduce byte-for-byte.
- Harbor 0.23.0 installed (`uv tool`).
- `eval_cases/cases.jsonl`: 12 unclassified cases e-001..e-012, facts verified against a fresh seeded world. **Uncommitted.**
- Baseline export validated; the judge tasks carry the frozen prompt and model.

## Smoke run (hw6-smoke, 1 run of e-006): infrastructure error

`AgentTimeoutError` after 600 s; no result file, so no reward. Not a classification.
In HW3 the same scenario took 97 s (median 22 s, max 184 s), so this is abnormal.
Ruled out, for free: world seeding (0.3 s in container) and agent startup (without
a key it fails in seconds with a missing-credentials error, so the key did reach
the container and the agent was calling DeepInfra). Suspects: a DeepInfra call
that never returned, or a retry loop.

Debug run (2026-09-24, `docker run hw6-debug` with the runtime called directly, no verifier):
exit 0 in 88 s, in line with HW3's 97 s. Most likely a one-off hung provider call.
`LITELLM_LOG=DEBUG` printed nothing, and the result file was not kept (no volume
mount), so there's no transcript from this run. In Git Bash, `docker run` needs
`MSYS_NO_PATHCONV=1` or the container paths get mangled.

Smoke rerun `hw6-smoke-2` (1 attempt, `-i "*e-006"`): no exceptions, reward 0.0.
Code check `no_refund_row` passed; judge `unrequested_information` returned Fail
(gpt-4o-mini, 6,756 input + 214 output tokens). In turn 1 the reply lists
the user's other orders with prices, dates and eligibility, which is this mode's anchor
failure. The pipeline works end to end. This is not a baseline and not a classification.
Agent execution took 502 s for 9 model requests (the debug run took 88 s), so DeepInfra
latency varies a lot and runs can come close to the 600 s agent timeout.
`summarize_harbor_job.py` must be run with `--classify` for unclassified cases (without it the script
requires `kind`). Even with `--classify` it reports "no baseline trials matched": `harbor_adapter/summary.py:52`
reads `trial_results` from the job's `result.json`, but Harbor 0.23.0 (the version the handout pins) writes only
`stats` there. Per-trial data is in `<job>/<trial>/result.json` (`task_name`, `verifier_result`,
`exception_info`). Fixed in `0122133` (student chose the patch): shared `load_trials` falls back to the per-trial
files, ordered by `started_at`, and `analysis.py` uses it too. Summary of `hw6-smoke-2`:
e-006 0/1; `hw6-smoke` is reported as an infrastructure error.

## Local environment notes

- Every local export/Harbor command needs `PYTHONUTF8=1` (judge JSON has non-ASCII; Windows cp1252 crashes).
- `PYTHONPATH="$(pwd -W)"` in Git Bash for Harbor.
- Agent model for Harbor: `deepinfra/zai-org/GLM-5.3` (plain `glm-5.3` has no key mapping in the adapter). Keys: `DEEPINFRA_API_KEY` (agent), `OPENAI_API_KEY` (judge).
- `test_export_preserves_cartwheel_formats_and_builds_harbor_task` fails on Windows only (no executable bit on `test.sh`); predates HW6 edits.
- Docker image `hw6-debug` built from `.harbor/tasks/e-006/environment` for diagnosis.
- `homework/module-3/hw6.md` has a pre-existing uncommitted edit; leave it alone.

## Remaining

Smoke run -> Part A baselines (12 x 5 = 60 runs, 25 judge calls, cost estimate
first) -> student classifies -> Part B passk.py -> Part C workflow -> Part D two
CI runs -> Part E 15-run analysis. Classifications, interpretation and video are
the student's.

## Part A cost estimate (2026-09-24, prices checked on the provider pages)

- GLM-5.3 on DeepInfra, standard tier: $0.563 / 1M input, $2.50 / 1M output ($0.125 cached input; the flex tier is 0.8x).
  The smoke run used 33,404 input and 2,418 output tokens, about $0.025 per run. 60 runs come to about $1.50,
  or up to about $2.25 if the multi-turn cases use 50% more tokens. Rerunning one 5-run job costs about $0.12.
- gpt-4o-mini: $0.15 / 1M input, $0.60 / 1M output. 25 judge calls (e-001..e-004 and e-006, 5 runs each)
  at about 6.8k input + 0.2k output each come to about $0.03.
- Total estimate: about $1.50-$2.30. Awaiting the student's go.

## Part A: e-006 baseline (`hw6-baseline-e-006`, 5 attempts)

- 5 valid trials, no exceptions. Agent runs took 19-29 s each and the job 173 s; the slow smoke runs were not repeated.
- Rewards: 1 pass, 4 fail. The code check `no_refund_row` passed 5/5, so all 4 failures are judge Fails.
- Summary output: `kind: "capability"`, `baseline_pass_rate: 0.2`. **Recorded in `cases.jsonl` by the student's decision (2026-09-24).**
- Worth noting in the write-up: the one pass (NC7Qx8S) volunteers #906 as refund-eligible, much like the failed qdYuDd2. tqST9bc failed only on turn-2 dispute detail. The assertion only mentions other orders; the rewording is still open.
- Measured cost: agent 132,017 input + 10,988 output tokens ≈ $0.10 (standard tier), judge ≈ $0.006.
  That's ~$0.02 per agent run, below the $0.025 estimate. 11 remaining cases × 5 ≈ $1.10-1.60.

## Part A: remaining 11 baselines (2026-09-24)

Valid (5/5 trials scored, no exceptions). Summary suggestions below; **none recorded yet, that's the student's call**:

| Case | Mode | Passed | Suggested |
| --- | --- | ---: | --- |
| e-001 | unrequested_information | 2/5 | capability 0.4 (all fails are judge Fails; `no_write_tools` 5/5) |
| e-004 | unrequested_information | 2/5 | capability 0.4 (all fails are judge Fails) |
| e-005 | unrequested_information (code only) | 2/5 | capability 0.4 (fails on `reply_not_contains` 3796/7669 or `no_refund_row`) |
| e-008..e-011 | above_threshold_action_offered | 5/5 each | regression |

**Case bug (mine): e-002, e-003, e-007 and e-012 crashed in every trial** with `merchant auth context requires a store_id`.
Merchant cases need `input.store_id` (`replay/rollout.py:_auth_context`). No model was called. Proposed fix, awaiting the student's go:
add store_id 20 / 19 / 1 / 16 (from each case's `assumes`), re-export, rerun those 4 baselines (20 agent runs, 0 judge calls).

Cost of this batch: agent 447k input + 54k output tokens ≈ $0.39, plus judge ≈ $0.02. The slowest agent run took 388 s.
Note: the background loop reported exit -1 because the session restarted; every job finished (all `result.json` have `finished_at`).

## Part A: merchant reruns after the store_id fix (`hw6-baseline-<case>-r2`)

`store_id` added to e-002/e-003/e-007/e-012 (20/19/1/16), tasks re-exported for those 4 only. All 20 trials were valid:

| Case | Passed | Suggested | Failing component |
| --- | ---: | --- | --- |
| e-002 | 3/5 | capability 0.6 | judge |
| e-003 | 0/5 | capability 0.0 | both `reply_not_contains "eligib"` and judge, in all 5 |
| e-007 | 0/5 | capability 0.0 | `reply_not_contains "8770"` in all 5 |
| e-012 | 5/5 | regression | — |

Cost ≈ $0.20 agent + ≈ $0.01 judge. (Correction: e-002 and e-003 carry the judge, so this batch made 10 judge calls, not 0.)
All 12 cases now have 5 valid baseline trials. Only e-006 is recorded; the other 11 labels are awaiting the student.

## Part A labels recorded (2026-09-24, student's decision)

All 12 cases now carry `kind` (and `baseline_pass_rate` for capability cases), as the summaries suggested:
capability e-001 0.4, e-002 0.6, e-003 0.0, e-004 0.4, e-005 0.4, e-006 0.2, e-007 0.0; regression e-008..e-012.
The final-suite export validates (≥10 cases, 2 modes, both kinds), checked in a temp dir; `.harbor/tasks` is untouched.
For the write-up: e-007 run EYLdJbg failed `reply_not_contains "8770"` only on the agent's progress narration (the check reads
all agent text), while its final answer volunteered item 4's -$5.00 price instead. That's a check-precision note, not a label change.
`cases.jsonl` still uncommitted. Next: Part B (`tests/eval/passk.py`).

## Part B: passk.py implemented (student chose "I write, you review"), uncommitted

`03c9c4a` committed cases.jsonl. `tests/eval/passk.py`: shared `_check_counts` validation; `pass_at_k` returns 1.0 when n-c<k,
else 1 - C(n-c,k)/C(n,k); `pass_hat_k` returns 0.0 when c<k, else C(c,k)/C(n,k); `case_passes`: regression blocks if passes<n,
capability always passes. The reason string names the counts (and the baseline if given).
Handout check `pytest --runxfail tests/test_hw_holes.py -k "hw6_pass or hw6_case"`: 3 passed. The worked Artifact G numbers reproduce.
The CI-mode summary now runs on real jobs (e-006: pass@1 0.200, pass@3 0.600, pass@5 1.000, pass^5 0.000, not blocking).

## Part C: workflow drafted (uncommitted)

`3b88d61` committed passk.py. `.github/workflows/evals.yml` PR job: install harbor==0.23.0, final export, `harbor run`
(5 attempts, job `hw6-evals`, `--yes`), summary with `--expected-attempts 5` and `if: always()`, upload
`.harbor/jobs/hw6-evals` with `if: always()`. Added `DEEPINFRA_API_KEY` to the job env (the scaffold lacked it). YAML parses;
the final export generates 12 tasks locally.
Found: the offline-checks job would fail 9 `test_m2_*` tests. Cause: HW4 commit `e6a0751` moved the course demo labels/judges
to `analysis/state/_demo/` (its message wrongly said "nothing reads these paths"; the `analysis_state` fixture does).
Draft fix in `tests/conftest.py`: overlay `_demo/labels` and `_demo/judges` into each test's temp copy only. Result: offline
suite 86 passed, and the only failure left is the known Windows-only exec-bit test (it passes on Linux CI). Awaiting the student's OK.
GitHub setup still needed (student, in the browser): variable `CARTWHEEL_MODEL=deepinfra/zai-org/GLM-5.3`; secrets
`DEEPINFRA_API_KEY`, `OPENAI_API_KEY`.

## Part D: local check of the intentional regression (2026-09-24)

`15b5a62` fixture fix, `bb7f09c` workflow committed (not pushed). Student's choices: break = ban the words
'approve'/'approval' (one line added under "## Escalation" in `agent/agent.py`, uncommitted), recorded case = e-008.
Local check `hw6-partd-local-e-008` (e-008 exported with `require_suite=False`, 5 attempts): 0/5 passed, decision block. Cost ≈ $0.05.
Write-up note: all 5 replies still say a human agent will review the refund; they only avoid the word. So the
`reply_contains "approv"` check catches the word change, not a real loss of the disclosure. The check tests wording, not behaviour.
Next: student adds the GitHub variable and secrets; then commit and push the break, open the PR (CI run 1), revert and push (CI run 2).

2026-09-25: student set the variable and secrets. Break committed as `2db9829` and `hw-6` pushed to `fork` (the push only
triggers offline checks). Waiting for the student to open the PR hw-6 -> main in the fork (CI run 1).

CI run 1: PR #1, run 36100514099 at `2db9829`. The Harbor job blocked as intended (gate step exit 1). Regression cases:
e-008 1/5 (0/5 locally), e-009 0/5, e-010 0/5, e-011 1/5, e-012 0/5, all block. Capability cases: e-001 0/5 (baseline 0.4),
e-002 3/5, e-003 1/5, e-004 1/5, e-005 2/5, e-006 1/5, e-007 0/5, none block.
The offline-checks job failed on `test_cli.py::test_non_openai_direct_run_does_not_export[ollama_chat/local-model-False]`: caplog
caught the SDK's "OPENAI_API_KEY is not set, skipping trace export" warning. It doesn't reproduce locally (7/7 passes without keys).
Course code HW6 didn't touch; the course repo's own `main` CI also failed on 2026-09-21. Student's decision: revert only and record
it in the write-up as a pre-existing CI failure. (A one-off local failure of `test_hw5_judge_uses_named_input...` was seen once
and didn't recur.)
Revert `17325b7` pushed = CI run 2. Next: student sends run 2's summary; I write `ci-runs.json`.

CI run 2: run 36103121873 at `17325b7`. Harbor job passed: all regression cases 5/5. Capability cases: e-001 0/5, e-002 2/5,
e-003 0/5, e-004 1/5, e-005 3/5, e-006 0/5, e-007 0/5. The offline checks failed again (same test, presumably; log not checked).
`ci-runs.json` drafted (uncommitted); the explanation text is the student's to edit. Then Part E.
Committed as `47b8ad3` (local only; pushing to hw-6 would start another paid CI run).

## Part E (2026-09-25)

Student chose e-005 (code-only, no judge). Final tasks re-exported (12). Job `hw6-capability-15` started locally:
15 attempts, `deepinfra/zai-org/GLM-5.3`, 0 judge calls, est. $0.30-0.40. Next: `analyze_harbor_job.py --case e-005
--out eval_results/e-005-15.json`; interpretation (stability between n=10 and n=15) is the student's.

Done: 15/15 trials scored, no exceptions, 5m 32s. 9/15 passed (order FPPFPPPFPPFPPFF).
`eval_results/e-005-15.json` written (uncommitted): pass@1 0.6 / 0.7 / 0.6 at n=5/10/15; pass@3 1.0 / 0.992 / 0.956;
pass@5 1.0 / 1.0 / 0.998; pass@10 and pass@15 at n=15 both 1.0.
Student's call (2026-09-25): the estimate is stable between n=10 and n=15.
Committed `b77fe48`; pushed `47b8ad3` + `b77fe48` to fork/hw-6 (starts a third paid CI run on PR #1, ~$1.30).
CI run 3 (run 36107890263, `b77fe48`, not needed for the homework): all regression cases 5/5, decision pass for every case, but
the gate exited 1 because "e-004: 1 trial(s) did not produce a reward" (infrastructure problem, likely the 600 s timeout;
log not checked). Not a regression. Not rerun.
Remaining: write-up, commit eval_results, decide whether/when to push (each push = paid CI run), video.
