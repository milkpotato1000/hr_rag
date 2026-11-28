"""Frozen chunk boundaries and durable, non-resumable model invocations (P030)."""
import copy,json,math,struct,time,uuid
from pathlib import Path
from . import chunk_policy as policy,embedding,llm
from .chunks import make_chunks,rule_settings
from .documents import load_snapshot
from .storage import RagError,require,digest,fingerprint,read_json,write_json,verify,seal,staging,new_output
from .ui_registry import atomic_json
from .llm.transport import http_transport,TransportError


def quantize(vectors):
    raw=b''.join(struct.pack('<'+str(len(v))+'f',*v) for v in vectors)
    return raw,unpack(raw,len(vectors),len(vectors[0]) if vectors else 0)


def unpack(raw,count,dimension):
    require(type(count) is int and type(dimension) is int and count>=0 and dimension>0 and len(raw)==count*dimension*4,'invalid_unit_vectors','chunking')
    vs=[list(struct.unpack_from('<'+str(dimension)+'f',raw,n*dimension*4)) for n in range(count)]
    require(all(all(math.isfinite(x) for x in v) and abs(math.hypot(*v)-1)<1e-4 for v in vs),'invalid_unit_vectors','chunking');return vs


def stats(chunks,maps,units):
    lengths=[len(c['text']) for c in chunks];intervals={}
    for c in chunks:intervals.setdefault(c['document_id'],[]).append((c['start'],c['end']))
    unique=0
    for ranges in intervals.values():
        cursor=0
        for a,b in sorted(ranges):unique+=max(0,b-max(a,cursor));cursor=max(cursor,b)
    return {'chunk_count':len(chunks),'unit_count':len(units),'lengths':lengths,'min':min(lengths,default=0),'max':max(lengths,default=0),
            'mean':sum(lengths)/len(lengths) if lengths else 0,'emitted_chars':sum(lengths),'unique_chars':unique,'duplicate_chars':sum(lengths)-unique,
            'forced_units':sum(u['reason']=='forced_unit_split' for u in units),'token_count':None,'token_status':'unmeasured; character/byte limits do not guarantee model context window'}


def preflight(snapshot_dir,config_path):
    sm,docs=load_snapshot(snapshot_dir);c,model=policy.read_config(config_path);cfg=policy.effective(c,model);method=c['method']
    us=policy.units(docs,sm['fingerprint'],c.get('unit_max_chars',min(400,c['size_chars'])))
    require(len(us)<=5000,'unit_limit','chunking');records=[]
    if method=='semantic':require(len(us)<=model['max_chunks'],'embedding_chunk_limit','chunking')
    if method=='llm':
        batches=policy.windows(us,c['window_max_chars'],c['window_max_units']);require(len(batches)<=c['max_windows'],'window_limit','chunking')
        for n,batch in enumerate(batches):
            messages,choice=policy.window_input(batch,c)
            schema=policy.choice_schema(c,cfg['model']['profile'],choice)
            preview=llm.preview(model,'chunking',messages,response_schema=schema)
            size=len(json.dumps(preview['body'],ensure_ascii=False,allow_nan=False).encode())
            require(size<=c['max_prompt_bytes'],'prompt_bytes_limit','chunking')
            records.append({**choice,'window_id':f'w{n:03d}','unit_ids':[u['id'] for u in batch],'messages':messages,'request':preview,'request_bytes':size,'token_count':None,'status':'pending','response':None,'selected_end_ids':None,'dispatch_attempted':False,'outcome_unknown':False})
    # Upper bound of one chunk per unit; rule methods are also computed before any model call.
    if method in ('fixed','recursive','structure'):
        chunks,maps=make_chunks(docs,sm['fingerprint'],rule_settings(c),max_chunks=10000);require(len(chunks)<=10000,'chunk_limit','chunking')
    return sm,docs,c,model,cfg,us,records


