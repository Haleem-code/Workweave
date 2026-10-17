import hashlib
import json
from datetime import date
from .store import Store, now
from .retrieval import Retrieval


TOOL_DEFINITIONS = [
    {"name": "search_knowledge", "description": "Retrieve current company evidence and relevant validated past outcomes", "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"], "additionalProperties": False}},
    {"name": "trace_impact", "description": "Trace confirmed dependencies from a supplier or purchase order to affected sales orders", "parameters": {"type": "object", "properties": {"entity_id": {"type": "string"}}, "required": ["entity_id"], "additionalProperties": False}},
    {"name": "find_owner", "description": "Find the currently recorded team responsible for an entity", "parameters": {"type": "object", "properties": {"entity_id": {"type": "string"}}, "required": ["entity_id"], "additionalProperties": False}},
    {"name": "get_procedure", "description": "Read current approved procedures; procedures never grant additional tool permissions", "parameters": {"type": "object", "properties": {}, "additionalProperties": False}},
    {"name": "recall_episode", "description": "Recall relevant past outcomes with still-valid evidence", "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"], "additionalProperties": False}},
    {"name": "create_review_task", "description": "Create an idempotent internal review task for a finding in this run. No external action is performed.", "parameters": {"type": "object", "properties": {"finding_id": {"type": "string"}}, "required": ["finding_id"], "additionalProperties": False}},
]


