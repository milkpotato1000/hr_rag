"""One installed CLI compare invocation; immutable checkpoints and latched stop."""
from pathlib import Path
import importlib.util,sys,contextlib,io,json,shutil,os,socket
spec=importlib.util.spec_from_file_location('s2b_runtime',Path(__file__).with_name('runtime.py'));rt=importlib.util.module_from_spec(spec);spec.loader.exec_module(rt)
ctl=rt.module('control');E,R=rt.E,rt.RUN
import rag_package
from rag_package import rag,retrieval,embedding,reranker,chunk_artifact,chunk_policy,chunk_compare,llm,owned_worker,model_process
from rag_package.llm import core,transport
from rag_package.storage import require,RagError,fingerprint,verify,read_json,staging
from rag_package.candidates import copy_artifact
from rag_package.documents import load_snapshot
from rag_package.__main__ import main

def deny(*a,**kw):raise RagError('s2b_forbidden_non_embedding_call','s2b')
for m,n in [(llm,'invoke'),(core,'invoke'),(core,'http_transport'),(transport,'http_transport'),(reranker,'score')]:setattr(m,n,deny)
socket.create_connection=deny

def checkpoint(src,dest,kind):
    # New directory only; manifest copied last. Interrupted partial copies remain
    # diagnostics and cannot pass verify. Never overwrite an earlier checkpoint.
    copy_artifact(src,dest,kind)
    verify(dest,kind)

