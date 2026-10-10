import sys,time,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
from app import main as api
class UpgradeAPI(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        api.mission=None;api.latest.clear();api.simulated_faults.clear();api.fault_status.clear()
        if hasattr(api,'fault_kinds'):api.fault_kinds.clear();api.fault_last_known.clear()
        for name in ['SHIP-01','UAV-01','USV-01']:
            api.latest[name]={'x':10,'y':0,'z':60 if name.startswith('UAV') else 0,'yaw':0,'sim_time':10,'received_at':time.time()}
    async def test_scenario_returns_to_fleet_camera(self):
        previous=api.camera_view
        try:
            api.camera_view='inspect'
            await api.start_scenario(api.ScenarioRequest(scenario='rescue'))
            self.assertEqual(api.camera_view,'wide')
        finally:api.camera_view=previous
    async def test_scenario_has_world_object_and_stays_fixed_for_debris(self):
        m=await api.start_scenario(api.ScenarioRequest(scenario='debris'))
        first=api.state()['scene'].get('situations',[])
        self.assertEqual(len(first),1)
        api.latest['SHIP-01'].update(x=100,sim_time=20)
        self.assertEqual(api.state()['scene']['situations'][0]['x'],first[0]['x'])
        await api.cancel_plan();self.assertEqual(api.state()['scene']['situations'],[])
    async def test_propulsion_fault_is_automatic_and_red_without_replacing_mission(self):
        m=await api.start_scenario(api.ScenarioRequest(scenario='crossing'))
        await api.start_scenario(api.ScenarioRequest(scenario='fault',vehicle_id='UAV-01',fault_type='propulsion'))
        self.assertEqual(api.mission['id'],m['id'])
        s=await api.get_formations();self.assertEqual(s['fault_modes']['UAV-01'],'propulsion')
        v=next(v for v in api.state()['vehicles'] if v['id']=='UAV-01')
        self.assertEqual(v['readiness']['operational_state'],'unavailable')
    async def test_communication_uses_last_known_and_excludes_task_assignment(self):
        await api.start_scenario(api.ScenarioRequest(scenario='fault',vehicle_id='UAV-01',fault_type='communication'))
        api.latest['UAV-01']['x']=80
        v=next(v for v in api.state()['vehicles'] if v['id']=='UAV-01')
        self.assertFalse(v['connected']);self.assertEqual(v['telemetry']['x'],10)
        self.assertEqual(v['simulation_pose']['x'],80)
        self.assertFalse((await api.get_formations())['availability']['UAV-01'])
    async def test_link_restoration_and_water_recovery_have_separate_guards(self):
        await api.set_simulated_fault('UAV-01',api.FaultRequest(unavailable=True,fault_type='communication'))
        await api.set_simulated_fault('UAV-01',api.FaultRequest(unavailable=False))
        self.assertNotIn('UAV-01',api.simulated_faults)
        await api.set_simulated_fault('UAV-01',api.FaultRequest(unavailable=True,fault_type='propulsion'))
        from fastapi import HTTPException
        with self.assertRaises(HTTPException):await api.set_simulated_fault('UAV-01',api.FaultRequest(unavailable=False))
        api.latest['UAV-01']['z']=.6;api.fault_status['UAV-01']={'phase':'ditched'}
        await api.set_simulated_fault('UAV-01',api.FaultRequest(unavailable=False))
        self.assertNotIn('UAV-01',api.simulated_faults)
class TypedMotion(unittest.TestCase):
    def test_moving_target_does_not_complete_observation_at_old_position(self):
        from mission_execution import ObservationRun
        m={'id':1,'card':{'offset':[100,0]},'approved':{'tasks':[{'vehicle':'UAV-01'}]}}
        run=ObservationRun(m,0,0);homes={'UAV-01':(0,0,60)}
        run.step(0,0,homes,{'UAV-01':(0,(100,0,60))},{'UAV-01':True})
        goal=run.step(6,0,homes,{'UAV-01':(6,(100,0,60))},{'UAV-01':True},target_world=[120,8])
        self.assertEqual(run.tasks['UAV-01']['stage'],'outbound')
        self.assertEqual(goal['UAV-01'],(120,8,60))

    def test_propulsion_failure_descends_and_inspection_tracks_actual_pose(self):
        from typed_fault_motion import FaultMotion
        from convoy_motion import poses
        f=FaultMotion()
        a=poses(0,typed_motion=f,fault_modes={})
        b=poses(.2,typed_motion=f,fault_modes={'UAV-01':'propulsion'},inspection={'id':'UAV-01'})
        self.assertLess(f.last['UAV-01']['z'],60) # starting ring is about 39m
        import re
        z0=float(re.search(r'name:"UAV-01".*?z:([-.0-9]+)',a).group(1))
        z1=float(re.search(r'name:"UAV-01".*?z:([-.0-9]+)',b).group(1))
        self.assertLess(z1,z0)
