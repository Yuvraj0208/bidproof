"""FormFiller integration (SPEC §5.8): declarations are filled from the
capability database, unknown fields flagged, and everything is tenant-scoped."""

import pytest

from test_capability import FACT, PRODUCT
from test_checking_api import client_for, make_app
from test_rules_api import FakeGateway
from test_upload_api import create_org

pytestmark = pytest.mark.integration

BLACKLIST_FACT = {
    "fact_type": "blacklist_status", "value_text": "none",
    "source": "synthetic demo data", "verified_at": "2026-07-01",
}
MSME_FACT = {
    "fact_type": "msme_status", "value_text": "not_msme",
    "source": "synthetic demo data", "verified_at": "2026-07-01",
}


async def test_declarations_filled_from_capability_with_flags(owner_conn):
    org_id = await create_org(owner_conn)
    app = make_app(FakeGateway([]))

    async with client_for(app, org_id) as client:
        assert (await client.post("/capability/facts", json=FACT)).status_code == 201
        assert (await client.post("/capability/facts", json=BLACKLIST_FACT)).status_code == 201
        assert (await client.post("/capability/facts", json=MSME_FACT)).status_code == 201

        declarations = (await client.get("/declarations")).json()
        non_blacklisting = (
            await client.get("/declarations/non_blacklisting")
        ).json()

    assert {d["template_id"] for d in declarations} >= {
        "non_blacklisting", "msme_status", "financial_capability", "integrity_pact"
    }

    fields = {f["key"]: f for f in non_blacklisting["fields"]}
    # filled from real capability data
    assert fields["company_name"]["filled"] is True
    assert fields["blacklist_status"]["filled"] is True
    assert "blacklisted" in fields["blacklist_status"]["value"].lower()
    # a human's to sign → blank + flagged
    assert fields["authorised_signatory"]["flagged"] is True
    assert fields["authorised_signatory"]["value"] is None
    assert non_blacklisting["complete"] is False
    assert non_blacklisting["flagged_count"] >= 1


async def test_declarations_with_no_capability_are_all_flagged(owner_conn):
    org_id = await create_org(owner_conn)   # no facts seeded
    app = make_app(FakeGateway([]))

    async with client_for(app, org_id) as client:
        financial = (await client.get("/declarations/financial_capability")).json()

    # company_name may resolve from the org record; the money fields cannot,
    # so they are blank and flagged — never invented.
    turnover = next(f for f in financial["fields"] if f["key"] == "latest_turnover")
    net_worth = next(f for f in financial["fields"] if f["key"] == "net_worth")
    assert turnover["value"] is None and turnover["flagged"] is True
    assert net_worth["value"] is None and net_worth["flagged"] is True


async def test_unknown_template_is_404(owner_conn):
    org_id = await create_org(owner_conn)
    app = make_app(FakeGateway([]))
    async with client_for(app, org_id) as client:
        response = await client.get("/declarations/no_such_form")
    assert response.status_code == 404


async def test_declarations_are_tenant_scoped(owner_conn):
    org_a = await create_org(owner_conn)
    org_b = await create_org(owner_conn)
    app = make_app(FakeGateway([]))

    async with client_for(app, org_a) as client:
        await client.post("/capability/facts", json=FACT)
        a_name = next(
            f for f in (await client.get("/declarations/non_blacklisting")).json()["fields"]
            if f["key"] == "company_name"
        )
    async with client_for(app, org_b) as client:
        b_name = next(
            f for f in (await client.get("/declarations/non_blacklisting")).json()["fields"]
            if f["key"] == "company_name"
        )

    # org A's declaration carries org A's legal entity; org B never saw it.
    assert a_name["value"] == "Demo Manufacturing Co Ltd"
    assert b_name["value"] != "Demo Manufacturing Co Ltd"