def publish(out,snapshot_dir,cfg,unit_policy,base_policy,us,base,details,work,raw=None,parent=None,before_publish=None):
    from .candidates import copy_artifact
    sm,docs=load_snapshot(snapshot_dir)
    if cfg['method'] in ('fixed','recursive','structure'):
        chunks,maps=make_chunks(docs,sm['fingerprint'],rule_settings(cfg),max_chunks=10000)
    else:chunks,maps=policy.emit(docs,sm['fingerprint'],cfg,base)
    require(len(chunks)<=10000,'chunk_limit','chunking')
    r={'schema_version':1,'source_fingerprint':sm['fingerprint'],'config':cfg,'unit_policy':unit_policy,'base_policy':base_policy,'base':base,'details':details,'work':copy.deepcopy(work),
       'parent_fingerprint':parent,'statistics':stats(chunks,maps,us),'units_hash':fingerprint(us),'chunks_hash':fingerprint(chunks),'coverage_hash':fingerprint(maps),
       'vectors_hash':digest(raw) if raw is not None else None,'unit_order_hash':fingerprint([u['id'] for u in us]),'algorithm':policy.MODEL_ALGORITHM}
    r['chunk_fingerprint']=fingerprint(r)
    with staging(out) as tmp:
        copy_artifact(snapshot_dir,tmp/'snapshot','snapshot');write_json(tmp/'units.json',us);write_json(tmp/'chunks.json',chunks);write_json(tmp/'coverage.json',maps);write_json(tmp/'chunk.json',r)
        if raw is not None:(tmp/'unit-vectors.f32').write_bytes(raw)
        seal(tmp,{'schema_version':1,'kind':'chunks','status':'ready','source_fingerprint':sm['fingerprint'],'chunk_fingerprint':r['chunk_fingerprint']})
        load(tmp)
        if before_publish is not None:before_publish(r)
    return {'status':'ready','chunk_fingerprint':r['chunk_fingerprint'],'statistics':r['statistics'],'work':r['work']}


