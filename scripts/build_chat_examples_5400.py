#!/usr/bin/env python3
"""Expand 200 scenarios into 1,800 synthetic dialogues / 5,400 responses."""
import copy,json,math
from pathlib import Path
from build_chat_examples import build,DIRECTIONS
from scenario_questions import CATALOG_CARDS,build_plans
from chat_scenario_briefing import assemble
ROOT=Path(__file__).resolve().parents[1]
STYLES=['구어체 · 배정 질문','신중한 확인 · 비교 질문','긴급 보고 · 승인 전 검토']
FOCUS={
 '미확인 선박 접근':'신원과 이동 방향을 확인하되 접근만으로 적대 의도를 단정하지 않습니다.',
 '충돌 가능성':'상대 속도·진로가 없으므로 최근접거리나 충돌 시각을 만들어내지 않습니다.',
 '복수 접근·혼잡':'각 대상의 위치를 따로 확인합니다. 전체 대상 수만으로 동일 경로나 대응 기체 수를 확정하지 않습니다.',
 '부유물·항로 장애물':'장애물 위치·크기·표류 여부를 확인합니다. 확인 전에는 접촉이나 수거를 지시하지 않습니다.',
 '인명·구조 지원':'인원·위치 확인과 전문 구조 요청 검토를 우선하며 USV에 실제 구조 장비가 있다고 가정하지 않습니다.',
 '파도·해상 상태':'파고·주기와 기체 운용 한계를 대조합니다. 검증된 한계값 없이 안전하다고 판단하지 않습니다.',
 '바람·비행 환경':'실측 풍속·돌풍과 기체 한계를 확인하고 관측 범위 확대보다 복귀 여유를 먼저 검토합니다.',
 '항법·위치 신뢰도':'위치 신뢰도가 떨어진 기체의 좌표를 정상 데이터와 분리하고 확인 전 이동 목표로 사용하지 않습니다.',
 '통신·데이터 지연':'마지막 수신 시각을 확인하고 오래된 자료로 현재 위치를 확정하지 않습니다.',
 '배터리·복귀 여유':'고장 신고 또는 복귀 여유 부족 기체를 신규 배정에서 제외합니다. 충전은 실제 착함 확인 후 상태로 표시합니다.',
 'UAV 고장·비행 이상':'이상 기체의 신규 임무를 제외하고 조종 가능 여부·위치·착함 조건을 확인합니다. 복귀 명령 실행을 주장하지 않습니다.',
 'USV 고장·추종 이상':'추진·조향 가능 여부와 현재 위치를 확인하고 정상 USV와 분리합니다. 정비 대기 이동은 계획으로만 설명합니다.',
 '센서 오인·불일치':'독립된 관측과 시각 정보를 비교합니다. 단일 센서 보고를 확정 탐지로 설명하지 않습니다.',
 '대형 유지·전환':'현재 점유 구역·경로 충돌·전환 가능 여부를 검토합니다. 대형 선택만으로 순간 이동하거나 승인됐다고 설명하지 않습니다.',
 '착함·충전·갑판 운영':'갑판 슬롯 점유와 실제 착함 상태를 확인합니다. 공중에 있는 기체를 충전 중으로 표시하지 않습니다.',
 '명령·데이터 무결성':'출처·시각·버전을 검증하며 오래된 승인이나 중복 요청을 새 실행 권한으로 사용하지 않습니다.',
 '함선 상태·항로':'함선 운항 변경은 함장 검토용으로 구분합니다. 자동 감속이나 변침이 구현됐다고 주장하지 않습니다.',
 '연안·항만·제한 공간':'통행 공간과 장애물 위치를 먼저 확인하고 직선 거리만으로 안전 경로라고 설명하지 않습니다.',
 '야간·가시성 저하':'관측 신뢰도와 누락 구역을 확인합니다. 화면이 어둡다는 이유만으로 고장 또는 대상 부재를 단정하지 않습니다.',
 '복합 상황·운용자 부담':'즉시 확인할 항목과 보류 가능한 항목을 구분하며 동시에 여러 명령을 자동 실행하지 않습니다.'}
