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
test('pending situations show AI choices by default while active execution remains selectable',()=>{
  const {reviewedMission}=require('../frontend/queue_state.js');
  const pending={id:4},active={id:6,approved:{id:'observe'}};
  assert.equal(reviewedMission({mission:pending,approval_queue:[pending]},99),pending);
  assert.equal(reviewedMission({mission:active,active_mission:active,approval_queue:[pending]},pending.id),pending);
  assert.equal(reviewedMission({mission:active,active_mission:active,approval_queue:[pending]},null),pending);
  assert.equal(reviewedMission({mission:active,active_mission:active,approval_queue:[pending]},active.id),active);
  assert.equal(reviewedMission({mission:active,active_mission:active,approval_queue:[]},null),active);
  assert.equal(reviewedMission({mission:null,approval_queue:[]},pending.id),null);
});

test('queue shows only two ranked items and refreshes at ten seconds without losing backlog',()=>{
 const {queueSnapshot}=require('../frontend/queue_state.js');
 const make=(id,p,score,created)=>({id,created_at:created,risk:{priority:p,score}});
 const queue=[make(1,'P3',20,9),make(2,'P1',90,1),make(3,'P0',10,1),make(4,'P2',60,2),make(5,'P1',90,3)];
 const first=queueSnapshot(null,queue,0,'all');assert.deepEqual(first.items.map(m=>m.id),[3,5]);assert.equal(first.total,5);assert.equal(queue.length,5);
 const next=[...queue,make(6,'P0',100,4)];assert.equal(queueSnapshot(first,next,9999,'all'),first);
 assert.deepEqual(queueSnapshot(first,next,10000,'all').items.map(m=>m.id),[6,3]);
 assert.deepEqual(queueSnapshot(first,next,1,'P2').items.map(m=>m.id),[4]);
 assert.deepEqual(queueSnapshot(first,next,1,'all',true).items.map(m=>m.id),[6,3]);
});
test('automatic plan refresh skips execution and resolved situations and renews stale plans',()=>{
 const {needsPlanRefresh}=require('../frontend/queue_state.js');
 const m={planned_at:100,created_at:90,basis_revision:2};
 assert.equal(needsPlanRefresh(m,2,109),false);
 assert.equal(needsPlanRefresh(m,2,110),true);
 assert.equal(needsPlanRefresh(m,3,101),true);
 assert.equal(needsPlanRefresh({...m,approved:{id:'verify'}},3,200),false);
 assert.equal(needsPlanRefresh({...m,resolved:true},3,200),false);
});
test('main dashboard renders two queue cards and clicks select their own situation',()=>{
 const fs=require('node:fs'),vm=require('node:vm');
 const source=fs.readFileSync(require('node:path').join(__dirname,'../frontend/app.js'),'utf8');
 const {queueSnapshot}=require('../frontend/queue_state.js');
 const dom={};const node=(tag,text,className)=>({tag,text,className,children:[],append(...items){this.children.push(...items)},replaceChildren(){this.children=[]},setAttribute(){},addEventListener(type,handler){this[type]=handler}});
 const context={queueSnapshot,queueView:null,reviewMissionId:2,missionRequestPending:false,lastPlanRefresh:Date.now(),$:id=>dom[id]||(dom[id]=node('div')),element:node,selectSituation:id=>context.selected=id,Date,Map};
 vm.createContext(context);vm.runInContext(source.slice(source.indexOf('function priorityText('),source.indexOf('async function refreshQueuePlans(')),context);
 const approval_queue=Array.from({length:5},(_,i)=>({id:i+1,created_at:i,card:{title:'상황 '+i},risk:{priority:'P1',score:80}}));
 context.renderMissionReview({approval_queue,active_mission:null});
 assert.equal(dom.approvalQueue.children.length,2);assert.match(dom.queueCount.textContent,/전체 5건/);
 assert.deepEqual(dom.approvalQueue.children.map(card=>card.children[0].text),['1순위','2순위']);
 dom.approvalQueue.children[0].click();assert.equal(context.selected,5);
 const html=fs.readFileSync(require('node:path').join(__dirname,'../frontend/index.html'),'utf8');
 assert.match(html,/id="approvalQueue"/);assert.doesNotMatch(html,/id="priorityFilter"|id="refreshMission"|id="missionReview"/);
});
test('risk response executes the API-created card even when it is outside the visible top three',async()=>{
 const fs=require('node:fs'),vm=require('node:vm');const source=fs.readFileSync(require('node:path').join(__dirname,'../frontend/app.js'),'utf8');
 const created={id:99,risk_id:'UAV-03:fault',approved:null};let executed;
 const context={missionRequest:async()=>created,executeResponse:async(m,id)=>executed=[m.id,id],encodeURIComponent,lastState:{mission:{id:1,risk_id:'other'}}};
 vm.createContext(context);const start=source.indexOf('async function executeRiskResponse(');assert.notEqual(start,-1);
 vm.runInContext(source.slice(start,source.indexOf('async function executeResponse(',start)),context);
 await context.executeRiskResponse('UAV-03:fault','verify');assert.deepEqual(executed,[99,'verify']);
});
test('response controls clearly distinguish ready, pending, confirmed and unavailable',()=>{
 const {responseControlState}=require('../frontend/queue_state.js');
 const m={id:1,options:[{id:'verify',available:true},{id:'observe',available:false}]};
 assert.equal(responseControlState(m,'verify',null,null).disabled,false);
 assert.match(responseControlState(m,'verify',null,{mission_id:1,option_id:'verify'}).label,/요청 중/);
 assert.match(responseControlState({...m,approved:{id:'verify'}},'verify',null,null).label,/명령 전달/);
 assert.match(responseControlState(m,'observe',null,null).label,/기체 부족/);
 assert.equal(responseControlState(m,'verify',{id:2},null).disabled,false);
 assert.match(responseControlState(m,'verify',{id:2},null).label,/전환/);
});
test('AI candidate has its own status and expires without changing two base choices',()=>{
 const {responseExecutionRequest,responseControlState}=require('../frontend/queue_state.js');
 const ai={id:'ai',available:true,expires_at:Date.now()/1000+60};
 const m={id:9,plan_revision:3,ai_status:{state:'ready'},options:[{id:'observe',available:true},{id:'prepare',available:true},ai]};
 assert.equal(responseExecutionRequest(m,'ai').option_id,'ai');
 assert.equal(responseControlState(m,'ai',null,null).disabled,false);
 ai.expires_at=Date.now()/1000-1;
 assert.throws(()=>responseExecutionRequest(m,'ai'),/만료/);
 assert.equal(responseControlState(m,'ai',null,null).disabled,true);
 assert.equal(responseControlState(m,'prepare',null,null).disabled,false);
 assert.notEqual(queueReviewKey(m),queueReviewKey({...m,ai_status:{state:'pending'}}));
});
