"""Synthetic situation geometry shared by map and Gazebo; no vehicle control."""
import math
from xml.sax.saxutils import escape
from mission_console import SCENARIOS
from defense_scenarios import DEFENSE_SCENARIOS,contacts
COLORS={'P0':'1 .12 .18 1','P1':'1 .42 .08 1','P2':'1 .82 .12 1','P3':'.2 .65 1 1',None:'1 .82 .12 1'}

def targets(missions,sim_time):
    result=[]
    for m in missions:
        if m['scenario']=='fault':continue
        o=m.get('scene_origin')
        if not o:continue
        if m['scenario'] in DEFENSE_SCENARIOS:
            if m.get('manual_takeover') or m.get('execution',{}).get('status') not in ('completed','cancelled'):result.extend(contacts(m,sim_time if sim_time is not None else m.get('scene_last_time',o['sim_time'])))
            continue
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
    if target['scenario'] in DEFENSE_SCENARIOS:return defense_model_sdf(target)
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

def defense_model_sdf(t):
    scale=t.get('scale',1);parts=[]
    def visual(name,geometry,pose,color,glow=False):
        roughness=.16 if name=='glass' else .9 if name=='collar' or name.startswith('seat') else .55
        pbr='' if name.startswith('wake') or glow else f'<specular>.25 .25 .25 1</specular><pbr><metal><metalness>.06</metalness><roughness>{roughness}</roughness></metal></pbr>'
        parts.append(f'<visual name="{name}"><pose>{pose}</pose><geometry>{geometry}</geometry><material><ambient>{color}</ambient><diffuse>{color}</diffuse>'+pbr+ (f'<emissive>{color}</emissive>' if glow else '')+'</material><cast_shadows>true</cast_shadows></visual>')
    for name,color in [('hull','.21 .25 .27 1'),('deck','.43 .46 .46 1'),('collar','.055 .067 .07 1'),('cabin','.61 .65 .65 1'),('glass','.09 .19 .22 1'),('canopy','.47 .53 .53 1')]:
        visual(name,f'<mesh><uri>model://defense_contact/meshes/{name}.obj</uri><scale>{scale} {scale} {scale}</scale></mesh>','0 0 0 0 0 0',color)
    for side in [-1,1]:
        visual('outboard_'+str(side),'<box><size>.6 .5 1.2</size></box>',f'{-6.15*scale} {side*.7*scale} .5 0 0 0','.075 .085 .085 1')
        color='.9 .08 .04 1' if side>0 else '.06 .85 .26 1'
        visual('navigation_'+str(side),'<sphere><radius>.055</radius></sphere>',f'-.7 {side*.96*scale} 2.2 0 0 0',color,True)
    for side in [-1,1]:
        for x in [2,4.4]:visual(f'rail_post_{side}_{x}','<cylinder><radius>.025</radius><length>.6</length></cylinder>',f'{x} {side*1.15} 1.1 0 0 0','.48 .52 .53 1')
        visual(f'rail_{side}','<cylinder><radius>.03</radius><length>2.4</length></cylinder>',f'3.2 {side*1.15} 1.4 0 1.5708 0','.48 .52 .53 1')
        visual(f'seat_{side}','<box><size>1.2 .6 .25</size></box>',f'-4 {side*.8} 1.05 0 0 0','.075 .09 .1 1')
        visual(f'seat_back_{side}','<box><size>.18 .6 .7</size></box>',f'-4.55 {side*.8} 1.45 0 -.15 0','.075 .09 .1 1')
    visual('antenna','<cylinder><radius>.025</radius><length>1.6</length></cylinder>','-1.3 0 3.3 0 0 0','.2 .23 .24 1')
    visual('stern_light','<sphere><radius>.055</radius></sphere>','-1.3 0 4.1 0 0 0','.95 .94 .8 1',True)
    for side in [-1,1]:
        visual('wake_'+str(side),f'<mesh><uri>model://navis_ocean/meshes/usv_foam.obj</uri><scale>{max(.7,min(1.5,t.get("speed_mps",1.5)/2))} 1.1 1</scale></mesh>',f'-5 {side*.85} .06 0 0 {side*.12}','.83 .9 .9 .38')
    return f'<sdf version="1.8"><model name="{escape(t["name"])}"><static>true</static><pose>{t["x"]} {t["y"]} {t["z"]} {t.get("roll",0)} {t.get("pitch",0)} {t["yaw"]}</pose><link name="hull">'+''.join(parts)+'</link></model></sdf>'
