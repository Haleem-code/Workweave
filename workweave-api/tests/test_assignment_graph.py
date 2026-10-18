"""Regression tests against a disposable FalkorDB (never the production instance)."""
import asyncio
import os
import pytest
import pytest_asyncio
from workweave_api.assignment import rank_candidates
from workweave_api.graph import Graph
from workweave_api.store import Store, uid


@pytest_asyncio.fixture
async def graph_store():
    graph = Graph(os.environ.get("WORKWEAVE_TEST_GRAPH_URL", "redis://127.0.0.1:16380"))
    store = Store(graph, "ww_" + uid("assignment_test"))
    await graph.schema(store.name)
    try:
        yield store
    finally:
        await graph.redis.execute_command("GRAPH.DELETE", store.name)
        await graph.close()


async def seed_roster(store):
    await store.put("source", {"id": "source_team", "version": "v1", "active": True, "import_complete": True})
    await store.put("chunk", {"id": "chunk_fin", "source_id": "source_team", "version": "v1", "active": True,
                              "excerpt": "Ada owns billing exports", "text": "Ada owns billing exports"})
    await store.link("source_team", "HAS_CHUNK", "chunk_fin")
    await store.put("person", {"id": "person_ada", "name": "Ada Bello", "role": "Finance Manager",
                              "responsibility": "billing export invoices", "clickup_id": "101", "confirmed": True,
                              "evidence_ids": ["chunk_fin"]})
    await store.put("person", {"id": "person_yusuf", "name": "Yusuf", "role": "Dispatch Supervisor",
                              "responsibility": "warehouse packing", "clickup_id": "102", "confirmed": True})
    for ident, outcome in [("on_time", "completed_on_time"), ("late", "completed_late")]:
        await store.put("external_task", {"id": ident, "title": "billing export", "status": "closed",
                                         "outcome": outcome, "assignee_person_id": "person_ada"})


@pytest.mark.asyncio
async def test_assignment_traverses_real_paths_and_penalizes_late_work(graph_store):
    store = graph_store
    await seed_roster(store)
    candidates = await rank_candidates(store, "billing export")
    assert [c["person_id"] for c in candidates] == ["person_ada"]
    ada = candidates[0]
    assert ada["factors"]["similar_completed_on_time"] == 1
    assert ada["factors"]["reassigned_or_overdue"] == 1
    assert ada["evidence_chunks"][0]["text"] == "Ada owns billing exports"
    rows = await store.graph.query(store.name, """
        MATCH path=(p:Person {id:$id})-[:HAS_ROLE]->(:Role)-[:RESPONSIBLE_FOR]->(:Responsibility)
        RETURN [n IN nodes(path) | n.id] AS ids
    """, {"id": "person_ada"})
    assert rows[0]["ids"] == ada["path_ids"]
    assert ada["breakdown"]["completed_outcomes"] == 1
    assert await rank_candidates(store, "nuclear physics") == []


@pytest.mark.asyncio
async def test_unconfirmed_unmapped_and_revoked_roles_are_not_recommended(graph_store):
    store = graph_store
    await seed_roster(store)
    ada = await store.get("person", "person_ada")
    ada["confirmed"] = False
    await store.put("person", ada)
    assert await rank_candidates(store, "billing export") == []
    ada.update(confirmed=True, clickup_id="")
    await store.put("person", ada)
    assert await rank_candidates(store, "billing export") == []
    ada["clickup_id"] = "101"
    await store.put("person", ada)
    source = await store.get("source", "source_team")
    source["active"] = False
    await store.put("source", source)
    assert await rank_candidates(store, "billing export") == []


@pytest.mark.asyncio
async def test_claims_are_atomic_and_stale_workers_cannot_save(graph_store):
    store = graph_store
    created = await asyncio.gather(*[
        store.create_once("outbox", {"id": "create_once_job", "state": "approved"}) for _ in range(8)
    ])
    assert sum(created) == 1
    await store.put("outbox", {"id": "job", "state": "approved", "attempts": 0})
    results = await asyncio.gather(*[
        store.claim("outbox", "job", ["approved"], "creating", 60, f"owner_{i}") for i in range(8)
    ])
    assert sum(result is not None for result in results) == 1
    current = await store.get("outbox", "job")
    assert current["attempts"] == 1
    assert current["state"] == "creating"
    assert not await store.put_owned("outbox", {**current, "state": "done"}, "wrong_owner")
    assert await store.put_owned("outbox", {**current, "state": "approved", "lease_until": 0}, current["lease_owner"])
    assert await store.claim("outbox", "job", ["approved"], "creating", 60, "new_owner") == 2
    assert not await store.put_owned("outbox", {**current, "state": "done"}, current["lease_owner"])
    assert next(item for item in await store.list("outbox") if item["id"] == "job")["lease_owner"] == "new_owner"
