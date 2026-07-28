"""Turning what we scraped into a link a human can still click.

Portals differ in whether their URLs are addresses or tickets:

- **GeM** links are addresses. `bidplus.gem.gov.in/showbidDocument/<id>` answers
  with the PDF itself, with no session, cookie or captcha.
- **CPPP** has no address to offer at all. Three things were checked live on
  2026-07-26, and all three are dead ends:
    1. a `/cppp/tendersfullview/...` deep link encodes a hash and the unix
       timestamp of the moment the listing was rendered, and only resolves for the
       session that minted it — otherwise *"Invalid Url.Please Check"*;
    2. even WITH that session the page carries no tender content, only
       *"Enter the characters shown in the image"* — the detail view is
       captcha-gated, not just the documents;
    3. there is no RSS/XML feed (`/cppp/rss*` → 404), so the public listing is
       the entire captcha-free surface.

So for CPPP there is no honest link to a tender, and pointing every row at the
search page was its own bug: eight tenders all landing on the same captcha form
looks broken, because functionally it is. `stable_portal_url` therefore returns
None for CPPP, and the manual route lives in `portal_search_url`, which the UI
labels for what it is. A captcha is a deliberate "no automation" sign and we
respect it — we do not solve them.

Pure functions — no I/O, so they are cheap to test and cannot fail at runtime.
"""

from urllib.parse import urlparse

# Stable entry points, verified reachable 2026-07-26.
CPPP_SEARCH = "https://eprocure.gov.in/cppp/tendersearch"
GEM_SEARCH = "https://bidplus.gem.gov.in/all-bids"

_SEARCH_BY_SOURCE = {"cppp": CPPP_SEARCH, "gem": GEM_SEARCH}

# The marker CPPP puts between the base64 segments of a session-bound deep link.
_CPPP_TICKET_MARKER = "A13h1"


def is_ephemeral(url: str | None) -> bool:
    """Whether this URL is a session ticket rather than a durable address."""
    if not url:
        return False
    return _CPPP_TICKET_MARKER in url or "/tendersfullview/" in url


def stable_portal_url(source: str, portal_url: str | None) -> str | None:
    """A link that lands ON this tender, or None when the portal offers none.

    Never falls back to a search page: a link labelled "open the tender" has to
    open the tender. The manual route is a separate, separately-labelled thing
    (`portal_search_url`).
    """
    if not portal_url or is_ephemeral(portal_url):
        return None
    host = (urlparse(portal_url).hostname or "").lower()
    # Only trust a link that really belongs to a portal we know. Anything else
    # is data we scraped, and data does not get to choose our links.
    if host.endswith("gem.gov.in") or host.endswith("eprocure.gov.in"):
        return portal_url
    return None


def portal_search_url(source: str) -> str | None:
    """Where a human can look this tender up by hand, or None if nowhere.

    On CPPP this form requires a captcha, which is why it is kept apart from
    `stable_portal_url` — the UI has to warn before sending anyone there.
    """
    return _SEARCH_BY_SOURCE.get((source or "").lower())


def requires_captcha(source: str) -> bool:
    """Whether reaching this tender by hand means solving a captcha."""
    return (source or "").lower() == "cppp"


_PORTAL_NAMES = {"cppp": "CPPP", "gem": "GeM"}


def portal_hint(source: str, external_id: str | None, portal_url: str | None) -> str | None:
    """One line telling the human what to do, or None when nothing needs saying.

    Silent in the two cases where a hint would be a lie: a link that works, and
    a tender that never came from a portal at all (a manual upload has nothing
    to search for and no link that expired).
    """
    portal = _PORTAL_NAMES.get((source or "").lower())
    if portal is None:
        return None
    if portal_url and not is_ephemeral(portal_url):
        return None

    reference = (external_id or "").strip()
    if requires_captcha(source):
        # Say the whole truth: there is no link we can give, and the manual
        # route costs a captcha. Anything vaguer just sends them in circles.
        subject = f"reference {reference}" if reference else "this tender"
        return (
            f"{portal} publishes the listing only. Its tender page and documents "
            f"both sit behind a captcha, so BidProof cannot open or read them — "
            f"search {portal} for {subject} by hand, or upload the PDF here."
        )
    where = (
        f"Search {portal} for reference {reference}."
        if reference
        else f"Search {portal} directly."
    )
    return f"{portal} gave us no direct link for this tender. {where}"


# Paths that answer with the document itself, per portal. Verified live
# 2026-07-26: GeM returns `application/pdf` here with no session, cookie or
# captcha. CPPP has no equivalent — its documents go through a POST form.
_DOCUMENT_PATHS = ("/showbiddocument/",)


def document_url(source: str, portal_url: str | None) -> str | None:
    """The URL that IS the tender document, or None if we have no such link.

    Deliberately narrow. `portal_url` is scraped data, so it is never trusted as
    a fetch target on its own — it has to be a known portal host AND a known
    document path before anything downloads it (SPEC §11.1 SSRF boundary). The
    fetcher's allow-list is the second gate, not the first.
    """
    if not portal_url or (source or "").lower() != "gem":
        return None
    parsed = urlparse(portal_url)
    if parsed.scheme not in ("http", "https"):
        return None
    host = (parsed.hostname or "").lower()
    if not (host == "gem.gov.in" or host.endswith(".gem.gov.in")):
        return None
    if not any(part in parsed.path.lower() for part in _DOCUMENT_PATHS):
        return None
    return portal_url
