#!/usr/bin/env python3
"""Loopback learning UI sharing immutable chunk/retrieval cores with CLI."""
import argparse,io,json,re,threading,time,zipfile
from pathlib import Path
from http.server import ThreadingHTTPServer,BaseHTTPRequestHandler
from urllib.parse import urlsplit,parse_qs
from document_common import STAGE,read_json,file_hash,fingerprint
from experiment_common import EXP,RUNTIME,ARTIFACTS,need,ExperimentError,source,spec,config,load_run,work_lock,new_id,save_state,strict,code_hash
from chunk_core import build
from run_llm_repetitions import one
from model_runtime import Provider,Ledger
from retrieval_core import build_index,Searcher,read_chunks,identity
from span_metrics import evaluate,select_budget
from source_io import union_length
from chunk_settings import LIMITS,custom
CORPUS='source-v4';DID='hr-v4-handbook'
JOBS=RUNTIME/'jobs';request_mutex=threading.Lock()

def registered_run(rid):
    need(isinstance(rid,str) and re.fullmatch(r'chunk-[a-f0-9]{32}',rid),'not_found','등록되지 않은 실행입니다.')
    path=ARTIFACTS/rid
    need(path.is_dir() and not path.is_symlink(),'not_found','실행 결과가 없습니다.')
    return path

def catalog():
    result=[];canon=spec()['corpus']['canonical_sha256']
    for p in sorted(ARTIFACTS.glob('chunk-*/manifest.json'),key=lambda p:p.stat().st_mtime):
        if p.parent.is_symlink():continue
        try:
            m=load_run(p.parent)
            need(m.get('run_id')==p.parent.name and m.get('canonical_sha256')==canon and m.get('text_version')=='canonical-slice-only-v1','stale','Incompatible run')
            cfg=config(m['config'])
            indexes={}
            for retriever in ('bm25','dense'):
                meta,fp,*_=identity(p.parent,retriever);index=RUNTIME/'indexes'/fp/'metadata.json'
                indexes[retriever]=index.is_file() and read_json(index).get('identity')==meta
            result.append({k:m.get(k) for k in ['run_id','status','config','counts','elapsed_ms']}|dict(created_at=m.get('created_at',p.stat().st_mtime),origin='사용자 설정' if custom(cfg) else 'P007 고정 실험',indexes=indexes))
        except (ValueError,OSError,KeyError,TypeError):continue
    return result

def replay(cfg):
    rows=[m for m in catalog() if m['status']=='complete' and m['config']==cfg]
    if custom(cfg):
        compatible=[]
        for row in rows:
            m=load_run(registered_run(row['run_id']))
            if m.get('code_hash')!=code_hash(['chunk_core.py','source_io.py','experiment_common.py','model_runtime.py','chunk_settings.py']):continue
            if any(m.get(key)!=file_hash(EXP/name) for key,name in [('spec_sha256','spec.json'),('prompt_sha256','prompt-contract.json'),('runtime_lock_sha256','runtime-metadata.json')]):continue
            if cfg['method']=='llm' and m.get('effective_prompt_sha256')!=fingerprint(read_json(EXP/'prompt-contract.json')['prefix'].replace('<=800 source characters',f"<={cfg['base_max_chars']} source characters")):continue
            compatible.append(row)
        rows=compatible
    need(rows,'not_found','저장 결과가 없습니다. 새로 실행을 선택하세요.')
    path=registered_run(rows[-1]['run_id']);load_run(path);return path

def compact_progress(v):
    return {k:v[k] for k in ['run_id','completed_windows','total_windows','elapsed_seconds'] if k in v}|{'attempts':sum(len(r['attempts']) for r in v.get('records',[]))}

def restart_jobs():
    JOBS.mkdir(parents=True,exist_ok=True)
    for p in JOBS.glob('*.json'):
        v=read_json(p)
        if v['status'] in ('QUEUED','RUNNING'):
            v.update(status='INTERRUPTED',reason='server_restart',message='서버 재시작으로 중단됐습니다. 자동 재실행하지 않습니다.');save_state(p,v)

def check_body(body,fields):
    need(isinstance(body,dict) and set(body)==set(fields),'invalid_input','요청 필드가 올바르지 않습니다.')

