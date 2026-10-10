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
if(typeof module!=='undefined')module.exports={queueReviewKey,responseExecutionRequest};
