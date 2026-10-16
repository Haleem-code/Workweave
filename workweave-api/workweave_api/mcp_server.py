"""Private stdio MCP server. The application binds its company, user and run."""
import asyncio
import os
import hashlib
from mcp.server.fastmcp import FastMCP
from .config import settings
from .graph import Graph
from .store import Store, company_store, now
from .providers import Router
from .tools import Tools

server = FastMCP("Workweave scoped tools")
graph = Graph(settings.graph_connection_url)
router = Router(settings)


async def bound():
    token = os.environ.get("WORKWEAVE_MCP_SESSION", "")
    session = await Store(graph, "ww_control").get("session", hashlib.sha256(token.encode()).hexdigest())
    company = os.environ.get("WORKWEAVE_MCP_COMPANY", "")
    member = await Store(graph, "ww_control").get("member", company + ":" + (session or {}).get("user_id", ""))
    if not token or not session or session["expires_at"] < now() or not member:
        raise ValueError("Authorized application session required")
    store = company_store(graph, company)
    run = await store.get("run", os.environ.get("WORKWEAVE_MCP_RUN", ""))
    if not run or run["user_id"] != session["user_id"]:
        raise ValueError("Run is not available to this session")
    return Tools(store, router, run["id"])


@server.tool()
async def search_knowledge(query: str) -> dict:
    return await (await bound()).search_knowledge(query)


@server.tool()
async def trace_impact(entity_id: str) -> dict:
    return await (await bound()).trace_impact(entity_id)


@server.tool()
async def find_owner(entity_id: str) -> dict:
    return await (await bound()).find_owner(entity_id)


@server.tool()
async def get_procedure() -> list:
    return await (await bound()).get_procedure()


@server.tool()
async def recall_episode(query: str) -> list:
    return await (await bound()).recall_episode(query)


@server.tool()
async def create_review_task(finding_id: str) -> dict:
    return await (await bound()).create_review_task(finding_id)


if __name__ == "__main__":
    server.run(transport="stdio")