def build(snapshot_dir,config_path,out,*,execute=False,embedding_backend=None,transport=None,key_resolver=None):
    new_output(out);sm,docs,c,model,cfg,us,records=preflight(snapshot_dir,config_path)
    method=c['method'];unit_policy={'version':policy.UNIT_VERSION,'maximum':c.get('unit_max_chars',min(400,c['size_chars']))};base_policy=dict(cfg)
    work={'execution_kind':'test_fixture' if embedding_backend or transport else 'offline' if method in ('fixed','recursive','structure') else 'local_hf' if method=='semantic' else 'live',
          'boundary_model_jobs':0,'boundary_attempts':0,'unit_observation':{},'requested_windows':len(records),'dispatches':0,'successful_windows':0,'failed_windows':0,'unknown_windows':0,'retry_count':0,'cost':None,'cost_status':'unmeasured','unit_embedding':None,'usage':{'input_tokens':None,'output_tokens':None},'elapsed_ms':0}
    if method in ('semantic','llm') and not execute:
        from .candidates import copy_artifact
        result={'status':'preview','config':cfg,'source_fingerprint':sm['fingerprint'],'units':us,'requests':records,'expected_unit_embeddings':len(us) if method=='semantic' else 0,'work':dict(work,execution_kind='preview'),'token_count':None}
        with staging(out) as tmp:
            copy_artifact(snapshot_dir,tmp/'snapshot','snapshot');write_json(tmp/'preview.json',result);seal(tmp,{'schema_version':1,'kind':'chunk-preview','status':'preview','source_fingerprint':sm['fingerprint']})
        return result
    # Sibling diagnostic directory survives failed publication and is never a ready artifact.
    invocation=Path(out).absolute().parent/(Path(out).name+'.invocation-'+uuid.uuid4().hex);invocation.mkdir(parents=True)
    diagnostic={'schema_version':1,'status':'prepared','source_fingerprint':sm['fingerprint'],'config':cfg,'windows':records,'work':work,'error':None,'outcome_unknown':False}
    state_path=invocation/'invocation.json';atomic_json(state_path,diagnostic);started=time.monotonic();base=[];details={};raw=None
    def persist():
        work['elapsed_ms']=(time.monotonic()-started)*1000
        for key in work['usage']:
            values=[r['response']['usage'][key] for r in records if r['dispatch_attempted'] and r.get('response')]
            work['usage'][key]=sum(values) if values and len(values)==work['dispatches'] and all(v is not None for v in values) else None
        atomic_json(state_path,diagnostic)
    try:
        diagnostic['status']='running';persist()
        if method=='semantic':
            work['boundary_attempts']=1;persist()
            from .reranker import SDK_VERSIONS
            vectors,ew=embedding.encode(model,[u['text'] for u in us],[u['id'] for u in us],'document',execute=True,backend=embedding_backend,allow_whitespace=True,observation=work['unit_observation'],expected_sdk=SDK_VERSIONS)
            work['boundary_model_jobs']=work['unit_observation'].get('workers_started',0)+work['unit_observation'].get('backend_calls',0)
            raw,vectors=quantize(vectors);work['unit_embedding']=ew
            base,distances=policy.semantic(us,vectors,c['size_chars']-c['overlap_chars'],c['minimum_chars'],c['distance_threshold'])
            details={'distances':distances,'dimension':model['catalog']['dimension'] if 'catalog' in model else embedding.CATALOG[model['model_id']]['dimension'],'sdk_versions':ew['sdk_versions'],'unit_vector_execution_kind':ew['execution_kind']}
        elif method=='llm':
            byid={u['id']:u for u in us};deadline=time.monotonic()+c['total_timeout_seconds'];send=transport or http_transport
            for record in records:
                remaining=deadline-time.monotonic();require(remaining>0,'total_deadline_exceeded','chunking')
                record['status']='in_progress';persist();batch=[byid[i] for i in record['unit_ids']]
                if record.get('selection_reason')=='single_candidate':
                    candidate=record['candidates'][0]
                    base.extend(policy.parse({'end_unit_ids':candidate['end_unit_ids']},batch,c['size_chars']-c['overlap_chars']))
                    record.update(status='complete',selected_candidate_id=candidate['id'],selected_end_ids=candidate['end_unit_ids'])
                    work['successful_windows']+=1
                    persist()
                    continue
                def bounded_send(method,url,headers,body,timeout):
                    remaining=deadline-time.monotonic()
                    if remaining<=0:raise TransportError('timeout',outcome_unknown=False)
                    if method=='POST':
                        record['status']='dispatch_prepared';persist()
                        remaining=deadline-time.monotonic()
                        if remaining<=0:raise TransportError('timeout',outcome_unknown=False)
                        # The durable intent precedes send; counters describe calls actually entered.
                        record['dispatch_attempted']=True;record['outcome_unknown']=True;work['dispatches']+=1;work['boundary_model_jobs']+=1;record['status']='in_progress'
                    try:result=send(method,url,headers,body,min(timeout,remaining))
                    except TransportError as error:
                        if method=='POST':record['outcome_unknown']=error.outcome_unknown
                        raise
                    if method=='POST':record['outcome_unknown']=False
                    if time.monotonic()>deadline:raise TransportError('timeout',outcome_unknown=False)
                    return result
                schema=policy.choice_schema(c,cfg['model']['profile'],record)
                response=llm.invoke(model,'chunking',record['messages'],transport=bounded_send,key_resolver=key_resolver,response_schema=schema)
                # P025 rejects hidden thinking. Keep normalized diagnostic content, never use it as chunk text.
                record['response']=response
                if not record['dispatch_attempted']:record['outcome_unknown']=False
                require(response['request_fingerprint']==record['request']['request_fingerprint'],'request_identity_changed','chunking')
                require(response['status']=='complete','chunking_provider_'+response['status'],'chunking')
                if 'candidates' in record:
                    resolved=policy.chosen_ends(response['parsed_json'],record['candidates'])
                    record['selected_candidate_id']=response['parsed_json']['candidate_id']
                else:resolved=policy.resolve_response(response['parsed_json'],batch,c.get('id_representation','persistent'))
                selected=policy.parse(resolved,batch,c['size_chars']-c['overlap_chars']);base.extend(selected)
                record.update(status='complete',selected_end_ids=resolved['end_unit_ids']);work['successful_windows']+=1;persist()
            details={'prompt_version':policy.prompt_version(c),'windows':[{**{key:r[key] for key in ('candidates','selection_reason','selected_candidate_id') if key in r},'window_id':r['window_id'],'unit_ids':r['unit_ids'],'selected_end_ids':r['selected_end_ids'],'actual_messages_hash':r['request']['actual_messages_hash'],'request_fingerprint':r['request']['request_fingerprint']} for r in records]}
        work['elapsed_ms']=(time.monotonic()-started)*1000
        def prepared(r):
            diagnostic.update(status='publication_prepared',artifact_fingerprint=r['chunk_fingerprint']);persist()
        result=publish(out,snapshot_dir,cfg,unit_policy,base_policy,us,base,details,work,raw,before_publish=prepared)
        # Publication is the commit point. A journal acknowledgement failure cannot undo it.
        diagnostic['status']='complete'
        try:persist()
        except (OSError,UnicodeError):result['diagnostic_status']='publication_prepared; ready artifact is authoritative'
        return dict(result,invocation_path=str(invocation))
    except (Exception,KeyboardInterrupt) as e:
        obs=work['unit_observation'];work['boundary_model_jobs']=work['dispatches']+obs.get('workers_started',0)+obs.get('backend_calls',0)
        for r in records:
            if r['status'] in ('in_progress','dispatch_prepared'):r['status']='interrupted' if isinstance(e,KeyboardInterrupt) else 'failed';work['failed_windows']+=1
        diagnostic['failed_window']=next((r['window_id'] for r in records if r['status'] in ('failed','interrupted')),None)
        work['unknown_windows']=sum(r['outcome_unknown'] for r in records);diagnostic.update(status='interrupted' if isinstance(e,KeyboardInterrupt) else 'failed',error={'code':getattr(e,'code','chunking_write_or_internal_error')},outcome_unknown=bool(work['unknown_windows']))
        try:persist()
        except (OSError,UnicodeError):pass  # Earlier durable in_progress is intentionally not silently resumed.
        return {'status':diagnostic['status'],'error':diagnostic['error'],'invocation_path':str(invocation),'work':work,'dispatch_attempted':bool(work['dispatches'] or work['boundary_model_jobs']),'outcome_unknown':diagnostic['outcome_unknown']}


