"""Locally generated random weights: SDK plumbing only, never retrieval quality."""
import os,socket,json,hashlib,sys,inspect
from pathlib import Path
os.environ.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',HF_HUB_DISABLE_TELEMETRY='1',TOKENIZERS_PARALLELISM='false')
def forbidden(*a,**k):raise AssertionError('network forbidden')
socket.socket.connect=forbidden;socket.getaddrinfo=forbidden
import torch
from transformers import BertConfig,BertModel,BertTokenizerFast
from sentence_transformers import SentenceTransformer,models
from rag_package.embedding import encode,CATALOG,versions
base=Path('.rag-runs/p010-sdk/tiny');base.mkdir(parents=True,exist_ok=True);records=[]
for mid,cat in CATALOG.items():
 root=base/('e5' if cat['dimension']==384 else 'bge');raw=root/'raw';raw.mkdir(parents=True,exist_ok=True)
 vocab=['[PAD]','[UNK]','[CLS]','[SEP]','[MASK]','query','passage',':','hello','world','birthday','leave']
 (raw/'vocab.txt').write_text('\n'.join(vocab)+'\n');tok=BertTokenizerFast(vocab_file=str(raw/'vocab.txt'));tok.save_pretrained(raw)
 cfg=BertConfig(vocab_size=len(tok),hidden_size=cat['dimension'],num_hidden_layers=1,num_attention_heads=4,intermediate_size=32,max_position_embeddings=512)
 torch.manual_seed(42);model=BertModel(cfg);params=sum(p.numel() for p in model.parameters());assert params<10_000_000;model.save_pretrained(raw,safe_serialization=True)
 transformer=models.Transformer(str(raw),max_seq_length=512,model_args={'local_files_only':True,'use_safetensors':True},tokenizer_args={'local_files_only':True})
 pool=models.Pooling(cat['dimension'],pooling_mode=cat['pooling']);st=SentenceTransformer(modules=[transformer,pool,models.Normalize()],device='cpu');dest=root/'export';st.save_pretrained(str(dest),safe_serialization=True)
 manifest={str(p.relative_to(dest)):hashlib.sha256(p.read_bytes()).hexdigest() for p in dest.rglob('*') if p.is_file()};assert sum(p.stat().st_size for p in dest.rglob('*') if p.is_file())<512*1024**2
 p={'schema_version':1,'model_id':mid,'revision':'1'*40,'local_path':str(dest.resolve()),'file_manifest':manifest,'device':'cpu','dtype':'float32','max_input_tokens':512,'batch_size':1,'timeout_seconds':120,'max_chunks':2000}
 v,stats=encode(p,['hello world','birthday leave'],['a','b'],'document',execute=True);assert len(v)==2
 prepared=[cat['document_prefix']+t for t in ['hello world','birthday leave']]
 tokens=st.tokenizer(prepared,padding=True,return_tensors='pt',truncation=False);st.eval()
 with torch.no_grad():
  hidden=st[0].auto_model(**tokens).last_hidden_state
  if cat['pooling']=='mean':
   mask=tokens['attention_mask'].unsqueeze(-1);pooled=(hidden*mask).sum(1)/mask.sum(1)
  else:pooled=hidden[:,0]
  expected=torch.nn.functional.normalize(pooled,p=2,dim=1)
 assert torch.allclose(torch.tensor(v),expected,atol=1e-5)
 short=dict(p,max_input_tokens=3)
 try:encode(short,['hello world hello world'],['too-long'],'document',execute=True);raise AssertionError('truncated')
 except ValueError as e:assert getattr(e,'code',None)=='input_too_long',str(e)
 (root/'profile.json').write_text(json.dumps(p,indent=2)+'\n');records.append({'label':'tiny_random_sdk_not_pretrained','catalog_contract':mid,'parameters':params,'dimension':len(v[0]),'stats':stats,'length_rejected':True,'prefix_pooling_normalization_matches_manual':True,'profile_path':str(root/'profile.json')})
Path('docs/verification/p010/tiny-sdk.json').write_text(json.dumps({'status':'PASS','sdk':versions(),'pretrained_models_loaded':0,'actual_network_calls':0,'results':records},indent=2)+'\n');print('tiny SDK PASS')
