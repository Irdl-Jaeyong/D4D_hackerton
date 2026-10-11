from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from check_enter import receiving_ids


class ReadinessTests(unittest.TestCase):
    def test_fresh_simulated_fault_proves_receiving_only(self):
        vehicle = {'id': 'UAV-01', 'connected': False, 'fault_type': 'communication',
                   'simulation_pose': {'received_at': 99.8}}
        self.assertEqual(receiving_ids({'vehicles': [vehicle]}, now=100), {'UAV-01'})
        self.assertFalse(vehicle['connected'])

    def test_stale_or_missing_fault_pose_cannot_mask_disconnect(self):
        for pose in [{}, {'received_at': 90}, {'received_at': 110}]:
            with self.subTest(pose=pose):
                vehicle = {'id': 'UAV-01', 'connected': False, 'fault_type': 'communication', 'simulation_pose': pose}
                self.assertEqual(receiving_ids({'vehicles': [vehicle]}, now=100), set())