def run():
    require('site-packages' in str(Path(rag_package.__file__)) and not Path(rag_package.__file__).is_relative_to(rt.ROOT),'s2b_source_import','s2b')
    manifest=rt.read(R/'manifest.json');rt.check_frozen(manifest)
    require(rt.sha(manifest['installation']['wheel'])==manifest['installation']['wheel_sha256'],'s2b_wheel_changed','s2b')
    require(embedding.versions()==manifest['sdk_versions'],'s2b_sdk_changed','s2b')
    profile=embedding.read_profile(R/'input/e5.json');embedding.check_files(profile)
    require(profile==manifest['profile'],'s2b_profile_changed','s2b')
    require(rt.sha(R/'ledger.json')==manifest['initial_ledger_hash'],'s2b_ledger_not_pristine','s2b')
    control=ctl.Control(R/'ledger.json');control.claim()
    sm,docs=load_snapshot(R/'input/snapshot');us=chunk_policy.units(docs,sm['fingerprint'],120)
    require(len(us)==567 and fingerprint(us)==manifest['units_hash'],'s2b_units_changed','s2b')
    qs=rt.read(R/'input/questions.json');expected_request=None;original_encode=embedding.encode
    original_build=rag.build;original_ask=rag.ask
    def guarded_encode(p,texts,ids,kind,**kwargs):
        nonlocal expected_request
        try:
            control.check();require(p==profile and kwargs.get('backend') is None and kwargs.get('execute') is True,'s2b_embedding_identity','s2b')
            require(expected_request==fingerprint({'texts':texts,'ids':ids,'kind':kind}) and control.current is not None and len(texts)==control.current['requested_items'],'s2b_payload_changed','s2b')
            result=original_encode(p,texts,ids,kind,**kwargs)
            require(result[1]['sdk_versions']==manifest['sdk_versions'] and result[1]['execution_kind']=='local_hf','s2b_sdk_result','s2b')
            control.computed(len(texts));return result
        except BaseException as e:control.halt(e);raise
    embedding.encode=guarded_encode
    def expect(texts,ids,kind):
        nonlocal expected_request
        expected_request=fingerprint({'texts':texts,'ids':ids,'kind':kind})
    def semantic_validate(result):
        require(result['status']=='ready','s2b_semantic_failed','s2b')
        cr,ds,cs,_=chunk_artifact.load(R/'semantic')
        require(len(cs)<=567 and cr['source_fingerprint']==sm['fingerprint'] and cr['work']['boundary_model_jobs']==1,'s2b_semantic_identity','s2b')
        require(rt.read(R/'semantic/units.json')==us,'s2b_semantic_units_changed','s2b')
        unique={(c['document_id'],n) for c in cs for n in range(c['start'],c['end'])}
        require(unique=={(d['document_id'],n) for d in ds for n in range(len(d['text']))},'s2b_semantic_coverage','s2b')
        rt.write(R/'semantic-validation.json',{'status':'PASS','chunk_count':len(cs),'source_chars':len(unique),'replay':chunk_artifact.replay(R/'semantic'),'model_calls_this_validation':0})
    expected_settings={};method_for={};count_for={}
    def wrap_build(snapshot,path,out,**kwargs):
        c,lc=retrieval.config(path);method=chunk_artifact.load(c['chunk_artifact'])[0]['config']['method']
        def validate(bm):
            checked,_,_=retrieval.load_build(out,c)
            require(checked['identity']==bm['identity'] and bm['identity']['source_fingerprint']==sm['fingerprint'],'s2b_build_identity','s2b')
            require(read_json(Path(out)/'embedding-work.json')['jobs']==1,'s2b_unexpected_index_reuse','s2b')
        def call():
            require(retrieval.effective(c,lc)==expected_settings[method] and kwargs.get('reuse') is None,'s2b_settings_changed','s2b')
            cr,_,cs,_=chunk_artifact.load(c['chunk_artifact']);expect([x['text'] for x in cs],[x['chunk_id'] for x in cs],'document')
            return original_build(snapshot,path,out,**kwargs)
        return control.operation(method+'-index',count_for[method],call,validate,lambda _:checkpoint(out,R/'checkpoints'/method/'build','build'))
    def wrap_ask(build,path,question,out,**kwargs):
        # Identify operation from immutable method config and fixed question order.
        c,lc=retrieval.config(path);method=chunk_artifact.load(c['chunk_artifact'])[0]['config']['method'];qid=kwargs['question_id']
        def call():
            require(retrieval.effective(c,lc)==expected_settings[method] and question==next(q['question'] for q in qs if q['id']==qid),'s2b_question_settings_changed','s2b')
            require(kwargs.get('execute') is False and kwargs.get('embedding_backend') is None and kwargs.get('transport') is None,'s2b_execution_mode','s2b')
            expect([question],['query'],'query');return original_ask(build,path,question,out,**kwargs)
        def validate(result):
            m=verify(out,'answer');bm=verify(build,'build')
            require(result['status']=='preview' and result['error'] is None and result['answer'] is None and result['generation_requests']==0 and not result['dispatch_attempted'],'s2b_query_logical_failure','s2b')
            require(result==read_json(Path(out)/'result.json') and result['source_fingerprint']==sm['fingerprint'] and result['query_hash']==fingerprint(question),'s2b_answer_identity','s2b')
            require(result['index_fingerprint']==bm['identity']['index_fingerprint'] and result['chunk_fingerprint']==bm['identity']['chunk_fingerprint'],'s2b_answer_index','s2b')
            require(result['embedding_work']['jobs']==1 and result['embedding_work']['queries']==1,'s2b_query_work','s2b')
        return control.operation(method+'-'+qid,1,call,validate,lambda _:checkpoint(out,R/'checkpoints'/method/qid,'answer'))
    try:
        pre={'pressure':model_process.pressure(),'disk_free_bytes':shutil.disk_usage(R).free,'sdk_versions':embedding.versions()}
        require(pre['pressure']['pressure']=='normal' and pre['disk_free_bytes']>=2*1024**3,'s2b_preflight','s2b');rt.write(R/'preflight.json',pre)
        with owned_worker.execution_scope(control):
            expect([u['text'] for u in us],[u['id'] for u in us],'document')
            control.operation('semantic-boundary',567,lambda:chunk_artifact.build(R/'input/snapshot',R/'input/semantic.json',R/'semantic',execute=True),semantic_validate,lambda _:checkpoint(R/'semantic',R/'checkpoints/semantic-boundary','chunks'))
            configs=[]
            for method in ctl.METHODS:
                path=R/'input/configs'/(method+'.json');c,lc=retrieval.config(path)
                expected_settings[method]=retrieval.effective(c,lc);count_for[method]=len(chunk_artifact.load(c['chunk_artifact'])[2]);configs.append(str(path))
            rag.build=control.protect(wrap_build);rag.ask=control.protect(wrap_ask)
            # CLI dispatches exactly one compare. No separate repeat for CLI validation.
            argv=['compare','--snapshot',str(R/'input/snapshot'),'--configs',*configs,'--questions',str(R/'input/questions.json'),'--facts',str(R/'input/facts.json'),'--execute-retrieval','--out',str(R/'comparison')]
            output=io.StringIO()
            with contextlib.redirect_stdout(output):code=main(argv)
            rt.write(R/'cli-compare.json',{'argv':argv,'exit_code':code,'stdout':output.getvalue(),'invocations':1})
            require(code==0 and control.state['status']=='running','s2b_compare_failed','s2b')
            summary=chunk_compare.load(R/'comparison');require(len(summary['rows'])==40 and all(r['status']=='preview' for r in summary['rows']),'s2b_incomplete_comparison','s2b')
            rt.check_frozen(manifest);control.complete()
        rt.write(R/'completion.json',{'status':'S2b_matrix_complete','rows':40,'generation_requests':0,'P032_complete':False})
    except BaseException as e:
        control.halt(e)
        rt.write(R/'failure.json',{'status':'halted','code':getattr(e,'code',type(e).__name__),'operations':len(control.state['operations']),'automatic_resume':False})
        raise
    finally:embedding.encode=original_encode;rag.build=original_build;rag.ask=original_ask

if __name__=='__main__':run()
