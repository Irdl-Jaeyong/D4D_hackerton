import math,sys,unittest,xml.etree.ElementTree as ET
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from scenario_scene import targets,model_sdf
from mission_console import options,readiness
from mission_execution import ObservationRun
from defense_scenarios import DEFENSE_SCENARIOS,DEFENSE_RESPONSES,defense_goal,formation_goals

def vehicle(id):
 v={'id':id,'type':id.split('-')[0],'connected':True,'telemetry':{'x':0,'y':0,'z':80 if id.startswith('UAV') else .7}}
 v['readiness']=readiness(v);return v
class DefenseScenarios(unittest.TestCase):
 def mission(self,kind):return {'id':10,'scenario':kind,'scene_origin':{'x':0,'y':0,'yaw':0,'sim_time':0},'risk':{'priority':'P1'}}
 def test_four_directional_situations_with_continuous_safe_approach(self):
  for kind in DEFENSE_SCENARIOS:
   start=targets([self.mission(kind)],0);later=targets([self.mission(kind)],20)
   self.assertEqual(len(start),len(DEFENSE_SCENARIOS[kind]['bearing_degrees']))
   for a,b in zip(start,later):
    self.assertLess(math.hypot(b['x']-30,b['y']),math.hypot(a['x'],a['y']))
    self.assertGreater(math.hypot(b['x']-30,b['y']),160)
   for p in targets([self.mission(kind)],300):self.assertGreater(math.hypot(p['x']-450,p['y']),160)
  self.assertLess(targets([self.mission('rear_approach')],0)[0]['x'],0)
  both=targets([self.mission('multi_approach')],0);self.assertLess(both[0]['y']*both[1]['y'],0)
 def test_no_large_marker_or_flag_and_mesh_boat_used(self):
  for p in targets([self.mission('fast_approach')],0):
   xml=ET.fromstring(model_sdf(p));self.assertIsNotNone(xml.find('.//mesh'))
   self.assertFalse(any(v.attrib['name'].startswith('marker') or 'flag' in v.attrib['name'] for v in xml.findall('.//visual')))
 def test_all_options_use_unique_drones_and_usvs_with_directional_formations(self):
  fleet=[vehicle('SHIP-01')]+[vehicle(f'{kind}-{i:02}') for kind in ['UAV','USV'] for i in range(1,9)]
  for kind in DEFENSE_SCENARIOS:
   plans=options(fleet,{'usv':'circle','uav':'hemisphere'},kind)
   self.assertTrue(all(p['available'] for p in plans))
   for p in plans:
    ids=[t['vehicle'] for t in p['tasks']];self.assertEqual(len(ids),len(set(ids)))
    self.assertTrue(any(id.startswith('UAV') for id in ids));self.assertTrue(any(id.startswith('USV') for id in ids))
   self.assertEqual(plans[1]['formations'],DEFENSE_RESPONSES[kind][1]['formations'])
 def test_missing_live_ship_has_no_invented_recommendation(self):
  from mission_console import defense_options
  self.assertEqual(defense_options([vehicle('UAV-01')],{'usv':'circle','uav':'hemisphere'},'fast_approach'),[])
 def test_screen_between_contact_and_ship_and_track_at_standoff(self):
  ship=(0,0);contact=(250,80)
  sea=defense_goal('USV',ship,contact,0);air=defense_goal('UAV',ship,contact,0)
  self.assertGreater(math.hypot(*sea[:2]),100);self.assertLess(math.hypot(*sea[:2]),math.hypot(*contact))
  self.assertGreater(air[2],60);self.assertGreater(math.dist(air[:2],contact),20)
 def test_rear_drone_v_points_rearward(self):
  points=[(80,10,85),(40,-30,85)]
  oriented=formation_goals('uav','v',points,'rear_approach')
  self.assertTrue(all(p[0]<0 for p in oriented))
 def test_tracking_and_screening_persist_until_operator_cancel(self):
  m=self.mission('fast_approach');m['card']={'offset':[250,0]};m['threats']=targets([m],0)
  m['approved']={'tasks':[{'vehicle':'UAV-01','role':'track','contact_index':0,'role_slot':0},{'vehicle':'USV-01','role':'screen','contact_index':0,'role_slot':0}]}
  r=ObservationRun(m,0,0);homes={'UAV-01':(0,0,80),'USV-01':(0,100,.7)};available={id:True for id in homes}
  for t in [0,10,30]:
   goals=r.step(t,1.5*t,homes,{id:(t,task['target']) for id,task in r.tasks.items()},available,contacts=targets([m],t))
   self.assertEqual(set(goals),set(homes));self.assertFalse(any(task['stage']=='returning' for task in r.tasks.values()))
  r.step(31,46.5,homes,{id:(31,task['target']) for id,task in r.tasks.items()},available,cancel=True)
  self.assertTrue(all(task['stage']=='returning' for task in r.tasks.values()))

class ExtraDefenseContacts(unittest.TestCase):
 def mission(self,kind):return {'id':20,'scenario':kind,'scene_origin':{'x':0,'y':0,'yaw':0,'sim_time':0},'risk':{'priority':'P1'}}
 def test_air_and_combined_contacts_have_correct_domains_and_altitudes(self):
  air=targets([self.mission('air_intrusion')],10);self.assertEqual(air[0]['contact_type'],'air');self.assertGreater(air[0]['z'],80)
  mixed=targets([self.mission('combined_intrusion')],10);self.assertEqual([t['contact_type'] for t in mixed],['air','surface'])
  self.assertGreater(mixed[0]['z'],80);self.assertLess(mixed[1]['z'],1)
 def test_new_domains_render_distinct_models_not_boat_hulls(self):
  for scenario,visual in [('air_intrusion','airframe'),('suspicious_float','floating_crate'),('communication_interference','zone_0'),('underwater_contact','submerged_body')]:
   t=targets([self.mission(scenario)],0)[0];xml=ET.fromstring(model_sdf(t))
   self.assertIsNotNone(xml.find(f'.//visual[@name="{visual}"]'))
 def test_air_observers_keep_vertical_separation(self):
  air=defense_goal('UAV',(0,0),(250,0),0,'air');self.assertGreater(air[2],120)
