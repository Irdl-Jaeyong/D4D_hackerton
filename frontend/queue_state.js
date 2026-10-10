// Keep human selections stable when only live explanatory text changes.
function queueReviewKey(m) {
  if (!m) return 'none';
  const r=m.risk||{};
  return JSON.stringify([m.id,m.plan_revision||0,m.approved?.id||null,
    r.priority,r.score,r.scores,r.status,r.p0_reasons,r.missing,!!m.resolved]);
}
function responseExecutionRequest(m,optionId) {
  const plan=m?.options?.find(p=>p.id===optionId);
  if(!plan?.available||m.approved||m.resolved)throw Error('현재 실행할 수 없는 대응안입니다.');
  return {mission_id:m.id,option_id:optionId,plan_revision:m.plan_revision||0,
    human_confirmed:true,decision_source:'response_button'};
}
function reviewedMission(state, selectedId) {
  const active=state.active_mission || (state.mission?.approved ? state.mission : null);
  const queue=state.approval_queue || [];
  const selected=queue.find(m=>m.id===selectedId);
  if(selected)return selected;
  if(active)return active;
  return queue.find(m=>m.id===selectedId) || queue[0] || state.mission || null;
}
if(typeof module!=='undefined')module.exports={queueReviewKey,responseExecutionRequest,reviewedMission,queueSnapshot,needsPlanRefresh};

function queueSnapshot(previous,queue,now,filter='all',force=false) {
  if(previous&&!force&&previous.filter===filter&&now-previous.updatedAt<10000)return previous;
  const rank=m=>['P0','P1','P2','P3'].indexOf(m.risk?.priority);
  const sorted=[...queue].sort((a,b)=>
    (rank(a)<0?4:rank(a))-(rank(b)<0?4:rank(b)) ||
    (b.risk?.score??-1)-(a.risk?.score??-1) || b.created_at-a.created_at || a.id-b.id);
  return {updatedAt:now,filter,total:queue.length,items:sorted.filter(m=>filter==='all'||(m.risk?.priority||'unknown')===filter).slice(0,3)};
}

function needsPlanRefresh(m,revision,now) {
  return !!m&&!m.approved&&!m.resolved&&(now-(m.planned_at??m.created_at)>=10||m.basis_revision!==revision);
}
