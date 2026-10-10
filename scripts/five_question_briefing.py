"""Five read-only dialogue routes, backed by live state; classifier is only a hint."""
import re
from collections import Counter
from question_intents import predict
from vehicle_briefing import brief
from fault_explanation import explain
from safety_risk_briefing import answer_risks

def route(message,snapshot,previous=None):
    query=(previous+'\n' if previous else '')+message
    prediction=predict(query)
    # Explicit semantic anchors override an experimental small-data classifier.
    intent=None
    if any(w in query for w in ('재개','재투입','다시 가능','다시 출동','다시 사용','해제 조건','복귀 조건','언제 복귀','복구하려','충전 끝','정비 끝')):intent='resume'
    elif any(w in query for w in ('왜','이유','원인','근거','어째서')):intent='reason'
    elif any(w in query for w in ('대응','어떻게','어떡','뭘 해야','뭘 하면','조치','처리')):intent='response'
    elif any(w in query for w in ('위험','이상 상황','문제 있는')):intent='risk'
    elif any(w in query for w in ('상태','뭐 하고','뭐하고','뭐 하는','무슨 임무','현재 임무','진행','대기 중인지','복귀 중인지','하는 일','뭐하는')):intent='status'
    elif prediction['score']>=.90 and prediction['margin']>=.25:intent=prediction['intent']
    if intent is None or intent=='unknown':return None
    if intent=='reason':result=explain(query,snapshot)
    elif intent in ('risk','response'):
        result=answer_risks(query,snapshot)
        if intent=='risk':
            result['recommendations']=[]
            result['reply']='\n'.join(f"{r['title']} · {r['vehicle']}\n근거: {r['evidence']}" for r in result['evidence'][:5]) or '현재 시연 기준에서 확인된 위험은 없어요. 실제로 안전하다는 보장은 아니에요.'
    else:
        ids=re.findall(r'(?:UAV|USV|SHIP)-\d{2}',query.upper());vehicles=snapshot.get('vehicles',[]);chosen=[v for v in vehicles if v['id'] in ids]
        questions=[];lines=[];evidence=[]
        if ids and len(chosen)!=len(set(ids)):questions=['등록된 기체 번호를 알려주세요.']
        elif intent=='resume' and not ids:questions=['어느 기체의 복귀·재개 조건을 확인할까요?']
        elif not ids:
            counts=Counter(brief(v)['label'] for v in vehicles);lines=['현재 상태: '+', '.join(f'{k} {n}대' for k,n in counts.items()),'기체 번호를 알려주면 현재 임무를 자세히 설명할게요.'];evidence=[{'state':k,'count':n} for k,n in counts.items()]
        for v in chosen if not questions else []:
            info=brief(v);r=v.get('readiness') or {};evidence.append({'vehicle':v['id'],**info,'connected':v.get('connected'),'available':r.get('available'),'battery_percent':r.get('battery_percent')});lines.append(v['id']+' · '+info['title']+'\n근거: '+info['evidence'])
            if intent=='resume':
                lines.append('재개 검토 조건: 최신 통신·위치 확인, 고장·정비 상태 확인, 복귀 에너지 여유와 현재 임무 확인, 운용자 승인.')
                lines.append('현재 시스템상 배정 가능해요. 실제 출동 전 경로와 복귀 조건을 별도로 확인해야 해요.' if r.get('available') else '현재 배정 가능으로 확인되지 않았어요. 자동 고장 해제나 출동은 하지 않아요.')
                lines.append('완료 시각과 실제 복구 시간은 제공되지 않아 언제 다시 가능한지는 확정할 수 없어요.')
        result={'reply':'\n'.join(questions or lines),'recommendations':[],'evidence':evidence,'clarification_questions':questions,'clarification_context':query[-6000:] if questions else None,'executed':False,'web_sources':[],'llm_used':False,'answer_type':intent,'retrieval_method':'live_state_five_intents'}
    result['question_intent']=intent;result['intent_prediction']=prediction
    result['response_policy']={'status':'현재 상태·임무 설명 하나','reason':'판정 이유와 근거 하나','risk':'확인된 위험 우선순위만 설명; 대응안 나열하지 않음','response':'확인된 위험의 안전 검토안 두 가지','resume':'검토 조건과 미확인 항목; 완료 시각 추측 금지'}[intent]
    return result
