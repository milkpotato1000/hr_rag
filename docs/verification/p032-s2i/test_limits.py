import tempfile, unittest
from unittest.mock import patch
from control import *
from runtime import verify_parent
class Limits(unittest.TestCase):
    def test_single_and_closed(self):
        c=State(initial(),lambda:20)
        c.claim()
        with self.assertRaises(Stop):c.claim()
        h=dict(at=20,rss_bytes=1,pressure=1,disk_free=3*1024**3)
        c.reserve('w000','a','a',h)
        self.assertEqual(c.s['deadline'],740)
        c.s['active']=None
        with self.assertRaisesRegex(Stop,'generation_cap'):c.reserve('w000','a','a',h)
        c.clock=lambda:740
        with self.assertRaisesRegex(Stop,'deadline'):c.check()
        c.halt('timeout')
        with self.assertRaises(Stop):c.check()
    def test_parent_tamper(self):
        with patch('runtime.sha',return_value='invalid'), self.assertRaisesRegex(Stop,'parent_changed'):verify_parent()
    def test_lock(self):
        with tempfile.TemporaryDirectory() as d:
            with ownership(Path(d)/'lock'), self.assertRaises(Stop):
                with ownership(Path(d)/'lock'):pass
