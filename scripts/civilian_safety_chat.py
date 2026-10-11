"""Civilian incident reporting only; no engagement or vehicle dispatch."""
import re

def briefing(question):
    if not any(w in question for w in ('공격','위협','접근 선박','선박이 접근','배가 접근')):return None
    missing=[]
    if not any(w in question for w in ('우현','좌현','전방','후방','정면')):missing.append('어느 방향에서 접근하나요?')
    if not re.search(r'\d+(?:\.\d+)?\s*(?:m|미터|km|킬로미터)',question,re.I):missing.append('거리는 얼마나 되나요?')
    guidance='사용자가 보고한 상황이며 실제 탐지나 공격 확정은 아니에요. 접근만으로 공격 의도를 판단할 수는 없어요. 위치·거리·접근 속도와 통신 응답을 확인하고, 선내 안전 담당자에게 관측 내용을 공유하세요. 인명 위험이 임박했다면 세부 확인을 기다리지 말고 선박의 비상 절차에 따라 경보·인명 보호와 관계 기관 연락을 진행하세요. 위험 여부와 후속 조치는 책임 운용자가 판단해야 해요.'
    if missing:guidance+=' '+' '.join(missing)+' 즉각적인 인명 위험이나 부상자가 있는지도 알려주세요.'
    return {'reply':guidance,'answer_type':'civilian_safety','reported_situation':question,'evidence':[{'source':'user_report','text':question,'verified_detection':False}],'recommendations':[],'clarification_questions':missing,'clarification_context':question[-6000:] if missing else None,'web_sources':[],'executed':False,'llm_used':False,'retrieval_method':'civilian_safety_checks','response_policy':'사용자 신고와 탐지 사실 구분. 민간 인명 안전·보고 확인만. 전투 기동·무장 대응·기체 배정 제안 금지.'}
