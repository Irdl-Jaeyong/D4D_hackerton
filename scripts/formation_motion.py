"""Leader-relative formations and continuous, bounded-speed transitions."""
import math
CATALOG={'usv':{'circle':'원형 호위','v':'후방 V자','columns':'양측 종대','fan':'전방 부채꼴'},'uav':{'hemisphere':'반구','box':'직육면체','triangle':'삼각형','v':'V자','rings':'다층 원형'}}
def targets(group,mode,t=0):
    if group=='usv':
        if mode=='circle':return [(115*math.cos(i*math.pi/5),75*math.sin(i*math.pi/5),.7) for i in range(10)]
        if mode=='v':return [(-95-(i//2)*18,(-1 if i%2 else 1)*(25+(i//2)*15),.7) for i in range(10)]
        if mode=='columns':return [(80-(i//2)*40,(-1 if i%2 else 1)*65,.7) for i in range(10)]
        if mode=='fan':return [(125*math.cos(-1.2+i*2.4/9),100*math.sin(-1.2+i*2.4/9),.7) for i in range(10)]
    if mode=='box':return [(-80+40*(i%5),-60+40*((i//5)%4),60+50*(i//20)) for i in range(40)]
    if mode=='triangle':return [(85-row*23,(slot-(count-1)/2)*23,85) for row,count in enumerate([2,3,4,5,5,6,7,8]) for slot in range(count)]
    if mode=='v':return [(80-(i//2)*8,(-1 if i%2 else 1)*(10+(i//2)*4),85+(i//2)*1.2) for i in range(40)]
    if mode=='rings':return [(105*math.cos((i//5)*math.pi/4),105*math.sin((i//5)*math.pi/4),30+(i%5)*22) for i in range(40)]
    raise ValueError(mode)
def crosses_hull(p,goal):
    low,high=0.,1.
    for axis,bound in [(0,90),(1,32)]:
        delta=goal[axis]-p[axis]
        if abs(delta)<1e-9:
            if abs(p[axis])>bound:return False
        else:
            a,b=sorted(((-bound-p[axis])/delta,(bound-p[axis])/delta))
            low=max(low,a);high=min(high,b)
    return low<high and high>0 and low<1

class Transition:
    def __init__(self,points,speed,acceleration):
        self.points=[list(p) for p in points];self.velocity=[[0.,0.,0.] for p in points];self.speed=speed;self.acceleration=acceleration;self.assignment=None;self.sides=[]
    def select(self,goals):
        # Closest-pair assignment avoids making distant vehicles exchange slots.
        pairs=sorted((math.dist(p,g),i,j) for i,p in enumerate(self.points) for j,g in enumerate(goals));mapping={};used=set()
        for _,i,j in pairs:
            if i not in mapping and j not in used:mapping[i]=j;used.add(j)
        self.assignment=[mapping[i] for i in range(len(self.points))]
        self.sides=[-1 if p[1]<-.1 or abs(p[1])<=.1 and goals[self.assignment[i]][1]<0 else 1 for i,p in enumerate(self.points)]
    def step(self,goals,dt,marine=False):
        if self.assignment is None:self.select(goals)
        snapshot=[p[:] for p in self.points]
        for i,p in enumerate(snapshot):
            goal=goals[self.assignment[i]]
            if marine and crosses_hull(p,goal):
                side=self.sides[i]
                goal=((p[0] if abs(p[0])>100 else math.copysign(105,p[0] or 1)),side*45,goal[2]) if abs(p[1])<42 else (goal[0],side*45,goal[2])
            delta=[goal[k]-p[k] for k in range(3)];d=math.sqrt(sum(x*x for x in delta))
            wanted=[x*min(self.speed,.6*d)/max(d,1e-9) for x in delta]
            # Keep a clear corridor around the flagship footprint for USV targets.
            if marine and abs(p[0])<90 and abs(p[1])<30:
                wanted[1]+=(-1 if p[1]<0 else 1)*2
            radius=14 if marine else 7
            for j,q in enumerate(snapshot):
                if j==i:continue
                sep=math.dist(p,q)
                if .001<sep<radius:
                    for k in range(2 if marine else 3):wanted[k]+=(p[k]-q[k])/sep*(radius-sep)
            norm=math.sqrt(sum(x*x for x in wanted));wanted=[x*min(1,self.speed/max(norm,1e-9)) for x in wanted]
            change=[wanted[k]-self.velocity[i][k] for k in range(3)];norm=math.sqrt(sum(x*x for x in change));scale=min(1,self.acceleration*dt/max(norm,1e-9))
            for k in range(3):self.velocity[i][k]+=change[k]*scale;self.points[i][k]+=self.velocity[i][k]*dt
        return max(math.dist(p,goals[self.assignment[i]]) for i,p in enumerate(self.points))
