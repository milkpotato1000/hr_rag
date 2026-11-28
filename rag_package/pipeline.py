"""Single selected document pipeline using immutable artifacts at every step."""
from pathlib import Path

from . import candidates, chunk_artifact, documents, embedding, rag, reranker, reranking, retrieval
from .llm.core import configuration_required
from .storage import RagError, read_json, require, seal, verify, write_json
from .ui_registry import atomic_json


def target(config, role):
    profile = config['profiles'][config['roles'][role]]
    return {'provider':profile['provider'], 'model':profile['model'], 'destination':profile['base_url'],
            'configuration_required':configuration_required(profile)}


def run(sources, chunk_config, search_config, question, out, *, reranker_profile=None, execute=False,
        transport=None, key_resolver=None, embedding_backend=None, reranker_backend=None):
    require(isinstance(question,str) and 0 < len(question.strip()) <= 2000,'invalid_question','pipeline')
    root = Path(out).absolute()
    try:
        root.mkdir(parents=True,exist_ok=False)
    except FileExistsError:
        raise RagError('output_exists','pipeline') from None
    stages = ('snapshot','chunks','index','search','candidates','rerank','answer')
    report = {'status':'running','question':question,'mode':'execute' if execute else 'preview',
              'execution_kind':'test_fixture' if any(x is not None for x in (transport,key_resolver,embedding_backend,reranker_backend)) else ('live' if execute else 'preview'),
              'stages':{stage:'pending' for stage in stages},'answer':None}
    def checkpoint():
        atomic_json(root/'pipeline.json',report)
    def step(name, operation, valid):
        report['active_stage']=name
        report['stages'][name]='running'
        checkpoint()
        result=operation()
        require(valid(result), (result.get('error') or {}).get('code',name+'_incomplete'),name)
        report['stages'][name]='complete'
        checkpoint()
        return result
    report['active_stage']='configuration'
    checkpoint()
    try:
        config, llm = retrieval.config(search_config)
        require(config['schema_version'] in (1,2),'search_template_required','pipeline')
        require(llm['profiles'][llm['roles']['generation']]['response_mode']=='json_object','json_object_required','pipeline')
        settings=dict(config['retrieval'])
        settings.setdefault('candidate_k',max(20,settings['top_k']))
        settings.setdefault('rrf_k',60)
        require(settings['candidate_k']<=100,'candidate_limit','pipeline')
        ep=embedding.read_profile(config['embedding_config']) if config.get('embedding_config') else None
        rp=reranker.read_profile(reranker_profile) if reranker_profile else None
        generation=target(llm,'generation')
        sm=step('snapshot',lambda:documents.snapshot(sources,root/'snapshot'),
                lambda r:r['identity']['status']=='ready')
        report['active_stage']='chunk_preflight'
        _,_,cfg,model,_,units,windows=chunk_artifact.preflight(root/'snapshot',chunk_config)
        chunk_target=target(model,'chunking') if cfg['method']=='llm' else None
        report['plan']={'source_fingerprint':sm['fingerprint'],'chunking':cfg,'retrieval':settings,
                        'embedding':embedding.identity(ep) if ep else None,'reranker':reranker.identity(rp) if rp else None,
                        'generation':generation,'generation_profile':{k:v for k,v in llm['profiles'][llm['roles']['generation']].items() if k!='api_key_env'},
                        'effective_chunking':chunk_artifact.policy.effective(cfg,model),'chunking_destination':chunk_target,
                        'work_upper_bounds':{'boundary_llm_requests':sum(w.get('selection_reason')!='single_candidate' for w in windows),'boundary_embedding_items':len(units) if cfg['method']=='semantic' else 0,
                                             'index_jobs':int(bool(ep)),'query_jobs':int(bool(ep)),
                                             'rerank_pairs':settings['candidate_k'] if rp else 0,'generation_requests':1},
                        'outputs':{name:name for name in stages}}
        if cfg.get("partition_mode")=="candidate_choice":
            report["plan"]["partition_windows"]=[{k:w[k] for k in ("window_id","candidates","selection_reason")} for w in windows]
        if execute:
            require(not generation['configuration_required'] and (not chunk_target or not chunk_target['configuration_required'])
                    and (not ep or embedding.configured(ep)) and (not rp or reranker.configured(rp)),
                    'configuration_required','pipeline')
            lpath=Path(search_config).absolute().parent/config['llm_config']
            config_path=root/'retrieval.json'
            write_json(config_path,dict(schema_version=3,chunk_artifact='chunks',llm_config=str(lpath),
                                        retrieval=settings,embedding_config=config.get('embedding_config')))
            step('chunks',lambda:chunk_artifact.build(root/'snapshot',chunk_config,root/'chunks',execute=True,embedding_backend=embedding_backend,transport=transport,key_resolver=key_resolver),lambda r:r['status']=='ready')
            step('index',lambda:retrieval.build(root/'snapshot',config_path,root/'index',execute_retrieval=True,embedding_backend=embedding_backend),lambda r:True)
            step('search',lambda:rag.ask(root/'index',config_path,question,root/'search',execute_retrieval=True,embedding_backend=embedding_backend),
                 lambda r:r['status'] in ('preview','abstained'))
            step('candidates',lambda:candidates.freeze(root/'index',root/'search','question',settings['candidate_k'],root/'candidates'),lambda r:True)
            step('rerank',lambda:reranking.run(root/'candidates','cross-encoder' if rp else 'none',root/'rerank',
                 profile=reranker_profile,top_k=settings['top_k'],context_budget_chars=settings['context_budget_chars'],
                 execute=True,backend=reranker_backend),lambda r:r['status']=='complete')
            answer=step('answer',lambda:reranking.answer(root/'rerank',lpath,root/'answer',execute=True,transport=transport,key_resolver=key_resolver),
                        lambda r:r['status'] in ('answered','abstained'))
            report.update(status=answer['status'],answer=answer['answer'],generation_requests=answer['generation_requests'])
        else:
            report['status']='preview'
            report['generation_requests']=0
        report['active_stage']=None
    except (RagError,ValueError,OSError) as exc:
        stage=report['active_stage']
        if stage in stages:
            report['stages'][stage]='failed'
        report.update(status='failed',failed_stage=stage,error=getattr(exc,'code',type(exc).__name__))
    checkpoint()
    seal(root,{'schema_version':1,'kind':'pipeline','status':report['status']})
    return report


