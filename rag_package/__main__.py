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
        dp=subs.add_parser('drive-preview');dp.add_argument('--config',required=True)
        dl=subs.add_parser('drive-pull');dl.add_argument('--config',required=True);dl.add_argument('--out',required=True);dl.add_argument('--execute',action='store_true')
        login=subs.add_parser('drive-login');login.add_argument('--client-secret-file',required=True);login.add_argument('--credentials-file',required=True);login.add_argument('--execute',action='store_true')
        init=subs.add_parser('init');init.add_argument('--out',required=True)
        doctor=subs.add_parser('doctor');doctor.add_argument('--config')
        server=subs.add_parser('serve');server.add_argument('--workspace',required=True);server.add_argument('--sources');server.add_argument('--llm-config',required=True,action='append');server.add_argument('--drive-config',action='append',default=[]);server.add_argument('--port',type=int,default=8765);server.add_argument('--allow-model-execution',action='store_true');server.add_argument('--allow-drive-download',action='store_true')
        args=p.parse_args(argv)
        if args.command=='serve':
            from .ui_server import serve
            return serve(args)
        if args.command in ('init','doctor'):
            from . import workspace
            if args.command=='init':result,code=workspace.init(args.out),0
            else:result,code=workspace.doctor(args.config)
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
        elif args.command=='build':r=build(args.snapshot,args.config,args.out);ok=True
        elif args.command=='ask':
            r=ask(args.run,args.config,args.question,args.out,execute=args.execute);ok=r['status'] in ('preview','answered','abstained')
        else:
            r=compare(args.snapshot,args.configs,args.questions,args.out,execute=args.execute);ok=not any(x['status']=='failed' for x in r['rows'])
        # Full private content remains in the requested artifact, not generic console logs.
        print(json.dumps({'status':'complete' if ok else 'needs_review_or_failed','command':args.command,'execution_kind':r.get('execution_kind','offline'),'artifact_written':True}))
        return 0 if ok else 1
    except (RagError,ValidationError) as e:
        print(json.dumps({'status':'error','error':{'code':e.code,'stage':getattr(e,'stage','input')},'dispatch_attempted':getattr(e,'dispatch_attempted',False),'requests':getattr(e,'requests',0),'request_stages':getattr(e,'request_stages',[]),'auth_refresh_attempted':getattr(e,'auth_refresh_attempted',False)}));return 2
    except Exception:
        print(json.dumps({'status':'error','error':{'code':'internal_error'}}));return 2

if __name__=='__main__':raise SystemExit(main())
