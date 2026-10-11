"""Local LLM writes explanations; live evidence and commands stay outside the model."""
import json,re
import httpx
from state_claim_guard import check as check_state_claims
from dialogue_style import EXAMPLES
from interface_chat import context as interface_context
SYSTEM='''당신은 한국어 해상 안전 시뮬레이션 대화 보조입니다. 편하게 읽히는 해요체를 사용하세요. 보고서 제목이나 현재 문제/지금 할 일/판단할 항목 같은 고정 표제를 붙이지 마세요. 짧은 문단으로 답하고, 다음 행동이 필요하면 operator_next_steps에서 가장 관련된 확인 사항을 마지막 문장에 자연스럽게 이어주세요. 정상 상태 질문에는 불필요한 경고를 반복하지 마세요. 충전·정비 여부와 고장 등록은 current_state에 명시된 경우에만 말하세요. 첫 문장에서 질문에 직접 답하고 문서나 데이터셋 문구를 그대로 읽지 마세요. 필요 없는 서론과 반복은 생략하세요. 사용자의 질문에 바로 답하세요. 미리 준비된 문장을 복사하지 말고 상황에 맞게 자연스럽게 설명하세요. 고장 등록 시점과 발생 순서는 제공되지 않았습니다. 충전 도중 고장이 등록됐다거나 충전 때문에 고장났다고 말하지 마세요. 현재 충전·정비 중이라는 상태만 설명하세요. payload는 임무 장비이며 다른 장치로 번역하지 마세요.
대형 목록은 선택 가능한 옵션입니다. 현재 선택은 selected_formations의 그룹별 하나뿐이며 전체 목록이 현재 적용됐다고 말하지 마세요. 화면에서 검토하는 안전 대응안은 최대 두 개입니다. 현재 상태와 검색된 참고 자료만 사실 근거로 사용하세요. 과거 대화의 상태를 현재 사실로 사용하지 마세요. 배터리는 모의 추정이며 고장 등록은 시연입니다. 수행불가 판정 이유와 실제 고장 원인을 구분하세요. 원인을 모르면 미확인이라고 말하세요. 문서의 기능이 시뮬레이터에 구현됐다고 가정하지 마세요.
원인·상태 질문은 설명 하나, 안전 대응 질문은 주어진 검토안 개수에 맞춰 답하세요. 추가 질문이 필요하면 제공된 clarification_questions의 누락 정보를 묻습니다.
기체 ID·수치·판정·근거·기체 배정·대형·명령을 새로 만들거나 변경하지 마세요. 이동·승인·복구를 실행했다고 주장하지 마세요. 군사 교전, 위협 대응 배정, 무기 운용 또는 전술 기동은 제시하지 말고 안전 상태 확인만 안내하세요.
정확히 JSON {"explanation":"짧고 자연스러운 설명", "answers":[{"number":1,"explanation":"검토안 설명"}]} 형식으로 출력하세요. explanation은 최대 네 문장, answers는 provided_recommendations와 동일 개수와 순서로 최대 두 문장씩. 검토안이 없으면 빈 배열입니다. 수치와 기체 ID는 UI가 표시하므로 출력에는 쓰지 마세요.'''
def validate(raw,count,allowed_facts=None):
 value=json.loads(raw);text=value.get('explanation');answers=value.get('answers')
 if not isinstance(text,str) or not 1<=len(text)<=1200 or not isinstance(answers,list) or len(answers)!=count:raise ValueError('invalid structure')
 parts=[text]
 for i,a in enumerate(answers,1):
  if not isinstance(a,dict) or a.get('number')!=i or not isinstance(a.get('explanation'),str) or not 1<=len(a['explanation'])<=700:raise ValueError('invalid answer')
  parts.append(a['explanation'])
 for p in parts:
  if re.search(r'실행했습니다|승인했습니다|복구했습니다|명령을 보냈',p,re.I):raise ValueError('unverified claims')
  if allowed_facts is None and re.search(r'\d|(?:UAV|USV|SHIP)-',p,re.I):raise ValueError('unverified claims')
  if allowed_facts is not None:
   allowed_ids=set(re.findall(r'(?:UAV|USV|SHIP)-\d{2}',allowed_facts))
   if not set(re.findall(r'(?:UAV|USV|SHIP)-\d{2}',p)).issubset(allowed_ids):raise ValueError('invented ID')
   allowed_numbers=set(re.findall(r'\d+(?:\.\d+)?',allowed_facts))
   if not set(re.findall(r'\d+(?:\.\d+)?',p)).issubset(allowed_numbers):raise ValueError('invented value')
 return value
