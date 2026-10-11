import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from operator_next_steps import attach,render
class NextStepTests(unittest.TestCase):
 def test_link(self):
  a=render(attach({'reply':'설명'},'UAV-01',{'vehicles':[{'id':'UAV-01','connected':False}]}));self.assertIn('마지막 수신',a['reply']);self.assertFalse(a['next_steps']['automatic_execution'])
 def test_missing(self):
  a=attach({'reply':'설명','clarification_questions':['어느 기체인가요?']},'',{'vehicles':[]});self.assertIn('어느 기체',a['next_steps']['now'])
 def test_queue_no_tactics(self):
  a=attach({'queue_reference':{'mission_id':1}},'',{'vehicles':[],'approval_queue':[]});self.assertIn('관측 기록',a['next_steps']['now'])
if __name__=='__main__':unittest.main()
