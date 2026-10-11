#!/usr/bin/env python3
"""60 adapted FAQs × 10 fictional conditions × 10 application responses."""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
CONDITIONS=[
 ('최초 신고 · 정보 부족','이상 신고는 받았지만 문제 기체·발생 시각·측정값은 아직 확인하지 못했다.','어느 기체에서 언제 발생했고 확인된 값이 무엇인가요?'),
 ('자료 갱신 지연','화면의 마지막 기체 상태는 15초 전이며 새 수신 여부를 확인 중이다.','현재 수신 시각과 마지막 정상 자료 시각을 알려주세요.'),
 ('정상 자료 · 설정 미확인','통신과 측정값은 갱신되고 있지만 보호 동작 또는 운용 기준 설정을 확인하지 못했다.','사용 중인 소프트웨어 버전과 해당 설정·기준을 확인했나요?'),
 ('저잔량 후보 포함','UAV-01 잔량은 18%로 표시되며 복귀 소요 시간과 배터리 계측 신뢰도는 미확인이다.','잔량의 계측 출처·현재 위치·복귀 여유를 확인해주세요.'),
 ('이상 기체 포함','UAV-02에 수행 불가 신고가 있으며 실제 공중·갑판 위치와 제어 가능 여부는 미확인이다.','UAV-02의 실제 위치·제어 가능 여부·정비 상태가 확인됐나요?'),
 ('관측·센서 불일치','영상 신고와 위치·자세 자료가 일치하지 않아 원인을 확인 중이다.','자료별 수신 시각과 관측 출처를 비교해주세요.'),
 ('가용 자원 부족','현재 신규 임무가 가능한 UAV와 USV는 각각 한 대뿐이며 다른 기체는 임무 또는 정비 중이다.','기존 임무를 유지해야 하는 기체와 실제 가용 후보를 알려주세요.'),
 ('환경·운용 범위 미확인','함선은 이동 중이며 바람·파고·허용 구역 또는 적용 공역의 확인이 필요하다.','현재 환경 측정값과 적용 가능한 운용 범위를 확인했나요?'),
 ('회복 신고 · 재검증 전','통신 또는 이상 상태가 회복됐다고 신고됐지만 재검증·정비 해제·현재 모드는 확인 전이다.','무엇이 회복됐고 현재 모드와 재검증 결과는 무엇인가요?'),
 ('여러 신고 · 승인 전','운용자가 여러 경고를 동시에 보고 있으며 어떤 계획도 최종 승인하지 않았다.','먼저 확인할 위험과 승인 여부·계획 버전을 알려주세요.')]
SPECIFICS={
 'battery':'배터리 잔량·전압·계측 출처와 현재 위치의 복귀 여유',
 'rc':'조종 링크·현재 모드·마지막 정상 조종 입력',
 'gcs':'관제 데이터·외부 제어·영상 링크의 구분과 각각의 수신 시각',
 'position':'위치 추정 품질·좌표 출처·센서 수신 시각',
 'fence':'허용 구역·현재 위치·현재 설정·계획 경로',
 'prearm':'시동 거부 메시지·교정 상태·배터리·정비 이력',
 'logs':'이상 시각·목표 자세와 실제 자세·오류 이벤트',
 'simulation':'시험 설정·고장 주입 여부·기대 결과와 실제 결과',
 'marine':'운용 해역·대상 진로와 속도·항법 규칙 적용 범위',
 'regulation':'운용 국가·공역·임무 종류·관할 기관의 최신 안내'}
