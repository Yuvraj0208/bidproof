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
|      |      |                                              |            |          |

## Promotion rule

An item leaves the parking lot only by:
1. Writing it as `US-XX` in `docs/SPEC.md` §3.2 with acceptance criteria, and
2. Confirming it does not weaken the demo spine (SPEC §18 "Never cut").

Until then, it stays a row in the table above.
