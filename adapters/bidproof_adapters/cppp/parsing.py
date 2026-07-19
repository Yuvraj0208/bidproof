"""Tolerant parsing of the CPPP/eprocure latest-tenders listing. The portal
serves either RSS-style XML or an HTML table (verified live 2026-07-19:
columns Sl.No | e-Published | Closing | Opening | Title/Ref/Id | Organisation
| Corrigendum). `parse_listing` tries XML first, then the table.

Tolerant means: a malformed item/row is skipped, a missing optional field
stays None — the parser never invents a value it cannot read (§9 rule 3)."""

import re
from datetime import datetime, timezone
from html import unescape
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


_ROW_RE = re.compile(r"<tr[^>]*>(.*?)</tr>", re.IGNORECASE | re.DOTALL)
_TD_RE = re.compile(r"<td[^>]*>(.*?)</td>", re.IGNORECASE | re.DOTALL)
_LINK_RE = re.compile(
    r'<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>(.*)', re.IGNORECASE | re.DOTALL
)
_TAG_RE = re.compile(r"<[^>]+>")


def _clean(html: str) -> str:
    return " ".join(unescape(_TAG_RE.sub(" ", html)).split())


def _parse_listing_dt(text: str) -> datetime | None:
    try:
        return datetime.strptime(text, "%d-%b-%Y %I:%M %p").replace(
            tzinfo=timezone.utc
        )
    except ValueError:
        return None


def parse_html_listing(html: str, portal: str = "cppp") -> list[DiscoveredTender]:
    """The live portal's table: one row per tender, title cell holding the
    detail link plus a trailing '/Ref.No./TenderId' — the tender id (last
    segment) is the stable dedup key."""
    tenders: list[DiscoveredTender] = []
    for row_html in _ROW_RE.findall(html):
        cells = _TD_RE.findall(row_html)
        if len(cells) < 6:
            continue
        link = _LINK_RE.search(cells[4])
        if not link:
            continue
        href, title_html, trailing_html = link.groups()
        title = _clean(title_html)
        if not title:
            continue
        trailing = _clean(trailing_html).strip("/")
        external_id = trailing.split("/")[-1].strip() if trailing else unescape(href)
        tenders.append(
            DiscoveredTender(
                portal=portal,
                external_id=external_id or unescape(href),
                title=title,
                url=unescape(href),
                closing_at=_parse_listing_dt(_clean(cells[2])),
                organisation=_clean(cells[5]) or None,
                raw={"published": _clean(cells[1])},
            )
        )
    return tenders


def parse_listing(text: str, portal: str = "cppp") -> list[DiscoveredTender]:
    return parse_feed(text, portal) or parse_html_listing(text, portal)


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
