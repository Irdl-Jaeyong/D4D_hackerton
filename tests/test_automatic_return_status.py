"""Automatic recovery is not a payload failure, and old epochs cannot latch it."""
import sys,time,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
from app import main as api
from vehicle_briefing import brief
from fault_explanation import explain
from risk_monitor import assess

class AutomaticReturnStatus(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        api.reset_demo_session();api.latest.clear();api.TOKEN='auto-test'
        for name in ('SHIP-01','UAV-01','UAV-02'):
            api.latest[name]={'x':0,'y':0,'z':60 if name.startswith('UAV') else 0,'yaw':0,'roll':0,'pitch':0,'sim_time':0,'received_at':time.time()}
        if hasattr(api,'last_sim_times'):api.last_sim_times.clear()
    def tearDown(self):api.TOKEN=''
    def vehicle(self):return next(v for v in api.state()['vehicles'] if v['id']=='UAV-01')
    async def test_low_battery_is_auto_return_not_equipment_failure(self):
        api.latest['UAV-01']['sim_time']=2000
        v=self.vehicle()
        self.assertTrue(v['automatic_return']);self.assertEqual(v['fault_type'],'automatic_return')
        self.assertEqual(v['return_reason'],'battery');self.assertEqual(v['readiness']['operational_state'],'waiting')
        self.assertFalse(v['readiness']['available']);self.assertIn('배터리',v['readiness']['reason'])
        self.assertNotIn('장비',brief(v)['title']);self.assertIn('자동 복귀',brief(v)['title'])
        answer=explain('UAV-01 왜 복귀해?',{'vehicles':[v]})
        self.assertNotIn('시뮬레이션 고장 상태 등록',answer['reply'])
        self.assertFalse(any(r['kind']=='fault' for r in assess([v])))
    async def test_tilt_is_still_unavailable_but_explained_as_automatic_recovery(self):
        api.latest['UAV-01']['roll']=.3
        v=self.vehicle();self.assertTrue(v['automatic_return']);self.assertEqual(v['return_reason'],'attitude')
        self.assertEqual(v['readiness']['operational_state'],'unavailable')
        api.latest['UAV-01']['roll']=0;api.fault_status['UAV-01']={'phase':'returning'}
        self.assertEqual(self.vehicle()['readiness']['operational_state'],'waiting')
    async def test_new_simulation_epoch_clears_auto_return_only(self):
        api.simulated_faults.add('UAV-01');api.automatic_returns.add('UAV-01');api.fault_status['UAV-01']={'phase':'landing','sim_time':100}
        api.last_sim_times['UAV-01']=100;api.charge_credit['UAV-01']=7
        await api.set_simulated_fault('UAV-02',api.FaultRequest(unavailable=True,fault_type='payload'))
        api.last_sim_times['UAV-02']=100
        for name in ('UAV-01','UAV-02'):
            await api.telemetry(api.Telemetry(vehicle_id=name,x=0,y=0,z=60,yaw=0,speed=0,sim_time=1),x_bridge_token='auto-test')
        self.assertNotIn('UAV-01',api.simulated_faults);self.assertNotIn('UAV-01',api.automatic_returns)
        self.assertNotIn('UAV-01',api.fault_status);self.assertNotIn('UAV-01',api.charge_credit)
        self.assertIn('UAV-02',api.simulated_faults);self.assertEqual(api.fault_kinds['UAV-02'],'payload')
    async def test_restore_clock_baseline_can_clear_legacy_auto_state(self):
        saved={'formation':{'usv':'circle','uav':'hemisphere','revision':0},'missions':[], 'faults':['UAV-01','UAV-02'],'automatic_returns':['UAV-01'],'fault_kinds':{'UAV-02':'payload'},'fault_status':{'UAV-01':{'phase':'landing','sim_time':100}},'telemetry_sim_times':{'UAV-01':120,'UAV-02':120}}
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/'console.json';p.write_text(json.dumps(saved))
            with patch.object(api,'CONSOLE_SNAPSHOT',p):api.restore_console()
        await api.telemetry(api.Telemetry(vehicle_id='UAV-01',x=0,y=0,z=60,yaw=0,speed=0,sim_time=2),x_bridge_token='auto-test')
        self.assertNotIn('UAV-01',api.simulated_faults);self.assertIn('UAV-02',api.simulated_faults)
    async def test_explicit_fault_overrides_auto_reason_and_stays_red(self):
        api.automatic_returns.add('UAV-01');api.simulated_faults.add('UAV-01')
        await api.set_simulated_fault('UAV-01',api.FaultRequest(unavailable=True,fault_type='payload'))
        v=self.vehicle();self.assertFalse(v.get('automatic_return',False))
        self.assertEqual(v['fault_type'],'payload');self.assertEqual(v['readiness']['operational_state'],'unavailable')

    async def test_small_out_of_order_packet_preserves_auto_return(self):
        api.simulated_faults.add('UAV-01');api.automatic_returns.add('UAV-01');api.last_sim_times['UAV-01']=100
        await api.telemetry(api.Telemetry(vehicle_id='UAV-01',x=0,y=0,z=60,yaw=0,speed=0,sim_time=99),x_bridge_token='auto-test')
        self.assertIn('UAV-01',api.simulated_faults);self.assertEqual(api.last_sim_times['UAV-01'],100)
    async def test_save_records_auto_cause_and_clock(self):
        api.automatic_return_reasons['UAV-01']='battery';api.last_sim_times['UAV-01']=100
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/'console.json'
            with patch.object(api,'CONSOLE_SNAPSHOT',p):api.save_console()
            saved=json.loads(p.read_text())
        self.assertEqual(saved['automatic_return_reasons']['UAV-01'],'battery')
        self.assertEqual(saved['telemetry_sim_times']['UAV-01'],100)
