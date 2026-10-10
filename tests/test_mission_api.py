"""Approval guards, tested in memory without mutating the live simulator."""
import sys,time,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
from app import main as api
from fastapi import HTTPException

class MissionAPI(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        api.mission=None;api.missions.clear();api.mission_counter=0;api.latest.clear();api.battery_origin.clear();api.simulated_faults.clear()
        api.formation.update(usv='circle',uav='hemisphere',revision=0)
        for id in ['SHIP-01','UAV-01','UAV-02','USV-01']:
            api.latest[id]={'x':0,'y':0,'z':0,'sim_time':0,'received_at':time.time()}
    async def scenario(self):
        return await api.start_scenario(api.ScenarioRequest(scenario='crossing'))
    async def approve(self,id,option='verify'):
        return await api.approve_plan(api.ApprovalRequest(mission_id=id,option_id=option,human_confirmed=True))
    async def test_defense_contact_does_not_change_formation_and_manual_choice_works(self):
        for kind in ('UAV','USV'):
            for i in range(1,9):api.latest[f'{kind}-{i:02}']={'x':0,'y':0,'z':80 if kind=='UAV' else .7,'sim_time':0,'received_at':time.time()}
        m=await api.start_scenario(api.ScenarioRequest(scenario='multi_approach'))
        self.assertEqual(len(m['threats']),2)
        self.assertEqual(api.formation['usv'],'circle');self.assertEqual(api.formation['uav'],'hemisphere')
        self.assertIsNone(api.mission)
        await api.set_formation(api.FormationRequest(group='usv',mode='columns',scenario_id=m['id']))
        self.assertEqual((await api.get_formations())['scenario_context']['id'],m['id'])
        await api.refresh_plan(m['id'])
        api.formation['scenario_id']=999 # a previous situation must not orient the new approved plan
        await api.approve_plan(api.ApprovalRequest(mission_id=m['id'],option_id='observe',human_confirmed=True,plan_revision=m['plan_revision']))
        self.assertEqual(api.formation['scenario_id'],m['id'])
        self.assertEqual({t['contact_index'] for t in m['approved']['tasks']},{0,1})
        await api.set_formation(api.FormationRequest(group='uav',mode='box',scenario_id=m['id']))
        self.assertTrue(m['manual_takeover']);self.assertTrue(m['cancel_requested'])
        self.assertEqual(api.formation['uav'],'box')
        m['execution']['status']='cancelled'
        self.assertEqual(len(api.state()['scene']['situations']),2)

    async def test_normal_start_clears_old_situations_faults_and_formations(self):
        await self.scenario()
        api.simulated_faults.add('UAV-01');api.fault_kinds['UAV-01']='propulsion'
        api.formation.update(usv='fan',uav='triangle',scenario_id=1)
        api.reset_demo_session()
        self.assertIsNone(api.mission);self.assertEqual(api.missions,{})
        self.assertFalse(api.simulated_faults);self.assertEqual(api.fault_kinds,{})
        self.assertEqual(api.formation,{'usv':'circle','uav':'hemisphere','revision':0})
        self.assertEqual(api.state()['scene']['situations'],[])

    async def test_missing_human_confirmation_does_not_execute(self):
        m=await self.scenario()
        with self.assertRaises(HTTPException):
            await api.approve_plan(api.ApprovalRequest(mission_id=m['id'],option_id='verify'))
        self.assertEqual(api.formation['revision'],0)
        self.assertIsNone(m['approved'])

    async def test_text_approval_is_exact_and_recorded(self):
        m=await self.scenario()
        request=dict(mission_id=m['id'],option_id='verify',human_confirmed=True,decision_source='captain_text')
        with self.assertRaises(HTTPException):
            await api.approve_plan(api.ApprovalRequest(**request,operator_command='1번 승인'))
        self.assertEqual(api.formation['revision'],0)
        await api.approve_plan(api.ApprovalRequest(**request,operator_command='2번 승인'))
        self.assertEqual(api.mission['approved']['operator_command'],'2번 승인')

    async def test_approval_applies_formation_and_locks_manual_changes(self):
        m=await self.scenario();await self.approve(m['id'])
        self.assertEqual(api.formation['usv'],'columns');self.assertEqual(api.formation['uav'],'box')
        with self.assertRaises(HTTPException) as e:
            await api.set_formation(api.FormationRequest(group='usv',mode='v'))
        self.assertEqual(e.exception.status_code,409)
        await api.cancel_plan();self.assertEqual(api.formation['usv'],'columns')
    async def test_expired_card_is_rejected_without_replacing_other_cards(self):
        m=await self.scenario();other=await self.scenario()
        m['planned_at']-=61
        with self.assertRaises(HTTPException):await self.approve(m['id'])
        self.assertIsNone(m['approved'])
        self.assertIn(other['id'],api.missions)
    async def test_offline_candidate_rejected_on_approval(self):
        m=await self.scenario();task=m['options'][1]['tasks'][0]
        api.latest[task['vehicle']]['received_at']-=10
        with self.assertRaises(HTTPException):await self.approve(m['id'])
        self.assertIsNone(m['approved'])
    async def test_simulated_fault_excluded_and_recovers(self):
        await api.set_simulated_fault('USV-01',api.FaultRequest(unavailable=True))
        v=next(v for v in api.state()['vehicles'] if v['id']=='USV-01')
        self.assertEqual(v['readiness']['operational_state'],'unavailable')
        m=await self.scenario();self.assertFalse(m['options'][1]['available'])
        await api.set_simulated_fault('USV-01',api.FaultRequest(unavailable=False))
        v=next(v for v in api.state()['vehicles'] if v['id']=='USV-01')
        self.assertEqual(v['readiness']['operational_state'],'defending')

    async def test_execution_pause_does_not_latch_availability_off(self):
        m=await self.scenario();await self.approve(m['id'],option='observe')
        id=m['approved']['tasks'][0]['vehicle']
        m['execution']={'tasks':{id:{'stage':'outbound','blocked':True}}}
        formations=await api.get_formations()
        self.assertTrue(formations['availability'][id])

    async def test_missing_leader_rejects_approval(self):
        m=await self.scenario();api.latest['SHIP-01']['received_at']-=10
        with self.assertRaises(HTTPException):await self.approve(m['id'])

    async def test_changed_formation_invalidates_recommendation(self):
        m=await self.scenario()
        await api.set_formation(api.FormationRequest(group='uav',mode='triangle'))
        with self.assertRaises(HTTPException):await self.approve(m['id'])
    async def test_completed_execution_releases_lock_and_preserves_result(self):
        m=await self.scenario();await self.approve(m['id'],option='observe')
        api.TOKEN='test'
        await api.report_execution(api.ExecutionReport(mission_id=m['id'],sim_time=20,elapsed_seconds=20,tasks={},status='completed'),x_bridge_token='test')
        self.assertIsNone(api.state()['active_mission'])
        self.assertEqual(api.missions[m['id']]['execution']['status'],'completed')
        await api.set_formation(api.FormationRequest(group='uav',mode='hemisphere'))
        import tempfile
        old=api.CONSOLE_SNAPSHOT
        try:
            with tempfile.TemporaryDirectory() as folder:
                api.CONSOLE_SNAPSHOT=Path(folder)/'snapshot.json';api.save_console();api.restore_console()
                self.assertIsNone(api.state()['active_mission'])
        finally:api.CONSOLE_SNAPSHOT=old;api.TOKEN=''

    async def test_automatic_creation_preserves_selected_camera(self):
        mode,image=api.camera_view,api.camera
        try:
            api.camera_view='inspect';api.camera={'received_at':time.time(),'jpeg':b'image'}
            await api.start_scenario(api.ScenarioRequest(scenario='crossing'),preserve_camera=True)
            self.assertEqual(api.camera_view,'inspect');self.assertIsNotNone(api.camera)
        finally:api.camera_view=mode;api.camera=image

if __name__=='__main__':unittest.main()
