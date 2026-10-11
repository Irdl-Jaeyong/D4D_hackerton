import sys,json,copy,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from llm_dialogue import generate
class MockResponse:
 def raise_for_status(self):pass
 def json(self):return {'message':{'content':json.dumps({'explanation':'현재는 담당 위치에서 대기 중입니다.','answers':[]},ensure_ascii=False)}}
class Client:
 captured=None
 def __init__(self,**kw):pass
 async def __aenter__(self):return self
 async def __aexit__(self,*args):pass
 async def post(self,url,json):Client.captured=json;return MockResponse()
class GenerationTests(unittest.IsolatedAsyncioTestCase):
 async def test_reads_evidence_without_mutation(self):
  v={'id':'UAV-01','connected':True,'status_briefing':{'title':'담당 위치 유지 · 대기·복귀','evidence':'현재 판정: 배정 가능'},'readiness':{}}
  snapshot={'vehicles':[v]};baseline={'reply':'근거 요약','recommendations':[],'answer_type':'fault_explanation','evidence':[{'vehicle':'UAV-01','reason':'배정 가능'}],'executed':False}
  before=copy.deepcopy(snapshot)
  with patch('llm_dialogue.httpx.AsyncClient',Client):r=await generate('뭐하고 있어?',snapshot,baseline,'http://localhost:11434','test-model')
  self.assertTrue(r['llm_used']);self.assertFalse(r['executed']);self.assertIn('UAV-01',r['reply']);self.assertEqual(snapshot,before);self.assertNotIn('tools',Client.captured);self.assertEqual(Client.captured['stream'],False)
if __name__=='__main__':unittest.main()
