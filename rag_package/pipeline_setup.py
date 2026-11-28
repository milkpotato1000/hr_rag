"""Assemble an offline pipeline selection using installed model profiles."""
from pathlib import Path
import shlex
import os

from . import chunk_policy, embedding, reranker, retrieval
from .documents import MAX_BYTES
from .llm.config import string, validate_config
from .llm.core import configuration_required
from .storage import read_json, require, staging, write_json, digest
from .ui_registry import bounded, contained, validate_upload
from .ui_jobs import question as validate_question


HANDBOOK_QUESTION = '생일 특별휴가를 신청하면 누구의 승인을 받아야 하나요?'


def checked_model(path, role):
    module = embedding if role == 'embedding' else reranker
    profile = module.read_profile(path)
    module.check_files(profile)
    return profile


def prepare_document(stage, document, title, synthetic):
    source=Path(document)
    fmt=source.suffix.lower().lstrip('.')
    require(fmt in ('pdf','txt','md'),'unsupported_source','setup')
    require(source.is_file(),'source_unreadable','setup')
    title=string(source.name if title is None else title,'document.title')
    raw=bounded(source,MAX_BYTES)
    validate_upload(fmt,raw)
    checksum=digest(raw)
    filename='original.'+fmt
    (stage/filename).write_bytes(raw)
    record=dict(document_id='local-'+checksum[:24],title=title,synthetic=synthetic,format=fmt,path=filename)
    write_json(stage/'sources.json',dict(schema_version=1,documents=[record]))
    provenance=dict(record,original_name=source.name,original_sha256=checksum,bytes=len(raw))
    write_json(stage/'source-info.json',provenance)
    return provenance


def setup(llm_config, chunk_config, method, out, *, embedding_config=None,
          reranker_config=None, top_k=5, candidate_k=20, budget=4000, size_chars=None, overlap_chars=None, document=None, title=None, synthetic=False, question=None):
    workspace = Path.cwd()
    out = contained(workspace, out)
    require(method in ('bm25', 'dense', 'hybrid'), 'unsupported_retrieval', 'setup')
    require(method == 'bm25' or embedding_config, 'embedding_config_required', 'setup')
    require(method != 'bm25' or not embedding_config, 'unexpected_embedding_config', 'setup')
    require(1 <= top_k <= candidate_k <= 100, 'invalid_candidate_depth', 'setup')
    require(1 <= budget <= 64000, 'invalid_context_budget', 'setup')
    sources = 'handbook-sources.json'
    if document is None:
        require(title is None and not synthetic,'document_required','setup')
        require((workspace/sources).is_file(), 'handbook_sources_missing', 'setup')
    else:
        require(question is not None,'question_required','setup')
    question=HANDBOOK_QUESTION if question is None else question.strip()
    validate_question(question)
    source_info=None
    controls = dict(method=method, top_k=top_k, candidate_k=candidate_k, rrf_k=60, context_budget_chars=budget)
    selection = {}
    with staging(out) as stage:
        if document is not None:
            source_info=prepare_document(stage,document,title,synthetic)
            sources=str(out.relative_to(workspace)/'sources.json')
        llm = validate_config(read_json(llm_config))
        generation = llm['profiles'][llm['roles']['generation']]
        require(generation['response_mode']=='json_object', 'json_object_required', 'setup')
        # Reuse the installed generation profile across presets so changing
        # retrieval does not consume another UI model registration.
        model_path=Path(llm_config).absolute()
        if model_path.is_relative_to(workspace):
            model_path=contained(workspace,model_path)
            model_reference=os.path.relpath(model_path,out)
        else:
            model_path=out/'model.json'
            model_reference='model.json'
            write_json(stage/model_reference,llm)
        chunk, boundary = chunk_policy.read_config(chunk_config)
        if size_chars is not None or overlap_chars is not None:
            if size_chars is not None:
                chunk['size_chars'] = size_chars
            if overlap_chars is not None:
                chunk['overlap_chars'] = overlap_chars
            chunk = chunk_policy.config(chunk)
        if chunk['method']=='semantic':
            embedding.check_files(boundary)
            write_json(stage/'boundary.json', boundary)
            chunk['embedding_config']='boundary.json'
        if chunk['method']=='llm':
            write_json(stage/'boundary.json', boundary)
            chunk['llm_config']='boundary.json'
        write_json(stage/'chunk.json', chunk)
        for role, path in (('embedding', embedding_config), ('reranker', reranker_config)):
            if path:
                p = checked_model(path, role)
                write_json(stage/(role+'.json'), p)
                selection[role] = {'model_id':p['model_id'], 'revision':p['revision']}
        # The pipeline builds its actual chunks from --chunk-config, including
        # model-based boundaries. The search template still needs rule settings.
        template = {k:chunk[k] for k in ('method','size_chars','overlap_chars')}
        if template['method'] in ('llm','semantic'):
            template['method']='fixed'
        if 'heading_profile' in chunk:
            template['heading_profile']=chunk['heading_profile']
        write_json(stage/'search.json',dict(schema_version=2, chunking=template, retrieval=controls,
                   llm_config=model_reference, embedding_config='embedding.json' if embedding_config else None))
        retrieval.config(stage/'search.json')
    folder=out.relative_to(workspace)
    preview=['rag-lab','pipeline','--sources',sources,'--chunk-config',str(folder/'chunk.json'),
             '--search-config',str(folder/'search.json'),'--question='+question,
             '--out',str(folder.with_name(folder.name+'-preview'))]
    serve=['rag-lab','serve','--workspace','.','--sources',sources,'--llm-config',str(model_path.relative_to(workspace)),
           '--chunk-config',str(folder/'chunk.json'),'--pipeline-search',str(folder/'search.json')]
    if question!=HANDBOOK_QUESTION:
        serve.append('--pipeline-question='+question)
    if embedding_config:
        serve+=['--embedding-config',str(folder/'embedding.json')]
    if reranker_config:
        preview+=['--reranker-profile',str(folder/'reranker.json')]
        serve+=['--reranker-config',str(folder/'reranker.json')]
    return {'status':'preview_ready','retrieval':controls,'models':selection,
            'generation_configuration_required':configuration_required(generation),
            'question':question,'sources':sources,'selected_document':source_info,
            'commands':{'pipeline_preview':shlex.join(preview),'serve':shlex.join(serve)},
            'inference_calls':0,'network_requests':0,'secrets_read':0}
