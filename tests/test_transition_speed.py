import math,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from formation_motion import Transition,targets
class TransitionSpeed(unittest.TestCase):
    def test_five_times_speed_preserves_virtual_path(self):
        for group,start,end,speed,acceleration in [('uav','box','triangle',10,4),('usv','circle','columns',3,1)]:
            normal=Transition(targets(group,start),speed,acceleration)
            fast=Transition(targets(group,start),speed,acceleration,time_scale=5)
            goals=targets(group,end)
            for _ in range(300):
                normal.step(goals,.05,marine=group=='usv');fast.step(goals,.01,marine=group=='usv')
            for a,b in zip(normal.points,fast.points):self.assertLess(math.dist(a,b),1e-8)
    def test_invalid_scale_rejected(self):
        for value in [0,-1,float('nan'),float('inf')]:
            with self.assertRaises(ValueError):Transition([(0,0,0)],10,4,time_scale=value)
