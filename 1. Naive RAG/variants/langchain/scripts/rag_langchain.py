"""One retrieval, whole-chunk context, one generation, then citation validation."""
import json
import math
import socket
from pathlib import Path
from time import perf_counter
from types import MappingProxyType
from urllib.error import URLError

import evaluate_retrieval as evaluation
from runtime_common import STAGE, RUNTIME, LocalAPI, load_lock, sha256
from generation import Generator, digest_text, strict_json, CITATION_MODE, RESPONSE_CONTRACT
from run_bm25_baseline import BM25Index

from rag import (ABSTENTION, CHUNKS, INDEX, PROMPTS, FIELDS, ProviderError,
                 validate_input, retrieve, select_context, context_snapshot, validate_answer)
import os
# This local experiment never enables outbound LangSmith tracing.
os.environ['LANGCHAIN_TRACING_V2'] = 'false'
os.environ['LANGSMITH_TRACING'] = 'false'
from langchain_core.runnables import RunnableLambda, RunnableBranch
from langsmith import tracing_context

def ask(question, retriever='dense', top_k=5, index_dir=INDEX, max_context_chars=8000,
        timeout_seconds=120, *, chunks_path=CHUNKS, retrieve_fn=retrieve, generator=None):
    """Explicit request-local Runnable stages; unchanged provider boundaries."""
    started = perf_counter()
    trace = {'question': question, 'retriever': retriever,
             'settings': {'top_k': top_k, 'max_context_chars': max_context_chars, 'timeout_seconds': timeout_seconds},
             'candidates': [], 'contexts': [], 'excluded': [], 'validation': [],
             'citation_mode': CITATION_MODE, 'response_contract': RESPONSE_CONTRACT,
             'semantic_support': 'not_automatically_evaluated',
             'generation_calls': 0, 'timings_ms': {'retrieval': 0, 'context': 0, 'generation': 0}}
    phase, phase_start = 'input', started
    rows, corpus_hash, chunks, candidates, snapshot, contexts, messages, raw, result = (None,) * 9
    def load_corpus(_):
        nonlocal phase, phase_start, rows, corpus_hash, chunks, candidates, snapshot, contexts, messages, raw, result
        validate_input(question, retriever, top_k, max_context_chars, timeout_seconds)
        phase = 'execution'
        rows, corpus_hash = evaluation.read_jsonl(Path(chunks_path))
        chunks = evaluation.validate_chunks(rows)
        trace['corpus_sha256'] = corpus_hash
        return None

    def search(_):
        nonlocal phase, phase_start, rows, corpus_hash, chunks, candidates, snapshot, contexts, messages, raw, result
        phase, phase_start = 'retrieval', perf_counter()
        candidates, retrieval_info = retrieve_fn(question, chunks, corpus_hash, retriever, top_k,
                                                  index_dir, timeout_seconds)
        trace['timings_ms']['retrieval'] = (perf_counter() - phase_start) * 1000
        trace['retrieval'] = retrieval_info
        trace['candidates'] = [dict(row, **{key: chunks[row['chunk_id']][key] for key in FIELDS if key != 'chunk_id'})
                               for row in candidates]
        return None

    def build_context(_):
        nonlocal phase, phase_start, rows, corpus_hash, chunks, candidates, snapshot, contexts, messages, raw, result
        phase, phase_start = 'context', perf_counter()
        contexts, excluded, used = select_context(candidates, chunks, top_k, max_context_chars)
        snapshot = context_snapshot(contexts)
        contexts = [dict(chunk) for chunk in snapshot]
        trace.update(contexts=contexts, excluded=excluded, context_chars=used)
        system = (PROMPTS / 'system-v3.txt').read_text()
        template = strict_json((PROMPTS / 'context-v1.json').read_text())
        if tuple(template['fields']) != FIELDS:
            raise ValueError('unsupported context template fields')
        messages = [{'role': 'system', 'content': system},
                    {'role': 'user', 'content': json.dumps({'question': question, 'contexts': contexts},
                                                          ensure_ascii=False, separators=(',', ':'))}]
        trace['prompt'] = {'system_version': 'system-v3', 'context_version': template['version'],
                           'system_sha256': digest_text(system),
                           'context_template_sha256': sha256(PROMPTS / 'context-v1.json'),
                           'messages': messages, 'messages_sha256': digest_text(json.dumps(messages, ensure_ascii=False))}
        trace['timings_ms']['context'] = (perf_counter() - phase_start) * 1000
        return None

    def generate(_):
        nonlocal phase, phase_start, rows, corpus_hash, chunks, candidates, snapshot, contexts, messages, raw, result
        phase, phase_start = 'generation', perf_counter()
        provider = generator if generator is not None else Generator(timeout=timeout_seconds)
        trace['generation'] = {'model': provider.lock['model']['name'], 'digest': provider.lock['model']['digest'],
                               'ollama_version': provider.lock['ollama_version'], 'request': None,
                               'request_dispatched': False, 'allowed_ids': [c['chunk_id'] for c in snapshot]}
        def record_request(request):
            trace['generation'].update(request=request, request_dispatched=True,
                schema_sha256=digest_text(json.dumps(request['format'], ensure_ascii=False, sort_keys=True)))
        trace['generation_calls'] = 1
        try:
            raw, observations = provider.generate(messages, [c['chunk_id'] for c in snapshot], on_send=record_request)
        except (OSError, ValueError, KeyError) as exc:
            raise ProviderError(exc) from exc
        trace['timings_ms']['generation'] = (perf_counter() - phase_start) * 1000
        trace['raw_content'] = raw
        trace['generation']['observations'] = observations
        return None

    def validate(_):
        nonlocal phase, phase_start, rows, corpus_hash, chunks, candidates, snapshot, contexts, messages, raw, result
        phase = 'validation'
        result, errors = validate_answer(raw, snapshot)
        trace['validation'] = errors
        trace['citation_structure_valid'] = not errors
        trace['semantic_support'] = 'not_automatically_evaluated'
        if errors:
            result = {'status': 'abstained', 'answer': ABSTENTION, 'citations': [], 'reason': 'invalid_model_response'}
        trace['citation_assembly'] = [{'chunk_id': c['chunk_id'], 'origin': 'request_context_snapshot',
            'text_sha256': digest_text(c['quote'])} for c in result['citations']]
        return None

    def abstain(_):
        nonlocal result
        result = {'status': 'abstained', 'answer': ABSTENTION, 'citations': [], 'reason': 'no_context'}

    chain = (RunnableLambda(load_corpus, name='load_corpus')
             | RunnableLambda(search, name='retrieve')
             | RunnableLambda(build_context, name='snapshot_and_messages')
             | RunnableBranch((lambda _: not contexts, RunnableLambda(abstain, name='no_context')),
                              RunnableLambda(generate, name='generate_once')
                              | RunnableLambda(validate, name='validate_and_assemble')))
    try:
        with tracing_context(enabled=False):
            chain.invoke(None, config={'callbacks': [], 'recursion_limit': 20})
    except (OSError, ValueError, KeyError, TypeError, RuntimeError, ImportError, ProviderError) as exc:
        if phase in trace['timings_ms']:
            trace['timings_ms'][phase] = (perf_counter() - phase_start) * 1000
        kind = exc.kind if isinstance(exc, ProviderError) else ('input' if phase == 'input' else 'execution')
        trace['error'] = {'kind': kind, 'phase': phase, 'message': str(exc)}
        result = {'status': 'error', 'answer': '실행 중 오류가 발생했습니다. trace의 오류를 확인하고 다시 시도하세요.',
                  'citations': [], 'reason': kind}
    trace['timings_ms']['total'] = (perf_counter() - started) * 1000
    return {**result, 'trace': trace}
