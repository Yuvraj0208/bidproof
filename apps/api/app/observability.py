"""Parse-run tracing (SPEC §13): every run is recorded under the tender's
trace id with page counts, duration, and rupee cost. Missing Langfuse keys
disable logging gracefully — observability must never take the pipeline down.
"""

import logging
from dataclasses import asdict, dataclass
from functools import lru_cache

from app.core.config import get_settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ParseRunLog:
    trace_id: str  # tender uuid hex — one trace follows the tender end to end
    tender_id: str
    document_id: str
    parse_run_id: str
    status: str
    pages_total: int
    pages_text: int
    pages_ocr: int
    pages_flagged: int
    elements: int
    elements_discarded: int
    cost_inr: float
    duration_s: float
    error: str | None = None


class LangfuseParseRunLogger:
    def __init__(self) -> None:
        settings = get_settings()
        self._client = None
        if settings.langfuse_public_key and settings.langfuse_secret_key:
            try:
                from langfuse import Langfuse

                self._client = Langfuse(
                    public_key=settings.langfuse_public_key,
                    secret_key=settings.langfuse_secret_key,
                    host=settings.langfuse_host,
                )
            except Exception:
                logger.warning("langfuse unavailable; parse runs not traced")

    def log(self, entry: ParseRunLog) -> None:
        if self._client is None:
            return
        try:
            metadata = asdict(entry)
            if hasattr(self._client, "trace"):  # SDK v2 API
                trace = self._client.trace(
                    id=entry.trace_id, name="tender", metadata={"tender_id": entry.tender_id}
                )
                trace.span(name="parse_run", metadata=metadata)
            else:  # SDK v3 (OTel) API
                span = self._client.start_span(
                    name="parse_run",
                    metadata=metadata,
                    trace_context={"trace_id": entry.trace_id},
                )
                span.end()
            self._client.flush()
        except Exception:
            logger.warning("failed to log parse run to langfuse", exc_info=True)


@lru_cache
def _default_logger() -> LangfuseParseRunLogger:
    return LangfuseParseRunLogger()


def get_parse_logger() -> LangfuseParseRunLogger:
    return _default_logger()


async def record_agent_run(
    org_id,
    tender_id,
    agent: str,
    *,
    duration_ms: int,
    status: str = "ok",
    model_role: str | None = None,
    prompt_version: str | None = None,
    tokens_in: int = 0,
    tokens_out: int = 0,
    cost_inr: float = 0.0,
    meta: dict | None = None,
) -> None:
    """One recorded step under the tender's trace id (SPEC §13). Recording
    must never take the pipeline down — failures are logged and swallowed."""
    from app.core.db import org_scoped_session
    from app.models import AgentRun

    try:
        async with org_scoped_session(org_id) as session:
            session.add(
                AgentRun(
                    org_id=org_id,
                    tender_id=tender_id,
                    trace_id=tender_id.hex,
                    agent=agent,
                    status=status,
                    model_role=model_role,
                    prompt_version=prompt_version,
                    tokens_in=tokens_in,
                    tokens_out=tokens_out,
                    cost_inr=cost_inr,
                    duration_ms=duration_ms,
                    meta=meta or {},
                )
            )
    except Exception:
        logger.warning("failed to record agent run %s/%s", agent, tender_id,
                       exc_info=True)
