#!/usr/bin/env python3
"""Generate local low-poly vessel assets and a flat-water preparation world."""
from pathlib import Path
import math
import xml.etree.ElementTree as E
ROOT=Path(__file__).resolve().parents[1]
assets=ROOT/'ros_ws/src/navis_sim/models/navis_vessels/meshes'
assets.mkdir(parents=True,exist_ok=True)
def hull(name,length,width,height):
    outline=[(-length/2,-width/2),(length*.28,-width/2),(length/2,0),(length*.28,width/2),(-length/2,width/2)]
    vertices=[(x,y,height/2) for x,y in outline]+[(x*.85,y*.65,-height/2) for x,y in outline]
    faces=[(1,2,3),(1,3,4),(1,4,5),(6,8,7),(6,9,8),(6,10,9)]
    for i in range(5):
        j=(i+1)%5
        faces.extend([(i+1,i+6,j+6),(i+1,j+6,j+1)])
    (assets/name).write_text('# NAVIS generated low-poly hull, metres\n'+''.join(f'v {x} {y} {z}\n' for x,y,z in vertices)+''.join('f %d %d %d\n'%f for f in faces))
hull('usv.obj',2.2,.85,.45)
hull('ship.obj',14,3.6,1.6)
path=ROOT/'ros_ws/src/navis_sim/worlds/prep.sdf'
tree=E.parse(path);world=tree.getroot().find('world')
world.find('scene/ambient').text='.65 .65 .65 1'
world.find('scene/background').text='.55 .72 .86 1'
for model in list(world.findall('model')):
    if model.get('name') in ('red_box','green_sphere','escort_ship'):world.remove(model)
ground=world.find("model[@name='ground']")
if ground is None: ground=world.find("model[@name='sea_surface']")
ground.set('name','sea_surface')
for size in ground.findall('.//plane/size'):size.text='1000 1000'
for color in ground.findall('.//material/ambient')+ground.findall('.//material/diffuse'):color.text='.025 .20 .32 1'
mat=ground.find('.//visual/material')
if mat.find('specular') is None: E.SubElement(mat,'specular')
mat.find('specular').text='.5 .65 .75 1'
usv=world.find("model[@name='USV-01']")
usv.find('pose').text='0 0 .23 0 0 0'
visual=usv.find("link/visual[@name='hull']")
g=visual.find('geometry');g.clear();mesh=E.SubElement(g,'mesh');E.SubElement(mesh,'uri').text='model://navis_vessels/meshes/usv.obj'
usv.find('link/collision/geometry/box/size').text='2.2 .85 .45'
usv.find('link/sensor/pose').text='.55 0 1.15 0 0 0'
usv.find('link/sensor/camera/clip/far').text='200'
for old in list(usv.find('link').findall('visual')):
    if old.get('name') in ('deck','sensor_mast'): usv.find('link').remove(old)
def box(link,name,size,pose,color):
    visual=E.SubElement(link,'visual',name=name);E.SubElement(visual,'pose').text=pose
    geometry=E.SubElement(visual,'geometry');E.SubElement(E.SubElement(geometry,'box'),'size').text=size
    material=E.SubElement(visual,'material')
    E.SubElement(material,'ambient').text=color;E.SubElement(material,'diffuse').text=color
box(usv.find('link'),'deck','.9 .6 .25','-.2 0 .3 0 0 0','.85 .88 .90 1')
box(usv.find('link'),'sensor_mast','.07 .07 .9','-.4 0 .7 0 0 0','.2 .25 .3 1')
ship=E.SubElement(world,'model',name='escort_ship');E.SubElement(ship,'static').text='true';E.SubElement(ship,'pose').text=f'15 0 .5 0 0 {math.pi/2}'
link=E.SubElement(ship,'link',name='hull')
v=E.SubElement(link,'visual',name='hull');geo=E.SubElement(v,'geometry');E.SubElement(E.SubElement(geo,'mesh'),'uri').text='model://navis_vessels/meshes/ship.obj'
mat=E.SubElement(v,'material');E.SubElement(mat,'ambient').text='.32 .38 .43 1';E.SubElement(mat,'diffuse').text='.32 .38 .43 1'
box(link,'deck','10 3 .2','-1 0 .85 0 0 0','.55 .61 .65 1')
collision=E.SubElement(link,'collision',name='flight_deck')
E.SubElement(collision,'pose').text='-1 0 .85 0 0 0'
E.SubElement(E.SubElement(E.SubElement(collision,'geometry'),'box'),'size').text='10 3 .2'
box(link,'superstructure','4 2.1 1.8','-1 0 1.8 0 0 0','.65 .69 .72 1')
box(link,'bridge','2.2 2.3 .9','1 0 2.6 0 0 0','.72 .76 .79 1')
box(link,'windows','2.23 2.33 .24','1 0 2.8 0 0 0','.05 .18 .26 1')
box(link,'mast','.14 .14 3','-1 0 4 0 0 0','.4 .46 .5 1')
box(link,'radar','1.8 .14 .3','-1 0 5.3 0 0 0','.6 .65 .68 1')
# Camera on the GUI looks down toward the sea and both vessels.
gui=world.find('gui')
if gui is not None:world.remove(gui)
gui=E.SubElement(world,'gui',fullscreen='0')
p=E.SubElement(gui,'plugin',filename='MinimalScene',name='3D View')
E.SubElement(p,'engine').text='ogre2';E.SubElement(p,'scene').text='scene';E.SubElement(p,'camera_pose').text='-14 -22 18 0 .5 .65'
E.SubElement(p,'ambient_light').text='.65 .65 .65';E.SubElement(p,'background_color').text='.55 .72 .86'
for name in ['GzSceneManager','InteractiveViewControl','CameraTracking','WorldControl','WorldStats','EntityTree']:
    E.SubElement(gui,'plugin',filename=name,name=name)
E.indent(tree);tree.write(path,encoding='utf-8',xml_declaration=True)
