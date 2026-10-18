import json
import re
from .store import Store
from .understanding import current_chunks


async def sync_assignment_graph(store: Store):
    """Project confirmed roster records into traversable, tenant-local relationships.

    This also migrates existing rosters; all identifiers below are persisted nodes.
    """
    people = await store.list("person", 5000)
    if people:
        await store.graph.query(store.name, """
            UNWIND $people AS item
            MATCH (p:Person {id:item[0]})
            SET p.confirmed=item[5], p.clickup_id=item[7], p.active=item[6]
            MERGE (role:Role {id:item[1]}) SET role.name=item[3]
            MERGE (responsibility:Responsibility {id:item[2]})
            SET responsibility.text=item[4]
            MERGE (p)-[:HAS_ROLE]->(role)
            MERGE (role)-[:RESPONSIBLE_FOR]->(responsibility)
        """, {"people": [[p["id"], "role_" + p["id"], "responsibility_" + p["id"],
            p.get("role", ""), p.get("responsibility", ""), p.get("confirmed", False),
            p.get("active", True), str(p.get("clickup_id") or p.get("clickup_user_id") or "")]
            for p in people]})
    # Replace assignment edges to avoid attributing an outcome to a former owner.
    tasks = await store.list("external_task", 5000)
    if tasks:
        await store.graph.query(store.name, """
            UNWIND $tasks AS item
            MATCH (task:ExternalTask {id:item})
            OPTIONAL MATCH (task)-[old:ASSIGNED_TO]->() DELETE old
        """, {"tasks": [t["id"] for t in tasks]})
        await store.graph.query(store.name, """
            UNWIND $tasks AS item
            MATCH (task:ExternalTask {id:item[0]}), (person:Person {id:item[1]})
            MERGE (task)-[:ASSIGNED_TO]->(person)
        """, {"tasks": [[t["id"], t.get("assignee_person_id", "")]
                       for t in tasks]})


def tokenize_terms(text: str) -> list[str]:
    words = re.findall(r"\b[a-zA-Z0-9_-]{3,30}\b", text.lower())
    stop_words = {
        "the", "and", "for", "with", "that", "this", "from", "have", "are",
        "can", "someone", "please", "task", "work", "need", "about", "your",
        "will", "when", "what", "which", "would", "there", "their", "into"
    }
    return [w for w in words if w not in stop_words]


