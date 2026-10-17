"""LangGraph tests with a scripted fake model and fake tools (no API key, no MCP server)."""
import asyncio

import pytest

pytest.importorskip("langgraph")
pytest.importorskip("langchain_core")

from langchain_core.language_models.fake_chat_models import GenericFakeChatModel  # noqa: E402
from langchain_core.messages import AIMessage, HumanMessage  # noqa: E402
from langchain_core.tools import tool  # noqa: E402
from langgraph.types import Command  # noqa: E402

from app.graph import build_graph, pending_approval  # noqa: E402

calls = []


@tool
def get_order(order_id: str) -> dict:
    """Look up an order."""
    calls.append("get_order")
    return {"order_id": order_id, "status": "delivered"}


@tool
def issue_refund(order_id: str, item_id: str, amount: float, reason: str) -> dict:
    """Refund an item."""
    calls.append("issue_refund")
    return {"ok": True, "refunded": amount}


class ToolFakeModel(GenericFakeChatModel):
    def bind_tools(self, tools, **kwargs):
        return self


def scripted():
    return ToolFakeModel(messages=iter([
        AIMessage(content="", tool_calls=[{"name": "get_order", "args": {"order_id": "NW-1"}, "id": "c1"}]),
        AIMessage(content="", tool_calls=[{"name": "issue_refund", "id": "c2",
                                           "args": {"order_id": "NW-1", "item_id": "IT-1", "amount": 90.0, "reason": "changed_mind"}}]),
        AIMessage(content="Your refund of $90.00 has been issued."),
    ]))


def test_refund_pauses_for_approval_then_runs():
    calls.clear()
    graph = build_graph([get_order, issue_refund], scripted())
    config = {"configurable": {"thread_id": "t1"}}

    async def run():
        await graph.ainvoke({"messages": [HumanMessage("Refund my jacket from NW-1")]}, config)
        pending = await pending_approval(graph, config)
        assert pending and pending[0]["tool"] == "issue_refund"
        assert calls == ["get_order"]                   # the refund has NOT run yet
        result = await graph.ainvoke(Command(resume={"approved": True}), config)
        assert calls == ["get_order", "issue_refund"]
        assert "refund" in result["messages"][-1].content.lower()

    asyncio.run(run())
