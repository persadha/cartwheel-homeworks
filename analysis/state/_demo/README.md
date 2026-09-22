# Course-shipped demo data

These files arrived with the Cartwheel codebase in commit `cdf1964`, "Add
Cartwheel codebase with hw1 and hw2". **None of it is student work.**

They were moved here on 2026-09-22, out of `analysis/state/labels/` and
`analysis/state/judges/`, because they are named after `unsupported_policy_claim`
— which by then was a real failure mode in the student's HW4 taxonomy. Left in
place they would have appeared in the Part E label grid as if they were the
student's own judgments, and `GET /api/labels` did report them that way.

| Path | What it is |
| --- | --- |
| `labels/unsupported_policy_claim.jsonl` | 121 label rows against synthetic trace ids (`upc-fail-tr-00`, ...) that do not exist in `traces/support_traces.json` |
| `judges/unsupported_policy_claim-v0..v3.json` | A worked example of judge prompt iteration, kept as HW5 reference |
| `judges/_history_unsupported_policy_claim.json` | The matching version history |

Nothing in the codebase reads these paths. `scripts/check_leakage.py` mentions
`judges/unsupported_policy_claim-v3` in a docstring example only, inside an
unimplemented HW6 placeholder.

The student's own Part E labels belong in `analysis/state/labels/`, and their
HW5 judges in `analysis/state/judges/`, both of which are now empty.
