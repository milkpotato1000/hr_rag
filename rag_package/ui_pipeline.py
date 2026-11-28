"""Translate registered workspace IDs into the same inputs used by the pipeline CLI."""
from . import pipeline
from .storage import require, write_json
from .ui_jobs import settings, question
from .ui_registry import exact


def prepare(jobs, value):
    exact(value, ('kind','request_id','input_ids','question','llm_config_id','chunk_config_id',
                  'retrieval','embedding_config_id','reranker_config_id','execute'))
    execute = value['execute']
    require(type(execute) is bool,'invalid_execute','input')
    question(value['question'])
    registry = jobs.registry
    inputs = registry.freeze_inputs(value['input_ids'])
    chunk, model = registry.chunk_config(value['chunk_config_id'])
    llm = jobs._llm(value['llm_config_id'],execute)
    retrieval = value['retrieval']
    template = dict(method='fixed',size_chars=400,overlap_chars=80)
    settings(template,retrieval)
    require('candidate_k' in retrieval and 'rrf_k' in retrieval,'candidate_depth_required','input')
    require(not execute or chunk['method'] not in ('llm','semantic') or jobs.allow_chunking,
            'chunking_execution_disabled','permission')
    embedding = None
    if retrieval['method']=='bm25':
        require(value['embedding_config_id'] is None,'unexpected_embedding_config','input')
    else:
        require(not execute or jobs.allow_retrieval,'retrieval_execution_required','permission')
        embedding=registry.embedding(value['embedding_config_id'])
    scorer = None
    if value['reranker_config_id'] is not None:
        require(not execute or jobs.allow_reranking,'reranking_execution_disabled','permission')
        scorer=registry.reranker(value['reranker_config_id'])
    return dict(inputs=inputs,chunk=chunk,chunk_model=model,chunking=template,llm=llm,
                retrieval=retrieval,embedding=embedding,scorer=scorer)


def execute(jobs, value, plan, work):
    sources=jobs._sources(work,plan['inputs'])
    search=jobs._config(work,plan)
    cfg=dict(plan['chunk'])
    for key in ('embedding_config','llm_config'):
        if key in cfg:
            cfg[key]='boundary-model.json'
            write_json(work/cfg[key],plan['chunk_model'])
    write_json(work/'chunk.json',cfg)
    profile=None
    if plan['scorer']:
        profile=work/'reranker.json'
        write_json(profile,plan['scorer'])
    out=work/'result'
    result=pipeline.run(sources,work/'chunk.json',search,value['question'],out,
                        execute=value['execute'],reranker_profile=profile,transport=jobs.transport,
                        key_resolver=jobs.key_resolver,embedding_backend=jobs.embedding_backend,
                        reranker_backend=jobs.reranker_backend)
    key=jobs.registry.add_artifact(out,'pipeline',label=value['question'],status=result['status'])
    return [key],'failed' if result['status']=='failed' else 'completed',result
