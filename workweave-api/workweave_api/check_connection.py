"""Verify configured FalkorDB with a real graph query; never print credentials."""
import asyncio
from .config import settings
from .graph import Graph, GraphUnavailable


async def check():
    graph = Graph(settings.graph_connection_url)
    try:
        result = await graph.query('ww_control', 'RETURN 1 AS available')
        if not result or result[0].get('available') != 1:
            raise GraphUnavailable('Unexpected graph response')
        connection = settings.graph_connection_info
        print(f"FalkorDB connected; graph query passed; {connection['mode']}; TLS {'enabled' if connection['tls'] else 'disabled'}.")
    except GraphUnavailable:
        print('Connection failed. Check host, port, username/password, TLS support, and network access. Credentials are not shown.')
        raise SystemExit(1)
    finally:
        await graph.close()


if __name__ == '__main__':
    asyncio.run(check())
