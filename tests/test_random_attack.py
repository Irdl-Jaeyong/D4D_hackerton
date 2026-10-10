import sys,time,json,random,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
from app import main as api
from auto_scenarios import ScenarioGenerator
from defense_scenarios import DEFENSE_SCENARIOS
from fastapi import HTTPException
class RandomAttack(unittest.IsolatedAsyncioTestCase):
 def setUp(self):
  self.previous=(api.auto_generator,dict(api.latest),dict(api.missions),api.mission,api.mission_counter,api.camera_view)
  api.latest.clear();api.missions.clear();api.mission=None
  for kind,count in [('SHIP',1),('UAV',8),('USV',6)]:
   for i in range(1,count+1):api.latest[f'{kind}-{i:02}']={'x':0,'y':0,'z':80 if kind=='UAV' else .7,'sim_time':0,'received_at':time.time()}
  config=json.loads((api.ROOT/'config/auto_scenarios.json').read_text());config['scenarios']=[k for k in DEFENSE_SCENARIOS if k!='communication_interference']
  api.auto_generator=ScenarioGenerator(config,random.Random(1),now=time.monotonic())
 def tearDown(self):
  api.auto_generator,latest,missions,api.mission,api.mission_counter,api.camera_view=self.previous
  api.latest.clear();api.latest.update(latest);api.missions.clear();api.missions.update(missions)
 async def test_button_generates_immediately_without_waiting_and_has_three_responses(self):
  next_at=api.auto_generator.next_at
  item=await api.random_attack()
  self.assertIn(item['scenario'],DEFENSE_SCENARIOS);self.assertEqual(len(item['options']),3)
  self.assertIsNone(item['approved']);self.assertTrue(item['manual_generated'])
  self.assertGreater(api.auto_generator.next_at,next_at)
 async def test_four_pending_cap_and_no_duplicate_scenarios(self):
  items=[await api.random_attack() for _ in range(4)]
  self.assertEqual(len({m['scenario'] for m in items}),4)
  with self.assertRaises(HTTPException) as error:await api.random_attack()
  self.assertEqual(error.exception.status_code,409);self.assertEqual(len(api.missions),4)
 async def test_missing_ship_rejected_without_creating_scene(self):
  api.latest.pop('SHIP-01')
  with self.assertRaises(HTTPException) as error:await api.random_attack()
  self.assertEqual(error.exception.status_code,409);self.assertFalse(api.missions)
