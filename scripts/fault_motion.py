"""Controlled fault/return/charging demonstration, not a flight safety model."""
import math

def deck_slot(number):
    return [-74+2.7*((number-1)%8),-6+3*((number-1)//8),3.45]

class FaultReturn:
    def __init__(self,number,point,t):
        self.point=list(point);self.target=deck_slot(number);self.started=t
        self.phase='unstable';self.roll=0.;self.pitch=0.;self.velocity=[0.,0.,0.]
    def step(self,t,dt):
        age=t-self.started
        self.roll=.32*math.sin(age*4) if age<5 else 0.
        self.pitch=.16*math.sin(age*3) if age<5 else 0.
        if age<5:
            self.phase='unstable';return self.point
        horizontal=math.hypot(self.target[0]-self.point[0],self.target[1]-self.point[1])
        self.phase='returning' if horizontal>.25 else 'landing'
        goal=[self.target[0],self.target[1],max(18,self.point[2])] if horizontal>.25 else self.target
        for axis in range(3):
            error=goal[axis]-self.point[axis];limit=(4 if axis<2 else 2)*dt
            wanted=max(-limit/max(dt,1e-9),min(limit/max(dt,1e-9),error*.6))
            self.velocity[axis]+=max(-1.5*dt,min(1.5*dt,wanted-self.velocity[axis]))
            self.point[axis]+=self.velocity[axis]*dt
        if math.dist(self.point,self.target)<.1:
            self.point=list(self.target);self.phase='charging';self.velocity=[0.,0.,0.]
        return self.point
