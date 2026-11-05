import copy
import gzip
import json
import socket
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from evaluator import *
from freeze import ROOT, create, approval_check, make_cases
from execution import verify, Ledger, extraction_comparison, replay, run
from generation_export import validate as validate_export, from_langchain, source_review
from reporting import render
from cli import export_bundle
from tokenization import QwenTokenizer, pieces


class EvaluatorTests(unittest.TestCase):
    def assertSubset(self,expected,actual):
        for k,v in expected.items():
            if isinstance(v,float): self.assertAlmostEqual(v,actual[k],places=12,msg=k)
            else: self.assertEqual(v,actual[k],k)

    def test_18_independent_arithmetic_fixtures(self):
        fixtures=read(ROOT/'docs/planning/specs/P013-metric-fixtures-draft.json')['cases']
        self.assertEqual(len(fixtures),18)
        for c in fixtures:
            with self.subTest(c['id']):
                kind=c['metric']
                if kind=='faithfulness': got=faithful(c['claims'],c['labels'])
                elif kind=='correctness':
                    status='review_required' if c.get('reference_issue_claims') else 'incomplete' if c.get('indeterminate_edges') else None
                    got=correctness(c['generated'],c['reference'],c['equivalent_edges'],status)
                elif kind=='normalization': got=normalize(c['raw_generated'],c['confirmed_duplicate_groups'])
                else: got=aggregate(c['runs'],kind.removeprefix('aggregate_'))
                self.assertSubset(c['expected'],got)

    def test_scenarios_distinguish_context_and_answer_omission(self):
        s=read(ROOT/'docs/planning/specs/P013-evaluator-scenarios-draft.json')
        for c in s['cases']:
            f=faithful(c['generated_claim_ids'],[v['label'] for v in c['expected']['claim_verdicts']])
            self.assertSubset(c['expected']['faithfulness'],f)
            actual=correctness(c['generated_claim_ids'],c['reference_claim_ids'],c['expected']['correctness']['matched_edges'])
            expected={k:v for k,v in c['expected']['correctness'].items() if not k.startswith('unmatched')}
            self.assertSubset(expected,actual)
        self.assertEqual(s['cases'][0]['expected']['correctness'],s['cases'][1]['expected']['correctness'])

    def scoped(self,core_count=6,wrong=None,extra=None,scope='additional',uncertain=False,source=None):
        required=['r'+str(i) for i in range(6)];sup=['s'];refs=required+sup
        rubric=dict(required_claim_ids=required,supplementary_claim_ids=sup,intents=[dict(id='eligibility',required_claim_ids=required[:3])]+[dict(id=r,required_claim_ids=[r]) for r in required[3:]])
        claims=[dict(id='g'+str(i),text='fact'+str(i)) for i in range(core_count)];items=[]
        for i,g in enumerate(claims):
            items.append(dict(generated_id=g['id'],scope='core',reason='test',pairs=[dict(reference_id=r,label='uncertain' if uncertain and i==0 and r=='r0' else 'equivalent' if r=='r'+str(i) and i!=wrong else 'different',reason='test') for r in refs]))
        if extra:
            claims.append(dict(id='extra',text='extra'))
            items.append(dict(generated_id='extra',scope=scope,reason='test',pairs=[dict(reference_id=r,label='equivalent' if extra=='true' and r=='s' else 'different',reason='test') for r in refs]))
        return scoped_correctness(claims,rubric,dict(items=items),source)

    def test_policy_all_optional_missing_wrong_unknown_and_no_claims(self):
        self.assertEqual(self.scoped()['f1'],1)
        optional=self.scoped(extra='true');self.assertEqual(optional['f1'],1);self.assertEqual(optional['additional'][0]['status'],'accepted_supplement')
        missing=self.scoped(core_count=5);self.assertAlmostEqual(missing['f1'],10/11);self.assertEqual(missing['intent_coverage'],.75)
        wrong=self.scoped(wrong=5);self.assertAlmostEqual(wrong['f1'],5/6);self.assertEqual((wrong['fp'],wrong['fn']),(1,1))
        extra=self.scoped(extra='wrong',source={'extra':dict(status='source_contradicted')});self.assertEqual(extra['f1'],1);self.assertTrue(extra['additional_factual_error']);self.assertIsNone(extra['whole_answer_correct'])
        unknown=self.scoped(extra='new');self.assertEqual(unknown['f1'],1);self.assertTrue(unknown['review_required'])
        unknown_scope=self.scoped(extra='new',scope='unknown');self.assertIsNone(unknown_scope['f1'])
        only=self.scoped(core_count=0,extra='true');self.assertEqual(only['f1'],0);self.assertIsNone(only['precision'])
        empty=self.scoped(core_count=0);self.assertEqual(empty['f1'],0)
        self.assertIsNone(self.scoped(uncertain=True)['f1'])
        self.assertEqual(normalize(['a','b'],[['a','b']])['unique_claims'],1)

    def test_zero_reference_and_scope_conflict(self):
        empty=scoped_correctness([],dict(required_claim_ids=[],supplementary_claim_ids=[],intents=[]),dict(items=[]))
        self.assertEqual(empty['status'],'no_reference_claims');self.assertTrue(empty['answerability_review_required']);self.assertIsNone(empty['f1'])
        # A core error cannot be hidden as true optional merely by its text.
        x=self.scoped(extra='true',scope='core');self.assertEqual(x['fp'],1)

    def test_matching_maximum_and_lexicographic_tie(self):
        self.assertEqual(maximum_matching(['b','a'],['y','x'],[('a','x'),('a','y'),('b','x'),('b','y')]),[['a','x'],['b','y']])
        with self.assertRaises(ValueError): maximum_matching(['a'],['r'],[('a','wrong')])
        with self.assertRaises(ValueError): normalize(['a','b'],[['a','b'],['a','b']])

    def test_json_schema_and_span_failures(self):
        for text in ['{"a":1,"a":2}','{"a":NaN}','{"a":Infinity}']:
            with self.assertRaises(ValueError): loads(text)
        data=dict(question='질문',answer='가🙂 가🙂')
        value=dict(status='complete',claims=[dict(id='c1',text='가🙂',occurrences=[dict(quote='가🙂')])],reason='ok')
        got=resolve('extraction',data,value);self.assertEqual([(o['start'],o['end']) for o in got['claims'][0]['occurrences']],[(0,2),(3,5)])
        for mutate in [lambda v:v.update(extra=1),lambda v:v['claims'].append(v['claims'][0]),lambda v:v['claims'][0]['occurrences'][0].update(quote='absent')]:
            bad=copy.deepcopy(value);mutate(bad)
            with self.assertRaises(ValueError):resolve('extraction',data,bad)
        no=resolve('extraction',dict(question='q',answer='hello'),dict(status='complete',claims=[],reason='greeting'))
        self.assertEqual(no['status'],'no_claims')
        self.assertEqual(resolve('extraction',data,dict(status='incomplete',claims=[],reason='exceeded'))['status'],'incomplete')

    def test_judge_context_only_and_label_rules(self):
        data=dict(claims=[dict(id='c',text='5일')],contexts=[dict(id='ctx',text='최대 5일이다.')])
        v=dict(items=[dict(claim_id='c',status='complete',label='entailment',evidence=[dict(context_id='ctx',quote='5일')],reason='explicit')])
        self.assertEqual(resolve('judge',data,v)['items'][0]['evidence'][0]['spans'][0]['start'],3)
        for mutate in [lambda x:x['items'][0].update(evidence=[]),lambda x:x['items'][0].update(claim_id='wrong'),lambda x:x['items'][0]['evidence'][0].update(context_id='excluded'),lambda x:x['items'][0].update(label=None)]:
            bad=copy.deepcopy(v);mutate(bad)
            with self.assertRaises(ValueError):resolve('judge',data,bad)
        v['items'][0].update(label='neutral',evidence=[]);resolve('judge',data,v)

    def test_input_isolation_and_full_reference_comparison(self):
        with self.assertRaises(ValueError):payload('extraction',dict(question='q',answer='a',expected_claims=[]))
        data=dict(question='q',intents=[],reference=[dict(id='r',text='a')],claims=[dict(id='g',text='a')])
        with self.assertRaises(ValueError):resolve('matching',data,dict(items=[dict(generated_id='g',scope='core',reason='x',pairs=[])]))
        cases,expected=make_cases(ROOT,approval_check(ROOT)[1]);self.assertEqual(len(cases),84)
        for c in cases:
            if c['role']=='extraction':self.assertEqual(set(c['data']),{'question','answer'})

    def test_tokenizer_30_historical_counts(self):
        show=loads(gzip.decompress((ROOT/'docs/verification/p019/model-show.json.gz').read_bytes()).decode());t=QwenTokenizer(show['model_info'])
        calls=list((ROOT/'evaluation/project_b/preparation/artifacts/run001/calls').glob('*.json'));self.assertEqual(len(calls),30)
        for p in calls:
            c=read(p);self.assertEqual(t.count(c['payload']['messages']),c['raw_response']['prompt_eval_count'])
        for value in ['한글 123\n\nabc','hello   world',"we're\r\n🙂",' \n \tlast','a\u0301']:
            self.assertEqual(''.join(pieces(value)),value)

    def test_approved_bundle_offline_replay_and_tamper(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(socket,'socket',side_effect=AssertionError('network forbidden')):
            out=Path(tmp)/'run';create(out);verify(out/'manifest.json')
            r=replay(out);self.assertEqual(r['model_requests'],0)
            bundle=Path(tmp)/'bundle';export_bundle(out,bundle);self.assertEqual(replay(bundle),r)
            packet=out/'inputs/evaluation/project_b/preparation/artifacts/run004/packet.json';packet.write_text('{}')
            with self.assertRaises(ValueError):verify(out/'manifest.json')
            with self.assertRaises(ValueError):create(out)

    def test_ledger_retry_pending_integrity_and_downstream_gate(self):
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)/'run';m=create(out);ledger=Ledger(out,m['manifest_sha256']);case=read(out/'cases.json')[0]
            event,_=ledger.reserve(case)
            with self.assertRaises(ValueError):ledger.reserve(case)
            ledger.finish(event,dict(status='failed',seconds=1))
            with self.assertRaises(ValueError):ledger.reserve(case)
            (out/'calls/001.json').write_text('{}')
            with self.assertRaises(ValueError):ledger.state()
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)/'run';create(out)
            with patch('execution.http',side_effect=AssertionError('must not dispatch')):
                with self.assertRaisesRegex(ValueError,'S2'):run(out/'manifest.json','judge')
                with self.assertRaisesRegex(ValueError,'S2'):run(out/'manifest.json','e2e')

    def test_extraction_semantics_not_self_approved(self):
        expected=read(ROOT/'docs/planning/specs/P013-fixed-extraction-candidates.json')['cases'][0]
        claims=copy.deepcopy(expected['expected_claims']);result=dict(status='valid',resolved=dict(claims=claims))
        self.assertEqual(extraction_comparison({},expected,result)['status'],'pass')
        claims[0]['text']='의미상 비슷한 별도 표현'
        c=extraction_comparison({},expected,result);self.assertEqual(c['status'],'review_required');self.assertIsNone(c['f1'])

    def test_ledger_time_budget_and_unresolved_stop(self):
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)/'run';m=create(out);ledger=Ledger(out,m['manifest_sha256']);case=read(out/'cases.json')[0]
            state=ledger.state();state['started_at']=1;write(ledger.path,state,immutable=False)
            with self.assertRaisesRegex(ValueError,'wall cap'):ledger.reserve(case)
            state['started_at']=None;state['unresolved']=True;write(ledger.path,state,immutable=False)
            with self.assertRaisesRegex(ValueError,'unresolved'):ledger.reserve(case)

    def test_source_review_requires_version_and_exact_evidence(self):
        canonical='한도는 5일';claims=[dict(id='a',text='한도는 10일')]
        review=dict(schema_version='p013-source-review-v1',reviewer='human_project_owner',export_sha256='run',source_canonical_sha256=sha(canonical),user_statement='이 항목의 오류 확인',items=[dict(claim_id='a',status='source_contradicted',evidence=[dict(start=0,end=len(canonical),quote=canonical,quote_sha256=sha(canonical))])])
        self.assertEqual(source_review(review,'run',canonical,claims)['a']['status'],'source_contradicted')
        review['items'][0]['evidence'][0]['start']=1
        with self.assertRaises(ValueError):source_review(review,'run',canonical,claims)

    def test_generation_export_snapshot_validation(self):
        ctx=[dict(chunk_id='x',text='source')];messages=[dict(role='system',content='system'),dict(role='user',content=json.dumps(dict(question='q',contexts=ctx),ensure_ascii=False))]
        result=dict(status='answered',answer='a',citations=[],trace=dict(question='q',retriever='dense',settings=dict(top_k=5,max_context_chars=8000),candidates=ctx,contexts=ctx,excluded=[],prompt=dict(messages=messages,messages_sha256=sha(json.dumps(messages,ensure_ascii=False))),generation=dict(request={'format':{}},request_dispatched=True,digest='model',observations={'done_reason':'stop'}),validation=[]))
        identity=dict(run_id='r',question_id='q',code_commit='c',source_canonical_sha256='canonical',chunk_run_id='chunk',chunks_sha256='chunks',index_fingerprint='index')
        exported=from_langchain(result,identity);self.assertEqual(validate_export(exported),'generated_answer')
        bad=copy.deepcopy(exported);bad['trace']['contexts'][0]['text']='other'
        with self.assertRaises(ValueError):validate_export(bad)
        result['trace']['generation']['request_dispatched']=False
        with self.assertRaises(ValueError):from_langchain(result,identity)

    def test_html_escaping_and_no_fake_model_scores(self):
        r=dict(model_requests=0,actual_rag_evaluated=False,gates={},cases=[dict(case_id='x',role='extraction',data=dict(question='<script>bad</script>',answer='a'),comparison=dict(status='review_required'),seconds=0)])
        h=render(r);self.assertIn('&lt;script&gt;',h);self.assertNotIn('<script>bad',h);self.assertNotIn('<details open',h)


if __name__=='__main__':unittest.main()
