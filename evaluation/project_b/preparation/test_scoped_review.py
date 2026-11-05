"""P023 scope, approval boundaries, immutable policy and four-version regressions."""
import copy
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from core import digest, file_hash, read, write
import scoped_review as scoped
from test_review_revision import Structure

ROOT=Path(__file__).resolve().parent
PARENT=ROOT/'artifacts/run003'
OUT=ROOT/'artifacts/run004'
AUDIT=OUT/'scope-audit.json'
POLICY=OUT/'scoring-policy.md'


class ScopedReviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.packet,cls.mapping,cls.policy=scoped.build(PARENT,AUDIT,POLICY)
        cls.old=read(PARENT/'packet.json');cls.audit=read(AUDIT)

    def test_57_original_claims_and_answers_are_unchanged_with_38_19_partition(self):
        self.assertEqual(self.packet['schema_version'],3)
        self.assertEqual(self.packet['review_version'],'p023-core-supplement-v1')
        expected=[(6,4),(3,0),(8,1),(2,4),(4,0),(3,4),(4,4),(8,2),(0,0),(0,0)]
        roles=[]
        for q,old,counts in zip(self.packet['questions'],self.old['questions'],expected):
            self.assertEqual({k:v for k,v in q.items() if k!='answer_rubric'},old)
            rubric=q['answer_rubric'];r=rubric['required_claim_ids'];s=rubric['supplementary_claim_ids']
            self.assertEqual((len(r),len(s)),counts)
            self.assertFalse(set(r)&set(s))
            self.assertEqual(set(r+s),{c['id'] for c in old['codex_source_checked']['claims']})
            for ids,answer in [(r,rubric['required_answer']),(s,rubric['supplementary_answer'])]:
                self.assertEqual(answer,'\n'.join(c['text'] for c in old['codex_source_checked']['claims'] if c['id'] in ids))
            roles.extend(rubric['claim_roles'])
        self.assertEqual(sum(r['role']=='required' for r in roles),38)
        self.assertEqual(sum(r['role']=='supplementary' for r in roles),19)
        self.assertEqual(len(self.mapping['changes']),57)
        self.assertEqual(self.packet['judgements'],self.old['judgements'])
        self.assertEqual(self.packet['experiment'],self.old['experiment'])

    def test_specific_scope_decisions_intents_and_clarification(self):
        qs={q['id']:q['answer_rubric'] for q in self.packet['questions']}
        self.assertEqual(qs['gt01']['required_claim_ids'],['gt01-c02-a1','gt01-c02-a2','gt01-c02-a3','gt01-c04-a1','gt01-c04-a2','gt01-c05-a1'])
        self.assertEqual(len(qs['gt01']['intents']),4)
        self.assertEqual(qs['gt04']['required_claim_ids'],['gt04-c01','gt04-c05'])
        self.assertEqual(qs['gt06']['required_claim_ids'],['gt06-c03','gt06-c04','gt06-c05'])
        self.assertEqual(qs['gt07']['required_claim_ids'],['gt07-c01-a1','gt07-c01-a2','gt07-c01-a3','gt07-c03'])
        clarification=next(r for r in qs['gt01']['claim_roles'] if r['claim_id']=='gt01-c07')
        self.assertEqual(clarification['role'],'supplementary')
        self.assertEqual(clarification['clarifies_required_ids'],['gt01-c04-a1'])
        for r in qs.values():
            for role in r['claim_roles']:
                if role['role']=='required':self.assertTrue(role['intent_ids'])
                else:self.assertEqual(role['intent_ids'],[])
            self.assertNotIn('answer_span',r)
        for q in self.packet['questions'][-2:]:
            self.assertEqual(q['answer_rubric']['required_answer'],'')
            self.assertEqual(q['codex_source_checked']['claims'],[])
            self.assertIn('명시되어 있지 않습니다',q['codex_source_checked']['answer'])

    def test_historical_five_approvals_never_become_blanket_approval(self):
        history=self.packet['prior_human_claim_reviews']
        self.assertEqual([h['claim']['id'] for h in history],['gt01-c02-a1','gt01-c02-a2','gt01-c02-a3','gt01-c04-a1','gt01-c04-a2'])
        old={c['id']:c for c in self.old['questions'][0]['codex_source_checked']['claims']}
        for h in history:
            self.assertEqual(h['parent_packet_sha256'],scoped.PARENT_SHA)
            self.assertEqual(h['claim'],old[h['claim']['id']])
            self.assertEqual(h['status'],'explicit_human_approval_on_parent_only')
        self.assertIsNone(self.packet['human_approval'])
        for q in self.packet['questions']+self.packet['judgements']:self.assertIsNone(q['human_approval'])
        self.assertIsNone(self.mapping['human_approval'])
        self.assertEqual(self.packet['new_model_requests'],0)

    def test_fixed_examples_preserve_policy_without_running_an_evaluator(self):
        examples={r[0]:r[1:] for r in scoped.expected_examples(self.policy)}
        self.assertEqual(len(examples),10)
        self.assertEqual(examples['core_plus_optional'][1:3],['6/6/6','1/1/1'])
        self.assertEqual(examples['missing_probation'][1:3],['5/6/5','1,5/6,10/11'])
        self.assertEqual(examples['wrong_deadline'][1:3],['6/6/5','5/6,5/6,5/6'])
        self.assertIn('additional_factual_error',examples['wrong_optional'][-1])
        self.assertIn('review_required',examples['unknown_extra'][-1])
        self.assertEqual(examples['optional_only'][1:3],['0/6/0','null,0,0'])
        self.assertIn('필수/보충/추가 생성 사실 전체',self.policy)
        self.assertEqual(hashlib.sha256(POLICY.read_bytes()).hexdigest(),scoped.POLICY_SHA)

    def test_html_order_reason_visible_quotes_collapsed_logs_and_json(self):
        text=scoped.render(self.packet,self.mapping,self.policy);dom=Structure();dom.feed(text)
        self.assertEqual(dom.quotes,57+18)
        self.assertEqual(dom.details,84)
        self.assertIn('필수 38개 / 보충 19개',text)
        self.assertIn('미명시 후보 2개',text)
        self.assertIn('핵심 점수가 만점이어도 답변 전체가 정답이라는 뜻은 아닙니다',text)
        self.assertIn('고정 기대 예시 10개 — 실제 모델 결과 아님',text)
        for q in self.packet['questions'][:8]:
            ident=q['id'];a=text.index('id="'+ident+'-required"');b=text.index('id="'+ident+'-supplementary"')
            self.assertLess(a,b)
            for role in q['answer_rubric']['claim_roles']:
                self.assertIn(role['claim_id'],dom.ids)
                self.assertIn(role['reason'],text)
        self.assertIn('scoring-policy.md',dom.links)
        self.assertIn('../run003/review.html',dom.links)
        embedded=text.split('<script type="application/json" id="packet">')[1].split('</script>')[0]
        self.assertEqual(json.loads(embedded),self.packet)
        bad=copy.deepcopy(self.packet);attack='</script><img src=x onerror=bad>&'
        bad['questions'][0]['codex_source_checked']['claims'][0]['source']['quote']=attack
        rendered=scoped.render(bad,self.mapping,self.policy)
        self.assertNotIn(attack,rendered);self.assertIn('&lt;img src=x onerror=bad&gt;&amp;',rendered)

    def test_bad_classification_or_derived_answer_is_rejected(self):
        cases=[('required_claim_ids',[]),('required_answer','wrong'),('intents',[])]
        for key,value in cases:
            p=copy.deepcopy(self.packet);p['questions'][0]['answer_rubric'][key]=value
            p['packet_sha256']=digest({k:v for k,v in p.items() if k!='packet_sha256'})
            with self.assertRaises(ValueError):scoped.validate(p,self.mapping,self.old,self.audit)
        p=copy.deepcopy(self.packet);p['prior_human_claim_reviews'].append(copy.deepcopy(p['prior_human_claim_reviews'][0]))
        p['packet_sha256']=digest({k:v for k,v in p.items() if k!='packet_sha256'})
        with self.assertRaisesRegex(ValueError,'approval boundary'):scoped.validate(p,self.mapping,self.old,self.audit)

    def test_corrupt_inputs_fail_before_output_and_do_not_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp)
            for name in ['run001','run002','run003']:shutil.copytree(ROOT/'artifacts'/name,base/name)
            before={n:scoped.inventory(base/n) for n in ['run001','run002','run003']}
            audit=base/'audit.json';policy=base/'policy.md'
            audit.write_bytes(AUDIT.read_bytes());policy.write_bytes(POLICY.read_bytes())
            for path in [audit,policy]:
                good=path.read_bytes();path.write_bytes(good+b' ')
                with patch('socket.socket',side_effect=AssertionError('network')):
                    with self.assertRaises(ValueError):scoped.create(base/'run003',audit,policy,base/'run004')
                self.assertFalse((base/'run004').exists());path.write_bytes(good)
            with patch('socket.socket',side_effect=AssertionError('network')):
                scoped.create(base/'run003',audit,policy,base/'run004')
                scoped.create(base/'run003',audit,policy,base/'run004')
                self.assertEqual(scoped.verify(base/'run004'),self.packet)
            for name in before:self.assertEqual(scoped.inventory(base/name),before[name])
            parent_packet=base/'run003/packet.json';saved=parent_packet.read_bytes()
            broken=read(parent_packet);broken['questions'][0]['question']='tampered';write(parent_packet,broken)
            changed_parent=file_hash(parent_packet)
            with self.assertRaises(ValueError):scoped.create(base/'run003',audit,policy,base/'run004-bad-parent')
            self.assertFalse((base/'run004-bad-parent').exists())
            self.assertEqual(file_hash(parent_packet),changed_parent)
            parent_packet.write_bytes(saved)
            path=base/'run004/scope-mapping.json';path.write_text('{}');changed=file_hash(path)
            with self.assertRaises(ValueError):scoped.create(base/'run003',audit,policy,base/'run004')
            self.assertEqual(file_hash(path),changed)
            with self.assertRaises(ValueError):scoped.create(base/'run003',audit,policy,base/'run003')

    def test_unknown_version_schema_and_model_path_fail_before_network(self):
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)/'run004';out.mkdir()
            for version,schema in [('unknown',3),('p023-core-supplement-v1',2),(None,3)]:
                p=copy.deepcopy(self.packet);p['review_version']=version;p['schema_version']=schema;write(out/'packet.json',p)
                r=subprocess.run([sys.executable,'-B',str(ROOT/'prepare.py'),'run','--out',str(out)],capture_output=True,text=True)
                self.assertNotEqual(r.returncode,0);self.assertRegex(r.stderr,'review_version|schema/version')
            write(out/'packet.json',self.packet)
            for name in ['run','revise-ground']:
                r=subprocess.run([sys.executable,'-B',str(ROOT/'prepare.py'),name,'--out',str(out)],capture_output=True,text=True)
                self.assertNotEqual(r.returncode,0);self.assertIn('offline only',r.stderr)
                self.assertFalse((out/'ledger.json').exists())

    def test_saved_html_policy_and_manifest_tamper_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp)
            for name in ['run001','run002','run003','run004']:shutil.copytree(ROOT/'artifacts'/name,base/name)
            for name in ['review.html','scoring-policy.md','packet-manifest.json']:
                path=base/'run004'/name;good=path.read_bytes();path.write_text('{}' if name.endswith('json') else 'changed')
                with self.assertRaises(ValueError):scoped.verify(base/'run004')
                path.write_bytes(good)
            self.assertEqual(scoped.verify(base/'run004'),self.packet)


if __name__=='__main__':unittest.main()
