import sys,unittest,math
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from span_metrics import coverage,fact_result,grade,evaluate,select_budget,aggregate,stability

def s(a,b,d='a'):return dict(document_id=d,start=a,end=b)
class SpanMetricTests(unittest.TestCase):
    def test_and_spans_across_chunks_and_duplicate_union(self):
        f={'evidence_sets':[[s(0,2),s(4,6)]]};found=[s(0,2),s(4,6),s(0,2)]
        self.assertEqual(fact_result(f,found),{'complete':True,'partial':1})
        self.assertEqual(fact_result(f,[s(0,2)])['partial'],.5)
    def test_or_does_not_mix_partial_sets(self):
        f={'evidence_sets':[[s(0,2),s(4,6)],[s(8,10),s(12,14)]]}
        self.assertEqual(fact_result(f,[s(0,2),s(12,14)]),{'complete':False,'partial':.5})
    def test_document_offsets_never_mix(self):
        self.assertEqual(coverage([s(0,2,'a')],[s(0,2,'b')]),(0,2))
    def test_whitespace_only_overlap_is_zero_grade(self):
        f={'evidence_sets':[[s(0,3)]]};self.assertEqual(grade(s(1,2),[f],{'a':'a b'}),0)
        self.assertEqual(grade(s(0,1),[f],{'a':'a b'}),1)
    def test_independent_metrics_missing_slots_and_idcg(self):
        q={'answerability':'answerable','required_fact_ids':['f']};facts={'f':{'evidence_sets':[[s(0,2)]]}};maps=[dict(chunk_id='full',**s(0,2)),dict(chunk_id='part',**s(0,1)),dict(chunk_id='bad',**s(3,4))]
        r=evaluate(q,facts,maps,['part','bad','full'],5,{'a':'abcd'})
        self.assertEqual(r['fact_recall'],1);self.assertEqual(r['precision'],.4);self.assertEqual(r['recall'],1);self.assertEqual(r['mrr'],1)
        self.assertAlmostEqual(r['ndcg'],(1+3/math.log2(4))/(3+1/math.log2(3)))
        r=evaluate(q,facts,maps,['full','full'],5,{'a':'abcd'});self.assertEqual(r['precision'],.2)
    def test_no_relevant_no_answer_and_unknown_query(self):
        q={'answerability':'answerable','required_fact_ids':['f']};f={'f':{'evidence_sets':[[s(0,2)]]}};maps=[dict(chunk_id='bad',**s(3,4))]
        r=evaluate(q,f,maps,['bad'],5,{'a':'abcd'});self.assertIsNone(r['recall']);self.assertIsNone(r['ndcg']);self.assertEqual(r['fact_recall'],0)
        self.assertEqual(evaluate(None,f,maps,[],5,{'a':'abcd'})['status'],'N/A')
        q['answerability']='unanswerable';self.assertEqual(evaluate(q,f,maps,[],5,{'a':'abcd'})['status'],'N/A')
    def test_whole_chunk_budget_skip_continue_and_no_overlap_discount(self):
        chunks={'big':{'text':'x'*900},'small':{'text':'x'*200},'last':{'text':'x'*300}}
        r=select_budget(['big','small','last'],chunks,400);self.assertEqual(r['selected'],['small']);self.assertEqual(r['used_chars'],200)
    def test_jaccard_forced_exclusion_empty_sets(self):
        r=stability([[3,9],[3,9],[5,9]],[9],9);self.assertEqual(r['pair_denominator'],3);self.assertAlmostEqual(r['mean_jaccard'],1/3)
        self.assertEqual(stability([[9],[9]],[],9)['mean_jaccard'],1)
if __name__=='__main__':unittest.main()
