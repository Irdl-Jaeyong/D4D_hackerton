#!/usr/bin/env python3
"""Deterministic render meshes: metre-scale ocean grid and sparse foam wakes."""
from pathlib import Path
import math,random
ROOT=Path(__file__).resolve().parents[1]/'ros_ws/src/navis_sim/models/navis_ocean/meshes'
def save(name,v,uv,faces):
 rows=['# Original NAVIS visual mesh: metres, Z-up']
 rows += ['v '+' '.join(f'{x:.5f}' for x in p) for p in v]
 rows += ['vt '+' '.join(f'{x:.6f}' for x in p) for p in uv]
 rows += ['vn 0 0 1']
 rows += ['f '+' '.join(f'{i+1}/{i+1}/1' for i in f) for f in faces]
 (ROOT/name).write_text('\n'.join(rows)+'\n')
def build():
 n=300;size=2400;v=[];uv=[];f=[]
 for j in range(n+1):
  for i in range(n+1):v.append(((i/n-.5)*size,(j/n-.5)*size,0));uv.append((i/n,j/n))
 for j in range(n):
  for i in range(n):
   a=j*(n+1)+i;b=a+1;c=a+n+1;d=c+1;f.extend([(a,b,d),(a,d,c)])
 save('near_ocean.obj',v,uv,f)
 for name,length,beam,seed in [('ship_foam.obj',65,16,19),('usv_foam.obj',14,2,23)]:
  rng=random.Random(seed);v=[];uv=[];f=[]
  for side in [-1,0,1]:
   for k in range(100 if side==0 else 70):
    distance=rng.uniform(0,length);spread=beam*.25+distance*.17
    x=-distance;y=side*spread+rng.gauss(0,.5 if name.startswith('ship') else .1)
    radius=(.25 if name.startswith('ship') else .055)*(1-distance/length)+.035
    a=len(v)
    for j in range(8):
     theta=j*math.pi/4;v.append((x+math.cos(theta)*radius*3,y+math.sin(theta)*radius,0));uv.append((.5+.5*math.cos(theta),.5+.5*math.sin(theta)))
    for j in range(1,7):f.append((a,a+j,a+j+1))
  save(name,v,uv,f)
def deck_surfaces():
    root=ROOT.parents[1]/'arleigh_burke/meshes'
    lines=(root/'part_47.obj').read_text().splitlines()
    verts=[tuple(map(float,l.split()[1:])) for l in lines if l.startswith('v ')]
    normals=[tuple(map(float,l.split()[1:])) for l in lines if l.startswith('vn ')]
    groups={'flight_deck':[],'nonskid_deck':[]};side_faces=[]
    for line in lines:
        if not line.startswith('f '):continue
        face=line.split()[1:];n=int(face[0].split('//')[1])-1
        if normals[n][2]<.85:
            side_faces.append(line);continue
        points=[verts[int(x.split('//')[0])-1] for x in face]
        groups['flight_deck' if sum(p[0] for p in points)/3 < -53 else 'nonskid_deck'].append(points)
    (root/'part_47_sides.obj').write_text('\n'.join([l for l in lines if not l.startswith('f ')]+side_faces)+'\n')
    # Upper hull also has duplicate deck caps; remove them before texturing.
    upper=(root/'part_46.obj').read_text().splitlines()
    upper_normals=[tuple(map(float,l.split()[1:])) for l in upper if l.startswith('vn ')]
    sides=[l for l in upper if not l.startswith('f ') or upper_normals[int(l.split()[1].split('//')[1])-1][2]<.85]
    (root/'part_46_sides.obj').write_text('\n'.join(sides)+'\n')
    for name,faces in groups.items():
        out=['# Deck surface copied from licensed NPS source; original coordinates; source top faces removed from side mesh']
        for face in faces:
            for x,y,z in face:out.append(f'v {x} {y} {z}')
        for face in faces:
            for x,y,z in face:
                u,v=((x+77)/24,(y+9)/18) if name=='flight_deck' else (x/2,y/2)
                out.append(f'vt {u} {v}')
        out.append('vn 0 0 1')
        for i in range(len(faces)):out.append('f '+' '.join(f'{i*3+j+1}/{i*3+j+1}/1' for j in range(3)))
        (root/(name+'.obj')).write_text('\n'.join(out)+'\n')

if __name__=='__main__':
    build()
    deck_surfaces()
