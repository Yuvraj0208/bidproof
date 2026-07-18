"""Tolerant parsing of the CPPP/eprocure tender feed (RSS-style XML).

Tolerant means: a malformed item is skipped, a missing optional field stays
None — the parser never invents a value it cannot read (§9 rule 3)."""

import re
from datetime import datetime, timezone
from urllib.parse import parse_qs, urlparse
from xml.etree import ElementTree

from bidproof_adapters.contract import DiscoveredTender

_CLOSING_RE = re.compile(
    r"closing\s*date\s*[:\-]?\s*(\d{2}[-/]\d{2}[-/]\d{4})(?:\s+(\d{2}:\d{2}))?",
    re.IGNORECASE,
)


def _parse_closing(text: str | None) -> datetime | None:
    if not text:
        return None
    match = _CLOSING_RE.search(text)
    if not match:
        return None
    date_part = match.group(1).replace("/", "-")
    time_part = match.group(2) or "00:00"
    try:
        return datetime.strptime(
            f"{date_part} {time_part}", "%d-%m-%Y %H:%M"
        ).replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _external_id(link: str, guid: str | None, title: str) -> str:
    query = parse_qs(urlparse(link).query)
    for key in ("id", "tender_id", "tenderid"):
        if key in query and query[key]:
            return query[key][0]
    if guid and guid.strip():
        return guid.strip()
    return link or title


def parse_feed(xml_text: str, portal: str = "cppp") -> list[DiscoveredTender]:
    try:
        root = ElementTree.fromstring(xml_text)
    except ElementTree.ParseError:
        return []

    tenders: list[DiscoveredTender] = []
    for item in root.iter("item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        if not title or not link:
            continue
        description = item.findtext("description") or ""
        tenders.append(
            DiscoveredTender(
                portal=portal,
                external_id=_external_id(link, item.findtext("guid"), title),
                title=title,
                url=link,
                pdf_url=(item.findtext("enclosure") or None),
                closing_at=_parse_closing(description),
                organisation=(item.findtext("author") or None),
                raw={"description": description[:2000]},
            )
        )
    return tenders
