import json
import re
from .assignment import rank_candidates
from .store import Store


EXTRACT_PROMPT = """You are a workplace assistant analyzing messages from team chat (Slack).
Determine whether the message asks for work, a fix, an action item, or task assignment.

Reply with a strict JSON object (no markdown, no backticks, no other text):
{
  "is_task": true or false,
  "title": "Clear concise task title under 150 characters",
  "description": "Brief summary of what needs to be done based strictly on the message",
  "terms": "key domain and responsibility keywords for skill matching",
  "due_date_text": "any mentioned deadline e.g. Friday, tomorrow, or empty string"
}
"""

CHOICE_PROMPT = """You are an assignment advisor reviewing candidates ranked by company knowledge.
Choose the BEST candidate among the provided candidates to assign this task to.
You MUST choose one of the provided candidate person_ids. Do NOT invent a person.

Reply with a strict JSON object:
{
  "chosen_person_id": "the exact person_id from the candidates list",
  "reason": "1-2 sentence explanation of why they are the best fit based on their role, responsibilities, and past work"
}
"""


def parse_json_object(text: str) -> dict | None:
    text = text.strip()
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except Exception:
        return None


async def analyze_message(router, policy: dict, message_text: str, author_name: str) -> dict:
    """Analyze a message with AI to extract task status, title, description, and keywords."""
    # Fast heuristic check for non-tasks (simple greetings, emojis, acknowledgements)
    clean = message_text.strip()
    if len(clean) < 5 or clean.lower() in ("ok", "okay", "thanks", "thank you", "sounds good", "noted", "👍", "done"):
        return {
            "is_task": False,
            "title": "",
            "description": clean,
            "terms": "",
            "due_date_text": "",
        }

    messages = [
        {"role": "system", "content": EXTRACT_PROMPT},
        {"role": "user", "content": f"Message from {author_name}:\n{message_text}"}
    ]

    try:
        result = await router.generate(messages, policy)
        data = parse_json_object(result.get("text", ""))
        if data and isinstance(data, dict) and isinstance(data.get("is_task"), bool):
            return {
                "is_task": data["is_task"],
                "title": str(data.get("title", "")).strip()[:150] or clean[:100],
                "description": str(data.get("description", "")).strip()[:3000] or clean,
                "terms": str(data.get("terms", "")).strip(),
                "due_date_text": str(data.get("due_date_text", "")).strip(),
            }
    except Exception:
        pass

    # Heuristic fallback if AI provider is unavailable
    has_action_words = bool(re.search(r"\b(fix|create|assign|check|review|update|send|need|prepare|investigate|deploy|build|bug|issue|task)\b", clean, re.I))
    return {
        "is_task": has_action_words,
        "title": clean.split("\n")[0][:120],
        "description": clean,
        "terms": clean[:100],
        "due_date_text": "",
        "manual_triage": True,
    }


async def triage_slack_message(
    store: Store,
    router,
    policy: dict,
    message_text: str,
    author_name: str,
    channel_id: str,
    thread_ts: str,
) -> dict:
    """End-to-end triage: extracts task details, runs FalkorDB graph ranking, and selects top candidate."""
    analysis = await analyze_message(router, policy, message_text, author_name)
    if not analysis["is_task"]:
        return {
            "is_task": False,
            "reason": "Message did not contain an actionable task or work request.",
        }

    # Run FalkorDB graph traversal ranking
    search_terms = f"{analysis['title']} {analysis['terms']} {analysis['description']}"
    candidates = await rank_candidates(store, search_terms)
    if analysis.get("manual_triage"):
        return {
            "is_task": True, "title": analysis["title"], "description": analysis["description"],
            "due_date_text": "", "chosen_candidate": None, "candidates": candidates[:3],
            "reason": "AI extraction was unavailable. Review the original message and choose an assignee; these candidates come from the company graph.",
        }

    if not candidates:
        return {
            "is_task": True,
            "title": analysis["title"],
            "description": analysis["description"],
            "due_date_text": analysis["due_date_text"],
            "chosen_candidate": None,
            "candidates": [],
            "reason": "No team members are configured in the workspace.",
        }

    top_candidates = candidates[:3]
    top_ids = {c["person_id"]: c for c in top_candidates}

    chosen = top_candidates[0]
    reason = chosen["summary"]
    ai_choice_made = False

    # Ask AI to choose among top 3
    if len(top_candidates) > 1 and router:
        prompt_content = {
            "task_title": analysis["title"],
            "task_description": analysis["description"],
            "candidates": [
                {
                    "person_id": c["person_id"],
                    "name": c["name"],
                    "role": c["role"],
                    "score": c["score"],
                    "evidence_summary": c["summary"],
                }
                for c in top_candidates
            ]
        }
        messages = [
            {"role": "system", "content": CHOICE_PROMPT},
            {"role": "user", "content": json.dumps(prompt_content, default=str)}
        ]
        try:
            res = await router.generate(messages, policy)
            choice_data = parse_json_object(res.get("text", ""))
            if choice_data and isinstance(choice_data, dict):
                pid = choice_data.get("chosen_person_id")
                if pid in top_ids:
                    chosen = top_ids[pid]
                    reason = str(choice_data.get("reason", "")).strip() or chosen["summary"]
                    ai_choice_made = True
        except Exception:
            pass

    return {
        "is_task": True,
        "title": analysis["title"],
        "description": analysis["description"],
        "due_date_text": analysis["due_date_text"],
        "chosen_candidate": chosen,
        "candidates": top_candidates,
        "reason": reason,
        "ai_choice_made": ai_choice_made,
    }
