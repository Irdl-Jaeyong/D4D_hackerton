const $=id=>document.getElementById(id);let history=[],connections={},lastState=null;
function event(text){if(!$('events'))return;const li=document.createElement('li');li.textContent=`${new Date().toLocaleTimeString('ko-KR')} · ${text}`;$('events').prepend(li);while($('events').children.length>20)$('events').lastChild.remove();}
function bubble(text,role){const p=document.createElement('p');p.className='bubble '+role;p.textContent=text;$('messages').append(p);$('messages').scrollTop=$('messages').scrollHeight;return p;}
const bandColors=['#55e7ef','#7ebaff','#ae97ff','#ffb567','#88ed9d'];
function map(state){
  const c=$('map'),ctx=c.getContext('2d');ctx.clearRect(0,0,c.width,c.height);
  const lead=state.vehicles.find(v=>v.id==='SHIP-01'&&v.connected);
  const ox=lead?lead.telemetry.x:0,oy=lead?lead.telemetry.y:0;
  const motion=state.scene?.motion,extent=Math.max(motion?.hemisphere_radius||52,...(motion?.escort_radii||[48,32]));
  const sx=(c.width-100)/(2*extent),sy=(c.height-65)/(2*extent);
  const point=(x,y)=>[c.width/2+(x-ox)*sx,c.height/2-(y-oy)*sy];
  ctx.strokeStyle='#193b50';
  for(let x=0;x<c.width;x+=38){ctx.beginPath();ctx.moveTo(x,0);ctx.lineTo(x,c.height);ctx.stroke();}
  for(let y=0;y<c.height;y+=30){ctx.beginPath();ctx.moveTo(0,y);ctx.lineTo(c.width,y);ctx.stroke();}
  ctx.font='12px sans-serif';ctx.fillStyle='#9cb7c9';ctx.fillText('메인 함선 기준 · 청록: USV / 색상별: 드론 고도 편대',15,22);
  ctx.strokeStyle='#2c6d77';ctx.setLineDash([5,6]);ctx.beginPath();ctx.ellipse(c.width/2,c.height/2,(motion?.escort_radii[0]||48)*sx,(motion?.escort_radii[1]||32)*sy,0,0,Math.PI*2);ctx.stroke();ctx.setLineDash([]);
  for(const v of state.vehicles){
    if(!v.connected)continue;const t=v.telemetry,[x,y]=point(t.x,t.y);
    const ring=(parseInt(v.id.split('-')[1],10)-1)%5;
    ctx.fillStyle=v.type==='SHIP'?'#fff':v.type==='USV'?'#25dbcc':bandColors[ring];
    ctx.save();ctx.translate(x,y);ctx.rotate(-t.yaw);
    if(v.type==='UAV'){ctx.beginPath();ctx.arc(0,0,3.5,0,Math.PI*2);ctx.fill();}
    else{ctx.beginPath();ctx.moveTo(v.type==='SHIP'?20:9,0);ctx.lineTo(-9,-5);ctx.lineTo(-9,5);ctx.closePath();ctx.fill();}ctx.restore();
    if(v.type!=='UAV'){ctx.fillStyle='#fff';ctx.fillText(v.id,x+10,y-7);}
  }
}
function cameraOverlay(state){
  const c=$('cameraOverlay'),ctx=c.getContext('2d');ctx.clearRect(0,0,c.width,c.height);
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
  if($('showDome').checked){
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
    const color=v.type==='SHIP'?'#fff':v.type==='USV'?'#25dbcc':bandColors[ring];
    ctx.fillStyle=color;ctx.beginPath();ctx.arc(q[0],q[1],v.type==='UAV'?3:4,0,Math.PI*2);ctx.fill();
    if(v.type!=='UAV'||v.id==='UAV-01'){ctx.fillStyle='#06121dcc';ctx.fillRect(q[0]+6,q[1]-18,73,19);ctx.fillStyle=color;ctx.fillText(v.id,q[0]+10,q[1]-4);}
  }
  ctx.fillStyle='#05131ecc';ctx.fillRect(14,14,405,30);ctx.fillStyle='#dcebf7';ctx.fillText('메인 함선 1 · 호위 USV 10 · 드론 40 / 반구 8자 순찰',24,34);
}
$('cameraView').addEventListener('change',async()=>{
  const select=$('cameraView');select.disabled=true;
  try{const r=await fetch('/api/camera/view',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({mode:select.value})});if(!r.ok)throw Error('시점 변경 실패');}
  catch(err){event(err.message);if(lastState)select.value=lastState.camera_view||'wide';}
  finally{select.disabled=false;}
});
$('showDome').addEventListener('change',()=>{if(lastState)cameraOverlay(lastState);});
async function poll(){try{const r=await fetch('/api/state');if(!r.ok)throw Error();const s=await r.json();lastState=s;if(!$('cameraView').disabled)$('cameraView').value=s.camera_view||'wide';$('cards').replaceChildren();for(const v of s.vehicles){const card=document.createElement('div');card.className='card';const name=document.createElement('strong');name.textContent=v.id;const badge=document.createElement('span');badge.className='badge'+(v.connected?' on':'');badge.textContent=v.connected?'연결됨':'미연결';const info=document.createElement('small');info.textContent=v.connected?`x ${v.telemetry.x.toFixed(2)} · y ${v.telemetry.y.toFixed(2)} · z ${(v.telemetry.z||0).toFixed(2)}m / ${v.telemetry.speed.toFixed(2)}m/s`:'실제 데이터 없음';card.append(name,badge,info);$('cards').append(card);if(connections[v.id]!==v.connected){event(`${v.id} ${v.connected?'Gazebo·ROS 연결':'미연결'}`);connections[v.id]=v.connected;}}$('connected').textContent=`${s.vehicles.filter(v=>v.connected).length} / ${s.vehicles.length} 연결`;$('camera').style.display=s.camera_available?'block':'none';$('cameraEmpty').style.display=s.camera_available?'none':'block';if(s.camera_available)$('camera').src='/api/camera?t='+Date.now();map(s);cameraOverlay(s);}catch{$('connected').textContent='백엔드 연결 끊김';document.querySelectorAll('.badge').forEach(b=>{b.className='badge';b.textContent='확인 불가';});$('map').getContext('2d').clearRect(0,0,760,300);$('camera').style.display='none';$('cameraEmpty').style.display='block';$('cameraEmpty').textContent='백엔드 연결 끊김';$('cameraOverlay').getContext('2d').clearRect(0,0,1280,720);}finally{setTimeout(poll,1000);}}
$('chatForm').addEventListener('submit',async e=>{e.preventDefault();const message=$('message').value.trim();if(!message)return;bubble(message,'user');$('message').value='';$('send').disabled=true;$('chatStatus').textContent='AI 분석 중 · 최초 요청은 로딩 시간이 걸릴 수 있습니다';try{const r=await fetch('/api/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({message,use_camera:$('useCamera').checked,history:history.slice(-8)})});const data=await r.json();if(!r.ok)throw Error(data.detail||'요청 실패');bubble(data.reply,'ai');history.push({role:'user',content:message},{role:'assistant',content:data.reply.slice(0,4000)});$('chatStatus').textContent=`${data.elapsed_seconds}초 · ${data.used_camera?'카메라 포함':'텍스트'} · 명령 실행 없음`;}catch(err){bubble(err.message,'ai error');$('chatStatus').textContent='요청 실패';}finally{$('send').disabled=false;}});
async function health(){try{const r=await fetch('/api/health'),s=await r.json();$('health').textContent=s.model_installed?'백엔드 · Ollama 준비됨':'Ollama 또는 모델 확인 필요';}catch{$('health').textContent='백엔드 연결 실패';}setTimeout(health,15000);}poll();health();
