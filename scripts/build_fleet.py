#!/usr/bin/env python3
"""Build a reproducible Gazebo fleet scene; staged vehicles have no motion controller."""
import json, math
from convoy_motion import fleet_poses
from pathlib import Path
import xml.etree.ElementTree as E
R=Path(__file__).resolve().parents[1]
cfg=json.loads((R/'config/fleet.json').read_text())
initial=fleet_poses(0)
cam=cfg['camera']
cam_pose=' '.join(str(v) for v in [*cam['offset'],0,cam['pitch'],cam['yaw']])
sdf=E.Element('sdf',version='1.8'); w=E.SubElement(sdf,'world',name='navis_prep')
def el(parent,name,text,**attrs):
    x=E.SubElement(parent,name,attrs);x.text=str(text);return x
for filename,name in [('physics','Physics'),('sensors','Sensors'),('user-commands','UserCommands'),('scene-broadcaster','SceneBroadcaster')]:
    p=E.SubElement(w,'plugin',filename=f'ignition-gazebo-{filename}-system',name=f'ignition::gazebo::systems::{name}')
    if name=='Sensors':el(p,'render_engine','ogre2')
ph=E.SubElement(w,'physics',name='default',type='ignored');el(ph,'max_step_size','.004');el(ph,'real_time_factor','1')
scene=E.SubElement(w,'scene');el(scene,'ambient','.28 .32 .38 1');el(scene,'background','.58 .73 .84 1');el(scene,'shadows','true')
l=E.SubElement(w,'light',name='sun',type='directional');el(l,'pose','0 0 100 0 0 0');el(l,'diffuse','1 .95 .85 1');el(l,'specular','.5 .5 .5 1');el(l,'direction','-.4 .3 -.8');el(l,'cast_shadows','true')
def model(name,pose):
    m=E.SubElement(w,'model',name=name);el(m,'static','true');el(m,'pose',pose);return m,E.SubElement(m,'link',name='base_link')
def visual(link,name,kind,data,pose='0 0 0 0 0 0',color='.45 .50 .55 1'):
    v=E.SubElement(link,'visual',name=name);el(v,'pose',pose);g=E.SubElement(v,'geometry');o=E.SubElement(g,kind)
    if kind=='box':el(o,'size',data)
    elif kind=='mesh':el(o,'uri',data)
    elif kind=='cylinder':el(o,'radius',data[0]);el(o,'length',data[1])
    elif kind=='sphere':el(o,'radius',data)
    mat=E.SubElement(v,'material');el(mat,'ambient',color);el(mat,'diffuse',color);el(mat,'specular','.3 .35 .4 1')
    el(v,'cast_shadows','false' if name=='water' or name.startswith('ripple') else 'true')
    return v
# A visual ocean, without implying hydrodynamic simulation.
m,l=model('ocean','0 0 -.25 0 0 0')
v=visual(l,'water','mesh','model://navis_ocean/meshes/waterlow.dae',color='.025 .16 .24 1')
el(v.find('geometry/mesh'),'scale','4 4 4')
pbr=E.SubElement(v.find('material'),'pbr');metal=E.SubElement(pbr,'metal')
el(metal,'metalness','.25');el(metal,'roughness','.28')
el(metal,'normal_map','model://navis_ocean/materials/textures/wave_normals.dds')
# Near-field ocean uses VRX's animated Gerstner/Fresnel shader.
# Keep the flat far-field below troughs; it cannot mask the near waves.
v.find('pose').text='0 0 -.35 0 0 0'
v=visual(l,'near_water','mesh','model://navis_ocean/meshes/near_ocean.obj')
v.remove(v.find('material'));v.find('cast_shadows').text='false'
wave=E.SubElement(v,'plugin',filename='libNavisWaveVisual.so',name='vrx::WaveVisual')
el(wave,'model_path','/project/ros_ws/src/navis_sim/models/navis_ocean/model.sdf')
shader=E.SubElement(wave,'shader');el(shader,'vertex','materials/programs/GerstnerWaves_vs_330.glsl');el(shader,'fragment','materials/programs/GerstnerWaves_fs_330.glsl')
params=E.SubElement(shader,'parameters')
for key,val in [('rescale','.18'),('bumpScale','440 440'),('hdrMultiplier','.48'),('fresnelPower','4'),('shallowColor','.018 .12 .15 1'),('deepColor','.007 .037 .064 1')]:el(params,key,val)
field=E.SubElement(wave,'wavefield');el(field,'topic','/navis/wavefield');waves=E.SubElement(field,'wave')
for key,val in [('model','CWR'),('number','3'),('amplitude','.055'),('period','5.5'),('scale','1.4'),('angle','.45'),('steepness','.15'),('direction','.6435'),('tau','2')]:el(waves,key,val)
def odom(m,id):
    p=E.SubElement(m,'plugin',filename='ignition-gazebo-odometry-publisher-system',name='ignition::gazebo::systems::OdometryPublisher')
    el(p,'odom_frame','world');el(p,'robot_base_frame',id+'/base_link');el(p,'odom_publish_frequency','5');el(p,'dimensions','3');el(p,'odom_topic',f'/navis/{id.replace("-","_")}/odometry')
