import sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from model_runtime import Ledger
from experiment_common import save_state
class BudgetTests(unittest.TestCase):
    def test_probes_persist_before_dispatch_and_timeout_blocks_restart(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'ledger.json';l=Ledger(path);self.assertEqual((l.state['llm_requests'],l.state['embedding_items']),(3,2))
            timeout,record=l.before('llm',1,{'fixture':True},'corpus');self.assertEqual(Ledger(path).state['llm_requests'],4)
            with self.assertRaises(ValueError):Ledger(path).before('llm',1,{},'corpus')
            l.after(record,1,exc=TimeoutError('fixture'),unresolved=True)
            with self.assertRaises(ValueError):Ledger(path).before('llm',1,{},'corpus')
    def test_hard_caps_do_not_increment_on_rejection(self):
        for kind,field,value,purpose,items in [('llm','llm_requests',219,'corpus',1),('llm','corpus_requests',210,'corpus',1),('llm','smoke_requests',6,'smoke',1),('llm','llm_seconds',7200,'corpus',1),('embedding','embedding_items',31999,'embedding',2),('embedding','embedding_seconds',1800,'embedding',1)]:
            with tempfile.TemporaryDirectory() as tmp:
                path=Path(tmp)/'ledger.json';l=Ledger(path);l.state[field]=value;save_state(path,l.state);before=path.read_bytes()
                with self.assertRaises(ValueError):l.before(kind,items,{},purpose)
                self.assertEqual(path.read_bytes(),before)
    def test_usage_count_failure_and_rankings(self):
        with tempfile.TemporaryDirectory() as tmp:
            l=Ledger(Path(tmp)/'ledger.json');_,r=l.before('embedding',2,{'input':['a','b']},'embedding');l.after(r,.5,exc=ValueError('bad vector'))
            self.assertEqual(l.state['embedding_items'],4)
            l.state['rankings']=2328;save_state(l.path,l.state)
            with self.assertRaises(ValueError):l.ranking()
if __name__=='__main__':unittest.main()

class ProviderFailureTests(unittest.TestCase):
    def test_timeout_is_durable_and_blocks_retry_without_extra_dispatch(self):
        from unittest.mock import patch
        from model_runtime import Provider,Ledger
        with tempfile.TemporaryDirectory() as t:
            ledger=Ledger(Path(t)/'ledger.json');provider=Provider(ledger);provider.checked=True
            with patch.object(provider,'http',side_effect=TimeoutError('controlled timeout')) as call:
                with self.assertRaisesRegex(ValueError,'controlled timeout'):provider.call('llm',{'model':'qwen3:4b'})
                with self.assertRaisesRegex(ValueError,'Previous call'):provider.call('llm',{'model':'qwen3:4b'})
                self.assertEqual(call.call_count,1)
            self.assertTrue(Ledger(ledger.path).refresh()['unresolved']);self.assertEqual(ledger.refresh()['llm_requests'],4)
