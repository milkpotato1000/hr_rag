"""Run installed pipeline CLI; reserve each owned worker and the single real POST."""
from pathlib import Path
import sys,runpy
sys.path.insert(0,str(Path(__file__).resolve().parent))
from runtime import *
from rag_package import owned_worker,reranking,rag,llm
from rag_package.llm import core
from rag_package.__main__ import main
import rag_package

f=read(E/'frozen.json')
ws=Path(f['practice'])
os.chdir(ws)
need(Path(rag_package.__file__).is_relative_to(Path(f['python']).parents[1]),'wrong_package')
out=ws/'.rag-runs/pipeline-live'
qid='first'
ctl=runpy.run_path(str(ROOT/'docs/verification/p032-s1/live_control.py'))
class RetrievalControl(ctl['Control']):
    def before_spawn(self,command):
        sequence=['index','search','rerank']
        n=len(self.state['jobs'])
        stage=read(out/'pipeline.json')['active_stage']
        need(n<3 and sequence[n]==stage,'order_or_worker_cap')
        pairs=0
        if stage=='rerank':
            pairs=len(read(out/'candidates/candidates.json')['rows'])
            need(pairs==20,'pair_cap')
        self.begin(stage,'reranker_full' if pairs else 'embedding_full',pairs)
        self.start_clock()
        super().before_spawn(command)
    def after_worker(self,obs):
        super().after_worker(obs)
        need(self.current is not None and obs['resume_safe'] and obs['completed'] and obs['workers_started']==1,'incomplete_worker')
        self.current['status']='complete'
        self.state['active']=None
        self.current=None
        self.save()
path=E/'retrieval-ledger.json'
with path.open('x') as stream:
    json.dump(dict(status='ready',started_at=None,active=None,jobs=[],reservations={'embedding_full':0,'reranker_full':0},reranker_full_pairs=0),stream)
control=RetrievalControl(path)
original=core.http_transport
def http(method,url,headers,body,timeout):
    need(url.startswith(BASE+'/api/'),'external_endpoint')
    need(len(control.state['jobs'])==3 and control.current is None,'workers_must_finish')
    if method=='GET' and url==BASE+'/api/tags':
        return metadata('/api/tags',actor='adapter-first')
    need(method=='POST' and url==BASE+'/api/chat' and timeout==480,'unexpected_call')
    r,c,docs,_=reranking.load(out/'rerank')
    contexts=r['selection']['contexts']
    need(c['question']==f['rows'][0]['question'] and len(contexts)==5,'context_selection')
    messages=rag.messages_for(c['question'],contexts,docs)
    preview=llm.preview(read(E/'profile.json'),'generation',messages,response_schema=rag.answer_schema(contexts))
    expected=core.hash_json(preview['body'])
    write(E/'dispatch-context.json',dict(body_hash=expected,actual_messages_hash=preview['actual_messages_hash'],context_ids=[x['chunk_id'] for x in contexts]))
    with transact(LEDGER) as state:state.reserve(qid,core.hash_json(body),expected,read(E/'health.json'))
    raw=original(method,url,headers,body,timeout)
    with transact(LEDGER) as state:state.response(qid)
    return raw
core.http_transport=http
with owned_worker.execution_scope(control):
    code=main(f['cli_args']+['--out',str(out),'--execute'])
control.state['status']='complete' if code==0 else 'halted'
control.save()
raise SystemExit(code)