def start_job(kind,b):
    check_body(b,['corpus_id','config','request_id','fresh'] if kind=='chunk' else ['chunk_run_id','retriever','request_id'])
    req=b['request_id'];need(isinstance(req,str) and re.fullmatch(r'[A-Za-z0-9_-]{8,100}',req),'invalid_input','request_id 형식 오류')
    if kind=='chunk':
        need(b['corpus_id']==CORPUS,'stale','원문 버전이 다릅니다.');cfg=config(b['config']);need(type(b['fresh']) is bool,'invalid_input','fresh는 명시적인 bool이어야 합니다.')
    else:
        registered_run(b['chunk_run_id']);need(b['retriever'] in ('bm25','dense'),'invalid_config','검색기를 확인하세요.')
    with request_mutex:
        for p in JOBS.glob('*.json'):
            old=read_json(p)
            if old['request_id']==req:
                need(old['request_hash']==fingerprint(b),'conflict','같은 request_id의 내용이 달라졌습니다.');return old
        jid=new_id('job');p=JOBS/(jid+'.json');v=dict(job_id=jid,request_id=req,request_hash=fingerprint(b),status='QUEUED',kind=kind,created_at=time.time(),request=b,progress={},result=None)
        ready=threading.Event();admission=[]
        def execute():
            try:
                with work_lock():
                    save_state(p,v);v.update(status='RUNNING',started_at=time.time());save_state(p,v);ready.set()
                    before=Ledger().refresh()
                    def progress(value):v['progress']=compact_progress(value);save_state(p,v)
                    if kind=='chunk':
                        if not b['fresh']:
                            out=replay(cfg);m=load_run(out);result=dict(run_id=m['run_id'],replayed=True,model_calls=0)
                        elif cfg['method']=='llm':
                            m=one(progress=progress,cfg=cfg);result=dict(run_id=m['run_id'],replayed=False)
                        else:
                            parent=None  # Explicit fresh means new boundaries; replay is a separate action.
                            m=build(cfg,parent=parent,on_progress=progress);result=dict(run_id=m['run_id'],replayed=False,boundary_replayed=bool(parent))
                    else:result=build_index(registered_run(b['chunk_run_id']),b['retriever'])
                    after=Ledger().refresh();result['usage_delta']={k:after[k]-before[k] for k in ['llm_requests','embedding_items','llm_seconds','embedding_seconds']}
                    v.update(status='SUCCEEDED',result=result,finished_at=time.time());save_state(p,v)
            except Exception as e:
                if not ready.is_set():admission.append(e)
                else:
                    v.update(status='FAILED',reason=getattr(e,'kind','execution'),message=str(e),finished_at=time.time());save_state(p,v)
            finally:ready.set()
        threading.Thread(target=execute,daemon=True).start();ready.wait(5)
        if admission:raise admission[0]
        need(ready.is_set(),'busy','작업 잠금을 확인 중입니다.')
        return read_json(p)

