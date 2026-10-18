import os
import httpx
import pytest
from copy import deepcopy
from workweave_api import main as main_module
from workweave_api.config import Settings
from workweave_api.main import create_app
from workweave_api.store import company_store, uid
from workweave_api.connections import read_selection


@pytest.fixture
def isolated_app(monkeypatch, tmp_path):
    # Exercise real HTTP auth/authorization and ingestion.preview; replace only
    # persistence and the unused worker, so no credentials or database are needed.
    records = {}
    class MemoryGraph:
        def __init__(self, *args): pass
        async def schema(self, *args): pass
        async def close(self): pass
    class MemoryStore:
        def __init__(self, graph, name): self.name=name
        async def put(self, kind, value):
            records[(self.name,kind,value['id'])]=deepcopy(value);return value
        async def get(self, kind, ident): return deepcopy(records.get((self.name,kind,ident)))
        async def list(self, kind, limit=500): return [deepcopy(v) for (name,k,_),v in records.items() if name==self.name and k==kind][:limit]
    async def idle(*args): pass
    monkeypatch.setattr(main_module,'Graph',MemoryGraph)
    monkeypatch.setattr(main_module,'Store',MemoryStore)
    monkeypatch.setattr(main_module,'company_store',lambda graph,ident:MemoryStore(graph,'ww_'+ident))
    monkeypatch.setattr(main_module.Engine,'start',idle)
    monkeypatch.setattr(main_module.Engine,'stop',idle)
    return create_app(Settings(_env_file=None,graph_url='redis://unused:6379',ollama_url='http://localhost:1',data_dir=tmp_path,allowed_hosts=['local.test']))


@pytest.mark.asyncio
@pytest.mark.parametrize('provider,selection,payload', [
    ('slack','C123456',{'ok':True,'messages':[{'ts':'1.0','user':'UDEMO','text':'Fictional shipment is late'}],'has_more':True}),
    ('clickup','12345',{'tasks':[{'id':'DEMO1','name':'Check fictional shipment','status':{'status':'open'},'assignees':[{'username':'Demo owner'}]}],'last_page':True})])
async def test_selected_connection_preview_scope_and_disconnect(isolated_app, provider, selection, payload):
    app=isolated_app
    calls=[]
    def remote(request):
        calls.append(request)
        assert request.method=='GET'
        assert request.url.host in ('slack.com','api.clickup.com')
        assert 'synthetic-test-token' in request.headers['authorization']
        return httpx.Response(200,json=payload)
    await app.state.router.http.aclose()
    app.state.router.http=httpx.AsyncClient(transport=httpx.MockTransport(remote))
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://local.test') as client:
            account=(await client.post('/api/v1/auth/signup',json={'username':uid('connector'),'password':'synthetic-password-123','company_name':'Fictional connector company'})).json()
            base='/api/v1/companies/'+account['company_id']
            body={'token':'synthetic-test-token','selection':selection,'synthetic_only':True}
            assert (await client.post('/api/v1/companies/not-a-member/connections/'+provider+'/preview',json=body)).status_code==404
            assert not calls
            assert (await client.post(base+'/connections/'+provider+'/preview',json={**body,'token':'   '})).status_code==400
            response=await client.post(base+'/connections/'+provider+'/preview',json=body)
            assert response.status_code==200,response.text
            assert response.json()['item_count']==1
            assert not (await client.get(base+'/sources')).json()  # explicit confirmation is still required
            state=await client.get(base+'/connections');assert 'synthetic-test-token' not in state.text
            store=main_module.company_store(app.state.graph,account['company_id'])
            assert 'synthetic-test-token' not in str(await store.list('connection'))+str(await store.list('import'))
            assert (await client.post(base+'/connections/'+provider+'/preview',json={**body,'token':''})).status_code==200
            assert (await client.delete(base+'/connections/'+provider)).status_code==200
            assert (await client.post(base+'/connections/'+provider+'/preview',json={**body,'token':''})).status_code==400
            assert app.state.router.vault.read().get('workplace:'+account['company_id']+':'+provider) is None
            before=len(calls)
            fixture=await client.post(base+'/connections/'+provider+'/demo')
            assert fixture.status_code==200 and fixture.json()['connected'] is False
            assert 'SYNTHETIC' in fixture.json()['preview']['sections'][0]['text']
            assert len(calls)==before
            state=(await client.get(base+'/connections')).json()
            assert not next(c for c in state if c['id']==provider)['connected']


@pytest.mark.asyncio
async def test_connector_limits_errors_and_fixed_destinations():
    calls=[]
    def response(request):
        calls.append(request)
        return httpx.Response(200,json={'tasks':[{'id':str(i),'name':'Fictional task'} for i in range(20)]})
    async with httpx.AsyncClient(transport=httpx.MockTransport(response)) as http:
        with pytest.raises(ValueError):await read_selection(http,'clickup','synthetic','https://evil.example')
        assert not calls
        content,count,truncated=await read_selection(http,'clickup','synthetic','123')
        assert count==15 and truncated and b'Task 19:' not in content
