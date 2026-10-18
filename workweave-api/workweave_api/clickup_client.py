import httpx
import time


async def get_list(http: httpx.AsyncClient, token: str, list_id: str) -> dict:
    url = f"https://api.clickup.com/api/v2/list/{list_id}"
    headers = {"Authorization": token}
    response = await http.get(url, headers=headers, timeout=15)
    if response.status_code != 200:
        raise ValueError(f"ClickUp list {list_id} could not be accessed. Status {response.status_code}")
    return response.json()


async def list_members(http: httpx.AsyncClient, token: str, list_id: str) -> list[dict]:
    url = f"https://api.clickup.com/api/v2/list/{list_id}/member"
    headers = {"Authorization": token}
    response = await http.get(url, headers=headers, timeout=15)
    if response.status_code != 200:
        # Fallback to team members if list/member is not available on certain tiers
        try:
            teams_res = await http.get("https://api.clickup.com/api/v2/team", headers=headers, timeout=15)
            if teams_res.status_code == 200:
                teams = teams_res.json().get("teams", [])
                members = []
                for t in teams:
                    for m in t.get("members", []):
                        user = m.get("user", {})
                        members.append({
                            "id": str(user.get("id")),
                            "username": user.get("username", "Unnamed"),
                            "email": user.get("email", ""),
                        })
                return members
        except Exception:
            pass
        raise ValueError(f"ClickUp members could not be loaded for list {list_id}. Status {response.status_code}")
    data = response.json()
    members = []
    for m in data.get("members", []):
        members.append({
            "id": str(m.get("id")),
            "username": m.get("username", "Unnamed"),
            "email": m.get("email", ""),
        })
    return members


async def find_by_marker(http: httpx.AsyncClient, token: str, list_id: str, marker: str, since_ms: int | None = None) -> dict | None:
    url = f"https://api.clickup.com/api/v2/list/{list_id}/task"
    headers = {"Authorization": token}
    params = {
        "include_closed": "true",
        "subtasks": "true",
        "page": 0,
    }
    if since_ms:
        params["date_created_gt"] = str(since_ms)
    
    target_needle = f"⟦workweave:{marker}⟧"
    # An incomplete or failed search is not proof that a task does not exist.
    deadline = time.monotonic() + 55
    for page in range(100):
        if time.monotonic() >= deadline:
            raise RuntimeError("ClickUp reconciliation incomplete; task creation paused")
        params["page"] = page
        response = await http.get(url, headers=headers, params=params, timeout=10)
        response.raise_for_status()
        tasks = response.json().get("tasks")
        if not isinstance(tasks, list):
            raise RuntimeError("Invalid ClickUp search response; task creation paused")
        for task in tasks:
            desc = task.get("description") or task.get("text_content") or ""
            name = task.get("name") or ""
            if target_needle in desc or target_needle in name:
                return task
        if len(tasks) < 100:
            return None
    raise RuntimeError("ClickUp reconciliation exceeded page limit; task creation paused")


async def create_task(
    http: httpx.AsyncClient,
    token: str,
    list_id: str,
    name: str,
    description: str,
    assignees: list[str | int] | None = None,
    due_date_ms: int | None = None,
) -> dict:
    url = f"https://api.clickup.com/api/v2/list/{list_id}/task"
    headers = {"Authorization": token, "Content-Type": "application/json"}
    payload = {
        "name": name[:300],
        "description": description[:20000],
    }
    if assignees:
        valid_assignees = []
        for a in assignees:
            s = str(a).strip()
            if s.isdigit():
                valid_assignees.append(int(s))
            elif s:
                valid_assignees.append(s)
        if valid_assignees:
            payload["assignees"] = valid_assignees
    if due_date_ms:
        payload["due_date"] = int(due_date_ms)

    response = await http.post(url, headers=headers, json=payload, timeout=25)
    if response.status_code not in (200, 201):
        try:
            err_msg = response.json().get("err") or response.text
        except Exception:
            err_msg = response.text
        raise ValueError(f"ClickUp task creation failed (HTTP {response.status_code}): {err_msg}")
    return response.json()


async def get_task(http: httpx.AsyncClient, token: str, task_id: str) -> dict:
    url = f"https://api.clickup.com/api/v2/task/{task_id}"
    headers = {"Authorization": token}
    response = await http.get(url, headers=headers, timeout=15)
    if response.status_code != 200:
        raise ValueError(f"ClickUp task {task_id} not found or inaccessible (HTTP {response.status_code})")
    return response.json()


async def list_tasks_updated(http: httpx.AsyncClient, token: str, list_id: str, date_updated_gt: int | None = None) -> list[dict]:
    url = f"https://api.clickup.com/api/v2/list/{list_id}/task"
    headers = {"Authorization": token}
    params = {"include_closed": "true", "subtasks": "true", "page": 0}
    if date_updated_gt:
        params["date_updated_gt"] = str(date_updated_gt)
    response = await http.get(url, headers=headers, params=params, timeout=20)
    if response.status_code != 200:
        return []
    return response.json().get("tasks", [])
