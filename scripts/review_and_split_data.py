#!/usr/bin/env python3
"""Review 50 representative examples and produce family-isolated candidate splits."""
import collections,hashlib,json
from pathlib import Path
from deduplicate_chat_data import read_rows,write_rows,stable
ROOT=Path(__file__).resolve().parents[1]
TOPIC_FAMILY={'battery':'배터리·복귀 여유','rc':'통신·데이터 지연','gcs':'통신·데이터 지연','position':'항법·위치 신뢰도','fence':'항법·위치 신뢰도','prearm':'UAV 고장·비행 이상','logs':'UAV 고장·비행 이상','marine':'충돌 가능성','simulation':'시뮬레이션 검증','regulation':'실제 운용 준비'}
VALIDATION={'배터리·복귀 여유','UAV 고장·비행 이상'}
TEST={'통신·데이터 지연','항법·위치 신뢰도'}
NOTES={
 '미확인 선박 접근':'방향·거리·척수뿐 아니라 진로·속도·신원 미확인 여부를 답변에 남겨야 합니다.',
 '충돌 가능성':'거리만으로 충돌 위험·최근접 시각을 확정하면 안 됩니다. 상대 진로와 속도의 추가 확인이 필요합니다.',
 '복수 접근·혼잡':'대상별 위치가 없는데 한 점을 여러 대상의 관측 위치로 사용합니다. 대상별 신고를 다시 묻도록 수정해야 합니다.',
 '부유물·항로 장애물':'크기·표류 방향을 확인해야 하며 좌표 지정만으로 접근 경로가 안전하다고 판단할 수 없습니다.',
 '인명·구조 지원':'사람 확인·전문 구조 지원 검토와 단순 관측 계획을 구분해야 합니다.',
 '파도·해상 상태':'파고·주기·기체 운용 한계가 누락된 상태에서 특정 대형이 더 안전하다고 단정하면 안 됩니다.',
 '바람·비행 환경':'풍속·돌풍·복귀 여유를 확인하는 추가 질문이 필요합니다.',
 '항법·위치 신뢰도':'위치 신뢰도 불량 기체를 정상 위치 자료와 분리해야 하며 복귀 가능성을 단정하면 안 됩니다.',
 '통신·데이터 지연':'영상·관제·조종 링크 종류와 마지막 수신 시각을 구분해서 다시 물어야 합니다.',
 '배터리·복귀 여유':'잔량만으로 복귀 가능성을 판단하지 말고 계측 출처와 복귀 에너지를 확인해야 합니다.',
 'UAV 고장·비행 이상':'제어 가능 여부·실제 위치·착함 조건을 확인해야 하며 고장 원인을 단정하면 안 됩니다.',
 'USV 고장·추종 이상':'현재 USV 출동은 계획 등록입니다. 실제 추진·조향 제어를 실행한 것으로 학습시키면 안 됩니다.',
 '센서 오인·불일치':'자료별 발생 시각·출처를 확인하고 단일 센서 보고를 확정 탐지로 사용하면 안 됩니다.',
 '대형 유지·전환':'현재 슬롯·경로·전환 가능성 확인이 필요하며 대형 선택과 실행 승인을 구분해야 합니다.',
 '착함·충전·갑판 운영':'실제 착함·슬롯 점유가 확인되어야 충전을 표시할 수 있습니다.',
 '명령·데이터 무결성':'출처·시각·버전 확인 전 명령을 적용하지 않아야 합니다. 서로 다른 안의 한계가 에너지 소비 같은 일반 문구에 치우칩니다.',
 '함선 상태·항로':'자동 감속·변침은 현재 구현된 실행 기능과 구분해야 합니다.',
 '연안·항만·제한 공간':'통행 공간·장애물·관할 규칙 정보가 부족하면 다시 질문해야 합니다.',
 '야간·가시성 저하':'가시성·센서 신뢰도를 확인해야 하며 대상이 보이지 않는다는 사실을 대상 부재로 해석하면 안 됩니다.',
 '복합 상황·운용자 부담':'기존 세 안만 반복하는 대신 위험 우선순위와 먼저 확인할 항목을 질문해야 합니다.'}
def family(item):
    row=item['record'];return row['category'] if item['kind']=='scenario_dialogue' else TOPIC_FAMILY[row['topic_id']]
