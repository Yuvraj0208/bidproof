"""Discovery orchestration (US-01): the Scout runs the adapters, and every
discovered tender is deduplicated and pushed through the SAME ingest
pipeline as a manual upload (SPEC §5.1)."""

import hashlib
import logging
import uuid
from datetime import datetime, timezone

from fastapi import Depends
from sqlalchemy import select

from bidproof_adapters import DiscoveredTender, DomainAllowList, GuardedFetcher
from bidproof_adapters.contract import PortalAdapter
from bidproof_adapters.cppp import CpppAdapter
from bidproof_adapters.gem import GemAdapter
from bidproof_scout import run_adapters

from app.core.config import get_settings
from app.core.db import org_scoped_session
from app.models import DiscoveryRun, Document, Tender
from app.observability import LangfuseParseRunLogger, get_parse_logger
from app.parsing import get_ladder
from app.services import ingest
from app.services import triage as triage_service
from app.storage import ObjectStorage

logger = logging.getLogger(__name__)


def get_adapters() -> list[PortalAdapter]:
    settings = get_settings()
    return [
        GemAdapter(bids_url=settings.gem_bids_url),
        CpppAdapter(feed_url=settings.cppp_feed_url),
    ]


def build_allowlist() -> DomainAllowList:
    return DomainAllowList(get_settings().scout_allowed_domains.split(","))


async def get_discovery_fetcher():
    settings = get_settings()
    fetcher = GuardedFetcher(
        build_allowlist(),
        max_download_bytes=settings.max_upload_mb * 1024 * 1024,
    )
    try:
        yield fetcher
    finally:
        await fetcher.aclose()


async def run_discovery(
    org_id: uuid.UUID,
    adapters: list[PortalAdapter],
    fetcher: GuardedFetcher,
    storage: ObjectStorage,
    ladder,
    parse_logger: LangfuseParseRunLogger,
) -> dict:
    started_at = datetime.now(timezone.utc)
    scout_report = await run_adapters(adapters, fetcher)

    runs: list[dict] = []
    for adapter_run in scout_report.runs:
        summary = {
            "adapter": adapter_run.adapter,
            "ok": adapter_run.ok,
            "error": adapter_run.error,
            "duration_s": adapter_run.duration_s,
            "discovered": len(adapter_run.tenders),
            "ingested": 0,
            "duplicates": 0,
            "document_failures": 0,
            "ingest_errors": 0,
        }
        for dt in adapter_run.tenders:
            # One bad tender must not sink the run (same isolation principle
            # as one bad adapter, SPEC §20).
            try:
                outcome = await _ingest_one(
                    org_id, dt, fetcher, storage, ladder, parse_logger
                )
            except Exception:
                logger.exception(
                    "ingest failed for %s %s", dt.portal, dt.external_id
                )
                summary["ingest_errors"] += 1
                continue
            if outcome == "duplicate":
                summary["duplicates"] += 1
            else:
                summary["ingested"] += 1
                if outcome == "document_failed":
                    summary["document_failures"] += 1
        runs.append(summary)

    report = {"runs": runs}
    async with org_scoped_session(org_id) as session:
        session.add(
            DiscoveryRun(
                org_id=org_id,
                started_at=started_at,
                finished_at=datetime.now(timezone.utc),
                report=report,
            )
        )
    return report


async def _ingest_one(
    org_id: uuid.UUID,
    dt: DiscoveredTender,
    fetcher: GuardedFetcher,
    storage: ObjectStorage,
    ladder,
    parse_logger: LangfuseParseRunLogger,
) -> str:
    """Returns 'ingested', 'duplicate', or 'document_failed' (tender kept,
    document could not be fetched/parsed — visible, never silent)."""
    settings = get_settings()

    async with org_scoped_session(org_id) as session:
        existing = await session.execute(
            select(Tender.id).where(
                Tender.source == dt.portal, Tender.external_id == dt.external_id
            )
        )
        if existing.first():
            return "duplicate"

    data: bytes | None = None
    if dt.pdf_url:
        try:
            data = await fetcher.download(dt.pdf_url)
            ingest.validate_pdf_upload(data, settings.max_upload_mb * 1024 * 1024)
        except Exception as exc:
            logger.warning(
                "document fetch failed for %s %s: %s", dt.portal, dt.external_id, exc
            )
            data = None

    if data is not None:
        sha = hashlib.sha256(data).hexdigest()
        async with org_scoped_session(org_id) as session:
            dup = await session.execute(
                select(Document.tender_id).where(Document.sha256 == sha)
            )
            if dup.first():
                return "duplicate"

        tender_id, document_id, parse_run_id, _ = (
            await ingest.create_tender_with_document(
                org_id,
                filename=f"{dt.external_id.replace('/', '_')}.pdf",
                title=dt.title[:500],
                data=data,
                storage=storage,
                source=dt.portal,
                external_id=dt.external_id,
                portal_url=dt.url,
                closing_at=dt.closing_at,
            )
        )
        await ingest.execute_parse_run(
            org_id=org_id,
            tender_id=tender_id,
            document_id=document_id,
            parse_run_id=parse_run_id,
            pdf_bytes=data,
            ladder=ladder,
            parse_logger=parse_logger,
        )
        await triage_service.triage_after_parse(org_id, tender_id)
        return "ingested"

    # No document (portal gave no link, or the fetch failed): keep the tender
    # metadata — it is still a discovery — and say so in the report.
    async with org_scoped_session(org_id) as session:
        tender = Tender(
            org_id=org_id,
            title=dt.title[:500],
            source=dt.portal,
            external_id=dt.external_id,
            portal_url=dt.url,
            closing_at=dt.closing_at,
        )
        session.add(tender)
        await session.flush()
        metadata_tender_id = tender.id
    await triage_service.triage_after_parse(org_id, metadata_tender_id)
    return "document_failed" if dt.pdf_url else "ingested"
