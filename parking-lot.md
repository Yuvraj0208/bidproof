# parking-lot.md — BidProof

Everything that is **not** in the current story or the SPEC lands here — not in the sprint.
This protects the 6-week clock and the Week-3 demo spine. Review the list during buffer weeks (SPEC §18).

When an idea comes up mid-build, add a row and move on. Nothing here gets built until it is
promoted into `docs/SPEC.md` §3.2 as a real user story with acceptance criteria.

| Date | Idea | Why it's parked (not in scope / not in SPEC) | Relates to | Decision |
|------|------|----------------------------------------------|------------|----------|
| _e.g. 2026-07-20_ | _Auto-email pre-bid letters to the buyer_ | _Violates least-privilege: no agent may send email or submit (SPEC §10)_ | _US-08_ | _Parked — human sends_ |
| 2026-07-17 | Move parse execution from in-process background task to a Celery worker (stack already has Redis+Celery) | Revisited at US-01: kept an in-process interval scheduler (meets the 4-hour AC); Celery pays off when parse workload must leave the API process | US-01 | Parked — revisit when parse load demands workers |
| 2026-07-17 | Decide PyMuPDF permanently: pypdfium2 stays, or buy a PyMuPDF commercial licence | SPEC §5.2 names PyMuPDF but it is AGPL — excluded by SPEC §11.4/§20 licence rule; pypdfium2 (Apache) used behind an interface | Parser | Parked — pypdfium2 until sponsor decides |
| 2026-07-31 | Make the Model Lab real — actual per-role gateway calls instead of `_simulate` | `services/modellab.py` scores nothing today; every row is honestly marked `simulated: true`, but the screen reads like evidence. Belongs with the Evaluation subsystem, not bundled into the Conductor | US-14 | Parked — do NOT show as model comparison until real |
| 2026-07-31 | Register `CHAT_PROMPT_V1` in the prompt-approval gate | Every other prompt is versioned and gold-set tested before shipping (SPEC §14); the chat prompt escapes that gate, so a bad edit ships unchecked | US-15 | Parked — real gap, own story |
| 2026-07-31 | Durable graph checkpointing across a process restart | Needs a `BaseCheckpointSaver` over the existing asyncpg session: LangGraph's stock Postgres saver wants psycopg and opens its own pool, which would put tenant run-state outside row-level security | Conductor | Parked — pause/resume works today by re-deriving state from Postgres |
| 2026-07-31 | Decision Analyst: an agent that explains the EV without producing it | Reasons about sensitivity and which assumption is load-bearing. Needs a guard rejecting any numeral not already in the input, so "the AI cannot invent a rupee figure" is tested rather than promised | US-06 | Parked — EV stays deterministic either way |
| 2026-07-31 | Port `replay.py` and `amendments.py` onto the graph | While `/process` runs through the Conductor and these call services directly, there are two orchestrations to keep in step — the same drift the Conductor exists to end | Conductor | Parked — after checkpoints 5 and 6 land |
|      |      |                                              |            |          |

## Promotion rule

An item leaves the parking lot only by:
1. Writing it as `US-XX` in `docs/SPEC.md` §3.2 with acceptance criteria, and
2. Confirming it does not weaken the demo spine (SPEC §18 "Never cut").

Until then, it stays a row in the table above.
