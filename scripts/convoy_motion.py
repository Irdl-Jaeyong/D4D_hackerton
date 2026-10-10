#!/usr/bin/env python3
"""Gazebo convoy trajectory demo, driven by simulation time.

The Bernoulli figure-eight curve is independently implemented from the
mathematical pattern documented by ModalAI's VOXL flight example. It is
mapped to spherical coordinates to preserve a hemispherical formation.
All USVs are excluded from pose commands and uses a Gazebo force-based plugin.
The flagship and drones use scripted trajectories; no flight controller runs.
"""
import json
from collections import deque
import math
import signal
import time
import os
import urllib.request
from formation_motion import Transition,targets
from mission_execution import ObservationRun
from fault_motion import FaultReturn
from typed_fault_motion import FaultMotion
import subprocess
from pathlib import Path

FLEET = json.loads((Path(__file__).resolve().parents[1]/'config/fleet.json').read_text())
MOTION = FLEET['motion']
CAMERA = FLEET['camera']


def figure_eight(angle):
    """Normalized Bernoulli lemniscate and its analytic tangent."""
    s,c=math.sin(angle),math.cos(angle)
    d=1+s*s
    scale=2*math.sqrt(2)
    return (c/d, scale*c*s/d,
            -s*(3-s*s)/(d*d), scale*(1-3*s*s)/(d*d))


def vessel_pose(t, index=None):
    """Analytic smooth course with bounded speed and yaw rate."""
    forward=MOTION['ship_speed']*t
    if index is None:return forward,0,0
    rx,ry=MOTION['escort_radii'];omega=MOTION['escort_angular_speed']
    a=2*math.pi*index/FLEET['usvs']+omega*t
    return (forward+rx*math.cos(a),ry*math.sin(a),
            math.atan2(ry*omega*math.cos(a),MOTION['ship_speed']-rx*omega*math.sin(a)))


def hull_response(t,x,y,yaw,large=False):
    """Bounded visual sea response, not a buoyancy/force solver."""
    # Spatial phases make nearby vessels respond to the same travelling swell.
    a=.10*math.cos(.065*x+.048*y-1.14*t)
    b=.055*math.cos(.042*x-.038*y-.92*t)
    attenuation=.3 if large else 1
    heave=attenuation*(a+b)
    roll=attenuation*.035*math.sin(.065*x+.048*y-1.14*t-yaw)
    pitch=attenuation*.022*math.sin(.042*x-.038*y-.92*t+yaw)
    return heave,roll,pitch


