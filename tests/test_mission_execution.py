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

class SurfaceResponse(unittest.TestCase):
    def run_fixture(self):
        return ObservationRun({'id':2,'card':{'offset':[100,50]},'approved':{'tasks':[{'vehicle':'UAV-01'},{'vehicle':'USV-02'}]}},0,0)
    def test_usv_goes_to_standoff_then_returns_using_measured_odometry(self):
        r=self.run_fixture();homes={'UAV-01':(0,0,80),'USV-02':(0,90,.7)};available={'UAV-01':True,'USV-02':True}
        goals=r.step(0,0,homes,{'UAV-01':(0,(0,0,80)),'USV-02':(0,(0,90,.7))},available)
        self.assertIn('USV-02',goals);self.assertEqual(goals['USV-02'],(100,75,.7))
        obs={'UAV-01':(10,(100,50,60)),'USV-02':(10,(100,75,.7))}
        r.step(10,0,homes,obs,available);self.assertEqual(r.tasks['USV-02']['stage'],'observing')
        r.step(15,0,homes,{id:(15,p) for id,(_,p) in obs.items()},available)
        self.assertEqual(r.tasks['USV-02']['stage'],'returning')
        r.step(20,0,homes,{'UAV-01':(20,(0,0,80)),'USV-02':(20,(0,90,.7))},available)
        self.assertEqual(r.report(20,{'UAV-01':(20,(0,0,80)),'USV-02':(20,(0,90,.7))},available)['status'],'completed')
    def test_usv_fault_cannot_claim_mission_complete_and_cancel_uses_home(self):
        r=self.run_fixture();homes={'UAV-01':(0,0,80),'USV-02':(0,90,.7)}
        r.step(5,0,homes,{'USV-02':(5,(100,75,.7))},{'USV-02':False})
        report=r.report(5,{'USV-02':(5,(100,75,.7))},{'USV-02':False})
        self.assertTrue(report['tasks']['USV-02']['blocked']);self.assertEqual(report['status'],'running')
        goals=r.step(6,0,homes,{'USV-02':(6,(100,75,.7))},{'USV-02':True},cancel=True)
        self.assertEqual(goals['USV-02'],homes['USV-02'])
    def test_moving_ship_target_updates_usv_standoff_and_uav_target(self):
        r=self.run_fixture();homes={'UAV-01':(0,0,80),'USV-02':(0,90,.7)}
        goals=r.step(1,0,homes,{'UAV-01':(1,(0,0,80)),'USV-02':(1,(0,90,.7))},{'UAV-01':True,'USV-02':True},target_world=[110,60])
        self.assertEqual(goals['USV-02'],(110,85,.7));self.assertEqual(goals['UAV-01'],(110,60,60))
