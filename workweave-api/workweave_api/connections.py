"""Read selected synthetic workplace content; never write to external services."""
import re
import httpx
from fastapi import Depends, HTTPException
from pydantic import BaseModel, Field, SecretStr
from . import ingestion
from .store import now


class ConnectionInput(BaseModel):
    token: SecretStr = SecretStr("")
    selection: str = Field(min_length=1, max_length=80)
    synthetic_only: bool = False


async def read_selection(http, provider, token, selection):
    if provider == "slack":
        if not re.fullmatch(r"C[A-Z0-9]{5,40}", selection):
            raise ValueError("Enter a public Slack channel ID, beginning with C")
        url = "https://slack.com/api/conversations.history"
        headers, params = {"Authorization": "Bearer " + token}, {"channel": selection, "limit": 15}
    elif provider == "clickup":
        if not re.fullmatch(r"[0-9]{1,30}", selection):
            raise ValueError("Enter the numeric ClickUp list ID")
        url = f"https://api.clickup.com/api/v2/list/{selection}/task"
        headers, params = {"Authorization": token}, {"page": 0, "include_closed": "true", "subtasks": "false"}
    else:
        raise HTTPException(404, "Unknown workplace tool")
    try:
        response = await http.get(url, headers=headers, params=params, timeout=20)
    except httpx.HTTPError:
        raise HTTPException(502, "The workplace tool could not be reached. Retry shortly.") from None
    if response.status_code == 429:
        raise HTTPException(429, "The tool's read limit was reached. Wait before trying again.")
    if response.status_code != 200:
        raise HTTPException(409, "Access was not accepted. Check your token and selected channel or list.")
    try:
        data = response.json()
    except ValueError:
        raise HTTPException(502, "The workplace tool returned an unreadable response") from None
    if provider == "slack":
        if not data.get("ok"):
            raise HTTPException(409, "Slack could not read this channel. Check channels:history permission and invite your bot to the channel.")
        items = [m for m in data.get("messages", [])[:15] if m.get("text")]
        blocks = [f"Message {m.get('ts', 'unknown')} | Author {m.get('user', 'unknown')}\n{str(m['text'])[:12000]}" for m in items]
        truncated = bool(data.get("has_more") or data.get("response_metadata", {}).get("next_cursor"))
    else:
        tasks = data.get("tasks")
        if not isinstance(tasks, list):
            raise HTTPException(502, "ClickUp did not return a task list")
        items = tasks[:15]
        blocks = []
        for task in items:
            owners = ", ".join(str(a.get("username", "Unnamed")) for a in task.get("assignees", [])) or "Not assigned"
            blocks.append(f"Task {task.get('id', 'unknown')}: {task.get('name', 'Untitled')}\nStatus: {task.get('status', {}).get('status', 'Unknown')}\nAssignees: {owners}\nDue date (Unix milliseconds): {task.get('due_date') or 'Not set'}\n{str(task.get('description') or '')[:12000]}")
        truncated = len(tasks) > 15 or not data.get("last_page", True)
    if not blocks:
        raise HTTPException(409, "No readable messages or tasks were found in that selection")
    content = f"{provider.title()} selection {selection}\nRead-only snapshot. At most 15 items; not a complete workspace history.\n\n" + "\n\n---\n\n".join(blocks)
    return content.encode(), len(items), truncated


def register_connections(app, router, workspace, administrator, engine):
    def provider_name(provider):
        if provider not in ("slack", "clickup"):
            raise HTTPException(404, "Unknown workplace tool")

    @app.get("/api/v1/companies/{company_id}/connections")
    async def status(company_id: str, access=Depends(workspace)):
        administrator(access)
        return [await access[0].get("connection", p) or {"id": p, "connected": False} for p in ("slack", "clickup")]

    @app.post("/api/v1/companies/{company_id}/connections/{provider}/demo")
    async def demonstration(company_id: str, provider: str, access=Depends(workspace)):
        administrator(access); provider_name(provider)
        fixtures = {
            "slack": "SYNTHETIC SLACK DEMO — not connected to Slack\n\n#delivery-ops | Ada Bello | October 17\nThe Northstar carton shipment now arrives October 23. Customer Success must check commitments before promising delivery.\n\n#delivery-ops | Yusuf Adeyemi | October 17\nAcme needs 10 cartons by October 19. Beacon needs 8 by October 20. Only 2 unallocated cartons remain. Do not tell either customer an alternative is confirmed.\n\n#delivery-ops | Ada Bello | October 17\nPacking tape has 30 unallocated units and the related order needs 10. The later carton order is due October 28.\n",
            "clickup": "SYNTHETIC CLICKUP DEMO — not connected to ClickUp\n\nTask DEMO-001: Review Acme carton commitment\nAssignee: Customer Success\nStatus: open\nRequired date: October 19\nCheck the delayed Northstar purchase order and 2 unallocated cartons before deciding what to tell Acme. No alternative supplier has accepted an order.\n\nTask DEMO-002: Review Beacon carton commitment\nAssignee: Customer Success\nStatus: open\nRequired date: October 20\nCheck whether 8 cartons can be supplied despite the revised October 23 shipment. Record the outcome after human review.\n"}
        async with engine.write_lock:
            result = await ingestion.preview(access[0], f"demo-{provider}.txt", fixtures[provider].encode(), source_key=f"demo-workplace:{provider}")
        # A fixture never creates a credential or a successful connection state.
        return {"preview": result, "mode": "synthetic_demo", "connected": False}

    @app.post("/api/v1/companies/{company_id}/connections/{provider}/preview")
    async def preview(company_id: str, provider: str, body: ConnectionInput, access=Depends(workspace)):
        administrator(access); provider_name(provider)
        vault_key = f"workplace:{company_id}:{provider}"
        integration_vault_key = f"company:{company_id}:{provider}:bot_token" if provider == "slack" else f"company:{company_id}:{provider}:token"
        supplied = body.token.get_secret_value().strip()
        v_data = router.vault.read()
        token = supplied or v_data.get(vault_key, "") or v_data.get(integration_vault_key, "")
        if not token or len(token) > 1000 or any(c.isspace() for c in token):
            raise ValueError("Enter a valid access token privately in this form or configure it in Connections")
        content, count, truncated = await read_selection(router.http, provider, token, body.selection)
        async with engine.write_lock:
            result = await ingestion.preview(access[0], f"{provider}-{body.selection}.txt", content, source_key=f"workplace:{provider}:{body.selection}")
            async with router.lock:
                router.vault.set(vault_key, token)
            await access[0].put("connection", {"id": provider, "connected": True, "selection": body.selection,
                "last_read_at": now(), "item_count": count, "truncated": truncated, "preview_id": result["id"]})
        return {"preview": result, "item_count": count, "truncated": truncated}

    @app.delete("/api/v1/companies/{company_id}/connections/{provider}")
    async def disconnect(company_id: str, provider: str, access=Depends(workspace)):
        administrator(access); provider_name(provider)
        async with engine.write_lock:
            async with router.lock:
                router.vault.set(f"workplace:{company_id}:{provider}", None)
            await access[0].put("connection", {"id": provider, "connected": False})
        return {"disconnected": True, "imported_sources_retained": True}
