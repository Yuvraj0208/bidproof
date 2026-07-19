"""The strict JSON schema the model must fill (§9 rule 6). Malformed output
is rejected — the caller retries or drops the AI side entirely. It is never
patched into shape. No free-text channel flows downstream."""

import json
import re

from pydantic import BaseModel, ConfigDict, ValidationError, field_validator

from bidproof_extractor.types import FAMILIES


class AiRule(BaseModel):
    model_config = ConfigDict(extra="forbid")

    family: str
    key: str
    requirement_text: str
    value: str | None = None
    el_id: str

    @field_validator("family")
    @classmethod
    def family_known(cls, v: str) -> str:
        if v not in FAMILIES:
            raise ValueError(f"family must be one of {FAMILIES}")
        return v

    @field_validator("key")
    @classmethod
    def key_shape(cls, v: str) -> str:
        if not re.fullmatch(r"[a-z][a-z0-9_]{1,60}", v):
            raise ValueError("key must be snake_case")
        return v

    @field_validator("requirement_text")
    @classmethod
    def text_present(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("requirement_text must not be blank")
        return v


class AiExtraction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rules: list[AiRule]


_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)


def parse_ai_response(raw: str) -> AiExtraction | None:
    """Strict parse. Returns None on ANY deviation — the schema is the
    contract, and a near-miss is a miss."""
    text = raw.strip()
    fenced = _FENCE_RE.search(text)
    if fenced:
        text = fenced.group(1).strip()
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return None
    try:
        return AiExtraction.model_validate(payload)
    except ValidationError:
        return None
