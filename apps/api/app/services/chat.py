"""Ask BidProof (US-15, SPEC §8.3, §11.2).

The chat answers ONLY from this tender's grounded elements and cites the
page for every answer. It hard-refuses anything out of scope, and the Guard
screens both the question and the answer. Refusal is a security feature.
"""

import logging
import re
import uuid

from sqlalchemy import select

from bidproof_guard import scan

from app.core.db import org_scoped_session
from app.llm.gateway import LLMGateway
from app.models import ChatMessage, Document, Element, Tender

logger = logging.getLogger(__name__)

OUT_OF_SCOPE = "I can only discuss the tenders in this workspace."
_TOKEN_RE = re.compile(r"[a-z0-9]{3,}")
_STOPWORDS = frozenset({
    "the", "what", "which", "does", "this", "that", "for", "are", "and",
    "how", "why", "who", "where", "when", "our", "your", "with", "from",
    "tender", "bid", "please", "tell", "about", "can", "you",
})


def _tokens(text: str) -> set[str]:
    return {t for t in _TOKEN_RE.findall(text.lower())} - _STOPWORDS


def get_chat_gateway() -> LLMGateway:
    return LLMGateway()


async def _log(session, org_id, tender_id, role, content, citations=None,
               refused=False, reason=None) -> None:
    session.add(ChatMessage(
        org_id=org_id, tender_id=tender_id, role=role, content=content,
        citations=citations or [], refused=refused, refusal_reason=reason,
    ))


async def ask(
    org_id: uuid.UUID, tender_id: uuid.UUID, question: str,
    gateway: LLMGateway | None = None,
) -> dict | None:
    guard = scan(question)

    async with org_scoped_session(org_id) as session:
        tender = await session.get(Tender, tender_id)
        if tender is None:
            return None
        await _log(session, org_id, tender_id, "user", question)

        # 1. Guard: a jailbreak / injection attempt is refused and recorded.
        if guard.flagged:
            reason = f"blocked by guard ({guard.category})"
            answer = (
                "That request was blocked as a possible prompt-injection or "
                "jailbreak attempt, and has been logged. " + OUT_OF_SCOPE
            )
            await _log(session, org_id, tender_id, "assistant", answer,
                       refused=True, reason=reason)
            return {"answer": answer, "citations": [], "refused": True,
                    "reason": reason}

        # 2. Retrieve from THIS tender's elements only.
        document = (
            await session.execute(
                select(Document.id)
                .where(Document.tender_id == tender_id)
                .order_by(Document.version.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        elements = []
        if document is not None:
            elements = (
                await session.execute(
                    select(Element)
                    .where(Element.document_id == document)
                    .order_by(Element.page_no, Element.seq)
                )
            ).scalars().all()

        wanted = _tokens(question)
        scored = []
        for el in elements:
            overlap = len(wanted & _tokens(el.text))
            if overlap:
                scored.append((overlap, el))
        scored.sort(key=lambda pair: pair[0], reverse=True)
        top = [el for _, el in scored[:3]]

        # 3. Nothing relevant in this tender → hard refusal (scope = security).
        if not top:
            await _log(session, org_id, tender_id, "assistant", OUT_OF_SCOPE,
                       refused=True, reason="out_of_scope")
            return {"answer": OUT_OF_SCOPE, "citations": [], "refused": True,
                    "reason": "out_of_scope"}

        # 4. Grounded answer, citing the page for each element used.
        citations = [
            {"el_id": str(el.el_id), "page_no": el.page_no}
            for el in top
        ]
        answer = _compose_answer(question, top, gateway)
        # The Guard also screens the answer before it is shown.
        if scan(answer).flagged:
            answer = OUT_OF_SCOPE
            citations = []
        await _log(session, org_id, tender_id, "assistant", answer, citations)
        return {"answer": answer, "citations": citations, "refused": False,
                "reason": None}


def _compose_answer(question: str, elements, gateway: LLMGateway | None) -> str:
    """Deterministic grounded answer — quotes the matched clauses with their
    page. (A small model can restyle this later; the citation is fixed.)"""
    parts = [
        f'On page {el.page_no}: "{el.text.strip()}"' for el in elements
    ]
    return "Based on this tender:\n" + "\n".join(parts)


async def history(org_id: uuid.UUID, tender_id: uuid.UUID) -> list[dict]:
    async with org_scoped_session(org_id) as session:
        rows = (
            await session.execute(
                select(ChatMessage)
                .where(ChatMessage.tender_id == tender_id)
                .order_by(ChatMessage.created_at)
            )
        ).scalars()
        return [
            {"role": m.role, "content": m.content, "citations": m.citations,
             "refused": m.refused, "reason": m.refusal_reason}
            for m in rows
        ]