async def rank_candidates(store: Store, search_terms: str, clickup_list_id: str | None = None) -> list[dict]:
    """Traverse FalkorDB Person -> Role -> Responsibility and past ExternalTask outcomes.
    Returns ranked candidates with exact evidence paths and factor breakdown."""
    query_tokens = set(tokenize_terms(search_terms))
    if not query_tokens:
        return []
    await sync_assignment_graph(store)
    # Candidate eligibility and task ownership are joins performed by FalkorDB.
    # Python only scores the bounded, graph-connected results.
    rows = await store.graph.query(store.name, """
        MATCH path=(person:Person)-[:HAS_ROLE]->(role:Role)-[:RESPONSIBLE_FOR]->(responsibility:Responsibility)
        WHERE person.active=true AND person.confirmed=true AND person.clickup_id <> ''
          AND any(term IN $terms WHERE toLower(role.name + ' ' + responsibility.text) CONTAINS term)
        OPTIONAL MATCH (task:ExternalTask)-[:ASSIGNED_TO]->(person)
        RETURN person.payload AS person, [n IN nodes(path) | n.id] AS path_ids,
               collect(task.payload) AS tasks
        LIMIT 200
    """, {"terms": sorted(query_tokens)})
    all_chunks = {c["id"]: c for c in await current_chunks(store)}

    candidates = []
    for row in rows:
        person = json.loads(row["person"])
        if not set(person.get("evidence_ids", [])) <= all_chunks.keys():
            continue

        person_id = person["id"]
        person_name = person["name"]
        role = person.get("role", "")
        responsibility = person.get("responsibility", "")
        clickup_id = person.get("clickup_id") or person.get("clickup_user_id")

        # Responsibility matching
        resp_text = f"{role} {responsibility}".lower()
        resp_tokens = set(tokenize_terms(resp_text))
        matched_tokens = query_tokens.intersection(resp_tokens)
        
        # Calculate responsibility score
        responsibility_score = len(matched_tokens) / max(1, len(query_tokens)) if query_tokens else 0.0
        if role and any(token in role.lower() for token in query_tokens):
            responsibility_score += 1.0

        # Traverse past tasks assigned to this person
        person_tasks = [json.loads(t) for t in row["tasks"] if t]
        
        similar_on_time = 0
        reassigned_or_overdue = 0
        open_count = 0

        past_task_evidence = []
        for t in person_tasks:
            status = t.get("status", "").lower()
            if status in ("open", "in_progress", "to do"):
                open_count += 1
            
            task_tokens = set(tokenize_terms(t.get("title", "") + " " + t.get("description", "")))
            is_similar = bool(query_tokens.intersection(task_tokens))
            
            outcome = t.get("outcome", "").lower()
            if is_similar:
                if outcome in ("overdue", "completed_late", "reassigned") or t.get("reassigned"):
                    reassigned_or_overdue += 1
                    past_task_evidence.append(t["id"])
                elif outcome == "completed_on_time":
                    similar_on_time += 1
                    past_task_evidence.append(t["id"])

        if responsibility_score == 0:
            continue
        total_score = (
                5.0 * responsibility_score +
                1.5 * min(similar_on_time, 5) -
                2.0 * min(reassigned_or_overdue, 5) -
                0.3 * min(open_count, 10)
            )

        # Collect valid evidence IDs
        person_evidence_ids = [eid for eid in person.get("evidence_ids", []) if eid in all_chunks]
        
        path_ids = row["path_ids"]

        factors = {
            "responsibility_score": round(responsibility_score, 2),
            "matched_terms": sorted(matched_tokens),
            "similar_completed_on_time": similar_on_time,
            "reassigned_or_overdue": reassigned_or_overdue,
            "open_tasks": open_count,
            "role": role,
        }

        # Build human-readable summary
        summary_parts = []
        if role:
            summary_parts.append(f"Role: {role}")
        if matched_tokens:
            summary_parts.append(f"matched keywords ({', '.join(sorted(matched_tokens))})")
        if similar_on_time > 0:
            summary_parts.append(f"{similar_on_time} similar task(s) completed on time")
        if reassigned_or_overdue > 0:
            summary_parts.append(f"{reassigned_or_overdue} task(s) overdue or reassigned")
        summary_parts.append(f"{open_count} open task(s)")

        candidates.append({
            "person_id": person_id,
            "name": person_name,
            "clickup_id": clickup_id,
            "role": role,
            "score": round(total_score, 3),
            "factors": factors,
            "breakdown": {"role_match": bool(query_tokens.intersection(tokenize_terms(role))),
                          "responsibility_score": factors["responsibility_score"],
                          "completed_outcomes": similar_on_time, "active_load": open_count,
                          "overdue_outcomes": reassigned_or_overdue},
            "path_ids": path_ids,
            "evidence_ids": person_evidence_ids[:10],
            "evidence_chunks": [{"id": eid, "text": all_chunks[eid].get("excerpt") or all_chunks[eid].get("text", ""),
                                 "location": all_chunks[eid].get("location", "")}
                                for eid in person_evidence_ids[:10]],
            "past_task_ids": past_task_evidence[:5],
            "summary": "; ".join(summary_parts) or "Profile match",
        })

    candidates.sort(key=lambda c: c["score"], reverse=True)
    for rank_idx, cand in enumerate(candidates, start=1):
        cand["rank"] = rank_idx

    return candidates
