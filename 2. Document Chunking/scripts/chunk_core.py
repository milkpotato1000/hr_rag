"""Five query-independent source-slice splitters and immutable artifacts."""
import json,math,re,statistics,time
from pathlib import Path
from document_common import read_json,write_json,file_hash,fingerprint,atomic_directory
from experiment_common import EXP,ARTIFACTS,need,ExperimentError,config as checked_config,source,code_hash,new_id,work_lock,strict,load_run
from source_io import windows,page_intersections,union_length
from model_runtime import Provider,validate_vector
from chunk_settings import custom,without_overlap


def boundary_units(text,nodes=(),maximum=400):
    need(isinstance(text,str) and bool(text),'empty_text','Empty canonical text')
    ends={len(text):'document_end'}
    for m in re.finditer(r'\n\s*\n',text):ends[m.end()]='paragraph'
    for m in re.finditer(r'[.?!。！？](?=\s|$)',text):
        p=m.end()
        while p<len(text) and text[p].isspace():p+=1
        ends.setdefault(p,'sentence')
    for node in nodes:
        p=node['heading']['end']
        need(0<p<=len(text),'invalid_offset','Heading boundary outside source')
        while p<len(text) and text[p].isspace():p+=1
        ends[p]='heading'
    result=[];start=0
    for end,kind in sorted(ends.items()):
        if end<=start:continue
        while end-start>maximum:
            result.append(dict(id=f'u{len(result):05d}',start=start,end=start+maximum,kind='forced_atom_split'));start+=maximum
        result.append(dict(id=f'u{len(result):05d}',start=start,end=end,kind=kind));start=end
    return result

def unit_windows(units,max_chars=1200,max_units=20):
    result=[];current=[]
    for unit in units:
        need(unit['end']-unit['start']<=max_chars,'input_overflow','Unit exceeds window size')
        if current and (unit['end']-current[0]['start']>max_chars or len(current)>=max_units):result.append(current);current=[]
        current.append(unit)
    if current:result.append(current)
    return result

def recursive(text,start=0,end=None,maximum=400):
    end=len(text) if end is None else end;result=[]
    while start<end:
        limit=min(start+maximum,end)
        if limit==end:stop=end
        else:
            piece=text[start:limit];stop=None
            for pattern in (r'\n\s*\n',r'[.?!。！？](?=\s|$)\s*',r'\s+'):
                hits=[m.end() for m in re.finditer(pattern,text) if start<m.end()<=limit and m.start()>=start]
                if hits:stop=max(hits);break
            stop=stop or limit
        result.append((start,stop));start=stop
    return result

def structure(text,nodes,maximum=400):
    cuts=sorted({0,len(text)}|{n['heading']['start'] for n in nodes})
    need(all(0<=x<=len(text) for x in cuts),'invalid_offset','Structural boundary outside document')
    return [span for a,b in zip(cuts,cuts[1:]) for span in recursive(text,a,b,maximum)]

def semantic(units,vectors,maximum=400,minimum=100,threshold=.25):
    need(len(units)==len(vectors) and units,'invalid_vector','Unit/vector count mismatch')
    for v in vectors:
        need(v and all(type(x) in (int,float) and math.isfinite(x) for x in v) and math.hypot(*v)>0,'invalid_vector','Invalid semantic vector')
    need(len({len(v) for v in vectors})==1,'invalid_vector','Semantic dimensions differ')
    out=[];start=units[0]['start'];distances=[]
    for i,u in enumerate(units):
        if not i:continue
        a,b=vectors[i-1],vectors[i];distance=1-sum(x*y for x,y in zip(a,b))/(math.hypot(*a)*math.hypot(*b))
        length_cut=u['end']-start>maximum;semantic_cut=u['start']-start>=minimum and distance>=threshold
        if length_cut or semantic_cut:out.append((start,u['start']));start=u['start']
        distances.append(dict(unit_id=u['id'],distance=distance,boundary=length_cut or semantic_cut,reason='maximum' if length_cut else 'semantic' if semantic_cut else None))
    out.append((start,units[-1]['end']));return out,distances

