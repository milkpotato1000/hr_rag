"""Run four predeclared BM25 searches and compare CLI and UI preview plans."""
import hashlib,json,os,shlex,subprocess,time,urllib.request,uuid
from pathlib import Path
E=Path(__file__).resolve().parent
def read(p):return json.loads(p.read_text())
base=Path(read(E/'installation.json')['base'])
ws=base/'practice'
cli=base/'env/bin/rag-lab'
env=dict(PATH=str(cli.parent)+':/usr/bin:/bin',LANG='en_US.UTF-8',PIP_NO_INDEX='1')
def run(args,cwd=ws,valid=True):
    r=subprocess.run(args,cwd=cwd,env=env,capture_output=True,text=True)
    assert (r.returncode==0)==valid,(args,r.stdout,r.stderr)
    return json.loads(r.stdout)
inputs=read(E/'inputs.json')
question=inputs['question']
quote=inputs['quote']
def setup(label,chunk='chunk-fixed.json',options=(),valid=True):
    return run([cli,'pipeline-setup','--llm-config','llm-local.json','--chunk-config',chunk,'--method','bm25',
                '--question',question,'--out',label,*options],valid=valid)
def ui_check(selection,plan):
    ui=subprocess.Popen(shlex.split(selection['commands']['serve'])+['--port','0'],env=env,cwd=ws,text=True,stdout=subprocess.PIPE)
    try:
        origin=json.loads(ui.stdout.readline())['url']
        def get(path):
            return json.load(urllib.request.urlopen(origin+path,timeout=10))['data']
        boot=get('/api/bootstrap')
        d=boot['pipeline_defaults']
        assert not boot['allow_model_execution'] and d['question']==question
        request=dict(kind='pipeline',request_id=str(uuid.uuid4()),input_ids=[x['id'] for x in boot['inputs']],
            question=d['question'],execute=False,llm_config_id=d['llm_id'],chunk_config_id=d['chunk_id'],
            retrieval=d['retrieval'],embedding_config_id=None,reranker_config_id=None)
        post=urllib.request.Request(origin+'/api/jobs',data=json.dumps(request).encode(),headers={
            'Content-Type':'application/json','X-Rag-Session':boot['session_token']})
        job=json.load(urllib.request.urlopen(post,timeout=10))['data']
        for _ in range(100):
            job=get('/api/jobs/'+job['id'])
            if job['status'] in ('completed','failed'):break
            time.sleep(.1)
        assert job['status']=='completed' and not job['dispatch_attempted']
        assert get('/api/artifacts/'+job['artifact_ids'][0])['result']['plan']==plan
    finally:
        ui.terminate();ui.wait(timeout=10)

if __name__=='__main__':
    import sys
    if sys.argv[1]=='ui':
        for label in inputs['variants']:
            ui_check(read(ws/label/'selection.json'),read(ws/(label+'-preview')/'pipeline.json')['plan'])
        print('Four UI job plans equal CLI plans; model execution disabled.')
        sys.exit()
    run([cli,'init','--out','practice'],cwd=base)
    protected=['documents/handbook.pdf','chunk-fixed.json','chunk-handbook.json','chunk-llm.json','llm-local.json','llm-chunking.json']
    hashes=lambda:{p:hashlib.sha256((ws/p).read_bytes()).hexdigest() for p in protected}
    before=hashes()
    run([cli,'snapshot','--sources','handbook-sources.json','--out','size-lab-pdf'])
    source=(ws/'size-lab-pdf/handbook/canonical.txt').read_text()
    offset=source.index(quote)
    rows={}
    for label,variant in inputs['variants'].items():
        args=[str(v) for item in variant.items() for v in item]
        selection=setup(label,options=args)
        folder=ws/label
        (folder/'selection.json').write_text(json.dumps(selection))
        preview=run(shlex.split(selection['commands']['pipeline_preview']))
        cfg=read(folder/'chunk.json');settings=preview['plan']['retrieval']
        assert preview['question']==question and preview['plan']['chunking']==cfg
        assert settings==dict(method='bm25',candidate_k=20,top_k=5,context_budget_chars=variant.get('--context-budget-chars',4000),rrf_k=60)
        assert cfg==dict(schema_version=1,method='fixed',size_chars=variant.get('--size-chars',400),overlap_chars=variant.get('--overlap-chars',80))
        run([cli,'build','--snapshot','size-lab-pdf','--config',folder/'search.json','--out',folder/'index'])
        run([cli,'ask','--run',folder/'index','--config',folder/'search.json','--question',question,'--out',folder/'search'])
        r=read(folder/'search/result.json')
        chunks=read(folder/'index/chunks.json')
        assert r['generation_requests']==0 and not r['dispatch_attempted']
        byid={c['chunk_id']:c for c in chunks}
        ranked=r['retrieval_trace']['bm25']
        whole=[x['rank'] for x in ranked if quote in byid[x['chunk_id']]['text']]
        selected=r['contexts']
        assert all(c['text']==source[c['start']:c['end']] for c in chunks)
        spans=[(c['start'],c['end']) for c in chunks]
        overlaps=[[b[0],a[1]] for a,b in zip(spans,spans[1:]) if a[1]>b[0]]
        rows[label]=dict(config=cfg,settings=settings,chunk_count=len(chunks),overlap_chars_total=sum(b-a for a,b in overlaps),
          local_overlaps=[o for o in overlaps if offset-400<o[0]<offset+400],source_quote_range=[offset,offset+len(quote)],
          nearby_chunks=[s for s in spans if s[0]<offset+len(quote) and offset<s[1]],
          ranking=ranked,full_quote_ranks=whole,contexts=selected,excluded=r['excluded'],delivered_chars=sum(len(c['text']) for c in selected),
          quote_delivered=any(quote in c['text'] for c in selected))
    assert rows['baseline']['ranking']==rows['budget']['ranking']
    assert read(ws/'baseline/index/chunks.json')==read(ws/'budget/index/chunks.json')
    for extra in [('--overlap-chars','400'),('--overlap-chars','-1'),('--size-chars','99')]:
        setup('invalid',options=extra,valid=False);assert not (ws/'invalid').exists()
    setup('invalid-model',chunk='chunk-llm.json',options=['--size-chars','150'],valid=False)
    assert not (ws/'invalid-model').exists()
    for chunk,label in [('chunk-llm.json','model'),('chunk-handbook.json','heading')]:
        setup(label,chunk=chunk,options=['--overlap-chars','0'])
        old=read(ws/chunk);new=read(ws/label/'chunk.json')
        if label=='model':
            assert read(ws/old.pop('llm_config'))==read(ws/label/new.pop('llm_config'))
        assert dict(old,overlap_chars=0)==new
    assert before==hashes()
    (E/'results.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n')
