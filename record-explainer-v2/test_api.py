import asyncio
import json
import unittest
from unittest.mock import patch

import httpx
from app import MODEL, RECORDS, create_app
from fastapi import HTTPException

class FakeGateway:
    def __init__(self, change=None):
        self.change = change or {}
        self.seen = []

    async def generate(self, record, question, is_read):
        self.seen.append((dict(record), question, is_read))
        result = {"answer": "기록에서 해결 여부는 확인할 수 없습니다.", "record_id": record["id"], "record_time": record["time"], "answerable": False, "supporting_quotes": []}
        result.update(self.change)
        return json.dumps(result, ensure_ascii=False)

def client_for(app):
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver", trust_env=False)

class ApiTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.gateway = FakeGateway()
        self.client = client_for(create_app(self.gateway))

    async def ask(self, record_id="TEST-A-001", question="상태를 설명해주세요", client=None):
        return await (client or self.client).post("/api/explain", json={"record_id": record_id, "question": question})

    async def test_read_is_idempotent_and_does_not_modify_original_or_resolution(self):
        before = (await self.client.get("/api/records")).json()["records"]
        for _ in range(3):
            self.assertEqual((await self.client.post("/api/records/TEST-A-001/read")).status_code, 200)
        after = (await self.client.get("/api/records")).json()["records"]
        self.assertTrue(after[0]["read"])
        for a, b in zip(before, after):
            self.assertEqual({k:v for k,v in a.items() if k!="read"}, {k:v for k,v in b.items() if k!="read"})
        await self.ask()
        self.assertTrue(self.gateway.seen[-1][2])

    async def test_unknown_and_empty_input_never_call_model(self):
        self.assertEqual((await self.ask("MISSING")).status_code, 404)
        self.assertEqual((await self.ask(question="   ")).status_code, 422)
        self.assertEqual((await self.ask(question="x"*501)).status_code, 422)
        self.assertEqual((await self.client.post("/api/records/MISSING/read")).status_code, 404)
        self.assertEqual(self.gateway.seen, [])

    async def test_selected_record_only_and_repeated_questions(self):
        for _ in range(3):
            response = await self.ask("TEST-B-001")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["evidence"]["record_id"], "TEST-B-001")
        self.assertTrue(all(r[0]["id"] == "TEST-B-001" for r in self.gateway.seen))
        self.assertTrue(all(not r["read"] for r in (await self.client.get("/api/records")).json()["records"]))

    async def test_wrong_evidence_or_empty_answer_is_not_displayable(self):
        for change in [{"record_id":"MISSING"}, {"record_id":"TEST-C-001"}, {"record_time":"wrong"}, {"answer":" "}]:
            with self.subTest(change=change):
                response = await self.ask(client=client_for(create_app(FakeGateway(change))))
                self.assertEqual(response.status_code, 502)
                self.assertNotIn("answer", response.json())

    async def test_model_failure_keeps_basic_record_view(self):
        real_client = httpx.AsyncClient
        for error, expected in [(httpx.ConnectError("stopped"),503), (httpx.ReadTimeout("timeout"),504)]:
            def handler(request):
                raise error
            def factory(**kwargs):
                return real_client(transport=httpx.MockTransport(handler), **kwargs)
            client = client_for(create_app())
            with self.subTest(error=type(error).__name__), patch("app.httpx.AsyncClient", side_effect=factory):
                self.assertEqual((await self.ask(client=client)).status_code, expected)
                self.assertEqual(len((await client.get("/api/records")).json()["records"]),3)

    async def test_malformed_incomplete_and_missing_model_responses(self):
        real_client = httpx.AsyncClient
        for status, data, expected in [(200,{"done":False,"response":"{}"},502), (200,{"done":True,"response":"not json"},502), (404,{"error":"model missing"},503)]:
            def factory(**kwargs):
                return real_client(transport=httpx.MockTransport(lambda r:httpx.Response(status,json=data)),**kwargs)
            client = client_for(create_app())
            with self.subTest(data=data), patch("app.httpx.AsyncClient",side_effect=factory):
                self.assertEqual((await self.ask(client=client)).status_code,expected)

    async def test_ungrounded_quote_or_no_quote_is_rejected(self):
        for change in [{"answerable":True,"supporting_quotes":[]}, {"answerable":True,"supporting_quotes":["장치는 정상입니다"]}]:
            response=await self.ask(client=client_for(create_app(FakeGateway(change))))
            self.assertEqual(response.status_code,502)
        response=await self.ask(client=client_for(create_app(FakeGateway({"answer":"없는 사실", "answerable":False}))))
        self.assertEqual(response.status_code,200)
        self.assertNotIn("없는 사실",response.json()["answer"])

    async def test_concurrent_request_rejected_and_lock_recovers(self):
        entered,release=asyncio.Event(),asyncio.Event()
        class Slow(FakeGateway):
            async def generate(self,*args):
                entered.set()
                await release.wait()
                return await super().generate(*args)
        client=client_for(create_app(Slow()))
        first=asyncio.create_task(self.ask(client=client))
        await asyncio.wait_for(entered.wait(),2)
        try:
            self.assertEqual((await self.ask(client=client)).status_code,429)
            self.assertEqual((await client.get("/api/records")).status_code,200)
        finally:
            release.set()
        self.assertEqual((await first).status_code,200)
        self.assertEqual((await self.ask(client=client)).status_code,200)

    async def test_static_page_served_without_exposing_project_files(self):
        self.assertEqual((await self.client.get("/")).status_code,200)
        for path in ("/state.js", "/ui.js"):
            response = await self.client.get(path)
            self.assertEqual(response.status_code, 200)
            self.assertIn("javascript", response.headers["content-type"])
        self.assertEqual((await self.client.get("/app.py")).status_code,404)
        for path, kind in [("/dashboard.css","text/css"),("/assets/harbor-concept.png","image/png")]:
            response=await self.client.get(path)
            self.assertEqual(response.status_code,200)
            self.assertIn(kind,response.headers['content-type'])
        self.assertEqual((await self.client.get('/assets/unknown.png')).status_code,404)

    async def test_model_error_releases_lock_for_retry(self):
        class OnceFail(FakeGateway):
            failed = False
            async def generate(self, *args):
                if not self.failed:
                    self.failed = True
                    raise HTTPException(504, "injected timeout")
                return await super().generate(*args)
        client = client_for(create_app(OnceFail()))
        original = (await client.get("/api/records")).json()
        self.assertEqual((await self.ask(client=client)).status_code, 504)
        self.assertEqual((await self.ask(client=client)).status_code, 200)
        self.assertEqual((await client.get("/api/records")).json(), original)

    async def test_unexpected_fields_and_wrong_input_types_are_rejected(self):
        for payload in [
            {"record_id": "TEST-A-001", "question": "설명", "command": "ignored"},
            {"record_id": "TEST-A-001", "question": None},
            {"record_id": 123, "question": "설명"},
        ]:
            self.assertEqual((await self.client.post("/api/explain", json=payload)).status_code, 422)
        self.assertEqual(self.gateway.seen, [])

if __name__ == "__main__":
    unittest.main(verbosity=2)
