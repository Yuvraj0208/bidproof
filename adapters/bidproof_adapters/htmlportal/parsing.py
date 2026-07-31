"""Strict parsing of a plain HTML tender table, driven by column config.

Some public buyers do not run NIC eProcurement — they publish an ordinary table
on their own website. Verified live 2026-07-30:

* **CWC** (cewacor.nic.in/Home/TenderList) — 7 labelled columns and, unusually
  for an Indian portal, a **durable** per-tender link
  (`/Home/ViewTenderData?TenderID=...`). Not a session ticket like CPPP's.
* **PNB** (pnbindia.in/Tender.aspx) — 3 columns, but the links are ASP.NET
  `__doPostBack` calls, so no individual tender has a URL at all.

Strict, for the reason recorded in `niceproc/parsing.py`: a lenient parser that
accepted "any row with a link" turned a website announcement into a tender. Here
a row must have enough real cells and a title, or it is skipped.
"""

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from html import unescape
from urllib.parse import urljoin

from bidproof_adapters.contract import DiscoveredTender

_ROW_RE = re.compile(r"<tr[^>]*>(.*?)</tr>", re.IGNORECASE | re.DOTALL)
_CELL_RE = re.compile(r"<td[^>]*>(.*?)</td>", re.IGNORECASE | re.DOTALL)
_TAG_RE = re.compile(r"<[^>]+>")

_DATE_FORMATS = (
    "%d-%m-%Y %I:%M:%S %p",
    "%d-%m-%Y %H:%M",
    "%d-%m-%Y",
    "%d/%m/%Y %H:%M",
    "%d/%m/%Y",
    "%d-%b-%Y %I:%M %p",
    "%d-%b-%Y",
)


@dataclass(frozen=True)
class TableProfile:
    """Where the interesting values sit in one portal's table.

    Indices are into the row's `<td>` cells. `detail_link_marker` is the
    substring that identifies a real per-tender link; when a portal has none
    (PNB posts back instead of linking), leave it empty and every tender falls
    back to the listing URL.
    """

    name: str
    listing_url: str
    title_col: int
    reference_col: int | None = None
    closing_col: int | None = None
    location_col: int | None = None
    detail_link_marker: str = ""
    min_cells: int = 3


def _clean(html: str) -> str:
    return " ".join(unescape(_TAG_RE.sub(" ", html)).split())


def _cell(cells: list[str], index: int | None) -> str:
    if index is None or index >= len(cells):
        return ""
    return cells[index]


def parse_closing(text: str) -> datetime | None:
    """A closing date, or None. Never a guess — an unparseable date stays absent
    rather than becoming today (§9 rule 3)."""
    candidate = (text or "").strip()
    if not candidate:
        return None
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(candidate, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    # Some portals append noise after the timestamp; try the leading date only.
    match = re.match(r"(\d{2}[-/]\d{2}[-/]\d{4})", candidate)
    if match:
        try:
            return datetime.strptime(
                match.group(1).replace("/", "-"), "%d-%m-%Y"
            ).replace(tzinfo=timezone.utc)
        except ValueError:
            return None
    return None


def parse_table(html: str, profile: TableProfile) -> list[DiscoveredTender]:
    tenders: list[DiscoveredTender] = []
    seen: set[str] = set()

    for row_html in _ROW_RE.findall(html):
        cells = [_clean(c) for c in _CELL_RE.findall(row_html)]
        if len(cells) < profile.min_cells:
            continue

        title = _cell(cells, profile.title_col)
        # A serial number or a stray control is not a title.
        if len(title) < 12:
            continue

        reference = _cell(cells, profile.reference_col)
        external_id = reference or title[:120]
        if external_id in seen:
            continue
        seen.add(external_id)

        url = profile.listing_url
        if profile.detail_link_marker:
            link = re.search(
                rf'href="([^"]*{re.escape(profile.detail_link_marker)}[^"]*)"',
                row_html,
                re.IGNORECASE,
            )
            if link:
                url = urljoin(profile.listing_url, unescape(link.group(1)))

        raw: dict = {}
        location = _cell(cells, profile.location_col)
        if location:
            raw["location"] = location

        tenders.append(
            DiscoveredTender(
                portal=profile.name,
                external_id=external_id,
                title=title[:500],
                url=url,
                closing_at=parse_closing(_cell(cells, profile.closing_col)),
                organisation=location or None,
                raw=raw,
            )
        )
    return tenders
