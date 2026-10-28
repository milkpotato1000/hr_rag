"""Mechanical artifact audit; semantic reviews remain explicit, separate prose."""
import hashlib
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[3]
STAGE=ROOT/'1. Naive RAG'
E=Path(__file__).parent
sys.path.insert(0,str(STAGE/'scripts'))
import generation as g
import rag

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()

def verify_result(path):
    result=json.loads(path.read_text());t=result['trace']
    assert result['status']!='error', path
    assert t['citation_mode']==g.CITATION_MODE
    assert t['response_contract']==g.RESPONSE_CONTRACT
    assert t['semantic_support']=='not_automatically_evaluated'
    assert t['prompt']['system_version']=='system-v3'
    assert t['prompt']['system_sha256']==sha(STAGE/'prompts/system-v3.txt')
    if not t['contexts']:
        assert t['generation_calls']==0 and 'generation' not in t
        return
    assert t['generation_calls']==1
    contexts={c['chunk_id']:c for c in t['contexts']}
    sent=t['generation']; ids=list(contexts)
    assert sent['allowed_ids']==ids
    assert sent['request_dispatched'] is True
    assert sent['request']==g.request_for_ids(g.load_generation_lock(),ids)
    assert sent['schema_sha256']==g.digest_text(json.dumps(sent['request']['format'],ensure_ascii=False,sort_keys=True))
    assert json.loads(t['prompt']['messages'][1]['content'])['contexts']==t['contexts']
    if result['status']=='answered':
        raw=json.loads(t['raw_content'])
        assert [c['chunk_id'] for c in raw['citations']]==[c['chunk_id'] for c in result['citations']]
        assert all(set(c)=={'chunk_id'} for c in raw['citations'])
        for c in result['citations']:
            source=contexts[c['chunk_id']]
            assert c['quote'].encode()==source['text'].encode()
            assert all(c[k]==source[k] for k in ['source','title','version','document_id'])
        assert t['citation_structure_valid'] is True
    return result

def main():
    hashes=json.loads((E/'preservation-before.json').read_text())
    # Path-navigation READMEs were explicitly requested in this chat; data bytes stay fixed.
    allowed={'1. Naive RAG/data/source-v2/README.md','1. Naive RAG/data/synthetic/README.md'}
    changed={p for p,h in hashes.items() if sha(ROOT/p)!=h}
    assert changed<=allowed, changed
    old=json.loads((E/'generation-lock-before.json').read_text());current=g.load_generation_lock()
    assert old['model']==current['model']
    assert old['ollama_version']==current['ollama_version']
    for k in ['options','stream','think']: assert old['request'][k]==current['request'][k]
    assert sha(STAGE/'generation-lock.json')==json.loads((E/'lock-migration.json').read_text())['after_sha256']
    files=sorted((E/'live').glob('*.json'))
    assert len(files)==16, len(files)
    for p in files: verify_result(p)
    meal=json.loads((E/'live/meal-bm25.json').read_text())
    assert meal['status']=='answered'
    assert 'welfare-meal' in [c['chunk_id'] for c in meal['citations']]
    pdf=json.loads((E/'live/pdf-q06.json').read_text())
    assert pdf['status']=='answered'
    assert any('\n' in c['quote'] for c in pdf['citations'])
    assert json.loads((E/'live/q13.json').read_text())['reason']=='model_abstained'
    report={'status':'PASS','preserved_files':len(hashes)-len(changed),'allowed_navigation_doc_changes':sorted(changed),'actual_local_model_results':len(files),'model_metadata_runtime_sampling_unchanged':True,'lock_unchanged_after_setup_and_live':True,'citation_bytes_and_trace':'all actual answered results exact','semantic_quality':'see separate final-review.md; not established by this audit'}
    (E/'preservation-and-trace.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(report,ensure_ascii=False))

if __name__=='__main__': main()
