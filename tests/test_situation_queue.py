import sys,time,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
from app import main as api
from fastapi import HTTPException
class SituationQueue(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        api.mission=None;api.mission_counter=0;api.latest.clear();api.simulated_faults.clear();api.fault_status.clear();api.fault_kinds.clear();api.charge_credit.clear();api.battery_origin.clear()
        if hasattr(api,'missions'):api.missions.clear()
        api.formation.update(usv='circle',uav='hemisphere',revision=0)
        for name in ['SHIP-01','UAV-01','UAV-02','UAV-03','USV-01']:
            api.latest[name]={'x':0,'y':0,'z':60 if name.startswith('UAV') else 0,'yaw':0,'sim_time':0,'received_at':time.time()}
    async def create(self,kind):return await api.start_scenario(api.ScenarioRequest(scenario=kind))
    async def test_three_situations_stay_visible_and_risk_sorted(self):
        a=await self.create('debris');b=await self.create('crossing');c=await self.create('rescue')
        s=api.state();self.assertEqual([m['id'] for m in s.get('approval_queue',[])],[c['id'],b['id'],a['id']])
        self.assertEqual(len(s['scene']['situations']),3)
        self.assertEqual(s['approval_queue'][0]['risk']['score'],96)
    async def test_cancel_one_keeps_other_world_objects(self):
        a=await self.create('debris');b=await self.create('rescue')
        await api.cancel_plan(api.CancelRequest(mission_id=b['id']))
        self.assertEqual([m['id'] for m in api.state()['approval_queue']],[a['id']])
        self.assertEqual([t['mission_id'] for t in api.state()['scene']['situations']],[a['id']])
    async def test_active_plan_and_new_queue_are_independent(self):
        a=await self.create('crossing')
        await api.approve_plan(api.ApprovalRequest(mission_id=a['id'],option_id='observe',human_confirmed=True))
        b=await self.create('rescue')
        s=api.state();self.assertEqual(s['active_mission']['id'],a['id']);self.assertEqual(s['approval_queue'][0]['id'],b['id'])
        self.assertEqual((await api.get_formations())['mission']['id'],a['id'])
        with self.assertRaises(HTTPException):await api.approve_plan(api.ApprovalRequest(mission_id=b['id'],option_id='observe',human_confirmed=True))
        await api.cancel_plan(api.CancelRequest(mission_id=b['id']))
        self.assertEqual(api.state()['active_mission']['id'],a['id'])
    async def test_refresh_keeps_id_anchor_and_rejects_old_consent(self):
        a=await self.create('crossing');origin=dict(a['scene_origin']);created=a['created_at']
        await api.refresh_plan(a['id'])
        self.assertEqual(a['scene_origin'],origin);self.assertEqual(a['created_at'],created)
        with self.assertRaises(HTTPException):await api.approve_plan(api.ApprovalRequest(mission_id=a['id'],option_id='observe',human_confirmed=True,plan_revision=0))
        await api.approve_plan(api.ApprovalRequest(mission_id=a['id'],option_id='observe',human_confirmed=True,plan_revision=1))
    async def test_fault_joins_queue_without_phantom_rescue_object(self):
        await self.create('crossing')
        await api.start_scenario(api.ScenarioRequest(scenario='fault',vehicle_id='UAV-01',fault_type='propulsion'))
        s=api.state();self.assertEqual(len(s['approval_queue']),2);self.assertEqual(len(s['scene']['situations']),1)
        self.assertEqual(s['approval_queue'][0]['risk']['priority'],'P0')
    async def test_missing_scores_are_unavailable_not_zero(self):
        from app.approval_risk import evaluate
        r=evaluate({'S':3});self.assertIsNone(r['score']);self.assertIsNone(r['priority']);self.assertEqual(r['missing'],['U','A'])
    async def test_same_kind_objects_do_not_overlap(self):
        await self.create('debris');await self.create('debris')
        objects=api.state()['scene']['situations'];self.assertNotEqual((objects[0]['x'],objects[0]['y']),(objects[1]['x'],objects[1]['y']))
    async def test_approved_risk_is_frozen_and_risk_plan_does_not_add_rescue_object(self):
        m=await self.create('crossing')
        await api.approve_plan(api.ApprovalRequest(mission_id=m['id'],option_id='observe',human_confirmed=True))
        frozen=dict(m['risk_at_approval'])
        api.simulated_faults.add('UAV-03')
        await api.risk_plan('UAV-03:fault')
        self.assertEqual(m['risk'],frozen)
        self.assertEqual(len(api.state()['scene']['situations']),1)
    async def test_queue_survives_console_snapshot(self):
        import tempfile
        old=api.CONSOLE_SNAPSHOT
        with tempfile.TemporaryDirectory() as folder:
            try:
                api.CONSOLE_SNAPSHOT=Path(folder)/'snapshot.json'
                a=await self.create('crossing');b=await self.create('rescue')
                await api.approve_plan(api.ApprovalRequest(mission_id=a['id'],option_id='observe',human_confirmed=True))
                api.save_console();api.missions.clear();api.mission=None
                api.restore_console()
                self.assertEqual(api.state()['active_mission']['id'],a['id'])
                self.assertEqual(api.state()['approval_queue'][0]['id'],b['id'])
            finally:api.CONSOLE_SNAPSHOT=old
class RiskFormula(unittest.TestCase):
    def test_boundaries_formula_p0_and_invalid(self):
        from app.approval_risk import evaluate
        for signals,score,priority in [({'S':0,'U':0,'A':0},0,'P3'),({'S':2,'U':2,'A':3},44,'P3'),({'S':3,'U':2.5,'A':0},45,'P2'),({'S':5,'U':2,'A':3},74,'P2'),({'S':5,'U':3.5,'A':1},75,'P1'),({'S':5,'U':5,'A':5},100,'P1')]:
            r=evaluate(signals);self.assertEqual((r['score'],r['priority']),(score,priority))
        self.assertEqual(evaluate({'S':0,'U':0,'A':0,'severe_control_loss':True})['priority'],'P0')
        r=evaluate({'collision_imminent':True});self.assertEqual(r['priority'],'P0');self.assertIsNone(r['score'])
        for value in [-1,6,True,float('nan'),float('inf')]:self.assertIn('S',evaluate({'S':value,'U':0,'A':0})['missing'])
