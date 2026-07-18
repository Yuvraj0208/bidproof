"""The Scout's core loop: run every adapter, isolated.

One adapter throwing — a portal redesign, a network error, a missing
optional dependency — is recorded as that adapter's failure and the loop
moves on. A single site can never take discovery down (SPEC §20).
"""

import logging
import time
from dataclasses import dataclass, field
from typing import Sequence

from bidproof_adapters.contract import DiscoveredTender, PortalAdapter
from bidproof_adapters.guard import GuardedFetcher

logger = logging.getLogger(__name__)


@dataclass
class AdapterRun:
    adapter: str
    ok: bool
    tenders: list[DiscoveredTender] = field(default_factory=list)
    error: str | None = None
    duration_s: float = 0.0


@dataclass
class DiscoveryReport:
    runs: list[AdapterRun]

    @property
    def tenders(self) -> list[DiscoveredTender]:
        return [t for run in self.runs if run.ok for t in run.tenders]

    @property
    def failed_adapters(self) -> list[str]:
        return [run.adapter for run in self.runs if not run.ok]


async def run_adapters(
    adapters: Sequence[PortalAdapter], fetcher: GuardedFetcher
) -> DiscoveryReport:
    runs: list[AdapterRun] = []
    for adapter in adapters:
        started = time.monotonic()
        try:
            tenders = await adapter.discover(fetcher)
            runs.append(
                AdapterRun(
                    adapter=adapter.name,
                    ok=True,
                    tenders=tenders,
                    duration_s=round(time.monotonic() - started, 3),
                )
            )
        except Exception as exc:
            logger.warning("adapter %s failed: %s", adapter.name, exc)
            runs.append(
                AdapterRun(
                    adapter=adapter.name,
                    ok=False,
                    error=f"{type(exc).__name__}: {exc}"[:500],
                    duration_s=round(time.monotonic() - started, 3),
                )
            )
    return DiscoveryReport(runs=runs)
