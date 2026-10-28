"""Run once with actual local models. Preserve every result; no quality retry."""
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[3]
STAGE=ROOT/'1. Naive RAG'
sys.path.insert(0,str(STAGE/'scripts'))
from rag import ask
OUT=Path(__file__).parent/'live'

def run(name,question,**kwargs):
    path=OUT/(name+'.json')
    if path.exists(): raise ValueError('refusing evidence overwrite: '+name)
    result=ask(question,**kwargs)
    path.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(name,result['status'],result['reason'],result['answer'],flush=True)
    if result['status']=='error': raise RuntimeError(result['trace']['error'])
    if result['status']=='answered':
        source={c['chunk_id']:c for c in result['trace']['contexts']}
        assert all(c['quote'].encode()==source[c['chunk_id']]['text'].encode() for c in result['citations'])
    return result

if __name__=='__main__':
    OUT.mkdir(exist_ok=True)
    run('meal-bm25','재택근무일과 휴가일에도 사무실 식대가 나오나요?',retriever='bm25')
    for row in map(json.loads,(STAGE/'data/synthetic/queries.jsonl').read_text().splitlines()):
        run(row['query_id'],row['question'])
    run('pdf-q06','미사용 연차는 며칠까지 이월하고 언제까지 써야 하나요?',chunks_path=STAGE/'data/source-v2/fixed-400-80/chunks.jsonl',index_dir=STAGE/'.runtime/index-source-v2-fixed-400-80')
