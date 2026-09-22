# HW4 review summary

Human trace review and failure taxonomy for the Cartwheel support agent.
Branch `hw-4`. Review completed 2026-09-22.

## 1. The reviewed sample

**105 conversations, 136 raw Langfuse traces, drawn from a population of 250.**

A counting convention matters here: the handout asks for at least 100 traces, and
this review counts **conversations**, not raw traces. Cartwheel emits one trace per
turn, so a four-turn conversation is four traces. Conversations are the unit
because a failure that only exists across turns cannot be judged from one turn.
Either way the minimum is met — 105 conversations, 136 traces.

Traces are grouped by `cartwheel.scenario_id` rather than `cartwheel.session_id`.
The session id varies within a single conversation in this trace store, so
grouping on it would have split conversations apart.

### Composition

| Role | n |
| --- | ---: |
| shopper | 53 |
| merchant | 27 |
| support | 25 |

17 of the 105 call a write tool (`issue_refund`, `cancel_order`,
`escalate_to_human`).

### Batches, and how each was selected

| Batch | n | Selection |
| --- | ---: | --- |
| `b1_uniform` | 15 | uniform random, seed 7 |
| `b1_cluster` | 15 | cluster representatives, seed 7 |
| `b2_role` | 30 | balanced across user role, 10/10/10 — the dimension was chosen before looking at any outcome |
| `b3_threshold_offer` | 3 | refund offered, order over $100, no approval language |
| `b3_threshold_negative` | 6 | `issue_refund` above $100 **with** approval language — retrieved as close negatives |
| `b3_completeness` | 2 | 3+ product searches returning empty, then an unhedged superlative |
| `b3_eligibility_negative` | 3 | a not-eligible tool result the reply handled correctly — close negatives |
| `b3_permission` | 4 | `permission_denied` results |
| `b3_malformed_call` | 4 | `invalid_argument` the agent worked around |
| `b3_lookup_failure` | 3 | `not_found`, including one repeated identical call |
| `b4_stability` | 15 | uniform random, seed 11 — drawn and reviewed **after** the taxonomy was drafted |
| `b5_threshold_offer_v2` | 3 | second-pass depth search after a definition revision (see §6) |
| `b6_ambiguous_refund_offer` | 2 | third-pass search after the ambiguity revision (see §6) |

All four batch types the handout requires are present. No conversation counts
toward more than one batch.

**The sample grew from 100 to 105.** Twice, a search run after a definition
revision retrieved conversations that were not in the original review set — three
for `b5_threshold_offer_v2` and two for `b6_ambiguous_refund_offer`. Leaving a
mode's defining traces outside the set would make the Part E sample fractions
incoherent, so both batches were added with their retrieval filters recorded,
following the precedent set by the `b3_*` depth searches.

### Review volume

107 annotations over all 105 conversations: **40 open codes and 67 "no failure
observed"**. Every conversation in the set was reviewed. Suggestion queue: 17
raised, **10 accepted and 7 rejected — all decided**.

## 2. The taxonomy

Six binary failure modes. Each carries a decision rule another reviewer can apply,
close negatives drawn from real traces, a boundary against its nearest neighbour,
a likely evaluator type and a requirement source. All of it is in
`analysis/state/patterns.json`.

| Mode | Positives | Close negatives | Requirement | Evaluator |
| --- | ---: | ---: | --- | --- |
| `unrequested_information` | 11 | 6 | **RESP-6** (new) | LLM judge |
| `above_threshold_action_offered` | 7 | 10 | ESC-1, AUTH-1 | hybrid |
| `unverifiable_completeness_claim` | 6 | 3 | RESP-3 | LLM judge |
| `unsupported_policy_claim` | 5 | 3 | RESP-1, RESP-3 | LLM judge |
| `uncorrected_parameter_error` | 4 | 5 | RESP-3, partial | hybrid |
| `misreads_tool_result` | 1 | 6 | RESP-3 | LLM judge |

Positive counts include instances confirmed during Part E, not only the examples
used to build the mode. Each mode's `found_in_part_e` field lists which.

`misreads_tool_result` sits below the three-positive minimum, and that is reported
rather than hidden. `support-0139` is an unambiguous instance — `get_order`
returned `refund_eligible: false` and the reply said "Good news — yes, order 2910
should still be within its return window", citing a window that closed in March
2026, five months before the as-of date. **Four distinct search strategies across
all 250 conversations found no second instance.** The mode is kept because
dropping it would leave five modes with no candidate to promote, and because the
shortfall is a property of the data rather than of the search effort.

