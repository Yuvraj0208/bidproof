"""Seed the Librarian from docs/REFERENCE_PROPOSAL.md.

Part A of that document asks for exactly this: chop the reference into tagged
blocks with section labels, so the ProposalWriter retrieves real structural
precedents instead of inventing a layout.

Why it matters more than it sounds. The writer's style reference is whatever
the Librarian returns; with nothing seeded it returns "none available" and the
model falls back on its own idea of what a bid looks like — which is where
three-paragraph sections come from. Feeding it the reference makes the target
shape retrievable rather than described.

The blocks are parsed out of the markdown rather than copied into this file, so
the reference stays the single source of truth. Editing the document changes
what the writer retrieves; there is no second copy to drift.

Run:  python -m uv run --project apps/api python infra/seed/seed_reference_proposal.py
"""

from __future__ import annotations

import asyncio
import os
import re
import sys
import uuid
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
REFERENCE = REPO_ROOT / "docs" / "REFERENCE_PROPOSAL.md"

# The reference's numbered headings, mapped onto the writer's section tags.
# A heading with no mapping is skipped rather than guessed at — a block filed
# under the wrong section is worse than one that is missing, because the writer
# will faithfully imitate it.
SECTION_MAP = {
    "covering letter": "cover_letter",
    "understanding of the requirement": "understanding_of_requirement",
    "technical compliance statement": "technical_compliance",
    "eligibility and credentials": "eligibility_compliance",
    "technical approach and methodology": "technical_approach",
    "quality assurance": "quality_assurance",
    "programme of work": "programme_of_work",
    "statement of deviations": "deviations",
    "schedule of enclosures": "schedule_of_enclosures",
    "price schedule": "commercial_terms",
}

_HEADING_RE = re.compile(r"^###\s+\d+\.\s+(.+?)\s*$", re.MULTILINE)


def parse_blocks(markdown: str) -> list[tuple[str, str]]:
    """(section_tag, text) for each mapped section of the reference."""
    matches = list(_HEADING_RE.finditer(markdown))
    blocks: list[tuple[str, str]] = []

    for i, match in enumerate(matches):
        title = match.group(1).strip().lower()
        # "Covering Letter (Annexure-A)" -> "covering letter"
        title = re.sub(r"\s*\(.*?\)\s*", "", title).strip()
        tag = SECTION_MAP.get(title)
        if tag is None:
            continue

        end = matches[i + 1].start() if i + 1 < len(matches) else len(markdown)
        body = markdown[match.end():end].strip()
        # Drop the horizontal rules that separate sections in the source.
        body = re.sub(r"^---+$", "", body, flags=re.MULTILINE).strip()
        if body:
            blocks.append((tag, body))

    return blocks


async def main() -> None:
    sys.path.insert(0, str(REPO_ROOT / "apps" / "api"))
    from sqlalchemy import delete, select

    from app.core.db import org_scoped_session
    from app.models import LibraryBlockRow, Organization

    if not REFERENCE.exists():
        raise SystemExit(f"reference not found: {REFERENCE}")

    blocks = parse_blocks(REFERENCE.read_text(encoding="utf-8"))
    if not blocks:
        raise SystemExit("no sections parsed — has the reference's heading style changed?")

    org_id = os.environ.get("SEED_ORG_ID")
    if org_id is None:
        # Default to the only org, so the common case needs no argument.
        from app.core.db import get_engine
        from sqlalchemy.ext.asyncio import AsyncSession

        async with AsyncSession(get_engine()) as session:
            rows = (await session.execute(select(Organization.id))).scalars().all()
        if len(rows) != 1:
            raise SystemExit(
                f"{len(rows)} organisations found — set SEED_ORG_ID to choose one"
            )
        org_id = str(rows[0])

    org = uuid.UUID(org_id)
    async with org_scoped_session(org) as session:
        # Replace rather than append: re-running after editing the reference
        # should leave one copy, not two competing precedents.
        await session.execute(
            delete(LibraryBlockRow).where(
                LibraryBlockRow.source_name == "REFERENCE_PROPOSAL.md"
            )
        )
        for section_tag, text in blocks:
            session.add(LibraryBlockRow(
                org_id=org,
                section_tag=section_tag,
                text=text,
                outcome="won",
                source_name="REFERENCE_PROPOSAL.md",
                # Pre-approved: this is our own reference document, not
                # third-party text that needs quarantining (SPEC §11.3).
                quarantined=False,
            ))

    print(f"seeded {len(blocks)} reference blocks for org {org}:")
    for tag, text in blocks:
        print(f"  {tag:32} {len(text):5} chars")


if __name__ == "__main__":
    asyncio.run(main())
