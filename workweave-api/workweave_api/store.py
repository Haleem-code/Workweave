import json
import time
from uuid import uuid4
from .graph import Graph


def now() -> float:
    return time.time()


def uid(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"


LABELS = {"company": "Company", "member": "Member", "user": "User", "session": "Session",
          "profile": "Profile", "source": "Source", "chunk": "Chunk", "entity": "Entity",
          "import": "Import", "conversation": "Conversation", "message": "Message", "run": "Run",
          "task": "Task", "episode": "Episode", "procedure": "Procedure", "change": "Change", "person": "Person"}


class Store:
    def __init__(self, graph: Graph, name: str):
        self.graph, self.name = graph, name

    async def put(self, kind: str, value: dict):
        label = LABELS[kind]
        value.setdefault("created_at", now())
        value["updated_at"] = now()
        await self.graph.query(self.name,
            f"MERGE (n:Record:{label} {{id:$id}}) SET n.kind=$kind, n.payload=$payload, n.active=$active, n.updated_at=$updated RETURN n.id AS id",
            {"id": value["id"], "kind": kind, "payload": json.dumps(value, default=str),
             "active": value.get("active", True), "updated": value["updated_at"]})
        return value

    async def get(self, kind: str, ident: str) -> dict | None:
        rows = await self.graph.query(self.name, "MATCH (n:Record {id:$id,kind:$kind}) RETURN n.payload AS payload", {"id": ident, "kind": kind})
        return json.loads(rows[0]["payload"]) if rows else None

    async def list(self, kind: str, limit: int = 500) -> list[dict]:
        rows = await self.graph.query(self.name, "MATCH (n:Record {kind:$kind}) RETURN n.payload AS payload ORDER BY n.updated_at DESC LIMIT $limit", {"kind": kind, "limit": limit})
        return [json.loads(x["payload"]) for x in rows]

    async def link(self, source: str, relation: str, target: str):
        if relation not in {"DEPENDS_ON", "OWNED_BY", "SUPPORTED_BY", "HAS_CHUNK", "SUPERSEDES", "HAS_RECEIPT", "BASED_ON", "PRODUCED", "HANDED_OFF_TO", "HAS_PERSON"}:
            raise ValueError("Unapproved relationship")
        await self.graph.query(self.name, f"MATCH (a:Record {{id:$a}}),(b:Record {{id:$b}}) MERGE (a)-[:{relation}]->(b)", {"a": source, "b": target})


def company_store(graph: Graph, company_id: str) -> Store:
    # IDs come from the control graph after membership authorization, never from a model.
    return Store(graph, f"ww_{company_id}")
