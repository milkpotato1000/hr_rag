"""General document RAG CLI; ask/compare default to no-call preview."""
import json
from .llm.__main__ import Parser
from .llm.config import ValidationError
from .storage import RagError
from .documents import snapshot
from .retrieval import build
from .rag import ask,compare

def main(argv=None):
    try:
        p=Parser(description='PDF/TXT/MD RAG. ask/compare default preview: no model/API/key access. Explicit --execute dispatches generation.')
        from ._version import __version__
        p.add_argument('--version',action='version',version=__version__)
        subs=p.add_subparsers(dest='command',required=True)
        s=subs.add_parser('snapshot');s.add_argument('--sources',required=True)
        b=subs.add_parser('build');b.add_argument('--snapshot',required=True);b.add_argument('--config',required=True)
        a=subs.add_parser('ask');a.add_argument('--run',required=True);a.add_argument('--config',required=True);a.add_argument('--question',required=True);a.add_argument('--execute',action='store_true')
        c=subs.add_parser('compare');c.add_argument('--snapshot',required=True);c.add_argument('--configs',nargs='+',required=True);c.add_argument('--questions',required=True);c.add_argument('--execute',action='store_true')
        for sub in (s,b,a,c):sub.add_argument('--out',required=True)
        for sub in (b,a,c):sub.add_argument('--execute-retrieval',action='store_true')
        c.add_argument('--qrels');c.add_argument('--facts')
        for name in ('chunk','chunk-replay','chunk-derive','chunk-report'):
            sub=subs.add_parser(name)
            if name=='chunk':sub.add_argument('--snapshot',required=True);sub.add_argument('--execute-chunking',action='store_true')
            else:sub.add_argument('--run',required=True)
            if name in ('chunk','chunk-derive'):sub.add_argument('--config',required=True)
            if name!='chunk-replay':sub.add_argument('--out',required=True)
        preview=subs.add_parser('retrieval-preview');preview.add_argument('--config',required=True)
        dp=subs.add_parser('drive-preview');dp.add_argument('--config',required=True)
        dl=subs.add_parser('drive-pull');dl.add_argument('--config',required=True);dl.add_argument('--out',required=True);dl.add_argument('--execute',action='store_true')
        login=subs.add_parser('drive-login');login.add_argument('--client-secret-file',required=True);login.add_argument('--credentials-file',required=True);login.add_argument('--execute',action='store_true')
        init=subs.add_parser('init');init.add_argument('--out',required=True)
        doctor=subs.add_parser('doctor');doctor.add_argument('--config')
        for name in ('llm','embedding','reranker','chunk'):doctor.add_argument('--'+name+'-config')
        subs.add_parser('model-catalog')
        mp=subs.add_parser('model-plan');mp.add_argument('--model',required=True);mp.add_argument('--role',choices=['embedding','reranker'],required=True);mp.add_argument('--out',required=True);mp.add_argument('--revision');mp.add_argument('--fetch-metadata',action='store_true')
        for name in ('model-prepare','model-import'):
            sub=subs.add_parser(name);sub.add_argument('--plan',required=True);sub.add_argument('--out',required=True);sub.add_argument('--execute-conversion',action='store_true')
            if name=='model-prepare':sub.add_argument('--execute-download',action='store_true')
            else:sub.add_argument('--source',required=True)
        mc=subs.add_parser('model-check');mc.add_argument('--profile',required=True)
        lc=subs.add_parser('llm-configure');lc.add_argument('--spec',required=True);lc.add_argument('--out',required=True);lc.add_argument('--inspect-local',action='store_true')
        server=subs.add_parser('serve');server.add_argument('--workspace',required=True);server.add_argument('--sources');server.add_argument('--llm-config',required=True,action='append');server.add_argument('--drive-config',action='append',default=[]);server.add_argument('--port',type=int,default=8765);server.add_argument('--allow-model-execution',action='store_true');server.add_argument('--allow-drive-download',action='store_true')
        server.add_argument('--embedding-config',action='append',default=[]);server.add_argument('--allow-retrieval-execution',action='store_true')
        for name in ('candidates','rerank','answer-from-rerank','rerank-compare','rerank-report'):
            sub=subs.add_parser(name);sub.add_argument('--out',required=True)
            if name=='candidates':
                sub.add_argument('--build',required=True);sub.add_argument('--result',required=True);sub.add_argument('--question-id',required=True);sub.add_argument('--n',type=int,default=20)
            elif name=='rerank':
                sub.add_argument('--candidates',required=True);sub.add_argument('--method',choices=['none','cross-encoder'],required=True);sub.add_argument('--profile');sub.add_argument('--top-k',type=int,default=5);sub.add_argument('--context-budget-chars',type=int,default=4000);sub.add_argument('--execute-reranking',action='store_true')
            elif name=='answer-from-rerank':
                sub.add_argument('--run',required=True);sub.add_argument('--llm-config',required=True);sub.add_argument('--execute',action='store_true')
            elif name=='rerank-compare':
                sub.add_argument('--candidates-set',required=True);sub.add_argument('--variants',required=True);sub.add_argument('--qrels');sub.add_argument('--facts');sub.add_argument('--execute-reranking',action='store_true')
            else:sub.add_argument('--run',required=True)
        server.add_argument('--reranker-config',action='append',default=[]);server.add_argument('--allow-reranking-execution',action='store_true')
        server.add_argument('--qrels',action='append',default=[]);server.add_argument('--facts',action='append',default=[])
        server.add_argument('--chunk-config',action='append',default=[]);server.add_argument('--allow-chunking-execution',action='store_true')
        view=subs.add_parser('compare-answers',help='Compare saved answer-from-rerank results without inference')
        view.add_argument('--result',nargs=2,action='append',required=True,metavar=('LABEL','DIRECTORY'))
        args=p.parse_args(argv)
        if args.command=='compare-answers':
            from .reranking import compare_answers
            print(json.dumps(compare_answers(args.result),ensure_ascii=False,indent=2))
            return 0
        if args.command.startswith('model-') or args.command=='llm-configure':
            from . import model_catalog,model_preparation,llm_setup
            if args.command=='model-catalog':r=model_catalog.catalog()
            elif args.command=='model-plan':r=model_catalog.plan(args.model,args.role,args.out,args.revision,args.fetch_metadata)
            elif args.command=='model-check':r=model_preparation.model_check(args.profile)
            elif args.command=='llm-configure':r=llm_setup.configure(args.spec,args.out,args.inspect_local)
            else:r=model_preparation.prepare(args.plan,args.out,source=getattr(args,'source',None),execute_download=getattr(args,'execute_download',False),execute_conversion=args.execute_conversion)
            print(json.dumps(r,ensure_ascii=False));return 1 if r.get('status') in ('failed','interrupted') else 0
        if args.command in ('chunk','chunk-replay','chunk-derive','chunk-report'):
            from . import chunk_artifact,chunk_compare
            if args.command=='chunk':r=chunk_artifact.build(args.snapshot,args.config,args.out,execute=args.execute_chunking)
            elif args.command=='chunk-replay':r=chunk_artifact.replay(args.run)
            elif args.command=='chunk-derive':r=chunk_artifact.derive(args.run,args.config,args.out)
            else:r=chunk_compare.report(args.run,args.out)
            print(json.dumps({k:v for k,v in r.items() if k not in ('units','requests','config')},ensure_ascii=False));return 1 if r.get('status') in ('failed','interrupted') else 0
        if args.command in ('candidates','rerank','answer-from-rerank','rerank-compare','rerank-report'):
            from . import candidates,reranking,rerank_compare
            if args.command=='candidates':r=candidates.freeze(args.build,args.result,args.question_id,args.n,args.out)
            elif args.command=='rerank':r=reranking.run(args.candidates,args.method,args.out,profile=args.profile,top_k=args.top_k,context_budget_chars=args.context_budget_chars,execute=args.execute_reranking)
            elif args.command=='answer-from-rerank':r=reranking.answer(args.run,args.llm_config,args.out,execute=args.execute)
            elif args.command=='rerank-compare':r=rerank_compare.compare(args.candidates_set,args.variants,args.out,qrels=args.qrels,facts=args.facts,execute=args.execute_reranking)
            else:r=rerank_compare.report(args.run,args.out)
            failed=r.get('status')=='failed' or any(row['status']=='failed' for row in r.get('rows',[]) if 'status' in row)
            print(json.dumps({'status':r.get('status','complete'),'command':args.command,'artifact_written':True,'reason':r.get('reason'),'error':r.get('error'),'work':r.get('work'),'generation_requests':r.get('generation_requests',0)}));return 1 if failed else 0
        if args.command=='retrieval-preview':
            from .retrieval import dry_run
            print(json.dumps(dry_run(args.config),ensure_ascii=False));return 0
        if args.command=='serve':
            from .ui_server import serve
            return serve(args)
        if args.command in ('init','doctor'):
            from . import workspace
            if args.command=='init':result,code=workspace.init(args.out),0
            else:result,code=workspace.doctor(args.config,llm_config=args.llm_config,embedding_config=args.embedding_config,reranker_config=args.reranker_config,chunk_config=args.chunk_config)
            print(json.dumps(result,ensure_ascii=False));return code
        if args.command=='drive-preview':
            from .connectors.drive_config import preview
            print(json.dumps(preview(args.config),ensure_ascii=False));return 0
        if args.command=='drive-pull':
            from .connectors.google_drive import pull
            r=pull(args.config,args.out,execute=args.execute)
            if not args.execute:print(json.dumps(r,ensure_ascii=False));return 0
            ok=r['status']=='ready'
        elif args.command=='drive-login':
            from .drive_auth import login
            r=login(args.client_secret_file,args.credentials_file,execute=args.execute)
            print(json.dumps(r,ensure_ascii=False));return 0
        elif args.command=='snapshot':
            r=snapshot(args.sources,args.out);ok=r['identity']['status']=='ready'
        elif args.command=='build':r=build(args.snapshot,args.config,args.out,execute_retrieval=args.execute_retrieval);ok=True
        elif args.command=='ask':
            r=ask(args.run,args.config,args.question,args.out,execute=args.execute,execute_retrieval=args.execute_retrieval);ok=r['status'] in ('preview','answered','abstained')
        else:
            r=compare(args.snapshot,args.configs,args.questions,args.out,execute=args.execute,execute_retrieval=args.execute_retrieval,qrels=args.qrels,facts=args.facts);ok=not any(x['status']=='failed' for x in r['rows'])
        if args.command=='build':
            from .storage import read_json
            from pathlib import Path
            r['embedding_work']=read_json(Path(args.out)/'embedding-work.json')
        # Full private content remains in the requested artifact, not generic console logs.
        print(json.dumps({'status':'complete' if ok else 'needs_review_or_failed','command':args.command,'execution_kind':r.get('execution_kind','offline'),'artifact_written':True,'embedding_work':r.get('embedding_work'),'generation_requests':r.get('generation_requests',0)}))
        return 0 if ok else 1
    except (RagError,ValidationError) as e:
        print(json.dumps({'status':'error','error':{'code':e.code,'stage':getattr(e,'stage','input')},'dispatch_attempted':getattr(e,'dispatch_attempted',False),'work':getattr(e,'observation',None),'offending_ids':getattr(e,'offending_ids',[]),'requests':getattr(e,'requests',0),'request_stages':getattr(e,'request_stages',[]),'auth_refresh_attempted':getattr(e,'auth_refresh_attempted',False)}));return 2
    except Exception:
        print(json.dumps({'status':'error','error':{'code':'internal_error'}}));return 2

if __name__=='__main__':raise SystemExit(main())
