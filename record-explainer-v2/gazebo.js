/* Read-only telemetry. Clear current values on any failed poll. */
(() => {
  const body = document.getElementById('gazebo-vehicles');
  const status = document.getElementById('gazebo-status');
  const number = value => Number.isFinite(value) ? value.toFixed(2) : '—';
  async function poll() {
    try {
      const response = await fetch('/api/gazebo/state', {cache: 'no-store', signal: AbortSignal.timeout(5000)});
      if (!response.ok) throw new Error('bridge unavailable');
      const data = await response.json();
      if (!Array.isArray(data.vehicles)) throw new Error('invalid telemetry');
      window.dispatchEvent(new CustomEvent('gazebo-state', {detail: data.vehicles}));
      body.replaceChildren();
      let connected = 0;
      for (const vehicle of data.vehicles) {
        const fresh = vehicle.connected === true && Number.isFinite(vehicle.age_seconds) && vehicle.age_seconds < 5;
        const t = fresh ? vehicle.telemetry || {} : {};
        if (fresh) connected++;
        const row = document.createElement('tr');
        for (const value of [vehicle.id, fresh ? '연결됨' : '연결 끊김', number(t.x), number(t.y), number(t.z), number(t.speed)]) {
          const cell = document.createElement('td'); cell.textContent = value; row.append(cell);
        }
        row.tabIndex=0; row.style.cursor='pointer';
        const select=()=>window.dispatchEvent(new CustomEvent('gazebo-select',{detail:vehicle.id}));
        row.onclick=select; row.onkeydown=e=>{if(e.key==='Enter')select();};
        body.append(row);
      }
      status.textContent = `${data.vehicles.length}대 중 ${connected}대 수신 · ${new Date().toLocaleTimeString('ko-KR')}`;
    } catch (_) {
      body.replaceChildren();
      window.dispatchEvent(new CustomEvent('gazebo-state', {detail: []}));
      status.textContent = '상태 수신 실패 · 현재 위치 확인 불가';
    } finally { setTimeout(poll, 1000); }
  }
  poll();
})();

(() => {
  const img = document.getElementById('gazebo-camera');
  const status = document.getElementById('gazebo-camera-status');
  let previous;
  async function pollCamera() {
    try {
      const response = await fetch('/api/gazebo/camera', {cache: 'no-store', signal: AbortSignal.timeout(5000)});
      if (!response.ok) throw new Error('camera unavailable');
      const blob = await response.blob();
      const next = URL.createObjectURL(blob);
      try {
        const decoded = new Image(); decoded.src = next; await decoded.decode();
        img.src = next; img.hidden = false;
        if (previous) URL.revokeObjectURL(previous);
        previous = next;
      } catch (error) { URL.revokeObjectURL(next); throw error; }
      status.textContent = '실제 영상 수신 · ' + new Date().toLocaleTimeString('ko-KR');
    } catch (_) {
      img.hidden = true; img.removeAttribute('src');
      if (previous) URL.revokeObjectURL(previous);
      previous = undefined;
      status.textContent = '영상 수신 끊김';
    } finally { setTimeout(pollCamera, 1000); }
  }
  pollCamera();
})();

(() => {
 const canvas=document.getElementById('gazebo-map'),ctx=canvas.getContext('2d'),detail=document.getElementById('gazebo-selection');
 let vehicles=[],selected=null,points=[];
 const colors={UAV:'#3cd9ed',USV:'#ffc76e',SHIP:'#be9eff'};
 function draw(){
  const w=canvas.clientWidth,h=320,dpr=devicePixelRatio||1;
  canvas.width=Math.round(w*dpr);canvas.height=h*dpr;ctx.setTransform(dpr,0,0,dpr,0,0);ctx.clearRect(0,0,w,h);
  const fresh=vehicles.filter(v=>v.connected&&v.age_seconds<5&&v.telemetry&&Number.isFinite(v.telemetry.x)&&Number.isFinite(v.telemetry.y));
  points=[];if(!fresh.length){ctx.fillStyle='#98b2ca';ctx.fillText('현재 좌표 수신 없음',20,35);detail.textContent='현재 위치 확인 불가';return;}
  const xs=fresh.map(v=>v.telemetry.x),ys=fresh.map(v=>v.telemetry.y);
  const cx=(Math.min(...xs)+Math.max(...xs))/2,cy=(Math.min(...ys)+Math.max(...ys))/2;
  const scale=Math.min((w-80)/Math.max(120,Math.max(...xs)-Math.min(...xs)+30),(h-70)/Math.max(120,Math.max(...ys)-Math.min(...ys)+30));
  const px=x=>w/2+(x-cx)*scale,py=y=>h/2-(y-cy)*scale;
  const step=Math.max(10,Math.ceil(40/scale/10)*10);
  ctx.font='11px system-ui';ctx.fillStyle='#98b2ca';ctx.strokeStyle='#214252';
  for(let x=Math.ceil((cx-(w/2-35)/scale)/step)*step;x<cx+(w/2-35)/scale;x+=step){const p=px(x);ctx.beginPath();ctx.moveTo(p,20);ctx.lineTo(p,h-30);ctx.stroke();ctx.fillText(x.toFixed(0),p,h-12);}
  for(let y=Math.ceil((cy-(h/2-30)/scale)/step)*step;y<cy+(h/2-30)/scale;y+=step){const p=py(y);ctx.beginPath();ctx.moveTo(35,p);ctx.lineTo(w-15,p);ctx.stroke();ctx.fillText(y.toFixed(0),2,p);}
  for(const v of fresh){const x=px(v.telemetry.x),y=py(v.telemetry.y);points.push({id:v.id,x,y});ctx.fillStyle=colors[v.type]||'#fff';ctx.beginPath();ctx.arc(x,y,v.id===selected?7:4,0,Math.PI*2);ctx.fill();if(v.id===selected){ctx.fillText(v.id,x+10,y-8);}}
  const v=fresh.find(v=>v.id===selected);
  detail.textContent=v?`${v.id} · X ${v.telemetry.x.toFixed(2)} / Y ${v.telemetry.y.toFixed(2)} / Z ${v.telemetry.z.toFixed(2)} m`:'실제 월드 XY · 범위 자동 추적 · UAV: 시안 / USV: 노랑 / SHIP: 보라';
 }
 window.addEventListener('gazebo-state',e=>{vehicles=e.detail;draw();});
 window.addEventListener('gazebo-select',e=>{selected=e.detail;draw();});
 canvas.onclick=e=>{const r=canvas.getBoundingClientRect();let best=18;for(const p of points){const d=Math.hypot(e.clientX-r.left-p.x,e.clientY-r.top-p.y);if(d<best){best=d;selected=p.id;}}draw();};
 new ResizeObserver(draw).observe(canvas);
})();
