import sys,time,unittest
from pathlib import Path
from unittest.mock import AsyncMock,patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tests'))
from app import main as api
from app.ai_response import AIProposal,build_plan
from test_defense_responses import fleet
from defense_scenarios import contacts
from fastapi import HTTPException
from pydantic import ValidationError
VALID=dict(title='분산 관측과 근접 경계',reason='현재 전방 접촉을 두 기체가 이격 관측하고 수상 기체는 함선 주변을 보호합니다.',tradeoff='세부 식별보다 관측 지속성을 우선합니다.',usv_formation='circle',uav_formation='box',uav_policy='standoff',usv_policy='protect',uav_count=2,usv_count=1)
class AISchema(unittest.TestCase):
 def test_only_supported_actions_and_no_risk_or_arbitrary_control(self):
  AIProposal(**VALID)
  for change in [{'score':100},{'uav_policy':'attack'},{'usv_count':20},{'target':[0,0]}]:
   with self.assertRaises(ValidationError):AIProposal(**{**VALID,**change})
 def test_fast_contact_cannot_use_interference_only_retreat_or_claim_to_slow_contact(self):
  m={'id':1,'scenario':'fast_approach','scene_origin':{'x':0,'y':0,'sim_time':0}}
  for change in [{'uav_policy':'avoid'},{'usv_policy':'investigate'},{'reason':'드론 배치로 상대 선박의 속도를 감소시켜 접근을 저지합니다.'}]:
   with self.assertRaises(ValueError):build_plan(AIProposal(**{**VALID,**change}),fleet(),{'usv':'circle','uav':'hemisphere'},m['scenario'],contacts(m,0))
 def test_plan_uses_available_measured_fleet_and_different_actual_targets(self):
  f=fleet();f[1]['readiness']['available']=False
  m={'id':1,'scenario':'fast_approach','scene_origin':{'x':0,'y':0,'sim_time':0}}
  p=build_plan(AIProposal(**VALID),f,{'usv':'circle','uav':'hemisphere'},m['scenario'],contacts(m,0))
  self.assertEqual(p['id'],'ai');self.assertTrue(p['available']);self.assertNotIn(f[1]['id'],[t['vehicle'] for t in p['tasks']])
class AIEndpoint(unittest.IsolatedAsyncioTestCase):
 def setUp(self):
  self.save_patch=patch.object(api,'save_console');self.save_patch.start()
  self.saved=(dict(api.latest),dict(api.missions),api.mission,dict(api.formation),api.mission_counter)
  api.latest.clear();api.missions.clear();api.mission=None
  for v in fleet():api.latest[v['id']]={**v['telemetry'],'sim_time':0,'received_at':time.time()}
  api.formation.update(usv='circle',uav='hemisphere')
 def tearDown(self):
  self.save_patch.stop()
  latest,missions,api.mission,formation,api.mission_counter=self.saved
  api.latest.clear();api.latest.update(latest);api.missions.clear();api.missions.update(missions);api.formation.clear();api.formation.update(formation)
 async def new(self):return await api.start_scenario(api.ScenarioRequest(scenario='fast_approach'))
 async def test_generated_third_option_survives_refresh_but_never_auto_approves(self):
  m=await self.new();score=m['risk']['score'];revision=api.formation['revision']
  with patch.object(api,'request_ai_proposal',AsyncMock(return_value=AIProposal(**VALID))) as model:
   out=await api.generate_ai_response(m['id'])
  self.assertEqual(model.await_count,1);self.assertEqual([p['id'] for p in out['options']][-1],'ai')
  self.assertEqual(len(out['options']),3);self.assertIsNone(api.mission);self.assertIsNone(out['approved'])
  self.assertEqual(out['risk']['score'],score);self.assertEqual(api.formation['revision'],revision)
  fresh=await api.refresh_plan(m['id']);self.assertEqual(len(fresh['options']),3)
  plan=next(p for p in fresh['options'] if p['id']=='ai');self.assertEqual(plan['source'],'llm')
 async def test_model_failure_does_not_invent_fallback_or_execute(self):
  m=await self.new()
  with patch.object(api,'request_ai_proposal',AsyncMock(side_effect=ValueError('Invalid model response'))):
   with self.assertRaises(HTTPException) as e:await api.generate_ai_response(m['id'])
  self.assertEqual(e.exception.status_code,502);self.assertEqual(len(m['options']),2)
  self.assertEqual(m['ai_status']['state'],'error');self.assertIsNone(api.mission)
 async def test_formation_changed_while_generating_rejects_old_response(self):
  m=await self.new()
  async def changed(*args,**kwargs):
   api.formation['revision']+=1;return AIProposal(**VALID)
  with patch.object(api,'request_ai_proposal',changed):
   with self.assertRaises(HTTPException) as e:await api.generate_ai_response(m['id'])
  self.assertEqual(e.exception.status_code,409);self.assertEqual(len(m['options']),2)

 async def test_operator_can_execute_ai_but_expired_ai_is_rejected(self):
  m=await self.new()
  with patch.object(api,'request_ai_proposal',AsyncMock(return_value=AIProposal(**VALID))):await api.generate_ai_response(m['id'])
  fresh=await api.refresh_plan(m['id'])
  plan=next(p for p in fresh['options'] if p['id']=='ai')
  request=api.ApprovalRequest(mission_id=m['id'],option_id='ai',human_confirmed=True,decision_source='response_button',plan_revision=fresh['plan_revision'])
  until=plan['expires_at'];plan['expires_at']=time.time()-1
  with self.assertRaises(HTTPException):await api.approve_plan(request)
  self.assertIsNone(api.mission)
  plan['expires_at']=until
  result=await api.approve_plan(request)
  self.assertEqual(result['approved']['id'],'ai')
  from mission_execution import ObservationRun
  run=ObservationRun(result,0,0)
  self.assertTrue(run.tasks)
  self.assertTrue(all(t['goal_policy'] in ('standoff','protect') for t in run.tasks.values()))