def extend(spans,overlap):
    return [(max(spans[i-1][0],a-overlap) if i else a,b) for i,(a,b) in enumerate(spans)]

def llm_payload(text,units,maximum=800):
    prompt=read_json(EXP/'prompt-contract.json');ids=[u['id'] for u in units]
    schema={'type':'object','additionalProperties':False,'required':['end_unit_ids'],'properties':{'end_unit_ids':{'type':'array','minItems':1,'uniqueItems':True,'items':{'type':'string','enum':ids}}}}
    enc=lambda x:json.dumps(x,ensure_ascii=False,separators=(',',':'))
    prefix=prompt['prefix'].replace('<=800 source characters',f'<={maximum} source characters')
    content=prefix+enc(schema)+'\nUnits:\n'+enc([dict(id=u['id'],start=u['start'],end=u['end'],text=text[u['start']:u['end']]) for u in units])
    template=read_json(EXP/'runtime-metadata.json')['/api/show:qwen3:4b']['template']
    upper=len(content.encode())+len(template.encode())+len(enc(schema).encode())+64
    need(upper+1024<=8192,'budget_unverified','Input upper bound plus output exceeds context')
    return dict(model='qwen3:4b',messages=[dict(role='user',content=content)],format=schema,stream=False,think=False,options=prompt['options']),upper

def parse_boundaries(response,units,maximum=800):
    need(response.get('model')=='qwen3:4b' and response.get('done') is True and response.get('done_reason')=='stop','incomplete_response','Expected completed stop response')
    value=strict(response.get('message',{}).get('content',''))
    need(isinstance(value,dict) and set(value)=={'end_unit_ids'},'invalid_boundaries','Response must contain only end_unit_ids')
    ids=value['end_unit_ids'];allowed=[u['id'] for u in units]
    need(isinstance(ids,list) and ids and all(type(x)==str and x in allowed for x in ids),'invalid_boundaries','Unknown/empty boundary IDs')
    indexes=[allowed.index(x) for x in ids];need(indexes==sorted(set(indexes)) and ids[-1]==allowed[-1],'invalid_boundaries','Unordered/duplicate/missing final boundary')
    start=units[0]['start'];spans=[]
    for i in indexes:
        end=units[i]['end'];need(0<end-start<=maximum,'invalid_boundaries','LLM span exceeds maximum');spans.append((start,end));start=end
    return spans

def llm_partition(text,units,provider,on_progress=lambda x:None,purpose='corpus',maximum=800):
    batches=unit_windows(units);need(len(batches)<=35,'input_overflow','Window budget exceeds frozen corpus')
    # Verify every window before the first paid/local inference call.
    payloads=[llm_payload(text,us,maximum) for us in batches]
    spans=[];records=[];started=time.monotonic()
    for i,us in enumerate(batches):
        payload,upper=payloads[i];record=dict(window_id=f'w{i:03d}',start=us[0]['start'],end=us[-1]['end'],input_upper_bound=upper,payload=payload,payload_sha256=fingerprint(payload),attempts=[])
        records.append(record)
        on_progress(dict(completed_windows=i,total_windows=len(batches),records=records,elapsed_seconds=time.monotonic()-started))
        for attempt in range(2):
            t=time.monotonic();response=None
            try:
                response=provider.call('llm',payload,purpose=purpose)
                selected=parse_boundaries(response,us,maximum)
                record['attempts'].append(dict(attempt=attempt+1,status='complete',content=response['message']['content'],usage={k:v for k,v in response.items() if k!='message'},wall_seconds=time.monotonic()-t))
                spans+=selected;record['selected_ends']=[b for a,b in selected];break
            except (ValueError,OSError) as exc:
                record['attempts'].append(dict(attempt=attempt+1,status='failed',reason=getattr(exc,'kind','invalid_json'),error=str(exc),content=response.get('message',{}).get('content') if response else None,wall_seconds=time.monotonic()-t))
                on_progress(dict(completed_windows=i,total_windows=len(batches),records=records,elapsed_seconds=time.monotonic()-started))
                if attempt or getattr(exc,'kind','') in ('provider_unresolved','budget_exhausted'):raise
                time.sleep(2)
        on_progress(dict(completed_windows=i+1,total_windows=len(batches),records=records,elapsed_seconds=time.monotonic()-started))
    return spans,dict(windows=records,forced_window_boundaries=[us[-1]['end'] for us in batches[:-1]],independent_inference=True)

