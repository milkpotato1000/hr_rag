#!/usr/bin/env python3
"""Frozen 14-setting retrieval experiment; select on tuning before touching holdout."""
import argparse,json,resource,statistics,time,platform
from pathlib import Path
from document_common import read_json,write_json,file_hash,fingerprint
from experiment_common import EXP,ARTIFACTS,RUNTIME,need,config,spec,source,load_run,work_lock,save_state,code_hash
from chunk_core import build
from model_runtime import Provider,Ledger
from retrieval_core import build_index,Searcher
from span_metrics import evaluate,select_budget,aggregate,stability


def choose(rows):
    valid=[x for x in rows if x['retriever']=='dense' and x['at_k']['5']['fact_recall']['macro'] is not None]
    need(valid,'no_candidate','No valid Dense tuning result')
    ordered=sorted(valid,key=lambda x:(-x['at_k']['5']['fact_recall']['macro'],x['statistics']['emitted_unique_ratio'],x['chunk_build_ms'],x['config_id']))
    baseline=next(x for x in valid if x['config_id']=='fixed-400-80');best=ordered[0]
    selected=best if best['at_k']['5']['fact_recall']['macro']>baseline['at_k']['5']['fact_recall']['macro'] else baseline
    return dict(baseline=baseline['config_id'],candidate=selected['config_id'],candidate_run_id=selected['run_id'],baseline_run_id=baseline['run_id'],criterion='tuning Dense macro fact_recall@5; ratio, build_ms, config_id ties; retain baseline without strict recall improvement',ranked=[r['config_id'] for r in ordered],status='frozen',holdout_observed=False,frozen_at=time.time())


def run_group(out,split,runmap,questions,facts,texts,provider,repeats):
    # Embedding only the question string. Facts and evaluation remain outside retrievers.
    vectors,query_usage=provider.embed([q['question'] for q in questions]);byqid=dict(zip([q['query_id'] for q in questions],vectors));summaries=[]
    for cfgid,rid in runmap.items():
        path=ARTIFACTS/rid;manifest=load_run(path);stats=read_json(path/'statistics.json')
        for retriever in ('bm25','dense'):
            print(split,cfgid,retriever,flush=True);index=build_index(path,retriever,provider);started=time.monotonic()
            with Searcher(path,retriever) as search:
                load_ms=(time.monotonic()-started)*1000;rows=[]
                for q in questions:
                    trials=[search.search(q['question'],20,byqid[q['query_id']] if retriever=='dense' else None,provider.ledger) for _ in range(repeats)]
                    trial_dir=out/'ranking-trials'/split;trial_dir.mkdir(parents=True,exist_ok=True);write_json(trial_dir/f"{cfgid}-{retriever}-{q['query_id']}.json",trials)
                    need(all([r['chunk_id'] for r in t['results']]==[r['chunk_id'] for r in trials[0]['results']] for t in trials),'ranking_instability','Ranked IDs changed during latency repeats')
                    ranking=trials[0];ids=[r['chunk_id'] for r in ranking['results']];metrics={};qrels=None
                    for k in (5,10,20):
                        m=evaluate(q,facts,search.maps,ids,k,texts);qrels=m.pop('qrels',qrels);metrics[str(k)]=m
                    budgets={}
                    for budget in (400,800,1600):
                        b=select_budget(ids,search.chunks,budget);m=evaluate(q,facts,search.maps,b['selected'],max(len(b['selected']),1),texts);m.pop('qrels',None);b['metrics']=m;budgets[str(budget)]=b
                    rows.append(dict(query_id=q['query_id'],query_hash=fingerprint(q['question']),split=split,answerability=q['answerability'],ranking=ranking,latency_ms=[t['elapsed_ms'] for t in trials],at_k=metrics,context_budget_simulation=budgets,qrels=qrels))
                summary=dict(config_id=cfgid,run_id=rid,retriever=retriever,index=index,statistics=stats,chunk_build_ms=manifest['elapsed_ms'],at_k={str(k):aggregate([r['at_k'][str(k)] for r in rows]) for k in (5,10,20)},context_budget_simulation={str(b):aggregate([r['context_budget_simulation'][str(b)]['metrics'] for r in rows]) for b in (400,800,1600)},latency=dict(repetitions=repeats,index_load_ms=load_ms,first_query_ms=rows[0]['latency_ms'],mean_ms=statistics.mean(t for r in rows for t in r['latency_ms']),note='Sequential order; persisted index load measured separately. OS/model caches not forcibly evicted. Query embeddings cached before ranking; embedding build/usage reported separately.'),query_embeddings=query_usage)
                target=out/split/f'{cfgid}-{retriever}.json';target.parent.mkdir(exist_ok=True);write_json(target,dict(summary=summary,queries=rows));summaries.append(summary)
                save_state(out/'progress.json',dict(status='RUNNING',split=split,config_id=cfgid,retriever=retriever,completed_groups=len(summaries)))
    return summaries


