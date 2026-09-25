# HW5 failure definition — `unrequested_information`

The single failure mode the HW5 judge detects. Carried over from the HW4 taxonomy
(`analysis/state/patterns.json`), restated here as a standalone rule the judge and a
human reviewer both apply to one conversation.

## The question the judge answers

> Does the assistant's reply state a substantive fact that the user did not ask for
> and that answering the question did not require?

## Requirement source

**RESP-6** (`SPEC.md` §6), written during HW4 for this mode:

> Answer the question asked. Do not volunteer order facts, sales history,
> eligibility status, or policy detail the user did not request. Offering a clearly
> labelled next step is permitted; stating additional facts about the order or
> catalogue is not.

The third sentence is load bearing. Without it nearly every Cartwheel reply ends with
a closing offer, the mode would fire everywhere, and it would discriminate nothing.

## Decision rule

Apply in order, to the assistant turn(s) in the conversation:

1. What did the user ask for in this turn?
2. List the substantive facts the reply states: order fields, prices, sales history,
   eligibility status, policy content.
3. Remove the facts needed to answer the question. Remove any closing offer of a
   next step.
4. **Anything left → Fail. Nothing left → Pass.**

## Pass (failure absent) — label `1`

- The reply answers only what was asked, using only the facts that answer it.
- The reply declines, refuses or reports a missing value without adding other facts.
- The reply ends with a **clearly labelled offer** of a next step — "Want me to check
  its return eligibility?", "Want me to help start the return?". An *offer* is a
  question about a future action, not a statement of fact. Always Pass.
- The reply relays a tool's own reason string for the order under discussion.

## Fail (failure present) — label `0`

- The reply states an order field the user did not ask about — dates, totals, status,
  store, quantity.
- The reply states **refund or return eligibility** when the user asked something else.
- The reply states facts about **other orders** the user never mentioned.
- The reply volunteers **sales history** or **catalogue/competitor prices**.
- The reply adds **policy detail** on a topic the user did not raise.

Truth is not a defence. Every confirmed instance states something correct. The
failure is scope, not accuracy.

## Evidence the judge needs

| Evidence | Why |
| --- | --- |
| The user's message(s) | Step 1 — establishes what was asked |
| The assistant's reply text | Step 2 — the facts actually stated |
| Tool calls and tool results | Distinguishes a relayed tool reason from a volunteered fact, and shows which order was under discussion |
| Earlier turns | A fact requested in turn 1 is not unrequested in turn 3 |

No policy document lookup is needed. This mode is decided from the conversation alone.

## Boundary against neighbouring modes

| Neighbour | Difference |
| --- | --- |
| `unsupported_policy_claim` | That mode is a policy **rule** stated with no retrieved identifier. This mode is **correct** facts nobody asked for. A reply can fail both; judge only this one. |
| `misreads_tool_result` | That mode contradicts a tool result. Here the facts are accurate — they are simply out of scope. |
| `unverifiable_completeness_claim` | That mode over-claims about a **set** ("nothing is cheaper"). This mode adds facts about **specific** records. |

A trace may carry any other failure and still be **Pass** for this mode.

## Anchor cases from HW4

**Clear Fail — `support-0084`** (the annotation that motivated RESP-6)
Shopper asked to list an order. The reply added: *"the order is currently not marked
as refund-eligible, which likely has to do with the return window having passed."*
Eligibility was never requested.

**Clear Fail — `support-0075`**
After a `permission_denied` on order 695, the reply volunteered a four-row table of
the user's other orders with dates, totals, statuses and eligibility, plus *"only
order 906 is currently refund-eligible."* None of it was requested.

**Clear Pass — `support-0116`**
*"Want me to pull up more details on order #6427 or check its return eligibility?"*
An offer, not a statement of fact.

**Clear Pass — `support-0100`**
Asked to look up order 1184; reported that order's own record and stopped.

**Borderline — `support-0001`** (recorded Pass; a reviewer could argue either way)
The volunteered facts — the order is 4 days overdue, tracking and order status are
out of sync — arguably serve the question actually asked (when the return window
starts), and the reply closes with a labelled next step.

## Boundary revision, 2026-09-22

Made by the reviewer before any judge was run, and recorded here because it
overturns two labels that HW4 published as close negatives.

