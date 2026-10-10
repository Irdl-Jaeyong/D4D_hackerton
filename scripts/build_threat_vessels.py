"""Original metre-scale patrol/RHIB visual meshes; generated locally without external assets."""
from pathlib import Path
import math
ROOT=Path(__file__).resolve().parents[1]/'ros_ws/src/navis_sim/models/defense_contact/meshes'
COLORS={'hull':(.24,.28,.3),'deck':(.32,.35,.35),'collar':(.045,.052,.055),'cabin':(.57,.61,.6),'glass':(.055,.13,.17),'canopy':(.43,.47,.48),'airframe':(.18,.22,.25)}
def save(name,vertices,faces):
    # Explicit OBJ normals and materials prevent unlit white fallback meshes.
    triangles=[(f[0],f[i],f[i+1]) for f in faces for i in range(1,len(f)-1)]
    normals=[[0.,0.,0.] for _ in vertices]
    for face in triangles:
        a,b,c=[vertices[i] for i in face];u=[b[i]-a[i] for i in range(3)];v=[c[i]-a[i] for i in range(3)]
        n=(u[1]*v[2]-u[2]*v[1],u[2]*v[0]-u[0]*v[2],u[0]*v[1]-u[1]*v[0])
        for index in face:
            for j in range(3):normals[index][j]+=n[j]
    normals=[tuple(x/max(math.sqrt(sum(y*y for y in n)),1e-9) for x in n) for n in normals]
    color=COLORS[name];ks=.65 if name=='glass' else .12
    (ROOT/(name+'.mtl')).write_text('newmtl vessel_'+name+'\nKd %s %s %s\nKa %s %s %s\nKs %s %s %s\nNs 80\nillum 2\n'%(*color,*color,ks,ks,ks))
    lines=['# Original NAVIS contact vessel mesh; metres, +X bow, Z up','mtllib '+name+'.mtl']
    lines += ['v %.5f %.5f %.5f'%p for p in vertices]
    lines += ['vn %.6f %.6f %.6f'%p for p in normals]
    lines += ['usemtl vessel_'+name]
    lines += ['f '+' '.join(f'{i+1}//{i+1}' for i in f) for f in triangles]
    (ROOT/(name+'.obj')).write_text('\n'.join(lines)+'\n')
def build():
    ROOT.mkdir(parents=True,exist_ok=True)
    stations=[(-6,1.25),(-5,1.6),(-2,1.7),(1,1.65),(3.5,1.3),(5,.65),(6,.035)]
    v=[];faces=[]
    for x,w in stations:
        v.extend([(x,-w,.8),(x,-w*.95,.2),(x,-w*.55,-.35),(x,0,-.55),(x,w*.55,-.35),(x,w*.95,.2),(x,w,.8)])
    for i in range(len(stations)-1):
        for j in range(6):a=i*7+j;b=a+7;faces.extend([(a,b+1,b),(a,a+1,b+1)])
    faces += [(6,5,4,3,2,1,0),(42,43,44,45,46,47,48)];save('hull',v,faces)
    v=[(x,side*w,.8) for x,w in stations for side in [-1,1]];faces=[]
    for i in range(len(stations)-1):a=i*2;faces.extend([(a,a+2,a+3),(a,a+3,a+1)])
    save('deck',v,faces)
    v=[];faces=[]
    for side in [-1,1]:
        base=len(v)
        for x,w in stations:
            for j in range(16):a=j*math.pi/8;v.append((x,side*w+.27*math.cos(a),.8+.27*math.sin(a)))
        for i in range(len(stations)-1):
            for j in range(16):a=base+i*16+j;b=base+i*16+(j+1)%16;faces.extend([(a,b+16,a+16),(a,b,b+16)])
    save('collar',v,faces)
    # Angled windscreen console and lightweight bridge canopy.
    v=[(-2,-.95,.9),(-2,.95,.9),(1.6,-.85,.9),(1.6,.85,.9),(-1.7,-.78,2.6),(-1.7,.78,2.6),(.85,-.68,2.35),(.85,.68,2.35)]
    save('cabin',v,[(0,2,6,4),(1,5,7,3),(0,4,5,1),(4,6,7,5)])
    save('glass',v,[(2,3,7,6)])
    v=[(-1.85,-.92,2.65),(-1.85,.92,2.65),(1.0,-.88,2.42),(1.0,.88,2.42)];save('canopy',v,[(0,2,3,1)])
    # Original tapered fixed-wing shell, 5 m wingspan, no armament.
    v=[(.6,-.45,.08),(-.45,-2.5,.02),(-.9,-2.5,.02),(-.6,-.45,.08),(.6,.45,.08),(-.45,2.5,.02),(-.9,2.5,.02),(-.6,.45,.08)]
    v += [(x,y,z-.13) for x,y,z in list(v)]
    save('airframe',v,[(0,3,2,1),(4,5,6,7),(8,9,10,11),(12,15,14,13),(0,1,9,8),(1,2,10,9),(2,3,11,10),(4,12,13,5),(5,13,14,6),(6,14,15,7)])
if __name__=='__main__':build()