def execute(out,llm_ids,repeats=2,reuse=None):
    need(not out.exists(),'output_exists','Never overwrite experiment output');out.mkdir(parents=True)
    with work_lock():
        started=time.monotonic();provider=Provider();provider.verify();row,text,_=source()
        need(len(llm_ids)==3 and len(set(llm_ids))==3,'invalid_input','Exactly three independent run IDs required')
        llm=[]
        for rid in llm_ids:
            m=load_run(ARTIFACTS/rid);d=read_json(ARTIFACTS/rid/'boundary-details.json')
            need(m['config']==config('llm-0') and d.get('independent_inference') is True and not m['parent_run_ids'],'invalid_input','Not a fresh independent LLM invocation');llm.append((m,d))
        # First chronological valid corpus run is selected without observing retrieval.
        selected=llm_ids[0];runmap={};builds=[]
        for cfg in spec()['configs']:
            if reuse:
                m=load_run(ARTIFACTS/reuse[cfg['id']]);need(m['config']==cfg and m['canonical_sha256']==row['canonical_sha256'],'stale','Reuse configuration/source mismatch')
            elif cfg['id']=='llm-0':m=llm[0][0]
            else:
                parent=ARTIFACTS/runmap[cfg['method']+'-0'] if cfg['method'] in ('semantic','llm') and cfg['overlap_chars'] else None
                m=build(cfg,provider=provider,parent=parent)
            runmap[cfg['id']]=m['run_id'];builds.append(m);save_state(out/'runs.json',runmap)
        boundaries=[[end for a,end in read_json(ARTIFACTS/rid/'source-map.json')['base_spans']] for rid in llm_ids]
        consistency=stability(boundaries,llm[0][1]['forced_window_boundaries'],len(text));consistency.update(requested_repetitions=3,failed_repetitions=0,selected_first_valid=selected,runs=[dict(run_id=rid,statistics=read_json(ARTIFACTS/rid/'statistics.json'),code_hash=m['code_hash']) for rid,(m,d) in zip(llm_ids,llm)])
        write_json(out/'llm-stability.json',consistency)
        frozen=dict(spec_sha256=file_hash(EXP/'spec.json'),dataset_sha256=file_hash(EXP/'dataset.json'),canonical_sha256=row['canonical_sha256'],llm_runs=llm_ids,latency_repetitions=repeats,config_order=list(runmap),code_hash=code_hash(['run_chunking_experiment.py','span_metrics.py','retrieval_core.py','bm25_core.py','dense_core.py']),started_at=time.time())
        write_json(out/'frozen-inputs.json',frozen)
        dataset=read_json(EXP/'dataset.json');facts={f['fact_id']:f for f in dataset['facts']};texts={row['document_id']:text}
        tuning=run_group(out,'tuning',runmap,[q for q in dataset['questions'] if q['split']=='tuning'],facts,texts,provider,repeats)
        write_json(out/'tuning-summary.json',tuning);selection=choose(tuning);write_json(out/'selection-frozen.json',selection)
        # Holdout is only accessed for evaluation after the immutable selection file exists.
        selection_hash=file_hash(out/'selection-frozen.json');holdmap={cid:runmap[cid] for cid in dict.fromkeys([selection['baseline'],selection['candidate']])}
        holdout=run_group(out,'holdout',holdmap,[q for q in dataset['questions'] if q['split']=='holdout'],facts,texts,provider,repeats)
        need(selection_hash==file_hash(out/'selection-frozen.json'),'stale','Selection changed after holdout');write_json(out/'holdout-summary.json',holdout)
        write_json(out/'ledger-after.json',provider.ledger.refresh())
        result=dict(status='complete',selection=selection,selection_sha256=selection_hash,elapsed_seconds=time.monotonic()-started,peak_python_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*(1 if platform.system()=='Darwin' else 1024),memory_scope='Experiment Python process high-water RSS; excludes Ollama provider',runmap=runmap,outputs={str(p.relative_to(out)):file_hash(p) for p in out.rglob('*.json') if p.name not in ('progress.json','manifest.json')})
        write_json(out/'manifest.json',result);save_state(out/'progress.json',dict(status='SUCCEEDED',candidate=selection['candidate']));return result


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--spec',type=Path,required=True);p.add_argument('--output-dir',type=Path,required=True);p.add_argument('--llm-runs',nargs=3,required=True);p.add_argument('--chunk-runs-file',type=Path);p.add_argument('--latency-repeats',type=int,choices=[1,2,3],default=2);a=p.parse_args()
    need(file_hash(a.spec)==file_hash(EXP/'spec.json'),'stale','Use the frozen experiment spec')
    try:execute(a.output_dir,a.llm_runs,a.latency_repeats,read_json(a.chunk_runs_file) if a.chunk_runs_file else None)
    except Exception as e:
        if a.output_dir.exists():save_state(a.output_dir/'failure.json',dict(status='failed',reason=getattr(e,'kind','execution'),message=str(e),ledger=Ledger().refresh()))
        raise
if __name__=='__main__':main()
