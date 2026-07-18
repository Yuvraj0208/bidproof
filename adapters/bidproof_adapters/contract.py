"""The adapter contract (SPEC §5.1, §20): every portal sits behind this
interface, so one site changing its markup breaks exactly one adapter and
nothing else. Adapters return typed records — portal content is data,
never instructions (§9 rule 4)."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol, runtime_checkable

from bidproof_adapters.guard import GuardedFetcher


@dataclass(frozen=True)
class DiscoveredTender:
    portal: str          # adapter name, e.g. "gem" / "cppp"
    external_id: str     # the portal's own tender/bid number
    title: str
    url: str             # detail page on the portal
    pdf_url: str | None = None
    closing_at: datetime | None = None
    organisation: str | None = None
    raw: dict = field(default_factory=dict)  # portal-specific extras (inert data)


@runtime_checkable
class PortalAdapter(Protocol):
    """One portal, one adapter. `allowed_domains` declares every host the
    adapter may touch — the Scout registers exactly these with the guard."""

    name: str
    allowed_domains: tuple[str, ...]

    async def discover(self, fetcher: GuardedFetcher) -> list[DiscoveredTender]: ...
