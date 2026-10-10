import math,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from formation_motion import targets,Transition,CATALOG
class Formations(unittest.TestCase):
    def test_stations_do_not_rotate_with_time(self):
        for group,modes in CATALOG.items():
            for mode in modes:
                if mode=='hemisphere':continue
                self.assertEqual(targets(group,mode,0),targets(group,mode,900))

    def test_hemisphere_keeps_leader_relative_stations(self):
        import convoy_motion as convoy
        initial=convoy.fleet_poses(0)
        for t in (30,300,900):
            current=convoy.fleet_poses(t)
            for i in range(40):
                name=f'UAV-{i+1:02}'
                for axis in ('x','y','z'):
                    value=current[name][axis]-(convoy.MOTION['ship_speed']*t if axis=='x' else 0)
                    self.assertAlmostEqual(value,initial[name][axis])

    def test_counts_and_unique_slots(self):
        for group,modes in CATALOG.items():
            for mode in modes:
                if mode=='hemisphere':continue
                points=targets(group,mode)
                self.assertEqual(len(points),10 if group=='usv' else 40)
                self.assertEqual(len(set(points)),len(points))
    def test_retargeting_preserves_position_and_limits_acceleration(self):
        planner=Transition(targets('uav','box'),10,4)
        goal=targets('uav','v');planner.select(goal)
        for _ in range(50):planner.step(goal,.1)
        old=[p[:] for p in planner.points];velocity=[v[:] for v in planner.velocity]
        goal=targets('uav','triangle');planner.select(goal)
        self.assertEqual(old,planner.points);self.assertEqual(velocity,planner.velocity)
        planner.step(goal,.1)
        for p,q,v,w in zip(old,planner.points,velocity,planner.velocity):
            self.assertLessEqual(math.dist(p,q),1.001)
            self.assertLessEqual(math.dist(v,w),.401)
    def test_usv_routes_clear_flagship_and_converge(self):
        for mode in ['v','columns','fan']:
            planner=Transition(targets('usv','circle'),3,1);goals=targets('usv',mode)
            clearance=1000
            for _ in range(6000):
                error=planner.step(goals,.1,marine=True)
                clearance=min(clearance,min(math.hypot(max(0,abs(p[0])-80),max(0,abs(p[1])-12)) for p in planner.points))
            self.assertLess(error,1)
            self.assertGreater(clearance,5)

    def test_static_drone_transition_converges_with_separation(self):
        planner=Transition(targets('uav','box'),10,4)
        goal=targets('uav','triangle');minimum=1000
        for _ in range(1800):
            error=planner.step(goal,.1)
            minimum=min(minimum,min(math.dist(p,q) for i,p in enumerate(planner.points) for q in planner.points[i+1:]))
        self.assertLess(error,1);self.assertGreater(minimum,4)
if __name__=='__main__':unittest.main()
