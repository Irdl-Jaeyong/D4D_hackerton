"""LLM proposes a bounded escort plan; rules allocate vehicles and compute all goals."""
import json,re
from typing import Literal
import httpx
from pydantic import BaseModel,ConfigDict,Field
from mission_console import defense_options
from defense_scenarios import DEFENSE_RESPONSES
class AIProposal(BaseModel):
    model_config=ConfigDict(extra='forbid',str_strip_whitespace=True)
    title: str=Field(min_length=3,max_length=40)
    reason: str=Field(min_length=10,max_length=200)
    tradeoff: str=Field(min_length=5,max_length=120)
    usv_formation: Literal['circle','v','columns','fan']
    uav_formation: Literal['hemisphere','box','triangle','v','rings']
    uav_policy: Literal['track','standoff','protect','avoid']
    usv_policy: Literal['screen','protect','standoff','investigate','avoid']
    uav_count: int=Field(ge=1,le=3,strict=True)
    usv_count: int=Field(ge=1,le=3,strict=True)
    def spec(self):
        return {'id':'ai','title':self.title,'benefit':self.reason,'tradeoff':self.tradeoff,
                'formations':{'usv':self.usv_formation,'uav':self.uav_formation},
                'allocation':{'UAV':{'count':self.uav_count,'goal_policy':self.uav_policy},'USV':{'count':self.usv_count,'goal_policy':self.usv_policy}}}
def validate_context(proposal,scenario):
    if scenario!='communication_interference' and 'avoid' in (proposal.uav_policy,proposal.usv_policy):
        raise ValueError('교란 반대편 이격은 통신 교란 상황에서만 사용할 수 있습니다.')
    if proposal.usv_policy=='investigate' and scenario not in ('suspicious_float','underwater_contact'):
        raise ValueError('추정 구역 확인은 부유물·수중 접촉 상황에서만 사용할 수 있습니다.')
    if re.search(r'속도.{0,14}(감소시|낮추|감속시|유도)',proposal.reason+' '+proposal.tradeoff):
        raise ValueError('관측·호위 기체는 상대의 속도나 행동을 변경할 수 없습니다.')
def signature(plan):
    return (tuple(sorted(plan['formations'].items())),tuple(sorted((t['vehicle'].split('-')[0],t['contact_index'],t['role_slot'],t.get('goal_policy')) for t in plan['tasks'])))
def build_plan(proposal,vehicles,formation,scenario,contacts):
    validate_context(proposal,scenario)
    plans=defense_options(vehicles,formation,scenario,contacts=contacts,specs=[proposal.spec()])
    if not plans:raise ValueError('함선의 최신 위치가 없습니다.')
    plan=plans[0]
    if any(signature(plan)==signature(p) for p in defense_options(vehicles,formation,scenario,contacts=contacts)):
        raise ValueError('기존 대응안과 같은 행동입니다. 다른 대형·배정·관측 방법이 필요합니다.')
    plan['source']='llm'
    return plan

def input_summary(item,vehicles,formation):
    available=[v for v in vehicles if v['type'] in ('UAV','USV') and v['readiness']['available']]
    return {'scenario':item['scenario'],'situation_name':item['card']['title'],'summary':item['card']['summary'],
            'contacts':[{k:t[k] for k in ('contact_type','range_m','speed_mps','x','y','z') if k in t} for t in item.get('threats',[])],
            'available':{kind:sum(v['type']==kind for v in available) for kind in ('UAV','USV')},
            'vehicle_samples':[{ 'id':v['id'],'x':round(v['telemetry']['x'],1),'y':round(v['telemetry']['y'],1),'battery_simulated':v['readiness']['battery_percent']} for kind in ('UAV','USV') for v in sorted((v for v in available if v['type']==kind),key=lambda v:v['id'])[:4]],
            'formations':{k:formation[k] for k in ('usv','uav')},'rule_risk':item.get('risk'),
            'existing_plans':DEFENSE_RESPONSES[item['scenario']],
            'data_limits':'위치·연결은 Gazebo 오도메트리, 접촉과 배터리는 모의 값입니다. 실제 소나·전파 탐지·차단 장비는 없습니다.'}
async def request_proposal(url,model,summary):
    prompt=('You propose ONE alternative non-weapon escort observation plan for a Gazebo demonstration. '
            'Return only the requested JSON. title, reason and tradeoff MUST be natural Korean. '
            'Use current supplied facts only; do not invent sensors, measurements, hostile intent or successful interception. '
            'Do not change risk scores or priority. Leave ship navigation unchanged. '
            'The escort vehicles CANNOT change the contact speed, movement or intention. Do not claim any such effects. '
            'Do not claim stopping, repelling, slowing or redirecting the contact. Describe only actual observation and escort movements. '
            'Title is a short Korean strategy name such as 이격 관측·근접 호위, NEVER repeat the situation name. '
            'Reason must be ONE short Korean sentence under 80 characters. Tradeoff must be ONE short Korean sentence under 60 characters. '
            'Your formations, goal policies or counts MUST differ from BOTH existing plans. '
            'Counts are units per contact, not total. Use available UAVs AND USVs. '
            'track: UAV distant observation; screen: USV outer boundary; standoff: greater distance from contact; '
            'protect: positions near the ship; investigate: USV observation around estimated contact area; '
            'avoid: positions on opposite side of interference. No weapons, jamming or physical interception. '
            'All coordinate goals and vehicle assignments will be calculated by deterministic rules. '
            'Explain why your different choice suits THIS situation and give a concrete limitation.')
    schema=AIProposal.model_json_schema()
    if summary['scenario']!='communication_interference':
        for field in ('uav_policy','usv_policy'):schema['properties'][field]['enum'].remove('avoid')
    if summary['scenario'] not in ('suspicious_float','underwater_contact'):
        schema['properties']['usv_policy']['enum'].remove('investigate')
    async with httpx.AsyncClient(timeout=80) as client:
        messages=[{'role':'system','content':prompt},{'role':'user','content':json.dumps(summary,ensure_ascii=False)}]
        for attempt in range(2):
            response=await client.post(url+'/api/chat',json={'model':model,'messages':messages,'format':schema,'stream':False,'think':False,'keep_alive':'10m','options':{'temperature':.2,'num_ctx':4096,'num_predict':650}})
            response.raise_for_status()
            content=response.json()['message']['content']
            try:
                proposal=AIProposal.model_validate_json(content)
                validate_context(proposal,summary['scenario'])
                return proposal
            except ValueError:
                if attempt:raise
                messages.append({'role':'assistant','content':content[:2500]})
                messages.append({'role':'user','content':'Return complete valid JSON matching the schema. Korean text. No extra fields.'})
