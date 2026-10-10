#!/usr/bin/env python3
from pathlib import Path
import copy
import re
import xml.etree.ElementTree as E
ROOT=Path(__file__).resolve().parents[1]
model=ROOT/'ros_ws/src/navis_sim/models/x3_uav/model.sdf'
t=E.parse(model)
for uri in t.getroot().iter('uri'):
    if uri.text and '/files/meshes/' in uri.text:
        uri.text='model://x3_uav/meshes/'+uri.text.split('/files/meshes/')[-1]
E.indent(t);t.write(model,encoding='utf-8',xml_declaration=True)
p=ROOT/'ros_ws/src/navis_sim/worlds/prep.sdf'
t=E.parse(p);world=t.getroot().find('world')
for inc in list(world.findall('include')):
    if (inc.findtext('name') or '').startswith('UAV-'):world.remove(inc)
link=world.find("model[@name='escort_ship']/link")
if link.find("collision[@name='flight_deck']") is None:
    c=E.SubElement(link,'collision',name='flight_deck');E.SubElement(c,'pose').text='-1 0 .85 0 0 0'
    E.SubElement(E.SubElement(E.SubElement(c,'geometry'),'box'),'size').text='10 3 .2'
source=(ROOT/'outputs/quadcopter_original.sdf').read_text()
example=E.fromstring(re.sub(r'<!--.*?-->', '', source, flags=re.S)).find('world/include')
for idx,(x,y) in enumerate([(14.2,-5.2),(15.8,-5.2),(14.2,-3.5),(15.8,-3.5)],1):
    name=f'UAV-{idx:02d}'
    inc=E.SubElement(world,'include');E.SubElement(inc,'uri').text='model://x3_uav';E.SubElement(inc,'name').text=name;E.SubElement(inc,'pose').text=f'{x} {y} 1.65 0 0 0'
    for plugin in example.findall('plugin'):
        plugin=copy.deepcopy(plugin);plugin.find('robotNamespace').text=name;inc.append(plugin)
    plugin=E.SubElement(inc,'plugin',filename='ignition-gazebo-odometry-publisher-system',name='ignition::gazebo::systems::OdometryPublisher')
    for key,value in [('odom_frame','world'),('robot_base_frame','X3/base_link'),('odom_publish_frequency','10'),('odom_topic',f'/navis/{name.replace(chr(45),chr(95))}/odometry'),('dimensions','3')]:E.SubElement(plugin,key).text=value
usv=world.find("model[@name='USV-01']")
usv.find('plugin/odom_topic').text='/navis/USV_01/odometry'
old=world.find("model[@name='USV-02']")
if old is not None:world.remove(old)
usv2=copy.deepcopy(usv);usv2.set('name','USV-02');usv2.find('pose').text='0 5 .23 0 0 0'
for sensor in list(usv2.find('link').findall('sensor')):usv2.find('link').remove(sensor)
usv2.find('plugin/odom_topic').text='/navis/USV_02/odometry';world.append(usv2)
E.indent(t);t.write(p,encoding='utf-8',xml_declaration=True)
print('Configured four UAVs and two USVs with distinct odometry topics')
