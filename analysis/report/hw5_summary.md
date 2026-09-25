# HW5 summary — an LLM judge for `unrequested_information`

Branch `hw-5`. Judge frozen and tested 2026-09-22.

**Headline.** The judge agrees with the human on **27% of Pass cases** and **89% of
Fail cases** on 29 held-out conversations. Both intervals are wide. It is not
usable as a gate. It is arguably usable as a screen, but the data cannot establish
that, and saying so is the main result.

## 1. The failure mode

`unrequested_information`, carried over from the HW4 taxonomy: *the reply states a
fact about an order, a sale, eligibility status or a policy that the user did not
ask for and that answering the question did not require.* Backed by **RESP-6**,
which HW4 added to `SPEC.md` for this mode.

Full definition, decision rule, boundary and the revision made during HW5:
[`hw5_failure_mode.md`](hw5_failure_mode.md).

Chosen over the other five HW4 modes because it had the most confirmed positives
(11), because HW4 had already marked it "LLM judge — deciding what the question
required is a judgment call", and because its boundary against a permitted closing
offer is sharp enough to argue about on camera.

## 2. Why not a code check

`write-judge-prompt` requires ruling out a deterministic evaluator first. One was
built and measured rather than dismissed.

`run_judges.py::screen_conversation` scores four regex signals drawn from the
decision rule — eligibility stated where the user never raised it, order numbers
the user never mentioned, volunteered sales history, volunteered dates or prices —
over declarative sentences only, so permitted closing offers do not trigger it.

Of the 145 conversations HW4 never reviewed, 54 carried a signal and 91 did not. A
blind random sample of 25 was drawn from the 91 and read: **13 of the 25 were
Fails.** The screen misses roughly half the mode. It is kept as a reading order,
never as an evaluator.

## 3. Labels

**74 conversations: 28 Pass, 46 Fail.** One record per conversation, keyed by a
canonical trace id. `1 = Pass`, `0 = Fail`, per the handout. The file is
append-only: a changed label appends a row and stamps `superseded_by` on the one it
replaces, so 83 rows on disk collapse to 74 live labels and the full history
survives.

| Source | n | Fail |
| --- | ---: | ---: |
| HW4 `human` labels, carried over | 19 | 11 (58%) |
| `hw5_screen` — regex-ranked candidates, read for HW5 | 30 | 20 (67%) |
| `hw5_random` — blind sample of unscreened conversations | 25 | 13 (52%) |

### The 86 labels that were excluded

HW4's Part E produced `human`, `code_gate` and `reviewer_accepted` labels, the last
accepted in bulk rather than read one at a time. HW4's own report kept them
distinct and predicted the problem: *"HW5 draws its ground truth from these files,
so how firmly each label was established is itself evidence."*

Every batch a human read runs 52–67% Fail. The 86 `reviewer_accepted` labels are
**0/86**. That gap is a property of the labelling, not the traces — and 48% of the
86 carry a screen signal, meaning they look like the conversations just labelled
Fail. Keeping them would have put a large one-directional error into the Pass
class and scored the judge wrong for calling them correctly.

They are archived with their reason in `hw5_labels/_excluded_bulk_accepted.jsonl`.
HW4's files are untouched, so HW4's Part E stands as submitted.

### Eight labels changed during HW5

Four from the boundary revision made before any judge ran, four from the dev
disagreement review. All are listed with reasons in `hw5_failure_mode.md` §
*Boundary revision* and in the `comment` field of each row.

## 4. Splits

`split_labels(fractions=(0.20, 0.40, 0.40), seed=7, min_per_class=10)`, run once
and not touched again. `analysis/state/splits.json`.

| Set | Pass | Fail | n |
| --- | ---: | ---: | ---: |
| Train | 5 | 10 | 15 |
| Dev | 12 | 18 | 30 |
| Test | 11 | 18 | 29 |

