"""Actual locked SDK, only locally randomized tensors; no network/pretrained files."""
from pathlib import Path
import copy,json,tempfile,hashlib,sys
import torch
from transformers import XLMRobertaConfig,XLMRobertaForSequenceClassification,PreTrainedTokenizerFast
from tokenizers import Tokenizer,models,pre_tokenizers,processors
from safetensors.torch import save_file
from rag_package.reranker_worker import validate_state,LEGACY_MODEL,LEGACY_REVISION,POSITION_KEY
from rag_package import reranker
from rag_package.storage import RagError,write_json
out=Path(sys.argv[1]);out.mkdir();root=out/'model';root.mkdir();torch.manual_seed(32)
cfg=XLMRobertaConfig(vocab_size=8,hidden_size=16,num_hidden_layers=1,num_attention_heads=2,intermediate_size=24,max_position_embeddings=514,num_labels=1,pad_token_id=1,bos_token_id=0,eos_token_id=2)
m=XLMRobertaForSequenceClassification(cfg).eval();p={'model_id':LEGACY_MODEL,'revision':LEGACY_REVISION}
base={k:list(v.shape) for k,v in m.state_dict().items()};legacy=dict(base,**{POSITION_KEY:[1,514]});buf=torch.arange(514).reshape(1,514);cases=[]
def check(name,stored,model=m,profile=p,buffer=buf,error=False):
 try:r=validate_state(stored,model,profile,buffer)
 except RagError as e:
  assert error and e.code=='model_weights_mismatch',(name,e);r=e.weight_validation
 else:assert not error,name
 cases.append({'case':name,'expected_failure':error,'validation':r})
check('legacy deterministic buffer',legacy)
check('normal no stored buffer',base,buffer=None)
for name,b in [('dtype',buf.float()),('shape',buf.flatten()),('value',buf+1)]:check('wrong '+name,legacy,buffer=b,error=True)
check('wrong stored shape',dict(legacy,**{POSITION_KEY:[514]}),error=True)
check('unknown extra key',dict(legacy,unknown=[1]),error=True)
x=dict(legacy);del x['classifier.out_proj.weight'];check('missing classifier',x,error=True)
x=dict(legacy);x['classifier.out_proj.weight']=[2,16];check('classifier shape',x,error=True)
check('different revision',legacy,profile=dict(p,revision='f'*40),error=True)
check('different model',legacy,profile=dict(p,model_id='BAAI/bge-reranker-v2-m3'),error=True)
for name,mutate in [('loaded value',lambda n:n.roberta.embeddings.position_ids.add_(1)),('loaded dtype',lambda n:setattr(n.roberta.embeddings,'position_ids',buf.float())),('loaded config',lambda n:setattr(n.config,'max_position_embeddings',515))]:
 n=copy.deepcopy(m);mutate(n);check(name,legacy,model=n,error=True)
n=copy.deepcopy(m);del n.roberta.embeddings.position_ids;n.roberta.embeddings.register_parameter('position_ids',torch.nn.Parameter(buf.clone(),requires_grad=False));check('parameter is not buffer',legacy,model=n,error=True)
assert POSITION_KEY in dict(m.named_buffers()) and POSITION_KEY not in m.state_dict()
vocab={'<s>':0,'<pad>':1,'</s>':2,'<unk>':3,'생일':4,'휴가':5,'신청':6,'기간':7}
t=Tokenizer(models.WordLevel(vocab,unk_token='<unk>'));t.pre_tokenizer=pre_tokenizers.Whitespace();t.post_processor=processors.RobertaProcessing(('</s>',2),('<s>',0))
fast=PreTrainedTokenizerFast(tokenizer_object=t,bos_token='<s>',eos_token='</s>',pad_token='<pad>',unk_token='<unk>',model_max_length=512);fast.save_pretrained(root);m.save_pretrained(root,safe_serialization=True)
rows=[{'chunk_id':'one','text':'생일 휴가'}];batch=fast('생일','생일 휴가',return_tensors='pt');batch.pop('token_type_ids',None)
with torch.no_grad():expected=m(**batch).logits[0,0].item()
def profile():return reranker.profile({'schema_version':1,**p,'local_path':str(root),'file_manifest':{f.name:hashlib.sha256(f.read_bytes()).hexdigest() for f in root.iterdir() if f.is_file()},'timeout_seconds':300})
results=[]
for mode in ('normal','legacy','tampered'):
 state=m.state_dict()
 if mode!='normal':state=dict(state,**{POSITION_KEY:buf.clone()+(1 if mode=='tampered' else 0)})
 save_file(state,root/'model.safetensors')
 try:s,w=reranker.score(profile(),'생일',rows)
 except RagError as e:
  assert mode=='tampered' and e.code=='model_weights_mismatch';assert e.work['worker_exited'];results.append({'mode':mode,'error':e.code,'work':e.work})
 else:
  assert mode!='tampered' and abs(s[0]['score']-expected)<1e-6;(results.append({'mode':mode,'scores':s,'expected_logit':expected,'work':w}))
write_json(out/'result.json',{'status':'PASS','fixture':'locally randomized tiny, pinned ID/revision only exercises guard','pretrained_loads':0,'network_calls':0,'sdk':reranker.versions(),'cases':cases,'owned_workers':results})
print(json.dumps({'status':'PASS','cases':len(cases),'owned_workers':len(results)}))
