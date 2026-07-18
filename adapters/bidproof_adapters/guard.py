"""The network guard (SPEC §10 tool guardrails, §11.4).

The Scout may ONLY reach an allow-list of portal domains. Adapters never see
a raw HTTP client — they receive a GuardedFetcher, and every request passes
the allow-list first. Blocked outright, regardless of the allow-list:
non-http(s) schemes, IP-literal hosts (kills 169.254.169.254-style metadata
and private-range SSRF), and localhost. Redirects are not followed — a
portal redirecting off-list is a failure, not a tunnel.
"""

import ipaddress
from typing import Iterable
from urllib.parse import urlparse

import httpx


class BlockedDomainError(RuntimeError):
    """URL refused by the allow-list. This is a security event, not a bug."""


class DomainAllowList:
    def __init__(self, domains: Iterable[str]) -> None:
        self._domains = {d.strip().lower().lstrip(".") for d in domains if d.strip()}

    @property
    def domains(self) -> frozenset[str]:
        return frozenset(self._domains)

    def extended(self, more: Iterable[str]) -> "DomainAllowList":
        return DomainAllowList(self._domains | set(more))

    def check(self, url: str) -> None:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            raise BlockedDomainError(f"scheme {parsed.scheme!r} is not allowed: {url}")
        host = (parsed.hostname or "").lower()
        if not host:
            raise BlockedDomainError(f"no host in url: {url}")
        if host == "localhost" or host.endswith(".localhost"):
            raise BlockedDomainError(f"localhost is never a portal: {url}")
        try:
            ipaddress.ip_address(host.strip("[]"))
        except ValueError:
            pass
        else:
            raise BlockedDomainError(f"IP-literal hosts are blocked (SSRF): {url}")
        if not any(host == d or host.endswith("." + d) for d in self._domains):
            raise BlockedDomainError(
                f"host {host!r} is not on the portal allow-list: {url}"
            )


class GuardedFetcher:
    """The only way anything in the Scout touches the network."""

    def __init__(
        self,
        allowlist: DomainAllowList,
        client: httpx.AsyncClient | None = None,
        max_download_bytes: int = 200 * 1024 * 1024,
    ) -> None:
        self.allowlist = allowlist
        self._client = client or httpx.AsyncClient(
            timeout=30, follow_redirects=False
        )
        self._max_download_bytes = max_download_bytes

    async def get(self, url: str) -> httpx.Response:
        self.allowlist.check(url)
        response = await self._client.get(url)
        response.raise_for_status()
        return response

    async def download(self, url: str) -> bytes:
        response = await self.get(url)
        data = response.content
        if len(data) > self._max_download_bytes:
            raise ValueError(
                f"download exceeds {self._max_download_bytes} bytes: {url}"
            )
        return data

    async def aclose(self) -> None:
        await self._client.aclose()
