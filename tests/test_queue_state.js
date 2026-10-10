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
