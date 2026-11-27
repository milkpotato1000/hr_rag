"""P031 actual random SDK preparation. No pretrained weights or network."""
import os,sys,socket,json,hashlib,gc
from pathlib import Path
from collections import OrderedDict
os.environ.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',HF_HUB_DISABLE_TELEMETRY='1',TOKENIZERS_PARALLELISM='false')
def denied(*a,**k):raise AssertionError('network forbidden')
socket.socket.connect=denied;socket.getaddrinfo=denied
import torch
from transformers import BertConfig,BertModel,PreTrainedTokenizerFast,XLMRobertaConfig,XLMRobertaForSequenceClassification
from tokenizers import Tokenizer,models,pre_tokenizers,processors
from rag_package import model_catalog as cat,model_preparation as prep,embedding,reranker
from rag_package.model_process import run_worker
from rag_package.storage import read_json,write_json
from rag_package.workspace import init
base=Path(sys.argv[1]).resolve();base.mkdir(parents=True,exist_ok=False)
ws=base/'workspace';init(ws)
# Actual torch.save OrderedDict with scalar, empty, noncontiguous and shared storage.
td=base/'tensors';td.mkdir();shared=torch.arange(12,dtype=torch.float32).reshape(3,4)
state=OrderedDict(a=shared,b=shared,c=shared.t(),half=torch.tensor([1.5,-2],dtype=torch.float16),integer=torch.tensor([0,42],dtype=torch.int64),scalar=torch.tensor(7.),empty=torch.empty(0))
torch.save(state,td/'input.bin');expected={k:({'shape':list(v.shape),'dtype':str(v.dtype),'hash':hashlib.sha256(v.contiguous().reshape(-1).view(torch.uint8).numpy().tobytes()).hexdigest()}) for k,v in state.items()}
r,obs=run_worker({'operation':'conversion','source':str(td/'input.bin'),'destination':str(td/'output.safetensors')},td,timeout=300)
assert set(r['tensors'])==set(expected)
for k,x in expected.items():assert r['tensors'][k]['shape']==x['shape'] and r['tensors'][k]['dtype']==x['dtype'] and r['tensors'][k]['value_sha256']==x['hash']
assert obs['workers_started']==1 and obs['worker_exited']
# Reject object state without pickle fallback.
bad=base/'invalid';bad.mkdir();torch.save({'object':Path('custom')},bad/'input.bin')
try:run_worker({'operation':'conversion','source':str(bad/'input.bin'),'destination':str(bad/'output.safetensors')},bad,timeout=300)
except Exception as e:assert e.code=='preparation_worker_failed' and e.observation['worker_exited']
else:raise AssertionError('custom object accepted')
# Actual owned child timeout is killed/waited without inference.
timeout_dir=base/'timeout';timeout_dir.mkdir()
try:run_worker({'operation':'conversion','source':str(td/'input.bin'),'destination':str(timeout_dir/'out.safetensors')},timeout_dir,timeout=0)
except Exception as e:
    assert e.code=='preparation_timeout' and e.observation['workers_started']==1 and e.observation['worker_exited']
else:raise AssertionError('timeout child was not stopped')
# Production HF adapter through actual SDK data classes, injected no-network endpoints.
from unittest.mock import patch
from types import SimpleNamespace
from huggingface_hub.hf_api import RepoSibling,BlobLfsInfo
from rag_package.model_worker import fetch_metadata,download
pinned=cat.make_plan('intfloat/multilingual-e5-small','embedding')
siblings=[RepoSibling(rfilename=f['path'],size=f['size'],blob_id=f['git_blob_oid'],lfs=BlobLfsInfo(size=f['size'],sha256=f['lfs_sha256'],pointer_size=130) if f['lfs_sha256'] else None) for f in pinned['files']]
with patch('huggingface_hub.model_info',return_value=SimpleNamespace(id=pinned['repo_id'],sha=pinned['revision'],private=False,gated=False,siblings=siblings)) as info:
    fetched=fetch_metadata(pinned['repo_id'],pinned['revision']);assert sorted(fetched['files'],key=lambda f:f['path'])==pinned['files']
    assert info.call_args.kwargs=={'revision':pinned['revision'],'files_metadata':True,'timeout':20,'token':False}
with patch('huggingface_hub.snapshot_download',return_value='fixture') as snap:
    download(pinned,str(base/'fake-download'))
    assert snap.call_args.kwargs['token'] is False and snap.call_args.kwargs['revision']==pinned['revision'] and snap.call_args.kwargs['max_workers']==1
    assert snap.call_args.kwargs['allow_patterns']==[f['path'] for f in pinned['files']]
