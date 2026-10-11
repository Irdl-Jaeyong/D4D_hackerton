"""Shared factual summaries for all vehicle IDs and the three UI states."""
LABELS={'defending':'방어중','waiting':'대기·복귀','unavailable':'수행불가'}
PHASES={'pending':'고장 처리 대기','unstable':'비행 중단','returning':'복귀 중','landing':'착함 중','charging':'충전·정비 중','moored':'정비 대기','emergency_descent':'비상 하강','ditched':'수면 도달 · 회수 필요','drifting':'표류 중','failsafe_return':'비상 복귀 시연'}
def brief(v):
    r=v.get('readiness') or {};fault=v.get('fault') or {};state=r.get('operational_state');label=LABELS.get(state,'상태 확인 필요');reason=r.get('reason') or '판정 사유 미수신';task=r.get('task') or '현재 임무 미수신'
    if v.get('automatic_return'):
        title='자동 복귀·충전' if fault.get('phase')=='charging' else '자동 복귀'
        evidence=reason+' · '+('자동 복귀 준비' if fault.get('phase')=='pending' else PHASES.get(fault.get('phase'),'단계 미수신'))
        limit='예방적 복귀 · 충전 완료 후 자동 배정 가능'
    elif fault:
        title={'communication':'통신 두절','propulsion':'추진 고장','payload':'임무 장비 이상'}.get(v.get('fault_type'),reason)
        evidence='모의 고장 등록 · '+PHASES.get(fault.get('phase'),fault.get('phase') or '단계 미수신')
        limit='시뮬레이션 등록 상태 · 실제 고장 원인 진단 아님'
    elif not v.get('connected'):
        title='최신 상태 미수신';age=v.get('age_seconds');evidence=f'마지막 수신 {age:.1f}초 전 · 연결 기준 5초 미만' if isinstance(age,(int,float)) else '수신 기록 없음';limit='통신 단절의 실제 원인은 미확인'
    else:
        title=reason if state=='unavailable' else task
        evidence='현재 판정: '+reason
        limit='실제 위협·임무 성공을 확인한 뜻은 아님' if state=='defending' else '대기·복귀를 같은 색으로 표시 · 실제 단계는 현재 임무에 표시' if state=='waiting' else '판정 사유와 실제 고장 원인은 구분'
    return {'state':state,'label':label,'title':title+' · '+label,'evidence':evidence,'limit':limit,'task':task,'reason':reason,'source':'current_state'}
