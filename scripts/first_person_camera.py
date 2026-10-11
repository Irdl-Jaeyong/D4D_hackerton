"""Body-mounted forward camera, using the vehicle's full measured/scripted pose."""
import json,math
from pathlib import Path
MOUNTS=json.loads((Path(__file__).resolve().parents[1]/'config/fleet.json').read_text())['first_person_camera']
def mounted_camera(name,pose):
    mount=MOUNTS[name.split('-')[0]];offset=mount['offset']
    roll,pitch,yaw=(pose.get(k,0) for k in ('roll','pitch','yaw'))
    cr,sr=math.cos(roll),math.sin(roll);cp,sp=math.cos(pitch),math.sin(pitch);cy,sy=math.cos(yaw),math.sin(yaw)
    rotation=[[cy*cp,cy*sp*sr-sy*cr,cy*sp*cr+sy*sr],[sy*cp,sy*sp*sr+cy*cr,sy*sp*cr-cy*sr],[-sp,cp*sr,cp*cr]]
    point={k:pose[k]+sum(rotation[i][j]*offset[j] for j in range(3)) for i,k in enumerate(('x','y','z'))}
    a=mount['pitch'];c,s=math.cos(a),math.sin(a)
    view=[[c*r[0]-s*r[2],r[1],s*r[0]+c*r[2]] for r in rotation]
    point.update(yaw=math.atan2(view[1][0],view[0][0]),pitch=math.atan2(-view[2][0],math.hypot(view[0][0],view[1][0])),roll=math.atan2(view[2][1],view[2][2]))
    return point
