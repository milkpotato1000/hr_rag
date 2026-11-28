"""Registered immutable chunk settings; browser cannot supply paths or credentials."""
from pathlib import Path
from . import chunk_artifact,chunk_policy,rag,retrieval
from .storage import require,read_json,write_json,fingerprint
from .ui_registry import exact
from .ui_jobs import settings,question
from .documents import safe_id,load_snapshot


def prepare(jobs,v):
    r=jobs.registry;k=v['kind'];common=('request_id','kind');plan={}
    if k in ('chunk','chunk_derive'):
        exact(v,(*common,'chunk_config_id', 'snapshot_id' if k=='chunk' else 'chunk_id'),('execute_chunking',))
        cfg,model=r.chunk_config(v['chunk_config_id']);enabled=v.get('execute_chunking',False);require(type(enabled) is bool,'invalid_execute_chunking','input')
        if enabled:require(jobs.allow_chunking and k=='chunk','chunking_execution_disabled','permission')
        path,e,m=r.artifact(v['snapshot_id'] if k=='chunk' else v['chunk_id'])
        if k=='chunk':
            path,_=r.snapshot_for(v['snapshot_id']);m=load_snapshot(path)[0];e={'kind':'snapshot'}
        else:require(e['kind']=='chunks','wrong_artifact_kind','input');chunk_artifact.load(path)
        return {'input':str(path),'input_kind':e['kind'],'input_fingerprint':m['fingerprint'],'config':cfg,'model':model}
    if k=='chunk_build':
        exact(v,(*common,'chunk_id','retrieval','llm_config_id'),('execute_retrieval','embedding_config_id'))
        path,e,m=r.artifact(v['chunk_id']);require(e['kind']=='chunks','wrong_artifact_kind','input');chunk_artifact.load(path)
        settings({'method':'fixed','size_chars':100,'overlap_chars':0},v['retrieval'])
        require('candidate_k' in v['retrieval'],'candidate_depth_required','input')
        return {'input':str(path),'input_kind':'chunks','input_fingerprint':m['fingerprint'],'chunk_artifact':str(path),'chunking':{},'retrieval':v['retrieval'],'llm':jobs._llm(v['llm_config_id'],False),'embedding':jobs._embedding(v,v['retrieval'])}
    exact(v,(*common,'chunk_ids','retrieval','llm_config_id','questions','execute'),('execute_retrieval','embedding_config_id','facts_id'))
    require(type(v['execute']) is bool and isinstance(v['chunk_ids'],list) and 2<=len(v['chunk_ids'])<=5 and len(set(v['chunk_ids']))==len(v['chunk_ids']),'comparison_limit','input')
    require(isinstance(v['questions'],list) and 1<=len(v['questions'])<=20,'question_limit','input');seen=set()
    for q in v['questions']:
        exact(q,('id','question'));require(safe_id(q['id']) and q['id'] not in seen,'invalid_question_id','input');seen.add(q['id']);question(q['question'])
    settings({'method':'fixed','size_chars':100,'overlap_chars':0},v['retrieval']);require('candidate_k' in v['retrieval'],'candidate_depth_required','input')
    ps=[]
    for id in v['chunk_ids']:
        path,e,m=r.artifact(id);require(e['kind']=='chunks','wrong_artifact_kind','input');cr,_,_,_=chunk_artifact.load(path)
        ps.append({'path':str(path),'fingerprint':m['fingerprint'],'source':cr['source_fingerprint']})
    require(len({p['source'] for p in ps})==1,'stale_chunk_source','input')
    return {'chunks':ps,'retrieval':v['retrieval'],'llm':jobs._llm(v['llm_config_id'],v['execute']),'embedding':jobs._embedding(v,v['retrieval']),'facts':r.label('facts',v.get('facts_id'))}


def execute(jobs,v,plan,work):
    from .storage import verify
    r=jobs.registry;k=v['kind'];out=work/'result'
    if 'input' in plan:require(verify(plan['input'],plan['input_kind'])['fingerprint']==plan['input_fingerprint'],'stale_chunk_input','jobs')
    if k in ('chunk','chunk_derive'):
        cfg=dict(plan['config'])
        for key in ('embedding_config','llm_config'):
            if key in cfg:
                write_json(work/'model.json',plan['model']);cfg[key]='model.json'
        write_json(work/'chunk.json',cfg)
        result=chunk_artifact.build(plan['input'],work/'chunk.json',out,execute=v.get('execute_chunking',False),embedding_backend=jobs.embedding_backend,transport=jobs.transport,key_resolver=jobs.key_resolver) if k=='chunk' else chunk_artifact.derive(plan['input'],work/'chunk.json',out)
        if result['status'] in ('failed','interrupted'):return [],'failed',result
        kind='chunks' if result['status']=='ready' else 'chunk-preview'
        return [r.add_artifact(out,kind)],'completed',dict(result,dispatch_attempted=bool(result['work'].get('boundary_model_jobs')))
    if k=='chunk_build':
        cfg=jobs._config(work,plan);retrieval.build(Path(plan['input'])/'snapshot',cfg,out,execute_retrieval=v.get('execute_retrieval',False),embedding_backend=jobs.embedding_backend)
        return [r.add_artifact(out,'build',snapshot_id=v['chunk_id'])],'completed',{}
    paths=[]
    for n,entry in enumerate(plan['chunks']):
        require(verify(entry['path'],'chunks')['fingerprint']==entry['fingerprint'],'stale_chunk_input','jobs')
        paths.append(jobs._config(work,dict(plan,chunking={},chunk_artifact=entry['path']),f'settings-{n}'))
    write_json(work/'questions.json',v['questions'])
    result=rag.compare(Path(plan['chunks'][0]['path'])/'snapshot',paths,work/'questions.json',out,execute=v['execute'],execute_retrieval=v.get('execute_retrieval',False),embedding_backend=jobs.embedding_backend,transport=jobs.transport,key_resolver=jobs.key_resolver,facts=plan['facts'])
    builds={};answers={}
    for row in result['rows']:
        if 'result_path' not in row:continue
        cid=row['config_id']
        if cid not in builds:builds[cid]=r.add_artifact(out/cid/'build','build',snapshot_id=v['chunk_ids'][0])
        answers[cid+'/'+row['question_id']]=r.add_artifact((out/row['result_path']).parent,'answer',snapshot_id=v['chunk_ids'][0],build_id=builds[cid])
    id=r.add_artifact(out,'comparison',snapshot_id=v['chunk_ids'][0],build_ids=builds,answer_ids=answers,labels=[f"{c['config'].get('heading_profile', c['config']['method'])} / {c['config']['size_chars']}자 / 중첩 {c['config']['overlap_chars']}" for c in result['chunk_artifacts']])
    return [id],'completed',dict(result,dispatch_attempted=bool(result['generation_requests']))
