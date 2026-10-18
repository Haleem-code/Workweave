import hashlib
import hmac
import time
import httpx
import math


class SlackDeliveryRejected(ValueError):
    """Slack explicitly rejected the write, so retrying cannot duplicate it."""


def verify_signature(raw_body: bytes, timestamp: str, signature: str, signing_secret: str) -> bool:
    if not timestamp or not signature or not signing_secret:
        return False
    try:
        ts = float(timestamp)
    except ValueError:
        return False
    if not math.isfinite(ts) or abs(time.time() - ts) > 300:
        return False

    basestring = f"v0:{timestamp}:".encode("utf-8") + raw_body
    computed = "v0=" + hmac.new(
        signing_secret.encode("utf-8"),
        basestring,
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(computed, signature)


async def auth_test(http: httpx.AsyncClient, token: str) -> dict:
    url = "https://slack.com/api/auth.test"
    headers = {"Authorization": f"Bearer {token}"}
    response = await http.post(url, headers=headers, timeout=15)
    data = response.json()
    if not data.get("ok"):
        error = data.get("error", "authentication failed")
        raise ValueError(f"Slack auth.test failed: {error}")
    return data


async def user_info(http: httpx.AsyncClient, token: str, user_id: str) -> dict:
    url = "https://slack.com/api/users.info"
    headers = {"Authorization": f"Bearer {token}"}
    response = await http.get(url, headers=headers, params={"user": user_id}, timeout=15)
    data = response.json()
    if not data.get("ok"):
        return {"id": user_id, "name": "Unknown", "email": ""}
    u = data.get("user", {})
    profile = u.get("profile", {})
    return {
        "id": user_id,
        "name": profile.get("display_name") or profile.get("real_name") or u.get("name") or "Unknown",
        "real_name": profile.get("real_name") or u.get("real_name") or "",
        "email": profile.get("email") or "",
    }


async def conversations_list(http: httpx.AsyncClient, token: str, types: str = "public_channel,private_channel") -> list[dict]:
    url = "https://slack.com/api/conversations.list"
    headers = {"Authorization": f"Bearer {token}"}
    params = {"types": types, "exclude_archived": "true", "limit": "200"}
    response = await http.get(url, headers=headers, params=params, timeout=20)
    data = response.json()
    if not data.get("ok"):
        error = data.get("error", "could not list channels")
        raise ValueError(f"Slack conversations.list failed: {error}")
    channels = []
    for c in data.get("channels", []):
        channels.append({
            "id": c.get("id"),
            "name": c.get("name"),
            "is_private": bool(c.get("is_private")),
            "is_member": bool(c.get("is_member")),
        })
    return channels


async def conversations_replies(http: httpx.AsyncClient, token: str, channel: str, thread_ts: str) -> list[dict]:
    url = "https://slack.com/api/conversations.replies"
    headers = {"Authorization": f"Bearer {token}"}
    params = {"channel": channel, "ts": thread_ts, "include_all_metadata": "true", "limit": "100"}
    response = await http.get(url, headers=headers, params=params, timeout=20)
    response.raise_for_status()
    data = response.json()
    if not data.get("ok"):
        raise ValueError("Slack thread reconciliation unavailable")
    return data.get("messages", [])


async def post_thread_reply(
    http: httpx.AsyncClient,
    token: str,
    channel: str,
    thread_ts: str,
    text: str,
    metadata: dict | None = None,
) -> dict:
    url = "https://slack.com/api/chat.postMessage"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json; charset=utf-8"}
    payload = {
        "channel": channel,
        "thread_ts": thread_ts,
        "text": text,
    }
    if metadata:
        payload["metadata"] = metadata
    response = await http.post(url, headers=headers, json=payload, timeout=20)
    data = response.json()
    if not data.get("ok"):
        error = data.get("error", "postMessage failed")
        raise SlackDeliveryRejected(f"Slack chat.postMessage failed: {error}")
    response.raise_for_status()
    return data
