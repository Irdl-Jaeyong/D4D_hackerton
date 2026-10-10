import asyncio
import copy
import json
import unittest
from unittest.mock import patch

import httpx
from fastapi import HTTPException
from app import RECORDS, OllamaGateway, create_app

def result():
    return {"items": [{"record_id": r["id"], "record_time": r["time"],
                       "summary": "원본 기록의 해결 여부는 확인할 수 없습니다.",
                       "supporting_quotes": [r["raw"]]} for r in RECORDS]}

class Gateway:
    def __init__(self, value=None):
        self.value = value or result()
        self.seen = []
    async def summarize(self, records):
        self.seen = [dict(r) for r in records]
        return json.dumps(self.value, ensure_ascii=False)

def client(gateway):
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=create_app(gateway)), base_url="http://testserver")

class SummaryTests(unittest.IsolatedAsyncioTestCase):
    async def test_all_records_one_summary_original_unchanged(self):
        g = Gateway(); c = client(g)
        before = (await c.get('/api/records')).json()
        response = await c.post('/api/summary', json={})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(g.seen, [dict(r) for r in RECORDS])
        self.assertEqual(response.json()['record_count'], 3)
        self.assertEqual([x['record_id'] for x in response.json()['items']], [r['id'] for r in RECORDS])
        self.assertEqual(before, (await c.get('/api/records')).json())

    async def test_missing_duplicate_cross_record_quote_and_bad_time(self):
        variants=[]
        v=result();v['items'].pop();variants.append(v)
        v=result();v['items'][1]=copy.deepcopy(v['items'][0]);variants.append(v)
        v=result();v['items'][0]['supporting_quotes']=[RECORDS[1]['raw']];variants.append(v)
        v=result();v['items'][0]['record_time']='wrong';variants.append(v)
        v=result();v['items'][0]['summary']=' ';variants.append(v)
        v=result();v['items'][0]['supporting_quotes']=[];variants.append(v)
        for v in variants:
            with self.subTest(value=v):
                r=await client(Gateway(v)).post('/api/summary',json={})
                self.assertEqual(r.status_code,502)
                self.assertNotIn('items',r.json())

    async def test_unknown_inputs_rejected_without_model(self):
        g=Gateway();c=client(g)
        self.assertEqual((await c.post('/api/summary',json={'records':[]})).status_code,422)
        self.assertEqual((await c.post('/api/summary',json={'question':'anything'})).status_code,422)
        self.assertEqual(g.seen,[])

    async def test_shared_lock_error_recovers_original_available(self):
        started=asyncio.Event();release=asyncio.Event()
        class Slow(Gateway):
            async def summarize(self, records):
                started.set();await release.wait()
                raise HTTPException(503,'model stopped')
        c=client(Slow())
        task=asyncio.create_task(c.post('/api/summary',json={}))
        await started.wait()
        self.assertEqual((await c.post('/api/summary',json={})).status_code,429)
        self.assertEqual((await c.post('/api/explain',json={'record_id':RECORDS[0]['id'],'question':'설명'})).status_code,429)
        release.set();self.assertEqual((await task).status_code,503)
        self.assertEqual(len((await c.get('/api/records')).json()['records']),3)
        self.assertEqual((await c.post('/api/summary',json={})).status_code,503)

    async def test_gateway_single_call_contains_only_synthetic_sources(self):
        real=httpx.AsyncClient;seen=[]
        def handler(request):
            seen.append(json.loads(request.content))
            return httpx.Response(200,json={'done':True,'response':json.dumps(result())})
        with patch('app.httpx.AsyncClient',side_effect=lambda **kwargs:real(transport=httpx.MockTransport(handler),**kwargs)):
            await OllamaGateway().summarize(RECORDS)
        self.assertEqual(len(seen),1)
        prompt=json.loads(seen[0]['prompt'])
        self.assertEqual(set(prompt),{'synthetic_records'})
        self.assertEqual(prompt['synthetic_records'],[dict(r) for r in RECORDS])
