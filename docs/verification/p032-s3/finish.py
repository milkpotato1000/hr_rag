"""Verify installed readout and citation slices, then render the learning report."""
from html import escape
import shlex
from runtime import *
from pypdf import PdfReader
verify_parent()
f=read(E/'frozen.json')
for entries,base in [(f['input_files'],ROOT),(f['scripts'],E),(f['installed_files'],Path('/'))]:
    for name,h in entries.items():need(sha(base/name)==h,'frozen_bytes_changed')
ws=Path(f['practice']);r=read(ws/'.rag-runs/answer/result.json')
need(r==read(E/'result.json') and r['question']==f['rows'][0]['question'],'result_changed')
guide=(ws/'HANDBOOK.md').read_text()
command=next(line for line in guide.splitlines() if line.startswith('python -c') and 'answer/result.json' in line)
out=subprocess.run([f['python'],*shlex.split(command)[1:]],cwd=ws,check=True,capture_output=True,text=True)
(E/'answer-readout.txt').write_text(out.stdout)
pdf=PdfReader(ws/'documents/handbook.pdf')
answer=r.get('answer') or {};citations=answer.get('citations',[])
for c in citations:
    source=''.join(pdf.pages[i['page']-1].extract_text() for i in c['pages'])
    need(''.join(c['quote'].split()) in ''.join(source.split()),'pdf_slice')
review=read(E/'review.json')
l=read(LEDGER);need(len(l['requests'])==r['generation_requests']==1,'call_count')
need(r['contexts']==read(E/'search-preview.json')['contexts'],'preview_context_mismatch')
samples=[json.loads(s) for s in (E/'resources.jsonl').read_text().splitlines()]
provider=r['provider_result']
checks=dict(question=r['question'],product_status=r['status'],error=r.get('error'),provider_status=provider['status'],finish_reason=provider['finish_reason'],usage=provider['usage'],elapsed_seconds=provider['elapsed_ms']/1000,api_calls=0,api_key_reads=0,local_generation_calls=1,retries=0,contexts=len(r['contexts']),pdf_pages=len(pdf.pages),verified_citations=len(citations),peak_sampled_rss_bytes=max(s['rss_bytes'] for s in samples),server_cleanup=read(E/'server-closed.json'),prior_artifacts_verified=True)
write(E/'final-checks.json',checks)
parts=['<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>내 PDF 첫 질문 실습</title><style>body{max-width:50rem;margin:3rem auto;padding:0 1rem;font:1.05rem/1.65 system-ui;color:#172b38}pre,blockquote{white-space:pre-wrap;overflow-wrap:anywhere;background:#f3f6f8;padding:1rem;margin:1rem 0}summary{cursor:pointer}</style><main><h1>내 PDF 첫 질문 실습</h1>', '<h2>'+escape(r['question'])+'</h2>','<blockquote>'+escape(answer.get('answer','게시된 답변 없음'))+'</blockquote>','<p>'+escape(review['conclusion'])+'</p>','<h2>실제 인용</h2>']
for c in citations:
    parts+=['<p>PDF '+', '.join(str(page['page']) for page in c['pages'])+'쪽</p><blockquote>'+escape(c['quote'])+'</blockquote>']
parts.append('<h2>전달된 문맥</h2>')
for n,c in enumerate(r['contexts'],1):
    parts.append('<details><summary>검색 순위 '+str(n)+' · PDF '+', '.join(str(p['page']) for p in c['pages'])+'쪽</summary><blockquote>'+escape(c['text'])+'</blockquote></details>')
parts.append('<details><summary>실행 기록</summary><pre>'+escape(json.dumps(checks,ensure_ascii=False,indent=2))+'</pre></details></main></html>')
(E/'report.html').write_text('\n'.join(parts))
