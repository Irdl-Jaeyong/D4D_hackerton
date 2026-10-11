"""Scripted, non-weapon contact approaches and persistent observation/screen positions."""
import json,math
from pathlib import Path
DEFENSE_RESPONSES=json.loads((Path(__file__).resolve().parents[1]/'config/defense_responses.json').read_text())
DEFENSE_SCENARIOS=json.loads((Path(__file__).resolve().parents[1]/'config/defense_scenarios.json').read_text())

def contacts(m,sim_time):
    profile=DEFENSE_SCENARIOS[m['scenario']];o=m['scene_origin'];elapsed=max(0,sim_time-o['sim_time']);slot=m.get('scene_slot',0)%2
    yaw=o.get('yaw',0);c,s=math.cos(yaw),math.sin(yaw);out=[]
    for i,bearing in enumerate(profile['bearing_degrees']):
        def position(t):
            extra=slot*22;gap=profile['initial_range_m']+extra-profile['standoff_m']
            radius=profile['standoff_m']+gap*math.exp(-profile['closing_speed_mps']*t/gap)
            a=math.radians(bearing)+.025*math.sin(.035*t+i)+slot*.075
            x=1.5*t+radius*math.cos(a);y=radius*math.sin(a)
            return o['x']+c*x-s*y,o['y']+s*x+c*y
        contact_type=profile.get('contact_types',['surface']*len(profile['bearing_degrees']))[i]
        altitude=95+12*math.sin(elapsed*.08+i) if contact_type=='air' else -8 if contact_type=='underwater' else .08*math.sin(elapsed*1.1+i)
        x,y=position(elapsed);xx,yy=position(elapsed+.1);heading=math.atan2(yy-y,xx-x)
        ship=(o['x']+c*1.5*elapsed,o['y']+s*1.5*elapsed)
        out.append({'mission_id':m['id'],'contact_index':i,'name':f"situation_{m['id']}"+(f'_{i}' if i else ''),'scenario':m['scenario'],
          'priority':m.get('risk',{}).get('priority'),'x':x,'y':y,'z':altitude,'contact_type':contact_type,'display_name':{'surface':'외부 선박','air':'미식별 드론','floating':'의심 부유물','interference':'통신 교란 구역','underwater':'수중 접촉 추정'}[contact_type],
          'roll':.012*math.sin(elapsed*.8+i),'pitch':.008*math.cos(elapsed*1.3+i),'yaw':heading,
          'range_m':round(math.hypot(x-ship[0],y-ship[1]),1),'speed_mps':round(math.hypot(xx-x,yy-y)/.1,2),
          'source':'scripted_contact','title':f"{profile['title']} · {'좌현' if y>ship[1] else '우현'} 접촉 {i+1}",
          'track_id':f"T{m['id']:03}-{i+1}",'scale':1.15 if m['scenario']=='patrol_contact' else 1.0})
    return out

def defense_goal(kind,ship,contact,slot=0,contact_type='surface',goal_policy=None):
    dx,dy=contact[0]-ship[0],contact[1]-ship[1];distance=max(math.hypot(dx,dy),1);ux,uy=dx/distance,dy/distance
    lateral=(-1 if slot%2 else 1)*(18+(16 if goal_policy else 12)*(slot//2))
    altitude=(135 if contact_type=='air' else 85)+18*slot
    if goal_policy in ('protect','avoid'):
        radius=(70 if kind=='USV' else 110) if goal_policy=='protect' else (105 if kind=='USV' else 130)
        direction=-1 if goal_policy=='avoid' else 1
        x,y=ship[0]+direction*ux*radius-uy*lateral,ship[1]+direction*uy*radius+ux*lateral
        # Never place a near-ship USV goal inside the flagship safety footprint.
        if kind=='USV' and abs(x-ship[0])<100 and abs(y-ship[1])<42:
            y=ship[1]+math.copysign(45+16*(slot//2),y-ship[1] or lateral)
        return x,y,.7 if kind=='USV' else altitude
    if kind=='USV':
        radius=min(145,max(115,distance*(.72 if contact_type in ('floating','underwater') else .52)))
        if goal_policy=='standoff':radius=max(70,min(145,distance-110))
        elif goal_policy=='investigate':radius=max(115,min(185,distance-80))
        x,y=ship[0]+ux*radius-uy*lateral,ship[1]+uy*radius+ux*lateral
        if abs(x-ship[0])<100 and abs(y-ship[1])<42:
            y=ship[1]+math.copysign(45+16*(slot//2),y-ship[1] or lateral)
        return x,y,.7
    gap=75 if goal_policy=='standoff' else 35
    return contact[0]-ux*gap-uy*lateral,contact[1]-uy*gap+ux*lateral,altitude

def formation_goals(group,mode,points,scenario):
    if scenario not in DEFENSE_SCENARIOS:return points
    if group=='uav' and mode=='v' and scenario=='rear_approach':return [(-x,-y,z) for x,y,z in points]
    if group=='uav' and mode=='triangle' and scenario=='fast_approach':return [(x+55,y,z) for x,y,z in points]
    return points
