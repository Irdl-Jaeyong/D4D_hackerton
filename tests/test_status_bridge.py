import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from gazebo_status_bridge import poses
class StatusBridge(unittest.TestCase):
    def snapshot(self,state,connected=True):
        return {'scene':{'camera':{'pitch':.78,'yaw':.91}},'vehicles':[{'id':'USV-01','connected':connected,'telemetry':{'x':20,'y':30,'z':.7},'readiness':{'operational_state':state}}]}
    def test_only_status_models_are_commanded(self):
        command=poses(self.snapshot('defending'),{})
        self.assertEqual(command.count('pose {'),3)
        self.assertEqual(command.count('z:-200'),2)
        self.assertNotIn('name: "USV-01"',command)
        self.assertIn('status_dot_USV-01_defending',command)
    def test_lost_link_keeps_last_position_with_unavailable_label(self):
        history={};poses(self.snapshot('defending'),history)
        command=poses(self.snapshot('unavailable',False),history)
        self.assertIn('name: "status_dot_USV-01_unavailable" position {x:20 y:30 z:8.7}',command)
        self.assertEqual(command.count('z:-200'),2)
    def test_no_position_does_not_invent_marker_location(self):
        self.assertEqual(poses(self.snapshot('unavailable',False),{}).count('z:-200'),3)
if __name__=='__main__':unittest.main()