def fleet_poses(t, camera=None):
    """Pure trajectory function, with continuous positions and headings."""
    camera=CAMERA if camera is None else camera
    forward=MOTION['ship_speed']*t
    result={}
    def add(name,x,y,z,yaw=0,pitch=0,roll=0):
        result[name]={'x':x,'y':y,'z':z,'yaw':yaw,'pitch':pitch,'roll':roll}
    for i in range(FLEET['ships']):
        add(f'SHIP-{i+1:02}',forward+i*90,0,2.4)
    # The level flagship frame carries the stabilized overhead sensors. Hull
    # visuals move separately so sea response cannot shake those sensors.
    h,r,p=hull_response(t,forward,0,0,True)
    add('SHIP-01_hull',forward,0,2.4+h,0,p,r)
    for i in range(FLEET['usvs']):
        x,y,yaw=vessel_pose(t,i)
        h,r,p=hull_response(t,x,y,yaw)
        add(f'USV-{i+1:02}',x,y,.7+h,yaw,p,r)
    # Five latitude rings cover the upper sphere. A small figure eight in
    # longitude / latitude remains on that sphere, including at the crossing.
    latitudes=MOTION['hemisphere_latitudes_deg']
    count=FLEET['uavs'];rings=len(latitudes);radius=MOTION['hemisphere_radius']
    step=2*math.pi/MOTION['figure_eight_period']
    for i in range(count):
        ring=i%rings;slot=i//rings
        ring_count=(count-1-ring)//rings+1
        direction=1 if ring%2==0 else -1
        angle=step*t+2*math.pi*slot/ring_count+.35*ring
        ex,ey,tx,ty=figure_eight(angle)
        latitude=math.radians(latitudes[ring])+MOTION['figure_eight_latitude_amplitude']*ey
        longitude=(2*math.pi*slot/ring_count
                   +direction*MOTION['hemisphere_rotation_rate']*t
                   +MOTION['figure_eight_longitude_amplitude']*ex)
        dlat=MOTION['figure_eight_latitude_amplitude']*ty*step
        dlon=(direction*MOTION['hemisphere_rotation_rate']
              +MOTION['figure_eight_longitude_amplitude']*tx*step)
        cl,sl=math.cos(latitude),math.sin(latitude)
        cp,sp=math.cos(longitude),math.sin(longitude)
        x=forward+radius*cl*cp;y=radius*cl*sp
        z=MOTION['hemisphere_center_height']+radius*sl
        dx=MOTION['ship_speed']+radius*(-sl*dlat*cp-cl*sp*dlon)
        dy=radius*(-sl*dlat*sp+cl*cp*dlon)
        add(f'UAV-{i+1:02}',x,y,z,math.atan2(dy,dx))
    # Each foam patch stays at an earlier stern location, not at the current
    # vessel heading. Sampling history makes curved turns leave curved wakes.
    for index in [None,*range(FLEET['usvs'])]:
        name='SHIP-01' if index is None else f'USV-{index+1:02}'
        for segment in range(20):
            age=(segment+.5)*(1.5 if index is None else .9)
            x,y,yaw=vessel_pose(max(0,t-age),index)
            aft=77 if index is None else 2.5
            add(f'wake_{name}_{segment:02}',x-aft*math.cos(yaw),y-aft*math.sin(yaw),-.04 if t>=age else -2,yaw)
    # Civilian traffic crosses ahead of the flagship's bow, outside its hull.
    # It enters, passes, then leaves the escort area in a 180-second demo cycle.
    crossing=t%180
    add('CIV-01',forward+105,120-3*crossing,.7,math.atan2(-3,MOTION['ship_speed']))
    ox,oy,oz=camera['offset']
    add('fleet_observer',forward+ox,oy,oz,camera['yaw'],camera['pitch'])
    # Recenter the purely visual, flat ocean so the demo never leaves it.
    add('ocean',forward,0,-.25)
    return result


def pose_message(name,p):
    cy,sy=math.cos(p['yaw']/2),math.sin(p['yaw']/2)
    cp,sp=math.cos(p['pitch']/2),math.sin(p['pitch']/2)
    cr,sr=math.cos(p.get('roll',0)/2),math.sin(p.get('roll',0)/2)
    return f'name:"{name}" position {{x:{p["x"]:.5f} y:{p["y"]:.5f} z:{p["z"]:.5f}}} orientation {{w:{cr*cp*cy+sr*sp*sy:.7f} x:{sr*cp*cy-cr*sp*sy:.7f} y:{cr*sp*cy+sr*cp*sy:.7f} z:{cr*cp*sy-sr*sp*cy:.7f}}}'



