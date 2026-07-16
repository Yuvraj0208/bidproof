"""documents, parse_runs, pages, elements — grounding enforced in the schema

Revision ID: 0002
Revises: 0001

`elements` is the load-bearing table: every row MUST carry text, a valid
box, a real page, and a confidence (§9 rule 1). An ungrounded element is
unrepresentable, not merely discouraged.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

CURRENT_ORG = "NULLIF(current_setting('app.current_org_id', true), '')::uuid"


def _uuid_pk() -> sa.Column:
    return sa.Column(
        "id",
        postgresql.UUID(as_uuid=True),
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
    )


def _org_col() -> sa.Column:
    return sa.Column(
        "org_id",
        postgresql.UUID(as_uuid=True),
        sa.ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )


def upgrade() -> None:
    op.create_table(
        "documents",
        _uuid_pk(),
        _org_col(),
        sa.Column(
            "tender_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenders.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("filename", sa.String(), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("bucket", sa.String(), nullable=False),
        sa.Column("object_key", sa.String(), nullable=False),
        sa.Column("page_count", sa.Integer()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("org_id", "sha256", name="uq_documents_org_sha"),
    )
    op.create_index("ix_documents_tender_id", "documents", ["tender_id"])

    op.create_table(
        "parse_runs",
        _uuid_pk(),
        _org_col(),
        sa.Column(
            "document_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("status", sa.String(), nullable=False, server_default="pending"),
        sa.Column("pages_total", sa.Integer()),
        sa.Column("pages_text", sa.Integer()),
        sa.Column("pages_ocr", sa.Integer()),
        sa.Column("pages_flagged", sa.Integer()),
        sa.Column("elements_discarded", sa.Integer()),
        sa.Column("cost_inr", sa.Numeric(12, 4), nullable=False, server_default="0"),
        sa.Column("trace_id", sa.String()),
        sa.Column("error", sa.Text()),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('pending','running','succeeded','needs_human','failed')",
            name="ck_parse_runs_status",
        ),
    )
    op.create_index("ix_parse_runs_document_id", "parse_runs", ["document_id"])

    op.create_table(
        "pages",
        _uuid_pk(),
        _org_col(),
        sa.Column(
            "document_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("page_no", sa.Integer(), nullable=False),
        sa.Column("width", sa.Float(), nullable=False),
        sa.Column("height", sa.Float(), nullable=False),
        sa.Column("route", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.UniqueConstraint("document_id", "page_no", name="uq_pages_doc_page"),
        sa.CheckConstraint("page_no >= 1", name="ck_pages_page_no"),
        sa.CheckConstraint("route IN ('text','ocr')", name="ck_pages_route"),
        sa.CheckConstraint("status IN ('parsed','flagged')", name="ck_pages_status"),
        sa.CheckConstraint(
            "confidence >= 0 AND confidence <= 1", name="ck_pages_confidence"
        ),
    )

    op.create_table(
        "elements",
        sa.Column(
            "el_id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        _org_col(),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("page_no", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("x0", sa.Float(), nullable=False),
        sa.Column("y0", sa.Float(), nullable=False),
        sa.Column("x1", sa.Float(), nullable=False),
        sa.Column("y1", sa.Float(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        # An element must sit on a page that was actually parsed.
        sa.ForeignKeyConstraint(
            ["document_id", "page_no"],
            ["pages.document_id", "pages.page_no"],
            name="fk_elements_page",
            ondelete="CASCADE",
        ),
        # The grounding contract: no blank text, no degenerate box, no
        # out-of-range confidence can ever be stored.
        sa.CheckConstraint("length(btrim(text)) > 0", name="ck_elements_text"),
        sa.CheckConstraint("x1 > x0 AND y1 > y0", name="ck_elements_bbox"),
        sa.CheckConstraint(
            "confidence >= 0 AND confidence <= 1", name="ck_elements_confidence"
        ),
    )
    op.create_index("ix_elements_doc_page_seq", "elements", ["document_id", "page_no", "seq"])

    for table in ("documents", "parse_runs", "pages", "elements"):
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"""
            CREATE POLICY {table}_isolation ON {table}
            USING (org_id = {CURRENT_ORG})
            WITH CHECK (org_id = {CURRENT_ORG})
            """
        )
        op.execute(
            f"GRANT SELECT, INSERT, UPDATE, DELETE ON {table} TO bidproof_app"
        )


def downgrade() -> None:
    op.drop_table("elements")
    op.drop_table("pages")
    op.drop_table("parse_runs")
    op.drop_table("documents")
