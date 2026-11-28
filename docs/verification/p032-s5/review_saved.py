"""Read-only audit of the installed local result, API preview and source spans."""
from pathlib import Path
import hashlib,json,subprocess

E=Path(__file__).resolve().parent
def read(p):
    return json.loads(p.read_text())
inst=read(E/'installation.json')
ws=Path(read(E/'frozen.json')['practice'])
artifact=ws/'.rag-runs'
local=read(artifact/'answer/result.json')
rows=json.loads(subprocess.check_output([Path(inst['python']).with_name('rag-lab'),'compare-answers','--result','Qwen 4B',artifact/'answer','--result','API preview',artifact/'api'],text=True,cwd=ws))
assert rows['same_input'] and rows['comparison_model_calls']==0
assert [r['generation_requests'] for r in rows['rows']]==[1,0]
assert len(read(E/'ledger.json')['requests'])==1
source=artifact/'on/candidates/snapshot/handbook'
canonical=(source/'canonical.txt').read_text()
citations=[]
for c in (local['answer'] or {}).get('citations',[]):
    assert canonical[c['start']:c['end']]==c['quote']
    for page in c['pages']:
        raw=(source/f"page-{page['page']}.txt").read_text()
        assert raw[page['page_start']:page['page_end']]==canonical[page['canonical_start']:page['canonical_end']]
    citations.append({'chunk_id':c['chunk_id'],'pages':[p['page'] for p in c['pages']],'deadline_present':'사용 3영업일 전까지 휴가 시스템에서 신청' in ' '.join(c['quote'].split())})
for file,h in read(E/'parent-hashes.json').items():
    assert hashlib.sha256(Path(file).read_bytes()).hexdigest()==h
(E/'comparison.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n')
print(local['status'],local['answer'] and local['answer']['answer'],citations,rows['rows'][0]['usage'],rows['rows'][0]['elapsed_ms'])
