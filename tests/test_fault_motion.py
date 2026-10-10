import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
class FaultMotionTests(unittest.TestCase):
    def test_drone_holds_world_position_and_recovers_without_teleport(self):
        from fault_motion import FaultMotion
        f=FaultMotion()
        def desired(x):return {'UAV-01':{'x':x,'y':0,'z':60,'yaw':0,'pitch':0,'roll':0},'SHIP-01':{'x':x}}
        f.apply(desired(0),0,set())
        self.assertEqual(f.apply(desired(10),1,{'UAV-01'})['UAV-01']['x'],0)
        self.assertEqual(f.apply(desired(20),2,{'UAV-01'})['UAV-01']['x'],0)
        resumed=f.apply(desired(30),2.1,set())['UAV-01']['x']
        self.assertGreater(resumed,0);self.assertLessEqual(resumed,1.01)
        self.assertEqual(f.apply(desired(30),5,set())['SHIP-01']['x'],30)
    def test_repeated_fault_preserves_position_and_usv_is_not_teleported(self):
        from fault_motion import FaultMotion
        f=FaultMotion();p={'UAV-01':{'x':5,'y':8,'z':20},'USV-01':{'x':10,'y':0,'z':1}}
        f.apply(p,0,set());held=f.apply(p,1,{'UAV-01','USV-01'})
        self.assertEqual(held,p)
        f.apply({**p,'UAV-01':{'x':100,'y':8,'z':20}},2,set())
        h=f.apply(p,3,{'UAV-01'})
        self.assertNotEqual(h['UAV-01']['x'],100)
if __name__=='__main__':unittest.main()

class TypedFaults(unittest.TestCase):
 def test_propulsion_fault_descends_instead_of_hovering(self):
  from fault_motion import FaultMotion
  f=FaultMotion();p={'UAV-01':{'x':0,'y':0,'z':60},'SHIP-01':{'x':0}}
  f.apply(p,0,{})
  q=f.apply(p,.2,{'UAV-01':'propulsion'})
  self.assertLess(q['UAV-01']['z'],60)
  self.assertEqual(q['UAV-01']['x'],0)
 def test_payload_and_link_fault_keep_flight_control_returning(self):
  from fault_motion import FaultMotion
  for kind in ['payload','communication']:
   f=FaultMotion();p={'UAV-01':{'x':100,'y':50,'z':60},'SHIP-01':{'x':0}}
   f.apply(p,0,{})
   for i in range(1,20):q=f.apply(p,i*.2,{'UAV-01':kind})
   self.assertLess(q['UAV-01']['x'],100)
   self.assertGreater(q['UAV-01']['z'],0)
