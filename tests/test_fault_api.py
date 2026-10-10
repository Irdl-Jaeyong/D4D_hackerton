import sys,time,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
from app import main as api
from fastapi import HTTPException
class FaultAPI(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        api.latest.clear();api.simulated_faults.clear();api.fault_status.clear();api.charge_credit.clear();api.battery_origin.clear();api.mission=None
        self.token=api.TOKEN;api.TOKEN='test-only'
        for id in ['SHIP-01','UAV-01','UAV-02','USV-01']:
            api.latest[id]={'x':0,'y':0,'z':80 if id.startswith('UAV') else 0,'sim_time':0,'received_at':time.time()}
    def tearDown(self):api.TOKEN=self.token
    async def test_inspection_requires_fresh_known_vehicle_and_does_not_change_formation(self):
        revision=api.formation['revision'];previous=api.camera_view
        try:
            with self.assertRaises(HTTPException):await api.set_camera_view(api.CameraView(mode='inspect',vehicle_id='UAV-99'))
            await api.set_camera_view(api.CameraView(mode='inspect',vehicle_id='UAV-02'))
            self.assertEqual(api.inspection_vehicle,'UAV-02')
            self.assertEqual(api.formation['revision'],revision)
        finally:api.camera_view=previous
    async def test_fault_cannot_be_released_in_air(self):
        await api.set_simulated_fault('UAV-01',api.FaultRequest(unavailable=True))
        with self.assertRaises(HTTPException):await api.set_simulated_fault('UAV-01',api.FaultRequest(unavailable=False))
        api.fault_status['UAV-01']={'phase':'charging'}
        await api.set_simulated_fault('UAV-01',api.FaultRequest(unavailable=False))
        self.assertNotIn('UAV-01',api.simulated_faults)
    async def test_airborne_emergency_return_is_not_labelled_parked_unavailable(self):
        api.simulated_faults.add('UAV-01');api.fault_status['UAV-01']={'phase':'returning'}
        v=next(v for v in api.state()['vehicles'] if v['id']=='UAV-01')
        self.assertEqual(v['readiness']['operational_state'],'waiting')
        self.assertFalse(v['readiness']['available'])
        self.assertIn('비상 복귀',v['readiness']['task'])
        api.fault_status['UAV-01']={'phase':'charging'}
        v=next(v for v in api.state()['vehicles'] if v['id']=='UAV-01')
        self.assertEqual(v['readiness']['operational_state'],'unavailable')
    async def test_charging_increases_energy_but_does_not_release_fault(self):
        api.simulated_faults.add('UAV-01')
        api.latest['UAV-01'].update(x=-74,y=-6,z=3.45)
        for stamp in [0,1]:await api.report_faults(api.FaultReport(tasks={'UAV-01':{'phase':'charging','sim_time':stamp}}),x_bridge_token='test-only')
        self.assertAlmostEqual(api.charge_credit['UAV-01'],.2)
        vehicle=next(v for v in api.state()['vehicles'] if v['id']=='UAV-01')
        self.assertFalse(vehicle['readiness']['available'])
        self.assertIn('충전',vehicle['readiness']['task'])
    async def test_charging_cannot_be_reported_while_still_airborne(self):
        api.simulated_faults.add('UAV-01')
        await api.report_faults(api.FaultReport(tasks={'UAV-01':{'phase':'charging','sim_time':1}}),x_bridge_token='test-only')
        self.assertEqual(api.fault_status['UAV-01']['phase'],'landing')
        self.assertNotIn('UAV-01',api.charge_credit)
    async def test_risk_recommendations_exclude_faulted_vehicle_and_need_human_approval(self):
        api.simulated_faults.add('UAV-01')
        m=await api.risk_plan('UAV-01:fault')
        self.assertEqual(len(m['options']),3)
        self.assertIsNone(m['approved'])
        self.assertTrue(all(t['vehicle']!='UAV-01' for p in m['options'] for t in p['tasks']))
        with self.assertRaises(HTTPException):await api.approve_plan(api.ApprovalRequest(mission_id=m['id'],option_id='observe'))
        api.simulated_faults.clear()
        with self.assertRaises(HTTPException):await api.risk_plan('UAV-01:fault')
