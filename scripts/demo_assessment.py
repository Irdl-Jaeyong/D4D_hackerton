"""Presentation-only state counter and mission continuity check, not combat modeling."""
import json,math
from pathlib import Path
CONFIG=json.loads((Path(__file__).resolve().parents[1]/'config/demo_assessment.json').read_text())

def evaluate(item,vehicles,sim_time):
    r={'source':'demo_rules','label':CONFIG['label'],'result':'평가 불가','virtual_state':None,'events':0,'remaining_seconds':None,'maintained':0,'interrupted':0,'assigned':0,'returned':0,'missing':[],'basis':[]}
    origin=(item.get('scene_origin') or {}).get('sim_time')
    if sim_time is None or origin is None or sim_time<origin:
        r['missing']=['현재 시뮬레이션 시간 또는 상황 시작 시간'];return r
    elapsed=min(CONFIG['window_seconds'],max(0,sim_time-origin))
    r.update(events=math.floor(elapsed/CONFIG['event_interval_seconds']),remaining_seconds=round(CONFIG['window_seconds']-elapsed,1))
    r['virtual_state']=max(0,100-r['events']*CONFIG['virtual_loss_per_event'])
    r['basis'].append(f"가상 상태값: 100 − 모의 이벤트 {r['events']}회 × {CONFIG['virtual_loss_per_event']}점; 대응안과 무관한 시연 카운터")
    assigned=list(dict.fromkeys(t['vehicle'] for t in (item.get('approved') or {}).get('tasks',[])))
    r['assigned']=len(assigned);known={v['id']:v for v in vehicles};tasks=item.get('execution',{}).get('tasks',{})
    for id in assigned:
        v=known.get(id);task=tasks.get(id)
        if v is None or v.get('connected') is None:r['missing'].append(id+' 연결 상태');continue
        if not v['connected'] or v.get('fault') or (task and task.get('blocked')):
            r['interrupted']+=1;r['basis'].append(id+' 연결 지연·고장·진행 차단 확인');continue
        if not v.get('telemetry') or not task or task.get('stage') is None or task.get('blocked') is None:
            r['missing'].append(id+' 최신 위치 또는 임무 단계');continue
        stage=task['stage']
        if stage=='completed':r['returned']+=1
        if stage in CONFIG['maintained_stages']:r['maintained']+=1
        r['basis'].append(id+' 현재 임무 단계: '+stage)
    if elapsed<CONFIG['window_seconds']:r['result']='평가 진행 중'
    elif r['missing']:r['result']='평가 불가'
    elif not assigned or not r['maintained']:r['result']='임무 유지 실패'
    elif r['maintained']==len(assigned):r['result']='임무 유지 성공'
    else:r['result']='일부 중단'
    r['basis'].append('현재 연결·고장·임무 단계의 판정; 전체 구간 이력이나 물리적 피해 판정은 아님')
    return r
