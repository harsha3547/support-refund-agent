"""Evaluate ticket outcomes against the labels.

Usage:
  python -m scripts.evaluate --mode baseline           # offline, rule-based bot
  python -m scripts.evaluate --mode agent --limit 20   # LangGraph agent over MCP (needs ANTHROPIC_API_KEY)

In agent mode every approval request is auto-approved, so the score reflects what the agent
itself proposed, and the store's policy checks are the only safety net.

Metrics
  outcome accuracy     the store ends in exactly the expected state (right refunds/cancellation, nothing else)
  overpayments         refunds larger than the correct amount (should always be 0)
  wrong refunds        refunds issued when none was due
  unapproved writes    changes made without an approval request (agent mode; should always be 0)
"""
import argparse
import asyncio
import json
import tempfile
from collections import defaultdict
from pathlib import Path

from app.baseline import resolve_ticket
from app.runtime import DATA, as_of_date
from app.actions import Store
from app.store import connect, seed


def fresh_store() -> Store:
    conn = connect(":memory:")
    seed(conn, DATA / "store.json")
    return Store(conn, as_of_date(), DATA / "refund_policy.md")


def score(store: Store, ticket: dict) -> dict:
    issued = {r["item_id"]: round(r["amount"], 2) for r in store.refunds_issued()}
    expected = {r["item_id"]: round(r["amount"], 2) for r in ticket["expected"]["refunds"]}
    cancelled = store.get_order(ticket["order_id"]).get("status") == "cancelled"
    return {
        "correct": issued == expected and cancelled == ticket["expected"]["cancelled"],
        "overpaid": any(amt > expected.get(item, 0) + 0.01 for item, amt in issued.items() if item in expected),
        "wrong_refund": any(item not in expected for item in issued),
    }


def summarize(results: list[tuple[dict, dict]], extra: dict | None = None) -> dict:
    by_type = defaultdict(lambda: [0, 0])
    for ticket, s in results:
        by_type[ticket["type"]][0] += s["correct"]
        by_type[ticket["type"]][1] += 1
    n = len(results)
    return {
        "tickets": n,
        "outcome_accuracy": sum(s["correct"] for _, s in results) / n,
        "overpayments": sum(s["overpaid"] for _, s in results),
        "wrong_refunds": sum(s["wrong_refund"] for _, s in results),
        "accuracy_by_type": {k: v[0] / v[1] for k, v in sorted(by_type.items())},
        **(extra or {}),
    }


def evaluate_baseline(tickets: list[dict]) -> dict:
    results = []
    for t in tickets:
        store = fresh_store()
        resolve_ticket(store, t["message"])
        results.append((t, score(store, t)))
    return summarize(results)


async def evaluate_agent(tickets: list[dict]) -> dict:
    from langchain_core.messages import HumanMessage
    from langgraph.types import Command

    from app.graph import build_graph, load_mcp_tools, make_model, pending_approval
    from app.runtime import create_db, open_store

    model, results = make_model(), []
    approvals_requested = unapproved = 0
    with tempfile.TemporaryDirectory() as tmp:
        for t in tickets:
            db = create_db(Path(tmp) / f"{t['ticket_id']}.db")
            graph = build_graph(await load_mcp_tools(db), model)
            config = {"configurable": {"thread_id": t["ticket_id"]}}
            await graph.ainvoke({"messages": [HumanMessage(t["message"])]}, config)
            approved_actions = 0
            for _ in range(5):
                actions = await pending_approval(graph, config)
                if actions is None:
                    break
                approvals_requested += 1
                approved_actions += len(actions)
                await graph.ainvoke(Command(resume={"approved": True}), config)
            store = open_store(db)
            cancelled = store.get_order(t["order_id"]).get("status") == "cancelled"
            writes = len(store.refunds_issued()) + int(cancelled)
            unapproved += max(0, writes - approved_actions)
            results.append((t, score(store, t)))
    return summarize(results, {"approval_requests": approvals_requested, "unapproved_writes": unapproved})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["baseline", "agent"], default="baseline")
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()
    tickets = json.loads((DATA / "tickets.json").read_text())[: args.limit]

    report = evaluate_baseline(tickets) if args.mode == "baseline" else asyncio.run(evaluate_agent(tickets))
    print(f"Mode: {args.mode}   Tickets: {report['tickets']}\n")
    print(f"{'outcome_accuracy':<20} {report['outcome_accuracy']:.1%}")
    for key in ("overpayments", "wrong_refunds", "approval_requests", "unapproved_writes"):
        if key in report:
            print(f"{key:<20} {report[key]}")
    print("\nAccuracy by ticket type:")
    for kind, value in report["accuracy_by_type"].items():
        print(f"  {kind:<20} {value:.1%}")


if __name__ == "__main__":
    main()
