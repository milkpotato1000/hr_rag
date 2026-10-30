"""Isolated browser error fixtures only. Never points at the production stage."""
import argparse,sys
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--stage',type=Path,required=True);p.add_argument('--port',type=int,default=8004);a=p.parse_args()
assert 'p007-independent-' in str(a.stage)
sys.path.insert(0,str(a.stage/'scripts'))
import serve_chunking as s
from experiment_common import ExperimentError
original=s.start_job

def fixture_job(kind,body):
    if kind=='chunk':
        cfg=body.get('config',{}).get('id')
        if cfg=='fixed-200-0':raise ExperimentError('invalid_config','[독립 오류 fixture] 미지원 설정입니다.')
        if cfg=='fixed-400-0':raise ExperimentError('stale','[독립 오류 fixture] corpus/index 버전이 다릅니다.')
    return original(kind,body)
def provider_failure(*args,**kwargs):raise ExperimentError('provider','[독립 오류 fixture] 모델 응답 실패. 기존 성공 결과는 보존됩니다. 실제 모델은 호출하지 않았습니다.')
s.start_job=fixture_job;s.one=provider_failure
class FixtureHandler(s.Handler):
    def file(self,path,ctype,digest=None,download=None):
        if path.name=='index.html':return self.send(200,path.read_bytes().replace(b'<main>',b'<main><p>ISOLATED ERROR FIXTURE / NO MODEL INFERENCE</p>'),ctype)
        return super().file(path,ctype,digest,download)
s.restart_jobs();s.ThreadingHTTPServer(('127.0.0.1',a.port),FixtureHandler).serve_forever()
