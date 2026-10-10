"""Grounded chat context: retrieved examples + immutable engine assignments."""
import json,re,math
from functools import lru_cache
from pathlib import Path
from scenario_questions import retrieve,build_plans
from formation_motion import CATALOG
from web_faq import retrieve_faq,briefing as faq_briefing

POSITIONAL={'미확인 선박 접근','충돌 가능성','복수 접근·혼잡','부유물·항로 장애물','인명·구조 지원'}
def details(text):
    directions=[('우현',-math.pi/2),('오른쪽',-math.pi/2),('좌현',math.pi/2),('왼쪽',math.pi/2),('정면',0),('전방',0),('앞쪽',0),('후방',math.pi),('뒤쪽',math.pi)]
    matches=[angle for name,angle in directions if name in text]
    distance=re.findall(r'(?<![\d.])(\d+(?:\.\d+)?)\s*(km|킬로미터|미터|m)(?![a-z])',text,re.I)
    count=re.findall(r'(\d+)\s*(?:대|척|명)',text)
    return {'bearing':matches[-1] if matches else None,'distance_m':float(distance[-1][0])*(1000 if distance[-1][1].lower() in ('km','킬로미터') else 1) if distance else None,'count':int(count[-1]) if count else None}

def prepare(question,snapshot):
    faq=retrieve_faq(question)
    if faq:return faq_briefing(faq,snapshot)
    card,candidates,method=retrieve(question)
    reported_ids=re.findall(r'(?<![A-Z0-9])(?:UAV|USV)-\d{2}(?!\d)',question.upper())
    info=details(question);questions=[];target=None
    if not card:
        questions=['어떤 상황인가요? 예: 미확인 선박 접근, 항로 부유물, UAV 고장.']
    elif card['category'] in POSITIONAL:
        if info['bearing'] is None:questions.append('함선 기준 어느 방향인가요? 정면·후방·좌현·우현 중 알려주세요.')
        if info['distance_m'] is None:questions.append('함선에서 몇 미터 떨어져 있나요? 예: 300m 또는 1km.')
        elif not 0 < info['distance_m'] <= 10000:questions.append('시뮬레이션 관측 범위 안의 양수 거리로 알려주세요 (최대 10km).')
        if info['count'] is None or info['count'] < 1:questions.append('대상은 몇 대·척·명인가요? 예: 선박 2척.')
        if not questions:
            leader=next((v for v in snapshot['vehicles'] if v['type']=='SHIP' and v['connected']),None)
            if leader:
                angle=leader['telemetry'].get('yaw',0)+info['bearing']
                target=(info['distance_m']*math.cos(angle),info['distance_m']*math.sin(angle))
    elif card['category'] in ('UAV 고장·비행 이상','USV 고장·추종 이상') and not reported_ids:
        questions=['어느 기체에 이상이 있나요? 예: UAV-01 또는 USV-02.']
    if questions:
        return {'summary':'구체적인 대응안을 계산하려면 다음 내용을 알려주세요.','scenario':None,'candidates':candidates,'retrieval_method':'clarification_required','plans':[], 'catalog_count':200,'clarification_questions':questions,'clarification_context':question,'reported_details':info}

    if card:
        plans=build_plans(card,snapshot['vehicles'],snapshot['formations'],target_offset=target,reported_ids=reported_ids)
        summary=f"입력 상황: {question}\n참고 사례: {card['id']} · {card['category']} (질문과 유사한 가상 예시)"
    else:
        plans=[]
        specs=[('observe','현재 상태 확인','현재 통신·배터리·임무 상태를 먼저 확인합니다.'),
               ('verify','불확실한 정보 추가 확인','대상의 종류·위치·문제 기체를 확인한 뒤 상황을 다시 평가합니다.'),
               ('prepare','새 출동 보류 · 가용 상태 확인','고장·통신 지연·복귀 잔량 부족 기체를 제외하고 승인 가능한 계획을 다시 검토합니다.')]
        for id,title,action in specs:
            plans.append({'id':id,'title':title,'action':action,'formations':{g:snapshot['formations'][g] for g in ('usv','uav')},'tasks':[],
                          'available':True,'requests':{'uav':0,'usv':0},'benefit':action,'tradeoff':'현재 정보만으로 구체적인 출동 위치를 확정할 수 없습니다.',
                          'unavailable_reason':'','validation':'추가 정보 확인용 제안. 이동 계획을 생성하지 않습니다.','execution_scope':'대화 설명만; 명령 실행 없음.'})
        summary='현재 자료만으로 해당 질문을 상황 카드 하나로 확정하기 어렵습니다. 확인 방법을 세 가지로 정리합니다.'
    connected=sum(v['connected'] for v in snapshot['vehicles'])
    summary+=f"\n실시간 연결 {connected}/{len(snapshot['vehicles'])} · 배터리는 시뮬레이션 추정입니다."
    return {'summary':summary,'scenario':{'id':card['id'],'category':card['category'],'situation':card['situation'],'check_before_decision':card['check_before_decision']} if card else None,
            'candidates':candidates,'retrieval_method':method,'plans':plans,'catalog_count':200,'clarification_questions':[],'clarification_context':None,'reported_details':info}

@lru_cache(maxsize=1)
def dialogue_examples():
    path=Path(__file__).resolve().parents[1]/'config/chat_examples_deduplicated.jsonl'
    if not path.exists():path=path.with_name('chat_examples_1800.jsonl')
    if not path.exists():path=path.with_name('chat_examples_600.jsonl')
    if not path.exists():return {}
    examples={}
    for line in path.read_text().splitlines():
        item=json.loads(line)
        examples.setdefault(item['scenario_id'],[]).append(item)
    return examples

