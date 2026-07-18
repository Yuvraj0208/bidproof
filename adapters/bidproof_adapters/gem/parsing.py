"""Pure parsing of the GeM bid-list page. Kept separate from the browser
driver so the parsing logic is unit-testable against fixture HTML and a
markup change is a one-file fix."""

import re
from datetime import datetime, timezone
from html import unescape
from urllib.parse import urljoin

from bidproof_adapters.contract import DiscoveredTender

_BID_NO_RE = re.compile(r"GEM/\d{4}/[A-Z]+/\d+")
_CARD_SPLIT_RE = re.compile(r'<div[^>]*class="[^"]*card[^"]*"', re.IGNORECASE)
_DATA_TITLE_RE = re.compile(r'data-title="([^"]+)"', re.IGNORECASE)
_TITLE_EL_RE = re.compile(
    r'<(?:h\d|a)[^>]*class="[^"]*bid[_-]?title[^"]*"[^>]*>(.*?)</',
    re.IGNORECASE | re.DOTALL,
)
_HREF_RE = re.compile(r'href="([^"]+)"', re.IGNORECASE)
_END_DATE_RE = re.compile(
    r"(?:end\s*date|closing\s*date)\s*[:\-]?\s*(\d{2}-\d{2}-\d{4})(?:\s+(\d{2}:\d{2}))?",
    re.IGNORECASE,
)
_TAG_RE = re.compile(r"<[^>]+>")


def _clean(text: str) -> str:
    return unescape(_TAG_RE.sub(" ", text)).split("  ")[0].strip()


def parse_bid_cards(html: str, base_url: str) -> list[DiscoveredTender]:
    tenders: list[DiscoveredTender] = []
    seen: set[str] = set()

    for chunk in _CARD_SPLIT_RE.split(html)[1:]:
        bid_no_match = _BID_NO_RE.search(chunk)
        if not bid_no_match:
            continue
        bid_no = bid_no_match.group(0)
        if bid_no in seen:
            continue
        seen.add(bid_no)

        # Prefer the data-title attribute; the bid_title element often just
        # repeats the bid number, which is a fallback, not a title.
        title = bid_no
        data_title = _DATA_TITLE_RE.search(chunk)
        if data_title and _clean(data_title.group(1)):
            title = _clean(data_title.group(1))
        else:
            element_title = _TITLE_EL_RE.search(chunk)
            if element_title:
                candidate = _clean(element_title.group(1))
                if candidate and candidate != bid_no:
                    title = candidate

        url = base_url
        href_match = _HREF_RE.search(chunk)
        if href_match:
            url = urljoin(base_url, unescape(href_match.group(1)))

        closing_at = None
        end_match = _END_DATE_RE.search(chunk)
        if end_match:
            try:
                closing_at = datetime.strptime(
                    f"{end_match.group(1)} {end_match.group(2) or '00:00'}",
                    "%d-%m-%Y %H:%M",
                ).replace(tzinfo=timezone.utc)
            except ValueError:
                closing_at = None

        tenders.append(
            DiscoveredTender(
                portal="gem",
                external_id=bid_no,
                title=title,
                url=url,
                closing_at=closing_at,
            )
        )
    return tenders
