'use strict';
globalThis.runRecordStateTests = function () {
  const S=globalThis.RecordUIState,passed=[];
  function test(name,fn){fn();passed.push(name);}
  function assert(value){if(!value)throw Error('Assertion failed');}
  const records=[{id:'A',time:'t1',read:false,status:'unknown',raw:'original'}, {id:'B',time:'t2',read:true,status:'missing'}];
  test('empty filter and selected fallback',()=>{assert(S.selected(records,'read','A')==='B');assert(S.selected(records,'unread','A')==='A');assert(S.selected([],'all','A')===null);});
  test('read idempotence and immutable original',()=>{const next=S.markRead(records,'A'),again=S.markRead(next,'A');assert(records[0].read===false);assert(next[0].status===records[0].status&&next[0].raw===records[0].raw);assert(JSON.stringify(next)===JSON.stringify(again));});
  test('question snapshot remains on original selection',()=>{const snap=S.snapshot(records[0],' hello ');assert(snap.id==='A'&&snap.question==='hello');assert(Object.isFrozen(snap));const valid={answer:'text',answerable:true,evidence:{record_id:'A',record_time:'t1'},supporting_quotes:['original']};assert(S.validEvidence(valid,snap));assert(!S.validEvidence({...valid,evidence:{record_id:'B',record_time:'t2'}},snap));assert(!S.validEvidence({...valid,supporting_quotes:[12]},snap));});
  test('empty question rejected',()=>{let rejected=false;try{S.snapshot(records[0],'  ');}catch{rejected=true;}assert(rejected);});
  test('measurement clock clicks and duplicate start',()=>{const m=S.createMeasurement();m.click();m.start('without_llm',100);let duplicate=false;try{m.start('with_llm',200);}catch{duplicate=true;}assert(duplicate);m.click();m.click();const t=m.stop(1350);assert(t.elapsed_ms===1250&&t.click_count===2&&t.question_count===0);m.click();assert(m.trials[0].click_count===2);});
  test('CSV contains only aggregate completed trials',()=>{const m=S.createMeasurement();m.start('with_llm',0);m.question();m.click();assert(m.csv().split('\r\n').length===2);m.stop(2000);const csv=m.csv();assert(csv.includes('1,with_llm,2000,1,1'));assert(!csv.includes('hello')&&!csv.includes('record_id'));});
  return passed;
};
