"""Reproduce the saved-vector experiment with an installed rag-lab and fresh output."""
import argparse
from collections import Counter
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import struct
import subprocess

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / 'p032-s2b-recovery001/run001/semantic'
QUESTION = '생일 특별휴가는 사용 며칠 전까지 신청해야 하나요?'
QUOTES = {
    'deadline': '사용 3영업일 전까지 휴가 시스템에서 신청',
    'approval': '팀장의 승인을 받아야 한다.',
    'both': '생일 특별휴가는 사용 3영업일 전까지 휴가 시스템에서 신청하고 팀장의 승인을 받아야 한다.',
}


def read(path):
    return json.loads(path.read_text())


def save(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')


def hashes():
    return {str(p.relative_to(PARENT)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(PARENT.rglob('*')) if p.is_file()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', required=True, type=Path)
    args = parser.parse_args()
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    cli = shutil.which('rag-lab')
    assert cli, 'Install rag-lab in the active environment first'
    before = hashes()
    units = read(PARENT / 'units.json')
    root = read(PARENT / 'chunk.json')
    raw = (PARENT / 'unit-vectors.f32').read_bytes()
    assert hashlib.sha256(raw).hexdigest() == root['vectors_hash']
    vectors = list(struct.iter_unpack('<384f', raw))
    source = (PARENT / 'snapshot/hr-handbook/canonical.txt').read_text()
    assert len(units) == len(vectors) == 567
    offsets = {key: source.index(quote, source.index(QUOTES['both'])) for key, quote in QUOTES.items()}
    thresholds = [0.35, 0.15, 0.05]
    retrieval = dict(method='bm25', candidate_k=20, top_k=5, rrf_k=60, context_budget_chars=4000)
    save(out / 'inputs.json', dict(parent_files=before, thresholds=thresholds, question=QUESTION,
                                    quotes=QUOTES, retrieval=retrieval))
    # Each installed CLI process denies sockets and child process execution.
    (out / 'sitecustomize.py').write_text(
        "import sys\ndef audit(event, args):\n"
        "    if event.startswith(('socket.', 'subprocess.', 'os.exec', 'os.posix_spawn', 'os.system')):\n"
        "        raise RuntimeError('offline experiment: '+event)\nsys.addaudithook(audit)\n")
    env = dict(PATH=os.defpath, LANG='en_US.UTF-8', PYTHONPATH=str(out), PYTHONDONTWRITEBYTECODE='1')

    def run(*argv):
        subprocess.run([cli, *map(str, argv)], cwd=out, env=env, check=True, stdout=subprocess.DEVNULL)

    rows = []
    baseline_ends = {b['end'] for b in root['base']}
    distances = [1 - sum(x*y for x, y in zip(a, b))/(math.hypot(*a)*math.hypot(*b))
                 for a, b in zip(vectors, vectors[1:])]
    for threshold in thresholds:
        target = out / str(threshold)
        target.mkdir()
        chunk = target / 'chunks'
        cfg = {k: v for k, v in root['config'].items() if k != 'model'}
        cfg.update(distance_threshold=threshold, embedding_config=str(HERE / 'embedding-profile.json'))
        save(target / 'policy.json', cfg)
        run('chunk-derive', '--run', PARENT, '--config', target/'policy.json', '--out', chunk)
        record = read(chunk/'chunk.json')
        assert record['parent_fingerprint'] == root['chunk_fingerprint']
        assert record['work']['boundary_model_jobs'] == record['work']['dispatches'] == 0
        assert (chunk/'unit-vectors.f32').read_bytes() == raw and read(chunk/'units.json') == units
        base = record['base']
        start = 0
        expected = []
        for i, d in enumerate(distances, start=1):
            u = units[i]
            assert abs(d-record['details']['distances'][i-1]['distance']) < 1e-10
            reason = ('maximum' if u['end']-start > 192 else
                      'semantic' if u['start']-start >= 120 and d >= threshold else None)
            if reason:
                expected.append((start, u['start'], reason))
                start = u['start']
        expected.append((start, len(source), 'document_end'))
        assert expected == [(b['start'], b['end'], b['reason']) for b in base]
        coverage = read(chunk/'coverage.json')['coverage']
        chunks = read(chunk/'chunks.json')
        assert len(coverage) == len(base) == len(chunks)
        for i, (b, c, emitted) in enumerate(zip(base, coverage, chunks)):
            left = max(base[max(i-1, 0)]['start'], b['start']-64)
            assert (c['base_start'], c['base_end'], c['start'], c['end']) == (b['start'], b['end'], left, b['end'])
            assert (emitted['start'], emitted['end'], emitted['text']) == (left, b['end'], source[left:b['end']])
        if threshold == 0.35:
            assert base == root['base'] and chunks == read(PARENT/'chunks.json')
            assert coverage == read(PARENT/'coverage.json')['coverage']
        changed = sorted(baseline_ends ^ {b['end'] for b in base})
        first = None
        if changed:
            pos = changed[0]
            i = next(i for i, unit in enumerate(units) if unit['start'] == pos)
            segment = next(b for b in base if b['start'] < pos <= b['end'])
            first = dict(offset=pos, before=units[i-1]['text'], after=units[i]['text'],
                         distance=distances[i-1], accumulated=pos-segment['start'],
                         including_next=units[i]['end']-segment['start'], reason=segment['reason'],
                         overlap=[max(segment['start'], pos-64), pos])
        save(target/'search.json', dict(schema_version=3, retrieval=retrieval, chunk_artifact=str(chunk),
             embedding_config=None, llm_config=str(HERE.parents[2]/'rag_package/resources/sample/llm-local.json')))
        run('build', '--config', target/'search.json', '--snapshot', PARENT/'snapshot', '--out', target/'build')
        run('ask', '--config', target/'search.json', '--run', target/'build', '--question', QUESTION, '--out', target/'ask')
        result = read(target/'ask/result.json')
        ranks = {r['chunk_id']: r['rank'] for r in result['retrieval_trace']['bm25']}
        context = {c['chunk_id']: n for n, c in enumerate(result['contexts'], 1)}
        assert len(ranks) == 20 and len(context) == 5
        assert result['generation_requests'] == result['embedding_work']['jobs'] == 0
        matches = {}
        for key, pos in offsets.items():
            ids = [c['chunk_id'] for c in chunks if c['start'] <= pos and c['end'] >= pos+len(QUOTES[key])]
            matches[key] = dict(candidate=sorted(ranks[i] for i in ids if i in ranks),
                                delivered=sorted(context[i] for i in ids if i in context))
        rows.append(dict(threshold=threshold, chunks=len(chunks), reasons=Counter(b['reason'] for b in base),
                         first_change=first, evidence=matches, fingerprint=record['chunk_fingerprint']))
    assert before == hashes()
    save(out/'results.json', dict(parent=root['chunk_fingerprint'], source_characters=len(source),
                                  units=len(units), distances=len(distances), original_files_preserved=len(before),
                                  embedding=0, generation=0, rows=rows))


if __name__ == '__main__':
    main()
