import asyncio
import json
import re
from .store import Store


class Retrieval:
    def __init__(self, router):
        self.router = router

    async def search(self, store: Store, query: str, limit: int = 8, user_id=None):
        # Membership was checked before selecting this graph. Recheck every source/version.
        sources = {s["id"]: s for s in await store.list("source", 10000) if not s.get("is_version")}
        all_chunks = await store.list("chunk", 10000)
        current = [c for c in all_chunks if c.get('active') and sources.get(c['source_id'], {}).get('active') and sources[c['source_id']].get('import_complete') and sources[c['source_id']]['version'] == c['version']]
        ranked = []
        tokens = re.findall(r"[\w-]+", query)[:15]
        if tokens:
            rows = await store.graph.query(store.name,
                "CALL db.idx.fulltext.queryNodes('Chunk',$query) YIELD node, score RETURN node.payload AS payload, score ORDER BY score DESC LIMIT 30",
                {"query": " | ".join(tokens)})
            ranked.append([json.loads(r["payload"]) for r in rows])
        semantic_status = "ready"
        try:
            if len(current) <= 6:
                # All current excerpts fit in context; an embedding call cannot
                # improve recall here and can cold-load a local model needlessly.
                ranked.append(current)
                semantic_status = "not_needed"
            else:
                vector = await asyncio.wait_for(self.router.embed(query), timeout=8)
                rows = await store.graph.query(store.name,
                    "CALL db.idx.vector.queryNodes('Chunk','embedding',30,vecf32($vector)) YIELD node, score RETURN node.payload AS payload, score ORDER BY score DESC",
                    {"vector": vector})
                ranked.append([json.loads(r["payload"]) for r in rows])
        except Exception:
            semantic_status = "degraded"
        exact = [c for c in all_chunks if query.lower() in c["excerpt"].lower() or any(t.lower() == (c.get("entity_id") or "").split(":")[-1].lower() for t in tokens)]
        ranked.insert(0, exact)
        scores, candidates = {}, {}
        for group in ranked:
            for i, item in enumerate(group):
                source = sources.get(item["source_id"])
                if not item.get("active") or not source or not source.get("active") or not source.get("import_complete") or source["version"] != item["version"]:
                    continue
                candidates[item["id"]] = item
                scores[item["id"]] = scores.get(item["id"], 0) + 1 / (60 + i + 1)
        selected = [candidates[k] for k in sorted(scores, key=scores.get, reverse=True)[:limit]]
        # Expand confirmed dependencies/ownership after rank fusion, using current versions only.
        seed_ids = [c.get("entity_id") for c in selected if c.get("entity_id")]
        graph_paths = []
        if seed_ids:
            related = await store.graph.query(store.name,
                "MATCH path=(seed:Entity {active:true})-[:DEPENDS_ON|OWNED_BY*1..2]->(related:Entity {active:true}) WHERE seed.id IN $ids AND all(n IN nodes(path) WHERE n.active=true) RETURN related.payload AS payload, [n IN nodes(path) | n.id] AS ids LIMIT 24", {"ids": seed_ids})
            related_ids = set()
            for row in related:
                entity = json.loads(row["payload"])
                source = sources.get(entity["source_id"])
                if source and source.get("active") and source.get("import_complete") and source["version"] == entity["version"]:
                    related_ids.add(entity["id"])
                    graph_paths.append(row["ids"])
            for chunk in all_chunks:
                source = sources.get(chunk["source_id"])
                if chunk.get("entity_id") in related_ids and chunk["id"] not in {c["id"] for c in selected} and chunk.get("active") and source and source.get("active") and source["version"] == chunk["version"]:
                    selected.append(chunk)
                    if len(selected) >= 12:
                        break
        episodes = []
        for episode in await store.list("episode", 100):
            if not episode.get("active", True):
                continue
            if not episode.get("shared") and episode.get("user_id") != user_id:
                continue
            if not {t.lower() for t in tokens}.intersection(re.findall(r"[\w-]+", episode["summary"].lower())):
                continue
            # Invalidated evidence cannot be reintroduced through a saved summary.
            support = [c for c in all_chunks if c["id"] in episode.get("evidence_ids", [])]
            if support and all(c.get("active") and sources.get(c["source_id"], {}).get("active") and sources[c["source_id"]]["version"] == c["version"] for c in support):
                episodes.append(episode)
        profile = await store.get("profile", "profile")
        if profile and profile.get("evidence_ids"):
            valid_ids = {c["id"] for c in all_chunks if c.get("active") and sources.get(c["source_id"], {}).get("active") and sources[c["source_id"]]["version"] == c["version"]}
            if not set(profile["evidence_ids"]) <= valid_ids:
                profile = None
        procedures = [p for p in await store.list("procedure") if p.get("active") and p.get("approved")]
        current_ids = {c['id'] for c in current}
        people = [p for p in await store.list('person') if p.get('confirmed') and set(p.get('evidence_ids', [])) <= current_ids]
        return {"evidence": selected, "episodes": episodes[:3], "people": people[:30], "profile": profile if profile and profile.get("confirmed") else None,
                "procedures": procedures[:3], "graph_paths": graph_paths, "semantic_status": semantic_status}
