const $=id=>document.getElementById(id);let history=[],connections={},lastState=null,lastScenarioStage=null;const cameraPickables=[],mapPickables=[];
function event(text){if(!$('events'))return;const li=document.createElement('li');li.textContent=`${new Date().toLocaleTimeString('ko-KR')} · ${text}`;$('events').prepend(li);while($('events').children.length>20)$('events').lastChild.remove();}
function bubble(text,role){const p=document.createElement('p');p.className='bubble '+role;p.textContent=text;$('messages').append(p);$('messages').scrollTop=$('messages').scrollHeight;return p;}
const stateLabels={defending:'방어중',waiting:'대기·복귀',unavailable:'수행불가'},stateColors={defending:'#2ce099',waiting:'#4aa8ff',unavailable:'#ff6b6b'};
const bandColors=['#55e7ef','#7ebaff','#ae97ff','#ffb567','#88ed9d'];
function contactLabel(t,ship){
  const a=Math.atan2(t.y-(ship?.y||0),t.x-(ship?.x||0))-(ship?.yaw||0),bearing=Math.atan2(Math.sin(a),Math.cos(a));
  const direction=Math.abs(bearing)<Math.PI/4?'전방':Math.abs(bearing)>3*Math.PI/4?'후방':bearing>0?'좌현':'우현';
  return `${t.display_name||'외부 선박'} · ${direction} · ${t.track_id}`;
}
function map(state){
  const c=$('map'),pixelRatio=window.devicePixelRatio||1;const width=Math.round(c.clientWidth*pixelRatio),height=Math.round(c.clientHeight*pixelRatio);if(c.width!==width)c.width=width;if(c.height!==height)c.height=height;const ctx=c.getContext('2d');ctx.clearRect(0,0,c.width,c.height);mapPickables.length=0;
  const live=state.vehicles.filter(v=>v.connected&&v.telemetry);
  const lead=live.find(v=>v.id==='SHIP-01'),ox=lead?.telemetry.x||0,oy=lead?.telemetry.y||0;
  const contacts=(state.scene?.situations||[]).filter(t=>t.source==='scripted_contact');
  const extent=Math.max(310,...contacts.map(t=>Math.max(Math.abs(t.x-ox),Math.abs(t.y-oy))*1.1),...live.map(v=>Math.max(Math.abs(v.telemetry.x-ox),Math.abs(v.telemetry.y-oy))*1.15));
  const left=36*pixelRatio,right=c.width-18*pixelRatio,top=18*pixelRatio,bottom=c.height-27*pixelRatio,steps=c.clientWidth<350?4:6;
  const point=(x,y)=>[left+(x-ox+extent)/(2*extent)*(right-left),bottom-(y-oy+extent)/(2*extent)*(bottom-top)];
  ctx.font=`${9*pixelRatio}px system-ui`;ctx.textAlign='center';ctx.fillStyle='#607f92';ctx.lineWidth=pixelRatio;
  for(let i=0;i<=steps;i++){
    const value=(i/steps*2-1)*extent,x=left+i/steps*(right-left),y=bottom-i/steps*(bottom-top);
    ctx.strokeStyle=i===steps/2?'#345367':'#1c3443';ctx.beginPath();ctx.moveTo(x,top);ctx.lineTo(x,bottom);ctx.stroke();
    ctx.beginPath();ctx.moveTo(left,y);ctx.lineTo(right,y);ctx.stroke();
    ctx.fillText(Math.round(value),x,bottom+17*pixelRatio);ctx.textAlign='right';ctx.fillText(Math.round(value),left-6*pixelRatio,y+3*pixelRatio);ctx.textAlign='center';
  }
  ctx.strokeStyle='#71889c66';ctx.setLineDash([5*pixelRatio,5*pixelRatio]);ctx.beginPath();
  for(let i=0;i<=80;i++){const a=i*Math.PI/40,[x,y]=point(ox+150*Math.cos(a),oy+150*Math.sin(a));i?ctx.lineTo(x,y):ctx.moveTo(x,y);}ctx.stroke();ctx.setLineDash([]);
  for(const t of contacts){
    const [x,y]=point(t.x,t.y),selected=t.mission_id===state.mission?.id,r=(selected?9:6)*pixelRatio;
    ctx.strokeStyle='#ff7777';ctx.fillStyle='#ff777733';ctx.lineWidth=(selected?2.5:1.5)*pixelRatio;
    ctx.beginPath();ctx.moveTo(x,y-r);ctx.lineTo(x+r,y);ctx.lineTo(x,y+r);ctx.lineTo(x-r,y);ctx.closePath();ctx.fill();ctx.stroke();
    ctx.textAlign='left';ctx.fillStyle='#ffaaaa';ctx.fillText(`${contactLabel(t,lead?.telemetry)} · ${Math.round(t.range_m)}m`,Math.max(left,Math.min(x+11*pixelRatio,c.width-180*pixelRatio)),Math.max(y-12*pixelRatio,12*pixelRatio));
  }
  for(const v of live){
    const t=v.telemetry,[x,y]=point(t.x,t.y),selected=v.id===selectedVehicle;
    const color=v.fault?'#fb8383':({UAV:'#63d8e3',USV:'#8fa9f7',SHIP:'#ead5a7'}[v.type]||'#fff');
    mapPickables.push({id:v.id,x,y});
    if(selected){ctx.strokeStyle='#65e9e8';ctx.lineWidth=1.5*pixelRatio;ctx.fillStyle='#65e9e822';ctx.beginPath();ctx.arc(x,y,10*pixelRatio,0,2*Math.PI);ctx.fill();ctx.stroke();}
    ctx.fillStyle=color;ctx.save();ctx.translate(x,y);ctx.rotate(-(t.yaw||0));
    if(v.type==='UAV'){ctx.beginPath();ctx.arc(0,0,(selected?4:3)*pixelRatio,0,2*Math.PI);ctx.fill();}
    else{ctx.beginPath();ctx.moveTo((v.type==='SHIP'?11:6)*pixelRatio,0);ctx.lineTo(-5*pixelRatio,-3*pixelRatio);ctx.lineTo(-5*pixelRatio,3*pixelRatio);ctx.closePath();ctx.fill();}ctx.restore();
    if(selected){ctx.textAlign='left';ctx.fillStyle='#c5f7f4';ctx.fillText(v.id,Math.min(x+12*pixelRatio,c.width-54*pixelRatio),Math.max(y-11*pixelRatio,12*pixelRatio));}
  }
}
function cameraOverlay(state){
  const c=$('cameraOverlay'),ctx=c.getContext('2d');ctx.clearRect(0,0,c.width,c.height);cameraPickables.length=0;
  if(state.camera_view==='inspect')return;
  if(!state.camera_available||!state.scene)return;
  const lead=state.vehicles.find(v=>v.id==='SHIP-01'&&v.connected);if(!lead)return;
  const cam=state.scene.camera,m=state.scene.motion,ship=lead.telemetry;
  const [cx,cy,cz]=cam.offset,cp=Math.cos(cam.pitch),sp=Math.sin(cam.pitch),ca=Math.cos(cam.yaw),sa=Math.sin(cam.yaw),tan=Math.tan(cam.horizontal_fov/2);
  function project(x,y,z){
    const dx=x-cx,dy=y-cy,dz=z-cz,along=dx*ca+dy*sa;
    const depth=along*cp-dz*sp;if(depth<=0)return null;
    const left=-dx*sa+dy*ca,up=along*sp+dz*cp;
    return [c.width*(.5-left/(2*depth*tan)),c.height*(.5-up/(2*depth*tan*c.height/c.width))];
  }
  function line(points,color,width=1){ctx.strokeStyle=color;ctx.lineWidth=width;ctx.beginPath();points.forEach((p,i)=>{const q=project(...p);if(q)(i?ctx.lineTo(...q):ctx.moveTo(...q));});ctx.stroke();}
  if($('showDome').checked&&state.formations?.uav==='hemisphere'){
    for(let ring=0;ring<m.hemisphere_latitudes_deg.length;ring++){
      const a=m.hemisphere_latitudes_deg[ring]*Math.PI/180,r=m.hemisphere_radius*Math.cos(a),z=m.hemisphere_center_height+m.hemisphere_radius*Math.sin(a);
      line(Array.from({length:81},(_,i)=>[r*Math.cos(i*Math.PI/40),r*Math.sin(i*Math.PI/40),z]),bandColors[ring]+'55');
    }
    // The local figure-eight template moves with UAV-01's formation slot.
    const elapsed=ship.x/m.ship_speed,baseLongitude=m.hemisphere_rotation_rate*elapsed;
    line(Array.from({length:121},(_,i)=>{
      const a=i*Math.PI/60,s=Math.sin(a),co=Math.cos(a),d=1+s*s;
      const lat=m.hemisphere_latitudes_deg[0]*Math.PI/180+m.figure_eight_latitude_amplitude*2*Math.sqrt(2)*co*s/d;
      const lon=baseLongitude+m.figure_eight_longitude_amplitude*co/d;
      return [m.hemisphere_radius*Math.cos(lat)*Math.cos(lon),m.hemisphere_radius*Math.cos(lat)*Math.sin(lon),m.hemisphere_center_height+m.hemisphere_radius*Math.sin(lat)];
    }),'#5bffffdd',2);
    for(let sector=0;sector<8;sector++){
      const a=sector*Math.PI/4;line(Array.from({length:31},(_,i)=>{const lat=i*Math.PI/60;return [m.hemisphere_radius*Math.cos(lat)*Math.cos(a),m.hemisphere_radius*Math.cos(lat)*Math.sin(a),m.hemisphere_center_height+m.hemisphere_radius*Math.sin(lat)];}),'#9ee9ff33');
    }
  }
  ctx.font='bold 18px system-ui';
  for(const t of state.scene.situations||[]){
    if(t.source!=='scripted_contact')continue;const q=project(t.x-ship.x,t.y-ship.y,Math.max(3,t.z||0));if(!q)continue;
    const selected=t.mission_id===state.mission?.id,r=selected?19:13;
    ctx.strokeStyle='#ff7777';ctx.fillStyle='#ff77772a';ctx.lineWidth=selected?3:2;
    ctx.beginPath();ctx.moveTo(q[0],q[1]-r);ctx.lineTo(q[0]+r,q[1]);ctx.lineTo(q[0],q[1]+r);ctx.lineTo(q[0]-r,q[1]);ctx.closePath();ctx.fill();ctx.stroke();
    const label=contactLabel(t,ship),detail=`${Math.round(t.range_m)}m · ${(t.speed_mps*1.944).toFixed(1)}kn · 모의 접촉`,width=ctx.measureText(label).width+16;
    const x=Math.max(4,Math.min(q[0]+r+8,c.width-width-4)),y=Math.max(4,Math.min(q[1]-26,c.height-52));
    ctx.fillStyle='#08131fed';ctx.fillRect(x,y,width,50);ctx.fillStyle='#ffaaaa';ctx.font='bold 18px system-ui';ctx.fillText(label,x+8,y+20);
    ctx.font='14px system-ui';ctx.fillStyle='#e7edf4';ctx.fillText(detail,x+8,y+40);ctx.font='bold 18px system-ui';
  }
  ctx.font='bold 13px system-ui';
  for(const v of state.vehicles){
    if(!v.connected)continue;const t=v.telemetry,q=project(t.x-ship.x,t.y-ship.y,t.z);if(!q)continue;
    const ring=(parseInt(v.id.split('-')[1],10)-1)%5;
    const color=stateColors[v.readiness?.operational_state]||'#fff';
    cameraPickables.push({id:v.id,x:q[0],y:q[1]});
    if(v.type==='UAV'){ctx.fillStyle=color;ctx.strokeStyle='#06121e';ctx.lineWidth=1;ctx.beginPath();ctx.arc(q[0],q[1],v.fault?3.5:v.id===selectedVehicle?3:2,0,Math.PI*2);ctx.fill();ctx.stroke();}
    if(v.id===selectedVehicle){ctx.strokeStyle=color;ctx.lineWidth=2;ctx.beginPath();ctx.arc(q[0],q[1],8,0,Math.PI*2);ctx.stroke();}
  }

}
function formationIcon(group,mode){
  const drawings={circle:'<ellipse cx="40" cy="24" rx="28" ry="18"/>',v:'<path d="M10 40L40 8L70 40"/>',columns:'<path d="M20 8V40M60 8V40"/>',fan:'<path d="M8 30Q40 -12 72 30M40 22V40"/>',hemisphere:'<path d="M8 38A32 30 0 0 1 72 38M24 38A16 30 0 0 1 56 38"/><ellipse cx="40" cy="38" rx="32" ry="7"/>',box:'<path d="M12 18L30 6H68V30L50 42H12ZM12 18H50V42M50 18L68 6M50 18V42M68 30H30V6"/>',triangle:'<path d="M40 5L8 42H72ZM40 17L23 37H57Z"/>',rings:'<ellipse cx="40" cy="11" rx="28" ry="7"/><ellipse cx="40" cy="24" rx="28" ry="7"/><ellipse cx="40" cy="37" rx="28" ry="7"/>'};
  return `<svg viewBox="0 0 80 48" width="80" height="48" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="2">${drawings[mode]||''}${group==='usv'?'<path d="M40 17L35 28H45Z" fill="currentColor"/>':''}</svg>`;
}
function formationControls(f){
  if(!f)return;
  for(const group of ['usv','uav']){
    const container=$(group+'Formation');
    if(!container.children.length){
      for(const [mode,label] of Object.entries(f.catalog[group])){
        const button=document.createElement('button');button.type='button';button.innerHTML=formationIcon(group,mode);const title=document.createElement('span');title.textContent=label;button.append(title);button.dataset.mode=mode;
        button.addEventListener('click',async()=>{
          const buttons=[...container.children];buttons.forEach(b=>b.disabled=true);
          try{const response=await fetch('/api/formations',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({group,mode,scenario_id:lastState?.mission?.id})});
            if(!response.ok)throw Error('대형 선택 실패');formationControls(await response.json());event(`${group==='usv'?'USV':'드론'} ${label} 대형으로 이동 요청`);
          }catch(err){event(err.message);}finally{buttons.forEach(b=>b.disabled=false);}
        });container.append(button);
      }
    }
    for(const button of container.children)button.setAttribute('aria-pressed',String(button.dataset.mode===f[group]));
    const status=f.status?.[group],valid=status?.mode===f[group];
    $(group+'Progress').textContent=valid?(status.moving?`${f.catalog[group][f[group]]}로 이동 중 · ${status.progress}% · 목표까지 최대 ${status.remaining_m}m`:`${f.catalog[group][f[group]]} 유지 중`):`${f.catalog[group][f[group]]} 전환 준비 중`;
  }
}
$('cameraView').addEventListener('change',async()=>{
  const select=$('cameraView');select.disabled=true;
  try{const r=await fetch('/api/camera/view',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({mode:select.value,vehicle_id:selectedVehicle})});if(!r.ok)throw Error('시점 변경 실패');}
  catch(err){event(err.message);if(lastState)select.value=lastState.camera_view||'wide';}
  finally{select.disabled=false;}
});
$('showDome').addEventListener('change',()=>{if(lastState)cameraOverlay(lastState);});
async function poll(){try{const r=await fetch('/api/state');if(!r.ok)throw Error();const s=reviewState(await r.json());lastState=s;if(!$('cameraView').disabled)$('cameraView').value=s.camera_view||'wide';renderVehicles(s);renderMission(s);$('connected').textContent=`${s.vehicles.filter(v=>v.connected).length} / ${s.vehicles.length} 연결`;$('cameraLive').textContent=s.camera_available?'● 실시간 수신':'영상 연결 대기';$('camera').style.display=s.camera_available?'block':'none';$('cameraEmpty').style.display=s.camera_available?'none':'block';if(s.camera_available)$('camera').src='/api/camera?t='+Date.now();map(s);cameraOverlay(s);formationControls(s.formations);for(const group of ['usv','uav'])for(const button of $(group+'Formation').children)button.disabled=(s.active_missions||[]).some(m=>m.approved&&!m.threats?.length);
const lead=s.vehicles.find(v=>v.id==='SHIP-01'&&v.connected);
if(lead&&s.scene.scenario){const t=lead.telemetry.x/s.scene.motion.ship_speed,phase=t%180;
const stage=phase<18?0:phase<80?1:phase<170?2:3,key=`${Math.floor(t/180)}-${stage}`;
if(key!==lastScenarioStage){event(['민간 배 접근: 충돌 예측 감시','교차 통항 구간: 위험을 예측한 USV가 우회','민간 배 통과 구간: 호위 위치 복귀','정상 호위 구간'][stage]);lastScenarioStage=key;}}
}catch{disconnectedDisplay();$('connected').textContent='백엔드 연결 끊김';document.querySelectorAll('.badge').forEach(b=>{b.className='badge';b.textContent='확인 불가';});$('fleetSummary').textContent='백엔드 연결 끊김 · 상태 확인 불가';document.querySelectorAll('#responseOptions [data-option],#aiResponseContent [data-option]').forEach(b=>b.disabled=true);$('finalApprove').disabled=true;$('submitApprovalCommand').disabled=true;$('cards').replaceChildren();$('vehicleDetails').textContent='연결 끊김 · 마지막 상태를 사용할 수 없습니다.';$('assignmentSummary').textContent='연결 끊김 · 배정 결과 확인 불가';$('assignmentReasons').replaceChildren();$('assignmentPlan').disabled=true;$('map').getContext('2d').clearRect(0,0,$('map').width,$('map').height);$('camera').style.display='none';$('cameraEmpty').style.display='block';$('cameraEmpty').textContent='백엔드 연결 끊김';$('cameraOverlay').getContext('2d').clearRect(0,0,1280,720);}finally{setTimeout(poll,500);}}
$('chatForm').addEventListener('submit',async e=>{e.preventDefault();const message=$('message').value.trim();if(!message)return;bubble(message,'user');$('message').value='';$('send').disabled=true;$('chatStatus').textContent='AI 분석 중 · 최초 요청은 로딩 시간이 걸릴 수 있습니다';try{const r=await fetch('/api/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({message,use_camera:$('useCamera').checked,history:history.slice(-8)})});const data=await r.json();if(!r.ok)throw Error(data.detail||'요청 실패');bubble(data.reply,'ai');history.push({role:'user',content:message},{role:'assistant',content:data.reply.slice(0,4000)});$('chatStatus').textContent=`${data.elapsed_seconds}초 · ${data.used_camera?'카메라 포함':'텍스트'} · 명령 실행 없음`;}catch(err){bubble(err.message,'ai error');$('chatStatus').textContent='요청 실패';}finally{$('send').disabled=false;}});

let selectedVehicle=null,missionRenderKey='',selectedResponse=null,reviewMissionId=null,missionRequestPending=false,queueView=null,plansRefreshing=false,responseExecuting=false,lastPlanRefresh=0,pendingExecution=null;
function reviewState(s){
  queueView=queueSnapshot(queueView,s.approval_queue||[],Date.now());
  const ids=new Set(queueView.items.map(m=>m.id));
  const m=reviewedMission({...s,approval_queue:(s.approval_queue||[]).filter(m=>ids.has(m.id))},reviewMissionId);
  reviewMissionId=m?.id??null;return {...s,mission:m};
}
function selectSituation(id){
  reviewMissionId=id;selectedResponse=null;missionRenderKey='';
  if(lastState){lastState=reviewState(lastState);renderMission(lastState);renderVehicles(lastState);$('missionFeedback').textContent=`✓ 선택됨 · #${lastState.mission.id} ${lastState.mission.card.title}`;$('missionFeedback').dataset.state='info';}
}
function priorityText(m){const index=queueView?.items.findIndex(item=>item.id===m.id)??-1;return index>=0?`${index+1}순위`:'실행 중';}
function renderMissionReview(s){
  queueView=queueSnapshot(queueView,s.approval_queue||[],Date.now());
  const seconds=Math.max(0,Math.ceil((10000-Date.now()+queueView.updatedAt)/1000));
  $('queueCount').textContent=`상위 ${queueView.items.length}건 / 전체 ${queueView.total}건`;
  $('queueRefresh').textContent=`자동 갱신 ${seconds}초`;
  $('activeMission').replaceChildren();$('approvalQueue').replaceChildren();
  const active=s.active_missions||(s.active_mission?[s.active_mission]:[]);
  $('fleetCapacity').textContent=`동시 임무 ${active.length}건 · 예비 UAV ${s.fleet_capacity?.UAV??'—'} / USV ${s.fleet_capacity?.USV??'—'}`;
  for(const m of active){const tasks=m.execution_tasks||m.approved.tasks,b=element('button',`${m.intervention?'결정 필요':m.cancel_requested?'복귀 중':'실행 중'} · #${m.id} ${m.card.title} · UAV ${tasks.filter(t=>t.vehicle.startsWith('UAV')).length} / USV ${tasks.filter(t=>t.vehicle.startsWith('USV')).length}`,'queue-active'+(reviewMissionId===m.id?' selected':''));b.type='button';b.disabled=missionRequestPending;b.setAttribute('aria-pressed',String(reviewMissionId===m.id));b.addEventListener('click',()=>selectSituation(m.id));$('activeMission').append(b);}
  $('operatorNotices').replaceChildren();
  for(const notice of s.operator_notices||[]){const b=element('button',`${notice.level==='decision'?'결정 필요':'자동 조치'} · ${notice.title} · ${notice.message}`,'operator-notice '+notice.level);b.type='button';b.addEventListener('click',()=>selectSituation(notice.mission_id));$('operatorNotices').append(b);}

  const live=new Map((s.approval_queue||[]).map(m=>[m.id,m]));
  for(const entry of queueView.items){const m=live.get(entry.id);if(!m)continue;
    const b=element('button',undefined,'queue-item'+(reviewMissionId===m.id?' selected':''));b.type='button';b.disabled=missionRequestPending;b.setAttribute('aria-pressed',String(reviewMissionId===m.id));
    b.append(element('span',priorityText(m),'priority-badge queue-rank-'+((queueView?.items.findIndex(item=>item.id===m.id)??-1)+1)),element('strong',`#${m.id} ${m.card.title}`),element('small',`${m.resolved?'원인 해소':m.risk?.score==null?'평가 불가':m.risk.score+'점'} · ${new Date(m.created_at*1000).toLocaleTimeString('ko-KR')}`));
    if(reviewMissionId===m.id)b.append(element('span','✓ 선택됨','selection-indicator'));
    b.addEventListener('click',()=>selectSituation(m.id));$('approvalQueue').append(b);
  }
  if(!queueView.items.length)$('approvalQueue').append(element('p','대기 중인 상황이 없습니다.','muted'));
  if(Date.now()-lastPlanRefresh>=10000)refreshQueuePlans(s);
}
async function refreshQueuePlans(s){
  if(plansRefreshing||responseExecuting||missionRequestPending)return;
  const ids=new Set(queueView?.items.map(m=>m.id)||[]);
  const cards=(s.approval_queue||[]).filter(m=>ids.has(m.id)&&needsPlanRefresh(m,s.formations.revision,Date.now()/1000));
  plansRefreshing=true;lastPlanRefresh=Date.now();
  try{await Promise.allSettled(cards.map(async m=>{const r=await fetch('/api/mission/'+m.id+'/refresh',{method:'POST'});if(!r.ok)throw Error('자동 갱신 실패');}));}
  finally{plansRefreshing=false;}
}
function element(tag,text,className){const node=document.createElement(tag);if(text!==undefined)node.textContent=text;if(className)node.className=className;return node;}

function assignmentContext(s){
  const m=s.mission;if(!m)return {mission:null,plan:null,expired:false};
  return {mission:m,plan:m.approved?{...m.approved,tasks:m.execution_tasks||m.approved.tasks}:m.options.find(p=>p.id===$('assignmentPlan').value),expired:!m.approved&&Date.now()/1000-(m.planned_at??m.created_at)>60};
}
function assignmentText(v,context){
  const task=context.plan?.tasks.find(t=>t.vehicle===v.id);
  if(!v.connected||v.fault||v.readiness.operational_state==='unavailable')return '배정 제외 · '+v.readiness.reason;
  if(task)return (context.mission.approved?'승인 계획':'추천 기체')+' · '+task.task+(context.expired?' · 재계산 필요':'');
  if(v.readiness.assigned_mission_id)return `다른 임무 #${v.readiness.assigned_mission_id} · ${v.readiness.task}`;
  if(v.type==='SHIP')return '함선 운항 유지';
  if(!context.plan)return '상황 생성 후 평가';
  return '이번 안 미선택 · '+v.readiness.task;
}
function renderAssignment(s){
  const select=$('assignmentPlan'),plans=s.mission?.approved?[{...s.mission.approved,tasks:s.mission.execution_tasks||s.mission.approved.tasks}]:(s.mission?.options||[]),previous=select.value;
  if([...select.options].map(o=>o.value).join('|')!==plans.map(p=>p.id).join('|')){
    select.replaceChildren(...plans.map(p=>{const option=element('option',p.title);option.value=p.id;return option;}));
    select.value=plans.some(p=>p.id===previous)?previous:(plans[0]?.id||'');
  }else for(const option of select.options)option.textContent=plans.find(p=>p.id===option.value).title;
  const c=assignmentContext(s),m=c.mission,p=c.plan;
  $('assignmentPlan').disabled=!m||!!m.approved;
  if(m?.approved)$('assignmentPlan').value=m.approved.id;
  $('assignmentReasons').replaceChildren();
  if(!p){$('assignmentSummary').textContent='상황을 생성하면 선택 기체·제외 이유·대형 유지 근거를 여기서 확인할 수 있습니다.';return;}
  $('assignmentSummary').textContent=`${m.card.title} / ${p.title} · ${m.approved?'승인된 계획':c.expired?'추천 만료 · 재계산 필요':'승인 대기'} · USV ${s.formations.catalog.usv[p.formations.usv]} / 드론 ${s.formations.catalog.uav[p.formations.uav]}`;
  for(const t of p.tasks){const v=s.vehicles.find(v=>v.id===t.vehicle),item=element('div',undefined,'assignment-reason');
    item.append(element('strong',t.vehicle+' → '+t.task),element('small',t.reason+` · 직선 이동 추정 ${t.eta_seconds}초`));
    if(v&&(!v.connected||v.readiness.operational_state==='unavailable'))item.append(element('small','현재 상태 변경: '+v.readiness.reason+' · 다시 계산하세요.','offline'));
    $('assignmentReasons').append(item);
  }
  $('assignmentReasons').append(element('p','기타 기체: 선택한 호위 대형의 담당 위치 유지. 선택 이유는 연결·시뮬레이션 잔량·직선 ETA 및 복귀 여유에 근거합니다.','muted'));
}

function vehicleDetails(s){
  if(!selectedVehicle&&s.camera_view==='inspect')selectedVehicle=s.inspection_vehicle;
  const v=s.vehicles.find(v=>v.id===selectedVehicle);$('inspectVehicle').disabled=!v?.connected;
  const live=!!(v?.connected&&v.telemetry),t=live?v.telemetry:null;
  $('selectedTitle').textContent=v?'선택 기체 · '+v.id:'선택 기체';
  $('selectedConnection').textContent=v?(live?'● 연결됨':'● 수신 지연'):'선택 대기';
  $('selectedConnection').className=live?'online':'offline';
  $('selectedType').textContent=v?({UAV:'무인 항공기',USV:'무인 수상정',SHIP:'기준 선박'}[v.type]||v.type):'—';
  $('selectedHeight').textContent=t?Number(t.z||0).toFixed(1)+' m':'—';
  $('selectedSpeed').textContent=t&&Number.isFinite(t.speed)?t.speed.toFixed(2)+' m/s':'—';
  $('selectedAge').textContent=v?.age_seconds!=null?v.age_seconds.toFixed(1)+'초 전':'—';
  const battery=live&&Number.isFinite(v.readiness?.battery_percent)?v.readiness.battery_percent:null;
  $('selectedBattery').textContent=battery===null?(live?'데이터 없음':'—'):battery+'%'+(v.fault?.phase==='charging'?' · 충전 중':'');
  $('selectedBattery').className=battery!==null&&battery<20?'battery-low':battery!==null&&battery<35?'battery-warning':'';
  $('selectedBatteryMeter').hidden=battery===null;
  if(battery!==null)$('selectedBatteryMeter').value=Math.max(0,Math.min(100,battery));
  $('selectedEndurance').textContent=live&&Number.isFinite(v.readiness?.endurance_minutes)?v.readiness.endurance_minutes+'분':'—';

  $('selectedTask').textContent=v?(live?(v.fault?'모의 고장 · ':'')+v.readiness.task+' · '+v.readiness.reason:'연결 끊김 · 현재 위치를 확인할 수 없습니다.'):'목록이나 지도의 기체를 선택하세요.';
  $('positionId').textContent=v?.id||'기체 선택';
  for(const axis of ['X','Y','Z'])$('position'+axis).textContent=t?Number(t[axis.toLowerCase()]||0).toFixed(1):'—';

  $('cameraIdentity').textContent=s.camera_view==='inspect'?`${s.inspection_vehicle} · 기체 전방 1인칭 · ${stateLabels[s.vehicles.find(v=>v.id===s.inspection_vehicle)?.readiness.operational_state]||'상태 확인 필요'}`:v?`선택: ${v.id} · ${v.type==='UAV'?'드론':v.type==='USV'?'무인 수상정':'메인 함선'} · 선택 기체 버튼으로 1인칭 시점을 보세요.`:'기체나 목록을 클릭해 선택한 뒤 선택 기체 버튼으로 1인칭 시점을 보세요.';
  if(!v)return;
  const r=v.readiness,p=v.telemetry;
  $('faultToggle').disabled=v.type==='SHIP'||!!(v.fault&&v.type==='UAV'&&v.fault.phase!=='charging');$('faultToggle').textContent=v.fault?'정비 완료 · 고장 해제':'선택 기체 고장 주입';
  $('vehicleDetails').textContent=`${v.id} · ${v.fault?.phase==='charging'?'갑판 충전·정비 중 · ':''}${r.battery_percent===null?'잔량 데이터 없음':`시뮬레이션 잔량 ${r.battery_percent}% / 잔여 ${r.endurance_minutes}분`} · 마지막 수신 ${v.age_seconds===null?'없음':v.age_seconds.toFixed(1)+'초 전'} · ${v.fault?'모의 고장 · '+r.task:r.reason} · ${r.task}`+(p&&v.connected?` · 위치 (${p.x.toFixed(1)}, ${p.y.toFixed(1)}, ${(p.z||0).toFixed(1)})m · 기울기 ${(Math.max(Math.abs(p.roll||0),Math.abs(p.pitch||0))*180/Math.PI).toFixed(1)}°`:' · 위치 확인 불가');
  const context=assignmentContext(s),task=context.plan?.tasks.find(t=>t.vehicle===v.id);
  $('vehicleDetails').append(element('strong',assignmentText(v,context),'vehicle-assignment-title'));
  if(task){const margin=r.endurance_minutes*60-(2*task.eta_seconds+300);
    $('vehicleDetails').append(element('div',`선정 당시 근거: ${task.reason}`),element('div',`직선 도달 추정 ${task.eta_seconds}초 · 현재 잔여시간 기준 왕복+5분 차감 여유 ${Math.floor(margin/60)}분 (추정)`),element('small','도달 시간은 상황 생성 당시 계산값입니다. 안전 경로·임무 중단 비용·감시 공백 평가는 미구현입니다.'));
  }else if(context.plan&&v.type!=='SHIP'&&r.operational_state!=='unavailable'){
    $('vehicleDetails').append(element('small','이번 대응안에 선택되지 않았습니다. 기체별 점수 비교와 경로 평가는 아직 표시하지 않습니다.'));
  }

}
function vehicleIcon(type){
  const ns='http://www.w3.org/2000/svg',svg=document.createElementNS(ns,'svg');svg.setAttribute('viewBox','0 0 24 24');svg.setAttribute('class','vehicle-symbol');svg.setAttribute('aria-hidden','true');
  const path=document.createElementNS(ns,'path');path.setAttribute('d',type==='UAV'?'M8 8l8 8M16 8l-8 8M5 3a3 3 0 1 0 0 6 3 3 0 0 0 0-6M19 3a3 3 0 1 0 0 6 3 3 0 0 0 0-6M5 15a3 3 0 1 0 0 6 3 3 0 0 0 0-6M19 15a3 3 0 1 0 0 6 3 3 0 0 0 0-6':type==='USV'?'M3 14h18l-4 5H7zM8 14V8h7l3 6M2 22q3-3 6 0t6 0 6 0':'M3 13h18l-4 7H7zM7 13V7h10v6M11 7V3M2 23q3-3 6 0t6 0 6 0');path.setAttribute('fill','none');path.setAttribute('stroke','currentColor');path.setAttribute('stroke-width','1.4');path.setAttribute('stroke-linecap','round');path.setAttribute('stroke-linejoin','round');svg.append(path);return svg;
}
function renderVehicles(s){
  if(!selectedVehicle)selectedVehicle=(s.vehicles.find(v=>v.id==='UAV-01')||s.vehicles[0])?.id||null;
  renderAssignment(s);
  const initial=!Object.keys(connections).length;
  for(const v of s.vehicles){if(!initial&&connections[v.id]!==v.connected)event(`${v.id} ${v.connected?'연결 복구':'수신 지연'}`);connections[v.id]=v.connected;}
  if(initial)event(`Gazebo 연결 · ${s.vehicles.filter(v=>v.connected).length}대 상태 수신`);
  const filter=$('vehicleFilter').value,query=$('vehicleSearch').value.trim().toUpperCase();
  const groups=new Map([...$('cards').querySelectorAll('details')].map(n=>[n.dataset.type,n.open]));
  const focus=document.activeElement?.dataset.vehicle,fragment=document.createDocumentFragment();
  let count=0;
  for(const type of ['UAV','USV','SHIP']){
    const members=s.vehicles.filter(v=>v.type===type&&(!query||v.id.toUpperCase().includes(query))&&(filter==='all'||(stateLabels[filter]?v.readiness.operational_state===filter:filter==='attention'?(!v.connected||!!v.fault||(v.type!=='SHIP'&&!v.readiness.available)):v.type===filter)));
    if(!members.length)continue;count+=members.length;
    const group=element('details',undefined,'vehicle-group');group.dataset.type=type;group.open=groups.has(type)?groups.get(type):true;
    const title=element('summary',type);title.append(element('span',members.length+'대','group-count'));group.append(title);
    for(const v of members){
      const row=element('button',undefined,'vehicle-row'+(v.id===selectedVehicle?' selected':''));row.type='button';row.dataset.vehicle=v.id;row.setAttribute('aria-pressed',String(v.id===selectedVehicle));row.setAttribute('aria-label',v.id+' · '+(v.connected?'연결됨':'수신 지연')+(v.fault?' · 모의 고장':''));
      const status=element('i',undefined,'status-dot'+(!v.connected?' offline':v.fault?' fault':''));status.title=!v.connected?'수신 지연':v.fault?'모의 고장':'연결됨';
      const battery=v.connected&&Number.isFinite(v.readiness?.battery_percent)?v.readiness.battery_percent:null;
      const batteryLabel=element('span',battery===null?'—':battery+'%','battery-value'+(battery!==null&&battery<20?' battery-low':battery!==null&&battery<35?' battery-warning':''));
      batteryLabel.title=battery===null?(v.connected?'배터리 데이터 없음':'수신 지연 · 배터리 확인 불가'):'모의 배터리 잔량'+(v.fault?.phase==='charging'?' · 충전 중':'');
      row.setAttribute('aria-label',row.getAttribute('aria-label')+' · '+(battery===null?'배터리 확인 불가':'모의 배터리 '+battery+'%'));
      row.append(vehicleIcon(v.type),element('span',v.id),batteryLabel,status);group.append(row);
    }
    fragment.append(group);
  }
  if(!count)fragment.append(element('p','검색 결과가 없습니다.','empty-list'));
  $('cards').replaceChildren(fragment);
  if(focus){const row=[...$('cards').querySelectorAll('[data-vehicle]')].find(n=>n.dataset.vehicle===focus);row?.focus({preventScroll:true});}
  vehicleDetails(s);
  $('stateParts').replaceChildren();for(const [key,label] of Object.entries(stateLabels)){const b=element('button',label+' '+s.vehicles.filter(v=>v.readiness.operational_state===key).length);b.type='button';b.style.borderColor=stateColors[key];b.addEventListener('click',()=>{$('vehicleFilter').value=key;renderVehicles(s);});$('stateParts').append(b);}
  const support=s.vehicles.filter(v=>v.type!=='SHIP'),ready=support.filter(v=>v.readiness.available).length,connected=s.vehicles.filter(v=>v.connected).length;
  const attention=s.vehicles.filter(v=>!v.connected||v.fault||(v.type!=='SHIP'&&!v.readiness.available)).length;
  $('summaryTotal').textContent=s.vehicles.length;$('summaryConnected').textContent=connected;$('summaryAttention').textContent=attention;
  $('fleetSummary').textContent=`가용 ${ready} / ${support.length} · ${s.mission?(s.mission.approved?'계획 승인됨':'계획 승인 대기'):'실시간 상태 수신 중'}`;
  for(const button of document.querySelectorAll('[data-filter]'))button.setAttribute('aria-pressed',String(button.dataset.filter===filter));
}
function disconnectedDisplay(){
  $('randomAttack').disabled=true;
  for(const id of ['summaryConnected','summaryAttention','selectedHeight','selectedSpeed','selectedAge','selectedBattery','selectedEndurance','positionX','positionY','positionZ'])$(id).textContent='—';
  $('selectedBatteryMeter').hidden=true;$('selectedConnection').textContent='● 연결 끊김';$('selectedConnection').className='offline';$('selectedTask').textContent='현재 상태를 확인할 수 없습니다.';$('cameraLive').textContent='영상 연결 끊김';$('inspectVehicle').disabled=true;$('faultToggle').disabled=true;mapPickables.length=0;cameraPickables.length=0;lastState=null;
}
function renderMission(s){
  const attackFull=(s.approval_queue||[]).length>=(s.auto_scenarios?.max_pending||4),shipReady=s.vehicles.some(v=>v.type==='SHIP'&&v.connected);
  $('randomAttack').disabled=missionRequestPending||attackFull||!shipReady;
  $('randomAttack').title=attackFull?'대기열이 가득 찼습니다. 기존 상황을 종료하세요.':!shipReady?'함선 연결을 기다리는 중입니다.':'9개 시나리오 중 하나를 무작위로 발생시킵니다.';
  const m=s.mission,key=queueReviewKey(m);
  $('situationSummary').textContent=m?`${priorityText(m)} · ${m.card.title} · 상세`:'선택 상황 상세';
  renderMissionReview(s);$('cancelMission').disabled=missionRequestPending||!m;
  if(key!==missionRenderKey){
    missionRenderKey=key;$('situationCard').replaceChildren();$('responseOptions').replaceChildren();$('aiResponseContent').replaceChildren();
    if(!m){$('situationCard').append(element('p','가상 상황을 선택해 대응안 2개를 확인하세요.','muted'));}
    else{
      $('situationCard').append(element('strong',m.card.title),element('p',m.card.summary),element('p',m.threats?.length?`모의 외부 접촉 ${m.threats.length}개 · 대형 버튼으로 직접 대응 가능`:`함선 상대 위치 x ${m.card.offset[0]}m / y ${m.card.offset[1]}m`,'muted'),element('p',m.card.unknown,'scope-note'));
      if(m.affected_vehicles)$('situationCard').append(element('p',m.affected_vehicles.length?`모의 통신 영향: ${m.affected_vehicles.join(', ')}`:'영향을 줄 가용 기체 없음 · 구역 표시만 생성','scope-note'));
      $('situationCard').append(element('p',`${priorityText(m)} · ${m.risk?.score==null?'평가 불가':m.risk.score+' / 100점'}`,'priority-badge queue-rank-'+((queueView?.items.findIndex(item=>item.id===m.id)??-1)+1)));
      if(!m.options.length)$('responseOptions').append(element('p','함선의 최신 위치가 없어 추천을 생성할 수 없습니다. 연결되면 자동 갱신됩니다.'));
      for(const [i,plan] of (m.approved?[{...m.approved,tasks:m.execution_tasks||m.approved.tasks}]:visibleResponsePlans(m.options)).entries()){
        const card=element(plan.id==='ai'?'div':'article',undefined,plan.id==='ai'?'':'response-card');card.append(element('h3',plan.id==='ai'?plan.title:`${i+1}. ${plan.title}`),element('p',`USV: ${s.formations.catalog.usv[plan.formations.usv]} / 드론: ${s.formations.catalog.uav[plan.formations.uav]}`));
        if(plan.id==='ai'){
          const facts=plan.input_summary,range=facts?.contacts.map(t=>`${Math.round(t.range_m)}m`).join(' / ');
          card.append(element('p',`입력 데이터: 모의 접촉 ${range||'거리 확인 필요'} · 가용 UAV ${facts?.available.UAV??'—'} / USV ${facts?.available.USV??'—'} · ${plan.model}`,'ai-facts'),element('p',`AI 추론: ${plan.benefit}`),element('small',`기체 위치·연결은 Gazebo 데이터, 접촉·배터리는 모의 값 · ${new Date(plan.input_captured_at*1000).toLocaleTimeString('ko-KR')} 기준`));
        }
        for(const task of plan.tasks)card.append(element('p',`${task.vehicle} → ${task.task}`,'task-line'));
        const details=element('details'),summary=element('summary','배정 근거 · 예상 시간 · 검증');details.append(summary);
        for(const task of plan.tasks)details.append(element('small',`${task.vehicle}: ${task.reason} · 직선 이동 추정 ${task.eta_seconds}초`));
        details.append(element('p',plan.benefit),element('small',plan.tradeoff),element('small',plan.validation));card.append(details);
        const current=s.formations;details.append(element('p',`승인 후: USV ${current.catalog.usv[current.usv]} → ${current.catalog.usv[plan.formations.usv]} / 드론 ${current.catalog.uav[current.uav]} → ${current.catalog.uav[plan.formations.uav]}`,'movement-summary'),element('small',plan.persistent?`${plan.execution_summary||plan.benefit} 대형 버튼으로 직접 조정하거나 상황을 종료할 수 있습니다.`:'현재와 같은 대형은 유지합니다. UAV·USV는 확인 후 복귀합니다.'));
        const button=element('button',m.approved?(m.approved.id===plan.id?'실행된 대응안':'선택 종료'):'이 대응안 선택 · 즉시 실행');button.type='button';button.dataset.option=plan.id;button.disabled=missionRequestPending||!!m.approved;
        if(!m.approved&&!plan.available){card.append(element('p','예비 기체 부족 · 기존 임무는 계속 수행합니다.','response-availability'));
          if(plan.id!=='ai'){const priority=element('button','선택 임무 중단 · 이 대응 우선 실행','resource-response');priority.type='button';priority.dataset.priorityOption=plan.id;priority.addEventListener('click',()=>{const source=Number($('resourceSource').value);if(source)executeResponse(m,plan.id,source);});card.append(priority);}
        }
        button.addEventListener('click',()=>executeResponse(m,plan.id));card.append(button);$(plan.id==='ai'?'aiResponseContent':'responseOptions').append(card);
      }
    }
  }
  renderHumanApproval(s);renderAIControls(s);renderResourceDecision(s);
  if(!m){$('missionStage').textContent='';return;}
  if(!m.approved){const remaining=Math.max(0,60-Math.floor(Date.now()/1000-(m.planned_at??m.created_at)));$('missionStage').textContent=`승인 대기 · 추천 유효시간 ${remaining}초 · 가상 상황 / 규칙 기반 배정`;
    for(const button of document.querySelectorAll('#responseOptions [data-option],#aiResponseContent [data-option]')){const plan=m.options.find(p=>p.id===button.dataset.option);const ui=responseControlState(m,button.dataset.option,s.active_mission,pendingExecution);button.disabled=missionRequestPending||ui.disabled;button.textContent=ui.label;}
  }else{
    const groups=['usv','uav'],matched=groups.every(g=>s.formations.status[g]?.mode===m.approved.formations[g]);
    const moving=!matched||groups.some(g=>s.formations.status[g]?.moving);
    $('missionStage').textContent=`${s.vehicles.some(v=>!v.connected)?'Gazebo 상태 확인 필요':moving?'Gazebo 대형 전환 중':'Gazebo 대형 유지 중'} · UAV·USV 임무: ${m.intervention?'역할 공백 · 운용자 결정 필요':m.manual_takeover?'직접 대형 운용':m.execution?.status==='running'?'추적·경계 진행':m.execution?.status==='pending'?'출동 준비':m.execution?.status||'대기'}`;
  }
}

function renderHumanApproval(s){
  const m=s.mission;
  if(selectedResponse?.mission_id!==m?.id||selectedResponse?.plan_revision!==(m?.plan_revision||0))selectedResponse=null;
  const plan=m?.options.find(p=>p.id===selectedResponse?.option_id);
  const expired=!!m&&Date.now()/1000-(m.planned_at??m.created_at)>60;
  const ready=!!plan&&plan.available&&!m.approved&&!expired&&s.formations.revision===m.basis_revision;
  $('finalApprove').disabled=missionRequestPending||!ready;
  $('submitApprovalCommand').disabled=missionRequestPending||!m||!!m.approved||expired;
  $('approvalCommand').disabled=missionRequestPending||!m||!!m.approved||expired;
  for(const card of document.querySelectorAll('.response-card')){const button=card.querySelector('[data-option]');if(!button)continue;const ui=responseControlState(m,button.dataset.option,s.active_mission,pendingExecution);card.classList.toggle('selected-response',ui.selected);button.setAttribute('aria-pressed',String(ui.selected));button.textContent=ui.label;button.disabled=missionRequestPending||ui.disabled;}
  $('approvalPreview').textContent=m?.approved?`운용자 최종 승인 기록 · ${m.approved.title} · ${m.approved.decision_source==='captain_text'?'직접 입력':'승인 버튼'} · ${new Date(m.approved.approved_at*1000).toLocaleTimeString('ko-KR')}`:plan?`선택: ${m.options.indexOf(plan)+1}번 ${plan.title} · ${expired?'추천 만료 · 자동 갱신을 기다려 주세요.':!plan.available?'가용 기체 부족 · 기체 상태를 확인하고 자동 갱신을 기다려 주세요.':s.formations.revision!==m.basis_revision?'대형 변경 · 자동 갱신을 기다려 주세요.':`배정 ${plan.tasks.map(t=>t.vehicle).join(', ')} · 대응안 선택 시 즉시 실행됩니다.`}`:expired?'추천이 만료되었습니다. 자동 갱신을 기다려 주세요.':'대응안을 선택해 검토하세요. 선택하면 즉시 실행됩니다.';
}
function renderResourceDecision(s){
  const m=s.mission,donors=(s.active_missions||[]).filter(item=>item.id!==m?.id&&!item.cancel_requested);
  const repair=!!m?.approved&&!!m.intervention&&!m.cancel_requested;
  const shortage=!!m&&!m.approved&&m.options.some(p=>p.id!=='ai'&&!p.available);
  const panel=$('resourceDecision');panel.hidden=!repair&&!shortage;
  const select=$('resourceSource'),previous=select.value;
  const key=donors.map(item=>item.id).join('|');
  if(select.dataset.sources!==key){select.replaceChildren(element('option','중단할 임무 선택'),...donors.map(item=>{const o=element('option',`#${item.id} ${item.card.title}`);o.value=item.id;return o;}));select.options[0].value='';select.dataset.sources=key;select.value=donors.some(item=>String(item.id)===previous)?previous:'';}
  $('resourceMessage').textContent=repair?m.intervention.message:donors.length?'예비 기체가 부족합니다. 기존 임무를 유지하거나, 중단할 임무를 선택한 뒤 대응안의 우선 실행 버튼을 누르세요.':'가용 기체가 부족합니다. 다른 실행 임무에서 확보할 기체가 없어 대기합니다.';
  $('repairMission').hidden=!repair;$('repairMission').disabled=missionRequestPending||!select.value;
  for(const button of document.querySelectorAll('[data-priority-option]'))button.disabled=missionRequestPending||!select.value||!!m?.resolved;
}
$('resourceSource').addEventListener('change',()=>{if(lastState)renderResourceDecision(lastState);});
$('repairMission').addEventListener('click',()=>{const id=Number($('resourceSource').value);if(id&&lastState?.mission)missionRequest('/api/mission/'+lastState.mission.id+'/reallocate',{release_mission_id:id,human_confirmed:true});});
const aiRequests=new Set(),aiAttempts=new Set(),aiErrors=new Map();
function aiAttemptKey(m,s){return `${m.id}:${m.ai_meta?.generated_at||'initial'}:${s.formations.revision}`;}
function renderAIControls(s){
  const m=s.mission,tools=$('aiResponseTools');$('aiResponseSlot').hidden=!m?.ai_supported||!!m.approved&&m.approved.id!=='ai';
  if(!m?.ai_supported)return;
  const plan=m.options.find(p=>p.id==='ai'),pending=aiRequests.has(m.id)||m.ai_status?.state==='pending';
  $('regenerateAI').disabled=pending||!!m.approved||!!m.resolved;
  $('regenerateAI').textContent=pending?'AI 분석 중…':'현재 상태로 다시 제안';
  $('aiResponseStatus').textContent=m.approved?(m.approved.id==='ai'?'선택한 AI 제안을 실행 중입니다.':'기본 대응안이 실행 중입니다.'):pending?'현재 상황·기체 상태를 읽고 새 대응안을 생성 중입니다.':aiErrors.get(m.id)||m.ai_status?.message||(plan?'AI 제안은 선택했을 때만 실행됩니다.':'AI가 현재 상황에 맞는 별도 대응안을 생성합니다.');
  if(m.approved||m.resolved||pending)return;
  if(plan&&plan.expires_at>Date.now()/1000&&plan.formation_revision===s.formations.revision)return;
  const key=aiAttemptKey(m,s);
  if(!aiAttempts.has(key)){aiAttempts.add(key);queueMicrotask(()=>requestAI(m.id));}
}
async function requestAI(id){
  if(aiRequests.has(id))return;
  aiRequests.add(id);aiErrors.delete(id);
  if(lastState?.mission?.id===id){aiAttempts.add(aiAttemptKey(lastState.mission,lastState));renderAIControls(lastState);}
  try{
    const r=await fetch('/api/mission/'+id+'/ai-response',{method:'POST'}),result=await r.json();
    if(!r.ok)throw Error(result.detail||'AI 제안 생성 실패');
    if(lastState?.mission?.id===id)missionRenderKey='';
  }catch(error){aiErrors.set(id,error.message);}
  finally{aiRequests.delete(id);if(lastState?.mission?.id===id)renderAIControls(lastState);}
}
$('regenerateAI').addEventListener('click',()=>{if(lastState?.mission)requestAI(lastState.mission.id);});

$('finalApprove').addEventListener('click',()=>{if(selectedResponse)missionRequest('/api/mission/approve',{...selectedResponse,human_confirmed:true,decision_source:'captain_button'});});
$('approvalCommandForm').addEventListener('submit',e=>{
  e.preventDefault();const command=$('approvalCommand').value,match=command.match(/^\s*([12])\s*번\s*(?:최종\s*)?승인\s*$/),m=lastState?.mission;
  if(!match||!m){$('missionFeedback').textContent='1번 승인, 2번 승인 중 하나를 정확히 입력하세요.';return;}
  const plan=m.options[Number(match[1])-1];if(!plan){$('missionFeedback').textContent='선택할 수 있는 대응안이 없습니다.';return;}
  selectedResponse={mission_id:m.id,option_id:plan.id,plan_revision:m.plan_revision||0};missionRequest('/api/mission/approve',{...selectedResponse,human_confirmed:true,decision_source:'captain_text',operator_command:command});
});

async function executeRiskResponse(riskId,optionId){
  const created=await missionRequest('/api/risks/'+encodeURIComponent(riskId)+'/plan');
  if(!created||created.risk_id!==riskId||created.approved)return;
  await executeResponse(created,optionId);
}
async function executeResponse(m,optionId,releaseId=null){
  if(responseExecuting||missionRequestPending)return;responseExecuting=true;pendingExecution={mission_id:m.id,option_id:optionId};
  $('missionFeedback').textContent='선택됨 · 기체 상태 확인 후 출동 요청 중…';$('missionFeedback').dataset.state='pending';if(lastState)renderMission(lastState);
  try{
    while(plansRefreshing)await new Promise(resolve=>setTimeout(resolve,30));
    const r=await fetch('/api/mission/'+m.id+'/refresh',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({release_mission_id:releaseId})}),fresh=await r.json();
    if(!r.ok)throw Error(fresh.detail||'대응안 갱신 실패');
    const request=responseExecutionRequest(fresh,optionId);
    if(releaseId!==null)request.replace_active_id=releaseId;
    selectedResponse=request;$('assignmentPlan').value=optionId;
    await missionRequest('/api/mission/approve',request);
  }catch(error){$('missionFeedback').textContent='실행 실패 · '+error.message;$('missionFeedback').dataset.state='error';}
  finally{responseExecuting=false;pendingExecution=null;if(lastState)renderMission(lastState);}
}
async function missionRequest(url,data={}){
  if(missionRequestPending)return;missionRequestPending=true;
  const buttons=[...document.querySelectorAll('.mission-console button')];buttons.forEach(b=>b.disabled=true);$('missionFeedback').textContent='처리 중…';
  try{const r=await fetch(url,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)}),result=await r.json();if(!r.ok)throw Error(result.detail||'요청 실패');if(result.id!==undefined){reviewMissionId=result.id;}
    const response=await fetch('/api/state');if(!response.ok)throw Error('상태 갱신 실패');queueView=null;lastState=reviewState(await response.json());missionRenderKey='';renderMission(lastState);renderVehicles(lastState);formationControls(lastState.formations);$('missionFeedback').textContent=url.endsWith('random-attack')?`공격 발생 · ${result.card.title} · 대응안을 선택하세요.`:url.endsWith('approve')?'✓ 출동 명령 전달 완료 · Gazebo 반영 중':url.endsWith('reallocate')?'✓ 운용자 결정 반영 · 부족한 역할 재배정':url.endsWith('cancel')?'선택 임무 종료 요청 · 다른 임무 유지':url.endsWith('simulated-fault')?'기체 배정 상태 시연 갱신':'상황 생성 완료 · 대응안 2개를 검토하세요.';$('missionFeedback').dataset.state='success';event($('missionFeedback').textContent);return result;
  }catch(error){$('missionFeedback').textContent='실행 불가 · '+error.message;$('missionFeedback').dataset.state='error';event(error.message);}
  finally{missionRequestPending=false;if(lastState)renderMission(lastState);}
}
$('faultToggle').addEventListener('click',async()=>{const v=lastState?.vehicles.find(v=>v.id===selectedVehicle);if(!v)return;await missionRequest('/api/vehicles/'+v.id+'/simulated-fault',{unavailable:!v.fault});});
$('randomAttack').addEventListener('click',()=>missionRequest('/api/mission/random-attack'));
$('cancelMission').addEventListener('click',()=>missionRequest('/api/mission/cancel',{mission_id:lastState?.mission?.id}));
$('assignmentPlan').addEventListener('change',()=>{const m=lastState?.mission;if(m&&!m.approved){selectedResponse={mission_id:m.id,option_id:$('assignmentPlan').value,plan_revision:m.plan_revision||0};renderHumanApproval(lastState);}if(lastState)renderVehicles(lastState);});
$('vehicleFilter').addEventListener('change',()=>{if(lastState)renderVehicles(lastState);});
function chooseVehicle(event){const row=event.target.closest('[data-vehicle]');if(row){selectedVehicle=row.dataset.vehicle;if(lastState?.camera_view==='inspect')inspectSelected();if(lastState){renderVehicles(lastState);map(lastState);cameraOverlay(lastState);}}}
$('cards').addEventListener('click',chooseVehicle);

async function health(){try{const r=await fetch('/api/health'),s=await r.json();$('health').textContent=s.model_installed?'백엔드 · Ollama 준비됨':'Ollama 또는 모델 확인 필요';}catch{$('health').textContent='백엔드 연결 실패';}setTimeout(health,15000);}poll();health();

// Keep the underlying camera pose unchanged: manipulate the displayed image only.
let cameraZoom=1,cameraPan={x:0,y:0},cameraDrag=null,cameraDragged=false;
const viewport=$('cameraViewport');
function transformCamera(){
  const limitX=viewport.clientWidth*(cameraZoom-1)/2,limitY=viewport.clientHeight*(cameraZoom-1)/2;
  cameraPan.x=Math.max(-limitX,Math.min(limitX,cameraPan.x));cameraPan.y=Math.max(-limitY,Math.min(limitY,cameraPan.y));
  for(const layer of [$('camera'),$('cameraOverlay')])layer.style.transform=`translate(${cameraPan.x}px,${cameraPan.y}px) scale(${cameraZoom})`;
  $('zoomValue').textContent=cameraZoom.toFixed(1)+'×';
}
viewport.addEventListener('wheel',e=>{e.preventDefault();cameraZoom=Math.max(1,Math.min(4,cameraZoom*Math.exp(-e.deltaY*.001)));transformCamera();},{passive:false});
viewport.addEventListener('pointerdown',e=>{if(e.button!==0)return;cameraDragged=false;cameraDrag={x:e.clientX,y:e.clientY};viewport.setPointerCapture(e.pointerId);});
viewport.addEventListener('pointermove',e=>{if(!cameraDrag)return;if(Math.hypot(e.movementX,e.movementY)>2)cameraDragged=true;cameraPan.x+=e.clientX-cameraDrag.x;cameraPan.y+=e.clientY-cameraDrag.y;cameraDrag={x:e.clientX,y:e.clientY};transformCamera();});
for(const eventName of ['pointerup','pointercancel'])viewport.addEventListener(eventName,()=>cameraDrag=null);
$('camera').draggable=false;
$('resetCamera').addEventListener('click',()=>{cameraZoom=1;cameraPan={x:0,y:0};transformCamera();});
window.addEventListener('resize',transformCamera);
viewport.addEventListener('click',e=>{
 if(cameraDragged||lastState?.camera_view==='inspect')return;
 const rect=$('cameraOverlay').getBoundingClientRect(),x=(e.clientX-rect.left)*1280/rect.width,y=(e.clientY-rect.top)*720/rect.height;
 const nearest=cameraPickables.map(p=>({...p,d:Math.hypot(p.x-x,p.y-y)})).sort((a,b)=>a.d-b.d)[0];
 if(nearest&&nearest.d<18){selectedVehicle=nearest.id;renderVehicles(lastState);cameraOverlay(lastState);}
});
async function inspectSelected(){
 if(!selectedVehicle)return;
 $('cameraView').value='inspect';$('cameraView').dispatchEvent(new Event('change'));
 cameraZoom=1;cameraPan={x:0,y:0};transformCamera();
}
$('inspectVehicle').addEventListener('click',inspectSelected);
viewport.addEventListener('dblclick',inspectSelected);
$('returnFleet').addEventListener('click',()=>{
 $('cameraView').value='wide';$('cameraView').dispatchEvent(new Event('change'));
 cameraZoom=1;cameraPan={x:0,y:0};transformCamera();
});

$('vehicleSearch').addEventListener('input',()=>{if(lastState)renderVehicles(lastState);});
for(const button of document.querySelectorAll('[data-filter]'))button.addEventListener('click',()=>{$('vehicleFilter').value=button.dataset.filter;if(lastState)renderVehicles(lastState);});
$('map').addEventListener('click',e=>{
  if(!lastState)return;const rect=$('map').getBoundingClientRect(),x=(e.clientX-rect.left)*$('map').width/rect.width,y=(e.clientY-rect.top)*$('map').height/rect.height;
  const nearest=mapPickables.map(p=>({...p,d:Math.hypot(p.x-x,p.y-y)})).sort((a,b)=>a.d-b.d)[0];
  if(nearest&&nearest.d<18*(window.devicePixelRatio||1)){selectedVehicle=nearest.id;if(lastState.camera_view==='inspect')inspectSelected();renderVehicles(lastState);map(lastState);cameraOverlay(lastState);}
});