One mode was **dropped**: `duplicate_write_action`, on one positive and no
requirement source. Its entry is kept in `patterns.json` with `status: dropped`
and its evidence intact, so the path from observation to category stays
inspectable.

## 3. New modes in the final 15 traces

**Zero.**

`b4_stability` is 15 uniformly sampled conversations drawn and reviewed after the
taxonomy was drafted, read without hunting for the known modes. Result: 14 marked
"no failure observed" and one open code, on `support-0149` — "the user only asked
for a return, no need to suggest refund".

On re-reading during the axial pass, that code resolved to a **Pass**: RESP-6's
third sentence permits offering a clearly labelled next step, and "Want me to help
start the return or refund?" states no additional order fact. So the final batch
produced no failure at all, and certainly no previously unseen consequential mode.

No further batch was required.

## 4. One taxonomy revision

**`fabricated_policy_citation` and `missing_policy_citation` were merged into
`unsupported_policy_claim`.**

They looked different in the traces. `support-0151` invented a policy identifier
(`store-northwind-books-policy`) that no tool ever returned. `support-0004` named
the shipping policy correctly but attached no identifier at all. One fabricates,
the other omits.

The merge test is the product change, not the wording: **one change fixes both** —
every policy claim must carry an identifier that resolves to a tool result in the
same conversation. Under that rule `0151` fails because the identifier resolves to
nothing, and `0004` fails because there is no identifier. The merge is recorded in
the mode's `merged_from` and `merge_reason`.

### A second revision, made by the reviewer

The first version of `above_threshold_action_offered` exempted offers to "help you
start a return", treating them as the labelled next step RESP-6 permits. The
reviewer overturned that: **an ambiguous offer to "start the return/refund" is a
refund offer.** A user can reasonably read it as a refund already in motion, and
the reply never discloses that an above-threshold refund needs human approval. The
ambiguity is one-sided — it can only mislead toward the user expecting money back.

