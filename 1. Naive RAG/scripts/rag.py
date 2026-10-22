"""One retrieval, whole-chunk context, one generation, then citation validation."""
import json
import math
import socket
from pathlib import Path
from time import perf_counter
from urllib.error import URLError

import evaluate_retrieval as evaluation
from runtime_common import STAGE, RUNTIME, LocalAPI, load_lock, sha256
from generation import Generator, digest_text, strict_json
from run_bm25_baseline import BM25Index

ABSTENTION = '제공된 문서만으로 확인할 수 없어 답변을 보류합니다. 인사 담당자 확인이 필요합니다.'
CHUNKS = STAGE / 'data/synthetic/chunks.jsonl'
INDEX = RUNTIME / 'index-v1'
PROMPTS = STAGE / 'prompts'
FIELDS = ('chunk_id', 'document_id', 'version', 'title', 'text', 'source')


class ProviderError(Exception):
    def __init__(self, cause):
        self.kind = 'timeout' if (isinstance(cause, (TimeoutError, socket.timeout)) or
                    isinstance(cause, URLError) and isinstance(cause.reason, (TimeoutError, socket.timeout))) else 'provider'
        super().__init__(str(cause))


def validate_input(question, retriever, top_k, max_context_chars, timeout_seconds):
    if not isinstance(question, str) or not question.strip():
        raise ValueError('question must be a nonempty string')
    if retriever not in ('dense', 'bm25'):
        raise ValueError('retriever must be dense or bm25')
    for name, value in [('top_k', top_k), ('max_context_chars', max_context_chars)]:
        if type(value) is not int or value <= 0:
            raise ValueError(name + ' must be a positive integer')
    if type(timeout_seconds) not in (int, float) or not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
        raise ValueError('timeout_seconds must be positive and finite')


def retrieve(question, chunks, corpus_hash, retriever, top_k, index_dir, timeout_seconds):
    started = perf_counter()
    if retriever == 'bm25':
        index = BM25Index(chunks)
        rows = index.search(question, top_k)[1]
        return rows, {'index_sha256': None, 'embedding_ms': 0,
                      'search_ms': (perf_counter() - started) * 1000}
    from dense_retrieval import DenseIndex
    lock, api = load_lock(), LocalAPI(timeout=timeout_seconds)
    # Verify local index before contacting the model; stale index is execution failure.
    with DenseIndex(index_dir, chunks, corpus_hash, lock) as index:
        open_ms = (perf_counter() - started) * 1000
        started = perf_counter()
        try:
            api.check(lock)
            vector = api.embed([question], lock['model']['dimension'])[0]
            api.check(lock)
        except (OSError, ValueError, KeyError) as exc:
            raise ProviderError(exc) from exc
        embed_ms = (perf_counter() - started) * 1000
        started = perf_counter()
        rows = index.search(vector, top_k)
        search_ms = (perf_counter() - started) * 1000
        return rows, {'index_sha256': sha256(Path(index_dir) / 'index-manifest.json'),
                      'index_hash_basis': 'validated index manifest; payload checked against corpus',
                      'index_manifest': index.manifest, 'index_open_ms': open_ms,
                      'embedding_ms': embed_ms, 'search_ms': search_ms}


def select_context(candidates, chunks, top_k, budget):
    selected, excluded, seen, used = [], [], set(), 0
    for rank, row in enumerate(candidates, 1):
        cid = row.get('chunk_id')
        if (not isinstance(cid, str) or cid not in chunks or cid in seen
                or type(row.get('score')) not in (int, float) or not math.isfinite(row['score'])):
            raise ValueError('invalid retrieval candidate')
        seen.add(cid)
        chunk = {key: chunks[cid][key] for key in FIELDS}
        size = len(json.dumps(chunk, ensure_ascii=False, separators=(',', ':')))
        if rank > top_k:
            excluded.append({'chunk_id': cid, 'reason': 'outside_top_k', 'chars': size})
        elif used + size > budget:
            excluded.append({'chunk_id': cid, 'reason': 'whole_chunk_exceeds_remaining_budget', 'chars': size})
        else:
            selected.append(chunk)
            used += size
    return selected, excluded, used


def validate_answer(raw, contexts):
    try:
        value = strict_json(raw)
    except (ValueError, TypeError) as exc:
        return None, ['invalid_content_json: ' + str(exc)]
    errors = []
    if not isinstance(value, dict) or set(value) != {'status', 'answer', 'citations'}:
        return None, ['response must contain exactly status, answer, citations']
    if value['status'] not in ('answered', 'abstained'):
        errors.append('invalid status')
    if not isinstance(value['answer'], str) or not value['answer'].strip():
        errors.append('answer must be a nonempty string')
    citations = value['citations']
    if not isinstance(citations, list):
        return None, errors + ['citations must be an array']
    if value['status'] == 'answered' and not citations:
        errors.append('answered requires at least one citation')
    source = {chunk['chunk_id']: chunk for chunk in contexts}
    enriched = []
    for citation in citations:
        if not isinstance(citation, dict) or set(citation) != {'chunk_id', 'quote'}:
            errors.append('citation must contain exactly chunk_id and quote; model metadata is forbidden')
            continue
        cid, quote = citation['chunk_id'], citation['quote']
        if not isinstance(cid, str) or cid not in source:
            errors.append('citation is outside transmitted contexts')
        elif not isinstance(quote, str) or not quote.strip() or quote not in source[cid]['text']:
            errors.append('quote is not a nonempty exact substring of source text')
        else:
            enriched.append({**citation, **{key: source[cid][key] for key in
                                           ('source', 'title', 'version', 'document_id')}})
    if errors:
        return None, errors
    if value['status'] == 'abstained':
        return {'status': 'abstained', 'answer': ABSTENTION, 'citations': [], 'reason': 'model_abstained'}, []
    return {'status': 'answered', 'answer': value['answer'], 'citations': enriched, 'reason': None}, []


