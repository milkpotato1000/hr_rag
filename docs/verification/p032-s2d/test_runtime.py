import tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import runtime as r
from control import *
class FakeProcess:
    def __init__(self,polls):self.polls=iter(polls);self.value=None;self.terminated=False;self.waited=False
    def poll(self):
        if self.terminated:return self.value
        try:self.value=next(self.polls)
        except StopIteration:pass
        return self.value
    def terminate(self):self.terminated=True;self.value=-15
    def wait(self,timeout=None):self.waited=True;self.value=-15 if self.terminated else 0;return self.value
class RuntimeTests(unittest.TestCase):
    def test_watchdog_and_owned_reap(self):
        proc=FakeProcess([None]*4);clock=iter([0,211])
        with self.assertRaisesRegex(Stop,'watchdog'):r.observe_client(proc,check=lambda:None,clock=lambda:next(clock))
        self.assertTrue(r.reap_owned_client(proc));self.assertTrue(proc.terminated and proc.waited)
    def test_failed_resource_before_metadata(self):
        proc=FakeProcess([None]);calls=[]
        with self.assertRaisesRegex(Stop,'critical'):r.observe_client(proc,check=lambda:None,measure=lambda:{'pressure':4,'rss_bytes':123},loaded=lambda _:calls.append(1))
        self.assertEqual(calls,[])
    def test_warning_observed_not_fake_cancellation(self):
        proc=FakeProcess([None,0]);calls=[]
        warning,observations=r.observe_client(proc,check=lambda:None,measure=lambda:{'pressure':2,'rss_bytes':1},persist=lambda x:calls.append(x),loaded=lambda _:{'models':[]},clock=lambda:1,sleep=lambda _:None)
        self.assertTrue(warning);self.assertEqual(len(observations),1);self.assertFalse(proc.terminated)
    def test_metadata_transport_timeout_is_five(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'ledger.json';write(path,initial());seen=[]
            class Client:
                def open(self,request,timeout):seen.append(timeout);raise TimeoutError('synthetic timeout')
            with patch.object(r,'LEDGER',path),patch.object(r.urllib.request,'build_opener',return_value=Client()):
                with self.assertRaises(TimeoutError):r.metadata('/api/tags')
            self.assertEqual(seen,[5]);s=read(path);self.assertEqual(len(s['metadata']),1);self.assertEqual(s['metadata'][0]['status'],'failed');self.assertEqual(s['requests'],[])
    def test_metadata_cap_blocks_transport(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'ledger.json';s=initial();s['metadata']=[{}]*200;write(path,s)
            with patch.object(r,'LEDGER',path),patch.object(r.urllib.request,'build_opener',side_effect=AssertionError('must not send')):
                with self.assertRaisesRegex(Stop,'metadata_cap'):r.metadata('/api/tags')
            self.assertEqual(read(path)['status'],'halted')
if __name__=='__main__':unittest.main(verbosity=2)