def expanded():
    cards={c['id']:c for c in CATALOG_CARDS};records=[]
    for base in build():
        card=cards[base['scenario_id']];i=int(card['id'][4:])-1
        for style in range(3):
            row=copy.deepcopy(base);row['id']=base['id']+f'-Q{style+1}';row['question_style']=STYLES[style]
            scene=row['snapshot'];reported=row['checks']['reported_fault_excluded'];target=None
            subject=card['situation']
            resource_note={'정상 자원':'현재 연결된 기체들 중 정상 기체로 검토해줘.','정비·저잔량 제외':'정비나 저잔량 기체는 후보에서 빼줘.','가용 자원 부족':'지금 가용 UAV와 USV가 각각 한 대뿐이야.'}[row['variant']]
            row['messages'][1]['content']=[f'야 {subject}. 누구를 보내고 나머지는 어떤 대형으로 두면 돼?',f'{subject}. 원인은 아직 모르겠어. 먼저 뭘 확인하고 어떤 선택지 세 개를 비교하면 좋을까?',f'{subject}. 급하게 판단해야 하는데 바로 실행하지 말고, 현재 가능한 안과 안 되는 안을 나눠서 세 개 보여줘.'][style]+' '+resource_note
            if row['reported_target']:
                direction,angle=DIRECTIONS[(i+style+int(base['id'][-1]))%4]
                distance=[120,250,450,750,1200,1800,2400][(i+style*2+int(base['id'][-1]))%7];count=1+(i+style)%4
                unit='명' if card['category']=='인명·구조 지원' else '척' if card['category'] in ('미확인 선박 접근','충돌 가능성','복수 접근·혼잡') else '개'
                row['reported_target']={'direction':direction,'distance_m':distance,'count':count};target=(distance*math.cos(angle),distance*math.sin(angle))
                row['messages'][2]['content']='최신 신고 기준으로 방향·거리·대상 수를 확인해주세요. 이전 보고와 바뀐 부분도 알려주세요. 추가 확인: '+'·'.join(card['check_before_decision'])+'.'
                fact=f'앞 보고를 정정할게. 최신 신고는 함선 기준 {direction} 약 {distance}m에 {count}{unit}이야. 속도와 정체는 아직 확인 안 됐어.'
            else:fact=base['messages'][3]['content']
            request=[' 배정 이유랑 필요한 확인 항목도 같이 말해줘.',' 지금 대형 유지하는 안과 바꾸는 안의 차이를 비교해줘.',' 수행 불가 기체는 빼고, 자원이 모자라면 그 이유부터 보여줘.'][style]
            row['messages'][3]['content']=fact+request
            plans=build_plans(card,scene['vehicles'],scene['formations'],target_offset=target,reported_ids=reported)
            for n,plan in enumerate(plans):
                plan['benefit']=plan['action']+' '+FOCUS[card['category']]
                plan['decision_steps']=[
                    '먼저 확인: '+'·'.join(card['check_before_decision'])+'의 최신 자료와 신고 내용 일치 여부.',
                    '배정 검토: 통신 최신성·배터리·현재 임무·복귀 여유를 확인하고 이상 신고 기체를 제외.',
                    '계획 검토: '+plan['action'],
                    '실행 전: 현재 자원으로 가능한지와 경로·갑판 조건을 사람이 확인한 뒤 별도 승인.']
                plan['hold_conditions']=['통신·위치 정보가 오래되거나 불확실함','요청 기체 수를 충족하지 못함','복귀 여유 부족 또는 경로 충돌 확인 전']
                plan['tradeoff']+=' '+(['현재 구역 감시를 유지하므로 새 관측 범위가 제한됩니다.','지원 보강은 다른 구역의 가용 자원을 줄일 수 있습니다.','노출을 줄이는 대신 추가 관측이 늦어질 수 있습니다.'][n] if any(plan['requests'].values()) else '기체 추가 출동은 없으며 운용자의 검증 시간이 필요합니다.')
                if not plan['available']:plan['tradeoff']+=' 이 조건에서는 수행 불가이며 부족 조건 해소 후 재계산해야 합니다.'
            summary='사용자 신고: '+row['messages'][3]['content']+'\n합성 예시 상태: '+row['variant']+' · 원인·의도는 미확인. 대상 수와 대응 기체 수는 자동으로 일치시키지 않습니다.'
            reply,answers=assemble({'summary':summary,'plans':plans})
            for answer in answers:
                reply+='\n\n'+str(answer['number'])+'번 세부 검토:\n'+'\n'.join(answer['decision_steps'])+'\n보류 조건: '+' / '.join(answer['hold_conditions'])
            row['messages'][4]['content']='배정 엔진 결과: '+json.dumps(plans,ensure_ascii=False)
            row['messages'][5]['content']=reply;row['expected_recommendations']=answers
            records.append(row)
    return records
if __name__=='__main__':
    rows=expanded();path=ROOT/'config/chat_examples_1800.jsonl';path.write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows))
    header='질문·대화 1,800개 / 대응안 5,400개\n기존 200개 상황 × 자원 조건 3개 × 질문 방식 3개.\n합성 예시이며 실전 운용 기준·모델 학습 완료를 의미하지 않습니다.\n\n'
    text='\n\n'.join(r['id']+' | '+r['category']+' | '+r['variant']+' | '+r['question_style']+'\n'+'\n\n'.join(m['role'].upper()+': '+m['content'] for m in r['messages'] if m['role']!='system') for r in rows)
    (ROOT/'outputs/chat_examples_5400.txt').write_text(header+text)
    print(f'{len(rows)} dialogues, {sum(len(r["expected_recommendations"]) for r in rows)} responses')
