"""Priority queue ordering and approval isolation."""
import sys,time,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
from app import main as api
from fastapi import HTTPException

class QueueTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        api.mission=None;api.mission_counter=0
        if hasattr(api,'missions'):api.missions.clear()
        api.latest.clear();api.battery_origin.clear();api.simulated_faults.clear()
        api.formation.update(usv='circle',uav='hemisphere',revision=0)
        for id in ['SHIP-01','UAV-01','UAV-02','USV-01']:
            api.latest[id]={'x':0,'y':0,'z':0,'sim_time':0,'received_at':time.time()}
    async def test_all_situations_retained_and_rescue_first(self):
        a=await api.start_scenario(api.ScenarioRequest(scenario='debris'))
        b=await api.start_scenario(api.ScenarioRequest(scenario='rescue'))
        q=api.state().get('approval_queue',[])
        self.assertEqual([m['id'] for m in q],[b['id'],a['id']])
    async def test_approve_one_retains_other_and_blocks_second(self):
        a=await api.start_scenario(api.ScenarioRequest(scenario='crossing'))
        b=await api.start_scenario(api.ScenarioRequest(scenario='rescue'))
        await api.approve_plan(api.ApprovalRequest(mission_id=a['id'],option_id='verify',human_confirmed=True))
        self.assertEqual([m['id'] for m in api.state()['approval_queue']],[b['id']])
        with self.assertRaises(HTTPException):
            await api.approve_plan(api.ApprovalRequest(mission_id=b['id'],option_id='verify',human_confirmed=True))
        self.assertEqual(api.mission['id'],a['id'])
    async def test_refresh_same_id_and_cancel_only_selected(self):
        a=await api.start_scenario(api.ScenarioRequest(scenario='crossing'))
        b=await api.start_scenario(api.ScenarioRequest(scenario='rescue'))
        a2=await api.refresh_plan(a['id'])
        self.assertEqual(a2['id'],a['id'])
        await api.cancel_plan(api.CancelRequest(mission_id=b['id']))
        self.assertEqual([m['id'] for m in api.state()['approval_queue']],[a['id']])
    async def test_reassessment_missing_and_p0_reorders_queue(self):
        a=await api.start_scenario(api.ScenarioRequest(scenario='debris'))
        b=await api.start_scenario(api.ScenarioRequest(scenario='rescue'))
        old=api.TOKEN;api.TOKEN='test-token'
        try:
            with self.assertRaises(HTTPException):await api.update_assessment(a['id'],api.RiskSignals(collision_imminent=True),'')
            await api.update_assessment(a['id'],api.RiskSignals(collision_imminent=True),'test-token')
            q=api.state()['approval_queue']
            self.assertEqual(q[0]['id'],a['id'])
            self.assertEqual(q[0]['risk']['priority'],'P0')
            self.assertIsNone(q[0]['risk']['score'])
            await api.update_assessment(a['id'],api.RiskSignals(S=3),'test-token')
            q=api.state()['approval_queue']
            self.assertEqual(q[0]['id'],b['id'])
            self.assertEqual(q[-1]['risk']['missing'],['U','A'])
        finally:api.TOKEN=old
    async def test_recalculated_plan_rejects_previous_selection(self):
        m=await api.start_scenario(api.ScenarioRequest(scenario='crossing'))
        request=api.ApprovalRequest(mission_id=m['id'],option_id='verify',human_confirmed=True)
        await api.refresh_plan(m['id'])
        with self.assertRaises(HTTPException):await api.approve_plan(request)
        self.assertIsNone(m['approved'])
    async def test_expired_and_duplicate_approval_rejected(self):
        m=await api.start_scenario(api.ScenarioRequest(scenario='crossing'))
        m['planned_at']-=61
        with self.assertRaises(HTTPException):await api.approve_plan(api.ApprovalRequest(mission_id=m['id'],option_id='verify',human_confirmed=True,plan_revision=m['plan_revision']))
        await api.refresh_plan(m['id'])
        await api.approve_plan(api.ApprovalRequest(mission_id=m['id'],option_id='verify',human_confirmed=True,plan_revision=m['plan_revision']))
        with self.assertRaises(HTTPException):await api.approve_plan(api.ApprovalRequest(mission_id=m['id'],option_id='verify',human_confirmed=True,plan_revision=m['plan_revision']))

class RiskTests(unittest.TestCase):
    def test_formula_boundaries_missing_and_override(self):
        from app.approval_risk import evaluate,sort_key
        for values,score,priority in [((0,0,0),0,'P3'),((2,2,3),44,'P3'),((3,2,1),46,'P2'),((5,2,3),74,'P2'),((5,3,2),76,'P1'),((5,5,5),100,'P1')]:
            r=evaluate(dict(zip(('S','U','A'),values)))
            self.assertEqual((r['score'],r['priority']),(score,priority))
        self.assertEqual(evaluate({'S':5})['missing'],['U','A'])
        self.assertIsNone(evaluate({'S':5})['priority'])
        self.assertEqual(evaluate({'collision_imminent':True})['priority'],'P0')
        self.assertIsNone(evaluate({'collision_imminent':True})['score'])
        self.assertIsNone(evaluate({'S':9,'U':1,'A':1})['score'])
        q=[{'id':i,'created_at':t,'risk':evaluate(s)} for i,t,s in [(1,1,{'S':5,'U':4,'A':4}),(2,2,{'S':5,'U':5,'A':5}),(3,0,{'S':5,'U':4,'A':4})]]
        self.assertEqual([m['id'] for m in sorted(q,key=sort_key)],[2,3,1])
if __name__=='__main__':unittest.main()
