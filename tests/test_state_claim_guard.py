import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from state_claim_guard import check
class ClaimTests(unittest.TestCase):
 def test_normal_rejects_invented(self):
  for text in ['현재 정비 중이에요','충전 중이에요','고장으로 등록됐어요','즉시 재개 가능해요']:
   with self.subTest(text=text),self.assertRaises(ValueError):check(text,[{'readiness':{'operational_state':'waiting','reason':'배정 가능'}}])
 def test_recorded_fault(self):check('현재 정비 중이에요',[{'fault':{'phase':'charging'},'readiness':{'task':'충전·정비 중','reason':'고장'}}])
 def test_unknown_vehicle(self):
  with self.assertRaises(ValueError):check('고장으로 등록됐어요',[])
 def test_transition(self):
  v={'readiness':{'task':'담당 위치 유지'}}
  with self.assertRaises(ValueError):check('충전 중이에요',[v])
  v['readiness']['task']='충전 중';check('충전 중이에요',[v])
  v['readiness']['task']='담당 위치 유지'
  with self.assertRaises(ValueError):check('충전 중이에요',[v])
if __name__=='__main__':unittest.main()
