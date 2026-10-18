import asyncio
import json
import re
from urllib.parse import urlsplit, urlunsplit
from redis.asyncio import Redis
from redis.asyncio.retry import Retry
from redis.backoff import NoBackoff


class GraphUnavailable(RuntimeError):
    pass


class Graph:
    """Scalar-only GRAPH.QUERY adapter. All queries are internal templates."""

    def __init__(self, url: str):
        # Windows may wait on ::1 even when Docker publishes only IPv4 localhost.
        parsed = urlsplit(url)
        if parsed.scheme == "redis" and parsed.hostname == "localhost":
            credentials = parsed.netloc.rsplit("@", 1)[0] + "@" if "@" in parsed.netloc else ""
            url = urlunsplit(parsed._replace(netloc=credentials + "127.0.0.1:" + str(parsed.port or 6379)))
        self.redis = Redis.from_url(url, decode_responses=True, socket_timeout=20, socket_connect_timeout=2, retry=Retry(NoBackoff(), 0))
        self.schema_lock = asyncio.Lock()

    async def query(self, graph: str, query: str, params: dict | None = None) -> list[dict]:
        if not re.fullmatch(r"ww_[a-zA-Z0-9_]+", graph):
            raise ValueError("Invalid graph name")
        values = []
        for key, value in (params or {}).items():
            if not re.fullmatch(r"[a-zA-Z_][a-zA-Z0-9_]*", key):
                raise ValueError("Invalid parameter")
            values.append(f"{key}={json.dumps(value, ensure_ascii=True, allow_nan=False)}")
        statement = ("CYPHER " + " ".join(values) + " " if values else "") + query
        try:
            result = await self.redis.execute_command("GRAPH.QUERY", graph, statement, "--compact", "TIMEOUT", 10000)
        except Exception as exc:
            # No query parameters or credentials are emitted in public errors.
            raise GraphUnavailable("FalkorDB query failed; check database availability and schema") from exc
        if len(result) < 2:
            return []
        names = [x if isinstance(x, str) else x[-1] for x in result[0]]
        return [dict(zip(names, [decode_scalar(cell) for cell in row])) for row in result[1]]

    async def schema(self, name: str):
        async with self.schema_lock:
            indexes = await self.query(name, "CALL db.indexes() YIELD label, types RETURN label, types")
            present = set()
            for item in indexes:
                kinds = item["types"]
                for kind in re.findall(r"RANGE|FULLTEXT|VECTOR", str(kinds)):
                    present.add((item["label"], kind))
            if ("Record", "RANGE") not in present:
                await self.query(name, "CREATE INDEX FOR (n:Record) ON (n.id)")
            if ("Chunk", "FULLTEXT") not in present:
                await self.query(name, "CREATE FULLTEXT INDEX FOR (n:Chunk) ON (n.text)")
            if ("Chunk", "VECTOR") not in present:
                await self.query(name, "CREATE VECTOR INDEX FOR (n:Chunk) ON (n.embedding) OPTIONS {dimension:768, similarityFunction:'cosine'}")
            if ("Responsibility", "FULLTEXT") not in present:
                try:
                    await self.query(name, "CREATE FULLTEXT INDEX FOR (n:Responsibility) ON (n.text)")
                except Exception:
                    pass
            if ("ExternalTask", "FULLTEXT") not in present:
                try:
                    await self.query(name, "CREATE FULLTEXT INDEX FOR (n:ExternalTask) ON (n.title)")
                except Exception:
                    pass

    async def close(self):
        await self.redis.aclose()


def decode_scalar(cell):
    kind, value = cell
    if kind == 1:
        return None
    if kind in (2, 3):
        return value
    if kind == 5:
        return float(value)
    if kind == 4:
        return value == "true"
    if kind == 6:
        return [decode_scalar(item) for item in value]
    if kind == 10:
        return {value[i]: decode_scalar(value[i + 1]) for i in range(0, len(value), 2)}
    raise GraphUnavailable("Graph query returned a non-scalar result; use reviewed scalar projections")