def origins(item):
    row=item['record']
    if item['kind']=='scenario_dialogue':return {'scenario:'+row['scenario_id']}
    ids={q['faq_id'] for q in row.get('question_variants',[])} or {row.get('faq_id',row['id'])}
    return {'faq:'+id for id in ids}
def split_for(group):return 'validation' if group in VALIDATION else 'test' if group in TEST else 'train'
def review(item):
    row=item['record'];issues=[];passes=[]
    if item['kind']=='scenario_dialogue':
        plans=row['expected_recommendations'];passes.append('대응안 3개와 자원 조건 확인')
        issues.append({'severity':'revision','code':'template_specificity','note':NOTES[row['category']]})
        actual=(row['messages'][1]['content']+' '+row['messages'][3]['content'])
        if row.get('reported_target'):
            passes.append('신고 위치는 합성 예시로 표시, ETA는 직선 추정')
            if any(len([t for t in p['tasks'] if t['execution']=='observe_target'])>1 and len({stable(t.get('target_world')) for t in p['tasks'] if t['execution']=='observe_target'})==1 for p in plans):
                issues.append({'severity':'blocking','code':'shared_target_without_separation','note':'복수 UAV에 같은 관측 좌표가 배정됩니다. 별도 관측 구역·고도·충돌 회피 경로가 계산되지 않아 서로 다른 구역 감시라는 설명을 뒷받침하지 못합니다.'})
        if any(not p['available'] for p in plans):passes.append('부족한 자원을 수행 불가로 표시')
        if all(t['vehicle'] not in row['checks']['reported_fault_excluded'] for p in plans for t in p['tasks']):passes.append('신고 기체를 신규 배정에서 제외')
        # User facts compared with immutable sample state: surfaced, not silently altered.
        if '연결은 되지만' in actual:passes.append('사용자 신고와 원인 미확인을 구분')
        if row['category'] not in ('미확인 선박 접근','충돌 가능성','복수 접근·혼잡','부유물·항로 장애물','인명·구조 지원'):
            issues.append({'severity':'revision','code':'unresolved_information','note':'추가 답변에서도 원인이나 확인 항목이 미확인인 채 최종 계획 설명으로 넘어갑니다. 재질문 또는 조건부 제안을 학습 예시에 명확히 넣어야 합니다.'})
    else:
        passes.extend(['출처와 합성 제안의 범위를 분리','자동 실행하지 않음'])
        issues.append({'severity':'revision','code':'question_specificity','note':'서로 다른 FAQ 질문에 주제별 동일 확인 문구와 일반 절차를 사용합니다. 각 질문에 대한 직접적인 설명과 필요한 추가 질문을 작성해야 합니다.'})
        if item['kind']=='faq_situation':issues.append({'severity':'blocking','code':'ten_perspectives_not_three_choices','note':'답변 10개는 함께 적용 가능한 점검 관점입니다. 이를 서로 다른 선택지로 취급하면 안 됩니다. 세 추천안·근거·한계 형식으로 변환이 필요합니다.'})
    return {'record_id':row['id'],'kind':item['kind'],'category':family(item),'source_group':family(item),
      'review_type':'assistant_content_review_with_structural_checks','expert_review':False,
      'verdict':'hold_for_revision','training_approved':False,'passes':passes,'issues':issues,
      'question':row['messages'][1]['content'] if item['kind']=='scenario_dialogue' else row.get('user_question',row.get('question'))}
def representative(items):
    selected=[]
    for category in sorted({r['record']['category'] for r in items if r['kind']=='scenario_dialogue'}):
        group=[r for r in items if r['kind']=='scenario_dialogue' and r['record']['category']==category]
        normal=next(r for r in group if r['record']['variant']=='정상 자원');selected.append(normal)
        shortage=next(r for r in group if r['record']['variant']=='가용 자원 부족' and r['record']['scenario_id']!=normal['record']['scenario_id']);selected.append(shortage)
    for i,topic in enumerate(TOPIC_FAMILY):
        kind='web_faq' if i%2==0 else 'faq_situation'
        selected.append(next(r for r in items if r['kind']==kind and r['record']['topic_id']==topic))
    return selected

