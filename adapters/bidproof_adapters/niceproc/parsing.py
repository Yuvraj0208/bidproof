"""Strict parsing of a NIC eProcurement tender list.

Written strict on purpose. The first attempt reused the CPPP listing parser,
which accepts any table row carrying a link — and on IOCL's page that matched a
*web announcement* ("Restriction in IOCL E-Tendering Portal towards...") and
reported it as a tender. Inventing a tender out of site furniture is exactly the
failure this product exists to prevent, so a row here is only a tender when it
carries a real tender-detail link.

If that means returning nothing, it returns nothing. Zero is a truthful answer;
a fabricated tender is not.
"""

import re
from datetime import datetime, timezone
from html import unescape
from urllib.parse import urljoin

from bidproof_adapters.contract import DiscoveredTender

_ROW_RE = re.compile(r"<tr[^>]*>(.*?)</tr>", re.IGNORECASE | re.DOTALL)
_CELL_RE = re.compile(r"<td[^>]*>(.*?)</td>", re.IGNORECASE | re.DOTALL)
_TAG_RE = re.compile(r"<[^>]+>")

# The only link that means "this row is a tender" on the NIC platform.
_TENDER_LINK_RE = re.compile(
    r'href="([^"]*page=FrontEndViewTender[^"]*)"', re.IGNORECASE
)
_CLOSING_RE = re.compile(r"(\d{2}-[A-Za-z]{3}-\d{4})(?:\s+(\d{2}:\d{2}))?")


def _clean(html: str) -> str:
    return " ".join(unescape(_TAG_RE.sub(" ", html)).split())


def _closing(text: str) -> datetime | None:
    match = _CLOSING_RE.search(text or "")
    if not match:
        return None
    try:
        return datetime.strptime(
            f"{match.group(1)} {match.group(2) or '00:00'}", "%d-%b-%Y %H:%M"
        ).replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def parse_tender_list(html: str, *, portal: str, base_url: str) -> list[DiscoveredTender]:
    """Tenders from a NIC eProcurement list page.

    A row must carry a `page=FrontEndViewTender` link and a non-empty title, or
    it is not a tender and is skipped. Malformed rows are skipped, never
    repaired (§9 rule 3).
    """
    tenders: list[DiscoveredTender] = []
    seen: set[str] = set()

    for row_html in _ROW_RE.findall(html):
        link = _TENDER_LINK_RE.search(row_html)
        if not link:
            continue  # site furniture, navigation, announcements

        cells = [_clean(c) for c in _CELL_RE.findall(row_html)]
        texts = [c for c in cells if c]
        if not texts:
            continue

        # The title is the longest cell: NIC puts the reference and dates in
        # short cells and the tender's own description in the widest one.
        title = max(texts, key=len)
        if len(title) < 8:
            continue

        # The reference is the best short cell that looks like an id.
        reference = next(
            (c for c in texts if c is not title and re.search(r"[0-9]", c) and "/" in c),
            None,
        )
        external_id = reference or title[:120]
        if external_id in seen:
            continue
        seen.add(external_id)

        tenders.append(
            DiscoveredTender(
                portal=portal,
                external_id=external_id,
                title=title[:500],
                url=urljoin(base_url, unescape(link.group(1))),
                closing_at=_closing(" ".join(texts)),
                raw={"cells": texts[:8]},
            )
        )
    return tenders
