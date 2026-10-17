"""Chat with the support agent in the terminal. You play both the customer and the support lead.

Usage: python -m app.chat            (needs ANTHROPIC_API_KEY)
Each run starts from a fresh copy of the store database.
"""
import asyncio
import json
import uuid
from pathlib import Path

from langchain_core.messages import HumanMessage
from langgraph.types import Command

from app.graph import build_graph, load_mcp_tools, make_model, pending_approval
from app.runtime import DATA, create_db


def text_of(message) -> str:
    """Message content can be a string or a list of content blocks; return the text either way."""
    content = message.content
    if isinstance(content, str):
        return content
    return "".join(block.get("text", "") for block in content if isinstance(block, dict))


async def main():
    db = create_db(DATA / "chat_session.db")
    graph = build_graph(await load_mcp_tools(db), make_model())
    config = {"configurable": {"thread_id": str(uuid.uuid4())}}   # the conversation's short-term memory
    print("Northwind support agent. Type a customer message (Ctrl+C to quit).\n")

    while True:
        text = input("Customer: ").strip()
        if not text:
            continue
        result = await graph.ainvoke({"messages": [HumanMessage(text)]}, config)
        while (actions := await pending_approval(graph, config)) is not None:
            print("\n--- Approval needed ---")
            for a in actions:
                print(f"  {a['tool']}({json.dumps(a['args'])})")
            answer = input("Support lead, approve? [y/N]: ").strip().lower()
            decision = {"approved": answer == "y"}
            if not decision["approved"]:
                decision["note"] = input("Reason for rejecting: ").strip()
            result = await graph.ainvoke(Command(resume=decision), config)
        print(f"\nAgent: {text_of(result['messages'][-1])}\n")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, EOFError):
        Path(DATA / "chat_session.db").unlink(missing_ok=True)
        print()