def load(root):
    root=Path(root);m=verify(root,'chunks');r=read_json(root/'chunk.json');us=read_json(root/'units.json');sm,docs=load_snapshot(root/'snapshot')
    require(isinstance(r,dict) and set(r)=={'schema_version','source_fingerprint','config','unit_policy','base_policy','base','details','work','parent_fingerprint','statistics','units_hash','chunks_hash','coverage_hash','vectors_hash','unit_order_hash','algorithm','chunk_fingerprint'} and type(r['schema_version']) is int and r['schema_version']==1 and r['algorithm']==policy.MODEL_ALGORITHM and m['identity'].get('status')=='ready','invalid_chunk_artifact','chunking')
    require(r['chunk_fingerprint']==fingerprint({k:v for k,v in r.items() if k!='chunk_fingerprint'})==m['identity']['chunk_fingerprint'],'stale_chunk_artifact','chunking')
    require(r['source_fingerprint']==sm['fingerprint']==m['identity']['source_fingerprint'],'stale_chunk_source','chunking')
    require(r['unit_policy']['version']==policy.UNIT_VERSION and us==policy.units(docs,sm['fingerprint'],r['unit_policy']['maximum']) and fingerprint(us)==r['units_hash'],'stale_units','chunking')
    require(fingerprint([u['id'] for u in us])==r['unit_order_hash'],'stale_unit_order','chunking')
    cfg=policy.validate_effective(r['config']);method=cfg['method'];base=r['base'];bp=policy.validate_effective(r['base_policy'])
    require(set(r['unit_policy'])=={'version','maximum'} and type(r['unit_policy']['maximum']) is int and 1<=r['unit_policy']['maximum']<=400,'invalid_unit_policy','chunking')
    if method in ('semantic','llm'):
        require(bp['method']==method and bp['model']==cfg['model'] and bp['unit_max_chars']==cfg['unit_max_chars']==r['unit_policy']['maximum'],'stale_base_policy','chunking')
        require(all(bp[k]==cfg[k] for k in cfg if k not in ('size_chars','overlap_chars')),'stale_base_policy','chunking')
    if r['parent_fingerprint'] is None:require(bp==cfg,'stale_initial_policy','chunking')
    if method=='semantic':
        from .reranker import SDK_VERSIONS
        require(isinstance(r['details']['sdk_versions'],dict) and all(isinstance(k,str) and isinstance(v,str) for k,v in r['details']['sdk_versions'].items()),'invalid_unit_sdk','chunking')
        if r['details']['unit_vector_execution_kind']=='local_hf':require(r['details']['sdk_versions']==SDK_VERSIONS,'stale_unit_sdk','chunking')
        else:require(r['details']['unit_vector_execution_kind']=='test_fixture','invalid_unit_execution_kind','chunking')
        raw=(root/'unit-vectors.f32').read_bytes();require(digest(raw)==r['vectors_hash'],'stale_unit_vectors','chunking')
        vectors=unpack(raw,len(us),r['details']['dimension']);expected,distances=policy.semantic(us,vectors,bp['size_chars']-bp['overlap_chars'],bp['minimum_chars'],bp['distance_threshold'])
        require(base==expected and r['details']['distances']==distances,'stale_semantic_boundaries','chunking')
    elif method=='llm':
        require(r['details']['prompt_version']==policy.prompt_version(bp),'stale_prompt_version','chunking')
        byid={u['id']:u for u in us};expected=[];flat=[]
        batches=policy.windows(us,bp['window_max_chars'],bp['window_max_units'])
        require(len(batches)==len(r['details']['windows'])<=bp['max_windows'],'stale_windows','chunking')
        for n,(batch,w) in enumerate(zip(batches,r['details']['windows'])):
            messages,choice=policy.window_input(batch,bp)
            if choice:
                require(all(w.get(key)==value for key,value in choice.items()),'stale_partition_candidates','chunking')
                chosen=policy.chosen_ends({'candidate_id':w.get('selected_candidate_id')},choice['candidates'])
                require(chosen['end_unit_ids']==w['selected_end_ids'],'stale_partition_selection','chunking')
            schema=policy.choice_schema(bp,bp['model']['profile'],choice)
            request=llm.preview(policy.saved_llm(bp['model']),'chunking',messages,response_schema=schema)
            require(w['window_id']==f'w{n:03d}' and w['unit_ids']==[u['id'] for u in batch] and w['actual_messages_hash']==request['actual_messages_hash'] and w['request_fingerprint']==request['request_fingerprint'],'stale_window_request','chunking')
            require(len(json.dumps(request['body'],ensure_ascii=False,allow_nan=False).encode())<=bp['max_prompt_bytes'],'prompt_bytes_limit','chunking')
            batch=[byid.get(i) for i in w['unit_ids']];require(all(x is not None for x in batch),'stale_window_units','chunking');flat.extend(w['unit_ids'])
            expected+=policy.parse({'end_unit_ids':w['selected_end_ids']},batch,bp['size_chars']-bp['overlap_chars'])
        require(flat==[u['id'] for u in us] and base==expected,'stale_llm_boundaries','chunking')
    require(method in ('fixed','recursive','structure','semantic','llm'),'unsupported_chunking','chunking')
    if method in ('fixed','recursive','structure'):chunks,maps=make_chunks(docs,sm['fingerprint'],rule_settings(cfg),max_chunks=10000)
    else:chunks,maps=policy.emit(docs,sm['fingerprint'],cfg,base)
    require(chunks==read_json(root/'chunks.json') and maps==read_json(root/'coverage.json') and fingerprint(chunks)==r['chunks_hash'] and fingerprint(maps)==r['coverage_hash'],'stale_emitted_chunks','chunking')
    require(r['statistics']==stats(chunks,maps,us),'stale_chunk_statistics','chunking')
    return r,docs,chunks,maps


