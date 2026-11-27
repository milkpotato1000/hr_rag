"""Actual SDK integration with local random weights, no pretrained download."""
import os,socket,json,hashlib,sys
from pathlib import Path
os.environ.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',HF_HUB_DISABLE_TELEMETRY='1',TOKENIZERS_PARALLELISM='false')
def forbidden(*a,**k):raise AssertionError('network forbidden')
socket.socket.connect=forbidden;socket.getaddrinfo=forbidden
import torch
from transformers import BertConfig,BertModel,BertTokenizerFast
from sentence_transformers import SentenceTransformer,models
from rag_package import embedding,chunk_artifact
from rag_package.storage import write_json,read_json,digest
from rag_package.workspace import init
from rag_package.documents import snapshot
base=Path('.rag-runs/p030-sdk').resolve();base.mkdir(parents=True,exist_ok=True);raw=base/'raw';raw.mkdir(exist_ok=True)
vocab=['[PAD]','[UNK]','[CLS]','[SEP]','[MASK]','passage',':','hello','world','birthday','leave']
(raw/'vocab.txt').write_text('\n'.join(vocab)+'\n');tok=BertTokenizerFast(vocab_file=str(raw/'vocab.txt'));tok.save_pretrained(raw)
torch.manual_seed(42);model=BertModel(BertConfig(vocab_size=len(tok),hidden_size=384,num_hidden_layers=1,num_attention_heads=4,intermediate_size=32,max_position_embeddings=512));params=sum(p.numel() for p in model.parameters());model.save_pretrained(raw,safe_serialization=True)
st=SentenceTransformer(modules=[models.Transformer(str(raw),max_seq_length=512,model_args={'local_files_only':True,'use_safetensors':True},tokenizer_args={'local_files_only':True}),models.Pooling(384,pooling_mode='mean'),models.Normalize()],device='cpu');dest=base/'export';st.save_pretrained(str(dest),safe_serialization=True)
p={'schema_version':1,'model_id':'intfloat/multilingual-e5-small','revision':'1'*40,'local_path':str(dest),'file_manifest':{str(f.relative_to(dest)):digest(f.read_bytes()) for f in dest.rglob('*') if f.is_file()},'device':'cpu','dtype':'float32','max_input_tokens':512,'batch_size':2,'timeout_seconds':120,'max_chunks':2000}
ws=base/'ws';init(ws);write_json(ws/'embedding.json',p);snapshot(ws/'sources.json',ws/'snapshot')
write_json(ws/'semantic.json',{'schema_version':1,'method':'semantic','size_chars':200,'overlap_chars':20,'unit_max_chars':40,'distance_threshold':.5,'minimum_chars':40,'embedding_config':'embedding.json'})
r=chunk_artifact.build(ws/'snapshot',ws/'semantic.json',ws/'chunks',execute=True);assert r['status']=='ready',r
assert r['work']['unit_observation']['workers_started']==1 and r['work']['unit_observation']['worker_exited']
rr,_,_,_=chunk_artifact.load(ws/'chunks');us=read_json(ws/'chunks/units.json');saved=chunk_artifact.unpack((ws/'chunks/unit-vectors.f32').read_bytes(),len(us),384)
expected=st.encode(['passage: '+u['text'] for u in us],normalize_embeddings=True,convert_to_tensor=True);assert torch.allclose(torch.tensor(saved),expected,atol=1e-5)
obs={};v,w=embedding.encode(p,['   \n'],['whitespace'],'document',execute=True,allow_whitespace=True,observation=obs);assert len(v)==1 and len(v[0])==384 and obs['workers_started']==1
embedding.encode=lambda *a,**kw:(_ for _ in ()).throw(AssertionError('no replay model'))
chunk_artifact.replay(ws/'chunks');write_json(ws/'derive.json',dict(read_json(ws/'semantic.json'),distance_threshold=1.5));chunk_artifact.derive(ws/'chunks',ws/'derive.json',ws/'derived');chunk_artifact.replay(ws/'derived')
write_json(Path('docs/verification/p030/tiny-sdk.json'),{'status':'PASS','label':'tiny_random_sdk_not_pretrained','parameters':params,'sdk':embedding.versions(),'pretrained_loads':0,'network_calls':0,'manual_document_prefix_vectors_match':True,'float32_replay':True,'whitespace_encoded':True,'model_free_derive':True,'work':r['work']});print('P030 tiny SDK PASS')
