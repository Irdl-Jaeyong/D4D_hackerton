"""Read-only current queue facts; excludes response assignments and tactics."""
import re

def briefing(query,snapshot):
    rank=re.search(r'(\d+)\s*순위',query)
    if not rank and not any(w in query for w in ('승인대기열','대기열','랜덤 공격','랜덤공격','어떤 공격','오는 상황')):return None
    queue=snapshot.get('approval_queue',[]);index=int(rank[1])-1 if rank else 0
    base={'answer_type':'queue_situation','recommendations':[],'web_sources':[],'executed':False,'llm_used':False,'retrieval_method':'live_approval_queue','question_intent':'status','response_policy':'현재 상황 사실과 근거만 설명. 공격 의도나 전투 대응을 추측하지 않음.'}
    if index<0 or index>=len(queue):return {**base,'reply':'요청한 순위의 승인대기 상황이 없어요. 현재 대기열을 확인해주세요.','evidence':[],'clarification_questions':['현재 표시된 순위를 알려주세요.'],'clarification_context':None}
    m=queue[index];card=m.get('card') or {};risk=m.get('risk') or {}
    facts={'mission_id':m['id'],'rank':index+1,'title':card.get('title'),'summary':card.get('summary'),'source':m.get('source'),'scenario':m.get('scenario'),'reported_offset':card.get('offset'),'target_world_current':m.get('target_world_current'),'risk_reason':risk.get('reason'),'risk_score':risk.get('score'),'resolved':m.get('resolved',False),'approved':bool(m.get('approved')),'unknown':card.get('unknown'),'created_at':m.get('created_at')}
    # Only simulator scenarios are supplied by this app; never assert real detection.
    reply=f"{index+1}순위 · 상황 #{m['id']} · {facts['title'] or '상황 확인 필요'}\n{facts['summary'] or '상황 설명 확인 필요'}\n근거: {facts['risk_reason'] or '판정 근거 확인 필요'}\n이 앱의 가상 시뮬레이션 상황이며 실제 공격 탐지나 적대 의도 판정은 아니에요."
    return {**base,'reply':reply,'queue_reference':facts,'evidence':[facts],'clarification_questions':[],'clarification_context':None}