async def generate(message,snapshot,baseline,base_url,model,history=None):
 requested=set(re.findall(r'(?:UAV|USV|SHIP)-\d{2}',message.upper()))
 selected=[v for v in snapshot.get('vehicles',[]) if not requested or v['id'] in requested]
 current=[{'id':v['id'],'connected':v['connected'],'state':(v.get('readiness') or {}).get('operational_state'),'task':(v.get('readiness') or {}).get('task'),'reason':(v.get('readiness') or {}).get('reason'),'battery_simulated':(v.get('readiness') or {}).get('battery_percent'),'fault_type':v.get('fault_type'),'fault_phase':(v.get('fault') or {}).get('phase')} for v in selected]
 context={'question':message,'operator_next_steps':baseline.get('next_steps'),'current_interface':interface_context(snapshot),'current_queue_situation':baseline.get('queue_reference'),'question_intent':baseline.get('question_intent'),'response_policy':baseline.get('response_policy'),'current_state':current,'reference_answer':baseline['reply'],'evidence':[{k:v for k,v in e.items() if k!='telemetry'} for e in baseline.get('evidence',[])[:5]],'clarification_questions':baseline.get('clarification_questions',[]),'provided_recommendations':baseline.get('recommendations',[]),'sources':baseline.get('web_sources',[])}
 if baseline.get('answer_type')=='fault_explanation':
  # Registration chronology is unavailable. Keep current phase in UI proof only.
  context['current_state']=[{k:v for k,v in row.items() if k not in ('task','fault_phase')} for row in current]
  context['evidence']=[{k:v for k,v in row.items() if k not in ('fault_phase','roll','pitch','age_seconds')} for row in context['evidence']]
  context['reference_answer']='현재 판정 이유와 모의 고장 등록 여부만 설명합니다. 발생 시점과 물리적 원인은 미확인입니다.'
 context['style_examples']={'examples':EXAMPLES,'limits':'말투와 설명 방식만 참고. 예시의 사실은 현재 기체 상태가 아님.'}
 fleet_summary=baseline.get('answer_type')=='status' and not requested
 inventory={kind:sum(v.get('type')==kind for v in snapshot.get('vehicles',[])) for kind in ('SHIP','UAV','USV')}
 if fleet_summary:
  # Give the model qualitative summary facts. Render numeric inventory directly
  # from the snapshot below rather than asking the model to count vehicle rows.
  connected_count=sum(bool(row['connected']) for row in current)
  connection_summary=('모든 기체의 연결이 확인돼요.' if current and connected_count==len(current) else
   '연결이 확인되는 기체와 연결이 확인되지 않는 기체가 함께 있어요.' if connected_count else
   '현재 기체 연결을 확인할 수 없어요.')
  states={'defending':'담당 위치 유지','waiting':'대기 또는 복귀','unavailable':'수행불가'}
  context={'question':message,'operator_next_steps':baseline.get('next_steps'),
   'connection_summary':connection_summary,
   'current_conditions':' / '.join(sorted({states.get(row['state'],row['state'] or '미확인')+' · '+(row['reason'] or '이유 미확인') for row in current})),
   'communication_fault_registered':any(v.get('fault_type')=='communication' for v in selected),
   'limits':'배터리는 모의 값이고 고장 등록은 시연이에요. 연결이 확인되지 않는 기체의 현재 상태나 실제 고장 원인을 단정하지 마세요.',
   'provided_recommendations':baseline.get('recommendations',[]),
   'instruction':'설명은 연결 여부와 현재 상태만 질적으로 요약하세요. 기체 종류별 수는 UI가 별도 표시합니다. 숫자와 기체 ID는 쓰지 마세요.'}
 messages=[{'role':'system','content':SYSTEM}]
 for item in (history or [])[-4:]:messages.append({'role':item.role,'content':item.content})
 messages.append({'role':'user','content':'다음 자료를 읽고 사용자의 질문에 답하세요. 입력 자료를 복사하지 마세요. 출력은 explanation과 answers만 포함합니다.\n자료:\n'+json.dumps(context,ensure_ascii=False)+'\n사용자 질문: '+message})
 count=len(baseline.get('recommendations',[]))
 if fleet_summary:
  # Counts belong to the live inventory, not to generated prose. In particular,
  # the SHIP must not be merged into the USV count.
  messages[-1]['content']+='\n전체 상태 설명에는 숫자나 기체 ID를 쓰지 마세요. 기체 종류별 수와 연결 수는 화면이 원본 상태로 별도 표시합니다. 함선을 USV로 분류하지 마세요.'
 schema={'type':'object','properties':{'explanation':{'type':'string'},'answers':{'type':'array','minItems':count,'maxItems':count,'items':{'type':'object','properties':{'number':{'type':'integer','minimum':1,'maximum':3},'explanation':{'type':'string'}},'required':['number','explanation'],'additionalProperties':False}}},'required':['explanation','answers'],'additionalProperties':False}
 async with httpx.AsyncClient(timeout=90) as client:
  r=await client.post(base_url+'/api/chat',json={'model':model,'messages':messages,'stream':False,'think':False,'format':schema,'options':{'temperature':.25,'num_ctx':8192,'num_predict':700},'keep_alive':'10m'})
  r.raise_for_status();output=r.json();value=validate(output['message']['content'],len(baseline.get('recommendations',[])),None if fleet_summary else json.dumps(context,ensure_ascii=False))
 check_state_claims(value['explanation']+' '.join(a['explanation'] for a in value['answers']),selected)
 result={**baseline,'llm_used':True,'model':model,'model_note':'로컬 LLM 설명 · 상태와 자료 검색 근거 사용'}
 result['recommendations']=[{**a,'explanation':value['answers'][i]['explanation']} for i,a in enumerate(baseline.get('recommendations',[]))]
 lines=[value['explanation']]
 if fleet_summary:
  vehicles=snapshot.get('vehicles',[])
  lines.append(f"기체 구성: 함선 {inventory['SHIP']}척 · UAV {inventory['UAV']}대 · USV {inventory['USV']}대\n연결: {sum(bool(v.get('connected')) for v in vehicles)}/{len(vehicles)}대 · 수신 시점 기준")
 if baseline.get('answer_type')=='interface_help':lines.append('화면 기준: '+baseline['reply'])
 # Model prose is separate from immutable evidence rendered by the application.
 if baseline.get('answer_type')=='fault_explanation':
  for evidence in baseline.get('evidence',[]):
   id=evidence['vehicle'];v=next(v for v in snapshot['vehicles'] if v['id']==id);info=v.get('status_briefing') or {}
   lines.append(f"{id} · {info.get('title',evidence.get('reason'))}\n근거: {info.get('evidence',evidence.get('reason'))}")
 elif baseline.get('answer_type')=='safety_risk' and baseline.get('evidence'):
  lines.append('확인된 근거: '+baseline['evidence'][0]['evidence'])
 lines.extend(f"{a['number']}. {a['title']}: {a['explanation']}" for a in result['recommendations'])
 result['reply']='\n'.join(lines);return result
