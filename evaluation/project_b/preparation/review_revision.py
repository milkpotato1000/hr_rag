"""P021 deterministic offline review revision. Never edits or calls the parent run."""
import copy
import hashlib
import html
import json
import re
import shutil
import tempfile
from pathlib import Path
from core import digest, file_hash, locate, read, validate_review_packet, write

PARENT_SHA = '6f9b0b673b4b18e3739ac5038f048c00c8563ceaeab9dde105dedea9b1e13508'
CANONICAL_SHA = '1c6867d284d136b2eb1cf6f9a707506480946988eaa155ae46b13ce25e2eb298'
VERSION = 'p021-review-v1'
MERGES = {'gt01-c01': 'gt01-c02', 'gt01-c03': 'gt01-c02', 'gt05-c01': 'gt05-c02'}
TEXTS = {
    'gt01-c02': '생일 특별휴가는 입사 후 3개월이 지난 재직자를 대상으로 매년 1일 신청할 수 있으며, 수습 중인 직원은 대상에서 제외됩니다.',
    'gt04-c01': '재택근무일에는 사무실 출근일에 지급하는 식대를 지원하지 않습니다.',
}


def inventory(parent):
    return {str(p.relative_to(parent)): file_hash(p) for p in sorted(parent.rglob('*')) if p.is_file()}


def build(parent):
    from report import verify_packet
    old = verify_packet(parent)
    if old['packet_sha256'] != PARENT_SHA or old['source_canonical_sha256'] != CANONICAL_SHA:
        raise ValueError('P021 requires the exact reviewed run001 packet')
    packet = copy.deepcopy(old)
    packet.pop('packet_sha256')
    packet['review_version'] = VERSION
    packet['scope'] = 'P021 offline revision of run001; unapproved review candidates, not a new model experiment or P013 evaluation'
    packet['parent'] = dict(path='../run001/packet.json', packet_sha256=PARENT_SHA,
                            execution_history='../run001/ledger.json',
                            files={n:h for n,h in inventory(parent).items() if n != '.runner.lock'})
    packet['new_model_requests'] = 0
    mapping = dict(version=VERSION, parent_packet_sha256=PARENT_SHA, old_claim_count=48,
                   new_claim_count=45, human_approval=None, changes=[])
    for revision in packet['codex_revision_history']:
        revision['path'] = '../run001/' + revision['path']
    for q, prior in zip(packet['questions'], old['questions']):
        for attempt in q['model_original_attempts']:
            attempt['artifact'] = '../run001/' + attempt['artifact']
        if 'absence_review' in q:
            q['absence_review'] = '../run001/absence-review.json'
        claims = q['codex_source_checked']['claims']
        kept = [c for c in claims if c['id'] not in MERGES]
        for c in kept:
            c['text'] = TEXTS.get(c['id'], c['text'])
        if kept:
            answer = '\n'.join(c['text'] for c in kept)
            for c in kept:
                c['answer_span'] = locate(answer, c['text'])
            q['codex_source_checked'] = dict(answer=answer, claims=kept)
        targets = {c['id']: c for c in kept}
        for original in prior['codex_source_checked']['claims']:
            target = targets[MERGES.get(original['id'], original['id'])]
            reason = ('대상·기간·연간 일수·수습 제외 조건을 한 권리 규칙으로 통합' if target['id']=='gt01-c02'
                      else '자격시험 응시 대상과 연1일 권리를 포함한 기존 c02로 통합' if target['id']=='gt05-c02'
                      else '재택일 미지원과 출근일 지급액을 분리; 금액은 gt04-c02에 보존' if target['id']=='gt04-c01'
                      else '의미·ID·원문 근거 유지; 답변 위치만 재계산')
            mapping['changes'].append(dict(old=copy.deepcopy(original), new=copy.deepcopy(target),
                                           reason=reason, merged=original['id'] in MERGES))
        q['review_revision'] = 'revision-mapping.json'
    packet['review_mapping_sha256'] = digest(mapping)
    packet['packet_sha256'] = digest(packet)
    validate_review_packet(packet)
    validate_claims(packet, parent)
    return packet, mapping


