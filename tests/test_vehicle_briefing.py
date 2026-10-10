import sys,unittest,copy
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from vehicle_briefing import brief
from safety_chat import answer
class StateCoverageTests(unittest.TestCase):
 def vehicle(self,id,state='waiting'):
  return {'id':id,'type':id.split('-')[0],'connected':True,'age_seconds':.1,'telemetry':{'x':0,'y':0,'z':30,'roll':0,'pitch':0},'readiness':{'available':state!='unavailable','operational_state':state,'reason':'배정 가능','task':'담당 위치 유지','battery_percent':80,'endurance_minutes':25}}
 def test_all_ids_all_three_states(self):
  ids=['SHIP-01']+[f'USV-{i:02}' for i in range(1,11)]+[f'UAV-{i:02}' for i in range(1,41)]
  for id in ids:
   for state,label in [('defending','방어중'),('waiting','대기·복귀'),('unavailable','수행불가')]:
    with self.subTest(id=id,state=state):
     v=self.vehicle(id,state);self.assertEqual(brief(v)['label'],label)
     # SHIP status API applies the same summary; chat targeting is UAV/USV.
     if not id.startswith('SHIP'):
      a=answer(id+' 왜 이 상태야?',{'vehicles':[v]});self.assertEqual(a['recommendations'],[]);self.assertIn(label,a['reply'])
 def test_risks_are_readonly(self):
  for kind in ['link','fault','battery','unstable','separation']:
   with self.subTest(kind=kind):
    v=self.vehicle('UAV-01');other=self.vehicle('UAV-02');other['telemetry']['x']=20
    if kind=='link':v['connected']=False;v['age_seconds']=10
    if kind=='fault':v['fault']={'phase':'charging'};v['fault_type']='payload'
    if kind=='battery':v['readiness']['battery_percent']=20
    if kind=='unstable':v['telemetry']['roll']=.4
    if kind=='separation':other['telemetry']['x']=2
    snap={'vehicles':[v,other]};before=copy.deepcopy(snap);a=answer('지금 위험에 어떻게 대응해?',snap)
    self.assertEqual(len(a['recommendations']),3);self.assertFalse(a['executed']);self.assertEqual(snap,before)
 def test_unobserved_danger_not_invented(self):
  a=answer('지금 위험에 어떻게 대응해?',{'vehicles':[self.vehicle('UAV-01')]});self.assertEqual(a['recommendations'],[]);self.assertTrue(a['clarification_questions'])
if __name__=='__main__':unittest.main()