def replay(root):
    manifest=verify(root,'pipeline')
    require('pipeline.json' in manifest['identity']['files'],'missing_pipeline_result','pipeline')
    return read_json(Path(root)/'pipeline.json')


def comparison_side(path):
    root = Path(path)
    report = replay(root)
    plan = report.get('plan', {})
    snapshot = None
    if report['stages']['snapshot'] == 'complete':
        snapshot = verify(root/'snapshot', 'snapshot')
        if plan:
            require(snapshot['fingerprint'] == plan['source_fingerprint'], 'stale_snapshot', 'pipeline')
    settings = {}
    if plan:
        chunk = plan.get('effective_chunking', plan['chunking'])
        settings.update({'chunk.'+k:v for k,v in chunk.items() if k != 'schema_version'})
        settings.update({'search.'+k:v for k,v in plan['retrieval'].items()
                         if k != 'rrf_k' or plan['retrieval']['method'] == 'hybrid'})
        settings.update(embedding=plan.get('embedding'), reranker=plan.get('reranker'))
        profile = plan.get('generation_profile', plan['generation'])
        settings.update({'generation.'+k:v for k,v in profile.items()})
    # Read only paths covered by the saved pipeline manifest. A stray file from
    # an interrupted or later run cannot supply missing context.
    files = read_json(root/'manifest.json')['identity']['files']
    answer = read_json(root/'answer/result.json') if 'answer/result.json' in files else {}
    if answer:
        require(answer['question'] == report['question'], 'question_mismatch', 'pipeline')
    selection = {}
    if report['stages']['rerank'] == 'complete':
        selection = read_json(root/'rerank/result.json')['selection']
    return {'source':snapshot['fingerprint'] if snapshot else None, 'question':report['question'],
            'settings':settings, 'complete_settings':bool(plan.get('generation_profile') and plan.get('effective_chunking')),
            'status':report['status'], 'execution_kind':report.get('execution_kind','historical_'+report['mode']),
            'mode':report['mode'], 'stages':report['stages'], 'error':report.get('error'),
            'failed_stage':report.get('failed_stage'), 'contexts':answer.get('contexts',selection.get('contexts',[])),
            'dispatch_attempted':answer.get('dispatch_attempted',False), 'answer':answer.get('answer')}


def compare(left, right):
    require(Path(left).resolve() != Path(right).resolve(), 'duplicate_pipeline', 'pipeline')
    a, b = comparison_side(left), comparison_side(right)
    keys = sorted(a['settings'].keys() | b['settings'].keys())
    changed = [key for key in keys if key not in a['settings'] or key not in b['settings']
               or a['settings'][key] != b['settings'][key]]
    same_source = a['source'] == b['source'] if a['source'] and b['source'] else None
    same_question = a['question'] == b['question']
    if same_source is False or not same_question:
        interpretation = 'different_inputs'
    elif same_source is None or not (a['complete_settings'] and b['complete_settings']):
        interpretation = 'incomplete_settings'
    elif a['mode'] != b['mode'] or a['execution_kind'] != b['execution_kind']:
        interpretation = 'different_execution'
    elif len(changed) == 1:
        interpretation = 'single_setting'
    else:
        interpretation = 'multiple_settings' if changed else 'same_settings'
    return {'same_source':same_source,'same_question':same_question,'changed':changed,
            'interpretation':interpretation,'runs':[a,b],'comparison_model_calls':0}