def validate_claims(packet, parent):
    canonical_path = parent/'source/extracted/canonical/hr-v4-handbook.txt'
    canonical = canonical_path.read_text()
    pages = read(parent/'source/extracted/manifest.json')['documents'][0]['pages']
    if file_hash(canonical_path) != CANONICAL_SHA:
        raise ValueError('canonical changed')
    claims = [c for q in packet['questions'] for c in q['codex_source_checked']['claims']]
    if len(claims) != 45 or len({c['id'] for c in claims}) != 45:
        raise ValueError('expected 45 distinct retained claims')
    for q in packet['questions']:
        checked = q['codex_source_checked']
        if checked['claims'] and checked['answer'] != '\n'.join(c['text'] for c in checked['claims']):
            raise ValueError('answer differs from claim list')
        for c in checked['claims']:
            s = c['source']; a, b = c['answer_span']
            actual_pages = [p['page_number'] for p in pages if p['start'] < s['end'] and p['end'] > s['start']]
            if (canonical[s['start']:s['end']] != s['quote'] or
                hashlib.sha256(s['quote'].encode()).hexdigest() != s['quote_sha256'] or
                s['canonical_sha256'] != CANONICAL_SHA or s['pages'] != actual_pages or
                checked['answer'][a:b] != c['text']):
                raise ValueError('claim source/answer offset, hash or page mismatch')
    birthday = next(c for c in claims if c['id']=='gt01-c02')
    if (birthday['source']['article_id'], birthday['source']['start'], birthday['source']['end']) != ('BD-01',272,336):
        raise ValueError('merged birthday evidence must retain the full rule')


