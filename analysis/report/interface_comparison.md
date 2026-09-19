# Interface comparison

The review interface under `analysis/review_app/` is a fork of the reference
interface (`analysis/server.py`, `analysis/ui/index.html`), adapted after
reading eight Cartwheel conversations in the stock Langfuse annotation view.
The observations from that reading are recorded verbatim in `hw4-progress.md`
and are referred to below as R1 to R5.

## One design retained from the reference interface

**Margin-note annotation driven by text selection.** The reviewer selects the
words where the failure shows, a popover takes a free-text note, and the note
appears in a right-hand margin column aligned with the highlighted span, linked
to it by hover. Agent suggestions use the same column with a dashed highlight,
a distinct border colour and an explicit accept/dismiss control.

It was kept because it makes the open code inseparable from its evidence. A
note reading "claimed the refund was processed" is only checkable if the exact
sentence it refers to is still attached to it, and Part D requires every mode to
remain inspectable back to the annotation it came from. A structured form or a
dropdown at this stage would have produced categories before evidence, which is
the failure mode open coding exists to prevent. The mechanics were also already
correct in the reference, including the pending-highlight wrapper that keeps the
selection visible while the input takes focus.

## One design changed after inspecting my traces

**Turn separators, because a Cartwheel conversation is several Langfuse
traces.** Cartwheel opens one trace per user turn, so 51 of the 250
conversations in this store span two or three traces. In the stock Langfuse
view those arrive as separate tabs with nothing connecting them; as recorded in
`hw4-progress.md`: *"I could tell that it was a 3-turn conversation by
inspecting the user_id and the time"* and *"I have to hold off the timestamp
from multi-turn conversations, since I have to click different tabs"* (R4).

The reference interface did not solve this either. `renderTrace()` walked the
message list flat, with no turn boundary drawn anywhere, and the record it
consumed had already lost the information needed to draw one:
`normalization._merge_multi_turn` concatenates the messages of every turn but
keeps only the first turn's `trace_id` and timestamp.

The fork therefore does its own grouping in `build_samples.py`, normalizing each
trace on its own and grouping by `cartwheel.scenario_id`, so every turn keeps
its identifier, its timestamp and a link to itself in Langfuse. `renderTrace()`
draws a separator at each turn start carrying the turn number, the timestamp,
that turn's tool-call count, any write tools it used, and the Langfuse link.

This matters for correctness, not only for comfort. A refund queued in turn 1
and described as complete in turn 2 is a `RESP-2` violation that is invisible in
either turn read alone. It also keeps Part E honest: scoring only the anchor
trace would have left the later turns of 51 conversations without a judgment.

Two further changes followed from the same reading and are recorded here for
completeness:

- **Nothing needed for a judgment hides behind a click (R1).** The stock view
  required clicking a tool name to see its output, and the reference reproduced
  this: tool arguments sat in a `<details>` element and any result over 240
  characters did too. Both are gone. Only a result over 2000 characters is
  clipped (26 of 890 in this store, all `list_my_orders` or `search_products`,
  never a write result), and the control that restores it states how many
  characters are hidden.
- **`resourceAttributes` and `scope` are never rendered (R5).** The four
  `cartwheel.*` attributes are promoted into a header that stays on screen while
  the conversation scrolls (R2).

## Substitution: the session grouping key

The handout requires grouping by `cartwheel.session_id`. That attribute is
absent from all 308 Module 1 traces: the Langfuse `sessionId` field is null on
every trace in the project, and the only trace-level Cartwheel attributes
recorded are `cartwheel.prompt_version`, `cartwheel.scenario_id`,
`cartwheel.user_id` and `cartwheel.user_role`. `server/app.py` does set
`cartwheel.session_id`, but that line post-dates the Homework 3 run and so could
not tag traces already recorded.

The interface groups on `cartwheel.scenario_id` instead, which every trace
carries and which identifies the same conversations. New runs, including the
Part C replays, will carry both identifiers.

## Trace source

Langfuse is the canonical store and holds the traces and the accepted labels.
`build_samples.py --source langfuse` pulls the review sample live; the committed
export `traces/support_traces.json` is an equivalent offline source, verified to
contain the same 308 `support-*` traces and the same 250 conversations as the
live project. The export was used while building and smoke-testing the
interface, to avoid repeated full pulls against the local stack during
development. Review batches are drawn from Langfuse.

Judgments are written to Langfuse as scores named after the mode, and mirrored
under `analysis/state/labels/<mode>.jsonl`. `server.py --no-langfuse` keeps a
session going with the stack down, and the interface reports plainly when a
canonical write failed and only the local mirror succeeded.

## One limitation remaining

**The interface cannot show a failure that is only visible against the
database.** It renders what the trace recorded: the conversation, the tool
arguments, the tool results and the retrieval hits. It has no access to
`data/cartwheel.db`, so it cannot tell that a tool returned a correct-looking
record for the wrong order, that an eligibility answer disagrees with the seeded
world date, or that a policy snippet was retrieved but does not support the
claim built on it. A reviewer can see that the agent's reply contradicts the
tool result, which is what `RESP-2` needs, but not that the tool result was
itself wrong.

A second, smaller limitation: the map view still depends on
`state/graph.json`, which nothing in this fork writes, so it renders empty.
Cluster-representative sampling is available through `build_samples.py` and the
instructor's `selection.select`, so the clustering is used for selection but is
not visualised.
