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
