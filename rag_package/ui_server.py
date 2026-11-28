"""Loopback-only UI over the actual installed document RAG core."""
import json,secrets,socket,threading
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from importlib.resources import files
from urllib.parse import urlsplit,parse_qs,unquote_to_bytes
from .ui_registry import Registry,exact,decode,contained,preparation_summary
from .ui_jobs import Jobs
from .storage import RagError,require,read_json,safe_path
from .llm.config import ValidationError
from .documents import load_snapshot

STATIC={'/':'index.html','/app.js':'app.js','/style.css':'style.css'}
MIME={'index.html':'text/html; charset=utf-8','app.js':'text/javascript; charset=utf-8','style.css':'text/css; charset=utf-8'}

def error_status(code):
    if code in ('busy',):return 429
    if code in ('origin_denied','host_denied','session_denied','model_execution_disabled','drive_download_disabled'):return 403
    if code.startswith('unknown_'):return 404
    if code.startswith('stale') or code in ('idempotency_conflict','output_exists'):return 409
    if code.endswith('_limit') or code in ('config_count','input_count'):return 413
    return 400

def integer(query,key,default,low,high):
    try:v=int(query.get(key,[str(default)])[0])
    except (TypeError,ValueError):raise RagError('invalid_query','input') from None
    require(low<=v<=high,'invalid_query','input');return v

class UI:
    def __init__(self,registry,jobs):self.registry=registry;self.jobs=jobs;self.token=secrets.token_urlsafe(32)
    def bootstrap(self):
        r=self.registry
        return {'session_token':self.token,'inputs':r.input_summary(),'configs':[r.config_summary(k) for k in r.data['configs']],
            'drive_configs':[{'id':k,'auth_mode':v['config']['auth']['mode']} for k,v in r.drives.items()],
            'allow_model_execution':self.jobs.allow_model,'allow_drive_download':self.jobs.allow_drive,'execution_kind':'test_fixture' if self.jobs.fixture else 'preview_default',
            'embedding_configs':[{'id':k,'model_id':v['config']['model_id'],'license':'MIT','preparation':preparation_summary(v['config']),'configuration_required':not __import__('rag_package.embedding',fromlist=['configured']).configured(v['config']),'quality':'Korean pretrained quality unverified'} for k,v in r.embeddings.items()],'allow_retrieval_execution':self.jobs.allow_retrieval,
            'reranker_configs':[{'id':k,'model_id':v['config']['model_id'],'preparation':preparation_summary(v['config']),'configuration_required':not __import__('rag_package.reranker',fromlist=['configured']).configured(v['config'])} for k,v in r.rerankers.items()],
            'allow_reranking_execution':self.jobs.allow_reranking,
            'labels':{kind:[{'id':k,'label':v['label']} for k,v in entries.items()] for kind,entries in r.labels.items()},
            'rerank_artifacts':[{'id':k,'kind':v['kind']} for k,v in r.data['artifacts'].items() if v['kind'] in ('candidates','rerank','rerank-comparison','rerank-answer')],
            'chunk_configs':[{'id':k,'method':v['config']['method'],'heading_profile':v['config'].get('heading_profile'),'size_chars':v['config']['size_chars'],'overlap_chars':v['config']['overlap_chars']} for k,v in r.chunk_configs.items()],
            'allow_chunking_execution':self.jobs.allow_chunking,
            'pipelines':[{'id':k,'label':v.get('label',k),'status':v.get('status')} for k,v in r.data['artifacts'].items() if v['kind']=='pipeline'],
            'chunk_artifacts':[r.chunk_summary(k) for k,v in r.data['artifacts'].items() if v['kind'] in ('chunks','chunk-preview')],
            'capabilities':{'chunking':['fixed','recursive','structure','semantic','llm'],'retrieval':['bm25','dense','hybrid'],'unsupported':['Qwen instruction 리랭커','평가기']},
            'limits':{'inputs':20,'configs':8,'upload_bytes':20*1024*1024,'concurrent_jobs':1,'comparison_requests':80},'jobs':self.jobs.summaries()}
    def artifact(self,key):
        p,e,m=self.registry.artifact(key);kind=e['kind'];out={'id':key,'kind':kind,'manifest':m,'snapshot_id':e.get('snapshot_id',key)}
        if kind=='pipeline':
            from .pipeline import replay
            out['result']=replay(p)
        elif kind=='snapshot':out['documents']=[{k:v for k,v in d.items() if k!='text'} for d in load_snapshot(p,ready=False)[1]]
        elif kind in ('chunks','chunk-preview'):
            if kind=='chunks':
                from .chunk_artifact import load
                cr,_,cs,coverage=load(p);out.update(result=cr,units=read_json(p/'units.json'),chunks=cs,coverage=coverage)
            else:out['result']=read_json(p/'preview.json')
        elif kind=='build':out.update(chunks_count=len(read_json(p/'chunks.json')),coverage=read_json(p/'coverage.json'),embedding_work=read_json(p/'embedding-work.json') if (p/'embedding-work.json').exists() else {'jobs':0,'documents':0,'queries':0})
        elif kind=='answer':
            result=read_json(p/'result.json')
            from .retrieval import load_build
            b,_,_=self.registry.artifact(e['build_id']);_,_,chunks=load_build(b,result['effective_settings'])
            wanted={c['chunk_id'] for c in result['candidates']}
            out.update(result=result,build_id=e['build_id'],candidate_chunks=[c for c in chunks if c['chunk_id'] in wanted])
        elif kind in ('candidates','rerank','rerank-comparison','rerank-answer'):
            from .ui_reranking import artifact
            out.update(artifact(p,e))
        else:out.update(result=read_json(p/'comparison.json'),answer_ids=e['answer_ids'],build_ids=e['build_ids'],labels=e['labels'])
        return out

