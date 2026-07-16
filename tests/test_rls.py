"""Row-level security: tenant isolation must hold at the database layer
(SPEC §15). All tests run through the RLS-constrained app role, never the
owner. Marked integration — they need a live Postgres."""

import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

pytestmark = pytest.mark.integration

SET_ORG = "SELECT set_config('app.current_org_id', :org_id, true)"


async def seed_two_orgs(owner_conn):
    org_a, org_b = uuid.uuid4(), uuid.uuid4()
    await owner_conn.execute(
        text(
            "INSERT INTO organizations (id, name, slug) VALUES "
            "(:a, 'Org A', 'org-a'), (:b, 'Org B', 'org-b')"
        ),
        {"a": org_a, "b": org_b},
    )
    await owner_conn.execute(
        text(
            "INSERT INTO tenders (org_id, title, source) VALUES "
            "(:a, 'Tender A', 'manual'), (:b, 'Tender B', 'manual')"
        ),
        {"a": org_a, "b": org_b},
    )
    await owner_conn.commit()
    return org_a, org_b


async def test_rls_blocks_cross_org_reads(owner_conn, app_engine):
    org_a, org_b = await seed_two_orgs(owner_conn)

    async with app_engine.connect() as conn:
        await conn.execute(text(SET_ORG), {"org_id": str(org_a)})
        rows = (await conn.execute(text("SELECT title FROM tenders"))).fetchall()

    assert [row.title for row in rows] == ["Tender A"]


async def test_rls_fails_closed_without_org_context(owner_conn, app_engine):
    await seed_two_orgs(owner_conn)

    async with app_engine.connect() as conn:
        rows = (await conn.execute(text("SELECT id FROM tenders"))).fetchall()
        org_rows = (await conn.execute(text("SELECT id FROM organizations"))).fetchall()

    assert rows == [], "without org context, tenders must be invisible"
    assert org_rows == [], "without org context, organizations must be invisible"


async def test_rls_blocks_cross_org_writes(owner_conn, app_engine):
    org_a, org_b = await seed_two_orgs(owner_conn)

    async with app_engine.connect() as conn:
        await conn.execute(text(SET_ORG), {"org_id": str(org_a)})
        with pytest.raises(DBAPIError):
            await conn.execute(
                text(
                    "INSERT INTO tenders (org_id, title, source) "
                    "VALUES (:org, 'Smuggled', 'manual')"
                ),
                {"org": str(org_b)},
            )


async def test_rls_is_forced_and_app_role_cannot_bypass(owner_conn):
    for table in ("tenders", "organizations"):
        row = (
            await owner_conn.execute(
                text(
                    "SELECT relrowsecurity, relforcerowsecurity "
                    "FROM pg_class WHERE relname = :t"
                ),
                {"t": table},
            )
        ).one()
        assert row.relrowsecurity, f"RLS not enabled on {table}"
        assert row.relforcerowsecurity, f"RLS not FORCED on {table} (owner would bypass)"

        owner = (
            await owner_conn.execute(
                text("SELECT tableowner FROM pg_tables WHERE tablename = :t"),
                {"t": table},
            )
        ).scalar_one()
        assert owner != "bidproof_app", f"app role must not own {table}"

    role = (
        await owner_conn.execute(
            text(
                "SELECT rolbypassrls, rolsuper FROM pg_roles "
                "WHERE rolname = 'bidproof_app'"
            )
        )
    ).one()
    assert not role.rolbypassrls, "app role must not have BYPASSRLS"
    assert not role.rolsuper, "app role must not be superuser"
