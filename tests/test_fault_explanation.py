import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from safety_chat import answer
class FaultExplanationTests(unittest.TestCase):
 def vehicle(self,id='UAV-01',**extra):
  return {'id':id,'connected':True,'readiness':{'available':False,'operational_state':'unavailable','reason':'추진 고장','battery_percent':60},'fault':{'phase':'pending'},'fault_type':'propulsion',**extra}
 def test_single_fault_inferred(self):
  a=answer('왜 고장이야?',{'vehicles':[self.vehicle()]});self.assertEqual(len(a['evidence']),1);self.assertEqual(a['recommendations'],[]);self.assertIn('진단한 것은 아닙니다',a['reply'])
 def test_multiple_ask(self):
  a=answer('왜 고장?',{'vehicles':[self.vehicle(),self.vehicle('UAV-02')]});self.assertTrue(a['clarification_questions']);self.assertEqual(a['evidence'],[])
  b=answer('UAV-02',{'vehicles':[self.vehicle(),self.vehicle('UAV-02')]},a['clarification_context']);self.assertEqual(b['evidence'][0]['vehicle'],'UAV-02')
 def test_normal_not_fault(self):
  a=answer('UAV-01 왜 수행불가야?',{'vehicles':[self.vehicle(fault=None,readiness={'available':False,'operational_state':'waiting','reason':'임무 수행 중'})]});self.assertIn('수행불가로 판정되어 있지 않습니다',a['reply'])
 def test_unknown(self):self.assertTrue(answer('UAV-99 왜?',{'vehicles':[]})['clarification_questions'])
if __name__=='__main__':unittest.main()
