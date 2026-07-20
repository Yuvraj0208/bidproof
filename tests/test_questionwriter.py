"""US-08 unit tests: grounded cited letters, the polish ground-check, and the
structural guarantee that the QuestionWriter cannot send anything."""

import importlib
import inspect
from datetime import date

from bidproof_questionwriter import (
    FailedRule,
    draft_letter,
    keep_polished_body,
)

RULE = FailedRule(
    rule_id="r-1", family="technical", key="required_standard",
    requirement_text="Bidder must hold valid ISO 27001 certification.",
    el_id="el-9", page_no=3,
    verdict_reason="no certificate or product covers ISO 27001.",
)


def test_letter_cites_the_clause_and_page():
    draft = draft_letter(RULE, "Demo Manufacturing Co", date(2026, 8, 1))
    assert draft.cites_el_id == "el-9"
    assert draft.cites_page == 3
    assert "page 3" in draft.body
    assert "ISO 27001" in draft.body           # the actual clause text
    assert "Demo Manufacturing Co" in draft.body
    assert "2026-08-01" in draft.body           # the query deadline
    assert "relax" in draft.body.lower()


def test_letter_without_deadline_still_grounded():
    draft = draft_letter(RULE, "Acme", None)
    assert "page 3" in draft.body
    assert "pre-bid query deadline" in draft.body


def test_polish_kept_only_if_it_preserves_the_citation():
    draft = draft_letter(RULE, "Acme", None)
    good = "Refined letter body that still references page 3 clearly."
    assert keep_polished_body(draft, good) == good

    dropped = "A slicker letter that forgot to mention which clause."
    assert keep_polished_body(draft, dropped) == draft.body   # template kept

    assert keep_polished_body(draft, None) == draft.body
    assert keep_polished_body(draft, "   ") == draft.body


def test_questionwriter_cannot_send_anything():
    """Least privilege (SPEC §10): no send/email/submit/post capability exists
    anywhere in the package — drafting only, by construction."""
    forbidden = ("send", "email", "submit", "post", "smtp", "deliver")
    module = importlib.import_module("bidproof_questionwriter")
    for name, member in inspect.getmembers(module):
        if inspect.isfunction(member) or inspect.isclass(member):
            assert not any(f in name.lower() for f in forbidden), (
                f"{name} looks like a send capability — the QuestionWriter must "
                "never send"
            )
        # and no callable's source references a network/mail client
    source = inspect.getsource(importlib.import_module("bidproof_questionwriter.letters"))
    for banned in ("smtplib", "requests.", "httpx.", "urllib", "socket"):
        assert banned not in source, f"letters.py must not reference {banned}"
