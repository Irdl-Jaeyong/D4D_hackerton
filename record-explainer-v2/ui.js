'use strict';
const State=globalThis.RecordUIState, byId=id=>document.getElementById(id);
let records=[],selected=null,busy=false,refreshing=false;
let syncConversationTarget=null;
let playbackFrame=null,playing=false,playTimer=null;
const pendingRead=new Set(), feedback=byId('feedback'), history=[], measurement=State.createMeasurement();

async function api(path,options) {
  const controller=new AbortController(), timer=setTimeout(()=>controller.abort(),60000);
  try {
    let response;
    try {response=await fetch(path,{...options,signal:controller.signal});}
    catch(e) {throw Error(e.name==='AbortError'?'요청 시간이 초과됐습니다.':'데모 서버에 연결할 수 없습니다.');}
    let body;try{body=await response.json();}catch{throw Error('서버 응답을 해석할 수 없습니다.');}
    if(!response.ok)throw Error(typeof body.detail==='string'?body.detail:'입력을 확인하세요.');
    return body;
  } finally {clearTimeout(timer);}
}
function tell(text){feedback.textContent=text;}
const groupNameKey='d4d.group-display-names.v1';
let groupNames=Object.create(null);
try{
  const saved=JSON.parse(localStorage.getItem(groupNameKey)||'{}');
  if(saved&&typeof saved==='object'&&!Array.isArray(saved))
    for(const [key,value] of Object.entries(saved))if(typeof value==='string'&&value.trim()&&value.length<=40)groupNames[key]=value;
}catch{}
function groupLabel(name){return groupNames[name]||name.replace('장치','그룹');}
const recordNameKey='d4d.record-display-names.v1';
let recordNames=Object.create(null);
try{
  const saved=JSON.parse(localStorage.getItem(recordNameKey)||'{}');
  if(saved&&typeof saved==='object'&&!Array.isArray(saved))
    for(const [key,value] of Object.entries(saved))if(typeof value==='string'&&value.trim()&&value.length<=40)recordNames[key]=value;
}catch{}
function recordLabel(record){return recordNames[record.id]||record.id;}
function editName(host,current,key,kind){
  if(host.querySelector('input'))return;
  const input=document.createElement('input');input.className='inline-name';input.type='text';input.maxLength=40;input.value=current;
  input.setAttribute('aria-label',kind==='group'?'그룹 이름 변경':'기록 표시 이름 변경');
  host.replaceChildren(input);
  const stop=event=>event.stopPropagation();
  for(const type of ['click','dblclick','pointerdown'])input.addEventListener(type,stop);
  input.addEventListener('keydown',event=>{
    event.stopPropagation();
    if(event.isComposing||event.keyCode===229)return;
    if(event.key==='Escape'){event.preventDefault();render();return;}
    if(event.key!=='Enter')return;
    event.preventDefault();const value=input.value.trim();
    if(!value){input.setCustomValidity('이름을 입력하세요.');input.reportValidity();return;}
    const names=kind==='group'?groupNames:recordNames,next={...names,[key]:value};
    try{localStorage.setItem(kind==='group'?groupNameKey:recordNameKey,JSON.stringify(next));}
    catch{tell('이름을 저장하지 못했습니다. 브라우저 저장소 설정을 확인하세요.');return;}
    if(kind==='group')groupNames=next;else recordNames=next;
    render();tell('이름을 변경했습니다.');
  });
  input.addEventListener('input',()=>input.setCustomValidity(''));
  input.addEventListener('blur',()=>{if(input.isConnected)render();});
  input.focus();input.select();
}

