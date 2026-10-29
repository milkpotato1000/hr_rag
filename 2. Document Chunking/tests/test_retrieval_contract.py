import sys,unittest,tempfile,math,json,contextlib
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from bm25_core import BM25Index,tokenize
from dense_core import create_index,DenseIndex
from document_common import STAGE,read_json
from experiment_common import EXP,source
from chunk_core import build,boundary_units,recursive
from run_chunking_experiment import choose

class RetrievalTests(unittest.TestCase):
    def test_bm25_independent_score_title_exclusion_and_tie(self):
        rows={'b':{'text':'cat dog','title':'SECRET'},'a':{'text':'cat cat','title':'dog'}}
        index=BM25Index(rows);_,hits=index.search('cat',2)
        idf=math.log(1+.5/2.5)
        self.assertEqual([h['chunk_id'] for h in hits],['a','b']);self.assertAlmostEqual(hits[0]['score'],idf*2*2.2/3.2)
        self.assertEqual(index.search('SECRET',2)[1],[]);self.assertEqual(tokenize('ＡＢＣ Cat'),'abc cat'.split())
        tied=BM25Index({'b':{'text':'cat'},'a':{'text':'cat'}});self.assertEqual([r['chunk_id'] for r in tied.search('cat',2)[1]],['a','b'])
    def test_dense_known_vectors_stale_and_payload(self):
        lock=read_json(STAGE/'runtime-lock.json');rows={cid:dict(chunk_id=cid,document_id='doc',version='1',title='title only',text='text '+cid,source='synthetic://test',synthetic=True) for cid in ['b','a','c']}
        x=[1.0]+[0.0]*1023;y=[0.0,1.0]+[0.0]*1022
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'index';create_index(rows,'hash',[x,x,y],lock,p)
            with DenseIndex(p,rows,'hash',lock) as index:
                hits=index.search(x,3);self.assertEqual([h['chunk_id'] for h in hits],['a','b','c']);self.assertAlmostEqual(hits[0]['score'],1.0);self.assertAlmostEqual(hits[2]['score'],0)
            with self.assertRaisesRegex(ValueError,'stale'):DenseIndex(p,rows,'different',lock)
            changed={**rows,'a':{**rows['a'],'text':'tampered'}}
            with self.assertRaisesRegex(ValueError,'payload'):DenseIndex(p,changed,'hash',lock)
    def test_no_label_policy_reads_or_prompt_leakage(self):
        original=Path.open;observed=[]
        def spy(path,*a,**kw):
            observed.append(str(path));self.assertNotIn('dataset.json',str(path));self.assertNotIn('policy-map',str(path));return original(path,*a,**kw)
        captured=[]
        class Embed:
            def embed(self,texts):captured.extend(texts);return [[1.,0.] for _ in texts],{'fixture':True}
        with tempfile.TemporaryDirectory() as tmp,patch.object(Path,'open',spy),patch('chunk_core.work_lock',contextlib.nullcontext):
            build('semantic-0',Path(tmp)/'chunk',provider=Embed())
        row,text,sections=source();units=boundary_units(text,sections['nodes'])
        self.assertEqual(captured,[text[u['start']:u['end']] for u in units]);self.assertTrue(observed)
    def test_recursive_decimal_boundary_uses_full_source(self):
        text='x 3.14 y z'
        self.assertEqual(recursive(text,maximum=4)[0],(0,2))
    def test_selection_ignores_holdout_and_retains_baseline_at_equal_recall(self):
        def row(cid,recall,ratio,ms):return dict(config_id=cid,run_id=cid,retriever='dense',at_k={'5':{'fact_recall':{'macro':recall}}},statistics={'emitted_unique_ratio':ratio},chunk_build_ms=ms)
        rows=[row('fixed-400-80',.5,1.2,10),row('llm-0',.5,1,1),row('structure-0',.6,1,2)]
        self.assertEqual(choose(rows)['candidate'],'structure-0');self.assertEqual(choose(rows[:2])['candidate'],'fixed-400-80')
if __name__=='__main__':unittest.main()