def run():
    items=read_rows(ROOT/'config/training_review_deduplicated.jsonl');destination=ROOT/'config/training';destination.mkdir(exist_ok=True)
    splits={name:[] for name in ('train','validation','test')}
    for item in items:splits[split_for(family(item))].append(item)
    for name,rows in splits.items():write_rows(destination/(name+'_candidates.jsonl'),rows)
    source=json.loads((ROOT/'config/defense_scenarios_200.json').read_text());faq=json.loads((ROOT/'config/web_faq_60.json').read_text())
    train_topics={item['record']['topic_id'] for item in splits['train'] if item['kind']!='scenario_dialogue'}
    train_ids={item['record']['scenario_id'] for item in splits['train'] if item['kind']=='scenario_dialogue'}
    train_faqs={o[4:] for item in splits['train'] for o in origins(item) if o.startswith('faq:')}
    reference={'scenarios':[r for r in source['scenarios'] if r['id'] in train_ids], 'topics':[r for r in faq['topics'] if r['id'] in train_topics], 'faqs':[r for r in faq['faqs'] if r['id'] in train_faqs],
      'usage':'오프라인 평가에는 이 학습용 참조만 사용. 운영 채팅의 전체 자료 검색·원본 자료를 평가 입력으로 사용하지 않음.'}
    (destination/'train_reference_catalog.json').write_text(json.dumps(reference,ensure_ascii=False,indent=2))
    sample=representative(items);reviews=[review(item) for item in sample]
    payload={'sample_count':len(reviews),'selection':'20개 상황 범주마다 정상·자원 부족 각 1개 + FAQ 주제 10개 각 1개',
      'reviewer':'assistant; no maritime expert or model performance validation','verdict_counts':dict(collections.Counter(r['verdict'] for r in reviews)),
      'issue_counts':dict(collections.Counter(i['code'] for r in reviews for i in r['issues'])),'reviews':reviews}
    (destination/'representative_review_50.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2))
    write_rows(destination/'representative_samples_50.jsonl',sample)
    manifest={'version':1,'seed':'deterministic category policy; no random row split', 'ready_for_training':False,'ready_reason':'자료 분리만 완료. 대표 검토에서 수정 필요. 학습 파일 형식 변환·전문가 검토·모델 평가 전.',
      'splits':{name:{'count':len(rows),'family_groups':sorted({family(r) for r in rows}), 'origin_groups':sorted({o for r in rows for o in origins(r)}),'kind_counts':dict(collections.Counter(r['kind'] for r in rows))} for name,rows in splits.items()},
      'leakage_policy':'원래 상황 ID·FAQ 별칭·주제 가족을 같은 분할에 유지. 평가 자료는 수정·프롬프트 개선·학습에 사용하지 않음.',
      'eval_reference':'train_reference_catalog.json; 운영용 전체 RAG 자료를 평가에 사용하면 정보 누출로 처리',
      'checks':{'all_records':sum(len(r) for r in splits.values())==len(items),
       'no_family_overlap':all(not {family(r) for r in splits[a]} & {family(r) for r in splits[b]} for a,b in [('train','validation'),('train','test'),('validation','test')]),
       'no_origin_overlap':all(not {o for r in splits[a] for o in origins(r)} & {o for r in splits[b] for o in origins(r)} for a,b in [('train','validation'),('train','test'),('validation','test')])},
      'limitations':['공통 답변 틀이 범주 간에도 남아 있으므로 의미 중복 완전 제거를 보장하지 않음.','원본 전체 자료는 운영에서 계속 사용. 평가에서는 별도 필터 참조를 사용해야 함.','특정 주제 전체를 제외하는 강한 분리라 일반화 평가용이며 실측 임무 성공률 평가가 아님.']}
    assert all(manifest['checks'].values()) and len(reviews)==50
    (destination/'split_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2))
    lines=['대표 사례 50개 검토','전문가 검증 또는 실제 모델 성능 평가가 아닌 자료 내용 검토입니다.','결과: 50개 모두 학습 전 수정 필요.','']
    for r in reviews:
        lines.extend([r['record_id']+' | '+r['category'], '질문: '+r['question'], '보존할 점: '+' / '.join(r['passes']), '수정할 점:'])
        lines.extend('['+i['severity']+'] '+i['note'] for i in r['issues']);lines.append('')
    (ROOT/'outputs/representative_review_50.txt').write_text('\n'.join(lines))
    print(json.dumps({'splits':{k:len(v) for k,v in splits.items()},'review':payload['verdict_counts'],'issues':payload['issue_counts'],'checks':manifest['checks']},ensure_ascii=False))
if __name__=='__main__':run()
