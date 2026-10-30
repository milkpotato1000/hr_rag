import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import core
from core import read, write, digest
import fixtures
import prepare
import runner


class PreparationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.out = Path(self.tmp.name)
        self.case = fixtures.smokes()[1]; self.case['payload'] = core.payload(self.case)
        self.case['payload_sha256'] = digest(self.case['payload'])
        self.lock = dict(digest=core.DIGEST, template='{{ .Content }}', tokenizer_verified=True,
                         single_user_template_verified=True)
        canonical = '원문입니다.'
        files = {
            'inputs.json': dict(canonical_sha256=hashlib.sha256(canonical.encode()).hexdigest(), questions=[]),
            'source/section-map.json': dict(nodes=[]), 'cases.json': [self.case],
            'model-lock.json': self.lock, 'preflight.json': dict(passed=True)}
        for name, value in files.items(): write(self.out / name, value)
        p = self.out / 'source/extracted/canonical/hr-v4-handbook.txt'; p.parent.mkdir(parents=True);p.write_text(canonical)
        names = list(files) + ['source/extracted/canonical/hr-v4-handbook.txt']
        frozen = dict(files={n: core.file_hash(self.out/n) for n in names}, human_approval=None)
        frozen['sha256'] = digest(frozen); write(self.out/'frozen.json', frozen)
        self.ledger = runner.Ledger(self.out, frozen['sha256'])

    def test_source_tamper_and_truncation_fail(self):
        prepare.verify_frozen(self.out)
        p=self.out/'source/extracted/canonical/hr-v4-handbook.txt';p.write_text(p.read_text()[:-1])
        with self.assertRaisesRegex(ValueError, 'changed'): prepare.verify_frozen(self.out)

    def test_unknown_id_mismatch_duplicate_quote(self):
        case=fixtures.smokes()[0]
        good={'claims':[dict(unit_id='s1',quote=case['expected_quotes'][0])]}
        core.validate_output(case,good)
        for bad in [dict(claims=[dict(unit_id='missing',quote=case['expected_quotes'][0])]),
                    dict(claims=[dict(unit_id='s1',quote='없는 인용')]),
                    dict(claims=good['claims']*2)]:
            with self.assertRaises(ValueError): core.validate_output(case,bad)
        with self.assertRaises(ValueError): core.locate('동일 동일','동일')

    def test_exact_offsets_and_answer_provenance(self):
        case=fixtures.smokes()[-1];quote='수습 중인 직원은 대상에서 제외한다.'
        value=dict(answer='수습 직원은 제외합니다.',claims=[dict(answer_quote='수습 직원은 제외합니다.',unit_id='s1',source_quote=quote)])
        row=core.validate_output(case,value)[0];a,b=row['source_local_span']
        self.assertEqual(case['units'][0]['text'][a:b],quote)
        value['claims'][0]['answer_quote']='추가되지 않은 답변'
        with self.assertRaises(ValueError): core.validate_output(case,value)

    def test_extra_fields_and_wrong_types_rejected(self):
        for value in [dict(label='E',unit_id='s1',premise_quote='원문',claim_quote='주장',reason='이유',approved=True),
                      dict(label='unknown',unit_id='s1',premise_quote='원문',claim_quote='주장',reason='이유')]:
            with self.assertRaises(ValueError): core.validate(value,core.VERIFY)

    def test_byte_bound_and_template_gate(self):
        body=self.case['payload'];self.assertLess(core.preflight(body,self.lock)['upper_bound'],8192)
        bad=copy.deepcopy(body);bad['messages'][0]['content']='한'*3000
        with self.assertRaisesRegex(ValueError,'budget'):core.preflight(bad,self.lock)
        with self.assertRaisesRegex(ValueError,'unverified'):core.preflight(body,dict(self.lock,single_user_template_verified=False))
        bad=copy.deepcopy(body);bad['options']['num_ctx']=16384
        with self.assertRaises(ValueError):core.preflight(bad,self.lock)

    def test_pending_restart_and_retry_limits(self):
        event,_=self.ledger.reserve('one',self.case['payload'],False)
        reloaded=runner.Ledger(self.out,self.ledger.frozen)
        with self.assertRaisesRegex(ValueError,'unresolved'):reloaded.reserve('two',self.case['payload'],False)
        self.ledger.finish(event,dict(status='failed',seconds=1))
        event,_=reloaded.reserve('one',self.case['payload'],False);reloaded.finish(event,dict(status='failed',seconds=1))
        with self.assertRaisesRegex(ValueError,'retry'):reloaded.reserve('one',self.case['payload'],False)

    def test_cumulative_cap_duplicate_and_artifact_tamper(self):
        for i in range(34):
            event,_=self.ledger.reserve(str(i),self.case['payload'],False)
            self.ledger.finish(event,dict(status='valid',seconds=1))
        with self.assertRaisesRegex(ValueError,'budget'):self.ledger.reserve('35',self.case['payload'],False)
        s=read(self.ledger.path);s['calls'][0]['id']=2;write(self.ledger.path,s)
        with self.assertRaisesRegex(ValueError,'duplicate'):self.ledger.state()

    def test_wall_time_cap(self):
        s=read(self.ledger.path);s['seconds']=2700;write(self.ledger.path,s)
        with self.assertRaisesRegex(ValueError,'budget'):self.ledger.reserve('one',self.case['payload'],False)

    def test_category_cap_includes_failed_attempts(self):
        for i in range(12):
            e,_=self.ledger.reserve('smoke-'+str(i),self.case['payload'],False)
            self.ledger.finish(e,dict(status='failed',seconds=1))
        with self.assertRaisesRegex(ValueError,'category'):self.ledger.reserve('smoke-new',self.case['payload'],False)

    def test_recorded_artifact_tamper_and_repeat_retry(self):
        e,_=self.ledger.reserve('repeat-one',self.case['payload'],True)
        self.ledger.finish(e,dict(status='valid',seconds=1))
        with self.assertRaisesRegex(ValueError,'retry'):self.ledger.reserve('repeat-one',self.case['payload'],True)
        write(self.out/'calls/001.json',dict(status='valid',seconds=0))
        with self.assertRaisesRegex(ValueError,'artifact changed'):self.ledger.state()

    @patch('runner.sample_memory')
    @patch('runner.verify_runtime')
    def test_timeout_saved_and_blocks_next_call(self,*mocks):
        with patch('runner.http',side_effect=TimeoutError('fixture timeout')):
            with self.assertRaisesRegex(ValueError,'unresolved'):runner.invoke(self.out,self.ledger,self.case,'timeout')
        self.assertTrue(self.ledger.state()['unresolved'])
        self.assertIn('fixture timeout',read(self.out/'calls/001.json')['error'])
        with self.assertRaises(ValueError):self.ledger.reserve('next',self.case['payload'],False)

    @patch('runner.sample_memory')
    @patch('runner.verify_runtime')
    def test_partial_response_is_not_success(self,*mocks):
        response=dict(model=core.MODEL,done=True,done_reason='length',message={'content':'{unfinished'})
        with patch('runner.http',return_value=response):r=runner.invoke(self.out,self.ledger,self.case,'partial')
        self.assertEqual(r['status'],'failed');self.assertIn('partial',r['error'])
        self.assertEqual(r['raw_response'],response)

    def test_semantics_separate_from_format(self):
        self.assertFalse(runner.semantic(self.case,{'label':'C'}))
        self.assertTrue(runner.semantic(self.case,{'label':'E'}))

    def test_approval_cannot_be_fabricated(self):
        rows=[dict(id=str(i),status='draft',reviewer='Codex',human_approval=None) for i in range(10)]
        packet=dict(status='draft',human_approval=None,questions=rows,judgements=fixtures.judgements());packet['packet_sha256']=digest(packet)
        core.validate_review_packet(packet)
        packet['questions'][0]['status']='approved';packet['packet_sha256']=digest({k:v for k,v in packet.items() if k!='packet_sha256'})
        with self.assertRaisesRegex(ValueError,'unapproved'):core.validate_review_packet(packet)

    def test_prompt_revision_preserves_inputs_and_cumulative_ledger(self):
        # Ground revision does not reset previously consumed calls/time.
        case=fixtures.smokes()[-1];case['payload']=core.payload(case);case['payload_sha256']=digest(case['payload'])
        write(self.out/'cases.json',[case]);f=read(self.out/'frozen.json');f['files']['cases.json']=core.file_hash(self.out/'cases.json');f['sha256']=digest({k:v for k,v in f.items() if k!='sha256'});write(self.out/'frozen.json',f)
        s=read(self.ledger.path);s['frozen_sha256']=f['sha256'];write(self.ledger.path,s)
        self.ledger=runner.Ledger(self.out,f['sha256'])
        e,_=self.ledger.reserve('old',case['payload'],False);self.ledger.finish(e,dict(status='failed',seconds=10))
        prepare.revise_ground(self.out);active=prepare.active_cases(self.out)
        self.assertEqual(len(self.ledger.state()['calls']),1);self.assertEqual(self.ledger.state()['seconds'],10)
        self.assertEqual(active[0]['units'],case['units']);self.assertEqual(active[0]['question'],case['question'])
        self.assertNotEqual(active[0]['payload_sha256'],case['payload_sha256'])

    def test_json_report_roundtrip_and_tamper(self):
        import report
        row=dict(id='gt09',question='금액?',status='needs_revision',reviewer='Codex',human_approval=None,
                 source_spans=[],codex_source_checked=dict(answer='문서에 명시되지 않았습니다.',claims=[]),
                 model_original_attempts=[],revision={'method':'fixture'},human_review_points=['확인'])
        packet=dict(status='draft',human_approval=None,questions=[dict(row,id='gt%02d'%i) for i in range(1,11)],judgements=fixtures.judgements())
        packet['packet_sha256']=digest(packet)
        rendered=report.render(packet)
        import re
        embedded=json.loads(re.search(r'id="packet">(.*?)</script>',rendered,re.S)[1])
        self.assertEqual(packet,embedded);core.validate_review_packet(embedded)
        embedded['questions'][0]['question']='changed'
        with self.assertRaisesRegex(ValueError,'hash'):core.validate_review_packet(embedded)

    def test_runtime_parameter_order_only_is_ignored(self):
        lock=dict(template='test',parameters='stop "a"\nstop "b"\ntemperature 0.6',tokenizer={})
        responses=[{'version':'0.40.8'},{'models':[{'name':core.MODEL,'digest':core.DIGEST}]},
                   {'models':[]},{'template':'test','parameters':'temperature 0.6\nstop "a"\nstop "b"','model_info':{}}]
        with patch('runner.http',side_effect=responses):runner.verify_runtime(lock)
        responses[-1]=dict(responses[-1],parameters='temperature 0.7\nstop "a"\nstop "b"')
        with patch('runner.http',side_effect=responses):
            with self.assertRaises(ValueError):runner.verify_runtime(lock)


if __name__=='__main__':unittest.main()