for i in range(cfg['ships']):
    id=f'SHIP-{i+1:02}';carrier,_=model(id,f'{i*220} 0 2.4 0 0 0');odom(carrier,id)
    m,l=model(id+'_hull',f'{i*220} 0 2.4 0 0 0')
    # Licensed, complete source ship; native metre scale, waterline at z=-.25.
    parts=json.loads((R/'ros_ws/src/navis_sim/models/arleigh_burke/meshes/parts.json').read_text())
    for k,part in enumerate(parts):
        if part["mesh"]=="part_47.obj":continue  # Entire surface is replaced by textured decks.
        v=visual(l,f'ddg_part_{k}','mesh','model://arleigh_burke/meshes/'+('part_46_sides.obj' if part['mesh']=='part_46.obj' else part['mesh']),'0 0 -2.65 0 0 0',color=' '.join(map(str,[*part['color'],1])))
        pbr=E.SubElement(v.find('material'),'pbr');metal=E.SubElement(pbr,'metal');el(metal,'roughness','.18' if max(part['color'])<.11 else '.8');el(metal,'metalness','0')
    for name,texture in [('flight_deck','nsflightdeck.jpg'),('nonskid_deck','nonskid.jpg')]:
        v=visual(l,name,'mesh',f'model://arleigh_burke/meshes/{name}.obj','0 0 -2.65 0 0 0',color='.65 .65 .65 1')
        pbr=E.SubElement(v.find('material'),'pbr');metal=E.SubElement(pbr,'metal');el(metal,'albedo_map','model://arleigh_burke/materials/textures/'+texture);el(metal,'roughness','.95');el(metal,'metalness','0')
    # Aft flight-deck safety rails, an approximate visual addition.
    for side,y in [('port',-7.7),('starboard',5.6)]:
        for railz in [3.65,4.05]:visual(l,f'rail_{side}_{railz}','cylinder',('.025','19'),f'-65 {y} {railz-2.65} 0 {math.pi/2} 0',color='.42 .46 .48 1')
        for k in range(11):visual(l,f'post_{side}_{k}','cylinder',('.03','.9'),f'{-74+k*1.8} {y} {3.65-2.65} 0 0 0',color='.42 .46 .48 1')
for i in range(cfg['uavs']):
    id=f'UAV-{i+1:02}';p=initial[id]
    m,l=model(id,f'{p["x"]} {p["y"]} {p["z"]} 0 0 {p["yaw"]}');odom(m,id)
    visual(l,'body','mesh','model://defense_contact/meshes/escort_body.obj',color='.29 .33 .36 1')
    visual(l,'camera_gimbal','sphere','.075','.19 0 -.17 0 0 0',color='.045 .065 .075 1')
    visual(l,'nose','box','.12 .28 .08','.34 0 -.02 0 0 0',color='.12 .15 .18 1')
    for side in [-1,1]:
        for x in [-.24,.24]:visual(l,f'leg_{side}_{x}','cylinder',('.025','.24'),f'{x} {side*.28} -.20 0 0 0',color='.38 .42 .46 1')
        visual(l,f'skid_{side}','cylinder',('.025','.8'),f'0 {side*.28} -.32 0 {math.pi/2} 0',color='.25 .28 .3 1')
    for k,(a,b) in enumerate([(-.55,-.55),(-.55,.55),(.55,-.55),(.55,.55)]):
        visual(l,f'arm{k}','box','1.55 .08 .07',f'0 0 0 0 0 {math.pi/4 if a*b>0 else -math.pi/4}',color='.09 .105 .12 1')
        visual(l,f'motor{k}','cylinder',('.065','.12'),f'{a} {b} .07 0 0 0',color='.62 .66 .7 1')
        visual(l,f'rotor{k}','cylinder',('.32','.035'),f'{a} {b} .12 0 0 0','.13 .15 .17 .22')