class Server(ThreadingHTTPServer):
    daemon_threads=True
    allow_reuse_address=False
    def __init__(self,port,ui):
        require(type(port) is int and (port==0 or 1024<=port<=65535),'invalid_port','server')
        self.ui=ui
        try:super().__init__(('127.0.0.1',port),Handler)
        except OSError:raise RagError('port_unavailable','server') from None
        self.origin='http://127.0.0.1:'+str(self.server_port);self.host='127.0.0.1:'+str(self.server_port)

class Handler(BaseHTTPRequestHandler):
    def setup(self):super().setup();self.connection.settimeout(30)
    def log_message(self,*args):pass
    def headers_out(self,status,ctype,size,attachment=None):
        self.send_response(status);self.send_header('Content-Type',ctype);self.send_header('Content-Length',str(size));self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self'; object-src 'none'; frame-ancestors 'none'; base-uri 'none'")
        if attachment:self.send_header('Content-Disposition','attachment; filename="'+attachment+'"')
        self.end_headers()
    def raw(self,status,data,ctype,attachment=None):
        self.headers_out(status,ctype,len(data),attachment);self.wfile.write(data)
    def reply(self,status,data=None,error=None):
        value={'schema_version':1,'status':'error','error':error} if error else {'schema_version':1,'status':'ok','data':data}
        self.raw(status,json.dumps(value,ensure_ascii=False,allow_nan=False).encode(),'application/json; charset=utf-8')
    def boundary(self,token=False):
        require(self.headers.get_all('Host')==[self.server.host],'host_denied','http')
        origins=self.headers.get_all('Origin')
        require(origins is None or origins==[self.server.origin],'origin_denied','http')
        if token:require(self.headers.get_all('X-Rag-Session')==[self.server.ui.token],'session_denied','http')
    def route(self):
        parsed=urlsplit(self.path);require(not parsed.scheme and not parsed.netloc and not parsed.fragment and '%' not in parsed.path and '..' not in parsed.path and '\\' not in parsed.path,'invalid_path','http')
        try:q=parse_qs(parsed.query,keep_blank_values=True,strict_parsing=True)
        except ValueError:raise RagError('invalid_query','http') from None
        require(all(len(v)==1 for v in q.values()),'invalid_query','http')
        return parsed.path,q
    def body(self,limit,ctype):
        require(self.headers.get('Transfer-Encoding') is None,'transfer_encoding_unsupported','http')
        lengths=self.headers.get_all('Content-Length');require(lengths is not None and len(lengths)==1 and lengths[0].isdigit(),'content_length_required','http')
        n=int(lengths[0]);require(0<n<=limit,'body_size_limit','http');require(self.headers.get('Content-Type','').split(';')[0].strip()==ctype,'content_type_required','http')
        data=self.rfile.read(n);require(len(data)==n,'partial_body','http');return data
    def do_GET(self):self.dispatch(False)
    def do_POST(self):self.dispatch(True)
    def dispatch(self,post):
        try:
            self.boundary(token=post);path,q=self.route();ui=self.server.ui;r=ui.registry
            if not post and path in STATIC:
                require(not q,'invalid_query','http');name=STATIC[path];self.raw(200,files('rag_package').joinpath('ui',name).read_bytes(),MIME[name]);return
            if not post and path=='/api/bootstrap':require(not q,'invalid_query','http');self.reply(200,ui.bootstrap());return
            if post:
                require(not q,'invalid_query','http')
                if path.startswith('/api/uploads/'):
                    fmt=path.removeprefix('/api/uploads/');require(fmt in ('pdf','txt','md'),'unsupported_source','upload');rawname=self.headers.get('X-File-Name','')
                    try:name=unquote_to_bytes(rawname).decode('utf-8')
                    except UnicodeError:raise RagError('invalid_filename','upload') from None
                    self.reply(201,r.upload(fmt,name,self.body(20*1024*1024,'application/octet-stream')));return
                data=decode(self.body(16*1024,'application/json'))
                if path=='/api/compare-answers':
                    from .reranking import compare_answers
                    require(isinstance(data,dict) and set(data)=={'ids'} and isinstance(data['ids'],list) and 2<=len(data['ids'])<=20,'comparison_size','http')
                    entries=[]
                    for key in data['ids']:
                        location,entry,_=r.artifact(key)
                        require(entry['kind']=='rerank-answer','wrong_artifact_kind','input')
                        entries.append((key,location))
                    self.reply(200,compare_answers(entries));return
                if path=='/api/jobs':job,new=ui.jobs.submit(data);self.reply(202 if new else 200,job);return
                if path=='/api/model-configs':self.reply(201,r.clone_model(data));return
                raise RagError('unknown_route','http')
            parts=path.strip('/').split('/')
            if len(parts)==3 and parts[:2]==['api','jobs']:
                require(not q,'invalid_query','http');self.reply(200,ui.jobs.get(parts[2]));return
            if len(parts)==4 and parts[:2]==['api','model-configs'] and parts[3]=='export':
                self.boundary(token=True);require(not q,'invalid_query','http');c=r.llm(parts[2]);self.raw(200,(json.dumps(c,ensure_ascii=False,indent=2)+'\n').encode(),'application/json','model-config.json');return
            if len(parts) in (3,4) and parts[:2]==['api','artifacts']:
                key=parts[2]
                if len(parts)==3:require(not q,'invalid_query','http');self.reply(200,ui.artifact(key));return
                operation=parts[3]
                if operation=='chunks':
                    require(set(q)<={'offset','limit'},'invalid_query','http');p,e,_=r.artifact(key);require(e['kind'] in ('build','chunks'),'wrong_artifact_kind','input')
                    offset=integer(q,'offset',0,0,1000000);limit=integer(q,'limit',50,1,100);chunks=read_json(p/'chunks.json');self.reply(200,{'items':chunks[offset:offset+limit],'next_offset':offset+limit if offset+limit<len(chunks) else None,'total':len(chunks),'snapshot_id':e.get('snapshot_id',key)});return
                require(operation in ('pages','original'),'unknown_route','http');require(set(q)<=({'document_id','page','offset','limit'} if operation=='pages' else {'document_id'}),'invalid_query','http')
                p,snapshot_id=r.snapshot_for(key);m,docs=load_snapshot(p,ready=False);d=next((d for d in docs if d['document_id']==q.get('document_id',[None])[0]),None);require(d is not None,'unknown_document','http')
                if operation=='original':self.raw(200,safe_path(p,d['original_path']).read_bytes(),'application/octet-stream','original.'+d['format']);return
                page=integer(q,'page',1,1,100);offset=integer(q,'offset',0,0,1000000);limit=integer(q,'limit',8000,1,8000);info=next((x for x in d['pages'] if x['page']==page),None);require(info is not None,'unknown_page','http')
                text=d['text'][info['start']:info['end']];self.reply(200,{'document_id':d['document_id'],'title':d['title'],'page':page,'offset':offset,'canonical_start':info['start']+offset,'text':text[offset:offset+limit],'next_offset':offset+limit if offset+limit<len(text) else None,'normalization':d['normalization'],'snapshot_id':snapshot_id});return
            raise RagError('unknown_route','http')
        except (RagError,ValidationError) as e:
            self.close_connection=True
            try:self.reply(error_status(e.code),error={'code':e.code,'stage':getattr(e,'stage','input')})
            except (OSError,ValueError):pass
        except (socket.timeout,TimeoutError):
            self.close_connection=True
            try:self.reply(400,error={'code':'request_timeout','stage':'http'})
            except OSError:pass
        except Exception:
            self.close_connection=True
            try:self.reply(500,error={'code':'internal_error','stage':'http'})
            except OSError:pass

