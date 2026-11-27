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
        subs=p.add_subparsers(dest='command',required=True)
        s=subs.add_parser('snapshot');s.add_argument('--sources',required=True)
        b=subs.add_parser('build');b.add_argument('--snapshot',required=True);b.add_argument('--config',required=True)
        a=subs.add_parser('ask');a.add_argument('--run',required=True);a.add_argument('--config',required=True);a.add_argument('--question',required=True);a.add_argument('--execute',action='store_true')
        c=subs.add_parser('compare');c.add_argument('--snapshot',required=True);c.add_argument('--configs',nargs='+',required=True);c.add_argument('--questions',required=True);c.add_argument('--execute',action='store_true')
        for sub in (s,b,a,c):sub.add_argument('--out',required=True)
        args=p.parse_args(argv)
        if args.command=='snapshot':
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
        print(json.dumps({'status':'error','error':{'code':e.code,'stage':getattr(e,'stage','input')},'dispatch_attempted':getattr(e,'dispatch_attempted',False)}));return 2
    except Exception:
        print(json.dumps({'status':'error','error':{'code':'internal_error'}}));return 2

if __name__=='__main__':raise SystemExit(main())
