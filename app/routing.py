"""Routing rule for the agent graph, kept free of framework imports so it can be unit-tested.

After the model responds:
  * no tool calls            -> END (the agent replied to the customer)
  * only read tools          -> "tools" (run them immediately)
  * any write tool requested -> "approval" (pause for a human before anything changes)
"""
from app.actions import WRITE_TOOLS

END = "__end__"   # identical to langgraph.graph.END


def route_after_agent(state: dict) -> str:
    last = state["messages"][-1]
    calls = getattr(last, "tool_calls", None) or []
    if not calls:
        return END
    if any(call["name"] in WRITE_TOOLS for call in calls):
        return "approval"
    return "tools"
