import sys,math,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import convoy_motion as motion
class DynamicObservation(unittest.TestCase):
    def test_camera_moves_relative_to_ship_and_tracks_it(self):
        a=motion.tracking_camera(0,motion.CAMERA);b=motion.tracking_camera(15,motion.CAMERA)
        self.assertGreater(math.dist(a[:3],b[:3]),5)
        for t in (0,15,40):
            x,y,z,yaw,pitch=motion.tracking_camera(t,motion.CAMERA)
            self.assertAlmostEqual(yaw,math.atan2(-y,-x))
            self.assertAlmostEqual(pitch,math.atan2(z-12,math.hypot(x,y)))
    def test_patrol_is_bounded_and_keeps_slot_separation(self):
        homes=[(i*20,0,80) for i in range(40)]
        for t in range(60):
            points=motion.patrol_goals(homes,t)
            self.assertTrue(all(math.dist(a,b)<5 for a,b in zip(homes,points)))
            self.assertGreater(min(math.dist(a,b) for i,a in enumerate(points) for b in points[i+1:]),10)
        self.assertNotEqual(motion.patrol_goals(homes,0),motion.patrol_goals(homes,8))
    def test_hull_sea_response_visible_but_bounded(self):
        samples=[motion.hull_response(t,1.5*t,0,0,True) for t in range(60)]
        self.assertGreater(max(p[0] for p in samples)-min(p[0] for p in samples),.2)
        self.assertLess(max(abs(p[1]) for p in samples),.06)