def make_chunks(row,text,nodes,units,cfg,base):
    need(base and base[0][0]==0 and base[-1][1]==len(text),'coverage','Partition endpoints')
    for a,b in base:need(type(a)==int and type(b)==int and 0<=a<b<=len(text),'coverage','Invalid base range')
    if cfg['method']!='fixed':need(all(a[1]==b[0] for a,b in zip(base,base[1:])),'coverage','Partition gaps/reorder')
    expanded=base if cfg['method']=='fixed' else extend(base,cfg['overlap_chars'])
    chunks=[];maps=[];skipped=[]
    for (a,b),(s,e) in zip(base,expanded):
        if not text[s:e].strip():skipped.append(dict(document_id=row['document_id'],start=s,end=e));continue
        identity=dict(document_id=row['document_id'],canonical_sha256=row['canonical_sha256'],algorithm_version='chunk-custom-v1' if custom(cfg) else 'chunk-experiment-v1',config=cfg,base_start=a,base_end=b,start=s,end=e)
        cid=cfg['method']+'-'+fingerprint(identity);pages=page_intersections(row['pages'],s,e)
        arts=[n for n in nodes if n['level']==4 and s<n['extent']['end'] and e>n['extent']['start']]
        title_paths=[n['title_path'] for n in arts];uri=f"synthetic://hr/source-v4/{row['document_id']}?chars={s}-{e}"
        chunks.append(dict(chunk_id=cid,document_id=row['document_id'],version=row['version'],title=arts[0]['title_path'][-1] if arts else row['title'],text=text[s:e],source=uri,synthetic=True))
        maps.append(dict(chunk_id=cid,**identity,pages=pages,title_paths=title_paths,article_ids=[n['id'] for n in arts],unit_ids=[u['id'] for u in units if s<u['end'] and e>u['start']],original_sha256=row['original_sha256'],text_sha256=fingerprint(text[s:e])))
    covered=union_length([(s,e) for s,e in expanded]);need(covered==len(text),'coverage','Whole document not covered')
    need(0<len(chunks)<=1000,'chunk_limit','Invalid chunk count')
    lengths=[len(x['text']) for x in chunks];emitted=sum(lengths);unique=union_length([(m['start'],m['end']) for m in maps])
    stats=dict(chunk_count=len(chunks),lengths=lengths,min=min(lengths),max=max(lengths),mean=statistics.mean(lengths),median=statistics.median(lengths),emitted_chars=emitted,unique_chars=unique,emitted_unique_ratio=emitted/unique,overlap_chars=emitted-unique,coverage_with_skipped=covered,canonical_chars=len(text),below_200_ratio=sum(n<200 for n in lengths)/len(lengths),chunks_per_unit=len(chunks)/len(units),base_lengths=[b-a for a,b in base])
    return chunks,dict(chunks=maps,skipped=skipped,base_spans=base,offset_unit='Unicode code point [start,end)',page_separator_note='Separators have no fake page'),stats