def ask(question, retriever='dense', top_k=5, index_dir=INDEX, max_context_chars=8000,
        timeout_seconds=120, *, chunks_path=CHUNKS, retrieve_fn=retrieve, generator=None):
    """Reusable API; injected boundaries are for tests, never a silent live fallback."""
    started = perf_counter()
    trace = {'question': question, 'retriever': retriever,
             'settings': {'top_k': top_k, 'max_context_chars': max_context_chars, 'timeout_seconds': timeout_seconds},
             'candidates': [], 'contexts': [], 'excluded': [], 'validation': [],
             'generation_calls': 0, 'timings_ms': {'retrieval': 0, 'context': 0, 'generation': 0}}
    phase, phase_start = 'input', started
    try:
        validate_input(question, retriever, top_k, max_context_chars, timeout_seconds)
        phase = 'execution'
        rows, corpus_hash = evaluation.read_jsonl(Path(chunks_path))
        chunks = evaluation.validate_chunks(rows)
        trace['corpus_sha256'] = corpus_hash
        phase, phase_start = 'retrieval', perf_counter()
        candidates, retrieval_info = retrieve_fn(question, chunks, corpus_hash, retriever, top_k,
                                                  index_dir, timeout_seconds)
        trace['timings_ms']['retrieval'] = (perf_counter() - phase_start) * 1000
        trace['retrieval'] = retrieval_info
        trace['candidates'] = [dict(row, **{key: chunks[row['chunk_id']][key] for key in FIELDS if key != 'chunk_id'})
                               for row in candidates]
        phase, phase_start = 'context', perf_counter()
        contexts, excluded, used = select_context(candidates, chunks, top_k, max_context_chars)
        trace.update(contexts=contexts, excluded=excluded, context_chars=used)
        system = (PROMPTS / 'system-v2.txt').read_text()
        template = strict_json((PROMPTS / 'context-v1.json').read_text())
        if tuple(template['fields']) != FIELDS:
            raise ValueError('unsupported context template fields')
        messages = [{'role': 'system', 'content': system},
                    {'role': 'user', 'content': json.dumps({'question': question, 'contexts': contexts},
                                                          ensure_ascii=False, separators=(',', ':'))}]
        trace['prompt'] = {'system_version': 'system-v2', 'context_version': template['version'],
                           'system_sha256': digest_text(system),
                           'context_template_sha256': sha256(PROMPTS / 'context-v1.json'),
                           'messages': messages, 'messages_sha256': digest_text(json.dumps(messages, ensure_ascii=False))}
        trace['timings_ms']['context'] = (perf_counter() - phase_start) * 1000
        if not contexts:
            result = {'status': 'abstained', 'answer': ABSTENTION, 'citations': [], 'reason': 'no_context'}
        else:
            phase, phase_start = 'generation', perf_counter()
            provider = generator if generator is not None else Generator(timeout=timeout_seconds)
            trace['generation'] = {'model': provider.lock['model']['name'], 'digest': provider.lock['model']['digest'],
                                   'ollama_version': provider.lock['ollama_version'], 'request': provider.lock['request']}
            trace['generation_calls'] = 1
            try:
                raw, observations = provider.generate(messages)
            except (OSError, ValueError, KeyError) as exc:
                raise ProviderError(exc) from exc
            trace['timings_ms']['generation'] = (perf_counter() - phase_start) * 1000
            trace['raw_content'] = raw
            trace['generation']['observations'] = observations
            phase = 'validation'
            result, errors = validate_answer(raw, contexts)
            trace['validation'] = errors
            trace['citation_structure_valid'] = not errors
            trace['semantic_support'] = 'not_automatically_evaluated'
            if errors:
                result = {'status': 'abstained', 'answer': ABSTENTION, 'citations': [], 'reason': 'invalid_model_response'}
    except (OSError, ValueError, KeyError, TypeError, RuntimeError, ImportError, ProviderError) as exc:
        if phase in trace['timings_ms']:
            trace['timings_ms'][phase] = (perf_counter() - phase_start) * 1000
        kind = exc.kind if isinstance(exc, ProviderError) else ('input' if phase == 'input' else 'execution')
        trace['error'] = {'kind': kind, 'phase': phase, 'message': str(exc)}
        result = {'status': 'error', 'answer': '실행 중 오류가 발생했습니다. trace의 오류를 확인하고 다시 시도하세요.',
                  'citations': [], 'reason': kind}
    trace['timings_ms']['total'] = (perf_counter() - started) * 1000
    return {**result, 'trace': trace}