def render(packet, mapping):
    esc = html.escape
    def details(title, content, ident=''):
        attr = ' id="'+esc(ident)+'"' if ident else ''
        return '<details'+attr+'><summary>'+esc(title)+'</summary>'+content+'</details>'
    def pretty(value):
        return '<pre>'+esc(json.dumps(value, ensure_ascii=False, indent=2))+'</pre>'
    parts = ['<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">',
             '<title>정답 후보 검토 · 질문과 원문 근거</title><style>'+CSS+'</style></head><body><main>',
             '<header><p class="eyebrow">HR RAG · 검토본 002</p><h1>질문과 근거를 함께 읽기</h1>',
             '<p class="intro">원문을 기준으로 정리한 <strong>미승인 정답 후보</strong>입니다. 아래 주장과 근거가 맞는지 확인해 주세요.</p>',
             '<p class="badge">질문 10개 · 정답 주장 45개 · 판정 후보 18개 · 사람 미승인</p>',
             '<p>기존 run001을 근거로 만든 검토본 개정입니다. 이번 개정의 모델 호출은 <strong>0회</strong>입니다. ',
             '<a href="../run001/review.html">이전 검토본 보기</a></p></header>',
             '<nav aria-label="질문 바로가기"><h2>질문 바로가기</h2><ol>']
    for q in packet['questions']:
        parts.append('<li><a href="#'+esc(q['id'])+'">'+esc(q['question'])+'</a></li>')
    parts.append('</ol><a href="#judgements">판정 후보 18개</a> · <a href="#experiment">실험 기록·한계</a></nav>')
    parts.append('<p class="guide">읽는 법: <b>gt</b>는 질문·정답 항목, <b>c</b>는 주장 ID이며 청크가 아닙니다. '
                 '<b>조항</b>은 규정집의 조항 ID, <b>페이지</b>는 원본 PDF의 페이지 번호입니다. 표시 순번은 읽기용이며 기존 ID는 유지했습니다.</p>')
    for index, q in enumerate(packet['questions'], 1):
        parts.append('<section id="'+esc(q['id'])+'" class="question"><p class="eyebrow">질문 '+str(index)+' · '+esc(q['id'])+'</p><h2>'+esc(q['question'])+'</h2>')
        claims = q['codex_source_checked']['claims']
        if not claims:
            parts.append('<h3>문서에 금액 미명시 — 확인 필요</h3><p>'+esc(q['codex_source_checked']['answer'])+'</p>'
                         '<p>이 문서에서 금액을 확인할 수 없다는 후보이며, 실제 회사가 지원하지 않는다는 뜻은 아닙니다. 부재를 증명하는 가짜 인용이나 주장을 만들지 않았습니다.</p>'
                         '<p><a href="../run001/absence-review.json">전체 원문·정책 목록 대조 기록</a> · '
                         '<a href="../run001/source/extracted/canonical/hr-v4-handbook.txt">규정집 전문</a> · '
                         '<a href="../run001/source/policy-inventory.json">정책 목록</a></p>')
        else:
            parts.append('<h3>정답 클레임과 근거 원문</h3>')
        for number, c in enumerate(claims, 1):
            s = c['source']
            parts.append('<article class="claim"><h4><span class="number">'+str(number)+'</span> '+esc(c['text'])+'</h4>')
            parts.append('<p class="source-label">근거 원문 · 조항 '+esc(s['article_id'])+' · 페이지 '+', '.join(map(str, s['pages']))+'</p><blockquote>'+esc(s['quote'])+'</blockquote>')
            parts.append(details('주장 ID·원문 위치·해시', '<p>'+esc(c['id'])+'</p><p>Unicode 문자 위치 ['+str(s['start'])+', '+str(s['end'])+'). PDF 좌표가 아닙니다.</p>'+pretty(c)))
            parts.append('</article>')
        parts.append('<p class="review-check">확인할 점: 사실·숫자가 맞는지 / 조건·예외가 보존됐는지 / 질문에 필요한 내용이 충분한지. <strong>사람 미승인</strong></p>')
        parts.append(details('모델 원응답·실패·수정 이력 (run001)', pretty(dict(attempts=q['model_original_attempts'],revision=q['revision']))))
        parts.append(details('이 질문의 지정 원문 전체', ''.join('<h4>조항 '+esc(s['article_id'])+'</h4><pre>'+esc(s['text'])+'</pre>' for s in q['source_spans']) or '<p>지정 근거가 없는 질문입니다. 위 전문·정책 목록을 확인해 주세요.</p>'))
        parts.append('</section>')
    parts.append('<section id="judgements"><p class="eyebrow">별도 검토</p><h2>판정 후보 18개</h2><p>통제된 가상 사례입니다. E = 지지 · N = 정보 부족 · C = 모순. 모든 판정은 사람 미승인입니다.</p>')
    labels = {'E':'지지','N':'정보 부족','C':'모순'}
    for i, j in enumerate(packet['judgements'], 1):
        parts.append('<article><h3>판정 '+str(i)+' · '+esc(j['category'])+'</h3><p class="source-label">근거</p><blockquote>'+esc(j['premise'])+'</blockquote><p><b>주장</b> '+esc(j['claim'])+'</p><p><b>제안 판정</b> '+esc(j['proposed_label']+' · '+labels[j['proposed_label']])+'</p><p>'+esc(j['reason'])+'</p><small>'+esc(j['id'])+' · 사람 미승인</small></article>')
    parts.append('</section>')
    log = ('<p><b>과거 run001 측정치</b>: 모델 호출 30회 = 기본 검사 8회 + 반복 검사 6회 + 실제 질문 초안 16회(8개 질문 × 2회). gt09·gt10은 근거가 없어 호출 0회입니다.</p>'
           '<ul><li>JSON 형식 통과: 전체 호출 중 28/30회.</li><li>정확한 원문 인용 검증 통과: 전체 호출 중 12/30회.</li>'
           '<li>실제 질문 초안: 질문 8개 중 정확 인용 검증 성공 0/8개. 각 질문의 두 시도 모두 통과하지 못했습니다.</li></ul>'
           '<p>호출 횟수와 질문 개수는 서로 다른 분모입니다. 정리된 정답 후보는 Codex의 원문 대조 결과이며 모델의 성공 답변이나 사람이 승인한 정답이 아닙니다. '
           '기본 검사 성공은 일반적인 답변 품질을 보장하지 않습니다. 이 자료는 개발·검토 세트로 독립 평가용 holdout이 아닙니다.</p>'
           '<p><b>이번 run002 개정</b>: 새 모델 호출·다운로드·서버 변경 0회. 이전 실패와 실행 이력을 보존했습니다.</p>'
           '<p><a href="../run001/ledger.json">과거 누적 호출 기록</a> · <a href="revision-mapping.json">변경 전후 ID·문장·근거 매핑</a> · <a href="packet.json">새 패킷 JSON</a> · <a href="packet-manifest.json">파일 해시 목록</a></p>')
    log += details('과거 모델 실행 상세 JSON', pretty(packet['experiment']))
    log += details('중복 주장 개정 내역 JSON', pretty(mapping))
    log += details('패킷·부모 패킷 해시', pretty(dict(packet_sha256=packet['packet_sha256'], parent_packet_sha256=PARENT_SHA)))
    parts.append(details('실험 기록·한계', log, 'experiment'))
    parts.append('<footer>이 문서에는 승인 기능이 없습니다. 검토 의견은 질문 ID와 주장 ID를 기준으로 남겨 주세요.</footer>')
    parts.append('<script type="application/json" id="packet">'+json.dumps(packet,ensure_ascii=False).replace('<','\\u003c')+'</script></main></body></html>\n')
    return ''.join(parts)


