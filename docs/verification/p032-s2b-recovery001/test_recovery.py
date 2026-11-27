"""Independent synthetic environment failures and cumulative child accounting."""
from pathlib import Path
import unittest,tempfile,importlib.util,sys,json,hashlib,base64,zipfile
from unittest.mock import patch
E=Path(__file__).resolve().parent
def mod(name):
 s=importlib.util.spec_from_file_location(name,E/(name+'.py'));m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
guard=mod('import_only');a=mod('environment_audit');c=mod('control');rt=mod('runtime')
from rag_package.storage import RagError,write_json
class Recovery(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.site=self.root/'site';self.site.mkdir();self.lock=self.root/'lock';self.lock.write_text('example==1.0\n');self.whl=self.root/'example.whl'
  with zipfile.ZipFile(self.whl,'w') as z:z.writestr('rag_package/example.py','x=1\n')
  (self.site/'rag_package').mkdir();(self.site/'rag_package/example.py').write_text('x=1\n')
  self.dist=self.site/'example-1.0.dist-info';self.dist.mkdir();(self.dist/'METADATA').write_text('Metadata-Version: 2.1\nName: example\nVersion: 1.0\n')
  (self.site/'example.py').write_text('original\n');p=self.site/'example.py';digest=base64.urlsafe_b64encode(hashlib.sha256(p.read_bytes()).digest()).decode().rstrip('=');(self.dist/'RECORD').write_text(f'example.py,sha256={digest},{p.stat().st_size}\n')
 def tearDown(self):self.temp.cleanup()
 def test_import_path_guard(self):
  for p in ('/python/lib/tokenize.py','/python/lib/token.py','/site-packages/transformers/tokenization_utils.py'):
   self.assertFalse(guard.forbidden_path(p))
  for p in ('/tmp/model.safetensors','/tmp/model.bin','/user/.aws/credentials','/tmp/token.json','/tmp/.env'):
   self.assertTrue(guard.forbidden_path(p))
 def test_complete_environment(self):self.assertEqual(a.audit(self.site,self.lock,self.whl)['locked_distributions'],{'example':'1.0'})
 def test_missing_entire_distribution(self):
  self.lock.write_text('example==1.0\nabsent==2.0\n')
  with self.assertRaisesRegex(ValueError,'missing_distribution:absent'):a.audit(self.site,self.lock,self.whl)
 def test_missing_metadata(self):
  (self.dist/'METADATA').unlink()
  with self.assertRaisesRegex(ValueError,'missing_distribution'):a.audit(self.site,self.lock,self.whl)
 def test_missing_record(self):
  (self.dist/'RECORD').unlink()
  with self.assertRaisesRegex(ValueError,'missing_record_metadata'):a.audit(self.site,self.lock,self.whl)
 def test_file_content_tamper(self):
  (self.site/'example.py').write_text('modified\n')
  with self.assertRaisesRegex(ValueError,'file_hash_mismatch'):a.audit(self.site,self.lock,self.whl)
 def test_product_tamper(self):
  (self.site/'rag_package/example.py').write_text('x=2\n')
  with self.assertRaisesRegex(ValueError,'product_wheel_mismatch'):a.audit(self.site,self.lock,self.whl)
 def test_import_failure(self):
  p=self.root/'bad.py';p.write_text('raise ImportError("independent missing dependency")')
  with self.assertRaisesRegex(ValueError,'sdk_import_failed'):a.import_check(sys.executable,p)
 def test_parent_content_tamper(self):
  expected=rt.hashes(self.site);rt.check_parent(self.site,expected);(self.site/'example.py').write_text('changed')
  with self.assertRaisesRegex(RagError,'parent_files_changed'):rt.check_parent(self.site,expected)
 def make(self):
  p=self.root/'ledger';write_json(p,c.initial());ctl=c.Control(p,clock=lambda:1795805000,disk=lambda:9*1024**3);ctl.claim();return ctl
 def test_parent_clock_and_unknown_preserved(self):
  ctl=self.make();ctl.begin('semantic-boundary',567);ctl.before_spawn(['x','rag_package.embedding_worker'])
  self.assertEqual(ctl.state['started_at'],1795804963.61378);self.assertEqual(ctl.state['deadline'],1795808563.61378);self.assertIsNone(ctl.state['parent_completed_items']);self.assertEqual(ctl.state['parent_requested_items']+ctl.state['reserved_items'],1134)
 def test_parent_budget_cannot_be_zeroed(self):
  ctl=self.make();ctl.state['parent_workers']=0;ctl.begin('semantic-boundary',567)
  with self.assertRaisesRegex(RagError,'recovery_parent_changed'):ctl.before_spawn(['x','rag_package.embedding_worker'])
 def test_deadline_cannot_extend(self):
  ctl=self.make();ctl.state['deadline']+=3600;ctl.begin('semantic-boundary',567)
  with self.assertRaisesRegex(RagError,'recovery_clock_changed'):ctl.before_spawn(['x','rag_package.embedding_worker'])
 def test_expired_before_dispatch(self):
  ctl=self.make();ctl.clock=lambda:1795808564
  with self.assertRaisesRegex(RagError,'s2b_deadline'):ctl.begin('semantic-boundary',567)
  self.assertEqual(ctl.state['reserved_workers'],0)
if __name__=='__main__':unittest.main()
