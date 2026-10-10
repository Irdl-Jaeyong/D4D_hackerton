"""Fleet ownership, fault substitution, and explicit resource decisions."""
import sys,time,unittest,tempfile
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
from app import main as api
from fastapi import HTTPException

class ConcurrentMissions(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        api.reset_demo_session();api.latest.clear();api.mission_counter=0
        self.save=patch.object(api,'save_console');self.save.start();self.addCleanup(self.save.stop)
        for kind,n in [('SHIP',1),('UAV',12),('USV',8)]:
            for i in range(1,n+1):
                api.latest[f'{kind}-{i:02}']={'x':0,'y':0,'z':80 if kind=='UAV' else .7,'yaw':0,'sim_time':0,'received_at':time.time()}
    async def create(self,kind):return await api.start_scenario(api.ScenarioRequest(scenario=kind))
    async def approve(self,m,release=None):
        await api.refresh_plan(m['id'],api.RefreshRequest(release_mission_id=release))
        return await api.approve_plan(api.ApprovalRequest(mission_id=m['id'],option_id='observe',human_confirmed=True,plan_revision=m['plan_revision'],replace_active_id=release))
    async def pair(self):
        a=await self.create('fast_approach');await self.approve(a)
        b=await self.create('rear_approach');await self.approve(b)
        return a,b
    async def test_parallel_missions_reserve_disjoint_vehicles_and_bridge_sees_both(self):
        a,b=await self.pair();s=api.state()
        self.assertEqual({m['id'] for m in s['active_missions']},{a['id'],b['id']})
        self.assertFalse({t['vehicle'] for t in a['execution_tasks']} & {t['vehicle'] for t in b['execution_tasks']})
        self.assertEqual(len((await api.get_formations())['missions']),2)
    async def test_fault_replaces_same_role_once_and_keeps_other_mission(self):
        a,b=await self.pair();before=list(a['approved']['tasks']);assigned=list(b['execution_tasks'])
        task=next(t for t in a['execution_tasks'] if t['vehicle'].startswith('UAV'))
        await api.set_simulated_fault(task['vehicle'],api.FaultRequest(unavailable=True))
        s=api.state();replacement=next(t for t in a['execution_tasks'] if t.get('replaces')==task['vehicle'])
        self.assertTrue(replacement['vehicle'].startswith('UAV'))
        self.assertEqual((replacement['goal_policy'],replacement['contact_index'],replacement['role_slot']),(task['goal_policy'],task['contact_index'],task['role_slot']))
        self.assertEqual(a['approved']['tasks'],before);self.assertEqual(b['execution_tasks'],assigned)
        revision=a['assignment_revision'];api.state();self.assertEqual(a['assignment_revision'],revision)
        self.assertEqual(len(a['reassignments']),1);self.assertIsNone(a['intervention'])
        self.assertEqual(len(s['operator_notices']),1)
    async def test_shortage_preserves_other_mission_and_can_explicitly_release_it(self):
        a,b=await self.pair();task=next(t for t in a['execution_tasks'] if t['vehicle'].startswith('UAV'))
        owned={t['vehicle'] for m in (a,b) for t in m['execution_tasks']}
        for name in api.latest:
            if name.startswith('UAV') and name not in owned:api.latest[name]['received_at']-=10
        await api.set_simulated_fault(task['vehicle'],api.FaultRequest(unavailable=True))
        s=api.state();self.assertEqual(a['intervention']['kind'],'capacity_shortage')
        self.assertEqual(b['execution']['status'],'pending')
        with self.assertRaises(HTTPException):await api.reallocate_mission(a['id'],api.ReallocationRequest(release_mission_id=b['id'],human_confirmed=False))
        self.assertEqual(b['execution']['status'],'pending')
        await api.reallocate_mission(a['id'],api.ReallocationRequest(release_mission_id=b['id'],human_confirmed=True))
        self.assertEqual(b['execution']['status'],'cancelled');self.assertIsNone(a['intervention'])
        self.assertEqual(len(api.state()['active_missions']),1)
    async def test_failed_resource_decision_does_not_cancel_donor(self):
        a,b=await self.pair()
        for name in api.latest:
            if name.startswith('UAV'):api.latest[name]['received_at']-=10
        api.state()
        with self.assertRaises(HTTPException):await api.reallocate_mission(a['id'],api.ReallocationRequest(release_mission_id=b['id'],human_confirmed=True))
        self.assertNotEqual(b['execution']['status'],'cancelled')
    async def test_report_revision_and_completion_affect_only_own_mission(self):
        a,b=await self.pair();api.TOKEN='test';self.addCleanup(setattr,api,'TOKEN','')
        old=a['assignment_revision'];task=a['execution_tasks'][0]
        await api.set_simulated_fault(task['vehicle'],api.FaultRequest(unavailable=True));api.state()
        with self.assertRaises(HTTPException):await api.report_execution(api.ExecutionReport(mission_id=a['id'],assignment_revision=old,sim_time=1,elapsed_seconds=1,tasks={},status='running'),x_bridge_token='test')
        await api.report_execution(api.ExecutionReport(mission_id=b['id'],assignment_revision=b['assignment_revision'],sim_time=1,elapsed_seconds=1,tasks={},status='completed'),x_bridge_token='test')
        self.assertEqual([m['id'] for m in api.state()['active_missions']],[a['id']])
    async def test_completed_role_is_not_reassigned_or_relaunched(self):
        a,b=await self.pair();task=a['execution_tasks'][0]
        a['execution']['tasks'][task['vehicle']]={'stage':'completed','blocked':False}
        await api.set_simulated_fault(task['vehicle'],api.FaultRequest(unavailable=True))
        api.state()
        self.assertEqual(a['assignment_revision'],0);self.assertFalse(a['reassignments'])
        self.assertIsNone(a['intervention'])

    async def test_multi_mission_restore_preserves_assignments(self):
        a,b=await self.pair()
        with tempfile.TemporaryDirectory() as folder,patch.object(api,'CONSOLE_SNAPSHOT',Path(folder)/'console.json'):
            # Use the real save implementation while preventing writes to the running demo.
            self.save.stop();api.save_console();self.save.start()
            api.missions.clear();api.mission=None;api.restore_console()
            self.assertEqual(len(api.state()['active_missions']),2)
            self.assertEqual(api.missions[a['id']]['execution_tasks'],a['execution_tasks'])
    async def test_cancelling_one_keeps_other_reservations_and_global_formation(self):
        a,b=await self.pair();forms=dict(api.formation)
        await api.cancel_plan(api.CancelRequest(mission_id=a['id']))
        self.assertTrue(a['cancel_requested']);self.assertFalse(b.get('cancel_requested',False))
        self.assertEqual(api.formation,forms)
        self.assertEqual(len(api.state()['active_missions']),2) # returning units remain reserved

class MultiExecutor(unittest.TestCase):
    def test_two_runs_and_assignment_update_keep_other_progress(self):
        from mission_execution import MultiMissionRuns
        def fixture(i,vehicle):return {'id':i,'card':{'offset':[100,50]},'approved':{'approved_at':1,'tasks':[{'vehicle':vehicle}]},'execution_tasks':[{'vehicle':vehicle}],'assignment_revision':0}
        a,b=fixture(1,'UAV-01'),fixture(2,'UAV-02');runner=MultiMissionRuns()
        homes={f'UAV-0{i}':(0,0,80) for i in (1,2,3)};obs={v:(0,p) for v,p in homes.items()};available=dict.fromkeys(homes,True)
        goals,reports=runner.step([a,b],0,0,homes,obs,available)
        self.assertEqual(set(goals),{'UAV-01','UAV-02'});self.assertEqual(len(reports),2)
        runner.runs[2].tasks['UAV-02']['distance_m']=42
        a['execution_tasks']=[{'vehicle':'UAV-03'}];a['assignment_revision']=1
        goals,reports=runner.step([a,b],1,0,homes,{v:(1,p) for v,p in homes.items()},available)
        self.assertEqual(set(goals),{'UAV-03','UAV-02'});self.assertEqual(runner.runs[2].tasks['UAV-02']['distance_m'],42)
        self.assertEqual(reports[0]['assignment_revision'],1)
