"""Explain recorded decisions without inferring physical root causes."""
import re
from vehicle_briefing import brief

def explain(query,snapshot):
    ids=re.findall(r'(?:UAV|USV)-\d{2}',query.upper())
    vehicles=snapshot.get('vehicles',[])
    faulty=[v for v in vehicles if v.get('fault') or v.get('readiness',{}).get('operational_state')=='unavailable']
    chosen=[v for v in vehicles if v['id'] in ids]
    questions=[]
    if ids and len(chosen)!=len(set(ids)):questions=['등록된 기체 번호를 알려주세요.']
    elif not ids:
        state_only=not any(w in query for w in ('고장','수행불가','수행 불가'))
        if state_only:questions=['어느 기체의 상태를 볼까요? 기체 번호를 알려주세요.']
        elif len(faulty)==1:chosen=faulty
        elif faulty:questions=['어느 기체의 이유를 볼까요? '+', '.join(v['id'] for v in faulty)]
        else:questions=['현재 수행불가 기체가 확인되지 않습니다. 확인할 기체 번호를 알려주세요.']
    evidence=[];lines=[]
    for v in chosen if not questions else []:
        r=v.get('readiness',{});p=v.get('telemetry') or {}
        reason=r.get('reason','판정 근거 없음')
        evidence.append({'vehicle':v['id'],'source':'current_state','available':r.get('available'),'operational_state':r.get('operational_state'),'reason':reason,'connected':v.get('connected'),'age_seconds':v.get('age_seconds'),'battery_percent':r.get('battery_percent'),'fault_type':v.get('fault_type'),'fault_phase':(v.get('fault') or {}).get('phase'),'roll':p.get('roll'),'pitch':p.get('pitch')})
        unavailable=r.get('operational_state')=='unavailable'
        info=brief(v)
        lines.append(f"{v['id']}: {info['title']}\n근거: {info['evidence']}")
        lines.append(f"{v['id']}: "+(f'수행불가 판정 이유는 “{reason}”입니다.' if unavailable else '현재 수행불가로 판정되어 있지 않습니다.'))
        if v.get('fault'):
            lines.append(f"근거: 시뮬레이션 고장 상태 등록 · 종류 {v.get('fault_type','정보 없음')} · 단계 {v['fault'].get('phase','정보 없음')}.")
            lines.append('등록된 시연 고장 종류를 설명한 것이며 실제 장치의 물리적 고장 원인을 진단한 것은 아닙니다.')
        elif not v.get('connected'):
            age=v.get('age_seconds')
            lines.append('근거: '+(f'마지막 수신 이후 {age:.1f}초 경과 · 연결 판정 기준 5초 미만.' if isinstance(age,(int,float)) else '수신 기록이 없습니다.'))
            lines.append('연결을 확인할 수 없다는 뜻이며 통신 단절 원인은 확인되지 않았습니다.')
        else:
            lines.append(f"근거: 현재 상태의 판정 사유 “{reason}” · 현재 임무 {r.get('task','정보 없음')}.")
        if r.get('battery_percent') is not None:lines.append(f"배터리 {r['battery_percent']}%는 시뮬레이션 추정값입니다.")
        lines.append('추가 로그가 없으므로 실제 고장 원인은 확정하지 않습니다.')
    return {'reply':'\n'.join(questions or lines),'answer_type':'fault_explanation','evidence':evidence,'recommendations':[],'clarification_questions':questions,'clarification_context':query[-6000:] if questions else None,'web_sources':[],'executed':False,'llm_used':False,'retrieval_method':'current_state_evidence','model_note':'실시간 상태 근거 설명; 원인 진단 아님'}

def is_reason_question(text):
    return any(w in text for w in ('왜','이유','원인','근거','고장 설명','고장설명')) and (any(w in text for w in ('고장','수행불가','수행 불가','방어중','방어 중','대기','복귀','상태','통신','배터리','흔들','추진')) or bool(re.search(r'(?:UAV|USV)-\d{2}',text,re.I)))
