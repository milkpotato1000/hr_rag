"""Owned local CrossEncoder worker. No labels/GT in the protocol."""
import contextlib
import json
import sys
import time
from .reranker import profile, check_files, strict, versions
from .storage import require, RagError, fingerprint


def run(request):
    strict(request, {'profile', 'query', 'passages', 'ids'})
    require(isinstance(request['query'],str) and isinstance(request['passages'],list) and isinstance(request['ids'],list) and len(request['passages'])==len(request['ids']), 'invalid_pairs','reranking')
    p = profile(request['profile']); root = check_files(p)
    started = time.monotonic()
    from safetensors import safe_open
    stored={}
    for file in root.rglob('*.safetensors'):
        with safe_open(file,framework='pt',device='cpu') as weights:
            for key in weights.keys():
                require(key not in stored,'duplicate_model_tensor','reranking')
                stored[key]=list(weights.get_slice(key).get_shape())
    require(all(k in stored for k in ('classifier.dense.weight','classifier.dense.bias','classifier.out_proj.weight','classifier.out_proj.bias')) and stored['classifier.out_proj.bias']==[1], 'classifier_weights_missing','reranking')
    import torch
    from sentence_transformers import CrossEncoder
    model = CrossEncoder(str(root), device=p['device'], backend='torch', local_files_only=True, trust_remote_code=False, token=False,
        activation_fn=torch.nn.Identity(), max_length=p['max_pair_tokens'], prompts={},
        model_kwargs={'use_safetensors': True, 'torch_dtype': torch.float32},
        processor_kwargs={'local_files_only': True, 'trust_remote_code': False, 'token': False},
        config_kwargs={'local_files_only': True, 'trust_remote_code': False, 'token': False})
    actual={k:list(v.shape) for k,v in model.model.state_dict().items()}
    require(stored==actual,'model_weights_mismatch','reranking')
    require(model.config.num_labels == 1, 'classifier_head_mismatch', 'reranking')
    # XLM-R positions start at padding_idx+1, not zero.
    limit = min(p['max_pair_tokens'], model.tokenizer.model_max_length, model.config.max_position_embeddings - model.config.pad_token_id - 1)
    require(p['max_pair_tokens'] <= limit, 'model_pair_limit', 'reranking')
    pairs = [(request['query'], t) for t in request['passages']]
    tokens = [model.tokenizer(q, t, add_special_tokens=True, truncation=False, padding=False)['input_ids'] for q, t in pairs]
    bad = [i for i, t in zip(request['ids'], tokens) if len(t) > limit]
    if bad: return {'error': 'pair_too_long', 'offending_ids': bad}
    loaded = time.monotonic()
    scores = model.predict(pairs, batch_size=p['batch_size'], show_progress_bar=False, activation_fn=torch.nn.Identity(), apply_softmax=False, prompt='', processing_kwargs={'text': {'truncation': False}}).tolist()
    require(isinstance(scores,list) and all(type(x) in (float,int) for x in scores), 'classifier_head_mismatch', 'reranking')
    ended = time.monotonic()
    import resource
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return {'scores': [{'chunk_id': i, 'score': s} for i,s in zip(request['ids'],scores)],
            'pair_tokens': [len(t) for t in tokens], 'applied_limit': limit, 'preprocessing_hash': fingerprint(tokens),
            'load_ms': (loaded-started)*1000, 'score_ms': (ended-loaded)*1000, 'sdk_versions': versions(),
            'peak_rss_bytes': peak if sys.platform=='darwin' else peak*1024, 'rss_method': 'OS process-lifetime ru_maxrss; includes imports/load; no periodic sampling'}


def main():
    try:
        request = json.load(sys.stdin)
        with contextlib.redirect_stdout(sys.stderr): response = run(request)
    except RagError as e: response = {'error': e.code}
    except Exception: response = {'error': 'reranker_sdk_failed'}
    print(json.dumps(response, allow_nan=False))

if __name__ == '__main__': main()
