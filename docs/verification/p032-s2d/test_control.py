import copy,json,tempfile,unittest
from pathlib import Path
from control import *
class Controls(unittest.TestCase):
    def setUp(self):self.now=100.;self.c=State(initial(),lambda:self.now);self.c.claim();self.health={'pressure':1,'rss_bytes':123,'at':100.,'disk_free':3*1024**3}
    def reserve(self,q='gt01'):self.c.reserve(q,'x','x',self.health)
    def test_duplicate_claim(self):
        with self.assertRaisesRegex(Stop,'duplicate'):self.c.claim()
    def test_order_and_parallel(self):
        with self.assertRaisesRegex(Stop,'order'):self.reserve('gt02')
        self.reserve()
        with self.assertRaisesRegex(Stop,'parallel'):self.reserve()
    def test_caps(self):
        self.c.s['requests']=[{}]*10
        with self.assertRaisesRegex(Stop,'cap'):self.reserve()
        self.c.s['metadata']=[{}]*200
        with self.assertRaisesRegex(Stop,'cap'):self.c.metadata('/api/tags','test')
    def test_deadline_not_reset(self):
        self.reserve();self.assertEqual(self.c.s['deadline'],2800.);self.now=2800
        with self.assertRaisesRegex(Stop,'deadline'):self.c.check()
    def test_smoke_gate(self):
        for q in ('gt01','gt02'):
            self.reserve(q);self.c.response(q);self.c.finish(q,True,True,True)
        with self.assertRaisesRegex(Stop,'smoke_gate'):self.reserve('gt03')
        self.c.gate('gt01',True);self.c.gate('gt02',True);self.reserve('gt03')
    def test_failed_smoke(self):
        self.reserve();self.c.finish('gt01',True,True,True)
        with self.assertRaisesRegex(Stop,'smoke_content_failed'):self.c.gate('gt01',False)
    def test_unknown_timeout_blocks(self):
        self.reserve();self.c.halt('timeout')
        self.assertEqual(self.c.s['requests'][0]['server_completion'],'unknown')
        with self.assertRaisesRegex(Stop,'halted'):self.reserve('gt02')
    def test_resource_and_freshness(self):
        for k,v in [('pressure',2),('pressure',4),('rss_bytes',9*1024**3),('at',90.),('disk_free',1)]:
            h=dict(self.health);h[k]=v
            with self.assertRaises(Stop):self.c.reserve('gt01','x','x',h)
    def test_monitor_and_watchdog(self):
        for pressure,rss in [(None,1),(4,1),(1,None),(1,9*1024**3)]:
            with self.assertRaises(Stop):monitor_check(pressure,rss)
        monitor_check(2,100)
        with self.assertRaisesRegex(Stop,'watchdog'):watchdog(210)
    def test_prompt(self):
        with self.assertRaisesRegex(Stop,'prompt_identity'):self.c.reserve('gt01','bad','x',self.health)
    def test_identity(self):
        tags={'models':[{'name':'qwen3:4b','digest':DIGEST}]};version={'version':'0.40.8'};show={'details':{'quantization_level':'Q4_K_M'},'model_info':{'general.architecture':'qwen3'}};identity(tags,version,show)
        for key,value in [('digest','wrong'),('name','qwen3:8b')]:
            bad=copy.deepcopy(tags);bad['models'][0][key]=value
            with self.assertRaises(Stop):identity(bad,version,show)
        with self.assertRaises(Stop):identity(tags,{'version':'other'},show)
    def test_failed_cleanup(self):
        self.reserve()
        with self.assertRaises(Stop):self.c.finish('gt01',True,False,True)
    def test_atomic_halt_and_duplicate_ownership(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'ledger.json';write(p,initial())
            with self.assertRaises(Stop):
                with transact(p) as c:c.claim();raise Stop('first_failure')
            self.assertEqual(read(p)['first_error']['code'],'Stop:first_failure')
            with self.assertRaises(Stop):
                with transact(p) as c:c.claim()
            self.assertEqual(read(p)['first_error']['code'],'Stop:first_failure')
            with ownership(Path(d)/'owner'):
                with self.assertRaises(Stop):
                    with ownership(Path(d)/'owner'):pass
if __name__=='__main__':unittest.main(verbosity=2)
