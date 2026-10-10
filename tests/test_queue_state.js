const test=require('node:test');
const assert=require('node:assert/strict');
const {queueReviewKey}=require('../frontend/queue_state.js');
const card={id:1,plan_revision:0,risk:{priority:'P1',score:80,scores:{S:4,U:4,A:4},status:'evaluated',p0_reasons:[],missing:[],reason:'마지막 수신 1초'}};
test('live age explanation preserves reviewed selection',()=>{
  assert.equal(queueReviewKey(card),queueReviewKey({...card,risk:{...card.risk,reason:'마지막 수신 2초'}}));
});
test('new recommendation, priority or resolution requires fresh selection',()=>{
  for(const changed of [{...card,plan_revision:1},{...card,risk:{...card.risk,priority:'P0',p0_reasons:['제어 불능']}},{...card,resolved:true}])assert.notEqual(queueReviewKey(card),queueReviewKey(changed));
});
test('response selection directly builds a confirmed execution request',()=>{
  const {responseExecutionRequest}=require('../frontend/queue_state.js');
  const m={id:9,plan_revision:2,options:[{id:'verify',available:true}],approved:null};
  assert.deepEqual(responseExecutionRequest(m,'verify'),{mission_id:9,option_id:'verify',plan_revision:2,human_confirmed:true,decision_source:'response_button'});
  assert.throws(()=>responseExecutionRequest({...m,approved:{id:'verify'}},'verify'));
  assert.throws(()=>responseExecutionRequest({...m,options:[{id:'verify',available:false}]},'verify'));
});
test('newly created lower priority situation stays selected across polling',()=>{
  const {reviewedMission}=require('../frontend/queue_state.js');
  const old={id:1,scenario:'crossing'},created={id:2,scenario:'rescue'};
  const snapshot={mission:old,active_mission:null,approval_queue:[old,created]};
  assert.equal(reviewedMission(snapshot,created.id),created);
  assert.equal(reviewedMission({...snapshot,approval_queue:[{...old},{...created}]},created.id).id,created.id);
});
test('removed review falls back to the queue and active execution takes precedence',()=>{
  const {reviewedMission}=require('../frontend/queue_state.js');
  const pending={id:4},active={id:6,approved:{id:'observe'}};
  assert.equal(reviewedMission({mission:pending,approval_queue:[pending]},99),pending);
  assert.equal(reviewedMission({mission:active,active_mission:active,approval_queue:[pending]},pending.id),active);
  assert.equal(reviewedMission({mission:null,approval_queue:[]},pending.id),null);
});
