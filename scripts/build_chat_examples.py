#!/usr/bin/env python3
"""Reproducible synthetic dialogue examples; no live state or model training."""
import json,math
from pathlib import Path
from scenario_questions import CATALOG_CARDS,build_plans
from chat_scenario_briefing import POSITIONAL,assemble
ROOT=Path(__file__).resolve().parents[1]
DIRECTIONS=[('정면',0),('우현',-math.pi/2),('좌현',math.pi/2),('후방',math.pi)]
def snapshot(variant,index):
    vehicles=[]
    for kind,count in [('SHIP',1),('UAV',4),('USV',2)]:
        for n in range(1,count+1):
            available=kind=='SHIP' or (n>1 if variant==1 else n==2 if variant==2 else True)
            vehicles.append({'id':f'{kind}-{n:02d}','type':kind,'connected':True,'telemetry':{'x':0,'y':(n-1)*20,'z':30 if kind=='UAV' else 0,'yaw':0},
             'readiness':{'available':available,'battery_percent':25 if not available else 90-n*3,'endurance_minutes':3 if not available else 25,'task':'정비 대기' if not available else '기존 담당 구역 감시'}})
    return {'vehicles':vehicles,'formations':{'usv':'circle','uav':'hemisphere'}}
def build():
    records=[]
    for i,card in enumerate(CATALOG_CARDS):
        for variant in range(3):
            scene=snapshot(variant,i);direction,angle=DIRECTIONS[(i+variant)%4];distance=[150,300,600,1000,1500][(i+variant)%5];count=1+(i+variant)%3
            checks=card['check_before_decision'];question=card['situation']+' 어떻게 대응할까?';target=None;reported=[]
            if card['category'] in POSITIONAL:
                question=card['category']+' 상황인데 어떻게 대응할까?'
                clarification='함선 기준 방향, 거리, 대상 수를 알려주세요. 추가로 '+ '·'.join(checks)+'도 확인해주세요.'
                followup=f'{direction} {distance}m에 {count}'+('명' if card['category']=='인명·구조 지원' else '척' if card['category'] in ('미확인 선박 접근','충돌 가능성','복수 접근·혼잡') else '개')+'이야. 속도와 정체는 아직 몰라.'
                target=(distance*math.cos(angle),distance*math.sin(angle))
            elif card['category'] in ('UAV 고장·비행 이상','USV 고장·추종 이상','배터리·복귀 여유'):
                id=('USV' if card['category'].startswith('USV') else 'UAV')+'-01';reported=[id]
                clarification='어느 기체인가요? '+ '·'.join(checks)+'의 현재 값과 마지막 수신 시각도 알려주세요.'
                followup=f'{id}이야. 연결은 되지만 원인은 아직 모르겠어. 고장 신고 기체는 배정에서 빼줘.'
            else:
                clarification='다음 항목을 확인해주세요: '+ '·'.join(checks)+'. 확인된 사실과 아직 모르는 부분을 나눠 알려주세요.'
                followup=checks[0]+' 관련 이상은 신고됐지만 원인은 미확인이야. 나머지 항목은 추가 확인이 필요해.'
            plans=build_plans(card,scene['vehicles'],scene['formations'],target_offset=target,reported_ids=reported)
            for plan in plans:
                plan['benefit']='이 사례에서는 '+card['situation']+'. '+plan['action']+' 확인 항목: '+'·'.join(checks)+'.'
                if variant==2:plan['tradeoff']+=' 현재 가용 자원이 적으므로 부족한 대응안을 가능하다고 표시하지 않습니다.'
            brief={'summary':'사용자 신고: '+followup+'\n가상 사례: '+card['id']+' · '+card['situation']+'\n확인 전인 원인·속도·의도를 단정하지 않습니다.','plans':plans}
            reply,answers=assemble(brief)
            records.append({'id':f"{card['id']}-V{variant+1}",'scenario_id':card['id'],'category':card['category'],'variant':['정상 자원','정비·저잔량 제외','가용 자원 부족'][variant],
                'synthetic':True,'snapshot':scene,'reported_target':{'direction':direction,'distance_m':distance,'count':count} if target else None,
                'messages':[{'role':'system','content':'가상 시뮬레이션 대화 예시입니다. 부족한 정보는 다시 묻고, 기체 번호는 제공된 엔진 결과만 사용합니다. 실전 이격 기준이나 고장 원인을 추측하지 않습니다. 승인·이동을 실행하지 않습니다.'},
                {'role':'user','content':question},{'role':'assistant','content':clarification},{'role':'user','content':followup},
                {'role':'system','content':'배정 엔진 결과: '+json.dumps(plans,ensure_ascii=False)}, {'role':'assistant','content':reply}],
                'expected_recommendations':answers,'checks':{'answer_count':3,'no_auto_execution':True,'reported_fault_excluded':reported,'unknown_facts':checks,'resource_shortage_must_be_visible':variant==2}})
    return records
if __name__=='__main__':
    records=build();destination=ROOT/'config/chat_examples_600.jsonl'
    destination.write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in records))
    out=ROOT/'outputs/chat_examples_600.txt';out.parent.mkdir(exist_ok=True)
    header='AI 대화 예시 600개 / 대응안 1800개\n200개 기존 상황 × 정상·정비 제외·가용 자원 부족 3조건.\n모두 합성 예시이며 기체 번호와 거리는 예시 스냅샷의 배정 엔진 계산입니다. 실제 운용 기준 또는 모델 재학습 완료를 뜻하지 않습니다.\n\n'
    out.write_text(header+'\n\n'.join(r['id']+' | '+r['variant']+'\n'+ '\n\n'.join(m['role'].upper()+': '+m['content'] for m in r['messages'] if m['role']!='system') for r in records))
    print(f'{len(records)} dialogue examples, {sum(len(r["expected_recommendations"]) for r in records)} responses')