def compare(b):
    common={'a_run_id','b_run_id','retriever','top_k','budget_chars'}
    need(isinstance(b,dict) and set(b) in (common|{'question'},common|{'query_id'}),'invalid_input','question 또는 query_id 하나를 지정하세요.')
    need(type(b['top_k']) is int and 1<=b['top_k']<=20 and type(b['budget_chars']) is int and 1<=b['budget_chars']<=LIMITS['budget_chars']['maximum'],'invalid_input','Top-K는 1~20, 문자 예산은 1~24,000의 정수로 입력하세요.')
    q=None;dataset=read_json(EXP/'dataset.json')
    if 'query_id' in b:
        q=next((q for q in dataset['questions'] if q['query_id']==b['query_id']),None);need(q,'not_found','등록 질문이 없습니다.')
        need(q['split']=='tuning','invalid_input','holdout은 동결 후 CLI 확인 실험에서만 실행합니다.');question=q['question']
    else:question=b['question']
    need(isinstance(question,str) and question.strip() and len(question)<=2000,'invalid_input','질문은 1~2000자입니다.')
    with work_lock():
        available={m['run_id'] for m in catalog()}
        need(all(b[k] in available for k in ('a_run_id','b_run_id')),'not_found','성공한 저장 이력에서 A/B를 선택하세요.')
        paths=[registered_run(b[k]) for k in ('a_run_id','b_run_id')]
        for path in paths:
            _,fp,*_=identity(path,b['retriever']);need((RUNTIME/'indexes'/fp/'metadata.json').exists(),'index_not_ready','먼저 해당 검색기 색인을 준비하세요.')
        vector=None;embedding=None
        if b['retriever']=='dense':vectors,embedding=Provider().embed([question]);vector=vectors[0]
        row,text,_=source();facts={f['fact_id']:f for f in dataset['facts']};out=[]
        for path in paths:
            with Searcher(path,b['retriever']) as search:
                ranking=search.search(question,20,vector,Ledger());ids=[r['chunk_id'] for r in ranking['results']]
                metrics=evaluate(q,facts,search.maps,ids,b['top_k'],{DID:text});metrics.pop('qrels',None)
                budget=select_budget(ids,search.chunks,b['budget_chars']);budget['candidate_count']=len(ids);budget['metrics']=evaluate(q,facts,search.maps,budget['selected'],max(1,len(budget['selected'])),{DID:text});budget['metrics'].pop('qrels',None)
                lookup={m['chunk_id']:m for m in search.maps}
                top=ids[:b['top_k']];emitted=sum(len(search.chunks[cid]['text']) for cid in top);unique=union_length([(lookup[cid]['start'],lookup[cid]['end']) for cid in top])
                budget['hits']=[dict(chunk_id=cid,text=search.chunks[cid]['text'],rank=ids.index(cid)+1,source=lookup[cid]) for cid in budget['selected']]
                out.append(dict(ranking=ranking,metrics=metrics,budget=budget,retrieved_text=dict(emitted_chars=emitted,unique_chars=unique,duplicate_chars=emitted-unique),hits=[dict(**r,text=search.chunks[r['chunk_id']]['text'],source=lookup[r['chunk_id']]) for r in ranking['results'][:b['top_k']]]))
        value=dict(comparison_id=new_id('comparison'),question=question,query_id=q['query_id'] if q else None,split=q['split'] if q else None,corpus_id=CORPUS,top_k=b['top_k'],budget_chars=b['budget_chars'],retriever=b['retriever'],embedding=embedding,results=out,dataset_sha256=file_hash(EXP/'dataset.json'))
        save_state(RUNTIME/'comparisons'/(value['comparison_id']+'.json'),value);return value

