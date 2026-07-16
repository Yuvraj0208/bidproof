"""The gateway client is the only path to a model. It accepts a role name —
never a model or vendor — and everything else comes from env (golden rule 7)."""

import httpx
import pytest


def make_gateway(captured: list[httpx.Request]):
    from app.llm.gateway import LLMGateway

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(
            200,
            json={"choices": [{"message": {"role": "assistant", "content": "hi"}}]},
        )

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return LLMGateway(
        base_url="http://litellm.test:4000", api_key="test-master-key", client=client
    )


async def test_gateway_rejects_unknown_role():
    from app.llm.gateway import UnknownRoleError

    gateway = make_gateway([])
    for bad_role in ("huge", "small ", "", "default"):
        with pytest.raises(UnknownRoleError):
            await gateway.complete(bad_role, messages=[{"role": "user", "content": "x"}])


async def test_gateway_sends_role_as_model_and_reads_env():
    captured: list[httpx.Request] = []
    gateway = make_gateway(captured)

    result = await gateway.complete(
        "small", messages=[{"role": "user", "content": "ping"}]
    )

    assert result["choices"][0]["message"]["content"] == "hi"
    assert len(captured) == 1
    request = captured[0]
    assert str(request.url).startswith("http://litellm.test:4000")
    assert str(request.url).endswith("/chat/completions")
    assert request.headers["authorization"] == "Bearer test-master-key"

    import json

    payload = json.loads(request.content)
    # The "model" the app asks for is the ROLE. LiteLLM maps it to a real
    # model from env — app code never knows which.
    assert payload["model"] == "small"
    assert payload["messages"] == [{"role": "user", "content": "ping"}]
