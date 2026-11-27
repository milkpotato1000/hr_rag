"""Independent omission cases for approved atomic facts; no models or rankings."""
import unittest
from pathlib import Path
from rag_package.storage import read_json
from rag_package.fact_metrics import coverage
P=Path(__file__).resolve().parent/'input';F=read_json(P/'facts.json');M=read_json(P/'claims-mapping.json');T=(P/'snapshot-installed/hr-handbook/canonical.txt').read_text()
def rows_except(a,b):return [{'document_id':'hr-handbook','start':0,'end':a},{'document_id':'hr-handbook','start':b,'end':len(T)}]
def find(qid):return next(q['required_facts'] for q in F['questions'] if q['question_id']==qid)
class Facts(unittest.TestCase):
 def test_birthday_probation_omission_does_not_remove_annual_day(self):
  c=next(c for c in M if c['claim_id']=='gt01-c02-a3');s=c['alternatives'][0]['spans'][1]
  r=coverage(rows_except(s['start'],s['end']),find('gt01'))
  self.assertIn('gt01-c02-a1',r['fulfilled_ids']);self.assertIn('gt01-c02-a2',r['fulfilled_ids']);self.assertNotIn('gt01-c02-a3',r['fulfilled_ids'])
 def test_outage_three_fields_are_independent(self):
  c=next(c for c in M if c['claim_id']=='gt07-c01-a2');s=c['alternatives'][0]['spans'][1]
  r=coverage(rows_except(s['start'],s['end']),find('gt07'))
  self.assertIn('gt07-c01-a1',r['fulfilled_ids']);self.assertNotIn('gt07-c01-a2',r['fulfilled_ids']);self.assertIn('gt07-c01-a3',r['fulfilled_ids'])
 def test_procedural_paraphrase_is_not_full_policy_support(self):
  c=next(c for c in M if c['claim_id']=='gt04-c05');rs=[dict(s) for s in c['related_partial_evidence']]
  r=coverage(rs,find('gt04'));self.assertNotIn('gt04-c05',r['fulfilled_ids'])
 def test_empty_tail_qrels_and_missing_answer(self):
  q=read_json(P/'qrels.json');cs=read_json(P/'build-bm25/chunks.json')
  for qid,i in (('gt03',85),('gt08',149),('gt06',171)):self.assertEqual(q['judgments'][qid][cs[i]['chunk_id']],0)
  for qid in ('gt09','gt10'):
   self.assertFalse(any(q['judgments'][qid].values()));self.assertIsNone(coverage([],find(qid))['fact_recall'])
if __name__=='__main__':unittest.main()
