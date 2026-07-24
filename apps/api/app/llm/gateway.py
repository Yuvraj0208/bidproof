"""The only path from application code to a model.

Callers name a ROLE — small, mid, or strong. The LiteLLM gateway maps each
role to an actual model from env (infra/litellm/config.yaml), so no vendor or
model name exists anywhere in application code and a model swap is a config
change (SPEC §12.4, repo golden rule 7).
"""

import httpx

from app.core.config import get_settings

ROLES = frozenset({"small", "mid", "strong"})


class UnknownRoleError(ValueError):
    """The caller asked for something that is not a configured role."""


class EmptyCompletionError(RuntimeError):
    """The gateway answered, but with no usable text.

    Seen when a role is pointed at a *reasoning* model: it spends the token
    budget in `reasoning_content` and returns an empty `content`. Callers must
    not silently fall back to a template on this — that is how a shallow output
    reaches a customer without anyone noticing (see docs/FINISH_STATUS.md D2).
    """


def extract_text(response: dict, allow_reasoning: bool = False) -> str:
    """The text of a completion, or raise EmptyCompletionError.

    `allow_reasoning` is OFF by default and should stay off for anything a
    human will read: a reasoning model's `reasoning_content` is its private
    planning ("Okay, let me start by..."), and shipping that as prose is worse
    than falling back to a grounded template. Health probes may switch it on,
    since there any text proves the role answers.
    """
    choices = response.get("choices")
    if not choices:
        raise EmptyCompletionError(
            f"gateway returned no choices: {str(response)[:200]}"
        )
    message = choices[0].get("message") or {}
    fields = ("content", "reasoning_content") if allow_reasoning else ("content",)
    for field in fields:
        text = (message.get(field) or "").strip()
        if text:
            return text
    finish = choices[0].get("finish_reason")
    raise EmptyCompletionError(
        f"gateway returned an empty completion (finish_reason={finish!r}). "
        "If this role points at a reasoning model, raise max_tokens or point "
        "the role at an instruction model."
    )


class LLMGateway:
    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        settings = get_settings()
        self._base_url = (base_url or settings.litellm_base_url).rstrip("/")
        self._api_key = api_key or settings.litellm_master_key
        self._client = client or httpx.AsyncClient(timeout=120)

    async def complete(self, role: str, messages: list[dict], **params) -> dict:
        if role not in ROLES:
            raise UnknownRoleError(
                f"unknown model role {role!r}; expected one of {sorted(ROLES)}"
            )
        response = await self._client.post(
            f"{self._base_url}/v1/chat/completions",
            headers={"Authorization": f"Bearer {self._api_key}"},
            json={"model": role, "messages": messages, **params},
        )
        response.raise_for_status()
        return response.json()

    async def aclose(self) -> None:
        await self._client.aclose()