for i in range(cfg['usvs']):
    id=f'USV-{i+1:02}';p=initial[id]
    m,l=model(id,f'{p["x"]} {p["y"]} {p["z"]} 0 0 {p["yaw"]}');odom(m,id)
    m.find('static').text='false'
    inertia=E.SubElement(l,'inertial');el(inertia,'mass','250')
    tensor=E.SubElement(inertia,'inertia')
    for key,value in [('ixx',150),('iyy',650),('izz',700),('ixy',0),('ixz',0),('iyz',0)]:el(tensor,key,value)
    for side,y in [('port',-.8),('starboard',.8)]:
        collision=E.SubElement(l,'collision',name=side+'_hull')
        el(collision,'pose',f'0 {y} -.85 0 0 0')
        geometry=E.SubElement(collision,'geometry');box=E.SubElement(geometry,'box');el(box,'size','4.4 .45 .45')
    physics=E.SubElement(m,'plugin',filename='libNavisMaritimeEscort.so',name='navis::MaritimeEscort')
    physics.append(E.fromstring(E.tostring(field)))
    el(physics,'target_model',f'USV_target_{i+1:02}')
    for key,value in [('phase',2*math.pi*i/cfg['usvs']),('leader_speed',cfg['motion']['ship_speed']),('angular_speed',cfg['motion']['escort_angular_speed']),('radius_x',cfg['motion']['escort_radii'][0]),('radius_y',cfg['motion']['escort_radii'][1]),('diagnostics_topic',f'/navis/{id.replace("-","_")}/physics')]:el(physics,key,value)
    v=visual(l,'wamv' ,'mesh','model://wamv_real/mesh/WAM-V-Base.dae','0 0 -1.1 0 0 0',color='1 1 1 1')
    pbr=E.SubElement(v.find('material'),'pbr');metal=E.SubElement(pbr,'metal')
    for tag,texture in [('albedo_map','Albedo'),('normal_map','Normal'),('roughness_map','Roughness'),('metalness_map','Metalness')]:
        el(metal,tag,f'model://wamv_real/mesh/WAM-V_{texture}.png')
# Invisible physical controller goals; only these markers receive pose commands.
for i in range(cfg['usvs']):
    p=initial[f'USV-{i+1:02}']
    model(f'USV_target_{i+1:02}',f'{p["x"]} {p["y"]} .7 0 0 0')
# Persistent path samples with progressively wider, fainter foam.
for name,p in initial.items():
    if not name.startswith('wake_'):continue
    segment=int(name.rsplit('_',1)[1]);flagship='SHIP-' in name
    m,l=model(name,f'{p["x"]} {p["y"]} {p["z"]} 0 0 {p["yaw"]}')
    v=visual(l,'foam','mesh','model://navis_ocean/meshes/foam_patch.obj',color='.72 .82 .82 1')
    el(v.find('geometry/mesh'),'scale',f'{2.8 if flagship else 1.7} {(8 if flagship else .9)*(1+segment*.07)} 1')
    el(v,'transparency',.22+.73*segment/19);v.find('cast_shadows').text='false'
# Cameras inherit the flagship transform in the same render update. They never
# orbit, ease toward a target, or receive independent per-frame pose commands.
ship_link=w.find("model[@name='SHIP-01']/link")
for mode,view in cfg['camera_views'].items():
    if mode=='inspect':
        _,sensor_link=model('inspection_camera','0 0 30 0 0 0')
    else:sensor_link=ship_link
    s=E.SubElement(sensor_link,'sensor',name=f'fleet_camera_{mode}',type='camera')
    ox,oy,oz=view['offset']
    el(s,'pose','0 0 0 0 0 0' if mode=='inspect' else f'{ox} {oy} {oz-2.4} 0 {view["pitch"]} {view["yaw"]}')
    el(s,'always_on','true');el(s,'update_rate','3' if mode=='inspect' else '5');el(s,'topic',f'/navis/camera/{mode}')
    c=E.SubElement(s,'camera');el(c,'horizontal_fov',view['horizontal_fov'])
    im=E.SubElement(c,'image');el(im,'width','1280');el(im,'height','720');el(im,'format','R8G8B8')
    clip=E.SubElement(c,'clip');el(clip,'near','.1');el(clip,'far','1500')
gui=E.SubElement(w,'gui',fullscreen='0');p=E.SubElement(gui,'plugin',filename='MinimalScene',name='3D View');el(p,'engine','ogre2');el(p,'scene','scene');el(p,'camera_pose',cam_pose)
for name in ['GzSceneManager','InteractiveViewControl','CameraTracking','WorldControl','WorldStats','EntityTree']:E.SubElement(gui,'plugin',filename=name,name=name)
E.indent(sdf);E.ElementTree(sdf).write(R/'ros_ws/src/navis_sim/worlds/prep.sdf',encoding='utf-8',xml_declaration=True)
print(f"Built {cfg['ships']} flagship, {cfg['uavs']} UAVs, {cfg['usvs']} escort USVs")
