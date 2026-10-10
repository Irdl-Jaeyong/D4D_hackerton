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
scene=E.SubElement(w,'scene');el(scene,'ambient','.55 .60 .67 1');el(scene,'background','.58 .73 .84 1');el(scene,'shadows','true')
l=E.SubElement(w,'light',name='sun',type='directional');el(l,'pose','0 0 100 0 0 0');el(l,'diffuse','1 .95 .85 1');el(l,'specular','.5 .5 .5 1');el(l,'direction','-.4 .3 -.8');el(l,'cast_shadows','true')
def model(name,pose):
    m=E.SubElement(w,'model',name=name);el(m,'static','true');el(m,'pose',pose);return m,E.SubElement(m,'link',name='base_link')
def visual(link,name,kind,data,pose='0 0 0 0 0 0',color='.45 .50 .55 1'):
    v=E.SubElement(link,'visual',name=name);el(v,'pose',pose);g=E.SubElement(v,'geometry');o=E.SubElement(g,kind)
    if kind=='box':el(o,'size',data)
    elif kind=='mesh':el(o,'uri',data)
    elif kind=='cylinder':el(o,'radius',data[0]);el(o,'length',data[1])
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
def odom(m,id):
    p=E.SubElement(m,'plugin',filename='ignition-gazebo-odometry-publisher-system',name='ignition::gazebo::systems::OdometryPublisher')
    el(p,'odom_frame','world');el(p,'robot_base_frame',id+'/base_link');el(p,'odom_publish_frequency','5');el(p,'dimensions','3');el(p,'odom_topic',f'/navis/{id.replace("-","_")}/odometry')
for i in range(cfg['ships']):
    id=f'SHIP-{i+1:02}';m,l=model(id,f'{i*90} 0 2.4 0 0 0');odom(m,id)
    v=visual(l,'hull','mesh','model://navis_vessels/meshes/ship.obj',color='.32 .39 .44 1');el(v.find('geometry/mesh'),'scale','4 4 3')
    visual(l,'deck','box','44 12 .3','-2 0 2.5 0 0 0','.34 .39 .42 1')
    for name,size,pose in [('bridge','10 7 5','8 0 5.2 0 0 0'),('windows','10.1 7.1 .9','8 0 6.6 0 0 0'),('mast','.3 .3 8','8 0 11 0 0 0'),('radar','4 .3 .6','8 0 14 0 0 0'),('hangar','7 8 3','-3 0 4.1 0 0 0')]:
        visual(l,name,'box',size,pose,'.045 .12 .18 1' if name=='windows' else '.48 .53 .56 1')
    for side in [-1,1]:
        visual(l,f'rail{side}','box','42 .1 .6',f'-2 {side*5.8} 3 0 0 0','.6 .64 .67 1')
    for x in [-19,-14,-9]:
        for dy in [-1,1]:visual(l,f'pad{x}_{dy}','box','3 .13 .02',f'{x} {dy*1.5} 2.66 0 0 0','.9 .91 .82 1')
        visual(l,f'padH{x}','box','.15 3 .02',f'{x} 0 2.66 0 0 0','.9 .91 .82 1')
for i in range(cfg['uavs']):
    id=f'UAV-{i+1:02}';p=initial[id]
    m,l=model(id,f'{p["x"]} {p["y"]} {p["z"]} 0 0 {p["yaw"]}');odom(m,id)
    visual(l,'body','box','.65 .35 .22',color='.16 .19 .21 1')
    for k,(a,b) in enumerate([(-.55,-.55),(-.55,.55),(.55,-.55),(.55,.55)]):
        visual(l,f'arm{k}','box','1.55 .08 .07',f'0 0 0 0 0 {math.pi/4 if a*b>0 else -math.pi/4}')
        visual(l,f'rotor{k}','cylinder',('.32','.035'),f'{a} {b} .12 0 0 0','.1 .12 .14 1')
for i in range(cfg['usvs']):
    id=f'USV-{i+1:02}';p=initial[id]
    m,l=model(id,f'{p["x"]} {p["y"]} {p["z"]} 0 0 {p["yaw"]}');odom(m,id)
    v=visual(l,'hull','mesh','model://navis_vessels/meshes/usv.obj',color='.16 .37 .41 1');el(v.find('geometry/mesh'),'scale','3 3 3')
    visual(l,'cabin','box','2 1.4 1','-.5 0 1 0 0 0','.5 .56 .6 1')
    visual(l,'sensor','cylinder',('.1','1.5'),'-.7 0 2 0 0 0','.18 .23 .28 1')
# World-fixed camera: positive pitch points the optical +X axis downward.
m,l=model('fleet_observer',cam_pose)
s=E.SubElement(l,'sensor',name='fleet_camera',type='camera');el(s,'always_on','true');el(s,'update_rate','5');el(s,'topic','/navis/camera')
c=E.SubElement(s,'camera');el(c,'horizontal_fov',cam['horizontal_fov']);im=E.SubElement(c,'image');el(im,'width','1280');el(im,'height','720');el(im,'format','R8G8B8');clip=E.SubElement(c,'clip');el(clip,'near','.1');el(clip,'far','1500')
gui=E.SubElement(w,'gui',fullscreen='0');p=E.SubElement(gui,'plugin',filename='MinimalScene',name='3D View');el(p,'engine','ogre2');el(p,'scene','scene');el(p,'camera_pose',cam_pose)
for name in ['GzSceneManager','InteractiveViewControl','CameraTracking','WorldControl','WorldStats','EntityTree']:E.SubElement(gui,'plugin',filename=name,name=name)
E.indent(sdf);E.ElementTree(sdf).write(R/'ros_ws/src/navis_sim/worlds/prep.sdf',encoding='utf-8',xml_declaration=True)
print(f"Built {cfg['ships']} flagship, {cfg['uavs']} UAVs, {cfg['usvs']} escort USVs")
