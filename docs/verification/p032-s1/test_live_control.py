import unittest,tempfile
from pathlib import Path
from live_control import Control,LIMITS
from rag_package.storage import write_json,read_json,RagError
class Tests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.p=Path(self.tmp.name)/'ledger.json';self.now=100
  write_json(self.p,{'status':'ready','active':None,'started_at':None,'jobs':[],'reservations':{k:0 for k in LIMITS},'reranker_smoke_pairs':0,'reranker_full_pairs':0,'download_attempts':[]})
 def tearDown(self):self.tmp.cleanup()
 def c(self):return Control(self.p,clock=lambda:self.now)
 def test_deadline_survives_restart_and_blocks(self):
  c=self.c()
  with c.job('a','embedding_smoke'):pass
  self.now=7300
  with self.assertRaisesRegex(RagError,'s1_deadline'):self.c().begin('b','embedding_full')
  self.assertEqual(read_json(self.p)['started_at'],100)
 def test_reservation_before_worker_and_no_retry(self):
  c=self.c()
  with self.assertRaises(ValueError),c.job('a','reranker_smoke',20):
   c.before_spawn(['p','-m','rag_package.reranker_worker']);self.assertEqual(read_json(self.p)['reservations']['reranker_smoke'],1);raise ValueError()
  r=read_json(self.p);self.assertEqual(r['reranker_smoke_pairs'],20);self.assertEqual(r['status'],'halted')
  with self.assertRaisesRegex(RagError,'run_not_ready'):self.c()
 def test_caps_download_and_unresolved(self):
  c=self.c();c.download('e5')
  with self.assertRaisesRegex(RagError,'download_already_attempted'):c.download('e5')
  c.state['reranker_full_pairs']=390;c.save()
  with self.assertRaisesRegex(RagError,'pair_budget'),c.job('a','reranker_full',20):c.before_spawn(['p','-m','rag_package.reranker_worker'])
  r=read_json(self.p);r.update(status='ready',active='unresolved');write_json(self.p,r)
  with self.assertRaisesRegex(RagError,'unresolved_previous_job'):self.c()
 def test_persist_failure_prevents_dispatch(self):
  def fail(*args):raise OSError('disk')
  c=Control(self.p,clock=lambda:self.now,persist=fail)
  with self.assertRaises(OSError):c.begin('a','embedding_smoke')
  self.assertEqual(read_json(self.p)['reservations']['embedding_smoke'],0)
if __name__=='__main__':unittest.main()
