"""Abstract fictional threat cues; never a weapon or damage effectiveness model."""
import math

def view(vehicles,contacts,missions,sim_time):
    result={'items':[],'effects':[],'source':'synthetic_visualization'}
    if sim_time is None:return result
    fresh={v['id']:v for v in vehicles if v.get('connected') and v.get('telemetry')}
    drones=[v for v in fresh.values() if v['type']=='UAV' and not v.get('fault')]
    if not drones:return result
    for contact in contacts:
        if contact.get('contact_type') not in ('air','surface'):continue
        item=missions.get(contact['mission_id'],{});origin=item.get('scene_origin')
        if not origin:continue
        # Stable target across frames; numbering is presentation, not tactical selection.
        target=drones[(item['id']-1)%len(drones)];p=target['telemetry']
        execution=item.get('execution',{}).get('tasks',{})
        assigned=[t['vehicle'] for t in (item.get('approved') or {}).get('tasks',[])]
        status='대응 대기'
        if item.get('approved'):
            observed=bool(assigned) and all(id in fresh and not fresh[id].get('fault') and id in execution and not execution[id].get('blocked') for id in assigned)
            status='접촉 관측 유지' if observed and all(execution[id].get('stage') in ('tracking','screening','observing') for id in assigned) else '대응 기체 이동 중' if observed else '대응 상태 확인 필요'
        result['items'].append({'mission_id':item['id'],'attacker':contact['name'],'target':target['id'],'status':status,'outcome':'피해·방어 성공 미판정','basis':'Gazebo 기체 연결 + 임무 단계 · 공격 효과는 모의 시각 표시'})
        elapsed=max(0,sim_time-origin['sim_time']);phase=elapsed%8
        suffix=contact['name'];start=(contact['x'],contact['y'],contact['z']+2);end=(p['x'],p['y'],p['z'])
        # Repeating animated cue has arbitrary screen timing, no ballistic meaning.
        for i in range(3):
            fraction=(phase*.5-i*.1)
            if 0<=fraction<=1:
                x,y,z=[a+(b-a)*fraction for a,b in zip(start,end)]
                result['effects'].append({'name':f'threat_cue_{suffix}_{i}','scenario':'threat_visual','priority':'P1','effect_kind':'pulse','x':x,'y':y,'z':z,'yaw':0})
        if phase<3:
            result['effects'].append({'name':f'threat_focus_{suffix}','scenario':'threat_visual','priority':'P1','effect_kind':'focus','x':p['x'],'y':p['y'],'z':p['z'],'yaw':elapsed*.7})
        if status=='접촉 관측 유지':
            for id in assigned:
                pos=fresh[id]['telemetry']
                result['effects'].append({'name':f'observation_cue_{suffix}_{id}','scenario':'threat_visual','priority':'P3','effect_kind':'observed','x':pos['x'],'y':pos['y'],'z':pos['z']+1,'yaw':0})
    return result

def model_sdf(t):
    import xml.sax.saxutils as xml
    kind=t['effect_kind'];color='.1 .85 1 .75' if kind=='observed' else '1 .18 .04 .9'
    size=1.3 if kind=='pulse' else .7
    positions=[(0,0,0)] if kind=='pulse' else [(5*math.cos(i*math.pi/4),5*math.sin(i*math.pi/4),0) for i in range(8)]
    visuals=''.join(f'<visual name="cue_{i}"><pose>{x} {y} {z} 0 0 0</pose><geometry><sphere><radius>{size}</radius></sphere></geometry><cast_shadows>false</cast_shadows><material><ambient>{color}</ambient><diffuse>{color}</diffuse><emissive>{color}</emissive></material></visual>' for i,(x,y,z) in enumerate(positions))
    return f'<sdf version="1.8"><model name="{xml.escape(t["name"])}"><static>true</static><pose>{t["x"]} {t["y"]} {t["z"]} 0 0 0</pose><link name="cue">{visuals}</link></model></sdf>'
