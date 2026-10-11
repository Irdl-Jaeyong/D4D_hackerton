import sys,time,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
from app import main as api
from fastapi import HTTPException
class FaultAPI(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        api.latest.clear();api.simulated_faults.clear();api.automatic_returns.clear();api.fault_kinds.clear();api.fault_status.clear();api.charge_credit.clear();api.battery_origin.clear();api.mission=None;api.missions.clear()
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
    async def test_first_person_ignores_frames_from_previous_vehicle_or_revision(self):
        import base64
        previous=(api.camera_view,api.inspection_vehicle,api.camera_revision,api.camera,api.camera_ready)
        try:
            old=await api.set_camera_view(api.CameraView(mode='inspect',vehicle_id='UAV-01'))
            new=await api.set_camera_view(api.CameraView(mode='inspect',vehicle_id='UAV-02'))
            frame=dict(vehicle_id='SHIP-01',x=0,y=0,z=0,yaw=0,speed=0,sim_time=0,camera_jpeg=base64.b64encode(b'\xff\xd8test').decode(),camera_mode='inspect')
            await api.telemetry(api.Telemetry(**frame,camera_revision=old['revision'],camera_vehicle_id='UAV-01'),x_bridge_token='test-only')
            self.assertIsNone(api.camera)
            await api.telemetry(api.Telemetry(**frame,camera_revision=new['revision'],camera_vehicle_id='UAV-01'),x_bridge_token='test-only')
            self.assertIsNone(api.camera)
            await api.telemetry(api.Telemetry(**frame,camera_revision=new['revision'],camera_vehicle_id='UAV-02'),x_bridge_token='test-only')
            self.assertIsNone(api.camera)
            with self.assertRaises(HTTPException):
                await api.camera_applied(api.CameraReady(revision=old['revision'],vehicle_id='UAV-01',sim_time=5),x_bridge_token='test-only')
            await api.camera_applied(api.CameraReady(revision=new['revision'],vehicle_id='UAV-02',sim_time=5),x_bridge_token='test-only')
            await api.telemetry(api.Telemetry(**frame,camera_revision=new['revision'],camera_vehicle_id='UAV-02',camera_capture_sim_time=5),x_bridge_token='test-only')
            self.assertIsNone(api.camera)
            await api.telemetry(api.Telemetry(**frame,camera_revision=new['revision'],camera_vehicle_id='UAV-02',camera_capture_sim_time=6),x_bridge_token='test-only')
            self.assertEqual(api.camera['jpeg'],b'\xff\xd8test')
        finally:api.camera_view,api.inspection_vehicle,api.camera_revision,api.camera,api.camera_ready=previous

    async def test_fault_cannot_be_released_in_air(self):
        await api.set_simulated_fault('UAV-01',api.FaultRequest(unavailable=True))
        with self.assertRaises(HTTPException):await api.set_simulated_fault('UAV-01',api.FaultRequest(unavailable=False))
        api.fault_status['UAV-01']={'phase':'charging'}
        await api.set_simulated_fault('UAV-01',api.FaultRequest(unavailable=False))
        self.assertNotIn('UAV-01',api.simulated_faults)
    async def test_airborne_fault_is_red_but_keeps_return_phase(self):
        api.simulated_faults.add('UAV-01');api.fault_status['UAV-01']={'phase':'returning'}
        v=next(v for v in api.state()['vehicles'] if v['id']=='UAV-01')
        self.assertEqual(v['readiness']['operational_state'],'unavailable')
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
        self.assertEqual(len(m['options']),2)
        self.assertIsNone(m['approved'])
        self.assertTrue(all(t['vehicle']!='UAV-01' for p in m['options'] for t in p['tasks']))
        with self.assertRaises(HTTPException):await api.approve_plan(api.ApprovalRequest(mission_id=m['id'],option_id='observe'))
        api.simulated_faults.clear()
        with self.assertRaises(HTTPException):await api.risk_plan('UAV-01:fault')
    async def test_low_battery_return_resumes_after_measured_deck_charge(self):
        api.latest['UAV-01'].update(x=-74,y=-6,z=3.45,sim_time=2000)
        api.state()
        self.assertIn('UAV-01',api.simulated_faults)
        api.charge_credit['UAV-01']=80
        await api.report_faults(api.FaultReport(tasks={'UAV-01':{'phase':'charging','sim_time':2000}}),x_bridge_token='test-only')
        self.assertNotIn('UAV-01',api.simulated_faults)
        v=next(v for v in api.state()['vehicles'] if v['id']=='UAV-01')
        self.assertTrue(v['readiness']['available']);self.assertEqual(v['readiness']['battery_percent'],80)
    async def test_explicit_payload_fault_stays_faulted_after_full_charge(self):
        await api.set_simulated_fault('UAV-02',api.FaultRequest(unavailable=True,fault_type='payload'))
        api.latest['UAV-02'].update(x=-71.3,y=-6,z=3.45,sim_time=2000)
        api.charge_credit['UAV-02']=100
        await api.report_faults(api.FaultReport(tasks={'UAV-02':{'phase':'charging','sim_time':2000}}),x_bridge_token='test-only')
        self.assertIn('UAV-02',api.simulated_faults)