def example_context(brief):
    if not brief.get('scenario'):return []
    rows=dialogue_examples().get(brief['scenario']['id'],[])
    selected=[];seen=set()
    for row in rows:
        if row['variant'] not in seen:selected.append(row);seen.add(row['variant'])
    selected=selected[:3]
    return [{'variant':item['variant'],'sample_question':item['messages'][1]['content'],
             'sample_clarification':item['messages'][2]['content'],
             'example_explanations':[answer['explanation'] for answer in item['expected_recommendations']],
             'limits':'합성 예시: 답변 형식과 확인 방식만 참고. 현재 배정은 engine_calculated_plans만 사용. 예시 신고나 자원 상태를 현재 사실로 간주하지 않음.'} for item in selected]

def context(brief,snapshot):
    vehicles=[{'id':v['id'],'connected':v['connected'],'battery':v['readiness']['battery_percent'],
               'available':v['readiness']['available'],'task':v['readiness']['task']} for v in snapshot['vehicles']]
    return {'question_examples':brief['scenario'],'retrieval_method':brief['retrieval_method'],'possible_related_examples':brief['candidates'],
            'engine_calculated_plans':brief['plans'],'current_vehicles':vehicles,'dialogue_style_examples':example_context(brief),
            'reported_details':brief.get('reported_details'),'faq_source_summary':brief['summary'] if brief.get('faq_reference') else None,'web_sources':brief.get('web_sources',[]),'faq_situation_examples':brief.get('faq_situation_examples',[]),'limits':'카드는 가상 예시이며 진단 아님. 위치는 사용자 신고와 현재 함선 방향으로 계산한 시뮬레이션 관측 지점. ETA는 직선 추정이며 충돌 회피 경로 검증 전. 대화는 실행 없음.'}

SYSTEM='''당신은 함선 시뮬레이션의 운용자 설명 보조입니다. 한국어로 답하세요.
질문과 관련된 가상 사례와 현재 상태로 계산한 대응안 세 개가 제공됩니다.
기체 배정·대형·배터리·도달 시간을 새로 만들거나 변경하지 마세요.
각 대응안의 action, benefit, tradeoff를 근거로 장점과 한계를 짧게 설명하세요.
가상 사례를 실제 탐지나 적대 의도·고장 확정으로 단정하지 마세요. 안전한 이동 경로가 검증됐다고 주장하지 마세요.
실행·승인·고장 해제를 했다고 말하지 마세요. 카메라 정보는 참고이며 명령 근거로 확정하지 마세요.
기체 번호와 수치는 시스템이 별도로 표시합니다. explanation에는 숫자나 기체 번호를 쓰지 마세요.
아래 JSON만 출력하세요. answers는 observe, verify, prepare 순서로 정확히 세 개여야 합니다.
{"answers":[{"option_id":"observe","explanation":"장점과 한계"},{"option_id":"verify","explanation":"장점과 한계"},{"option_id":"prepare","explanation":"장점과 한계"}]}'''

def validated_explanations(raw):
    value=json.loads(raw)
    if not isinstance(value,dict):raise ValueError('Expected object')
    answers=value.get('answers')
    if not isinstance(answers,list) or len(answers)!=3:raise ValueError('Expected three answers')
    out={}
    for item,id in zip(answers,('observe','verify','prepare')):
        if not isinstance(item,dict) or item.get('option_id')!=id:raise ValueError('Unexpected option order')
        text=item.get('explanation')
        if not isinstance(text,str) or not text.strip() or len(text)>500 or re.search(r'\d',text):raise ValueError('Ungrounded numeric detail')
        out[id]=text.strip()
    return out

def assemble(brief,explanations=None):
    recommendations=[];parts=[brief['summary']]
    if brief.get('clarification_questions'):return brief['summary']+'\n'+'\n'.join(brief['clarification_questions']),[]
    for i,plan in enumerate(brief['plans'],1):
        selected=' / '.join(t['vehicle']+' → '+t['task']+(f" · 이동 {t['distance_m']}m · 직선 ETA 약 {t['eta_seconds']}초" if t.get('distance_m') is not None else '') for t in plan['tasks']) or '추가 출동 기체 없음'
        formation=f"USV {CATALOG['usv'][plan['formations']['usv']]} / UAV {CATALOG['uav'][plan['formations']['uav']]}"
        explanation=(explanations or {}).get(plan['id']) or plan['benefit']+' '+plan['tradeoff']
        status=('검토 제안 · 추가 출동 없음' if brief.get('faq_reference') else '현재 자원 조건 충족') if plan['available'] else '현재 수행 불가: '+plan['unavailable_reason']
        answer={**plan,'number':i,'formation_label':formation,'assignment_label':selected,'explanation':explanation,'status_label':status}
        recommendations.append(answer)
        parts.append(f"{i}. {plan['title']}\n{formation}\n{selected}\n{explanation}\n{status}")
    if brief.get('faq_check_question'):parts.append('추가로 확인할 내용: '+brief['faq_check_question'])
    for source in brief.get('web_sources',[]):parts.append('출처: '+source['title']+' '+source['url'])
    parts.append('기체 번호는 배정 엔진 결과입니다. 대화로 기체 이동·승인 명령은 실행되지 않았습니다.')
    return '\n\n'.join(parts),recommendations