def replay(root):
    r,_,_,_=load(root);return {'status':'ready','chunk_fingerprint':r['chunk_fingerprint'],'model_calls':0,'statistics':r['statistics'],'config':r['config'],'work':r['work']}


def derive(root,config_path,out):
    new_output(out);r,_,_,_=load(root);c,model=policy.read_config(config_path);cfg=policy.effective(c,model);old=r['config']
    require(cfg['method']==old['method'],'derive_requires_new_execution','chunking');method=cfg['method'];us=read_json(Path(root)/'units.json')
    if method in ('semantic','llm'):
        require(cfg['model']==old['model'] and cfg['unit_max_chars']==old['unit_max_chars'],'derive_requires_new_execution','chunking')
    base=r['base'];details=copy.deepcopy(r['details']);bp=r['base_policy'];raw=None
    if method=='semantic':
        require(all(u['end']-u['start']<=c['size_chars']-c['overlap_chars'] for u in us),'derive_requires_new_unitization','chunking')
        raw=(Path(root)/'unit-vectors.f32').read_bytes();vectors=unpack(raw,len(us),details['dimension'])
        if any(cfg[k]!=old[k] for k in ('size_chars','minimum_chars','distance_threshold')):
            base,details['distances']=policy.semantic(us,vectors,c['size_chars']-c['overlap_chars'],c['minimum_chars'],c['distance_threshold']);bp=cfg
    elif method=='llm':
        require(all(cfg[k]==old[k] for k in old if k not in ('size_chars','overlap_chars')),'derive_requires_new_execution','chunking')
    work={'execution_kind':'derived','parent_execution_kind':r['work']['execution_kind'],'origin_execution_kind':r['work'].get('origin_execution_kind',r['work']['execution_kind']),'boundary_model_jobs':0,'dispatches':0,'unit_embedding':None,'retry_count':0,'cost':None}
    return publish(out,Path(root)/'snapshot',cfg,r['unit_policy'],bp,us,base,details,work,raw,parent=r['chunk_fingerprint'])
