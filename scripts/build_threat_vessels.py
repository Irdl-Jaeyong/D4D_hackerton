"""Original metre-scale patrol/RHIB visual meshes; generated locally without external assets."""
from pathlib import Path
import math
ROOT=Path(__file__).resolve().parents[1]/'ros_ws/src/navis_sim/models/defense_contact/meshes'
def save(name,vertices,faces):
    lines=['# Original NAVIS contact vessel mesh; metres, +X bow, Z up']
    lines += ['v %.5f %.5f %.5f'%p for p in vertices]
    lines += ['f '+' '.join(str(i+1) for i in f) for f in faces]
    (ROOT/(name+'.obj')).write_text('\n'.join(lines)+'\n')
def build():
    ROOT.mkdir(parents=True,exist_ok=True)
    stations=[(-6,1.25),(-5,1.6),(-2,1.7),(1,1.65),(3.5,1.3),(5,.65),(6,.035)]
    v=[];faces=[]
    for x,w in stations:
        v.extend([(x,-w,.8),(x,-w*.95,.2),(x,-w*.55,-.35),(x,0,-.55),(x,w*.55,-.35),(x,w*.95,.2),(x,w,.8)])
    for i in range(len(stations)-1):
        for j in range(6):a=i*7+j;b=a+7;faces.extend([(a,b,b+1),(a,b+1,a+1)])
    faces += [(0,1,2,3,4,5,6),(42,43,44,45,46,47,48)];save('hull',v,faces)
    v=[(x,side*w,.8) for x,w in stations for side in [-1,1]];faces=[]
    for i in range(len(stations)-1):a=i*2;faces.extend([(a,a+2,a+3),(a,a+3,a+1)])
    save('deck',v,faces)
    v=[];faces=[]
    for side in [-1,1]:
        base=len(v)
        for x,w in stations:
            for j in range(16):a=j*math.pi/8;v.append((x,side*w+.27*math.cos(a),.8+.27*math.sin(a)))
        for i in range(len(stations)-1):
            for j in range(16):a=base+i*16+j;b=base+i*16+(j+1)%16;faces.extend([(a,a+16,b+16),(a,b+16,b)])
    save('collar',v,faces)
    # Angled windscreen console and lightweight bridge canopy.
    v=[(-2,-.95,.9),(-2,.95,.9),(1.6,-.85,.9),(1.6,.85,.9),(-1.7,-.78,2.6),(-1.7,.78,2.6),(.85,-.68,2.35),(.85,.68,2.35)]
    save('cabin',v,[(0,2,6,4),(1,5,7,3),(0,4,5,1),(4,6,7,5)])
    save('glass',v,[(2,3,7,6)])
    v=[(-1.85,-.92,2.65),(-1.85,.92,2.65),(1.0,-.88,2.42),(1.0,.88,2.42)];save('canopy',v,[(0,2,3,1)])
if __name__=='__main__':build()
