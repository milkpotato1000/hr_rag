import unittest,tempfile,json,copy
from pathlib import Path
from continuation_control import Continuation,initial,START
from rag_package.storage import read_json,write_json,digest,RagError
E=Path(__file__).resolve().parent
class Tests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.parent=self.root/'parent';self.parent.mkdir();self.path=self.root/'ledger.json'
  (self.parent/'ledger.json').write_bytes((E/'run001/ledger.json').read_bytes());(self.parent/'manifest.json').write_bytes((E/'run001/manifest.json').read_bytes());self.identity={p.name:digest(p.read_bytes()) for p in self.parent.iterdir()};write_json(self.path,initial(self.parent,self.identity))
 def tearDown(self):self.tmp.cleanup()
 def c(self,now=START+100):return Continuation(self.path,self.parent,self.identity,clock=lambda:now)
 def test_parent_immutable_inherited_attempts_and_new_label(self):
  before=(self.parent/'ledger.json').read_bytes();c=self.c()
  with c.job('mmini-smoke-gt01','reranker_smoke',20):
   c.before_spawn(['p','-m','rag_package.reranker_worker']);c.after_worker({'workers_started':1,'worker_exited':True,'resume_safe':True})
  self.assertEqual((self.parent/'ledger.json').read_bytes(),before);self.assertEqual(c.state['reranker_smoke_pairs'],40);self.assertEqual(sum(c.state['reservations'].values()),26)
  self.assertEqual(c.state['jobs'][-1]['label'],'continuation001:mmini-smoke-gt01');self.assertIsNone(c.state['jobs'][-2]['completed_pairs'])
 def test_deadline_original_and_no_e5_download(self):
  with self.assertRaisesRegex(RagError,'s1_deadline'):self.c(START+7200)
  with self.assertRaisesRegex(RagError,'repeat_preparation_forbidden'):self.c().download('e5')
 def test_worker_and_pair_caps(self):
  c=self.c();c.state['reservations']['reranker_smoke']=5;c.save()
  with self.assertRaisesRegex(RagError,'worker_budget'),c.job('x','reranker_smoke',20):c.before_spawn(['p','-m','rag_package.reranker_worker'])
  self.tearDown();self.setUp();c=self.c();c.state['reranker_smoke_pairs']=90;c.save()
  with self.assertRaisesRegex(RagError,'pair_budget'),c.job('x','reranker_smoke',20):c.before_spawn(['p','-m','rag_package.reranker_worker'])
 def test_parent_tamper_rejected(self):
  (self.parent/'manifest.json').write_text('{}')
  with self.assertRaisesRegex(RagError,'parent_changed'):self.c()
 def test_unresolved_parent_worker_rejected(self):
  s=read_json(self.parent/'ledger.json');s['jobs'][-1]['observation']['worker_exited']=False;write_json(self.parent/'ledger.json',s);self.identity['ledger.json']=digest((self.parent/'ledger.json').read_bytes())
  with self.assertRaisesRegex(RagError,'unresolved_previous_worker'):initial(self.parent,self.identity)
 def test_failed_continuation_stays_halted(self):
  c=self.c()
  with self.assertRaises(ValueError),c.job('x','reranker_smoke',20):raise ValueError('fixture')
  with self.assertRaisesRegex(RagError,'run_not_ready'):self.c()
if __name__=='__main__':unittest.main()
