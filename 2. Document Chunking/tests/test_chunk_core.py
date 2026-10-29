import copy,json,sys,unittest,tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from chunk_core import boundary_units,unit_windows,recursive,structure,semantic,extend,parse_boundaries,make_chunks,llm_payload
from source_io import windows
from experiment_common import ExperimentError,source,EXP
from document_common import read_json

def response(ids):return {'model':'qwen3:4b','done':True,'done_reason':'stop','message':{'content':json.dumps({'end_unit_ids':ids})}}
class ChunkCoreTests(unittest.TestCase):
    def test_fixed_unicode_and_last_window(self):
        self.assertEqual(list(windows('한글🙂abc',4,1)),[(0,4),(3,6)])
        for size,overlap in [(True,0),(0,0),(4,4),(4,-1)]:
            with self.assertRaises(ValueError):list(windows('x',size,overlap))
    def test_units_preserve_whitespace_decimals_and_forced_splits(self):
        text='0.5일이다.  다음!\n\n긴문장끝';u=boundary_units(text,maximum=8)
        self.assertEqual(''.join(text[x['start']:x['end']] for x in u),text)
        self.assertNotIn(2,[x['end'] for x in u]);self.assertTrue(any(x['kind']=='forced_atom_split' for x in u))
        with self.assertRaises(ValueError):boundary_units('')
    def test_heading_end_but_not_toc_visual_line(self):
        text='목차\n제1장\n\n제1장\n내용이다.';nodes=[{'heading':{'end':12}}]
        u=boundary_units(text,nodes);self.assertIn(12,[x['end'] for x in u]);self.assertNotIn(3,[x['end'] for x in u])
    def test_recursive_priority_and_overlap(self):
        self.assertEqual(recursive('ab\n\ncd efgh',maximum=8),[(0,4),(4,11)])
        self.assertEqual(extend([(0,2),(2,7),(7,10)],4),[(0,2),(0,7),(3,10)])
        self.assertEqual(recursive('abcdefgh',maximum=3),[(0,3),(3,6),(6,8)])
    def test_structure_keeps_small_articles(self):
        ns=[{'heading':{'start':2}},{'heading':{'start':5}}]
        self.assertEqual(structure('abcdefgh',ns,400),[(0,2),(2,5),(5,8)])
    def test_semantic_maximum_before_distance_and_equal_threshold(self):
        u=[{'id':str(i),'start':i*100,'end':(i+1)*100} for i in range(4)]
        spans,_=semantic(u,[[1,0],[0,1],[0,1],[0,1]],maximum=200,minimum=100,threshold=1)
        self.assertEqual(spans,[(0,100),(100,300),(300,400)])
        with self.assertRaises(ValueError):semantic(u,[[0,0]]*4)
    def test_window_limits_and_complete_response(self):
        u=[{'id':f'u{i}','start':i*300,'end':(i+1)*300} for i in range(5)]
        self.assertEqual([len(w) for w in unit_windows(u,1200,20)],[4,1])
        self.assertEqual(parse_boundaries(response(['u1','u4']),u,900),[(0,600),(600,1500)])
        for ids in [[],['missing'],['u0'],['u1','u1','u4'],['u4','u1'],['u4']]:
            with self.assertRaises(ValueError):parse_boundaries(response(ids),u)
        for content in ['{"end_unit_ids":[],"end_unit_ids":["u4"]}','{"end_unit_ids":["u4"],"x":0}','not json']:
            r=response([]);r['message']['content']=content
            with self.assertRaises(ValueError):parse_boundaries(r,u)
        r=response(['u1','u4']);r['done_reason']='length'
        with self.assertRaises(ValueError):parse_boundaries(r,u,900)
    def test_source_slice_coverage_skips_and_page_separator(self):
        text='한글\n\n abc';row={'document_id':'fixture','version':'4','title':'x','canonical_sha256':'canon','original_sha256':'pdf','pages':[dict(page_number=1,start=0,end=2,text_sha256='one',raw_text_sha256='one'),dict(page_number=2,start=4,end=8,text_sha256='two',raw_text_sha256='two')]}
        u=boundary_units(text);cfg={'id':'fixture','method':'recursive','overlap_chars':0};chunks,m,s=make_chunks(row,text,[],u,cfg,[(0,2),(2,4),(4,8)])
        self.assertEqual(len(chunks),2);self.assertEqual(m['skipped'][0]['start'],2);self.assertEqual(s['coverage_with_skipped'],8)
        self.assertEqual(m['chunks'][1]['pages'][0]['page_number'],2)
        with self.assertRaises(ValueError):make_chunks(row,text,[],u,cfg,[(0,2),(3,8)])
    def test_frozen_units_windows_and_prompt_budget(self):
        _,text,sections=source();units=boundary_units(text,sections['nodes']);self.assertEqual(units,read_json(EXP/'boundary-map.json')['units'])
        batches=unit_windows(units);self.assertEqual(len(batches),35);self.assertEqual(max(llm_payload(text,b)[1] for b in batches),6510)
        probes=read_json(EXP/'source-profile.json')['fixed_count_profile']
        self.assertEqual([len(list(windows(text,p['size'],p['overlap']))) for p in probes],[193,241,97,121,49,61])
if __name__=='__main__':unittest.main()
