import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from safety_chat import answer
class FiveIntentsTests(unittest.TestCase):
 def setUp(self):self.s={'vehicles':[{'id':'UAV-01','type':'UAV','connected':True,'age_seconds':.1,'telemetry':{'x':0,'y':0,'z':30},'fault':{'phase':'charging'},'fault_type':'payload','readiness':{'operational_state':'unavailable','task':'충전·정비 중','reason':'임무 장비 고장','available':False,'battery_percent':100}}]}
 def test_five_routes(self):
  for q,k,n in [('UAV-01 지금 뭐 하고 있어','status',0),('UAV-01 왜 수행불가야','reason',0),('현재 위험 확인해줘','risk',0),('현재 위험에 어떻게 대응해','response',3),('UAV-01 언제 다시 가능해','resume',0)]:
   with self.subTest(q=q):
    a=answer(q,self.s);self.assertEqual(a['question_intent'],k);self.assertEqual(len(a['recommendations']),n);self.assertFalse(a['executed'])
 def test_resume_clarifies_target(self):
  a=answer('언제 다시 가능해',self.s);self.assertTrue(a['clarification_questions']);b=answer('UAV-01',self.s,a['clarification_context']);self.assertEqual(b['question_intent'],'resume');self.assertFalse(b['clarification_questions'])
 def test_risk_not_three_actions(self):self.assertNotIn('1.',answer('뭐가 위험해',self.s)['reply'])
 def test_recovery_not_guaranteed(self):self.assertIn('확정할 수 없어요',answer('UAV-01 재개 조건 알려줘',self.s)['reply'])
if __name__=='__main__':unittest.main()
