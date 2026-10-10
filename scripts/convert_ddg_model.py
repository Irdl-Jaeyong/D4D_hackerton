#!/usr/bin/env python3
"""Convert the licensed NPS X3D static ship geometry to Gazebo OBJ/MTL.

Preserves source transforms/materials. Animation and non-surface helper lines
are omitted. Coordinates change from X3D Y-up to Gazebo Z-up.
"""
import math
import json
from pathlib import Path
import xml.etree.ElementTree as E
import numpy as np
ROOT=Path(__file__).resolve().parents[1]/'ros_ws/src/navis_sim/models/arleigh_burke'
def numbers(s):return [float(x) for x in s.replace(',',' ').split()]
def translation(a):
 m=np.eye(4);m[:3,3]=a;return m
def rotation(a):
 x=np.array(a[:3],float);angle=a[3]
 if np.linalg.norm(x)==0:return np.eye(4)
 x/=np.linalg.norm(x);c=math.cos(angle);s=math.sin(angle)
 cross=np.array([[0,-x[2],x[1]],[x[2],0,-x[0]],[-x[1],x[0],0]])
 m=np.eye(4);m[:3,:3]=c*np.eye(3)+(1-c)*np.outer(x,x)+s*cross;return m
def main():
 root=E.parse(ROOT/'source/ArleighBurkeHighDetail.x3d').getroot()
 defs={n.get('DEF'):n for n in root.iter() if n.get('DEF')}
 def resolved(n):return defs[n.get('USE')] if n is not None and n.get('USE') else n
 parts=[]
 def walk(node,m):
  node=resolved(node)
  if node.tag=='Transform':
   t=numbers(node.get('translation','0 0 0'));c=numbers(node.get('center','0 0 0'))
   r=rotation(numbers(node.get('rotation','0 0 1 0')))
   sr=rotation(numbers(node.get('scaleOrientation','0 0 1 0')))
   scale=np.diag([*numbers(node.get('scale','1 1 1')),1])
   m=m@translation(t)@translation(c)@r@sr@scale@sr.T@translation(-np.array(c))
  if node.tag=='Shape':
   geom=next((resolved(x) for x in node if x.tag in ('IndexedFaceSet','Cylinder','Box')),None)
   if geom is None:return
   app=resolved(node.find('Appearance'));mat=resolved(app.find('Material')) if app is not None else None
   color=numbers(mat.get('diffuseColor','.6 .6 .6')) if mat is not None else [.6]*3
   if geom.tag=='IndexedFaceSet':
    coord=resolved(geom.find('Coordinate'));vertices=np.array(numbers(coord.get('point'))).reshape(-1,3)
    faces=[];face=[]
    for i in map(int,geom.get('coordIndex').replace(',',' ').split()):
     if i==-1:
      if len(face)>=3:faces.append(face if geom.get('ccw','true')=='true' else list(reversed(face)))
      face=[]
     else:face.append(i)
    if len(face)>=3:faces.append(face)
   elif geom.tag=='Box':
    size=np.array(numbers(geom.get('size','2 2 2')))/2
    vertices=np.array([[-1,-1,-1],[1,-1,-1],[1,1,-1],[-1,1,-1],[-1,-1,1],[1,-1,1],[1,1,1],[-1,1,1]])*size
    faces=[[3,2,1,0],[4,5,6,7],[0,1,5,4],[1,2,6,5],[2,3,7,6],[3,0,4,7]]
   else:
    radius=float(geom.get('radius','1'));height=float(geom.get('height','2'));n=24
    vertices=np.array([(radius*math.cos(i*2*math.pi/n),y,radius*math.sin(i*2*math.pi/n)) for y in [-height/2,height/2] for i in range(n)])
    faces=[[i,(i+1)%n,(i+1)%n+n,i+n] for i in range(n)]
    faces += [list(range(n)),list(reversed(range(n,2*n)))]
   v=(m@np.column_stack([vertices,np.ones(len(vertices))]).T).T[:,:3]
   # right-handed rotation: X stays X, Y-up becomes Z-up.
   v=v[:,[0,2,1]];v[:,1]*=-1
   parts.append((v,faces,color,node.get('DEF',geom.get('DEF','part'))))
   return
  for child in node:walk(child,m)
 walk(defs['dad_DDG51'],np.eye(4))
 allv=np.concatenate([p[0] for p in parts]);lo=allv.min(axis=0);hi=allv.max(axis=0)
 print('Source bounds:',lo.tolist(),hi.tolist(),'dimensions:',(hi-lo).tolist())
 center=np.array([(lo[0]+hi[0])/2,(lo[1]+hi[1])/2,0])
 obj=['# NPS LT Patrick Sullivan: ArleighBurkeHighDetail.x3d converted to Z-up','mtllib arleigh_burke.mtl'];mtl=[];offset=0
 for k,(v,faces,color,name) in enumerate(parts):
  obj.extend([f'o part_{k}',f'usemtl material_{k}'])
  obj += ['v '+' '.join(f'{x:.6f}' for x in p-center) for p in v]
  for f in faces:
   for i in range(1,len(f)-1):obj.append('f '+' '.join(str(offset+j+1) for j in [f[0],f[i],f[i+1]]))
  offset+=len(v)
  mtl += [f'newmtl material_{k}','Ka '+' '.join(str(x*.6) for x in color),'Kd '+' '.join(map(str,color)),'Ks .08 .08 .08','Ns 12','d 1','']
 # Explicit per-part SDF materials avoid Gazebo overriding imported groups.
 manifest=[]
 for k,(v,faces,color,name) in enumerate(parts):
  rows=['# Derived from licensed NPS source, metre scale, Z-up']
  rows += ['v '+' '.join(f'{x:.6f}' for x in p-center) for p in v]
  triangles=[(f[0],f[j],f[j+1]) for f in faces for j in range(1,len(f)-1)]
  for a,b,c in triangles:
   normal=np.cross(v[b]-v[a],v[c]-v[a]);length=np.linalg.norm(normal)
   normal=normal/length if length>1e-12 else np.array([0.,0.,1.])
   rows.append('vn '+' '.join(f'{x:.7f}' for x in normal))
  for n,face in enumerate(triangles):rows.append('f '+' '.join(f'{i+1}//{n+1}' for i in face))
  filename=f'part_{k:02}.obj';(ROOT/'meshes'/filename).write_text('\n'.join(rows)+'\n')
  manifest.append({'mesh':filename,'color':color,'source_name':name})
 (ROOT/'meshes/parts.json').write_text(json.dumps(manifest,indent=2)+'\n')
 # COLLADA carries per-surface materials reliably through Gazebo's importer.
 dae=E.Element('COLLADA',xmlns='http://www.collada.org/2005/11/COLLADASchema',version='1.4.1')
 asset=E.SubElement(dae,'asset');E.SubElement(asset,'unit',name='meter',meter='1');E.SubElement(asset,'up_axis').text='Z_UP'
 effects=E.SubElement(dae,'library_effects');materials=E.SubElement(dae,'library_materials');geometries=E.SubElement(dae,'library_geometries')
 scenes=E.SubElement(dae,'library_visual_scenes');scene=E.SubElement(scenes,'visual_scene',id='ShipScene')
 for k,(v,faces,color,name) in enumerate(parts):
  effect=E.SubElement(effects,'effect',id=f'effect{k}');profile=E.SubElement(effect,'profile_COMMON');tech=E.SubElement(profile,'technique',sid='common');phong=E.SubElement(tech,'phong')
  for tag,rgba in [('ambient',[*(x*.5 for x in color),1]),('diffuse',[*color,1]),('specular',[.08,.08,.08,1])]:
   E.SubElement(E.SubElement(phong,tag),'color').text=' '.join(map(str,rgba))
  E.SubElement(E.SubElement(phong,'shininess'),'float').text='12'
  material=E.SubElement(materials,'material',id=f'material{k}');E.SubElement(material,'instance_effect',url=f'#effect{k}')
  geom=E.SubElement(geometries,'geometry',id=f'geometry{k}',name=name);mesh=E.SubElement(geom,'mesh')
  src=E.SubElement(mesh,'source',id=f'positions{k}');E.SubElement(src,'float_array',id=f'array{k}',count=str(len(v)*3)).text=' '.join(f'{x:.6f}' for x in (v-center).flatten())
  acc=E.SubElement(E.SubElement(src,'technique_common'),'accessor',source=f'#array{k}',count=str(len(v)),stride='3')
  for axis in ['X','Y','Z']:E.SubElement(acc,'param',name=axis,type='float')
  vertices=E.SubElement(mesh,'vertices',id=f'vertices{k}');E.SubElement(vertices,'input',semantic='POSITION',source=f'#positions{k}')
  tris=[]
  for f in faces:
   for j in range(1,len(f)-1):tris.extend([f[0],f[j],f[j+1]])
  t=E.SubElement(mesh,'triangles',count=str(len(tris)//3),material=f'surface{k}');E.SubElement(t,'input',semantic='VERTEX',source=f'#vertices{k}',offset='0');E.SubElement(t,'p').text=' '.join(map(str,tris))
  node=E.SubElement(scene,'node',id=f'node{k}');instance=E.SubElement(node,'instance_geometry',url=f'#geometry{k}')
  bind=E.SubElement(E.SubElement(instance,'bind_material'),'technique_common');E.SubElement(bind,'instance_material',symbol=f'surface{k}',target=f'#material{k}')
 E.SubElement(E.SubElement(dae,'scene'),'instance_visual_scene',url='#ShipScene')
 E.indent(dae);E.ElementTree(dae).write(ROOT/'meshes/arleigh_burke.dae',encoding='utf-8',xml_declaration=True)
 (ROOT/'meshes/arleigh_burke.obj').write_text('\n'.join(obj)+'\n')
 (ROOT/'meshes/arleigh_burke.mtl').write_text('\n'.join(mtl))
 print(f'Converted {len(parts)} surfaces, {offset} vertices')
if __name__=='__main__':main()
