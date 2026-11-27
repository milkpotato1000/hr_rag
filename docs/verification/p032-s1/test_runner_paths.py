"""Offline repair test: prepare phase succeeded, runtime output directories were absent."""
from pathlib import Path
import tempfile,unittest
from unittest.mock import patch
import live_run
from rag_package.storage import read_json,write_json
class Paths(unittest.TestCase):
 def test_runtime_output_parents_and_config_without_model_calls(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);private=root/'private';out=root/'out';inp=root/'input';inp.mkdir()
   pp=private/'e5/prepared';pp.mkdir(parents=True)
   p={'schema_version':1,'model_id':'intfloat/multilingual-e5-small','revision':'c'*40,'local_path':'model','file_manifest':{'config.json':'d'*64},'device':'cpu','dtype':'float32','max_input_tokens':512,'batch_size':1,'timeout_seconds':120,'max_chunks':5000};write_json(pp/'profile.json',p)
   write_json(inp/'bm25.json',read_json(live_run.I/'bm25.json'))
   with patch.object(live_run,'PRIVATE',private),patch.object(live_run,'OUT',out),patch.object(live_run,'I',inp),patch.object(live_run.embedding,'encode',side_effect=AssertionError('no model')),patch.object(live_run.model_preparation,'prepare',side_effect=AssertionError('no download')):
    with self.assertRaises(FileNotFoundError):live_run.runtime_profile('e5')
    for d in ('profiles','configs'):(out/d).mkdir(parents=True)
    rp=live_run.runtime_profile('e5');cfg=live_run.cfg('e5','dense');assert read_json(rp)['timeout_seconds']==300;assert read_json(cfg)['embedding_config']==str(rp)
if __name__=='__main__':unittest.main()