function render() {
  const locked=busy||refreshing||pendingRead.size>0||!!measurement.active;
  for(const id of ['play-start','play-next','play-reset','play-auto'])byId(id).disabled=locked;
  byId('play-pause').disabled=!playing;
  byId('play-status').textContent=playbackFrame===null?'초기 합성 기록 표시 중':`합성 재생 ${playbackFrame+1}/3 · ${playing?'재생 중':'일시정지/종료'} · 표시 시각은 예시 시각입니다.`;
  const focusKey=document.activeElement?.dataset?.focusKey, mode=byId('filter').value, query=byId('search').value;
  selected=State.selected(records,mode,selected,query);
  const visible=State.visible(records,mode,query),cards=byId('cards');
  const openGroups=new Map([...cards.querySelectorAll('details')].map(el=>[el.dataset.group,el.open]));
  cards.replaceChildren();
  byId('count').textContent=`표시 ${visible.length}건 / 전체 ${records.length}건`;
  byId('metric-total').textContent=records.length;
  byId('metric-groups').textContent=new Set(records.map(r=>r.device)).size;
  byId('metric-read').textContent=records.filter(r=>r.read).length;
  byId('metric-unread').textContent=records.filter(r=>!r.read).length;
  for(const button of document.querySelectorAll('[data-filter]'))button.setAttribute('aria-pressed',String(button.dataset.filter===mode));
  const groups=new Map();
  for(const r of visible){if(!groups.has(r.device))groups.set(r.device,[]);groups.get(r.device).push(r);}
  for(const [name,items] of groups){
    const group=document.createElement('details');group.className='record-group';group.dataset.group=name;
    group.open=openGroups.get(name)??true;
    const title=document.createElement('summary');title.textContent=`${groupLabel(name)} · ${items.length}건`;title.title='더블클릭으로 이름 변경';title.ondblclick=event=>{event.preventDefault();editName(title,groupLabel(name),name,'group');};group.append(title);
    for(const r of items){
      const b=document.createElement('button');b.type='button';b.className='device';b.dataset.focusKey=`card-${r.id}`;
      b.setAttribute('aria-pressed',String(selected===r.id));b.setAttribute('aria-controls','detail');
      const label=document.createElement('span');label.textContent=recordLabel(r);label.title='더블클릭으로 이름 변경';
      const read=document.createElement('span');read.className='read-dot';read.textContent=r.read?'읽음':'표시 없음';
      b.append(label,read);b.title=`${r.device} · ${r.status} · ${r.time}`;
      b.onclick=event=>{if(event.target.closest('input'))return;selected=r.id;clearTimeout(b.selectTimer);b.selectTimer=setTimeout(()=>{if(!b.querySelector('input'))render();},500);};b.ondblclick=event=>{event.preventDefault();event.stopPropagation();clearTimeout(b.selectTimer);editName(label,recordLabel(r),r.id,'record');};group.append(b);
    }
    cards.append(group);
  }
  if(!visible.length){const empty=document.createElement('p');empty.textContent=records.length?'검색·필터 결과가 없습니다. 필터 초기화로 전체를 볼 수 있습니다.':'기록이 아직 없습니다. 기록 새로고침을 이용하세요.';cards.append(empty);}
  const recent=byId('recent-records');recent.replaceChildren();
  for(const [index,r] of [...visible].sort((a,b)=>b.time.localeCompare(a.time)).entries()){
    const row=document.createElement('tr');if(r.id===selected)row.className='selected';
    const number=document.createElement('td');number.textContent=index+1;
    const idCell=document.createElement('td'),button=document.createElement('button');button.type='button';button.className='table-record';button.textContent=recordLabel(r);button.onclick=()=>{selected=r.id;render();byId('detail').focus();};idCell.append(button);
    const group=document.createElement('td');group.textContent=groupNames[r.device]||r.device.replace('장치 ','');
    const time=document.createElement('td');time.textContent=new Intl.DateTimeFormat('ko-KR',{timeZone:'Asia/Seoul',year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',second:'2-digit',hourCycle:'h23'}).format(new Date(r.time));
    const read=document.createElement('td');read.textContent=r.read?'있음':'없음';if(r.read)read.className='read-yes';
    row.append(number,idCell,group,time,read);recent.append(row);
  }
  if(!visible.length){const row=document.createElement('tr'),cell=document.createElement('td');cell.colSpan=5;cell.textContent='표시할 기록이 없습니다.';row.append(cell);recent.append(row);}
  const area=byId('detail');area.replaceChildren();const record=records.find(r=>r.id===selected);
  byId('target').textContent=record?`질문 대상: ${recordLabel(record)}`:'질문 대상 없음';
  byId('selected-title').textContent=record?`선택 기록 · ${recordLabel(record)}`:'선택 기록 없음';
  byId('send').disabled=busy||!record;byId('send').setAttribute('aria-label',busy?'설명 생성 중':'질문 보내기');byId('send').setAttribute('aria-busy',String(busy));
  byId('assistance').disabled=busy||!!measurement.active;
  byId('summary-send').disabled=busy||refreshing||!records.length||!byId('assistance').checked;
  byId('refresh').disabled=refreshing||pendingRead.size>0;byId('refresh').textContent=refreshing?'불러오는 중…':'기록 새로고침';
  for(const entry of history)if(entry.retry)entry.retry.disabled=busy;
  if(record){
    const dl=document.createElement('dl');
    for(const[label,value]of [['대상',record.device],['기록 ID',record.id],['발생 시각',record.time],['출처','합성 시험 기록'],['원본 상태',record.status],['확인 표시',record.read?'읽음':'읽지 않음'],['해결 여부',record.resolution]]){const dt=document.createElement('dt'),dd=document.createElement('dd');dt.textContent=label;dd.textContent=value;dl.append(dt,dd);}
    const pre=document.createElement('pre');pre.textContent=record.raw;
    const button=document.createElement('button');button.type='button';button.dataset.focusKey=`read-${record.id}`;
    button.textContent=record.read?'읽음 표시됨':pendingRead.has(record.id)?'표시 중…':'읽음 표시';
    button.disabled=record.read||pendingRead.has(record.id)||refreshing;
    button.onclick=()=>markRead(record.id);area.append(dl,pre,button);
  } else area.textContent='표시할 원본 기록이 없습니다.';
  if(focusKey){const target=[...document.querySelectorAll('[data-focus-key]')].find(el=>el.dataset.focusKey===focusKey&&!el.disabled);
    (target||cards.querySelector('[aria-pressed="true"]')||cards.querySelector('button')||byId('filter')).focus();}
  renderMeasurement();
  if(syncConversationTarget)syncConversationTarget();
}
async function refreshRecords() {
  if(refreshing||pendingRead.size)return;refreshing=true;render();
  try{const data=await api(playbackFrame===null?'/api/records':`/api/playback?frame=${playbackFrame}`);if(!Array.isArray(data.records))throw Error('기록 목록 형식이 잘못됐습니다.');records=data.records;render();tell('서버의 원본·읽음 표시를 새로 확인했습니다.');return true;}
  catch(e){tell(`${e.message} 이미 표시된 원본은 유지합니다. 기록 새로고침으로 재시도하세요.`);}
  finally{refreshing=false;render();}
}
async function markRead(id) {
  if(refreshing||pendingRead.has(id))return;pendingRead.add(id);render();
  try{await api(`/api/records/${encodeURIComponent(id)}/read`,{method:'POST'});records=State.markRead(records,id);tell('');}
  catch(e){tell(`${id}: ${e.message} 읽음 표시를 다시 시도할 수 있습니다.`);}
  finally{pendingRead.delete(id);render();}
}
function appendText(parent,text,cls){const p=document.createElement('p');p.textContent=text;if(cls)p.className=cls;parent.append(p);return p;}
async function explain(snapshot,{clearInput=false}={}) {
  if(busy)return;
  if(!byId('assistance').checked){tell('LLM 보조 없는 조건에서는 설명을 요청할 수 없습니다.');return;}
  if(!records.some(r=>r.id===snapshot.id&&r.time===snapshot.time)){tell('원래 질문의 기록이 없거나 시각이 달라 재시도할 수 없습니다.');return;}
  if(clearInput)byId('question').value='';
  busy=true;measurement.question();byId('chat-empty')?.remove();
  const box=document.createElement('article');box.className='exchange';box.setAttribute('aria-label',`질문 ${history.length+1} · ${snapshot.id}`);
  appendText(box,`사용자 · ${snapshot.id}`,'message-meta user-meta');
  appendText(box,snapshot.question,'user-message');
  const status=appendText(box,'응답 대기 중…','muted'),entry={snapshot,box,status,retry:null};history.push(entry);byId('history').append(box);render();byId('history').scrollTop=byId('history').scrollHeight;tell(`${snapshot.id}에 대한 설명을 생성 중입니다.`);
  try{
    const liveQuestion = /(현재|실시간|지금|전체|기체|드론|uav|usv|함선|가제보|gazebo)/i.test(snapshot.question) && /(상태|브리핑|요약|위치|속도|연결)/.test(snapshot.question);
    if (liveQuestion) {
      const result = await api('/api/gazebo/briefing', {method:'POST'});
      status.textContent='Gazebo · 실제 상태 브리핑'; status.className='message-meta';
      appendText(box,result.answer,'assistant-message');
      appendText(box,`출처: 실제 Gazebo ROS 텔레메트리 · 조회 시각: ${result.generated_at}\n수신 데이터를 코드로 집계한 요약입니다. LLM 판단이나 합성 기록 설명이 아닙니다.`,'muted');
      tell('실제 Gazebo 상태로 브리핑했습니다.');
      return;
    }
    const result=await api('/api/explain',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({record_id:snapshot.id,question:snapshot.question})});
    if(!State.validEvidence(result,snapshot))throw Error('응답의 근거가 원래 질문 기록과 일치하지 않습니다. 설명을 표시하지 않습니다.');
    status.textContent=`AI · ${result.answerable?'기록 설명':'확인 불가'}`;status.className='message-meta';
    appendText(box,result.answer,'assistant-message');
    appendText(box,`원본 인용: ${result.supporting_quotes.join(' / ')||'근거 부족'}\n근거: ${result.evidence.record_id} · ${result.evidence.record_time}\n생성 시각: ${result.generated_at}\n${result.notice}`,'muted');
    const evidence=document.createElement('button');evidence.className='evidence-link';evidence.type='button';evidence.textContent=`원본 ${snapshot.id} 확인`;
    evidence.onclick=()=>{if(!records.some(r=>r.id===snapshot.id)){tell('이 답변은 이전 재생 단계의 기록입니다. 답변에 표시된 원본 인용과 시각을 확인하세요.');return;}byId('filter').value='all';byId('search').value='';selected=snapshot.id;render();byId('detail').focus();tell('이 답변의 원본 기록을 선택했습니다.');};box.append(evidence);
    tell(`${snapshot.id}의 설명을 받았습니다. 현재 선택 ${selected||'없음'}과는 별도로 이 질문에 연결되어 있습니다.`);
  }catch(e){status.textContent=`설명 실패: ${e.message}`;status.className='error';const retry=document.createElement('button');retry.type='button';retry.textContent=`같은 질문 재시도 · ${snapshot.id}`;retry.onclick=()=>explain(snapshot);entry.retry=retry;box.append(retry);tell(e.message);}
  finally{busy=false;render();byId('history').scrollTop=byId('history').scrollHeight;}
}
function renderMeasurement(){const active=!!measurement.active;byId('measure-start').disabled=active||busy||refreshing||pendingRead.size>0||!records.length;byId('measure-stop').disabled=!active||busy;byId('measure-export').disabled=!measurement.trials.length||active;
  byId('measure-status').textContent=active?`측정 중 · ${measurement.active.mode} · UI 클릭 ${measurement.active.clicks}회`:`완료된 측정 ${measurement.trials.length}건 · 새로고침하면 사라집니다.`;}
byId('filter').onchange=render;byId('search').oninput=render;
for(const button of document.querySelectorAll('[data-filter]'))button.onclick=()=>{byId('filter').value=button.dataset.filter;render();};byId('reset').onclick=()=>{byId('filter').value='all';byId('search').value='';render();tell('검색·필터만 초기화했습니다. 읽음과 질문 이력은 유지합니다.');};byId('refresh').onclick=refreshRecords;
byId('assistance').onchange=()=>{byId('chat-panel').hidden=!byId('assistance').checked;byId('summary-panel').hidden=!byId('assistance').checked;render();};
async function summarizeCurrent(){
  if(busy||!byId('assistance').checked)return;
  const frame=playbackFrame,snapshot=records.map(r=>({...r}));
  busy=true;measurement.question();render();
  const status=byId('summary-status'),area=byId('summary-result');
  area.replaceChildren();status.textContent='전체 기록 요약 생성 중…';
  try{
    const data=await api('/api/summary',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(frame===null?{}:{playback_frame:frame})});
    const ids=Array.isArray(data.items)?data.items.map(x=>x.record_id):[];
    if(data.synthetic!==true||data.playback_frame!==frame||ids.length!==snapshot.length||new Set(ids).size!==snapshot.length||
      !snapshot.every(r=>data.items.some(x=>x.record_id===r.id&&x.record_time===r.time)))throw Error('전체 요약의 기록 근거가 일치하지 않습니다.');
    for(const item of data.items){
      const r=snapshot.find(r=>r.id===item.record_id);
      if(typeof item.summary!=='string'||!Array.isArray(item.supporting_quotes)||!item.supporting_quotes.length||
        !item.supporting_quotes.every(q=>typeof q==='string'&&q.length>=4&&(r.raw.includes(q)||r.status.includes(q))))throw Error('전체 요약의 원본 인용을 확인할 수 없습니다.');
    }
    appendText(area,`${data.overview}\n요약 대상: ${frame===null?'초기 기록':`합성 재생 ${frame+1}/3`} · ${snapshot[0].time}`);
    for(const item of data.items){
      const box=document.createElement('article');box.className='exchange';
      appendText(box,`${item.device} · ${item.summary}`);
      appendText(box,`근거: ${item.record_id} · ${item.record_time}\n원본 인용: ${item.supporting_quotes.join(' / ')}`,'muted');
      const button=document.createElement('button');button.type='button';button.textContent=`원본 ${item.record_id} 확인`;
      button.onclick=()=>{if(!records.some(r=>r.id===item.record_id)){tell('이 요약은 이전 재생 단계의 기록입니다. 표시된 원본 인용과 시각을 확인하세요.');return;}byId('filter').value='all';byId('search').value='';selected=item.record_id;render();byId('detail').focus();};box.append(button);area.append(box);
    }
    appendText(area,`생성 시각: ${data.generated_at}\n${data.notice}`,'muted');status.textContent='전체 합성 기록 요약 완료';
  }catch(e){area.replaceChildren();status.textContent=`요약 실패: ${e.message} 버튼으로 재시도할 수 있습니다.`;}
  finally{busy=false;render();}
}
byId('summary-send').onclick=summarizeCurrent;
function pausePlayback(){playing=false;clearTimeout(playTimer);playTimer=null;render();}
async function showFrame(frame){
  const previous=playbackFrame;playbackFrame=frame;
  if(!await refreshRecords()){playbackFrame=previous;pausePlayback();return false;}
  byId('summary-status').textContent='기록 단계가 변경됐습니다. 이전 요약은 이전 시점의 설명입니다.';
  if(byId('play-auto').checked&&byId('assistance').checked)await summarizeCurrent();
  return true;
}
function schedulePlayback(){clearTimeout(playTimer);if(!playing)return;
  playTimer=setTimeout(async()=>{
    if(!playing)return;
    if(busy||refreshing||pendingRead.size||measurement.active){schedulePlayback();return;}
    if(playbackFrame===2){pausePlayback();return;}
    if(await showFrame(playbackFrame===null?0:playbackFrame+1))schedulePlayback();
  },5000);
}
byId('play-start').onclick=async()=>{if(busy||refreshing)return;playing=true;render();if(playbackFrame===null||playbackFrame===2)await showFrame(0);schedulePlayback();};
byId('play-pause').onclick=pausePlayback;
byId('play-next').onclick=async()=>{if(busy||refreshing)return;pausePlayback();await showFrame(playbackFrame===null?0:Math.min(2,playbackFrame+1));};
byId('play-reset').onclick=async()=>{if(busy||refreshing)return;pausePlayback();await showFrame(null);};
byId('ask').onsubmit=event=>{event.preventDefault();if(busy)return;try{explain(State.snapshot(records.find(r=>r.id===selected),byId('question').value),{clearInput:true});}catch(e){tell(e.message);}};
byId('question').addEventListener('keydown',event=>{
  if(event.key!=='Enter'||event.shiftKey||event.isComposing||event.keyCode===229)return;
  event.preventDefault();
  if(event.repeat||busy||byId('send').disabled)return;
  byId('ask').requestSubmit(byId('send'));
});
byId('measure-start').onclick=()=>{measurement.start(byId('assistance').checked?'with_llm':'without_llm',performance.now());render();};
byId('measure-stop').onclick=()=>{const row=measurement.stop(performance.now());render();tell(`측정 완료: ${row.elapsed_ms}ms / ${row.click_count}회`);};
byId('measure-export').onclick=()=>{const url=URL.createObjectURL(new Blob(['\uFEFF'+measurement.csv()],{type:'text/csv;charset=utf-8'}));const a=document.createElement('a');a.href=url;a.download='synthetic-record-measurements.csv';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);};
document.addEventListener('click',event=>{const target=event.target.closest('button,input,select,textarea');if(event.isTrusted&&target&&!target.id.startsWith('measure-')&&!target.disabled){measurement.click();renderMeasurement();}},true);
render();refreshRecords();

