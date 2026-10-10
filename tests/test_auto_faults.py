import sys,time,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
from app import main as api
class AutoFaults(unittest.IsolatedAsyncioTestCase):
 def setUp(self):
  api.missions.clear();api.mission=None;api.simulated_faults.clear();api.latest.clear();api.mission_counter=0
  for id in ['SHIP-01','UAV-01','UAV-02','USV-01']:api.latest[id]={'x':0,'y':0,'z':20,'sim_time':0,'received_at':time.time()}
 async def test_fault_event_applies_and_cancel_recovers(self):
  m=await api.start_scenario(api.ScenarioRequest(scenario='fault',vehicle_id='UAV-01'))
  v=next(v for v in api.state()['vehicles'] if v['id']=='UAV-01')
  self.assertEqual(v['readiness']['operational_state'],'unavailable')
  self.assertIn('UAV-01',(await api.get_formations())['simulated_faults'])
  await api.cancel_plan(api.CancelRequest(mission_id=m['id']))
  self.assertNotIn('UAV-01',(await api.get_formations())['simulated_faults'])
 async def test_duplicate_fault_events_do_not_prematurely_recover(self):
  a=await api.start_scenario(api.ScenarioRequest(scenario='fault',vehicle_id='USV-01'))
  b=await api.start_scenario(api.ScenarioRequest(scenario='fault',vehicle_id='USV-01'))
  await api.cancel_plan(api.CancelRequest(mission_id=a['id']))
  self.assertIn('USV-01',(await api.get_formations())['simulated_faults'])
  await api.cancel_plan(api.CancelRequest(mission_id=b['id']))
  self.assertNotIn('USV-01',(await api.get_formations())['simulated_faults'])
