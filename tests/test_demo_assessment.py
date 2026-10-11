import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from demo_assessment import evaluate
class DemoAssessment(unittest.TestCase):
    def setUp(self):
        self.item={'scene_origin':{'sim_time':10},'approved':{'tasks':[{'vehicle':'UAV-01'},{'vehicle':'USV-01'}]},'execution':{'tasks':{'UAV-01':{'stage':'tracking','blocked':False},'USV-01':{'stage':'screening','blocked':False}}}}
        self.vehicles=[{'id':id,'connected':True,'telemetry':{'sim_time':42}} for id in ('UAV-01','USV-01')]
    def test_success_uses_observed_state_after_window(self):
        r=evaluate(self.item,self.vehicles,42)
        self.assertEqual(r['result'],'임무 유지 성공');self.assertEqual(r['virtual_state'],68)
        self.assertEqual(r['source'],'demo_rules');self.assertEqual(r['maintained'],2)
    def test_partial_and_failure(self):
        self.vehicles[0]['fault']={'phase':'returning'}
        self.assertEqual(evaluate(self.item,self.vehicles,42)['result'],'일부 중단')
        self.vehicles[1]['connected']=False
        self.assertEqual(evaluate(self.item,self.vehicles,42)['result'],'임무 유지 실패')
    def test_missing_data_is_not_success(self):
        del self.item['execution']['tasks']['UAV-01']
        r=evaluate(self.item,self.vehicles,42)
        self.assertEqual(r['result'],'평가 불가');self.assertTrue(r['missing'])
        self.assertEqual(evaluate(self.item,self.vehicles,None)['result'],'평가 불가')
    def test_event_count_is_independent_of_polling_and_response_choice(self):
        self.assertEqual(evaluate(self.item,self.vehicles,17)['virtual_state'],100)
        self.assertEqual(evaluate(self.item,self.vehicles,18)['virtual_state'],92)
        self.assertEqual(evaluate(self.item,self.vehicles,1000)['virtual_state'],68)
        self.assertEqual(evaluate(self.item,self.vehicles,42),evaluate(self.item,self.vehicles,42))
    def test_waiting_and_return_completion(self):
        self.assertEqual(evaluate(self.item,self.vehicles,12)['result'],'평가 진행 중')
        self.item['execution']['tasks']['UAV-01']['stage']='completed'
        self.assertEqual(evaluate(self.item,self.vehicles,42)['result'],'임무 유지 성공')
        self.item.pop('approved')
        self.assertEqual(evaluate(self.item,self.vehicles,42)['result'],'임무 유지 실패')