def poses(t, camera=None, history=None, formations=None, faults=None, inspection=None, typed_motion=None, fault_modes=None):
    fleet=fleet_poses(t,camera)
    fleet.pop('CIV-01',None)
    if formations:
        for group,points in formations.items():
            for i,p in enumerate(points):
                name=f'UAV-{i+1:02}' if group=='uav' else f'USV_target_{i+1:02}'
                old=fleet.get(name,{'yaw':0,'pitch':0,'roll':0})
                fleet[name]={**old,'x':MOTION['ship_speed']*t+p[0],'y':p[1],'z':p[2]}
    for name,run in (faults or {}).items():
        if name.startswith('UAV'):
            fleet[name].update(x=MOTION['ship_speed']*t+run.point[0],y=run.point[1],z=run.point[2],roll=run.roll,pitch=run.pitch)
            if run.phase=='charging':
                # Parked aircraft follows the deck, including the hull sea response.
                h,r,p=hull_response(t,MOTION['ship_speed']*t,0,0,True)
                x,y,z=run.point;z-=2.4
                sr,cr=math.sin(r),math.cos(r);sp,cp=math.sin(p),math.cos(p)
                fleet[name].update(x=MOTION['ship_speed']*t+cp*x+sp*(sr*y+cr*z),y=cr*y-sr*z,z=2.4+h-sp*x+cp*(sr*y+cr*z),roll=r,pitch=p)
        else:
            marker=fleet.get('USV_target_'+name.split('-')[1])
            if marker:marker.update(x=MOTION['ship_speed']*t-65,y=30 if int(name[-2:])%2 else -30,pitch=.8)
    for name,samples in (history or {}).items():
        for segment in range(20):
            stamp=t-(segment+.5)*.9
            previous=samples[0];following=samples[-1]
            for sample in samples:
                if sample[0]<=stamp:previous=sample
                if sample[0]>=stamp:following=sample;break
            fraction=max(0,min(1,(stamp-previous[0])/max(1e-9,following[0]-previous[0])))
            x=previous[1]+fraction*(following[1]-previous[1])
            y=previous[2]+fraction*(following[2]-previous[2])
            delta=math.atan2(math.sin(following[3]-previous[3]),math.cos(following[3]-previous[3]))
            yaw=previous[3]+fraction*delta
            wake=fleet[f'wake_{name}_{segment:02}']
            wake.update(x=x-2.5*math.cos(yaw),y=y-2.5*math.sin(yaw),yaw=yaw,z=-.04 if stamp>=samples[0][0] else -2)
    if typed_motion:
        fleet=typed_motion.apply(fleet,t,{id:kind for id,kind in (fault_modes or {}).items() if kind in ('propulsion','communication')})
    if inspection:
        name=inspection['id'];target=fleet.get(name)
        if name.startswith('USV') and history and history.get(name):
            point=history[name][-1];target={'x':point[1],'y':point[2],'z':.7}
        if target:
            scale=15 if name.startswith('SHIP') else 1.5 if name.startswith('USV') else 1
            dx,dy,dz=-6*scale,-8*scale,6*scale
            fleet['inspection_camera']={'x':target['x']+dx,'y':target['y']+dy,'z':target['z']+dz,'yaw':math.atan2(-dy,-dx),'pitch':math.atan2(dz,math.hypot(dx,dy)),'roll':0}
    return ' '.join('pose {'+pose_message(name,p)+'}' for name,p in fleet.items() if name!='fleet_observer' and not name.startswith('USV-'))