class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def send(self,status,data,ctype='application/json',download=None):
        raw=json.dumps(data,ensure_ascii=False,allow_nan=False).encode() if ctype=='application/json' else data
        self.send_response(status);self.send_header('Content-Type',ctype);self.send_header('Content-Length',str(len(raw)));self.send_header('X-Content-Type-Options','nosniff');self.send_header('Cache-Control','no-store')
        self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'")
        if download:self.send_header('Content-Disposition','attachment; filename="'+download+'"')
        self.end_headers();self.wfile.write(raw)
    def secure(self):
        host=f'127.0.0.1:{self.server.server_port}';need(self.headers.get('Host')==host,'forbidden','Loopback Host만 허용합니다.')
        need(self.headers.get('Origin') in (None,'http://'+host),'forbidden','다른 Origin은 허용하지 않습니다.')
    def file(self,p,ctype,digest=None,download=None):
        need(p.is_file() and not any(x.is_symlink() for x in [p,*p.parents]),'not_found','등록 파일이 없습니다.')
        if digest:need(file_hash(p)==digest,'stale','등록 파일의 hash가 다릅니다.')
        self.send(200,p.read_bytes(),ctype,download)
    def dispatch(self,post=False):
        try:
            self.secure();url=urlsplit(self.path);path=url.path
            need('%' not in path and '..' not in path and '\\' not in path,'not_found','잘못된 경로입니다.')
            if post:
                need(self.headers.get('Content-Type','').split(';')[0]=='application/json','invalid_input','JSON만 허용합니다.')
                length=int(self.headers.get('Content-Length','0'));need(0<length<=65536,'too_large' if length>65536 else 'invalid_input','JSON 최대 크기는 64KiB입니다.')
                b=strict(self.rfile.read(length).decode());
                if path in ('/api/chunk-jobs','/api/index-jobs'):return self.send(202,start_job('chunk' if path=='/api/chunk-jobs' else 'index',b))
                if path=='/api/search-comparisons':return self.send(200,dict(status='complete',data=compare(b)))
                raise ExperimentError('not_found','등록 API가 없습니다.')
            if path=='/api/corpora':
                row,_,_=source();dataset=read_json(EXP/'dataset.json')
                return self.send(200,dict(status='complete',corpus_id=CORPUS,document_id=DID,title=row['title'],canonical_sha256=row['canonical_sha256'],synthetic=True,source_mode='fixture',configs=spec()['configs'],input_limits=LIMITS,runs=catalog(),questions=[{k:q[k] for k in ('query_id','question','split')} for q in dataset['questions'] if q['split']=='tuning'],ledger={k:v for k,v in Ledger().refresh().items() if k not in ('calls','pending')},jobs=[read_json(p) for p in sorted(JOBS.glob('*.json'))]))
            if path==f'/api/documents/{DID}':
                need(parse_qs(url.query)=={'corpus_id':[CORPUS]},'invalid_input','corpus_id가 필요합니다.');r,t,s=source()
                nodes=[dict(id=n['id'],level=n['level'],title_path=n['title_path'],start=n['heading']['start'],pages=n['heading']['pages']) for n in s['nodes']]
                return self.send(200,dict(document_id=DID,text=t,pages=r['pages'],sections=nodes,canonical_sha256=r['canonical_sha256']))
            if path==f'/api/documents/{DID}/pdf':
                row,_,_=source();return self.file(STAGE/'data/source-v4/output/pdf/hr-handbook.pdf','application/pdf',row['original_sha256'],'hr-handbook.pdf')
            match=re.fullmatch(f'/api/documents/{DID}/pages/([0-9]+)/preview',path)
            if match:
                n=int(match[1]);need(1<=n<=23,'not_found','페이지 범위 오류')
                digest=next(r['sha256'] for r in read_json(EXP/'preview-manifest.json')['files'] if r['page']==n)
                return self.file(STAGE/'previews/source-v4'/f'page-{n:02d}.png','image/png',digest)
            match=re.fullmatch('/api/jobs/(job-[a-f0-9]{32})',path)
            if match:
                p=JOBS/(match[1]+'.json');need(p.is_file(),'not_found','작업이 없습니다.');return self.send(200,read_json(p))
            match=re.fullmatch('/api/runs/(chunk-[a-f0-9]{32})(/export)?',path)
            if match:
                p=registered_run(match[1]);m=load_run(p)
                if match[2]:
                    buffer=io.BytesIO()
                    with zipfile.ZipFile(buffer,'w',zipfile.ZIP_DEFLATED) as z:
                        for name in ['manifest.json',*m['outputs']]:
                            need('/' not in name and not (p/name).is_symlink(),'stale','잘못된 산출물 경로');z.writestr(name,(p/name).read_bytes())
                    return self.send(200,buffer.getvalue(),'application/zip',m['run_id']+'.zip')
                _,chunks,maps=read_chunks(p);return self.send(200,dict(manifest=m,statistics=read_json(p/'statistics.json'),chunks=list(chunks.values()),source_map=maps,indexes={r:(RUNTIME/'indexes'/identity(p,r)[1]/'metadata.json').exists() for r in ('bm25','dense')}))
            static={'/':('index.html','text/html; charset=utf-8'),'/app.js':('app.js','text/javascript; charset=utf-8'),'/style.css':('style.css','text/css; charset=utf-8'),'/base.css':('base.css','text/css; charset=utf-8')}
            need(path in static,'not_found','등록 경로가 없습니다.');name,ctype=static[path];return self.file(STAGE/'web_chunking'/name,ctype)
        except (Exception,) as e:
            kind=getattr(e,'kind','invalid_input' if isinstance(e,(ValueError,KeyError,TypeError)) else 'execution')
            status={'not_found':404,'busy':409,'conflict':409,'stale':409,'index_not_ready':409,'too_large':413,'forbidden':403,'invalid_config':422,'runtime_mismatch':422,'execution':500}.get(kind,400)
            self.send(status,dict(status='error',reason=kind,message=str(e)))
    def do_GET(self):self.dispatch()
    def do_POST(self):self.dispatch(True)

def main():
    p=argparse.ArgumentParser();p.add_argument('--port',type=int,default=8003);a=p.parse_args();source();restart_jobs()
    server=ThreadingHTTPServer(('127.0.0.1',a.port),Handler);print(f'Chunking UI http://127.0.0.1:{a.port}',flush=True);server.serve_forever()
if __name__=='__main__':main()
