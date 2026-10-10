"""Read-only suggestions for observed simulator safety signals."""
from risk_monitor import assess
PX4={'title':'PX4 Safety Configuration','url':'https://docs.px4.io/main/en/config/safety','checked_on':'2026-10-10'}
ACTIONS={
 'link':[('최신 수신 확인','마지막 수신 시각과 링크 상태를 확인합니다. 마지막 위치를 현재 위치로 단정하지 않습니다.'),('설정·연결 기록 확인','설정된 통신 손실 보호 모드와 링크 로그를 확인합니다. 링크 회복 전 명령 전달을 보장하지 않습니다.'),('추가 작업 보류','해당 기체의 새 배정을 보류하는 안을 검토하고 운용자가 상태 확인 후 복구를 판단합니다.')],
 'fault':[('등록 상태 확인','고장 종류와 복귀·착함·정비 단계를 확인합니다. 모의 고장 기록과 실제 진단을 구분합니다.'),('진행 상태 관찰','위치와 상태가 신뢰 가능한지 확인하며 비상 처리 시연의 진행을 관찰합니다.'),('정비 검토','고장 해제 전에 정상 상태 확인과 정비 검토를 요청합니다. 충전 완료만으로 고장 해제를 단정하지 않습니다.')],
 'battery':[('잔량 근거 확인','배터리 수치의 출처와 시간 경과를 확인합니다. 현재 잔량은 모의 추정입니다.'),('귀환 여유 검토','거리·소모·착륙 위치를 확인해 왕복 여유를 다시 검토합니다. 고정 퍼센트만으로 안전을 보장하지 않습니다.'),('신규 작업 보류','추가 작업을 보류하고 운용자가 귀환 또는 정비 필요성을 판단합니다.')],
 'unstable':[('자세 계측 확인','기울기와 수신 시각을 확인합니다. 흔들림만으로 추진기 고장을 확정하지 않습니다.'),('원인 기록 확인','환경 조건·제어 기록·센서 상태를 교차 확인합니다. 확인되지 않은 원인은 미확인으로 표시합니다.'),('임무 지속 검토','새 작업을 보류하는 안을 검토하고 운용자가 현재 임무 지속 또는 복귀를 판단합니다.')],
 'separation':[('간격 재확인','두 기체의 최신 3D 위치와 시간 동기화를 확인합니다. 간격 부족을 충돌 발생으로 단정하지 않습니다.'),('경로 검토','현재 목표점과 이동 경로의 겹침 여부를 확인합니다. 검증 없이 회피 방향을 정하지 않습니다.'),('추가 이동 보류','겹치는 신규 이동 계획을 보류하는 안을 검토하고 운용자가 안전한 분리 경로를 확인합니다.')]
}
def answer_risks(query,snapshot):
 import re
 ids=re.findall(r'(?:UAV|USV)-\d{2}',query.upper());risks=assess(snapshot.get('vehicles',[]))
 if ids:risks=[r for r in risks if r['vehicle'] in ids or any(i in r['id'] for i in ids)]
 kind=next((k for k,words in [('battery',['배터리','잔량']),('link',['통신','끊']),('unstable',['흔들','기울','자세']),('separation',['간격','충돌']),('fault',['고장'])] if any(w in query for w in words)),None)
 if kind:risks=[r for r in risks if r['kind'].startswith(kind)]
 top=risks[0] if risks else None
 recommendations=[]
 if top:
  key=top['kind'].split('-')[0]
  recommendations=[{'number':i,'title':title,'explanation':text} for i,(title,text) in enumerate(ACTIONS.get(key,ACTIONS['fault']),1)]
 reply=(f"{top['title']} · {top['vehicle']}\n근거: {top['evidence']}" if top else '현재 시뮬레이션 기준에서 질문에 해당하는 위험은 확인되지 않았습니다. 위험이 없다는 보장은 아닙니다. 관측한 기체·증상·시각을 알려주세요.')
 reply+='\n'+'\n'.join(f"{r['number']}. {r['title']}: {r['explanation']}" for r in recommendations)
 reply+='\n시연 기준에 따른 검토 제안이며 자동 승인·이동 명령은 실행하지 않습니다.'
 return {'reply':reply,'answer_type':'safety_risk','recommendations':recommendations,'evidence':risks,'clarification_questions':[] if top else ['관측한 기체 번호와 증상·발생 시각을 알려주세요.'],'clarification_context':query[-6000:] if not top else None,'web_sources':[PX4] if top else [],'executed':False,'llm_used':False,'retrieval_method':'live_safety_signals'}