async function refreshSimulator() {
  try {
    const data=await api('/api/gazebo/state');
    const fresh=data.vehicles.filter(v=>v.connected && v.age_seconds<5);
    byId('sim-status').textContent=fresh.length ? `현재 Gazebo ${fresh.length}/${data.vehicles.length}대 상태 수신 중` : '현재 Gazebo 상태 수신 없음';
    byId('sim-values').replaceChildren();
    appendText(byId('sim-values'),'출처: 클론한 브랜치 · ROS 기체 텔레메트리','muted');
  } catch(e) {
    byId('sim-status').textContent='진단 API 확인 실패 — 현재 값 표시 중단';
    byId('sim-values').replaceChildren();
    appendText(byId('sim-values'),e.message,'muted');
  } finally {setTimeout(refreshSimulator,2000);}
}
refreshSimulator();


// Conversation archive is local to this browser and origin.
(()=>{
  const key='d4d.conversations.v1',area=byId('history'),selector=byId('conversation-list');
  let threads=[],active=null,restoring=false,target=null;
  let activeByRecord=Object.create(null);
  const notice=text=>{byId('conversation-status').hidden=!text;byId('conversation-status').textContent=text;};
  const makeId=()=>`${Date.now()}-${Math.random().toString(36).slice(2)}`;
  try{
    const data=JSON.parse(localStorage.getItem(key)||'null');
    if(data&&Array.isArray(data.threads)){
      threads=data.threads.filter(t=>t&&typeof t.id==='string'&&typeof t.title==='string'&&Array.isArray(t.messages));
      threads=threads.flatMap(thread=>{
        if(typeof thread.recordId==='string')return [thread];
        const groups=new Map();
        for(const message of thread.messages){const meta=(message.parts||[]).find(p=>typeof p.text==='string'&&p.text.startsWith('사용자 · '));if(!meta)continue;const id=meta.text.slice('사용자 · '.length);if(!groups.has(id))groups.set(id,[]);groups.get(id).push(message);}
        return [...groups].map(([recordId,messages])=>({id:makeId(),recordId,title:thread.title,messages}));
      });
      if(data.activeByRecord&&typeof data.activeByRecord==='object')activeByRecord=Object.assign(Object.create(null),data.activeByRecord);
    }
  }catch{notice('저장된 대화를 읽지 못했습니다.');}
  function persist(){try{localStorage.setItem(key,JSON.stringify({activeByRecord,threads}));notice('');}catch{notice('대화 이력을 저장하지 못했습니다. 브라우저 저장 공간을 확인하세요.');}}
  function options(){selector.replaceChildren();for(const thread of threads.filter(t=>t.recordId===target)){const option=document.createElement('option');option.value=thread.id;option.textContent=thread.title;selector.append(option);}selector.value=active||'';selector.disabled=busy||!target;byId('conversation-new').disabled=busy||!target;byId('conversation-delete').disabled=busy||!active;const title=byId('conversation-title');if(!title.querySelector('input'))title.textContent=threads.find(t=>t.id===active)?.title||'';}
  function restore(){
    restoring=true;area.replaceChildren();history.length=0;
    const thread=threads.find(t=>t.id===active);
    for(const message of thread?.messages||[]){
      const article=document.createElement('article');article.className='exchange';
      for(const part of message.parts||[]){
        if(typeof part.text!=='string')continue;
        if(part.tag==='p')appendText(article,part.text,['message-meta','user-meta','user-message','assistant-message','muted','error'].filter(c=>(part.cls||'').split(' ').includes(c)).join(' '));
        else if(part.tag==='button'&&part.text.startsWith('원본 ')){
          const button=document.createElement('button');button.type='button';button.className='evidence-link';button.textContent=part.text;
          button.onclick=()=>{const id=part.text.slice(3).replace(/ 확인$/,'');if(!records.some(r=>r.id===id)){tell('현재 목록에 해당 원본 기록이 없습니다.');return;}byId('filter').value='all';byId('search').value='';selected=id;render();byId('detail').focus();};article.append(button);
        }
      }
      area.append(article);
    }
    if(!area.children.length){const p=appendText(area,target?'이 항목의 대화를 시작하세요.':'왼쪽에서 기록을 선택하고 질문하세요.','chat-empty');p.id='chat-empty';}
    area.scrollTop=area.scrollHeight;observer.takeRecords();restoring=false;options();
  }
  function capture(){
    if(restoring)return;
    const thread=threads.find(t=>t.id===active);if(!thread)return;
    thread.messages=[...area.querySelectorAll('article.exchange')].map(article=>({parts:[...article.children].filter(el=>el.tagName==='P'||el.tagName==='BUTTON').map(el=>({tag:el.tagName.toLowerCase(),text:el.textContent,cls:el.className}))}));
    const question=area.querySelector('.user-message')?.textContent;
    if(question&&!thread.customTitle)thread.title=question.slice(0,40);persist();options();
    selector.disabled=busy||!target;byId('conversation-new').disabled=busy||!target;byId('conversation-delete').disabled=busy||!active;
  }
  const observer=new MutationObserver(capture);observer.observe(area,{childList:true,subtree:true,characterData:true});
  selector.onchange=()=>{if(busy){selector.value=active;return;}const next=selector.value;capture();active=next;activeByRecord[target]=active;restore();persist();};
  byId('conversation-new').onclick=()=>{if(busy||!target)return;capture();active=makeId();threads.unshift({id:active,recordId:target,title:'새 대화',messages:[]});activeByRecord[target]=active;restore();persist();};
  byId('conversation-delete').onclick=()=>{
    const thread=threads.find(t=>t.id===active);
    if(busy||!thread)return;
    if(!window.confirm(`“${thread.title}” 대화를 삭제할까요? 삭제한 이력은 복구할 수 없습니다.`))return;
    threads=threads.filter(t=>t.id!==active);
    active=threads.find(t=>t.recordId===target)?.id||null;
    if(!active){active=makeId();threads.unshift({id:active,recordId:target,title:'새 대화',messages:[]});}
    activeByRecord[target]=active;restore();persist();
  };
  function renameConversation(){
    const thread=threads.find(t=>t.id===active),host=byId('conversation-title');
    if(busy||!thread||host.querySelector('input'))return;
    const input=document.createElement('input');input.className='inline-name';input.value=thread.title;input.maxLength=80;input.setAttribute('aria-label','대화 제목 변경');host.replaceChildren(input);
    const cancel=()=>{host.textContent=thread.title;};
    input.onkeydown=event=>{
      event.stopPropagation();if(event.isComposing||event.keyCode===229)return;
      if(event.key==='Escape'){event.preventDefault();cancel();return;}
      if(event.key!=='Enter')return;
      event.preventDefault();const value=input.value.trim();if(!value){input.setCustomValidity('제목을 입력하세요.');input.reportValidity();return;}
      thread.title=value;thread.customTitle=true;cancel();persist();options();
    };
    input.oninput=()=>input.setCustomValidity('');input.onblur=()=>{if(input.isConnected)cancel();};input.focus();input.select();
  }
  byId('conversation-title').ondblclick=renameConversation;
  byId('conversation-title').onkeydown=event=>{if(event.key==='F2'){event.preventDefault();renameConversation();}};
  selector.ondblclick=renameConversation;
  syncConversationTarget=()=>{
    if(busy){selector.disabled=true;byId('conversation-new').disabled=true;byId('conversation-delete').disabled=true;return;}
    if(target===selected){options();return;}
    capture();target=selected;
    active=threads.find(t=>t.recordId===target&&t.id===activeByRecord[target])?.id||threads.find(t=>t.recordId===target)?.id||null;
    if(target&&!active){active=makeId();threads.unshift({id:active,recordId:target,title:'새 대화',messages:[]});}
    if(target)activeByRecord[target]=active;
    restore();persist();
  };
  syncConversationTarget();
})();