CSS = '''
:root{color-scheme:light;--ink:#203334;--muted:#526767;--accent:#16665e;--line:#d7e2df}
*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;background:#f3f6f4;color:var(--ink);font:16px/1.75 system-ui,sans-serif;overflow-wrap:anywhere}
main{max-width:900px;margin:0 auto;padding:48px 24px}h1{font-size:2.25rem;line-height:1.25;letter-spacing:-.04em}h2{font-size:1.4rem;line-height:1.5}h3{font-size:1.1rem}h4{font-size:1.05rem;line-height:1.75;margin:0 0 16px}p{margin:12px 0}a{color:var(--accent);text-underline-offset:3px}
header{padding:0 8px 24px}.intro{font-size:1.15rem}.eyebrow,.source-label{color:var(--accent);font-weight:650}.eyebrow{font-size:.85rem;letter-spacing:.04em}.badge{display:inline-block;background:#e2eee8;border-radius:8px;padding:8px 12px;font-size:.9rem}
nav,section{padding:28px;background:white;border:1px solid var(--line);border-radius:16px;margin:24px 0}nav ol{padding-left:24px}nav li{margin:8px 0}.guide{color:var(--muted);font-size:.9rem;padding:0 8px}.question{scroll-margin-top:20px}article{padding:22px 0;border-bottom:1px solid var(--line)}article:last-child{border:0}.number{color:var(--accent);font-variant-numeric:tabular-nums}.source-label{font-size:.9rem;margin-bottom:8px}blockquote{margin:0;padding:16px 18px;border-left:3px solid #8bb6a6;background:#f2f6f3;white-space:pre-wrap}.review-check{font-size:.9rem;background:#faf6e9;padding:14px;border-radius:8px}details{border:1px solid var(--line);border-radius:8px;margin:12px 0;padding:12px 16px}summary{cursor:pointer;color:var(--muted);font-size:.9rem;min-height:26px}summary:focus-visible,a:focus-visible{outline:3px solid #1e8175;outline-offset:4px}pre{white-space:pre-wrap;overflow-wrap:anywhere;font:13px/1.65 ui-monospace,monospace;background:#f5f7f6;padding:14px;max-width:100%}small,footer{color:var(--muted);font-size:.85rem}footer{padding:20px 4px}#experiment{background:white;padding:22px}#experiment>summary{font-size:1.1rem;font-weight:650}
@media(max-width:600px){main{padding:24px 12px}h1{font-size:1.8rem}section,nav{padding:18px 16px}blockquote{padding:12px}details{padding:10px 12px}.intro{font-size:1rem}}
@media(prefers-reduced-motion:reduce){html{scroll-behavior:auto}}
'''


def verify(out):
    out = out.resolve(); parent = out.parent/'run001'
    packet, mapping = build(parent)
    if read(out/'packet.json') != packet or read(out/'revision-mapping.json') != mapping:
        raise ValueError('review revision differs from approved transformation')
    text = (out/'review.html').read_text()
    embedded = re.search(r'<script type="application/json" id="packet">(.*?)</script>', text, re.S)
    if text != render(packet, mapping) or not embedded or json.loads(embedded[1]) != packet:
        raise ValueError('revision HTML/JSON mismatch')
    expected = dict(version=VERSION, packet_sha256=packet['packet_sha256'], parent_packet_sha256=PARENT_SHA,
                    files={n:file_hash(out/n) for n in ['packet.json','revision-mapping.json','review.html']})
    if read(out/'packet-manifest.json') != expected:
        raise ValueError('review revision manifest mismatch')
    return packet


def create(parent, out):
    parent, out = parent.resolve(), out.resolve()
    if parent.name != 'run001' or out.parent != parent.parent or out == parent:
        raise ValueError('revision must be a new sibling of run001')
    if out.exists():
        packet = verify(out)
    else:
        packet, mapping = build(parent)
        stage = Path(tempfile.mkdtemp(prefix='.review-', dir=out.parent))
        try:
            write(stage/'packet.json', packet, immutable=True)
            write(stage/'revision-mapping.json', mapping, immutable=True)
            (stage/'review.html').write_text(render(packet, mapping))
            write(stage/'packet-manifest.json', dict(version=VERSION, packet_sha256=packet['packet_sha256'],
                  parent_packet_sha256=PARENT_SHA, files={n:file_hash(stage/n) for n in ['packet.json','revision-mapping.json','review.html']}))
            verify(stage)
            if out.exists():
                raise ValueError('revision destination appeared during generation')
            stage.rename(out)
        finally:
            if stage.exists():shutil.rmtree(stage)
    print('Unapproved offline review revision:',packet['packet_sha256'])
    return packet
