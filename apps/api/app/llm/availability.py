"""Is real intelligence actually switched on?

The pipeline may run in two modes:

* **live**  — every agent calls its model role through the gateway.
* **deterministic** — the gateway is unreachable or a role is misconfigured, so
  agents fall back to their grounded templates.

Deterministic mode is a legitimate fallback (it is how the product demos with
no keys and no cost), but it must never be *silent*: a template answer that
looks like a model answer is how a shallow output reaches a customer. The
result of this probe is logged loudly at startup and surfaced in the UI
(SPEC §13; docs/FINISH_STATUS.md D9).
"""

import asyncio
import logging
import time

from app.llm.gateway import ROLES, LLMGateway, extract_text

logger = logging.getLogger(__name__)

_PROBE = [{"role": "user", "content": "Reply with the single word: OK"}]

# Cached so the UI can poll cheaply; refreshed at startup and on demand.
_status: dict | None = None
_probed_at: float = 0.0

# How long a probe result may be trusted. Without an expiry the very first
# probe won: an API that started while the LiteLLM container was still
# booting cached 'deterministic' and reported it forever, so the UI badge
# claimed templates long after real models were reachable. A badge that
# lies about whether answers came from a model is worse than no badge.
_CACHE_TTL_S = 60.0


async def probe_roles(timeout_s: float = 45.0) -> dict:
    """Ask every role for a reply. Returns per-role health + overall mode.

    The budget below is deliberately close to what the writer actually asks
    for. A tiny probe is dishonest: a provider checks whether the account can
    afford `max_tokens` up front, so a 200-token probe still succeeds on an
    exhausted balance while every real generation fails with 402 — the UI would
    show "live" while the pipeline silently served templates.

    A timeout gets ONE retry. Hosted providers are erratic under load — the same
    role was measured at 0.6 s and 21.7 s minutes apart — and a single slow reply
    was enough to paint the whole app DEGRADED before a demo when nothing was
    wrong. A 402 or an auth failure is never retried: those are definitive
    answers, and retrying them would only slow down the honest bad news.
    """
    gateway = LLMGateway()
    roles: dict[str, dict] = {}
    try:
        for role in sorted(ROLES):
            roles[role] = await _probe_one(gateway, role, timeout_s)
    finally:
        await gateway.aclose()

    healthy = [r for r, v in roles.items() if v["ok"]]
    mode = "live" if len(healthy) == len(ROLES) else (
        "degraded" if healthy else "deterministic"
    )
    return {"mode": mode, "roles": roles, "healthy": sorted(healthy)}


def _is_definitive(exc: Exception) -> bool:
    """Errors a retry cannot change: no credit, bad key, unknown model."""
    text = str(exc)
    return any(
        marker in text
        for marker in ("402", "Payment Required", "401", "403", "invalid_api_key")
    )


async def _probe_one(gateway: LLMGateway, role: str, timeout_s: float) -> dict:
    last: Exception | None = None
    for attempt in (1, 2):
        try:
            async with asyncio.timeout(timeout_s):
                response = await gateway.complete(role, messages=_PROBE, max_tokens=1600)
            # A probe only proves the role answers, so reasoning text counts here.
            extract_text(response, allow_reasoning=True)
            if attempt > 1:
                logger.warning("role %s answered on retry after a timeout", role)
            return {"ok": True, "model": response.get("model"), "error": None}
        except Exception as exc:
            last = exc
            if _is_definitive(exc) or attempt == 2:
                break
            logger.warning(
                "role %s did not answer within %.0fs; retrying once", role, timeout_s
            )

    detail = f"{type(last).__name__}: {str(last)[:160]}"
    # The most common real-world cause, named plainly so the UI can tell the
    # operator what to actually do about it.
    if _is_definitive(last) and ("402" in str(last) or "Payment Required" in str(last)):
        detail = (
            "no model credit — the provider refused the request "
            "(402 Payment Required). Top up the account behind the "
            "gateway; until then results come from templates."
        )
    elif isinstance(last, TimeoutError):
        detail = (
            f"the gateway did not answer within {timeout_s:.0f}s, twice. "
            "The provider may be overloaded — retry, or check the gateway."
        )
    return {"ok": False, "model": None, "error": detail}


async def refresh() -> dict:
    global _status, _probed_at
    _status = await probe_roles()
    _probed_at = time.monotonic()
    return _status


def cached() -> dict | None:
    """The last probe, or None once it is stale enough to be re-checked.

    Returning None makes the caller re-probe, which is how the badge recovers
    on its own after the gateway comes back.
    """
    if _status is None:
        return None
    if time.monotonic() - _probed_at > _CACHE_TTL_S:
        return None
    return _status


async def log_at_startup() -> None:
    """Loud, unmissable log line. Never raises — the API must still boot so the
    UI can *show* the degraded mode rather than the user meeting a dead port."""
    try:
        status = await refresh()
    except Exception as exc:  # pragma: no cover - defensive
        logger.error("MODEL CHECK FAILED: %s", exc)
        return
    if status["mode"] == "live":
        logger.info(
            "MODEL CHECK: live — all roles reachable (%s)",
            ", ".join(f"{r}={v['model']}" for r, v in status["roles"].items()),
        )
        return
    broken = {r: v["error"] for r, v in status["roles"].items() if not v["ok"]}
    logger.error(
        "MODEL CHECK: %s — real intelligence is NOT fully on. "
        "Broken roles: %s. Agents will fall back to grounded templates and the "
        "UI will show 'deterministic'. Fix the gateway/keys before demoing.",
        status["mode"].upper(),
        broken,
    )
