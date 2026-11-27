"""Locally generated random XLM-R, no pretrained downloads. Actual SDK probe."""
from pathlib import Path
import json, hashlib, time
from rag_package import reranker
from rag_package.storage import write_json

def main():
    import torch
    from tokenizers import Tokenizer, models, pre_tokenizers, processors
    from transformers import PreTrainedTokenizerFast, XLMRobertaConfig, XLMRobertaForSequenceClassification
    torch.manual_seed(20)
    root=Path('.rag-runs/p020-sdk/tiny').resolve();root.mkdir(parents=True,exist_ok=True)
    vocab={'<s>':0,'<pad>':1,'</s>':2,'<unk>':3,'생일':4,'휴가':5,'신청':6,'기간':7,'포인트':8}
    tok=Tokenizer(models.WordLevel(vocab,unk_token='<unk>'));tok.pre_tokenizer=pre_tokenizers.Whitespace()
    tok.post_processor=processors.RobertaProcessing(('</s>',2),('<s>',0))
    fast=PreTrainedTokenizerFast(tokenizer_object=tok,bos_token='<s>',eos_token='</s>',pad_token='<pad>',unk_token='<unk>',model_max_length=64)
    fast.save_pretrained(root)
    cfg=XLMRobertaConfig(vocab_size=len(vocab),hidden_size=32,num_hidden_layers=1,num_attention_heads=4,intermediate_size=48,max_position_embeddings=66,num_labels=1,pad_token_id=1,bos_token_id=0,eos_token_id=2)
    model=XLMRobertaForSequenceClassification(cfg).eval();model.save_pretrained(root,safe_serialization=True)
    count=sum(p.numel() for p in model.parameters());assert count<10_000_000
    p={'schema_version':1,'model_id':'BAAI/bge-reranker-v2-m3','revision':'1'*40,'local_path':str(root),'file_manifest':{f.name:hashlib.sha256(f.read_bytes()).hexdigest() for f in root.iterdir() if f.is_file()},'max_pair_tokens':64}
    p=reranker.profile(p);write_json(root.parent/'profile.json',p)
    rows=[{'chunk_id':'a','text':'생일 휴가 신청'},{'chunk_id':'b','text':'생일 포인트'}]
    batch=fast(['생일 휴가']*2,[r['text'] for r in rows],padding=True,truncation=False,return_tensors='pt');batch.pop('token_type_ids',None)
    with torch.no_grad():expected=model(**batch).logits[:,0].tolist()
    results=[]
    for name in reranker.CATALOG:
        current=dict(p,model_id=name);scores,work=reranker.score(current,'생일 휴가',rows)
        assert all(abs(r['score']-e)<1e-6 for r,e in zip(scores,expected)),(scores,expected)
        results.append({'profile_id':name,'scores':scores,'direct_logits':expected,'work':work})
    try:reranker.score(p,'생일 '*70,rows)
    except Exception as e:assert getattr(e,'code',None)=='pair_too_long' and e.offending_ids==['a','b']
    else:raise AssertionError('length not rejected')
    boundary=dict(p,max_pair_tokens=9)
    reranker.score(boundary,'생일 휴가',rows)
    try:reranker.score(dict(p,max_pair_tokens=8),'생일 휴가',rows)
    except Exception as e:assert e.code=='pair_too_long' and e.offending_ids==['a']
    else:raise AssertionError('special-token boundary missing')
    try:reranker.score(dict(p,timeout_seconds=1),'생일 휴가',rows)
    except Exception as e:assert e.code=='reranker_timeout' and e.work['workers']==1 and e.work['worker_exited'] and e.work['pairs'] is None
    else:raise AssertionError('expected cold-import timeout')
    import shutil
    bad=root.parent/'bad-head'
    if bad.exists():shutil.rmtree(bad)
    shutil.copytree(root,bad)
    badcfg=json.loads((bad/'config.json').read_text());badcfg['id2label']={'0':'a','1':'b'};badcfg['label2id']={'a':0,'b':1};write_json(bad/'config.json',badcfg)
    bp=dict(p,local_path=str(bad),file_manifest={f.name:hashlib.sha256(f.read_bytes()).hexdigest() for f in bad.iterdir() if f.is_file()})
    try:reranker.score(bp,'생일 휴가',rows)
    except Exception as e:assert e.code=='classifier_head_mismatch' and e.work['workers']==0
    else:raise AssertionError('head mismatch accepted')
    print(json.dumps({'status':'PASS','special_token_boundary':'PASS','actual_owned_worker_timeout':'PASS','bad_head_before_worker':'PASS' ,'kind':'locally_generated_random_not_pretrained','parameters':count,'bytes':sum(f.stat().st_size for f in root.iterdir()),'results':results,'overlength':'PASS','sdk':reranker.versions()},ensure_ascii=False,indent=2))
if __name__=='__main__': main()
