import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from gazebo_status_bridge import poses
class StatusBridge(unittest.TestCase):
    def snapshot(self,state,connected=True):
        return {'scene':{'camera':{'pitch':.78,'yaw':.91}},'vehicles':[{'id':'USV-01','connected':connected,'telemetry':{'x':20,'y':30,'z':.7},'readiness':{'operational_state':state}}]}
    def test_only_status_models_are_commanded(self):
        command=poses(self.snapshot('defending'),{})
        self.assertEqual(command.count('pose {'),4)
        self.assertEqual(command.count('z:-200'),3)
        self.assertNotIn('name: "USV-01"',command)
        self.assertIn('status_dot_USV-01_defending',command)
    def test_lost_link_keeps_last_position_with_unavailable_label(self):
        history={};poses(self.snapshot('defending'),history)
        command=poses(self.snapshot('unavailable',False),history)
        self.assertIn('name: "status_dot_USV-01_unavailable" position {x:20 y:30 z:8.7}',command)
        self.assertEqual(command.count('z:-200'),3)
    def test_no_position_does_not_invent_marker_location(self):
        self.assertEqual(poses(self.snapshot('unavailable',False),{}).count('z:-200'),4)
    def test_parked_drone_indicator_attaches_to_body_not_eight_metres_above(self):
        snapshot=self.snapshot('unavailable');v=snapshot['vehicles'][0];v.update(id='UAV-01',fault={'phase':'charging'},telemetry={'x':10,'y':20,'z':3.5})
        command=poses(snapshot,{})
        self.assertIn('name: "status_dot_UAV-01_unavailable" position {x:10 y:20 z:3.7}',command)
        self.assertNotIn('z:11.5',command)
        self.assertIn('name: "charge_pad_UAV-01" position {x:10 y:20 z:3.37}',command)
    def test_inspection_hides_indicators_and_charging_pad_that_obscure_model(self):
        snapshot=self.snapshot('unavailable');v=snapshot['vehicles'][0];v.update(id='UAV-01',fault={'phase':'charging'})
        snapshot.update(camera_view='inspect',inspection_vehicle='UAV-01')
        command=poses(snapshot,{})
        self.assertEqual(command.count('z:-200'),5)
if __name__=='__main__':unittest.main()