def create_server(workspace,llm_configs,sources=None,drive_configs=(),port=8765,allow_model=False,allow_drive=False,embedding_configs=(),allow_retrieval=False,reranker_configs=(),allow_reranking=False,qrels=(),facts=(),chunk_configs=(),allow_chunking=False,pipeline_runs=(),**test_injection):
    r=Registry(workspace,llm_configs,sources,drive_configs,embedding_configs,reranker_configs,qrels,facts,chunk_configs)
    from .pipeline import replay
    for path in pipeline_runs:
        directory=contained(r.workspace,path)
        require(not any(p.is_symlink() for p in directory.rglob('*')),'symlink_denied','registry')
        result=replay(directory)
        existing=next((k for k,v in r.data['artifacts'].items() if v['kind']=='pipeline' and v['path']==r.relative(directory)),None)
        if existing:r.artifact(existing)
        else:r.add_artifact(directory,'pipeline',label=result['question'],status=result['status'])
    jobs=Jobs(r,allow_model,allow_drive,allow_retrieval=allow_retrieval,allow_reranking=allow_reranking,allow_chunking=allow_chunking,**test_injection);return Server(port,UI(r,jobs))

def serve(args):
    server=create_server(args.workspace,args.llm_config,args.sources,args.drive_config,args.port,args.allow_model_execution,args.allow_drive_download,embedding_configs=args.embedding_config,allow_retrieval=args.allow_retrieval_execution,reranker_configs=args.reranker_config,allow_reranking=args.allow_reranking_execution,qrels=args.qrels,facts=args.facts,chunk_configs=args.chunk_config,allow_chunking=args.allow_chunking_execution,pipeline_runs=args.pipeline_run)
    print(json.dumps({'status':'serving','url':server.origin,'execution_kind':'preview_default','model_execution_allowed':args.allow_model_execution,'drive_download_allowed':args.allow_drive_download}),flush=True)
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:server.server_close()
    return 0
