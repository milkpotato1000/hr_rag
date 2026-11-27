"""Owned local CrossEncoder worker. No labels/GT in the protocol."""
import contextlib
import json
import sys
import time
from .reranker import profile, check_files, strict, versions
from .storage import require, RagError, fingerprint

LEGACY_MODEL = 'cross-encoder/mmarco-mMiniLMv2-L12-H384-v1'
LEGACY_REVISION = '1427fd652930e4ba29e8149678df786c240d8825'
POSITION_KEY = 'roberta.embeddings.position_ids'


def validate_state(stored, model, p, stored_buffer=None):
    """One pinned deterministic legacy buffer; all persistent weights stay exact."""
    import torch
    actual = {k: list(v.shape) for k, v in model.state_dict().items()}
    compared = dict(stored)
    diagnostic = {'stage': 'persistent_state', 'legacy_buffer': 'absent'}
    if POSITION_KEY in stored and p['model_id'] == LEGACY_MODEL and p['revision'] == LEGACY_REVISION:
        diagnostic.update(stage='legacy_position_buffer', legacy_buffer='invalid')
        buffers = dict(model.named_buffers()); parameters = dict(model.named_parameters())
        rebuilt = buffers.get(POSITION_KEY)
        valid = (model.config.max_position_embeddings == 514 and
                 stored[POSITION_KEY] == [1, 514] and
                 stored_buffer is not None and stored_buffer.dtype == torch.int64 and
                 list(stored_buffer.shape) == [1, 514] and
                 POSITION_KEY not in parameters and POSITION_KEY not in actual and
                 rebuilt is not None and rebuilt.dtype == torch.int64 and
                 list(rebuilt.shape) == [1, 514] and not rebuilt.requires_grad)
        if valid:
            expected = torch.arange(514, dtype=torch.int64).reshape(1, 514)
            valid = torch.equal(stored_buffer.cpu(), expected) and torch.equal(rebuilt.cpu(), expected)
        if not valid:
            err = RagError('model_weights_mismatch', 'reranking'); err.weight_validation = diagnostic; raise err
        del compared[POSITION_KEY]
        diagnostic.update(stage='persistent_state', legacy_buffer='verified',
                          buffer_key=POSITION_KEY, buffer_dtype='I64', buffer_shape=[1, 514],
                          buffer_rule='arange(514)', buffer_nontrainable=True)
    missing = sorted(set(compared) - set(actual))
    unexpected = sorted(set(actual) - set(compared))
    mismatched = sorted(k for k in compared.keys() & actual.keys() if compared[k] != actual[k])
    diagnostic.update(missing=missing[:20], unexpected=unexpected[:20], mismatched=mismatched[:20],
                      difference_counts={'missing':len(missing),'unexpected':len(unexpected),'mismatched':len(mismatched)},
                      stored_count=len(stored), loaded_count=len(actual))
    if missing or unexpected or mismatched:
        err = RagError('model_weights_mismatch', 'reranking'); err.weight_validation = diagnostic; raise err
    return diagnostic


def run(request):
    strict(request, {'profile', 'query', 'passages', 'ids'})
    require(isinstance(request['query'],str) and isinstance(request['passages'],list) and isinstance(request['ids'],list) and len(request['passages'])==len(request['ids']), 'invalid_pairs','reranking')
    p = profile(request['profile']); root = check_files(p)
    started = time.monotonic()
    from safetensors import safe_open
    stored={}; stored_buffer=None
    for file in root.rglob('*.safetensors'):
        with safe_open(file,framework='pt',device='cpu') as weights:
            for key in weights.keys():
                require(key not in stored,'duplicate_model_tensor','reranking')
                stored[key]=list(weights.get_slice(key).get_shape())
                if key == POSITION_KEY and p['model_id'] == LEGACY_MODEL and p['revision'] == LEGACY_REVISION:
                    # Read only the expected small buffer, never an arbitrary extra tensor.
                    if stored[key] == [1, 514] and weights.get_slice(key).get_dtype() == 'I64':
                        stored_buffer = weights.get_tensor(key)
    require(all(k in stored for k in ('classifier.dense.weight','classifier.dense.bias','classifier.out_proj.weight','classifier.out_proj.bias')) and stored['classifier.out_proj.bias']==[1], 'classifier_weights_missing','reranking')
    import torch
    from sentence_transformers import CrossEncoder
    model = CrossEncoder(str(root), device=p['device'], backend='torch', local_files_only=True, trust_remote_code=False, token=False,
        activation_fn=torch.nn.Identity(), max_length=p['max_pair_tokens'], prompts={},
        model_kwargs={'use_safetensors': True, 'torch_dtype': torch.float32},
        processor_kwargs={'local_files_only': True, 'trust_remote_code': False, 'token': False},
        config_kwargs={'local_files_only': True, 'trust_remote_code': False, 'token': False})
    weight_validation = validate_state(stored, model.model, p, stored_buffer)
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
    return {'weight_validation': weight_validation, 'scores': [{'chunk_id': i, 'score': s} for i,s in zip(request['ids'],scores)],
            'pair_tokens': [len(t) for t in tokens], 'applied_limit': limit, 'preprocessing_hash': fingerprint(tokens),
            'load_ms': (loaded-started)*1000, 'score_ms': (ended-loaded)*1000, 'sdk_versions': versions(),
            'peak_rss_bytes': peak if sys.platform=='darwin' else peak*1024, 'rss_method': 'OS process-lifetime ru_maxrss; includes imports/load; no periodic sampling'}


def main():
    try:
        request = json.load(sys.stdin)
        with contextlib.redirect_stdout(sys.stderr): response = run(request)
    except RagError as e:
        response = {'error': e.code}
        if hasattr(e, 'weight_validation'): response['weight_validation'] = e.weight_validation
    except Exception: response = {'error': 'reranker_sdk_failed'}
    print(json.dumps(response, allow_nan=False))

if __name__ == '__main__': main()
