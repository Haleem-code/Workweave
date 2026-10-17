import asyncio
import os

import httpx
import pytest

from workweave_api import demo
from workweave_api.config import Settings
from workweave_api.main import create_app
from workweave_api.store import company_store, uid


@pytest.mark.asyncio
async def test_example_preparation_recovers_without_replacing_company_data(tmp_path, monkeypatch):
    app = create_app(Settings(graph_host='', graph_url=os.environ['WORKWEAVE_TEST_GRAPH_URL'],
        ollama_url='http://localhost:1', data_dir=tmp_path, allowed_hosts=['local.test']))
    original_seed = demo.seed

    async def interrupted_seed(store, router, *, resume=False):
        await store.put('profile', {**demo.PROFILE, 'demo_fixture': 'harbor_supply'})
        raise RuntimeError('Synthetic interruption after saving example profile')

    async def finished(client, base, ident):
        for _ in range(200):
            run = (await client.get(base + '/runs/' + ident)).json()
            if run['status'] in ('completed', 'blocked'):
                return run
            await asyncio.sleep(.05)
        pytest.fail('Example did not settle')

    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://local.test') as client:
            account = (await client.post('/api/v1/auth/signup', json={
                'username': uid('demo_tester'), 'password': 'synthetic-test-password', 'company_name': 'Real company fixture'})).json()
            own_base = '/api/v1/companies/' + account['company_id']
            # The demo must not replace an existing company's confirmed profile.
            await client.put(own_base + '/profile', json={'description': 'Keep this company', 'confirmed': True})
            assert (await client.post(own_base + '/demo')).status_code == 400
            assert (await client.get(own_base + '/profile')).json()['description'] == 'Keep this company'
            company = (await client.post('/api/v1/companies', json={'name': 'Recovery example'})).json()
            base = '/api/v1/companies/' + company['id']
            monkeypatch.setattr(demo, 'seed', interrupted_seed)
            response = await client.post(base + '/demo')
            assert response.status_code == 200
            initial = response.json()['runs'][0]
            assert initial['checkpoint'] == 'preparing_example'
            assert initial['status'] == 'queued'
            failed = await finished(client, base, initial['id'])
            assert failed['status'] == 'blocked'
            monkeypatch.setattr(demo, 'seed', original_seed)
            assert (await client.post(base + '/runs/' + initial['id'] + '/resume')).status_code == 200
            recovered = await finished(client, base, initial['id'])
            assert recovered['status'] == 'completed', recovered
            assert len(recovered['findings']) == 2
            repeated = (await client.post(base + '/demo')).json()['runs'][0]
            assert repeated['id'] == recovered['id']
            assert len((await client.get(base + '/tasks')).json()) == 2
            assert len(await company_store(app.state.graph, company['id']).list('procedure')) == 1
