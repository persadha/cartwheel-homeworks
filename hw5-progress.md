# HW5 working log

Session of 2026-09-22, branch `hw-5`. One sitting, start to frozen judge.

Companion to [`analysis/report/hw5_summary.md`](analysis/report/hw5_summary.md),
which is the graded write-up. This file is the narrative: what happened in what
order, which decisions were mine, and what went wrong along the way.

**Status: Parts A–E complete and committed. The video is not recorded.**

---

## 1. What the assignment asked

Build one LLM judge for one failure mode from HW4. Compare its Pass/Fail calls
with human labels, use the disagreements to improve the prompt, then test the
frozen prompt on held-out traces. Report TPR, TNR and confidence intervals, and
say whether you would use the judge. Five-minute video.

Two skills: `write-judge-prompt` (draft the prompt) and `validate-evaluator`
(split, review disagreements, final test). Both installed from the course repo.

---

## 2. Chronology

### Step 0 — setup

Installed both skills with `npx skills add`. `uv sync` confirmed DocETL 0.3.0.
`OPENAI_API_KEY` was already present (I had wrongly assumed it was blank).

`uv run pytest tests/test_hw_holes.py -k m2` gave **9 failed, 9 passed, 3
skipped** — and still does. These are pre-existing: the tests expect the course
demo judge `unsupported_policy_claim-v3` at `analysis/state/judges/`, which HW4
deliberately moved to `analysis/state/_demo/` so it would not masquerade as my
own labels in the Part E grid. Nothing in HW5 depends on them.

### Part A — choosing the mode, and the label problem

Picked **`unrequested_information`**: most confirmed positives (11), already
marked "LLM judge" in HW4, and a sharp boundary (a closing offer is permitted, a
statement is not) that is good material to argue about on camera.

The blocking problem was immediate: **HW5 needs ≥30 Fail; I had 11.** Worse,
`split_labels(min_per_class=10)` refuses below 25 per class. Every HW4 mode was
short — the largest was this one.

The lever: HW4 reviewed 105 of 250 conversations. **145 were unmined**, and
already exported locally, so searching them cost nothing but reading time.

`next_to_label(strategy="enrich")` was no help — it returned all 145 with one
undifferentiated signal. So I built a regex screen from the mode's own decision
rule (eligibility stated unasked, order numbers the user never mentioned,
volunteered sales history, volunteered dates or prices), scoring **declarative
sentences only** so permitted closing offers would not trigger it. 54 of 145
carried a signal; 91 did not.

**My decision:** label the 54 screened *plus* 25 drawn at random from the 91, as
a check that the screen was not defining the Fail class. This turned out to be
the most valuable decision of the day.

To label, I extended the HW4 review app with a `--hw5` mode: its own sample file,
its own label file, the inverted convention, `p`/`f` keys, and a queue that
filters to unlabelled or to judge disagreements. Part E's grid, map and progress
views are hidden there so the HW4 label set cannot be edited by accident.

#### Finding 1 — the screen had a large blind spot

I stopped at 30 Fails, then labelled the blind slice. **13 of those 25 were
Fails — 52%**, against 67% for the screened batch. The regex was not finding the
mode; it was finding one shape of it. That is the argument for having drawn the
random batch at all, and it is why the screen is documented as a reading order
and never as an evaluator.

#### Finding 2 — my HW4 labels were the weak link

Splitting Fail rate by how each label was produced:

| Label provenance | n | Fail |
| --- | ---: | ---: |
| HW4 `human` (read individually) | 19 | 11 (58%) |
| `hw5_screen` (read now) | 30 | 20 (67%) |
| `hw5_random` (read now, blind) | 25 | 13 (52%) |
| HW4 `reviewer_accepted` (bulk-accepted) | 86 | **0 (0%)** |

Zero in 86, against three independent readings at 52–67%. That is a property of
the labelling, not the traces — and 48% of those 86 carried a screen signal,
meaning they *look* like the conversations I had just called Fail.

HW4's own report predicted this: *"HW5 draws its ground truth from these files,
so how firmly each label was established is itself evidence."*

**My decision:** exclude all 86. They are archived with their reason in
`_excluded_bulk_accepted.jsonl`, and HW4's files are untouched, so HW4's Part E
stands as submitted. That left **30 Pass / 44 Fail**, all individually read —
which happened to land exactly on the handout's minimum.

### Part B — inputs and the split

`prepare_inputs()` writes one record per conversation, `trace_id` and `trace` and
nothing else, built from a **whitelist** rather than by deleting fields, so a
column added to the sample later cannot reach the judge.

Two things I got wrong and then fixed:

- My first leakage guard was a substring scan for suspicious field names. It
  fired on `"reason"` — which is a legitimate parameter of `issue_refund` and
  `cancel_order` (SPEC.md TOOL-7/8) that the judge needs. Replaced with a
  structural check plus a direct test that none of my review notes appear in what
  the judge reads.