Judge input is `hw5_trace_inputs.json`: one record per conversation, `trace_id` and
`trace` and nothing else. Built from a whitelist rather than by deleting fields, so
a field added to the sample later cannot reach the judge, and checked against the
reviewer's own notes to confirm none appear in what the judge reads.

## 5. Prompt versions

Model `gpt-4o-mini` throughout, as the handout requires. Two revisions, the limit.

| Version | Change | Dev TPR | Dev TNR | Agreement |
| --- | --- | ---: | ---: | ---: |
| v0 | First draft: criterion, 4-step rule, offer/statement distinction, 3 examples | 0.000 | 1.000 | 0.600 |
| v1 | Revision 1 | 0.333 | 0.944 | 0.700 |
| v2 | Revision 2 — **frozen** | 0.333 | 1.000 | 0.733 |

Dev figures are against the final labels, so all three are comparable.

**v0 returned Fail on all 30 dev conversations.** Its TNR of 1.000 was worthless —
a judge that always says Fail catches every Fail by construction, and its 0.600
agreement was simply the Fail share of the split. This is the handout's warning
about agreement, mirrored.

**v1** relaxed the rule: the answer can never be the unrequested fact; the
eligibility rule governs an order's eligibility *status*, not the word "refund";
disambiguation is in scope; identifying detail is in scope; a reply need not be
minimal. Examples rebalanced to 2 Fail / 3 Pass and a second Fail shape added, so
the judge would not learn that eligibility is the only way to fail.

**v2** changed the shape of the task instead of adding more exceptions. v1 was a
strict rule followed by a growing list of carve-outs, and the judge applied
whichever it had read last. v2 replaces subtraction with a **naming test**: to
return Fail it must complete *"The reply states ___, which belongs to ___, a record
or topic the user never raised"*, quoting a fact and naming one of five categories.
If it cannot fill both blanks, the answer is Pass.

**A withdrawn v2.** The first v2 quoted two sentences verbatim from dev
conversations (`support-0117`, `support-0082`), which would have let the judge
pattern-match those traces. A content-level leakage check caught it before the
version ran. The sentences were replaced with generic phrasing, the unrun record
was withdrawn, and the corrected prompt registered as v2. The leaked text is kept
at `analysis/prompts/unrequested_information-v2-withdrawn.txt`.

### Why revision stopped

The handout allows two, and two were used. Two specific defects in v2 were
identified but not fixed, and they are named in §8 rather than repaired, because
fixing them would have been a third revision.

## 6. A development disagreement

**`support-0087`** — the clearest case of the reviewer being wrong rather than the
judge.

The user asked *"whats the status of my Portable Journal order, 8454"*. The reply
gave the status and timeline, then added: *"**Refund:** $160.50 has been refunded,
so no further refund is available on this order."*

It was labelled **Pass**. Judge v0 called it **Fail**.

The judge was right. The order's status is "delivered, refunded", which is
responsive — but *"no further refund is available"* is an eligibility statement,
and the user never raised refunds. That is exactly what the boundary revision made
earlier the same day had ruled out. The label predated the reviewer's own rule.

It was flipped to Fail, with the reason recorded in the row. Three further labels
moved the other way after v1 — `support-0046`, `support-0204` and `support-0055`,
all cases where the reviewer had been stricter than the rule allowed.

**Four of the twelve dev disagreements were labelling errors, not judge errors.**
Correcting them moved v1's dev TPR from 0.111 to 0.333 and its TNR from 0.810 to
0.944 without changing a single prediction. That is the strongest argument in this
assignment for inspecting disagreements one at a time instead of reading the
headline rate.

## 7. Test result

`unrequested_information-v2`, frozen, scored once on 29 held-out conversations.

| | Judge Pass | Judge Fail |
| --- | ---: | ---: |
| **Human Pass** | 3 (TP) | 8 (FN) |
| **Human Fail** | 2 (FP) | 16 (TN) |

| Metric | Value | 95% Wilson interval |
| --- | ---: | --- |
| **TPR** = TP/(TP+FN) = 3/11 | **0.273** | **0.098 – 0.566** |
| **TNR** = TN/(TN+FP) = 16/18 | **0.889** | **0.672 – 0.969** |
| Agreement | 0.655 | |

