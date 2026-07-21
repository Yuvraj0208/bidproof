"""Standard bid declarations, filled from real data only (SPEC §5.8).

Filling is deterministic lookup: each field names a data source, and the
value comes from the verified context or not at all. A missing source is
left blank and flagged — never inferred, never defaulted. There is no model
here, so a guessed legal declaration is impossible by construction.
"""

from dataclasses import dataclass, field

# Sources a human must always complete themselves (an act of signing, not a
# fact about the company) — always flagged.
HUMAN_ONLY_SOURCES = frozenset(
    {"authorised_signatory", "signatory_designation", "place", "declaration_date"}
)


@dataclass(frozen=True)
class FieldSpec:
    key: str
    label: str
    source: str          # which context value fills this field
    legal: bool = True   # part of a legal declaration


@dataclass(frozen=True)
class DeclarationTemplate:
    id: str
    title: str
    fields: tuple[FieldSpec, ...]


@dataclass
class FilledField:
    key: str
    label: str
    value: str | None
    filled: bool
    flagged: bool
    source: str
    reason: str | None = None


@dataclass
class FilledDeclaration:
    template_id: str
    title: str
    fields: list[FilledField]

    @property
    def complete(self) -> bool:
        return all(f.filled for f in self.fields)

    @property
    def flagged_count(self) -> int:
        return sum(1 for f in self.fields if f.flagged)


def _field(key: str, label: str, source: str) -> FieldSpec:
    return FieldSpec(key=key, label=label, source=source)


NON_BLACKLISTING = DeclarationTemplate(
    id="non_blacklisting",
    title="Declaration of Non-Blacklisting",
    fields=(
        _field("company_name", "Name of bidder", "company_legal_name"),
        _field("blacklist_status", "Blacklisting status", "blacklist_status"),
        _field("authorised_signatory", "Authorised signatory", "authorised_signatory"),
        _field("place", "Place", "place"),
        _field("date", "Date", "declaration_date"),
    ),
)

MSME_DECLARATION = DeclarationTemplate(
    id="msme_status",
    title="MSME / Startup Status Declaration",
    fields=(
        _field("company_name", "Name of bidder", "company_legal_name"),
        _field("msme_status", "MSME status", "msme_status"),
        _field("authorised_signatory", "Authorised signatory", "authorised_signatory"),
        _field("date", "Date", "declaration_date"),
    ),
)

FINANCIAL_DECLARATION = DeclarationTemplate(
    id="financial_capability",
    title="Declaration of Financial Capability",
    fields=(
        _field("company_name", "Name of bidder", "company_legal_name"),
        _field("latest_turnover", "Latest annual turnover", "latest_turnover"),
        _field("net_worth", "Net worth", "net_worth"),
        _field("authorised_signatory", "Authorised signatory", "authorised_signatory"),
        _field("place", "Place", "place"),
        _field("date", "Date", "declaration_date"),
    ),
)

INTEGRITY_PACT = DeclarationTemplate(
    id="integrity_pact",
    title="Integrity Pact",
    fields=(
        _field("company_name", "Name of bidder", "company_legal_name"),
        _field("registered_office", "Registered office", "registered_office"),
        _field("authorised_signatory", "Authorised signatory", "authorised_signatory"),
        _field("signatory_designation", "Designation", "signatory_designation"),
        _field("place", "Place", "place"),
        _field("date", "Date", "declaration_date"),
    ),
)

STANDARD_DECLARATIONS: tuple[DeclarationTemplate, ...] = (
    NON_BLACKLISTING,
    MSME_DECLARATION,
    FINANCIAL_DECLARATION,
    INTEGRITY_PACT,
)


def template_by_id(template_id: str) -> DeclarationTemplate | None:
    return next((t for t in STANDARD_DECLARATIONS if t.id == template_id), None)


def fill_declaration(
    template: DeclarationTemplate, context: dict[str, str | None]
) -> FilledDeclaration:
    """Fill each field from the context, or leave it blank and flagged. The
    context holds only verified company data; anything absent is a human's
    to complete."""
    filled: list[FilledField] = []
    for spec in template.fields:
        value = context.get(spec.source)
        has_value = isinstance(value, str) and value.strip() != ""
        if has_value:
            filled.append(FilledField(
                key=spec.key, label=spec.label, value=value.strip(),
                filled=True, flagged=False, source=spec.source,
            ))
        else:
            reason = (
                "to be signed/entered by a human"
                if spec.source in HUMAN_ONLY_SOURCES
                else "no verified data on file — a human must complete this"
            )
            filled.append(FilledField(
                key=spec.key, label=spec.label, value=None,
                filled=False, flagged=True, source=spec.source, reason=reason,
            ))
    return FilledDeclaration(template.id, template.title, filled)
