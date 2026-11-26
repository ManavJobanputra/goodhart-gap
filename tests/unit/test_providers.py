"""Provider tests using httpx.MockTransport — no network.

Critical: a 3-turn tool-call conversation must re-send every prior
reasoning_content verbatim (DeepSeek thinking-mode requirement).
"""

from __future__ import annotations

import json

import httpx
import pytest
from openai import OpenAI

from goodhart_gap.providers.base import ChatMessage, ToolSpec
from goodhart_gap.providers.cost import compute_cost, get_model
from goodhart_gap.providers.openai_compat import OpenAICompatProvider
from goodhart_gap.providers.ratelimit import BudgetExceeded, BudgetTracker


def _make_provider(handler) -> OpenAICompatProvider:
    transport = httpx.MockTransport(handler)
    cfg = get_model("deepseek-flash")
    client = OpenAI(
        api_key="test-key",
        base_url="https://api.deepseek.com",
        http_client=httpx.Client(transport=transport),
    )
    return OpenAICompatProvider(cfg, client=client)


def _completion(content: str = "ok", reasoning: str | None = None, tool_calls=None) -> dict:
    msg = {"role": "assistant", "content": content}
    if reasoning is not None:
        msg["reasoning_content"] = reasoning
    if tool_calls:
        msg["tool_calls"] = tool_calls
    return {
        "id": "x",
        "object": "chat.completion",
        "created": 0,
        "model": "deepseek-flash",
        "choices": [{"index": 0, "message": msg, "finish_reason": "stop"}],
        "usage": {
            "prompt_tokens": 100,
            "completion_tokens": 20,
            "total_tokens": 120,
            "prompt_tokens_details": {"cached_tokens": 40},
        },
    }


def test_request_body_contains_thinking_and_effort() -> None:
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json=_completion())

    prov = _make_provider(handler)
    prov.chat([ChatMessage(role="user", content="hi")], thinking=True, reasoning_effort="max")
    body = seen["body"]
    # The SDK flattens extra_body into the top-level request body.
    assert body["thinking"]["type"] == "enabled"
    assert body["reasoning_effort"] == "max"


def test_thinking_disabled() -> None:
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json=_completion())

    prov = _make_provider(handler)
    prov.chat([ChatMessage(role="user", content="hi")], thinking=False)
    assert seen["body"]["thinking"]["type"] == "disabled"


def test_reasoning_content_preserved_in_response() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_completion(reasoning="my chain of thought"))

    prov = _make_provider(handler)
    resp = prov.chat([ChatMessage(role="user", content="hi")])
    assert resp.message.reasoning_content == "my chain of thought"


def test_three_turn_tool_conversation_resends_reasoning_verbatim() -> None:
    """The key DeepSeek requirement: every prior assistant reasoning_content is
    echoed back verbatim on subsequent requests that include tools."""
    requests: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(json.loads(request.content))
        turn = len(requests)
        if turn == 1:
            return httpx.Response(
                200,
                json=_completion(
                    content="",
                    reasoning="R1: think about tool A",
                    tool_calls=[
                        {
                            "id": "call_a",
                            "type": "function",
                            "function": {"name": "list_dir", "arguments": "{}"},
                        }
                    ],
                ),
            )
        if turn == 2:
            return httpx.Response(
                200,
                json=_completion(
                    content="",
                    reasoning="R2: think about tool B",
                    tool_calls=[
                        {
                            "id": "call_b",
                            "type": "function",
                            "function": {"name": "read_file", "arguments": '{"path": "x"}'},
                        }
                    ],
                ),
            )
        return httpx.Response(200, json=_completion(content="done", reasoning="R3: final"))

    prov = _make_provider(handler)
    tools = [
        ToolSpec(name="list_dir", description="", parameters={}),
        ToolSpec(name="read_file", description="", parameters={}),
    ]

    history = [ChatMessage(role="user", content="fix it")]
    r1 = prov.chat(history, tools=tools)
    history.append(r1.message)
    history.append(ChatMessage(role="tool", content="[a.py]", tool_call_id="call_a"))
    r2 = prov.chat(history, tools=tools)
    history.append(r2.message)
    history.append(ChatMessage(role="tool", content="contents", tool_call_id="call_b"))
    r3 = prov.chat(history, tools=tools)

    # Third request must include both prior assistant reasoning_content verbatim.
    third = requests[2]
    assistant_msgs = [m for m in third["messages"] if m["role"] == "assistant"]
    reasonings = [m.get("reasoning_content") for m in assistant_msgs]
    assert "R1: think about tool A" in reasonings
    assert "R2: think about tool B" in reasonings
    assert r3.message.reasoning_content == "R3: final"


def test_retry_on_500() -> None:
    state = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        state["n"] += 1
        if state["n"] < 3:
            return httpx.Response(500, json={"error": "boom"})
        return httpx.Response(200, json=_completion())

    cfg = get_model("deepseek-flash")
    transport = httpx.MockTransport(handler)
    client = OpenAI(
        api_key="k",
        base_url="https://api.deepseek.com",
        http_client=httpx.Client(transport=transport),
        max_retries=0,
    )
    prov = OpenAICompatProvider(cfg, client=client, base_backoff_s=0.0)
    resp = prov.chat([ChatMessage(role="user", content="hi")])
    assert resp.message.content == "ok"
    assert state["n"] == 3


def test_cache_hit_tokens_parsed() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_completion())

    prov = _make_provider(handler)
    resp = prov.chat([ChatMessage(role="user", content="hi")])
    assert resp.usage.cache_hit_tokens == 40


def test_compute_cost() -> None:
    cfg = get_model("deepseek-flash")
    # 1M prompt tokens, all cache-miss, 1M output → 0.30 + 1.20 = 1.50
    cost = compute_cost(cfg, prompt_tokens=1_000_000, completion_tokens=1_000_000)
    assert abs(cost - (cfg.price_input_cache_miss + cfg.price_output)) < 1e-9
    # With 1M cache-hit input only:
    cost2 = compute_cost(
        cfg, prompt_tokens=1_000_000, completion_tokens=0, cache_hit_tokens=1_000_000
    )
    assert abs(cost2 - cfg.price_input_cache_hit) < 1e-9


def test_budget_stop_triggers(tmp_path) -> None:
    bt = BudgetTracker(cap_usd=0.01, log_path=tmp_path / "spend.jsonl")
    bt.record({"m": 1}, cost_usd=0.004)
    assert bt.remaining() > 0
    with pytest.raises(BudgetExceeded):
        bt.record({"m": 2}, cost_usd=0.02)
    assert bt.spent_usd >= 0.01
