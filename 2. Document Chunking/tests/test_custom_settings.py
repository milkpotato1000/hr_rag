import json,sys,tempfile,unittest,math
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from experiment_common import config,source,EXP,ExperimentError
from chunk_settings import normalize,without_overlap,LIMITS
from chunk_core import build,boundary_units,unit_windows,llm_payload,parse_boundaries,llm_partition
from document_common import read_json
import serve_chunking as server

class CustomTests(unittest.TestCase):
    def test_roundtrip_separation_and_rejection(self):
        a=config(dict(method='fixed',size_chars=600,overlap_chars=100));self.assertEqual(a,config(a));self.assertEqual(a,config(dict(overlap_chars=100,size_chars=600,method='fixed')))
        self.assertNotEqual(a['id'],config(dict(method='fixed',size_chars=601,overlap_chars=100))['id'])
        for v in [None,[],True,dict(method='fixed',size_chars=600,overlap_chars=100,foo=1),{**a,'id':'forged'},dict(method='semantic',size_chars=600,overlap_chars=0,distance_threshold=float('nan'))]:
            with self.assertRaises(ExperimentError):config(v)
    def test_ranges_and_conditional_parameters(self):
        for method,b in LIMITS['methods'].items():
            good=dict(method=method,size_chars=b['default'],overlap_chars=0)
            if method=='semantic':good['distance_threshold']=.25
            config(good)
            for bad in [True,0,-1,1.5,b['minimum']-1,b['maximum']+1]:
                with self.assertRaises(ExperimentError):config({**good,'size_chars':bad})
            for bad in [True,-1,401,good['size_chars']]:
                with self.assertRaises(ExperimentError):config({**good,'overlap_chars':bad})
        with self.assertRaises(ExperimentError):config(dict(method='fixed',size_chars=100,overlap_chars=1))
    def test_frozen_configs_unchanged(self):
        for c in read_json(EXP/'spec.json')['configs']:
            self.assertEqual(config(c),c);self.assertEqual(config(c['id']),c)
    def test_build_applies_size_and_is_deterministic(self):
        with tempfile.TemporaryDirectory() as tmp:
            paths=[Path(tmp)/f'run{i}' for i in range(3)]
            for p,size in zip(paths,[600,600,700]):build(dict(method='fixed',size_chars=size,overlap_chars=100),p)
            self.assertEqual((paths[0]/'chunks.jsonl').read_bytes(),(paths[1]/'chunks.jsonl').read_bytes())
            a=read_json(paths[0]/'statistics.json');b=read_json(paths[2]/'statistics.json')
            self.assertEqual(a['max'],600);self.assertEqual(b['max'],700);self.assertNotEqual(a['chunk_count'],b['chunk_count'])
            self.assertEqual(a['coverage_with_skipped'],38582)
            self.assertEqual(read_json(paths[0]/'source-map.json')['base_spans'][:2],[[0,600],[500,1100]])
    def test_structure_and_recursive_actual_size(self):
        with tempfile.TemporaryDirectory() as tmp:
            for method in ('structure','recursive'):
                counts=[]
                for size in [100,600]:
                    p=Path(tmp)/f'{method}{size}';build(dict(method=method,size_chars=size,overlap_chars=0),p)
                    s=read_json(p/'statistics.json');self.assertLessEqual(s['max'],size);self.assertEqual(s['coverage_with_skipped'],38582);counts.append(s['chunk_count'])
                self.assertGreater(counts[0],counts[1])
    def test_semantic_size_and_threshold_passed_to_core(self):
        class FixtureProvider:
            def embed(self,texts):return [[1.,0.]]*len(texts),{'fixture':True}
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'semantic';build(dict(method='semantic',size_chars=600,overlap_chars=40,distance_threshold=2),p,provider=FixtureProvider())
            s=read_json(p/'statistics.json');self.assertTrue(any(x>400 for x in s['base_lengths']));self.assertLessEqual(max(s['base_lengths']),600)
            q=Path(tmp)/'threshold';build(dict(method='semantic',size_chars=600,overlap_chars=40,distance_threshold=0),q,provider=FixtureProvider())
            self.assertGreater(read_json(q/'statistics.json')['chunk_count'],s['chunk_count'])
    def test_parent_requires_same_parameters(self):
        a=config(dict(method='semantic',size_chars=600,overlap_chars=80,distance_threshold=.3));p=without_overlap(a)
        self.assertEqual(p['base_max_chars'],600);self.assertEqual(p['distance_threshold'],.3);self.assertEqual(p['overlap_chars'],0)
    def test_llm_prompt_budget_and_length_validation(self):
        _,text,nodes=source();units=boundary_units(text,nodes['nodes']);windows=unit_windows(units)
        for maximum in (400,600,1200):
            for us in windows:
                payload,upper=llm_payload(text,us,maximum);self.assertLessEqual(upper+1024,8192);self.assertIn(f'<={maximum} source characters',payload['messages'][0]['content'])
        us=[dict(id='a',start=0,end=400),dict(id='b',start=400,end=800)]
        response={'model':'qwen3:4b','done':True,'done_reason':'stop','message':{'content':'{"end_unit_ids":["b"]}'}}
        with self.assertRaises(ExperimentError):parse_boundaries(response,us,600)
        self.assertEqual(parse_boundaries(response,us,900),[(0,800)])
    def test_budget_limits_validate_before_lookup(self):
        body=dict(a_run_id='x',b_run_id='y',retriever='bm25',top_k=5,question='question')
        for value in (1,1600,8000,24000):
            with patch.object(server,'catalog',return_value=[]):
                with self.assertRaises(ExperimentError) as ctx:server.compare({**body,'budget_chars':value})
                self.assertEqual(ctx.exception.kind,'not_found')
        for value in (0,24001,True,1.5):
            with self.assertRaises(ExperimentError) as ctx:server.compare({**body,'budget_chars':value})
            self.assertEqual(ctx.exception.kind,'invalid_input')
    def test_history_rejects_failed_stale_and_mutated(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(server,'ARTIFACTS',Path(tmp)):
            p=Path(tmp)/('chunk-'+'a'*32);build(dict(method='fixed',size_chars=600,overlap_chars=100),p)
            self.assertEqual(len(server.catalog()),1)
            (p/'chunks.jsonl').write_text('changed');self.assertEqual(server.catalog(),[])
    def test_empty_failed_and_wrong_source_history(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(server,'ARTIFACTS',Path(tmp)):
            self.assertEqual(server.catalog(),[])
            p=Path(tmp)/('chunk-'+'a'*32);p.mkdir();(p/'manifest.json').write_text(json.dumps(dict(status='failed')))
            self.assertEqual(server.catalog(),[])
            q=Path(tmp)/('chunk-'+'b'*32);build(dict(method='fixed',size_chars=600,overlap_chars=100),q)
            m=read_json(q/'manifest.json');m['canonical_sha256']='wrong';(q/'manifest.json').write_text(json.dumps(m))
            self.assertEqual(server.catalog(),[])
    def test_unknown_run_and_missing_index_reject_before_model(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(server,'ARTIFACTS',Path(tmp)),patch.object(server,'Provider') as provider:
            cfg=dict(method='fixed',size_chars=600,overlap_chars=100);p=Path(tmp)/('chunk-'+'c'*32);build(cfg,p)
            body=dict(a_run_id=p.name,b_run_id=p.name,retriever='dense',top_k=5,budget_chars=8000,question='test')
            with self.assertRaises(ExperimentError) as ctx:server.compare(body)
            self.assertEqual(ctx.exception.kind,'index_not_ready');provider.assert_not_called()
            with self.assertRaises(ExperimentError) as ctx:server.compare({**body,'a_run_id':'unknown'})
            self.assertEqual(ctx.exception.kind,'not_found');provider.assert_not_called()
    def test_replay_does_not_mix_code_prompt_or_runtime_versions(self):
        cfg=config(dict(method='fixed',size_chars=600,overlap_chars=100))
        with tempfile.TemporaryDirectory() as tmp,patch.object(server,'ARTIFACTS',Path(tmp)):
            p=Path(tmp)/('chunk-'+'d'*32);build(cfg,p);original=read_json(p/'manifest.json')
            self.assertEqual(server.replay(cfg),p)
            for key in ('code_hash','prompt_sha256','runtime_lock_sha256','spec_sha256'):
                (p/'manifest.json').write_text(json.dumps({**original,key:'stale'}))
                with self.assertRaises(ExperimentError):server.replay(cfg)
            (p/'manifest.json').write_text(json.dumps(original))
            self.assertEqual(server.replay(cfg),p)
    def test_custom_parent_rejects_stale_code(self):
        class FixtureProvider:
            def embed(self,texts):return [[1.,0.]]*len(texts),{'fixture':True}
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'parent';cfg=dict(method='semantic',size_chars=600,overlap_chars=0,distance_threshold=.3)
            build(cfg,p,provider=FixtureProvider());m=read_json(p/'manifest.json');m['code_hash']='old-code';(p/'manifest.json').write_text(json.dumps(m))
            with self.assertRaises(ExperimentError):build({**cfg,'overlap_chars':80},Path(tmp)/'child',parent=p)
if __name__=='__main__':unittest.main()
