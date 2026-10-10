"""Observation/return state machine driven by measured UAV and USV odometry."""
import math
class ObservationRun:
    def __init__(self,mission,t,leader_x):
        self.id=mission['id'];self.approved_at=mission['approved'].get('approved_at');self.started=t;self.cancelled=False
        offset=mission['card']['offset'];target=mission.get('target_world',[leader_x+offset[0],offset[1]]);self.tasks={}
        for task in mission['approved']['tasks']:
            name=task['vehicle'];marine=name.startswith('USV-')
            if not marine and not name.startswith('UAV-'):continue
            offset=task.get('target_offset',[0,25 if target[1]>=0 else -25] if marine else [0,0])
            altitude=.7 if marine else 60+12*sum(id.startswith('UAV-') for id in self.tasks)
            self.tasks[name]={'stage':'outbound','target':(target[0]+offset[0],target[1]+offset[1],altitude),'offset':offset,'arrival_m':8 if marine else 4,
                                       'dwell_started':None,'distance_m':0.,'last_position':None,'completed_at':None}
    def step(self,t,leader_x,homes,observations,available,cancel=False,target_world=None):
        self.cancelled=self.cancelled or cancel;overrides={}
        for id,task in self.tasks.items():
            if task['stage']=='completed':continue
            obs=observations.get(id);fresh=obs is not None and 0<=t-obs[0]<2
            p=obs[1] if fresh else None
            if p is not None:
                if task['last_position'] is not None:task['distance_m']+=math.dist(p,task['last_position'])
                task['last_position']=p
            if task['stage']=='completed':continue
            if self.cancelled and task['stage']!='returning':task['stage']='returning'
            if not fresh or not available.get(id,False):
                # Keep current controller goal, but never claim observation/success.
                if task['stage']=='observing':task['dwell_started']=None
                continue
            if target_world is not None:task['target']=(target_world[0]+task['offset'][0],target_world[1]+task['offset'][1],task['target'][2])
            target=task['target']
            if task['stage']=='outbound' and math.dist(p,target)<task['arrival_m']:
                task['stage']='observing';task['dwell_started']=t
            if task['stage']=='observing':
                if math.dist(p,target)>=task['arrival_m']:task['stage']='outbound';task['dwell_started']=None
                else:
                    if task['dwell_started'] is None:task['dwell_started']=t
                    if t-task['dwell_started']>=5:task['stage']='returning'
            if task['stage']=='returning':
                home=homes[id];world_home=(leader_x+home[0],home[1],home[2])
                if math.dist(p,world_home)<task['arrival_m']:
                    task['stage']='completed';task['completed_at']=t
                else:overrides[id]=home
            else:overrides[id]=(target[0]-leader_x,target[1],target[2])
        return overrides
    def report(self,t,observations,available):
        tasks={}
        for id,task in self.tasks.items():
            fresh=id in observations and 0<=t-observations[id][0]<2
            tasks[id]={'stage':task['stage'],'blocked':not fresh or not available.get(id,False),
                       'distance_m':round(task['distance_m'],1),'elapsed_seconds':round((task['completed_at'] or t)-self.started,1),
                       'target_world':list(task['target'])}
        complete=bool(tasks) and all(task['stage']=='completed' for task in tasks.values())
        return {'mission_id':self.id,'sim_time':t,'elapsed_seconds':round(t-self.started,1),'tasks':tasks,
                'status':'cancelled' if complete and self.cancelled else 'completed' if complete else 'running','cancelled':self.cancelled}
