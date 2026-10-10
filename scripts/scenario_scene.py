"""Synthetic situation geometry shared by map and Gazebo; no vehicle control."""
import math
from xml.sax.saxutils import escape
from mission_console import SCENARIOS
COLORS={'P0':'1 .12 .18 1','P1':'1 .42 .08 1','P2':'1 .82 .12 1','P3':'.2 .65 1 1',None:'1 .82 .12 1'}

def targets(missions,sim_time):
    result=[]
    for m in missions:
        if m['scenario']=='fault':continue
        o=m.get('scene_origin')
        if not o:continue
        t=max(0,(sim_time if sim_time is not None else m.get('scene_last_time',o['sim_time']))-o['sim_time'])
        x,y=SCENARIOS[m['scenario']]['offset']
        slot=m.get('scene_slot',0);x+=40*slot;y+=8*(slot%3)
        yaw=o.get('yaw',0)
        if m['scenario']=='crossing':
            # Forward at convoy speed, approach laterally, then maintain safe offset.
            x+=1.5*t;y=min(-55+8*(slot%3),y+.8*t);heading=yaw+math.atan2(.8 if t<43.75 else 0,1.5)
        else:heading=yaw
        c,s=math.cos(yaw),math.sin(yaw)
        result.append({'mission_id':m['id'],'name':f"situation_{m['id']}",'scenario':m['scenario'],
                       'priority':m.get('risk',{}).get('priority'),'x':o['x']+c*x-s*y,'y':o['y']+s*x+c*y,
                       'z':0,'yaw':heading,'source':'synthetic','title':SCENARIOS[m['scenario']]['title']})
    return result

def model_sdf(target):
    pieces=[]
    def visual(name,geom,pos,color,rotation='0 0 0'):
        glow=f'<emissive>{color}</emissive>' if name.startswith('marker_') or name=='priority_flag' else ''
        pieces.append(f'<visual name="{name}"><pose>{pos} {rotation}</pose><geometry>{geom}</geometry><cast_shadows>false</cast_shadows><material><ambient>{color}</ambient><diffuse>{color}</diffuse>{glow}</material></visual>')
    def box(name,size,pos,color,rotation='0 0 0'):
        visual(name,f'<box><size>{size}</size></box>',pos,color,rotation)
    def sphere(name,r,pos,color):visual(name,f'<sphere><radius>{r}</radius></sphere>',pos,color)
    color=COLORS.get(target.get('priority'),COLORS[None])
    # Large perimeter is a visible synthetic identification marker, not object scale.
    for i,(pos,size) in enumerate([('0 -14 .35','30 1 .35'),('0 14 .35','30 1 .35'),('-14 0 .35','1 28 .35'),('14 0 .35','1 28 .35')]):box('marker_'+str(i),size,pos,color)
    box('flag_pole','.3 .3 9','-10 10 4.5','1 1 1 1');box('priority_flag','5 .2 3','-7.5 10 8',color)
    if target['scenario']=='crossing':
        box('hull','21 7 2','0 0 1.2','.08 .22 .35 1')
        box('deck','19 6 .4','0 0 2.4','.8 .85 .87 1')
        box('cabin','7 4 3','-2 0 4','1 .95 .8 1')
        box('bridge_glass','.1 4 1.1','1.6 0 4.5','.12 .55 .8 1')
        box('roof','8 5 .35','-2 0 5.7','.95 .35 .15 1')
        box('mast','.3 .3 4','-3 0 7.5','1 1 1 1')
        for i in range(6):box('wake_'+str(i),'4 6 .04',f'{-14-5*i} 0 .18',f'1 1 1 {max(.1,.55-.07*i)}')
    elif target['scenario']=='debris':
        for i,(x,y,angle) in enumerate([(-5,-4,.3),(4,3,-.5),(-1,6,.9),(6,-5,.2)]):box('floating_log_'+str(i),'9 1.3 1',f'{x} {y} .5','.36 .19 .07 1',f'0 0 {angle}')
        box('floating_container','6 3 2','0 0 1','.8 .25 .08 1')
    elif target['scenario']=='rescue':
        sphere('head',.35,'0 0 1.1','.85 .6 .4 1');box('life_jacket','1 .7 .8','0 0 .5','1 .3 .03 1')
        for i in range(12):
            a=2*math.pi*i/12;sphere('lifebuoy_'+str(i),.25,f'{2.2+math.cos(a)} {math.sin(a)} .35','1 .4 .04 1' if i%3 else '1 1 1 1')
        box('left_arm','1.2 .25 .25','-.6 0 .65','.85 .6 .4 1');box('right_arm','1.2 .25 .25','.6 0 .65','.85 .6 .4 1')
    name=escape(target['name'],{'"':'&quot;'})
    return f'<sdf version="1.8"><model name="{name}"><static>true</static><pose>{target["x"]} {target["y"]} {target["z"]} 0 0 {target["yaw"]}</pose><link name="object">'+''.join(pieces)+'</link></model></sdf>'
