import asyncio
import os
import json
# pyrefly: ignore [missing-import]
import pytest
from workweave_api.config import Settings
from workweave_api.graph import Graph
from workweave_api.store import Store,company_store,uid
from workweave_api.providers import Router
from workweave_api.engine import Engine
from workweave_api.demo import seed


@pytest.mark.asyncio
async def test_real_private_mcp_retrieval_and_cited_answer(tmp_path):
    test_url=os.environ.get('WORKWEAVE_TEST_GRAPH_URL', 'redis://localhost:16380')
    graph=Graph(test_url)
    router=Router(Settings(graph_host='',graph_url=test_url,ollama_url='http://localhost:1',data_dir=tmp_path))
    control=Store(graph,'ww_control')
    company,user_id=uid('company'),uid('user')
    await graph.schema('ww_'+company)
    await control.put('company',{'id':company,'name':'MCP fixture','provider_policy':{'allowed':['ollama'],'local_only':True}})
    await control.put('member',{'id':company+':'+user_id,'user_id':user_id,'company_id':company,'role':'admin'})
    store=company_store(graph,company)
    await seed(store,router)
    conv=await store.put('conversation',{'id':uid('conversation'),'user_id':user_id,'title':'Ownership'})
    run=await store.put('run',{'id':uid('run'),'user_id':user_id,'conversation_id':conv['id'],'status':'queued','checkpoint':'queued','query':'Who owns Acme cartons?','events':[],'findings':[],'paths':[]})
    calls=[]
    async def generate(messages,policy,tools,notify):
        calls.append(messages)
        if len(calls)==1:
            assert {t['name'] for t in tools}=={'search_knowledge','trace_impact','find_owner','get_procedure','recall_episode','create_review_task'}
            return {'text':'','tool_calls':[{'id':'retrieval','name':'search_knowledge','arguments':{'query':'Acme cartons'}},{'id':'owner','name':'find_owner','arguments':{'entity_id':'SO1'}}], 'provider':'ollama','native_parts':[],'usage':{}}
        outputs=[m for m in messages if m['role']=='tool']
        owner=json.loads(outputs[-1]['content'])
        if 'result' in owner: owner=owner['result']
        assert owner['name']=='Customer Success'
        retrieval=json.loads(outputs[-2]['content'])
        if 'result' in retrieval: retrieval=retrieval['result']
        evidence=next(e for e in retrieval['evidence'] if e.get('entity_id')=='SalesOrder:SO1')
        return {'text':json.dumps({'claims':[{'text':'Acme cartons is assigned to Customer Success.','evidence_ids':[evidence['id']]}]}),'tool_calls':[],'provider':'ollama','native_parts':[],'usage':{}}
    router.generate=generate
    await Engine(graph,router).execute(company,run['id'])
    final=await store.get('run',run['id'])
    assert final['status']=='completed'
    assert any(e['type']=='tool.finished' and not e['data']['error'] for e in final['events'])
    assert (await store.get('message','answer_'+run['id']))['claims'][0]['evidence_ids']
    assert (await store.get('episode','episode_'+run['id']))['shared'] is False
    await router.close();await graph.close()