def main():
    import rclpy
    from rclpy.node import Node
    from rclpy.executors import ExternalShutdownException
    from rclpy.qos import qos_profile_sensor_data
    from rosgraph_msgs.msg import Clock
    from nav_msgs.msg import Odometry
    class Convoy(Node):
        def __init__(self):
            super().__init__('navis_convoy')
            self.origin=None;self.elapsed=None;self.last_sent=None;self.failures=0
            self.clock_stamp=None
            self.selection={'usv':'circle','uav':'hemisphere','revision':0}
            initial=fleet_poses(0)
            self.planners={group:Transition([(initial[f'{kind}-{i+1:02}']['x'],initial[f'{kind}-{i+1:02}']['y'],initial[f'{kind}-{i+1:02}']['z']) for i in range(FLEET[key])],speed,accel) for group,kind,key,speed,accel in [('usv','USV','usvs',3,1),('uav','UAV','uavs',10,4)]}
            self.checked=0;self.planner_time=None;self.initial_error={};self.formation_status={}
            self.physical_history={}
            self.uav_observations={};self.mission_run=None;self.execution_report=None;self.fault_runs={};self.fault_report={};self.typed_motion=FaultMotion()
            for i in range(FLEET['uavs']):
                name=f'UAV-{i+1:02}'
                self.create_subscription(Odometry,f'/navis/{name.replace("-","_")}/odometry',lambda msg,name=name:self.uav_odom(name,msg),qos_profile_sensor_data)
            self.odom_subscriptions=[]
            for i in range(FLEET['usvs']):
                name=f'USV-{i+1:02}'
                self.odom_subscriptions.append(self.create_subscription(Odometry,f'/navis/{name.replace("-","_")}/odometry',lambda msg,name=name:self.physical_odom(name,msg),qos_profile_sensor_data))
            self.clock_subscription=self.create_subscription(Clock,'/world/navis_prep/clock',self.clock,qos_profile_sensor_data)
            self.timer=self.create_timer(.1,self.update)
            self.get_logger().info('Simulation-time convoy: straight leader, assigned escort stations, UAV leader-relative station keeping')
        def uav_odom(self,name,msg):
            if self.origin is None:return
            stamp=msg.header.stamp.sec+msg.header.stamp.nanosec/1e9-self.origin
            p=msg.pose.pose.position
            if name not in self.uav_observations or stamp>self.uav_observations[name][0]:self.uav_observations[name]=(stamp,(p.x,p.y,p.z))
        def physical_odom(self,name,msg):
            if self.origin is None:return
            t=msg.header.stamp.sec+msg.header.stamp.nanosec/1e9-self.origin
            p=msg.pose.pose.position;q=msg.pose.pose.orientation
            yaw=math.atan2(2*(q.w*q.z+q.x*q.y),1-2*(q.y*q.y+q.z*q.z))
            history=self.physical_history.setdefault(name,deque(maxlen=400))
            if not history or t>history[-1][0]:history.append((t,p.x,p.y,yaw))
        def clock(self,msg):
            stamp=msg.clock.sec+msg.clock.nanosec/1e9
            # A delayed clock packet must never move the convoy backwards.
            if self.clock_stamp is not None and stamp<=self.clock_stamp:return
            self.clock_stamp=stamp
            if self.origin is None:self.origin=stamp
            self.elapsed=stamp-self.origin
        def update(self):
            if self.elapsed is None or self.elapsed==self.last_sent:return
            t=self.elapsed
            now=time.monotonic()
            if now-self.checked>.5:
                self.checked=now
                try:
                    with urllib.request.urlopen('http://127.0.0.1:8000/api/formations',timeout=.2) as response:selection=json.load(response)
                    for group in ('usv','uav'):
                        if selection[group]!=self.selection[group]:
                            self.planners[group].assignment=None;self.initial_error.pop(group,None)
                    self.selection=selection
                except (OSError,ValueError,KeyError):pass
            dt=min(.25,max(0,t-(self.planner_time if self.planner_time is not None else t)))
            self.planner_time=t
            reference=fleet_poses(t);points={}
            for group,planner in self.planners.items():
                mode=self.selection[group]
                if group=='uav' and mode=='hemisphere':
                    goals=[(reference[f'UAV-{i+1:02}']['x']-MOTION['ship_speed']*t,reference[f'UAV-{i+1:02}']['y'],reference[f'UAV-{i+1:02}']['z']) for i in range(FLEET['uavs'])]
                else:goals=targets(group,mode,t)
                if group=='uav':
                    if planner.assignment is None:planner.select(goals)
                    homes={f'UAV-{i+1:02}':goals[planner.assignment[i]] for i in range(FLEET['uavs'])}
                    requested=self.selection.get('mission')
                    if requested and requested.get('approved') and (self.mission_run is None or self.mission_run.id!=requested['id'] or self.mission_run.approved_at!=requested['approved'].get('approved_at')):
                        self.mission_run=ObservationRun(requested,t,MOTION['ship_speed']*t)
                    if self.mission_run:
                        cancel=not requested or requested['id']!=self.mission_run.id or requested.get('cancel_requested',False)
                        availability=self.selection.get('availability',{})
                        overrides=self.mission_run.step(t,MOTION['ship_speed']*t,homes,self.uav_observations,availability,cancel,target_world=requested.get('target_world_current') if requested else None)
                        for id,point in overrides.items():goals[planner.assignment[int(id.split('-')[1])-1]]=point
                        self.execution_report=self.mission_run.report(t,self.uav_observations,availability)
                error=planner.step(goals,dt,marine=group=='usv');points[group]=planner.points
                self.initial_error[group]=max(self.initial_error.get(group,0),error,1)
                # Dynamic patrols retain a small steady tracking error.
                if group=='usv':
                    for i in range(FLEET['usvs']):
                        history=self.physical_history.get(f'USV-{i+1:02}')
                        if history:
                            goal=goals[planner.assignment[i]]
                            error=max(error,math.hypot(history[-1][1]-MOTION['ship_speed']*t-goal[0],history[-1][2]-goal[1]))
                tolerance=10 if mode=='hemisphere' else 8 if mode=='circle' else 3
                self.formation_status[group]={'mode':mode,'moving':error>tolerance,'remaining_m':round(error,1),'progress':round(max(0,min(100,100*(1-error/self.initial_error[group]))))}
            modes=self.selection.get('fault_modes',{})
            all_faults=set(self.selection.get('faults',[]))
            active={id for id in all_faults if modes.get(id,'payload')=='payload'}
            for id in list(self.fault_runs):
                if id not in active:
                    run=self.fault_runs.pop(id)
                    if id.startswith('UAV'):
                        i=int(id[-2:])-1;self.planners['uav'].points[i]=list(run.point);self.planners['uav'].velocity[i]=[0.,0.,0.]
            self.fault_report={}
            for id in active:
                if id.startswith('UAV'):
                    i=int(id[-2:])-1
                    if id not in self.fault_runs:
                        self.fault_runs[id]=FaultReturn(i+1,self.planners['uav'].points[i],t)
                        if self.selection.get('fault_states',{}).get(id,{}).get('phase')=='charging':
                            self.fault_runs[id].point=list(self.fault_runs[id].target);self.fault_runs[id].started=t-5
                    run=self.fault_runs[id];run.step(t,dt)
                    self.fault_report[id]={'phase':run.phase,'sim_time':t,'deck_slot':run.target}
                else:
                    self.fault_runs[id]=None
                    history=self.physical_history.get(id)
                    near=history and math.hypot(history[-1][1]-MOTION['ship_speed']*t+65,abs(history[-1][2])-30)<10
                    self.fault_report[id]={'phase':'moored' if near else 'returning','sim_time':t}
            for id in all_faults-active:
                kind=modes.get(id);pose=self.typed_motion.last.get(id,{})
                phase=('ditched' if pose.get('z',10)<=.6 else 'emergency_descent') if kind=='propulsion' and id.startswith('UAV') else 'drifting' if id.startswith('USV') else 'failsafe_return'
                self.fault_report[id]={'phase':phase,'sim_time':t,'fault_type':kind}
            if now-self.checked<.05:
                try:
                    data=json.dumps(self.formation_status).encode()
                    req=urllib.request.Request('http://127.0.0.1:8000/api/internal/formations',data=data,headers={'Content-Type':'application/json','X-Bridge-Token':os.environ.get('NAVIS_BRIDGE_TOKEN','')})
                    with urllib.request.urlopen(req,timeout=.2) as response:response.read()
                    req=urllib.request.Request('http://127.0.0.1:8000/api/internal/faults',data=json.dumps({'tasks':self.fault_report}).encode(),headers={'Content-Type':'application/json','X-Bridge-Token':os.environ.get('NAVIS_BRIDGE_TOKEN','')})
                    with urllib.request.urlopen(req,timeout=.2) as response:response.read()
                    if self.execution_report:
                        req=urllib.request.Request('http://127.0.0.1:8000/api/internal/execution',data=json.dumps(self.execution_report).encode(),headers={'Content-Type':'application/json','X-Bridge-Token':os.environ.get('NAVIS_BRIDGE_TOKEN','')})
                        with urllib.request.urlopen(req,timeout=.2) as response:response.read()
                except (OSError,ValueError):pass
            try:
                response=subprocess.run(['ign','service','-s','/world/navis_prep/set_pose_vector','--reqtype','ignition.msgs.Pose_V','--reptype','ignition.msgs.Boolean','--timeout','1200','--req',poses(t,history=self.physical_history,formations=points,faults=self.fault_runs,inspection={'id':self.selection.get('inspection_vehicle','UAV-01')},typed_motion=self.typed_motion,fault_modes=modes)],capture_output=True,text=True,timeout=1.5)
                if response.returncode or 'true' not in response.stdout:
                    self.failures+=1
                    if self.failures%10==1:self.get_logger().warning('Pose update failed: '+response.stderr[:160])
                else:self.failures=0;self.last_sent=t
            except subprocess.TimeoutExpired:self.get_logger().warning('Pose update timed out')
    rclpy.init();node=Convoy()
    signal.signal(signal.SIGTERM,lambda *_:rclpy.try_shutdown())
    try:rclpy.spin(node)
    except (KeyboardInterrupt,ExternalShutdownException):pass
    finally:node.destroy_node();rclpy.try_shutdown()

if __name__=='__main__':main()
