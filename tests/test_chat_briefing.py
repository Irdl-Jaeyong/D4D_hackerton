import copy,json,sys,time,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
from app import main as api
from chat_scenario_briefing import prepare,assemble,validated_explanations
from scenario_questions import CATALOG_CARDS,retrieve
class ChatBriefing(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        api.latest.clear();api.simulated_faults.clear();api.battery_origin.clear()
        api.formation.update(usv='circle',uav='hemisphere',revision=0)
        for id in ['SHIP-01','UAV-01','UAV-02','USV-01']:
            api.latest[id]={'x':0,'y':0,'z':0,'sim_time':0,'received_at':time.time()}
    def test_catalog_and_explicit_retrieval(self):
        self.assertEqual(len(CATALOG_CARDS),200)
        for card in CATALOG_CARDS:
            self.assertEqual(retrieve(card['id'])[0],card)
            self.assertEqual(len(card['recommendations']),3)
    def test_reported_fault_excluded_and_no_invented_target(self):
        brief=prepare('UAV-01 드론이 심하게 흔들려요',api.state())
        self.assertEqual(brief['scenario']['category'],'UAV 고장·비행 이상')
        for plan in brief['plans']:
            for task in plan['tasks']:
                self.assertNotEqual(task['vehicle'],'UAV-01')
                self.assertNotEqual(task['execution'],'observe_target')
        self.assertTrue(any(not p['available'] for p in brief['plans']))
    def test_unknown_question_does_not_allocate(self):
        brief=prepare('안녕',api.state());self.assertIsNone(brief['scenario'])
        self.assertEqual(len(assemble(brief)[1]),0)
        self.assertTrue(brief['clarification_questions'])
        self.assertTrue(all(not p['tasks'] for p in brief['plans']))
    def test_invalid_explanations_rejected(self):
        for raw in ['[]','{}','{"answers":[null,null,null]}',json.dumps({'answers':[{'option_id':id,'explanation':'UAV-99 출동'} for id in ['observe','verify','prepare']]})]:
            with self.assertRaises(ValueError):validated_explanations(raw)
    async def test_model_failure_still_returns_three_and_does_not_execute(self):
        mission=copy.deepcopy(api.mission);formation=copy.deepcopy(api.formation)
        with patch.object(api.httpx,'AsyncClient',side_effect=api.httpx.ConnectError('offline')):
            result=await api.scenario_chat(api.Chat(message='DEF-101 UAV-01'))
        self.assertEqual(len(result['recommendations']),3)
        self.assertFalse(result['llm_used']);self.assertFalse(result['executed'])
        self.assertEqual(api.mission,mission);self.assertEqual(api.formation,formation)
    async def test_invalid_card_returns_validation_error(self):
        with self.assertRaises(api.HTTPException) as error:await api.scenario_chat(api.Chat(message='DEF-999'))
        self.assertEqual(error.exception.status_code,422)

    async def test_valid_model_explains_engine_assignments(self):
        from unittest.mock import AsyncMock,MagicMock
        output={'answers':[{'option_id':id,'explanation':'감시 공백을 줄일 수 있지만 상태 확인이 먼저 필요합니다.'} for id in ['observe','verify','prepare']]}
        response=MagicMock();response.json.return_value={'message':{'content':json.dumps(output)}}
        client=AsyncMock();client.post.return_value=response
        manager=AsyncMock();manager.__aenter__.return_value=client
        with patch.object(api.httpx,'AsyncClient',return_value=manager):
            result=await api.scenario_chat(api.Chat(message='DEF-101 UAV-01'))
        self.assertTrue(result['llm_used']);self.assertEqual(len(result['recommendations']),3)
        sent=client.post.call_args.kwargs['json']
        self.assertIn('engine_calculated_plans',sent['messages'][0]['content'])
        self.assertFalse(result['executed'])

    async def test_followup_collects_missing_fields_and_rotates_to_ship_heading(self):
        api.latest['SHIP-01']['yaw']=1.5707963267948966
        first=await api.scenario_chat(api.Chat(message='미확인 선박이 접근해'))
        self.assertEqual(len(first['clarification_questions']),3)
        self.assertEqual(first['recommendations'],[])
        with patch.object(api.httpx,'AsyncClient',side_effect=api.httpx.ConnectError('offline')):
            second=await api.scenario_chat(api.Chat(message='우현 300m에 2척',clarification_context=first['clarification_context']))
        self.assertEqual(second['clarification_questions'],[])
        self.assertEqual(len(second['recommendations']),3)
        task=second['recommendations'][0]['tasks'][0]
        self.assertEqual(task['target_world'],{'x':300.0,'y':0.0})
        self.assertEqual(task['distance_m'],300.0);self.assertEqual(task['eta_seconds'],30)
        self.assertEqual(second['reported_details']['count'],2)
        self.assertFalse(second['executed'])
    def test_distance_without_direction_keeps_asking(self):
        brief=prepare('미확인 선박 2척이 300m에 접근',api.state())
        self.assertEqual(len(brief['clarification_questions']),1)
        self.assertEqual(brief['plans'],[])