def answers(faq,condition,topic):
    label,report,clarify=condition;focus=SPECIFICS[faq['topic_id']]
    pairs=[
      ('필요 정보부터 묻기',clarify+' 추가로 '+focus+'를 확인합니다.','사용자가 답하지 않은 값은 생성하지 않습니다.'),
      ('신고와 확인 사실 분리',f'“{report}”는 이 예시의 신고 내용으로 표시하고, {focus} 중 실제 확인된 항목만 따로 제시합니다.','신고만으로 고장 원인·안전성·허가 상태를 확정하지 않습니다.'),
      ('최신 자료 확인','각 자료의 수신 시각과 발생 시각을 비교하고 오래된 값은 최신 기체 상태와 분리합니다.','15초는 예시 지연값이며 공통 안전 타임아웃 기준이 아닙니다.'),
      ('공식 근거 확인','이 질문의 근거 문서와 운용 환경의 설정·버전을 비교하고 실제 적용 범위를 확인합니다.','웹 문서 기능이 현재 시뮬레이터에 구현됐다고 가정하지 않습니다.'),
      ('배정 후보 재검토','배정 엔진에 통신 최신성·배터리·현재 임무·복귀 여유를 전달하고 이상 신고 기체를 제외하는 안을 검토합니다.','LLM이 번호를 임의로 선택하지 않으며 이 FAQ 답변은 출동 기체를 배정하지 않습니다.'),
      ('현재 임무·대형 검토','위치·제어 신뢰도가 확인된 기체의 기존 임무를 기준으로 대형 유지 또는 변경 필요성을 사람이 검토합니다.','유지가 항상 안전하다고 단정하거나 미확인 기체에 위치 유지 명령을 주지 않습니다.'),
      ('자원 부족 표시','요청 임무와 실제 가용 후보 수를 비교하고 부족하면 수행 불가 이유와 추가 확인 사항을 표시합니다.','다른 기체의 기존 임무를 승인 없이 취소하지 않습니다.'),
      ('복귀·정비 조건 확인','문제 기체의 위치·제어 상태·복귀 에너지와 착함 조건을 확인하고 필요한 정비 검토를 요청합니다.','공중 기체를 충전 중으로 표시하거나 복귀가 항상 가능하다고 주장하지 않습니다.'),
      ('재현 시험·기록 준비','관련 시뮬레이션 시험 조건과 '+focus+'의 관측값을 기록하고 기대 결과와 실제 결과를 비교합니다.','실제 운용의 보호 기능을 끄는 방식으로 문제를 해결하지 않습니다.'),
      ('운용자 최종 판단 요청','확인된 사실·미확인 항목·가능한 계획·수행 불가 사유를 요약해 운용자가 검토할 수 있도록 제시합니다.','선택·설명만으로 승인·이동·정비 해제를 실행하지 않습니다.')]
    return [{'id':f'answer-{i:02d}','title':title,'action':action,'limit':limit,'execution':'proposal_only'} for i,(title,action,limit) in enumerate(pairs,1)]
def build():
    faqdata=json.loads((ROOT/'config/web_faq_60.json').read_text());topics={t['id']:t for t in faqdata['topics']};rows=[]
    for faq in faqdata['faqs']:
        topic=topics[faq['topic_id']]
        for i,condition in enumerate(CONDITIONS,1):
            label,report,clarify=condition
            rows.append({'id':faq['id']+f'-S{i:02d}','faq_id':faq['id'],'topic_id':faq['topic_id'],'category':topic['category'],
              'condition':label,'situation':report,'user_question':faq['question']+' 지금 '+report+' 이럴 때 어떻게 판단할까?',
              'clarifying_question':clarify,'synthetic':True,'automatic_execution':False,
              'source_reference':topic['source'],'source_fact_reference':topic['id'],
              'source_scope':'출처는 원래 FAQ 주제의 사실만 지원. 상황·답변은 프로젝트용 합성 예시이며 실측 빈도·공식 절차·법적 판단이 아님.',
              'answers':answers(faq,condition,topic)})
    return rows
if __name__=='__main__':
    rows=build();(ROOT/'config/faq_situations_600.jsonl').write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows))
    lines=['FAQ 60개 × 상황 10개 × 답변 10개 = 600개 상황 / 6,000개 답변','공식 문서 주제에 기반한 합성 예시. 각 답은 검토 관점이며 서로 배타적인 실행 전술 10개가 아님.','']
    for row in rows:
        lines.extend([row['id']+' | '+row['category']+' | '+row['condition'],'질문: '+row['user_question'],'추가 확인: '+row['clarifying_question'],'출처: '+row['source_reference']['title']+' '+row['source_reference']['url']])
        lines.extend(f'{i}. {a["title"]}\n   {a["action"]}\n   한계: {a["limit"]}' for i,a in enumerate(row['answers'],1));lines.append('')
    (ROOT/'outputs/faq_situations_600_answers_6000.txt').write_text('\n'.join(lines))
    print(f'{len(rows)} situations, {sum(len(r["answers"]) for r in rows)} answers')