- `normalization._flatten` prints a `tool_call` from its `arguments` alone, so
  the **tool name is dropped**. A judge seeing `tool_call: {"order_id": 5453}`
  cannot tell `get_order` from `check_return_eligibility` — exactly the
  distinction this mode turns on. Fixed by folding the name into the fields that
  survive flattening.

Split 20/40/40, seed 7, run once: train 6/9, dev 12/18, test 12/17 at that point.

### Part C — the boundary revision, before any judge ran

Picking few-shot examples surfaced a contradiction in my own training data.

`support-0091` ("pull up order 6575") stated `Refund eligible: No` as a bullet and
I had called it **Pass**. `support-0084` ("check order 5453") stated the same kind
of fact in prose — *"One thing to note: the order is currently not marked as
refund-eligible"* — and I had called it **Fail**. The only difference was whether
the fact sat in a list or was flagged as an aside. 23 of 74 labels had this shape.

**My decision:** the literal reading of RESP-6, which names "eligibility status"
explicitly. Eligibility is in scope **only** if the user raised refunds, returns,
cancellation, restocking, sending an item back, or getting money back.

Claude's text search proposed 7 labels to flip; **only 4 were genuine**. The other
three were misfires — one was an *offer* (permitted), one was a user who said
"send order 623 back" (a return, which my pattern missed), and one was a
restocking question I had already adjudicated in HW4. Worth remembering: the
search proposes, the reading decides.

Two of the four flips overturned HW4 close negatives (`support-0100`,
`support-0116`). That is recorded rather than slipped in.

### Parts C–D — three prompt versions

Model `gpt-4o-mini` throughout, as the handout requires. Two revisions, the limit.

| | Change | Dev TPR | Dev TNR | Agree |
| --- | --- | ---: | ---: | ---: |
| v0 | First draft | 0.000 | 1.000 | 0.600 |
| v1 | Revision 1 | 0.333 | 0.944 | 0.700 |
| v2 | Revision 2, **frozen** | 0.333 | 1.000 | 0.733 |

*(dev figures against the final labels, so comparable)*

**v0 said Fail to all 30.** Its TNR of 1.000 was worthless — a judge that always
says Fail catches every Fail by construction, and its 0.600 agreement was just the
Fail share of the split. The handout's warning about agreement, mirrored.

**v1** relaxed the rule in five places: the answer can never be the unrequested
fact; the eligibility rule is about an order's *status*, not the word "refund";
disambiguation is in scope; identifying detail is in scope; a reply need not be
minimal. Examples rebalanced to 2 Fail / 3 Pass, plus a second Fail shape so the
judge would not learn that eligibility is the only way to fail.

**v2** changed the shape of the task instead of adding more exceptions — v1 was a
strict rule followed by a growing list of carve-outs, and the judge applied
whichever it had read last. v2 uses a **naming test**: to return Fail it must
complete *"The reply states ___, which belongs to ___, a record or topic the user
never raised"*, quoting a fact and naming one of five categories. If it cannot
fill both blanks, the answer is Pass.

#### Finding 3 — a third of the disagreements were mine

`support-0087`: I had asked only for order status and the reply added *"$160.50
has been refunded, so no further refund is available on this order."* I labelled
Pass; v0 said Fail; **the judge was right** — that is eligibility, and my own
boundary rule from that morning ruled it out. Flipped.

After v1, three more went the other way — `support-0046`, `support-0204`,
`support-0055` — all cases where I had been *stricter* than the rule allowed.

**Four of twelve dev disagreements were labelling errors, not judge errors.**
Correcting them moved v1's dev TPR from 0.111 to 0.333 and TNR from 0.810 to
0.944 **without changing a single prediction**. That is the strongest argument in
the whole assignment for reading disagreements one at a time instead of trusting
the headline rate.

#### A leak I caught before it cost anything

My content-level check (8-word shingles of every conversation against every
prompt) found that v2 quoted two sentences verbatim from **dev** conversations —
`"None of your orders include the Portable Pencil Set"` (support-0117) and
`"arrived a few days ahead of the estimated delivery"` (support-0082). I had
picked both *because* the judge got them wrong on dev, which is exactly the
leakage the train/dev split exists to prevent.

v2 had not yet run, so nothing was contaminated. **My decision:** withdraw the
unrun record, replace the sentences with generic phrasing, re-register as v2 —
keeping the history at v0/v1/v2, the two revisions the handout allows. The leaked
text is preserved as `unrequested_information-v2-withdrawn.txt`.

Two other flagged overlaps were false positives: *"Is there anything else I can
help you with"* is boilerplate that also ends my train example `support-0175`.

#### Why revision stopped

Two revisions used. Two defects were identified in v2 and deliberately **not**
fixed, because fixing them would have been a third:

1. **It reads tool results as though the assistant said them.** On `support-0082`
   the critique says *"The reply states 'refund eligible: true'"* — the reply says
   no such thing; that field is only in the `get_order` tool result.
2. **It forces observations into category 5.** On `support-0046` it quotes *"None
   of your orders are currently in transit"* and calls it refund eligibility.
   Transit status is not eligibility. The naming test demands a category, so it
   picks the broadest-sounding one instead of returning Pass.

Four of the eight remaining misses trace to these.

### Part D — frozen test

Before freezing I checked 10 test conversations whose shapes the boundary
revision had touched. Eight were `eligibility-unasked` already labelled Fail,
which the new rule confirms. Of the other two, `support-0074` and `support-0075`
stay Fail because they don't just *list* candidate orders, they *assess* them
("only order 906 is currently refund-eligible"), and `support-0111` stays Pass.
No test labels changed, and no test predictions were seen.

`unrequested_information-v2`, frozen, scored once on 29 conversations:

| | Judge Pass | Judge Fail |
| --- | ---: | ---: |
| **Human Pass** | 3 (TP) | 8 (FN) |
| **Human Fail** | 2 (FP) | 16 (TN) |

| Metric | Value | 95% Wilson |
| --- | ---: | --- |
| **TPR** = 3/11 | **0.273** | 0.098 – 0.566 |
| **TNR** = 16/18 | **0.889** | 0.672 – 0.969 |
| Agreement | 0.655 | |

Dev → test: TPR 0.333 → 0.273, TNR 1.000 → 0.889. Both fell, as a tuned split
should. TNR is the telling one — a perfect dev score became 0.889 on fresh data,
so two real failures slipped through where none had before.

---

## 3. The verdict I need to give on camera

- **Not usable as a gate.** TPR 0.273 means roughly three of every four
  acceptable replies are condemned.
- **As a screen, "not proven".** 16 of 18 failures caught is the right shape, but
  the interval runs 0.672–0.969. Eighteen failures cannot establish "nine in ten".
- **The interval is the finding, not the point estimate.** Both are wide because
  the splits are small. No further prompt work narrows them; only more labels
  would.

---

## 4. What I decided, in one place

| Decision | Choice |
| --- | --- |
| Failure mode | `unrequested_information` |
| Closing the Fail gap | Mine the 145 unreviewed, then reassess |
| Labelling queue | 54 screened + 25 blind random |
| HW4 bulk-accepted labels | Exclude all 86, archive with reasons |
| Eligibility boundary | Always Fail unless the user raised refunds/returns |
| The 7 proposed flips | Apply 4, reject 3 |
| `support-0087` | My label was wrong → Fail |
| `support-0046`/`0204`/`0055` | My labels were wrong → Pass |
| Disambiguation listings | In scope (Pass) |
| Leaked v2 | Withdraw unrun record, re-register corrected as v2 |
| After two revisions | Freeze v2, report the defects rather than fix them |

---

## 5. Numbers to remember

- 74 labels, 28 Pass / 46 Fail, every one read individually
- 83 rows on disk, 9 superseded — the label history is intact
- 86 HW4 labels excluded; 8 labels changed during HW5
- Splits: train 5/10, dev 12/18, test 11/18
- Four `gpt-4o-mini` batches, **roughly $0.06 total**

---

## 6. What is left

- **Record the video (up to 5 min, one take).** Walk through the failure mode,
  one development disagreement, and the test TPR/TNR with intervals; say whether
  you would use the judge; recalculate the test metrics live from saved
  predictions.
- The recalculation script lives in the session scratchpad, not the repo. It
  rebuilds the confusion matrix and both Wilson intervals from
  `analysis/state/judges/unrequested_information-v2.json` and asserts they match
  the committed `test-unrequested_information-v2.json`. **Move it into the repo
  before recording** if you want to run it on camera from a clean checkout.
- Optional extensions not attempted: two more judges, and prevalence estimation
  with the Rogan–Gladen correction (the sample is deliberately enriched, so it
  would need a fresh random draw).

---

## 7. Commits

| | |
| --- | --- |
| `5356ecc` | utf-8 fix in `check_leakage.py`, gitignore for vendored skills |
| `e250fbd` | Parts A–B: labels, judge inputs, split, review-app `--hw5` mode |
| `dc9aeea` | Parts C–D: three prompts, judge records, dev + test metrics, summary |

HW4 deliverables are byte-identical — `git diff ee7cd85..HEAD` over `labels/`,
`patterns.json`, `annotations.json`, `samples.json`, `review_summary.md`,
`interface_comparison.md` and `SPEC.md` returns nothing. `splits.json` only gained
a key.

Side fix: `scripts/check_leakage.py` read judge records with no encoding, so on
Windows it decoded them as cp1252 and died on the first non-ascii character. It
never surfaced while `analysis/state/judges/` was empty. Pinned to utf-8; it now
fails at its own intended HW6 `NotImplementedError` instead.