def build(cfg,output_dir=None,provider=None,parent=None,on_progress=lambda x:None,documents=None):
    cfg=checked_config(cfg);out=Path(output_dir) if output_dir else ARTIFACTS/new_id('chunk');started=time.monotonic();details={};parent_ids=[]
    need(not out.exists(),'output_exists','Output exists')
    with work_lock():
        row,text,sections=source(documents);units=boundary_units(text,sections['nodes'])
        need(units==read_json(EXP/'boundary-map.json')['units'],'boundary_mismatch','Boundary map differs from frozen plan')
        if parent:
            pm=load_run(parent);need(cfg['method'] in ('semantic','llm') and pm['config']==checked_config(without_overlap(cfg)) and pm['canonical_sha256']==row['canonical_sha256'],'stale','Invalid boundary parent')
            if custom(cfg):
                need(pm.get('code_hash')==code_hash(['chunk_core.py','source_io.py','experiment_common.py','model_runtime.py','chunk_settings.py']),'stale','Boundary parent code version differs')
                need(all(pm.get(key)==file_hash(EXP/name) for key,name in [('spec_sha256','spec.json'),('prompt_sha256','prompt-contract.json'),('runtime_lock_sha256','runtime-metadata.json')]),'stale','Boundary parent contract version differs')
                if cfg['method']=='llm':need(pm.get('effective_prompt_sha256')==fingerprint(read_json(EXP/'prompt-contract.json')['prefix'].replace('<=800 source characters',f"<={cfg['base_max_chars']} source characters")),'stale','Boundary parent prompt differs')
            base=[tuple(x) for x in read_json(Path(parent)/'source-map.json')['base_spans']];parent_ids=[pm['run_id']];details=dict(boundary_replay=True,model_calls=0,parent_run_id=pm['run_id'])
        elif cfg['method']=='fixed':base=list(windows(text,cfg['size_chars'],cfg['overlap_chars']))
        elif cfg['method']=='recursive':base=recursive(text,maximum=cfg['base_max_chars'])
        elif cfg['method']=='structure':base=structure(text,sections['nodes'],maximum=cfg['base_max_chars'])
        elif cfg['method']=='semantic':
            vectors,usage=(provider or Provider()).embed([text[u['start']:u['end']] for u in units]);base,distances=semantic(units,vectors,maximum=cfg['base_max_chars'],minimum=cfg.get('minimum_chars',100),threshold=cfg['distance_threshold']);details=dict(embedding=usage,distances=distances)
        elif cfg['method']=='llm':base,details=llm_partition(text,units,provider or Provider(),on_progress,maximum=cfg['base_max_chars'])
        chunks,maps,stats=make_chunks(row,text,sections['nodes'],units,cfg,base)
        # Keep LangChain orchestration request-local; the provider remains explicit and bounded.
        from langchain_core.runnables import RunnableLambda
        import os
        os.environ['LANGCHAIN_TRACING_V2']='false';os.environ['LANGSMITH_TRACING']='false'
        from langsmith import tracing_context
        def publish(_):
            run_id=out.name
            with atomic_directory(out) as target:
                (target/'chunks.jsonl').write_text(''.join(json.dumps(c,ensure_ascii=False,separators=(',',':'))+'\n' for c in chunks),encoding='utf-8')
                for name,value in [('source-map.json',maps),('statistics.json',stats),('boundary-details.json',details)]:write_json(target/name,value)
                m=dict(schema_version=1,run_id=run_id,status='complete',algorithm_version='chunk-custom-v1' if custom(cfg) else 'chunk-experiment-v1',created_at=time.time(),config=cfg,canonical_sha256=row['canonical_sha256'],input_manifest_sha256=file_hash(Path(documents) if documents else EXP.parents[1]/'data/source-v4/extracted/manifest.json'),
                    spec_sha256=file_hash(EXP/'spec.json'),prompt_sha256=file_hash(EXP/'prompt-contract.json'),runtime_lock_sha256=file_hash(EXP/'runtime-metadata.json'),parent_run_ids=parent_ids,code_hash=code_hash(['chunk_core.py','source_io.py','experiment_common.py','model_runtime.py','chunk_settings.py']),outputs={p.name:file_hash(p) for p in target.iterdir()},elapsed_ms=(time.monotonic()-started)*1000,counts={'chunks':len(chunks),'units':len(units)},text_version='canonical-slice-only-v1')
                if cfg['method']=='llm':
                    m['effective_prompt_sha256']=fingerprint(read_json(EXP/'prompt-contract.json')['prefix'].replace('<=800 source characters',f"<={cfg['base_max_chars']} source characters"))
                write_json(target/'manifest.json',m)
            return m
        with tracing_context(enabled=False):return RunnableLambda(publish,name='publish_verified_source_slices').invoke(None)