**Two training conversations were labelled oppositely on the same facts.**
`support-0091` ("can you pull up order 6575") stated `Refund eligible: No` as one
row of the order record and was a Pass. `support-0084` ("can you check order
5453") stated the same kind of fact in prose -- "One thing to note: the order is
currently not marked as refund-eligible" -- and was a Fail. The only difference
was presentation: a bullet in a list versus a sentence flagged as an aside.

Twenty-three of the 74 labels state eligibility where the user never raised
refunds or returns, so the ambiguity was not confined to one pair.

**The rule adopted.** Refund and return eligibility is in scope **only if the user
raised refunds, returns, cancellation, restocking, sending an item back, or
getting money back.** Otherwise stating it is a Fail, including when it appears as
one line of an order record. Asking to "look up", "pull up", "check" or "find" an
order is not a request for its eligibility.

This is the literal reading of RESP-6, which names "eligibility status" among the
things not to volunteer. It was preferred over the presentation-based alternative
because a rule that turns on whether a fact sits in a bullet or a sentence cannot
be applied consistently by a judge or by a second reviewer.

**Labels changed (4).** Each appends a new row and stamps `superseded_by` on the
row it replaces, so the history stays in the file.

| Conversation | Split | Was | Now | Why |
| --- | --- | --- | --- | --- |
| `support-0091` | train | Pass | Fail | "pull up order 6575" -> states `Refund eligible: No` |
| `support-0098` | dev | Pass | Fail | "order 1767 status please" -> "No further refunds are eligible on this one" |
| `support-0100` | test | Pass | Fail | "look up order 1184" -> states `Refund eligible: No` |
| `support-0116` | dev | Pass | Fail | "find the Classic Hammer order" -> states `Refund eligible: Yes` |

`support-0100` and `support-0116` are recorded in HW4's `patterns.json` as close
negatives for this mode -- `0100` as "reported that order's own record, which is
what was asked. Pass." The revision overturns both. HW4's own files are unchanged.

**Three conversations matched the same text search and were deliberately left as
Pass**, because the rule does not reach them:

- `support-0118` -- "I can also check return/refund eligibility if that's what
  they're after" is an offer, which RESP-6's third sentence permits.
- `support-0229` -- the user asked "if i send order 623 back", which raises a
  return.
- `support-0234` -- restocking applies only to a return, so eligibility is
  responsive. HW4 had already adjudicated this one and overturned it to Pass.

**Resulting counts:** 74 labels, 26 Pass and 48 Fail (train 5/10, dev 10/20,
test 11/18).

## Label provenance, and the 86 labels that were excluded

HW5's ground truth is restricted to labels a human read individually.

HW4's Part E produced three kinds of label: `human` (decided by reading),
`code_gate` (Passes a deterministic check made certain), and `reviewer_accepted`
(proposed by the agent and accepted as a block, never read one at a time). HW4's
own report kept them distinct and said so: "HW5 draws its ground truth from these
files, so how firmly each label was established is itself evidence."

Measured for this mode, every batch a human read runs 52-67% Fail:

| Labels | n | Fail |
| --- | ---: | ---: |
| HW4 `human` | 19 | 11 (58%) |
| `hw5_screen`, read for HW5 | 30 | 20 (67%) |
| `hw5_random`, read blind for HW5 | 25 | 13 (52%) |
| HW4 `reviewer_accepted` | 86 | **0 (0%)** |

Zero in 86, against three independent readings at 52-67%, is a property of the
labelling rather than of the traces; 48% of those 86 carry a signal from the
screen described below. Keeping them would have put a large one-directional error
into the Pass class, and the judge would have been scored wrong for calling them
correctly. They are archived with their reason in
`analysis/state/hw5_labels/_excluded_bulk_accepted.jsonl`. HW4's files are
unchanged, so HW4's Part E stands as submitted.

## Why a code-based check will not do

`write-judge-prompt` requires ruling out a code evaluator first. One was built and
measured. `analysis/run_judges.py::screen_conversation` scores a conversation on
four regex signals drawn from the decision rule -- eligibility stated where the
user never raised it, order numbers the user never mentioned, volunteered sales
history, volunteered dates or prices -- over declarative sentences only, so
permitted closing offers do not trigger it.

Of the 145 conversations HW4 never reviewed, 54 carried a signal and 91 did not.
A blind random sample of 25 drawn from the 91 was then read: **13 of the 25 were
Fails.** The screen misses roughly half of them. It is kept as a reading order,
not as an evaluator.

## Label convention

**HW5 inverts HW4.** HW4 stored `1 = failure present`. HW5 stores **`1 = Pass`
(failure absent), `0 = Fail` (failure present)**, per the handout, so that Pass is the
positive class in TPR/TNR. `analysis/helpers/tools.py::_load_labels` performs the flip
automatically once `analysis/state/hw5_labels/<mode>.jsonl` exists.
