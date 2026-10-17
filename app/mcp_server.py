"""MCP server exposing the store as tools. Any MCP client (LangGraph, Claude Desktop, ...) can use it.

Run standalone:  python -m app.mcp_server        (stdio transport)
The database file comes from the STORE_DB environment variable (default data/store.db).
"""
from mcp.server.fastmcp import FastMCP

from app.runtime import open_store

store = open_store()
mcp = FastMCP("northwind-store")


@mcp.tool()
def get_order(order_id: str) -> dict:
    """Look up an order by id (e.g. NW-1042): status, delivery date, items, prices and amounts already refunded."""
    return store.get_order(order_id)


@mcp.tool()
def list_orders(customer_email: str) -> list[dict]:
    """List a customer's orders by email address."""
    return store.list_orders(customer_email)


@mcp.tool()
def get_refund_policy() -> str:
    """Return the store's refund policy text."""
    return store.get_refund_policy()


@mcp.tool()
def check_refund_eligibility(order_id: str, item_id: str, reason: str) -> dict:
    """Check whether an item can be refunded and the maximum amount.
    reason: damaged, defective, wrong_item, changed_mind, too_small, too_large or other."""
    return store.check_refund_eligibility(order_id, item_id, reason)


@mcp.tool()
def issue_refund(order_id: str, item_id: str, amount: float, reason: str) -> dict:
    """Refund an item. REQUIRES support-lead approval. Fails if the policy does not allow it or the amount is too high."""
    return store.issue_refund(order_id, item_id, amount, reason)


@mcp.tool()
def update_order_status(order_id: str, status: str) -> dict:
    """Change an order's status. Only 'cancelled' for in-transit orders is supported. REQUIRES support-lead approval."""
    return store.update_order_status(order_id, status)


if __name__ == "__main__":
    mcp.run()