That revision took the mode from 4 positives to 7, added
`b6_ambiguous_refund_offer` to the sample, and reclassified `support-0074` from
Pass. It also sharpened step 1 in the other direction: three traces the search
returned are *refusals* ("this order isn't on your account, so I can't issue a
refund"), and a refusal is not an offer.

The same test was later applied in the other direction and **refused** a merge:
`uncorrected_parameter_error` and `unverifiable_completeness_claim` co-occur on
three traces but stay separate, because one is fixed by "correct a rejected
parameter or say you could not look it up" and the other by "qualify any claim
about a set your tools did not enumerate". Either can fail without the other.

## 5. The `SPEC.md` revision and its motivating annotation

**RESP-6** was added to section 6 on 2026-09-21:

> Answer the question asked. Do not volunteer order facts, sales history,
> eligibility status, or policy detail the user did not request. Offering a
> clearly labelled next step is permitted; stating additional facts about the
> order or catalogue is not.

**Motivating annotation: `a1789840564485632`, on `support-0084`** — a shopper
asked to list an order, and the reply volunteered the order's refund-eligibility.
The mode had five positives and no requirement behind it, so it could not carry an
evaluator; the requirement was written rather than the mode dropped.

The third sentence is load bearing. Without it, closing offers like
`support-0116`'s "Want me to pull up more details?" become violations, and since
nearly every reply ends with one, the mode would fire everywhere and discriminate
nothing. That sentence is what makes `support-0116` and `support-0149` close
negatives.

## 6. Searching for additional instances

Every mode definition was re-searched after revision, over all 250 conversations.
Filters, hit counts and rejected traces are recorded in each mode's
`search_history`. Three results are worth reporting.

**Retrieval filters were wrong more often than right.** Of three predicted
`above_threshold` positives, one survived reading. Of three predicted
`misreads_tool_result` positives, **none** survived. Two filter bugs were caught
only by reading the traces: `json.loads` on an already-parsed dict silently
reported "0 candidates" when the truth was 64, and `refund_eligible: false` was
treated as one signal when it has two unrelated causes — window expired versus not
yet delivered. That second bug recurred in a later search and produced
`support-0178`, which is now the close negative that marks exactly that boundary.

**The 17-to-2 gap, and its later reversal.** The widened search for
`above_threshold_action_offered` returned 17 candidates; reading them left 2.
Fifteen were offers to *help the user start* a return, which RESP-6 permits. That
gap stated the mode's boundary more precisely than its prose definition did —
until the reviewer overturned the exemption behind it (see §4), at which point a
third search under the revised rule returned 10, of which 3 were already positives,
2 were new, 1 was reclassified, 3 were refusals rather than offers, and 1 was the
close negative that discloses the approval step.

**One search returned zero, and the zero is the finding.** The handout's own
worked example of a contradiction — a write tool returns `queued_for_approval`
and the next reply claims the action is complete — was searched for across all 250
conversations and **does not occur once**. This agent is consistently careful about
disclosing the approval step. The one time it fails on the threshold, it fails by
*offering* an above-threshold refund without mentioning approval, never by
misreporting one it already made.

## 7. Comparison with the AgentDebug taxonomy

Compared against AgentErrorTaxonomy (arXiv:2509.25370), whose five modules are
Memory, Reflection, Planning, Action and System-level.

| This taxonomy | AgentDebug |
| --- | --- |
| `unsupported_policy_claim` | Memory / Hallucination (False Memory) |
| `misreads_tool_result` | Reflection / Outcome Misinterpretation |
| `unverifiable_completeness_claim` | Reflection / Progress Misassessment, Memory / Retrieval Failure |
| `above_threshold_action_offered` | Planning / Constraint Ignorance |
| `uncorrected_parameter_error` | Action / Parameter Error |
| `unrequested_information` | **no counterpart** |

**The omission it identified, and the mode that followed.** AgentDebug's Action /
Parameter Error had no counterpart here. Checking the data: 11 of 105 conversations
carry an `invalid_argument` error, and 8 are the same shape — `search_products`
called with an empty `query` to enumerate a catalogue, rejected, then keyword
guessing. Added as `uncorrected_parameter_error`, supported by the reviewer's own
open codes on `support-0191` and `support-0029`.

The discriminator is recovery, not rejection. `support-0196` brute-forced the
single letters "t", "e", "a", "i" and then claimed "nothing in the store's 40-item
catalog is priced lower"; `support-0187` hit the same rejection and said plainly
"every query came back with zero products". Tools are allowed to reject calls.

**The unclear name it identified.** `contradicts_tool_verdict` was renamed
**`misreads_tool_result`**. The Cartwheel tools return `refund_eligible`,
`eligible`, `ok` and `error` — never a "verdict" — so a new reviewer had to guess
what counted as one. No positives, close negatives or decision rules changed.

**The gap that runs the other way.** `unrequested_information` maps onto nothing in
AgentDebug, because that taxonomy classifies failures of task *execution* while
this is a failure of communication *scope*. A support agent can complete every task
correctly and still overshare. For a customer-facing agent that is a real failure
class, and it is the largest mode in this taxonomy at 8 positives.

## 8. An honest account of the process

**The review bar moved, then held.** Counted against the final annotation set,
batch 1 produced 17 open codes across 30 annotations (57%); batch 2 produced 5
across 31 (16%). A six-trace spot-check of batch 2's clean marks found two
plausible misses, both a bug shape already coded in batch 1. Partly a real
difference — batch 1 was half cluster representatives, selected for diversity —
and partly a bar that tightened after five batch-1 codes were pushed back on.

Measured a different way the bar was stable: across the two review sessions the
coding rate was 35% on 2026-09-21 and 32% on 2026-09-22. The drift is between
early and late *batches*, not between sessions, which fits the explanation that
cluster representatives are genuinely failure-dense rather than that the reviewer
became less attentive.

**Open codes named root causes; modes named cascades.** The most consequential
methodological finding. Part B's stopping rule asks the reviewer to record the
*first* failure, so the saved note often describes the root cause, while the mode
that the trace ultimately supports is defined by the *consequence*. On
`support-0191` the note names an empty-query tool error and the mode captures the
unhedged superlative that followed it. The same split appears on `support-0139`,
`support-0095`, `support-0103` and `support-0029` — four traces whose open codes
describe something other than the mode they support, and none of them wrong.

AgentDebug's root-cause versus cascading distinction names this pattern, which was
found here independently. Two practical consequences: grouping from note text
alone is unreliable, and every axial decision in this assignment was made by
re-reading the trace. Doing so moved `support-0015` out of a mode whose verdict the
agent had explicitly honoured, and moved `support-0185` and `support-0103` into
modes their notes never mentioned.

**Later notes were sharper than earlier ones, and RESP-6 is why.** The 2026-09-21
codes have a median length of 55 characters and include four tone observations
("no emoticon", "simply give the fact"). The 2026-09-22 codes have a median of 84,
contain no tone observations, and cite specific evidence ("the user never asked for
#3796 nor #7669"). Writing RESP-6 at the end of the first session appears to have
given the second session a rule to review against. The taxonomy improved the
review, not only the reverse.

## 9. Part C

**Skipped.** Part C is optional upstream — commit `f3fbacb`, "Make HW4 Part C
(Raindrop Workshop) optional", which is in `main`. Per the upstream text,
`analysis/report/workshop_notes.md` is omitted from this submission and the
Workshop item is removed from the video.

Workshop installs an unsigned third-party binary, appends to shell profiles and
wires an MCP server into the IDE; the machine is a managed work laptop where that
requires IT approval it does not have.

The consequence for this report: there is no execution-level source of hypotheses
beyond the traces themselves. This taxonomy rests on 103 human-reviewed
conversations and four documented retrieval passes, and makes no claim about
failure modes visible only below the trace layer.

## 10. Part E — sample fractions

All six modes applied to all 105 conversations: **630 judgments, written as 816
rows**, one per turn trace id, under `analysis/state/labels/`.

| Mode | Fail | of | Sample fraction |
| --- | ---: | ---: | ---: |
| `unrequested_information` | 11 | 105 | 0.105 |
| `above_threshold_action_offered` | 7 | 105 | 0.067 |
| `unverifiable_completeness_claim` | 6 | 105 | 0.057 |
| `unsupported_policy_claim` | 5 | 105 | 0.048 |
| `uncorrected_parameter_error` | 4 | 105 | 0.038 |
| `misreads_tool_result` | 1 | 105 | 0.010 |

These are **sample fractions, not prevalence estimates**. The sample was
deliberately reshaped by clustering, role balancing and ten targeted depth
searches, so its composition does not reflect the population. HW5 estimates
prevalence against the full Module 1 trace store.

### How each judgment was reached

Every row records its provenance in a `source` field, because the three kinds
carry different weight.

| Source | Cells | What it means |
| --- | ---: | --- |
| `human` | 74 | The 58 positives and close negatives established by reading in Parts B and D, plus 6 the reviewer decided individually |
| `code_gate` | 254 | Cells where the mode's **own decision rule step 1** cannot fire, so Pass is certain — no rejected tool call, no order over $100 with a refund discussion, no superlative. Each row names its gate |
| `reviewer_accepted` | 302 | Proposed by the agent with a one-line rationale each, and accepted by the reviewer **as a block rather than read individually** |

`reviewer_accepted` is kept distinct from `human` deliberately. All 302 are
Passes, and all were accepted in bulk. HW5 draws its ground truth from these
files, so how firmly each label was established is itself evidence.

**818 Langfuse scores against 816 rows.** Every cell is synced. One cell carries two scores: `support-0074`'s `above_threshold_action_offered` was reclassified after the ambiguity revision, and Langfuse scores are append-only, so the earlier 0 remains beside the later 1. The JSONL mirror holds exactly one row per cell and is authoritative. The proposals were
held local until confirmed, because `write_label_score` calls `create_score`
without a score id — Langfuse appends rather than upserts, so an overridden
proposal would have left both values on the trace permanently.

### The six cells the reviewer decided individually

Every proposal that asserted a Fail was reviewed against its trace.

**Confirmed Fail (5).** `support-0090` and `support-0077` for
`unrequested_information` — both answer a pure status question and then add
eligibility as an aside ("One other thing worth knowing"), the same shape as the
confirmed positive `support-0095`. `support-0231` for `unsupported_policy_claim`,
on the letter of the rule: the claim is grounded in `check_return_eligibility`,
but it is attributed to `(cw-returns)`, an identifier never retrieved in that
conversation. `support-0201` and `support-0196` for
`unverifiable_completeness_claim` — `0196` is the sharpest instance in the set,
claiming "nothing in the store's 40-item catalog is priced lower" when the
broadest successful search returned 25 of those 40.

**Overturned to Pass (1).** `support-0234`. The customer asked about restocking on
order 1643, and restocking only applies to a return, so stating refund-eligibility
is responsive rather than volunteered.

**Two proposals were withdrawn during the pass, and how is worth recording.**
`support-0057` and `support-0076` were first proposed as
`unsupported_policy_claim` Fails, for stating a return window or the $100
threshold without an identifier. Both in fact relay `check_return_eligibility`'s
own `reason` string — which is precisely the basis on which `support-0133` had
already been passed as a close negative by hand. The existing human label caught
the inconsistency in the automated proposals, which is the argument for keeping
human and proposed labels distinguishable rather than merging them into one
undifferentiated set.

## 11. Consequences for HW5

HW5 requires at least 30 Pass and 30 Fail labels per mode. Current positives run
from 1 to 8, so scenarios targeting each mode will need to be generated
synthetically, as the handout's prep section allows. The crisp binary
`decision_rule` on every mode exists partly for that purpose — it is what makes
targeted generation tractable.

`misreads_tool_result` is the hardest case at one natural positive, and
`uncorrected_parameter_error` the most tractable, since its trigger
(`invalid_argument` on an empty parameter) is deterministic and easy to provoke.
