"""World-fixed demonstration hover and bounded-speed recovery for scripted UAVs."""
import math
class FaultMotion:
    def __init__(self):self.last={};self.held=set();self.recovering=set();self.time=None;self.started={}
    def apply(self,fleet,t,faults):
        dt=max(0,min(.25,t-self.time)) if self.time is not None else 0
        if self.time is not None and t<self.time:self.last.clear();self.held.clear();self.recovering.clear()
        self.time=t;result={name:dict(p) for name,p in fleet.items()}
        for name,goal in fleet.items():
            if not name.startswith('UAV-'):continue
            old=self.last.get(name,goal)
            if name in faults:
                kind=faults[name] if isinstance(faults,dict) else 'legacy_hold'
                if name not in self.held:self.started[name]=t
                result[name]=dict(old);self.held.add(name);self.recovering.discard(name)
                if kind=='propulsion':result[name]['z']=max(.6,old['z']-3*dt)
                elif kind in ('payload','communication') and (kind=='payload' or t-self.started.get(name,t)>=2):
                    ship=fleet.get('SHIP-01',{});destination={'x':ship.get('x',0)-110,'y':60 if old['y']>=0 else -60,'z':max(35,old['z'])}
                    distance=math.sqrt(sum((destination[k]-old[k])**2 for k in ('x','y','z')))
                    fraction=min(1,8*dt/max(distance,1e-9))
                    for k in ('x','y','z'):result[name][k]=old[k]+(destination[k]-old[k])*fraction
            else:
                if name in self.held:self.held.remove(name);self.recovering.add(name)
                if name in self.recovering:
                    distance=math.sqrt(sum((goal[k]-old[k])**2 for k in ('x','y','z')))
                    fraction=min(1,10*dt/max(distance,1e-9))
                    result[name]={**goal,**{k:old[k]+(goal[k]-old[k])*fraction for k in ('x','y','z')}}
                    if fraction>=1:self.recovering.discard(name)
            self.last[name]=dict(result[name])
        return result
