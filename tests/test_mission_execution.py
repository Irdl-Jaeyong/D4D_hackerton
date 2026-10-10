import unittest,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from mission_execution import ObservationRun
class Observation(unittest.TestCase):
    def run_fixture(self):
        return ObservationRun({'id':1,'card':{'offset':[100,50]},'approved':{'tasks':[{'vehicle':'UAV-01'}]}},0,0)
    def step(self,run,t,p,available=True,cancel=False):
        return run.step(t,0,{'UAV-01':(0,0,80)},{'UAV-01':(t,p)},{'UAV-01':available},cancel)
    def test_observe_return_complete_uses_measured_positions(self):
        r=self.run_fixture();self.step(r,0,(0,0,80));self.assertEqual(r.tasks['UAV-01']['stage'],'outbound')
        self.step(r,10,(100,50,60));self.assertEqual(r.tasks['UAV-01']['stage'],'observing')
        self.step(r,14,(100,50,60));self.assertEqual(r.tasks['UAV-01']['stage'],'observing')
        self.step(r,15,(100,50,60));self.assertEqual(r.tasks['UAV-01']['stage'],'returning')
        self.step(r,30,(0,0,80));self.assertEqual(r.report(30,{'UAV-01':(30,(0,0,80))},{'UAV-01':True})['status'],'completed')
    def test_distance_does_not_grow_after_completion(self):
        r=self.run_fixture();self.step(r,0,(0,0,80));self.step(r,10,(100,50,60));self.step(r,15,(100,50,60));self.step(r,30,(0,0,80))
        distance=r.tasks['UAV-01']['distance_m']
        self.step(r,60,(100,0,80));self.assertEqual(r.tasks['UAV-01']['distance_m'],distance)

    def test_missing_or_unavailable_observation_never_completes(self):
        r=self.run_fixture();r.step(10,0,{'UAV-01':(0,0,80)},{},{'UAV-01':True})
        self.step(r,20,(100,50,60),False);self.assertEqual(r.tasks['UAV-01']['stage'],'outbound')
    def test_cancel_returns_home_without_observing(self):
        r=self.run_fixture();goal=self.step(r,5,(50,0,80),cancel=True)
        self.assertEqual(goal['UAV-01'],(0,0,80))
        self.step(r,10,(0,0,80));self.assertTrue(r.cancelled);self.assertEqual(r.tasks['UAV-01']['stage'],'completed')
if __name__=='__main__':unittest.main()
