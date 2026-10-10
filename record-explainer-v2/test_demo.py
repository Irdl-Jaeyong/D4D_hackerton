import signal
import unittest
from unittest.mock import Mock, patch

import demo

class ShutdownTests(unittest.TestCase):
    def test_disappearing_child_does_not_skip_other_owned_child(self):
        first, second = Mock(pid=11), Mock(pid=22)
        first.poll.return_value = second.poll.return_value = None
        with patch("demo.os.killpg", side_effect=[ProcessLookupError(), None]) as kill:
            demo.stop([first, second])
        self.assertEqual([call.args for call in kill.call_args_list], [(22,signal.SIGTERM),(11,signal.SIGTERM)])
        first.wait.assert_called_once()
        second.wait.assert_called_once()

    def test_already_exited_child_is_not_signalled(self):
        child = Mock(pid=33)
        child.poll.return_value = 0
        with patch("demo.os.killpg") as kill:
            demo.stop([child])
        kill.assert_not_called()

if __name__ == "__main__":
    unittest.main(verbosity=2)
