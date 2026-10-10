// Keep human selections stable when only live explanatory text changes.
function queueReviewKey(m) {
  if (!m) return 'none';
  const r=m.risk||{};
  return JSON.stringify([m.id,m.plan_revision||0,m.approved?.id||null,
    r.priority,r.score,r.scores,r.status,r.p0_reasons,r.missing,!!m.resolved]);
}
if(typeof module!=='undefined')module.exports={queueReviewKey};
