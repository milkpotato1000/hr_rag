"""Private worker protocol. Local snapshots only; never a download endpoint."""
import contextlib,json,sys
from .embedding import profile,check_files,CATALOG,versions
from .storage import RagError,require

def run(request):
    p=profile(request['profile']);root=check_files(p);cat=CATALOG[p['model_id']]
    import torch
    from sentence_transformers import SentenceTransformer
    model=SentenceTransformer(str(root),device=p['device'],backend='torch',local_files_only=True,trust_remote_code=False,token=False,
        model_kwargs={'use_safetensors':True,'torch_dtype':torch.float32},processor_kwargs={'local_files_only':True,'trust_remote_code':False,'token':False},config_kwargs={'local_files_only':True,'trust_remote_code':False,'token':False})
    require(model.get_sentence_embedding_dimension()==cat['dimension'],'model_dimension_mismatch','embedding')
    model.max_seq_length=p['max_input_tokens'];prefix=cat[request['kind']+'_prefix'];texts=[prefix+t for t in request['texts']]
    too_long=[]
    for i,text in zip(request['ids'],texts):
        tokens=model.tokenizer(text,add_special_tokens=True,truncation=False,padding=False)['input_ids']
        if len(tokens)>p['max_input_tokens']:too_long.append(i)
    if too_long:return {'error':'input_too_long','offending_ids':too_long}
    vectors=model.encode(texts,batch_size=p['batch_size'],show_progress_bar=False,convert_to_numpy=True,normalize_embeddings=True,prompt='').tolist()
    import resource
    peak=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return {'vectors':vectors,'sdk_versions':versions(),'peak_rss_bytes':peak if sys.platform=='darwin' else peak*1024,'rss_method':'OS process-lifetime ru_maxrss; no periodic sampling; includes imports/model/tokenization/encode'}

def main():
    try:
        request=json.load(sys.stdin)
        with contextlib.redirect_stdout(sys.stderr):response=run(request)
    except RagError as e:response={'error':e.code}
    except Exception:response={'error':'embedding_sdk_failed'}
    print(json.dumps(response,allow_nan=False))

if __name__=='__main__':main()