Class counts: 11 human Pass, 18 human Fail.

**Dev to test.** TPR 0.333 → 0.273 and TNR 1.000 → 0.889. Both fell, as expected:
dev is where the prompt was tuned. TNR is the telling one — a perfect dev score
became 0.889 on fresh data, so two real failures slipped through where none had
before. Reporting the dev TNR as the judge's detection rate would have overstated
it.

## 8. Would I use this judge?

**Not as a gate.** TPR 0.273 means roughly three of every four acceptable replies
are condemned. Any process that blocked, escalated or retried on this verdict would
be acting on false alarms most of the time.

**As a screen, the honest answer is "not proven".** TNR 0.889 — 16 of 18 real
failures caught — is the shape a screen needs. But the interval runs 0.672 to
0.969. With 18 test failures, the data is equally consistent with the judge missing
a third of them. "Catches about nine in ten" is not a claim these 29 conversations
can support. The interval, not the point estimate, is the result.

**The limit is the label count, not the prompt.** Both intervals are wide because
the splits are small. No further prompt work narrows them; only more labelled
conversations would.

### The two defects that would be fixed first

Both are faults in the prompt, both were found in the dev critiques, and together
they account for four of the eight test-set misses' dev equivalents.

1. **The judge reads tool results as though the assistant had said them.** On
   `support-0082` the critique states *"The reply states 'refund eligible: true'"*
   — the reply says no such thing; `refund_eligible: true` appears only in the
   `get_order` tool result. The prompt says "the assistant's reply" but never says
   tool results are evidence rather than output.
2. **It forces observations into category 5.** On `support-0046` it quotes *"None
   of your orders are currently in transit"* and calls it refund eligibility status.
   Transit status is not eligibility. The naming test requires a category, so the
   model picks the broadest-sounding one instead of returning Pass. The categories
   need an explicit "if none fits, the answer is Pass".

`validate-evaluator` also suggests a more capable model when alignment stalls. The
handout fixes the judge model at `gpt-4o-mini`, so that was not tried, and it
remains an untested explanation for part of the gap.

## 9. Limitations

- **The Fail class is partly screen-derived.** 20 of 46 Fails came from
  regex-ranked candidates. The 25-conversation blind slice is the control, and it
  found failures at a similar rate (52% against 67%), which argues the screen
  ranked rather than defined the class — but it is one sample of 25.
- **28 Pass labels is thin**, and it is the Pass class that drives the TPR
  interval. Reaching the handout's 30 was possible only before the bulk-accepted
  labels were excluded.
- **One labeller.** Every judgment is the same person's, so no inter-annotator
  agreement can be reported, and the boundary revision mid-assignment means early
  and late labels were made under slightly different rules. The eight corrected
  labels are the visible part of that; others may remain.
- **Prevalence is not estimated.** The optional Rogan–Gladen extension was not
  attempted; the sample is deliberately enriched and would not support it without
  a fresh random draw.

## 10. Files

| Artifact | Path |
| --- | --- |
| Failure definition and boundary revision | `analysis/report/hw5_failure_mode.md` |
| Labels and evidence | `analysis/state/hw5_labels/unrequested_information.jsonl` |
| Excluded bulk-accepted labels | `analysis/state/hw5_labels/_excluded_bulk_accepted.jsonl` |
| Splits, judge inputs, review queue | `analysis/state/splits.json`, `hw5_trace_inputs.json`, `hw5_samples.json` |
| Prompts, including the withdrawn draft | `analysis/prompts/` |
| Judge records, predictions, critiques | `analysis/state/judges/` |
| Code | `analysis/run_judges.py`, `analysis/review_app/` (`--hw5`) |
| Metrics | `analysis/report/dev-*.json`, `analysis/report/test-unrequested_information-v2.json` |

Total model spend: roughly $0.06 across four `gpt-4o-mini` batches.
