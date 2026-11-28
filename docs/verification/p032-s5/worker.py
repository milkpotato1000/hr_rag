"""Installed real CLI with accounting around the original real HTTP transport."""
import sys
from pathlib import Path
# Only verification helpers are added, never the checkout package.
sys.path.insert(0,str(Path(__file__).resolve().parent))
from runtime import *
from rag_package.llm import core
from rag_package.__main__ import main
import rag_package
frozen=read(E/'frozen.json');need(str(Path(frozen['python']).parent.parent) in rag_package.__file__,'wrong_installed_package')
qid=sys.argv[1];row=next(r for r in frozen['rows'] if r['question_id']==qid);original=core.http_transport
from rag_package.llm.core import hash_json
def observed_http(method,url,headers,body,timeout):
    need(url.startswith(BASE+'/api/'),'external_endpoint')
    endpoint=url[len(BASE):]
    if endpoint!='/api/chat':
        need(method=='GET' and endpoint=='/api/tags','unexpected_product_metadata')
        return metadata(endpoint,actor='adapter-'+qid)
    need(method=='POST' and timeout==480,'generation_request_contract')
    need(body.get('model')=='qwen3:4b' and body.get('think') is True and body.get('keep_alive')==0,'generation_model_contract')
    with transact(LEDGER) as c:c.reserve(qid,hash_json(body),row['body_hash'],read(E/'health.json'))
    # Unchanged production transport; no canned response, parser or provider substitution.
    raw=original(method,url,headers,body,timeout)
    with transact(LEDGER) as c:c.response(qid)
    return raw
core.http_transport=observed_http
practice=Path(frozen['practice'])
os.chdir(practice)
need(read('handbook-model.json')==read(E/'profile.json'),'profile_mismatch')
raise SystemExit(main(['answer-from-rerank','--run','.rag-runs/on','--llm-config','handbook-model.json','--out','.rag-runs/answer','--execute']))
