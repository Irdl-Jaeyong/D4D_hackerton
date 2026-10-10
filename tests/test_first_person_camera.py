import math,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from first_person_camera import mounted_camera
class FirstPersonCamera(unittest.TestCase):
 def test_drone_camera_is_in_front_and_follows_heading(self):
  p={'x':10,'y':20,'z':80,'yaw':math.pi/2,'roll':0,'pitch':0}
  c=mounted_camera('UAV-01',p)
  self.assertAlmostEqual(c['x'],10);self.assertGreater(c['y'],20)
  self.assertAlmostEqual(c['yaw'],math.pi/2);self.assertAlmostEqual(c['roll'],0)
 def test_surface_camera_mount_is_above_hull_and_follows_attitude(self):
  for name in ['USV-01','SHIP-01']:
   p={'x':10,'y':0,'z':.7,'yaw':-.7,'roll':.12,'pitch':-.06};c=mounted_camera(name,p)
   self.assertGreater(c['z'],p['z']);self.assertLess(abs(c['yaw']-p['yaw']),.1)
   self.assertNotEqual(c['roll'],0)
 def test_half_turn_reverses_camera_position_and_heading(self):
  a=mounted_camera('USV-01',{'x':0,'y':0,'z':.7,'yaw':0})
  b=mounted_camera('USV-01',{'x':0,'y':0,'z':.7,'yaw':math.pi})
  self.assertAlmostEqual(a['x'],-b['x']);self.assertAlmostEqual(a['y'],-b['y']);self.assertAlmostEqual(a['z'],b['z'])
