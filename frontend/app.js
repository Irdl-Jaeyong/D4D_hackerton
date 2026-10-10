const $=id=>document.getElementById(id);let history=[],connections={},lastState=null,lastScenarioStage=null;const cameraPickables=[];
function event(text){if(!$('events'))return;const li=document.createElement('li');li.textContent=`${new Date().toLocaleTimeString('ko-KR')} · ${text}`;$('events').prepend(li);while($('events').children.length>20)$('events').lastChild.remove();}
function bubble(text,role){const p=document.createElement('p');p.className='bubble '+role;p.textContent=text;$('messages').append(p);$('messages').scrollTop=$('messages').scrollHeight;return p;}
const stateLabels={defending:'방어중',waiting:'대기·복귀',unavailable:'수행불가'},stateColors={defending:'#2ce099',waiting:'#4aa8ff',unavailable:'#ff6b6b'};
const bandColors=['#55e7ef','#7ebaff','#ae97ff','#ffb567','#88ed9d'];
function map(state){
  const c=$('map'),ctx=c.getContext('2d');ctx.clearRect(0,0,c.width,c.height);
  const lead=state.vehicles.find(v=>v.id==='SHIP-01'&&v.connected);
  const ox=lead?lead.telemetry.x:0,oy=lead?lead.telemetry.y:0;
  const motion=state.scene?.motion,extent=Math.max(185,motion?.hemisphere_radius||52,...(motion?.escort_radii||[48,32]));
  const sx=(c.width-100)/(2*extent),sy=(c.height-65)/(2*extent);
  const point=(x,y)=>[c.width/2+(x-ox)*sx,c.height/2-(y-oy)*sy];
  ctx.strokeStyle='#193b50';
  for(let x=0;x<c.width;x+=38){ctx.beginPath();ctx.moveTo(x,0);ctx.lineTo(x,c.height);ctx.stroke();}
  for(let y=0;y<c.height;y+=30){ctx.beginPath();ctx.moveTo(0,y);ctx.lineTo(c.width,y);ctx.stroke();}
  for(const situation of state.scene?.situations||[]){const [x,y]=point(situation.x,situation.y);ctx.strokeStyle='#ffb567';ctx.beginPath();ctx.arc(x,y,9,0,Math.PI*2);ctx.stroke();ctx.fillStyle='#ffb567';ctx.fillText(situation.title,x+12,y-8);}
  ctx.font='12px sans-serif';ctx.fillStyle='#9cb7c9';
  if(state.formations?.usv==='circle'){ctx.strokeStyle='#2c6d77';ctx.setLineDash([5,6]);ctx.beginPath();ctx.ellipse(c.width/2,c.height/2,(motion?.escort_radii[0]||48)*sx,(motion?.escort_radii[1]||32)*sy,0,0,Math.PI*2);ctx.stroke();ctx.setLineDash([]);}
  if(lead&&motion&&state.scene.scenario){
    const phase=(lead.telemetry.x/motion.ship_speed)%180;
    const [x,y]=point(ox+105,120-3*phase);
    ctx.strokeStyle='#ff982b88';ctx.setLineDash([5,5]);ctx.beginPath();
    ctx.moveTo(...point(ox+105,120));ctx.lineTo(...point(ox+105,-130));ctx.stroke();ctx.setLineDash([]);
    ctx.fillStyle='#ff982b';ctx.beginPath();ctx.arc(x,y,6,0,Math.PI*2);ctx.fill();ctx.fillText('CIV-01 민간 배',x+10,y-8);
  }
  for(const v of state.vehicles){
    if(!v.telemetry||(!v.connected&&v.source!=='last_known'))continue;const t=v.telemetry,[x,y]=point(t.x,t.y);
    const ring=(parseInt(v.id.split('-')[1],10)-1)%5;
    ctx.fillStyle=stateColors[v.readiness?.operational_state]||'#fff';
    ctx.save();ctx.translate(x,y);ctx.rotate(-t.yaw);
    if(v.type==='UAV'){ctx.beginPath();ctx.arc(0,0,3.5,0,Math.PI*2);ctx.fill();}
    else{ctx.beginPath();ctx.moveTo(v.type==='SHIP'?20:9,0);ctx.lineTo(-9,-5);ctx.lineTo(-9,5);ctx.closePath();ctx.fill();}ctx.restore();

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
  ctx.font='bold 13px system-ui';
  for(const v of state.vehicles){
    if(!v.connected)continue;const t=v.telemetry,q=project(t.x-ship.x,t.y-ship.y,t.z);if(!q)continue;
    const ring=(parseInt(v.id.split('-')[1],10)-1)%5;
    const color=stateColors[v.readiness?.operational_state]||'#fff';
    cameraPickables.push({id:v.id,x:q[0],y:q[1]});
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
          try{const response=await fetch('/api/formations',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({group,mode})});
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
async function poll(){try{const r=await fetch('/api/state');if(!r.ok)throw Error();const s=await r.json();lastState=s;if(!$('cameraView').disabled)$('cameraView').value=s.camera_view||'wide';renderVehicles(s);renderMission(s);$('connected').textContent=`${s.vehicles.filter(v=>v.connected).length} / ${s.vehicles.length} 연결`;$('camera').style.display=s.camera_available?'block':'none';$('cameraEmpty').style.display=s.camera_available?'none':'block';if(s.camera_available)$('camera').src='/api/camera?t='+Date.now();map(s);cameraOverlay(s);formationControls(s.formations);for(const group of ['usv','uav'])for(const button of $(group+'Formation').children)button.disabled=!!s.active_mission;
const lead=s.vehicles.find(v=>v.id==='SHIP-01'&&v.connected);
if(lead&&s.scene.scenario){const t=lead.telemetry.x/s.scene.motion.ship_speed,phase=t%180;
const stage=phase<18?0:phase<80?1:phase<170?2:3,key=`${Math.floor(t/180)}-${stage}`;
if(key!==lastScenarioStage){event(['민간 배 접근: 충돌 예측 감시','교차 통항 구간: 위험을 예측한 USV가 우회','민간 배 통과 구간: 호위 위치 복귀','정상 호위 구간'][stage]);lastScenarioStage=key;}}
}catch{$('connected').textContent='백엔드 연결 끊김';document.querySelectorAll('.badge').forEach(b=>{b.className='badge';b.textContent='확인 불가';});$('fleetSummary').textContent='백엔드 연결 끊김 · 상태 확인 불가';document.querySelectorAll('#responseOptions button').forEach(b=>b.disabled=true);$('finalApprove').disabled=true;$('submitApprovalCommand').disabled=true;$('cards').replaceChildren();$('vehicleDetails').textContent='연결 끊김 · 마지막 상태를 사용할 수 없습니다.';$('assignmentSummary').textContent='연결 끊김 · 배정 결과 확인 불가';$('assignmentReasons').replaceChildren();$('assignmentPlan').disabled=true;$('map').getContext('2d').clearRect(0,0,760,300);$('camera').style.display='none';$('cameraEmpty').style.display='block';$('cameraEmpty').textContent='백엔드 연결 끊김';$('cameraOverlay').getContext('2d').clearRect(0,0,1280,720);}finally{setTimeout(poll,500);}}
$('chatForm').addEventListener('submit',async e=>{e.preventDefault();const message=$('message').value.trim();if(!message)return;bubble(message,'user');$('message').value='';$('send').disabled=true;$('chatStatus').textContent='AI 분석 중 · 최초 요청은 로딩 시간이 걸릴 수 있습니다';try{const r=await fetch('/api/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({message,use_camera:$('useCamera').checked,history:history.slice(-8)})});const data=await r.json();if(!r.ok)throw Error(data.detail||'요청 실패');bubble(data.reply,'ai');history.push({role:'user',content:message},{role:'assistant',content:data.reply.slice(0,4000)});$('chatStatus').textContent=`${data.elapsed_seconds}초 · ${data.used_camera?'카메라 포함':'텍스트'} · 명령 실행 없음`;}catch(err){bubble(err.message,'ai error');$('chatStatus').textContent='요청 실패';}finally{$('send').disabled=false;}});

let selectedVehicle=null,missionRenderKey='',selectedResponse=null,reviewMissionId=null;
function element(tag,text,className){const node=document.createElement(tag);if(text!==undefined)node.textContent=text;if(className)node.className=className;return node;}


function reviewMission(s){
  const items=[...(s.approval_queue||[]),...(s.active_mission?[s.active_mission]:[])];
  let chosen=items.find(m=>m.id===reviewMissionId);
  if(!chosen){chosen=items[0]||null;reviewMissionId=chosen?.id??null;}
  return chosen;
}
function selectSituation(id){
  reviewMissionId=id;selectedResponse=null;missionRenderKey='';
  if(lastState){renderMission(lastState);renderVehicles(lastState);map(lastState);}
}
function priorityText(r){return r?.priority?`${r.priority} ${{P0:'긴급',P1:'높음',P2:'주의',P3:'정보'}[r.priority]}`:'평가 불가';}
function renderQueue(s){
  const queue=s.approval_queue||[],filter=$('priorityFilter').value;
  $('queueCount').textContent=`승인 대기열 · ${queue.length}건`;
  $('activeMission').replaceChildren();$('approvalQueue').replaceChildren();
  if(s.active_mission){const m=s.active_mission,b=element('button',`실행 ${m.execution?.status||'대기'} · #${m.id} ${m.card.title}`,'queue-active');b.type='button';b.addEventListener('click',()=>selectSituation(m.id));$('activeMission').append(b);}
  const shown=queue.filter(m=>filter==='all'||(m.risk?.priority||'unknown')===filter);
  for(const m of shown){
    const b=element('button',undefined,'queue-item'+(reviewMissionId===m.id?' selected':''));b.type='button';b.setAttribute('aria-pressed',String(reviewMissionId===m.id));
    b.append(element('span',priorityText(m.risk),'priority-badge '+(m.risk?.priority||'unknown')),element('strong',`#${m.id} ${m.card.title}`),element('small',`${m.resolved?'원인 해소 · 종료 가능':m.risk?.score==null?'점수 평가 불가':m.risk.score+'점'} · ${new Date(m.created_at*1000).toLocaleTimeString('ko-KR')}`));
    b.addEventListener('click',()=>selectSituation(m.id));$('approvalQueue').append(b);
  }
  if(!shown.length)$('approvalQueue').append(element('p',queue.length?'해당 등급에 대기 중인 상황 없음':'승인 대기 중인 상황 없음','muted'));
}
function assignmentContext(s){
  const m=reviewMission(s);if(!m)return {mission:null,plan:null,expired:false};
  return {mission:m,plan:m.approved||m.options.find(p=>p.id===$('assignmentPlan').value),expired:!m.approved&&Date.now()/1000-(m.planned_at||m.created_at)>60};
}
function assignmentText(v,context){
  const task=context.plan?.tasks.find(t=>t.vehicle===v.id);
  if(!v.connected||v.fault||v.readiness.operational_state==='unavailable')return '배정 제외 · '+v.readiness.reason;
  if(task)return (context.mission.approved?'승인 계획':'추천 기체')+' · '+task.task+(context.expired?' · 재계산 필요':'');
  if(v.type==='SHIP')return '함선 운항 유지';
  if(!context.plan)return '상황 생성 후 평가';
  return '이번 안 미선택 · '+v.readiness.task;
}
function renderAssignment(s){
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
  $('assignmentReasons').append(element('p','기타 기체: 기존 담당 위치 유지. 선택 이유는 연결·시뮬레이션 잔량·직선 ETA 및 복귀 여유에 근거합니다.','muted'));
}

function vehicleDetails(s){
  if(!selectedVehicle&&s.camera_view==='inspect')selectedVehicle=s.inspection_vehicle;
  const v=s.vehicles.find(v=>v.id===selectedVehicle);$('inspectVehicle').disabled=!v?.connected;
  $('cameraIdentity').textContent=s.camera_view==='inspect'?`${s.inspection_vehicle} · 실제 기체 근접 관측 · ${stateLabels[s.vehicles.find(v=>v.id===s.inspection_vehicle)?.readiness.operational_state]||'상태 확인 필요'}`:v?`선택: ${v.id} · ${v.type==='UAV'?'드론':v.type==='USV'?'무인 수상정':'메인 함선'} · 근접 관측으로 형상을 확인하세요.`:'기체나 목록을 클릭해 선택한 뒤 근접 관측으로 형상을 확인하세요.';
  if(!v)return;
  const r=v.readiness,p=v.telemetry;
  $('faultToggle').hidden=!v.fault;
  $('faultToggle').disabled=v.type==='SHIP'||!!(v.fault&&v.type==='UAV'&&v.fault_type!=='communication'&&!['charging','ditched'].includes(v.fault.phase));$('faultToggle').textContent=v.fault_type==='communication'?'통신 복구 시연':v.fault?.phase==='ditched'?'회수·정비 완료 시연':v.fault?'정비 완료 · 고장 해제':'선택 기체 고장 주입';
  $('vehicleDetails').textContent=`${v.id} · ${v.fault?.phase==='charging'?'갑판 충전·정비 중 · ':''}${r.battery_percent===null?'잔량 데이터 없음':`시뮬레이션 잔량 ${r.battery_percent}% / 잔여 ${r.endurance_minutes}분`} · 마지막 수신 ${v.age_seconds===null?'없음':v.age_seconds.toFixed(1)+'초 전'} · ${v.fault?'모의 고장 · '+r.task:r.reason} · ${r.task}`+(p&&v.connected?` · 위치 (${p.x.toFixed(1)}, ${p.y.toFixed(1)}, ${(p.z||0).toFixed(1)})m · 기울기 ${(Math.max(Math.abs(p.roll||0),Math.abs(p.pitch||0))*180/Math.PI).toFixed(1)}°`:' · 위치 확인 불가');
  const context=assignmentContext(s),task=context.plan?.tasks.find(t=>t.vehicle===v.id);
  $('vehicleDetails').append(element('strong',assignmentText(v,context),'vehicle-assignment-title'));
  if(task){const margin=r.endurance_minutes*60-(2*task.eta_seconds+300);
    $('vehicleDetails').append(element('div',`선정 당시 근거: ${task.reason}`),element('div',`직선 도달 추정 ${task.eta_seconds}초 · 현재 잔여시간 기준 왕복+5분 차감 여유 ${Math.floor(margin/60)}분 (추정)`),element('small','도달 시간은 상황 생성 당시 계산값입니다. 안전 경로·임무 중단 비용·감시 공백 평가는 미구현입니다.'));
  }else if(context.plan&&v.type!=='SHIP'&&r.operational_state!=='unavailable'){
    $('vehicleDetails').append(element('small','이번 대응안에 선택되지 않았습니다. 기체별 점수 비교와 경로 평가는 아직 표시하지 않습니다.'));
  }

}
function renderVehicles(s){
  renderAssignment(s);const assignment=assignmentContext(s);
  const filter=$('vehicleFilter').value,fragment=document.createDocumentFragment();
  for(const v of s.vehicles){
    if(connections[v.id]!==v.connected){event(`${v.id} ${v.connected?'Gazebo·ROS 연결':'미연결'}`);connections[v.id]=v.connected;}
    if(filter!=='all'&&(stateLabels[filter]?v.readiness.operational_state!==filter:filter==='attention'?v.connected&&v.readiness.available:v.type!==filter))continue;
    const r=v.readiness,row=element('tr');row.dataset.vehicle=v.id;row.style.borderLeft='3px solid '+stateColors[r.operational_state];row.tabIndex=0;row.setAttribute('aria-label',v.id+' 상세 상태');if(v.id===selectedVehicle)row.className='selected';
    row.append(element('td',v.id));const battery=element('td');
    if(r.battery_percent!==null&&v.connected){const meter=element('progress');meter.max=100;meter.value=r.battery_percent;meter.setAttribute('aria-label',v.id+' 시뮬레이션 배터리');battery.append(meter,element('small',r.battery_percent+'% · '+(v.fault?.phase==='charging'?'충전 중':r.endurance_minutes+'분')));}
    else battery.textContent=v.type==='SHIP'?'미연결 센서':'확인 불가';
    const link=element('td',v.connected?'정상':'수신 지연',v.connected?'online':'offline');
    const task=element('td');task.append(element('div',(stateLabels[r.operational_state]||'')+' · '+r.task),element('small',assignmentText(v,assignment)));row.append(battery,link,task);fragment.append(row);
  }
  $('cards').replaceChildren(fragment);vehicleDetails(s);$('stateParts').replaceChildren();for(const [key,label] of Object.entries(stateLabels)){const b=element('button',label+' '+s.vehicles.filter(v=>v.readiness.operational_state===key).length);b.type='button';b.style.borderColor=stateColors[key];b.style.color=stateColors[key];b.addEventListener('click',()=>{$('vehicleFilter').value=key;renderVehicles(s);});$('stateParts').append(b);}
  const support=s.vehicles.filter(v=>v.type!=='SHIP'),ready=support.filter(v=>v.readiness.available).length;
  $('fleetSummary').textContent=`가용 ${ready} / ${support.length} · 통신 확인 필요 ${s.vehicles.filter(v=>!v.connected).length} · 잔량 부족 ${support.filter(v=>v.connected&&v.readiness.battery_percent<35).length} · ${s.mission?(s.mission.approved?'대응안 승인됨':'대응안 승인 대기'):'상황 없음'}`;
}
function renderMission(s){
  const m=reviewMission(s),key=queueReviewKey(m);
  renderQueue(s);
  $('refreshMission').disabled=!m||!!m.approved||!!m.resolved;
  $('cancelMission').disabled=!m;$('startScenario').disabled=false;
  if(key!==missionRenderKey){
    missionRenderKey=key;selectedResponse=null;$('situationCard').replaceChildren();$('responseOptions').replaceChildren();
    if(!m){$('situationCard').append(element('p','가상 상황을 선택해 대응안 3개를 확인하세요.','muted'));}
    else{
      $('situationCard').append(element('strong',m.card.title),element('p',m.card.summary),element('p',`함선 상대 위치 x ${m.card.offset[0]}m / y ${m.card.offset[1]}m · 관제 지도에 가상 표식 표시`,'muted'),element('p',m.card.unknown,'scope-note'));
      const risk=m.risk,reason=element('p',risk?.reason||'평가 근거 없음','scope-note');reason.id='riskReason';$('situationCard').append(element('p',`${priorityText(risk)} · ${risk?.score==null?'점수 평가 불가':risk.score+' / 100점'}`,'priority-badge '+(risk?.priority||'unknown')),element('p',`S ${risk?.scores?.S??'없음'} / U ${risk?.scores?.U??'없음'} / A ${risk?.scores?.A??'없음'} · R = 10S + 6U + 4A`,'muted'),reason);
      if(risk?.p0_reasons?.length)$('situationCard').append(element('p','P0 강제 조건: '+risk.p0_reasons.join(', '),'scope-note'));
      if(risk?.missing?.length)$('situationCard').append(element('p','누락 정보: '+risk.missing.join(', '),'scope-note'));
      if(m.resolved)$('situationCard').append(element('p','원인이 해소되었습니다. 상황을 종료하세요.','muted'));
      if(!m.options.length)$('responseOptions').append(element('p','함선의 최신 위치가 없어 추천을 생성할 수 없습니다. 연결 후 재계산하세요.'));
      for(const [i,plan] of m.options.entries()){
        const card=element('article',undefined,'response-card');card.append(element('h3',`${i+1}. ${plan.title}`),element('p',`USV: ${s.formations.catalog.usv[plan.formations.usv]} / 드론: ${s.formations.catalog.uav[plan.formations.uav]}`));
        for(const task of plan.tasks)card.append(element('p',`${task.vehicle} → ${task.task}`,'task-line'));
        const details=element('details'),summary=element('summary','배정 근거 · 예상 시간 · 검증');details.append(summary);
        for(const task of plan.tasks)details.append(element('small',`${task.vehicle}: ${task.reason} · 직선 이동 추정 ${task.eta_seconds}초`));
        details.append(element('p',plan.benefit),element('small',plan.tradeoff),element('small',plan.validation));card.append(details);
        const current=s.formations;card.append(element('p',`승인 후: USV ${current.catalog.usv[current.usv]} → ${current.catalog.usv[plan.formations.usv]} / 드론 ${current.catalog.uav[current.uav]} → ${current.catalog.uav[plan.formations.uav]}`,'movement-summary'),element('small','현재와 같은 대형은 유지하고, 다른 대형은 현재 위치에서 점진적으로 이동합니다. UAV는 확인 지점 이동·5초 체류·복귀, USV 출동은 계획 등록입니다.'));
        const button=element('button',m.approved?(m.approved.id===plan.id?'승인된 대응안':'선택 종료'):'이 대응안 선택');button.type='button';button.dataset.option=plan.id;button.disabled=!!m.approved||!plan.available;
        button.addEventListener('click',()=>{selectedResponse={mission_id:m.id,option_id:plan.id,plan_revision:m.plan_revision||0};$('assignmentPlan').value=plan.id;renderHumanApproval(lastState);renderVehicles(lastState);$('missionFeedback').textContent=`${i+1}번 대응안 선택 · 최종 승인 전에는 실행되지 않습니다.`;});card.append(button);$('responseOptions').append(card);
      }
    }
  }
  if($('riskReason')&&m)$('riskReason').textContent=m.risk?.reason||'평가 근거 없음';
  renderHumanApproval(s);
  if(!m){$('missionStage').textContent='';return;}
  if(!m.approved){const remaining=Math.max(0,60-Math.floor(Date.now()/1000-(m.planned_at||m.created_at)));$('missionStage').textContent=`승인 대기 · 추천 유효시간 ${remaining}초 · 가상 상황 / 규칙 기반 배정`;
    for(const button of document.querySelectorAll('#responseOptions button')){const plan=m.options.find(p=>p.id===button.dataset.option);button.disabled=!remaining||!plan?.available||!!s.active_mission||!!m.resolved;}
  }else{
    const groups=['usv','uav'],matched=groups.every(g=>s.formations.status[g]?.mode===m.approved.formations[g]);
    const moving=!matched||groups.some(g=>s.formations.status[g]?.moving);
    $('missionStage').textContent=`${s.vehicles.some(v=>!v.connected)?'Gazebo 상태 확인 필요':moving?'Gazebo 대형 전환 중':'Gazebo 대형 유지 중'} · UAV 임무: ${m.execution?.status||'대기'} / USV 출동은 계획 등록`;
  }
}

function renderHumanApproval(s){
  const m=reviewMission(s);
  if(selectedResponse?.mission_id!==m?.id)selectedResponse=null;
  const plan=m?.options.find(p=>p.id===selectedResponse?.option_id);
  const expired=!!m&&Date.now()/1000-(m.planned_at||m.created_at)>60;
  const ready=!!plan&&plan.available&&!m.approved&&!expired&&s.formations.revision===m.basis_revision&&!s.active_mission&&!m.resolved&&selectedResponse.plan_revision===(m.plan_revision||0);
  $('finalApprove').disabled=!ready;
  $('submitApprovalCommand').disabled=!m||!!m.approved||expired||!!s.active_mission||!!m.resolved;
  $('approvalCommand').disabled=!m||!!m.approved||expired||!!s.active_mission||!!m.resolved;
  for(const card of document.querySelectorAll('.response-card')){const button=card.querySelector('button');card.classList.toggle('selected-response',button.dataset.option===selectedResponse?.option_id);button.setAttribute('aria-pressed',String(button.dataset.option===selectedResponse?.option_id));}
  $('approvalPreview').textContent=m?.approved?`운용자 최종 승인 기록 · ${m.approved.title} · ${m.approved.decision_source==='captain_text'?'직접 입력':'승인 버튼'} · ${new Date(m.approved.approved_at*1000).toLocaleTimeString('ko-KR')}`:s.active_mission&&!m?.approved?'현재 승인 임무를 종료한 후 이 상황을 승인할 수 있습니다.':m?.resolved?'원인이 해소되었습니다. 상황을 종료하세요.':expired?'추천이 만료되었습니다. 최신 상태로 다시 계산하세요.':plan?`선택: ${m.options.indexOf(plan)+1}번 ${plan.title} · 배정 ${plan.tasks.map(t=>t.vehicle).join(', ')} · 대형 적용과 UAV 관측·복귀를 승인합니다.`:'대응안을 선택해 검토하세요. 선택만으로 실행되지 않습니다.';
}
$('finalApprove').addEventListener('click',()=>{if(selectedResponse)missionRequest('/api/mission/approve',{...selectedResponse,human_confirmed:true,decision_source:'captain_button'});});
$('approvalCommandForm').addEventListener('submit',e=>{
  e.preventDefault();const command=$('approvalCommand').value,match=command.match(/^\s*([123])\s*번\s*(?:최종\s*)?승인\s*$/),m=lastState&&reviewMission(lastState);
  if(!match||!m){$('missionFeedback').textContent='1번 승인, 2번 승인, 3번 승인 중 하나를 정확히 입력하세요.';return;}
  const plan=m.options[Number(match[1])-1];if(!plan){$('missionFeedback').textContent='선택할 수 있는 대응안이 없습니다.';return;}
  selectedResponse={mission_id:m.id,option_id:plan.id,plan_revision:m.plan_revision||0};missionRequest('/api/mission/approve',{...selectedResponse,human_confirmed:true,decision_source:'captain_text',operator_command:command});
});

async function missionRequest(url,data={}){
  const buttons=[...document.querySelectorAll('.mission-console button')];buttons.forEach(b=>b.disabled=true);$('missionFeedback').textContent='처리 중…';
  try{const r=await fetch(url,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)}),result=await r.json();if(!r.ok)throw Error(result.detail||'요청 실패');
    if(result.id&&url.includes('/api/risks/'))reviewMissionId=result.id;
    const response=await fetch('/api/state');if(!response.ok)throw Error('상태 갱신 실패');lastState=await response.json();missionRenderKey='';renderMission(lastState);renderVehicles(lastState);formationControls(lastState.formations);$('missionFeedback').textContent=url.endsWith('approve')?'승인 완료 · 대형 적용 요청 / 임무 계획 등록':url.endsWith('cancel')?(result.message||'선택 상황 종료'):url.endsWith('refresh')?'선택 상황의 대응안 재계산 완료':url.endsWith('simulated-fault')?'기체 고장 상태 갱신':$('scenarioSelect').value==='fault'?'고장 반영 완료 · 기체 움직임과 위험 목록을 확인하세요.':'상황 생성 완료 · 대응안 3개를 검토하세요.';event($('missionFeedback').textContent);
  }catch(error){$('missionFeedback').textContent=error.message;event(error.message);}
  finally{if(lastState)renderMission(lastState);}
}
$('faultToggle').addEventListener('click',async()=>{const v=lastState?.vehicles.find(v=>v.id===selectedVehicle);if(!v)return;await missionRequest('/api/vehicles/'+v.id+'/simulated-fault',{unavailable:!v.fault});});
$('startScenario').addEventListener('click',()=>missionRequest('/api/mission/scenario',{scenario:$('scenarioSelect').value,vehicle_id:selectedVehicle,fault_type:$('faultType').value}));
$('cancelMission').addEventListener('click',()=>{const m=lastState&&reviewMission(lastState);if(m)missionRequest('/api/mission/cancel',{mission_id:m.id});});
$('refreshMission').addEventListener('click',()=>{const m=lastState&&reviewMission(lastState);if(m)missionRequest('/api/mission/'+m.id+'/refresh');});
$('priorityFilter').addEventListener('change',()=>{if(lastState)renderQueue(lastState);});
$('assignmentPlan').addEventListener('change',()=>{if(lastState)renderVehicles(lastState);});
$('vehicleFilter').addEventListener('change',()=>{if(lastState)renderVehicles(lastState);});
function chooseVehicle(event){const row=event.target.closest('tr[data-vehicle]');if(row){selectedVehicle=row.dataset.vehicle;if(lastState)renderVehicles(lastState);}}
$('cards').addEventListener('click',chooseVehicle);$('cards').addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();chooseVehicle(e);}});

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
let latestRisks=null;
async function refreshRisks(){
 try{
  const response=await fetch('/api/risks');if(!response.ok)throw Error('위험 평가 연결 실패');const data=await response.json();latestRisks=data;
  $('riskRefresh').textContent=new Date(data.evaluated_at*1000).toLocaleTimeString('ko-KR')+' · 10초 주기';
  $('riskList').replaceChildren();$('riskResponses').replaceChildren();
  if(!data.items.length){$('riskList').append(element('p','현재 기준을 넘는 위험 없음 · 계속 감시 중','muted'));return;}
  for(const [i,risk] of data.items.slice(0,5).entries()){
   const row=element('button',`${i+1}. ${risk.title} · ${risk.vehicle}`,i===0?'risk-item critical':'risk-item');row.type='button';row.append(element('small',risk.evidence));
   row.addEventListener('click',()=>{selectedVehicle=risk.vehicle;if(lastState)renderVehicles(lastState);});$('riskList').append(row);
  }
  const top=data.items[0];if(!selectedVehicle){selectedVehicle=top.vehicle;if(lastState)renderVehicles(lastState);}$('riskResponses').append(element('strong','최우선 상황 · 대응안 3개'));
  for(const [i,plan] of (top.options||[]).entries()){
   const title=['현재 대형 유지 · 주변 관측','양측 종대 · 복귀 구역 확인','후방 V자 · 대체 기체 관측'][i];
   const card=element('article',undefined,'risk-response');card.append(element('strong',`${i+1}. ${title}`),element('small',plan.tasks.map(t=>t.vehicle+' · '+t.task).join(' / ')||'가용 기체 없음'));
   const button=element('button','이 안 검토');button.type='button';button.disabled=!plan.available;
   button.addEventListener('click',async()=>{
    await missionRequest('/api/risks/'+encodeURIComponent(top.id)+'/plan');
    const m=lastState&&reviewMission(lastState);if(m?.risk_id!==top.id||m.approved)return;
    selectedResponse={mission_id:m.id,option_id:plan.id,plan_revision:m.plan_revision||0};$('assignmentPlan').value=plan.id;renderHumanApproval(lastState);renderVehicles(lastState);$('finalApprove').focus({preventScroll:true});
   });card.append(button);$('riskResponses').append(card);
  }
 }catch(error){$('riskRefresh').textContent='평가 연결 실패';$('riskList').textContent=error.message;$('riskResponses').replaceChildren();}
 finally{setTimeout(refreshRisks,10000);}
}
refreshRisks();

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

function faultSelector(){ $('faultType').hidden=$('scenarioSelect').value!=='fault'; }
$('scenarioSelect').addEventListener('change',faultSelector);faultSelector();
