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


def run(sources, chunk_config, search_config, question, out, *, reranker_profile=None, execute=False):
    require(isinstance(question,str) and 0 < len(question.strip()) <= 2000,'invalid_question','pipeline')
    root = Path(out).absolute()
    try:
        root.mkdir(parents=True,exist_ok=False)
    except FileExistsError:
        raise RagError('output_exists','pipeline') from None
    stages = ('snapshot','chunks','index','search','candidates','rerank','answer')
    report = {'status':'running','question':question,'mode':'execute' if execute else 'preview',
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
                        'generation':generation,'chunking_destination':chunk_target,
                        'work_upper_bounds':{'boundary_llm_requests':len(windows),'boundary_embedding_items':len(units) if cfg['method']=='semantic' else 0,
                                             'index_jobs':int(bool(ep)),'query_jobs':int(bool(ep)),
                                             'rerank_pairs':settings['candidate_k'] if rp else 0,'generation_requests':1},
                        'outputs':{name:name for name in stages}}
        if execute:
            require(not generation['configuration_required'] and (not chunk_target or not chunk_target['configuration_required'])
                    and (not ep or embedding.configured(ep)) and (not rp or reranker.configured(rp)),
                    'configuration_required','pipeline')
            lpath=Path(search_config).absolute().parent/config['llm_config']
            config_path=root/'retrieval.json'
            write_json(config_path,dict(schema_version=3,chunk_artifact='chunks',llm_config=str(lpath),
                                        retrieval=settings,embedding_config=config.get('embedding_config')))
            step('chunks',lambda:chunk_artifact.build(root/'snapshot',chunk_config,root/'chunks',execute=True),lambda r:r['status']=='ready')
            step('index',lambda:retrieval.build(root/'snapshot',config_path,root/'index',execute_retrieval=True),lambda r:True)
            step('search',lambda:rag.ask(root/'index',config_path,question,root/'search',execute_retrieval=True),
                 lambda r:r['status'] in ('preview','abstained'))
            step('candidates',lambda:candidates.freeze(root/'index',root/'search','question',settings['candidate_k'],root/'candidates'),lambda r:True)
            step('rerank',lambda:reranking.run(root/'candidates','cross-encoder' if rp else 'none',root/'rerank',
                 profile=reranker_profile,top_k=settings['top_k'],context_budget_chars=settings['context_budget_chars'],
                 execute=True),lambda r:r['status']=='complete')
            answer=step('answer',lambda:reranking.answer(root/'rerank',lpath,root/'answer',execute=True),
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
    verify(root,'pipeline')
    return read_json(Path(root)/'pipeline.json')