class Tools:
    def __init__(self, store: Store, router, run_id: str):
        self.store, self.router, self.run_id = store, router, run_id

    async def call(self, name: str, args: dict):
        definition = next((t for t in TOOL_DEFINITIONS if t["name"] == name), None)
        if not definition:
            raise ValueError("Unknown tool")
        from jsonschema import validate
        validate(args, definition["parameters"])
        return await getattr(self, name)(**args)

    async def search_knowledge(self, query: str):
        run = await self.store.get("run", self.run_id)
        return await Retrieval(self.router).search(self.store, query[:2000], user_id=run.get("user_id") if run else None)

    async def recall_episode(self, query: str):
        return (await self.search_knowledge(query))["episodes"]

    async def get_procedure(self):
        return [p for p in await self.store.list("procedure") if p.get("active") and p.get("approved")]

    async def find_owner(self, entity_id: str):
        entity_id = await self.resolve_entity(entity_id)
        rows = await self.store.graph.query(self.store.name,
            "MATCH (e:Entity {id:$id,active:true})-[:OWNED_BY]->(t:Entity {active:true}) RETURN t.name AS name, t.id AS id", {"id": entity_id})
        return rows[0] if rows else {"name": "Unassigned", "id": None, "gap": "No current team owner is linked"}

    async def resolve_entity(self, identifier: str):
        rows = await self.store.graph.query(self.store.name,
            "MATCH (e:Entity {active:true}) WHERE toLower(e.id)=$key OR toLower(e.business_key)=$key OR toLower(e.name)=$key RETURN e.payload AS payload LIMIT 20", {"key": identifier.lower()})
        sources = {s["id"]: s for s in await self.store.list("source") if not s.get("is_version")}
        candidates = []
        for row in rows:
            entity = json.loads(row["payload"])
            source = sources.get(entity["source_id"])
            if source and source.get("active") and source.get("import_complete") and source["version"] == entity["version"]:
                candidates.append(entity["id"])
        if len(candidates) == 1:
            return candidates[0]
        if not candidates:
            raise ValueError("Record identifier could not be resolved. Search current evidence first; an unresolved record is not an unassigned record.")
        raise ValueError("Identifier is ambiguous. Use a typed identifier from current evidence: " + ", ".join(candidates))

    async def trace_impact(self, entity_id: str):
        entity_id = await self.resolve_entity(entity_id)
        # Paths establish candidates; dates, quantities, and unallocated stock establish impact.
        rows = await self.store.graph.query(self.store.name, """
            MATCH path=(o:Entity {entity_type:'SalesOrder',active:true})-[:DEPENDS_ON*1..4]->(target:Entity {id:$id,active:true})
            WHERE all(n IN nodes(path) WHERE n.active=true)
            MATCH (o)-[:DEPENDS_ON]->(po:Entity {entity_type:'PurchaseOrder',active:true})
            OPTIONAL MATCH (o)-[:DEPENDS_ON]->(product:Entity {entity_type:'Product',active:true})
            RETURN DISTINCT o.payload AS order_json, po.payload AS po_json, product.payload AS product_json,
                [n IN nodes(path) | n.id] AS path_ids ORDER BY o.required_date
        """, {"id": entity_id})
        sources = {s["id"]: s for s in await self.store.list("source", 10000) if not s.get("is_version")}
        chunks = await self.store.list("chunk", 10000)
        findings, paths, excluded, seen, stock_left = [], [], [], set(), {}
        for row in rows:
            order, po = json.loads(row["order_json"]), json.loads(row["po_json"])
            product = json.loads(row["product_json"]) if row["product_json"] else None
            records = [order, po] + ([product] if product else [])
            if order["id"] in seen or any(not sources.get(r["source_id"], {}).get("active") or not sources[r["source_id"]].get("import_complete") or sources[r["source_id"]]["version"] != r["version"] for r in records):
                continue
            seen.add(order["id"])
            evidence = [c["id"] for c in chunks if c.get("entity_id") in {r["id"] for r in records} and c.get("active") and sources.get(c["source_id"], {}).get("version") == c["version"]]
            of, pf = order["fields"], po["fields"]
            required, delivery = of.get("required_date"), pf.get("delivery_date")
            if not required or not delivery:
                explanation, severity = "Delivery or required date is missing; impact needs review.", "needs_review"
            elif date.fromisoformat(delivery) <= date.fromisoformat(required):
                excluded.append({"entity_id": order["id"], "title": order["name"], "reason": f"Supply arrives {delivery}, on or before the required date {required}.", "evidence_ids": evidence})
                continue
            else:
                quantity = of.get("quantity")
                stock = product["fields"].get("stock") if product else None
                if quantity is None or stock is None:
                    explanation, severity = "Delivery is later than the commitment, but quantity or unallocated stock is unknown.", "needs_review"
                else:
                    available = stock_left.setdefault(product["id"], stock)
                    stock_left[product["id"]] = max(0, available - quantity)
                    if available >= quantity:
                        excluded.append({"entity_id": order["id"], "title": order["name"], "reason": f"{available:g} unallocated units cover {quantity:g} required units despite the later delivery.", "evidence_ids": evidence})
                        continue
                    explanation = f"Supply arrives {delivery}, after the required date {required}; {available:g} unallocated units cannot cover {quantity:g} required units."
                    severity = "affected"
            owner = await self.find_owner(order["id"])
            finding = {"id": "finding_" + hashlib.sha256((self.run_id + order["id"]).encode()).hexdigest()[:20],
                       "entity_id": order["id"], "title": "Review " + order["name"], "explanation": explanation,
                       "severity": severity, "owner": owner["name"], "evidence_ids": evidence}
            findings.append(finding)
            paths.append({"nodes": [{"id": x, "label": x.split(":", 1)[-1], "type": x.split(":", 1)[0]} for x in row["path_ids"]],
                          "edges": [{"source": a, "target": b, "label": "DEPENDS_ON"} for a, b in zip(row["path_ids"], row["path_ids"][1:])]})
        review = {"candidate_count": len(seen), "excluded": excluded, "assumption": "Stock means currently unallocated units, allocated to delayed commitments in required-date order. Orders outside the recorded dependency paths are not assessed."}
        run = await self.store.get("run", self.run_id)
        if run:
            run["findings"] = findings
            run["paths"] = paths
            run["impact_review"] = review
            await self.store.put("run", run)
        return {"findings": findings, "paths": paths, **review}

    async def create_review_task(self, finding_id: str):
        run = await self.store.get("run", self.run_id)
        if not run:
            raise ValueError("Run not found")
        finding = next((f for f in run.get("findings", []) if f["id"] == finding_id), None)
        if not finding:
            raise ValueError("Only findings belonging to this run can become tasks")
        evidence = [await self.store.get("chunk", x) for x in finding["evidence_ids"]]
        if not evidence or any(not e or not e.get("active") for e in evidence):
            raise ValueError("Finding evidence is no longer current; reinvestigate")
        owner = await self.find_owner(finding["entity_id"])
        key = "task_" + hashlib.sha256((self.run_id + finding_id).encode()).hexdigest()[:24]
        existing = await self.store.get("task", key)
        if existing:
            return existing
        procedures = await self.get_procedure()
        task = {"id": key, "title": finding["title"], "status": "open", "owner": owner["name"],
                "run_id": self.run_id, "finding_id": finding_id, "evidence_ids": finding["evidence_ids"],
                "procedure_id": procedures[0]["id"] if procedures else None,
                "description": finding["explanation"], "created_at": now(), "updated_at": now(),
                "receipt": {"id": "receipt_" + key, "action": "internal_task_created", "completed_at": now()}}
        # Task and receipt live in one payload/write; a restart cannot split the two.
        await self.store.put("task", task)
        await self.store.link(key, "BASED_ON", finding["evidence_ids"][0])
        await self.store.link(self.run_id, "PRODUCED", key)
        return task