results=[]
for index,model_id in enumerate(("intfloat/multilingual-e5-small","BAAI/bge-m3","BAAI/bge-reranker-v2-m3","cross-encoder/mmarco-mMiniLMv2-L12-H384-v1")):
    folder=ws/('model-'+str(index));folder.mkdir();src=folder/'source';src.mkdir();role=cat.RECIPES[model_id][1]
    vocab={'<s>':0,'<pad>':1,'</s>':2,'<unk>':3,'생일':4,'휴가':5,'신청':6,'query':7,'passage':8,':':9}
    tok=Tokenizer(models.WordLevel(vocab,unk_token='<unk>'));tok.pre_tokenizer=pre_tokenizers.Whitespace();tok.post_processor=processors.RobertaProcessing(('</s>',2),('<s>',0))
    fast=PreTrainedTokenizerFast(tokenizer_object=tok,bos_token='<s>',eos_token='</s>',pad_token='<pad>',unk_token='<unk>',model_max_length=512);fast.save_pretrained(src)
    torch.manual_seed(31)
    if role=='embedding':
        dimension=384 if index==0 else 1024
        model=BertModel(BertConfig(vocab_size=len(vocab),hidden_size=dimension,num_hidden_layers=1,num_attention_heads=4,intermediate_size=16,max_position_embeddings=512,pad_token_id=1))
        model.save_pretrained(src,safe_serialization=True)
        if index==1:
            torch.save(model.state_dict(),src/'pytorch_model.bin');(src/'model.safetensors').unlink()
        write_json(src/'modules.json',[{'idx':0,'name':'0','path':'','type':'sentence_transformers.models.Transformer'},{'idx':1,'name':'1','path':'1_Pooling','type':'sentence_transformers.models.Pooling'}])
        (src/'1_Pooling').mkdir();write_json(src/'1_Pooling/config.json',{'word_embedding_dimension':dimension,'pooling_mode':'mean' if index==0 else 'cls'})
        write_json(src/'sentence_bert_config.json',{'max_seq_length':512,'do_lower_case':False})
    else:
        cfg=XLMRobertaConfig(vocab_size=len(vocab),hidden_size=32,num_hidden_layers=1,num_attention_heads=4,intermediate_size=48,max_position_embeddings=514,num_labels=1,pad_token_id=1,bos_token_id=0,eos_token_id=2)
        model=XLMRobertaForSequenceClassification(cfg);model.save_pretrained(src,safe_serialization=True)
    del model;gc.collect()
    # Fast WordLevel tokenizer uses tokenizer.json. This recipe placeholder is never loaded.
    for name in cat.recipe(model_id):
        if not (src/name).exists():(src/name).write_bytes(b'{}' if name.endswith('.json') else b'tiny fixture not sentencepiece')
    # Keep exact reviewed recipe, not README/training metadata from save_pretrained.
    for p in list(src.rglob('*')):
        if p.is_file() and p.relative_to(src).as_posix() not in cat.recipe(model_id):p.unlink()
    rows=[]
    for name in cat.recipe(model_id):
        data=(src/name).read_bytes();rows.append({'path':name,'size':len(data),'git_blob_oid':hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest(),'lfs_sha256':hashlib.sha256(data).hexdigest() if name.endswith(('.bin','.safetensors','.model')) else None})
    cat.plan(model_id,role,folder/'plan',revision='tiny-random',fetch_metadata=True,metadata_backend=lambda _,rows=rows:{'revision':'c'*40,'files':rows,'observed_at':'2026-11-28'})
    prepared=prep.prepare(folder/'plan',folder/'prepared',source=src,execute_conversion=True);assert prepared['status']=='ready',prepared
    profile=folder/'prepared/profile.json';check=prep.model_check(profile)
    if role=='embedding':
        p=embedding.read_profile(profile);v,work=embedding.encode(p,['생일 휴가'],['one'],'document',execute=True);assert len(v[0])==dimension
    else:
        p=reranker.read_profile(profile);v,work=reranker.score(p,'생일',[{'chunk_id':'one','text':'생일 휴가'}]);assert len(v)==1
    results.append({'model_id':model_id,'role':role,'preparation':prepared,'check':check,'worker':work,'profile':str(profile)})
write_json(base/'result.json',{'status':'PASS','execution_kind':'tiny_random_sdk_not_pretrained','pretrained_loads':0,'network_requests':0,'owned_timeout_kill_wait':True,'production_hf_adapter_fake_sdk_transport':True,'conversion':r,'observation':obs,'models':results,'workspace':str(ws),'sdk':embedding.versions()})
print(json.dumps({'status':'PASS','workspace':str(ws),'models':len(results),'tensor_variants':list(expected)}))
