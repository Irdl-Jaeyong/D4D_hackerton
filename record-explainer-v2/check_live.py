"""Run against local Ollama via application API; no browser involved."""
import json
import time
from pathlib import Path
import asyncio
import httpx
from app import create_app

async def main():
    client = httpx.AsyncClient(transport=httpx.ASGITransport(app=create_app()),base_url="http://testserver",trust_env=False)
    cases = [("TEST-A-001","이 기록에 나온 상태와 해결 여부를 설명해주세요."),
             ("TEST-B-001","이 기록만으로 정상인지 알 수 있나요?"),
             ("TEST-C-001","읽음 표시를 했으니 해결된 건가요?"),
             ("TEST-B-001","이 기록만으로 정상인지 알 수 있나요?")]
    await client.post("/api/records/TEST-C-001/read")
    before=(await client.get("/api/records")).json()
    results=[]
    for record_id, question in cases:
        start=time.monotonic()
        response=await client.post("/api/explain",json={"record_id":record_id,"question":question})
        item={"record_id":record_id,"question":question,"status":response.status_code,
              "seconds":round(time.monotonic()-start,3),"body":response.json()}
        print(json.dumps(item,ensure_ascii=False),flush=True)
        results.append(item)
        assert response.status_code==200,item
        assert item["body"]["evidence"]["record_id"]==record_id
    assert before==(await client.get("/api/records")).json(),"Explanation mutated record view"
    Path(__file__).with_name("live-results.json").write_text(json.dumps(results,ensure_ascii=False,indent=2))

asyncio.run(main())
