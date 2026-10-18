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
          "task": "Task", "episode": "Episode", "procedure": "Procedure", "change": "Change",
          "person": "Person", "connection": "Connection",
          "slack_event": "SlackEvent", "proposal": "TaskProposal", "outbox": "Outbox",
          "external_task": "ExternalTask", "external_identity": "ExternalIdentity",
          "role": "Role", "responsibility": "Responsibility", "integration_route": "IntegrationRoute",
          "roster": "RosterMember"}


class Store:
    def __init__(self, graph: Graph, name: str):
        self.graph, self.name = graph, name

    async def put(self, kind: str, value: dict, props: dict | None = None):
        label = LABELS[kind]
        value.setdefault("created_at", now())
        value["updated_at"] = now()
        payload = json.dumps(value, default=str)
        params = {"id": value["id"], "kind": kind, "payload": payload,
                  "active": value.get("active", True), "updated": value["updated_at"]}
        set_clauses = ["n.kind=$kind", "n.payload=$payload", "n.active=$active", "n.updated_at=$updated"]
        for key in ("state", "lease_until", "lease_owner", "attempts"):
            if key in value:
                params[key] = value[key]
                set_clauses.append(f"n.{key}=${key}")
        if props:
            for k, v in props.items():
                params[k] = v
                set_clauses.append(f"n.{k}=${k}")
        set_str = ", ".join(set_clauses)
        await self.graph.query(self.name,
            f"MERGE (n:Record:{label} {{id:$id}}) SET {set_str} RETURN n.id AS id",
            params)
        return value

    async def create_once(self, kind: str, value: dict, props: dict | None = None) -> bool:
        label = LABELS[kind]
        value.setdefault("created_at", now())
        value["updated_at"] = now()
        payload = json.dumps(value, default=str)
        params = {"id": value["id"], "kind": kind, "payload": payload,
                  "active": value.get("active", True), "updated": value["updated_at"]}
        set_clauses = ["n.kind=$kind", "n.payload=$payload", "n.active=$active", "n.updated_at=$updated"]
        if "state" in value:
            params["state"] = str(value["state"])
            set_clauses.append("n.state=$state")
        if props:
            for k, v in props.items():
                params[k] = v
                set_clauses.append(f"n.{k}=${k}")
        set_str = ", ".join(set_clauses)
        query = (
            f"OPTIONAL MATCH (existing:Record {{id:$id}}) "
            f"WITH existing WHERE existing IS NULL "
            f"CREATE (n:Record:{label} {{id:$id}}) "
            f"SET {set_str} "
            f"RETURN n.id AS id"
        )
        rows = await self.graph.query(self.name, query, params)
        return bool(rows and rows[0].get("id"))

    async def claim(self, kind: str, ident: str, from_states: list[str], to_state: str, lease_seconds: float, owner: str) -> int | None:
        current_now = now()
        until = current_now + lease_seconds
        rows = await self.graph.query(self.name,
            """MATCH (n:Record {id:$id, kind:$kind})
               WHERE (n.state IN $from_states) OR (n.state = $to_state AND coalesce(n.lease_until, 0) < $now)
               SET n.state = $to_state,
                   n.lease_until = $until,
                   n.lease_owner = $owner,
                   n.attempts = coalesce(n.attempts, 0) + 1,
                   n.updated_at = $now
               RETURN n.attempts AS attempts, n.payload AS payload""",
            {"id": ident, "kind": kind, "from_states": from_states, "to_state": to_state,
             "now": current_now, "until": until, "owner": owner}
        )
        if not rows:
            return None
        attempts = int(rows[0]["attempts"])
        return attempts

    @staticmethod
    def _decode(row: dict) -> dict:
        value = json.loads(row["payload"])
        for key in ("state", "lease_until", "lease_owner", "attempts"):
            if row.get(key) is not None:
                value[key] = row[key]
        return value

    async def put_owned(self, kind: str, value: dict, owner: str) -> bool:
        """Only the current, unexpired lease holder may advance a durable job."""
        stamp = now()
        value["updated_at"] = stamp
        rows = await self.graph.query(self.name, """
            MATCH (n:Record {id:$id, kind:$kind})
            WHERE n.lease_owner=$owner AND n.lease_until > $now
            SET n.payload=$payload, n.state=$state, n.updated_at=$now,
                n.lease_until=$until, n.attempts=$attempts
            RETURN n.id AS id
        """, {"id": value["id"], "kind": kind, "owner": owner, "now": stamp,
              "payload": json.dumps(value, default=str), "state": value["state"],
              "until": value.get("lease_until", 0), "attempts": value.get("attempts", 0)})
        return bool(rows)

    async def get(self, kind: str, ident: str) -> dict | None:
        rows = await self.graph.query(self.name, "MATCH (n:Record {id:$id,kind:$kind}) RETURN n.payload AS payload, n.state AS state, n.lease_until AS lease_until, n.lease_owner AS lease_owner, n.attempts AS attempts", {"id": ident, "kind": kind})
        return self._decode(rows[0]) if rows else None

    async def list(self, kind: str, limit: int = 500) -> list[dict]:
        rows = await self.graph.query(self.name, "MATCH (n:Record {kind:$kind}) RETURN n.payload AS payload, n.state AS state, n.lease_until AS lease_until, n.lease_owner AS lease_owner, n.attempts AS attempts ORDER BY n.updated_at DESC LIMIT $limit", {"kind": kind, "limit": limit})
        return [self._decode(x) for x in rows]

    async def link(self, source: str, relation: str, target: str):
        allowed = {
            "DEPENDS_ON", "OWNED_BY", "SUPPORTED_BY", "HAS_CHUNK", "SUPERSEDES",
            "HAS_RECEIPT", "BASED_ON", "PRODUCED", "HANDED_OFF_TO", "HAS_PERSON",
            "HAS_ROLE", "RESPONSIBLE_FOR", "IDENTIFIED_AS", "PROPOSED", "RECOMMENDS",
            "ASSIGNED_TO", "FOR"
        }
        if relation not in allowed:
            raise ValueError(f"Unapproved relationship: {relation}")
        await self.graph.query(self.name, f"MATCH (a:Record {{id:$a}}),(b:Record {{id:$b}}) MERGE (a)-[:{relation}]->(b)", {"a": source, "b": target})


def company_store(graph: Graph, company_id: str) -> Store:
    # IDs come from the control graph after membership authorization, never from a model.
    return Store(graph, f"ww_{company_id}")
