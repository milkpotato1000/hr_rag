"""P022 source-reviewed, pinned, offline atomic claims; model schemas stay unchanged."""
import copy
import hashlib
import html
import json
from pathlib import Path
import re
import shutil
import tempfile
from collections import Counter
from core import digest, file_hash, locate, read, validate_review_packet, write
from report import resolve_needle
from review_revision import CANONICAL_SHA, CSS, inventory, verify as verify_parent

VERSION = 'p022-atomic-v1'
PARENT_SHA = 'e6a264387d3dd169168bcf1733156bf91bd4bdf76fc8bb70f5a704e3bc7a2b0e'
AUDIT_SHA = 'e9dd80869464b6e41d3e7f77482a2908702b9eb742a410c78a8c7bff337140ae'
COUNTS = [10,3,9,6,4,7,8,10,0,0]
# Codex rechecked these complete rules against the canonical article bodies.
# Shared context supports independent facts; it is not an additional scored fact.
EVIDENCE = {
 'gt01-c02': '입사 후 3개월이 지난 재직자는 매년 생일 특별휴가 1일을 신청할 수 있다. 수습 중인 직원은 대상에서 제외한다.',
 'gt01-c04': '생일 특별휴가는 생일이 속한 달의 근무일에 사용한다.',
 'gt01-c05': '생일 특별휴가는 사용 3영업일 전까지 휴가 시스템에서 신청하고 팀장의 승인을 받아야 한다.',
 'gt03-c05': '재택근무는 매주 최대 2일이며 전주 금요일까지 팀장 승인을 받는다.',
 'gt04-c03': '재직자에게 생일 축하 포인트 3만 점을 지급한다.',
 'gt05-c02': '직무 관련 자격시험 응시자는 연 1일 교육 휴가를 신청할 수 있다.',
 'gt06-c01': '출장은 출발 5영업일 전에 팀장의 승인을 받는다.',
 'gt07-c01': '다만 시스템에 접속할 수 없거나 제출 후 접수 화면이 표시되지 않아 기록 존재를 확인할 수 없는 경우에는 담당자가 신청자가 알린 시점, 사용 희망일, 장애 상황을 임시 기록으로 남기고 이를 접수 확인용으로 안내한다.',
 'gt08-c01': '여러 날짜의 요청 중 일부만 취소하려는 경우에는 유지하는 날짜와 취소하는 날짜를 나누어 기록하고, 전체 신청을 일괄 삭제하지 않는다.',
 'gt08-c02': '여러 날짜의 요청 중 일부만 취소하려는 경우에는 유지하는 날짜와 취소하는 날짜를 나누어 기록하고, 전체 신청을 일괄 삭제하지 않는다.',
 'gt08-c03': '실제 사용 여부가 아직 확인되지 않았거나 사용 내역 반영이 지연되고 있으면 담당자는 신청 취소 의사와 기존 사용 사실의 확인을 구분해 처리한다.',
 'gt08-c07': '응시 계획을 취소했다는 연락을 받으면 담당자는 취소하려는 교육휴가 요청을 먼저 식별한다. 시험 접수만 취소한 것인지 휴가 신청도 취소하려는 것인지 구분하고, 신청자가 아직 결정하지 못한 문의를 확정된 취소로 기록하지 않는다. 확인된 취소 의사는 원래 신청과 연결하여 남기며, 다른 시험에 관한 요청이나 이미 별도로 관리되는 휴가 기록까지 일괄 삭제하지 않는다.',
}


def load_audit(path):
    if file_hash(path) != AUDIT_SHA:
        raise ValueError('atomicity audit differs from exact adopted plan')
    return read(path)


def source_for(q, old_id, article_id, canonical, pages):
    unit = next(s for s in q['source_spans'] if s['article_id']==article_id)
    if canonical[unit['start']:unit['end']] != unit['text']:
        raise ValueError('article source span mismatch')
    a,b = resolve_needle(unit['text'], EVIDENCE[old_id])
    start,end = unit['start']+a,unit['start']+b
    quote = canonical[start:end]
    return dict(article_id=article_id,start=start,end=end,quote=quote,
                quote_sha256=hashlib.sha256(quote.encode()).hexdigest(),
                pages=[p['page_number'] for p in pages if p['start']<end and p['end']>start],
                canonical_sha256=CANONICAL_SHA)


def build(parent, audit_path):
    old = verify_parent(parent)
    audit = load_audit(audit_path)
    if old['packet_sha256'] != PARENT_SHA or file_hash(parent/'packet.json') != audit['source_file_sha256']:
        raise ValueError('atomic review parent mismatch')
    if audit['source_packet_sha256'] != PARENT_SHA or audit['source_canonical_sha256'] != CANONICAL_SHA:
        raise ValueError('audit source mismatch')
    run001 = parent.parent/'run001'
    canonical = (run001/'source/extracted/canonical/hr-v4-handbook.txt').read_text()
    pages = read(run001/'source/extracted/manifest.json')['documents'][0]['pages']
    packet = copy.deepcopy(old);packet.pop('packet_sha256')
    packet.update(schema_version=2,review_version=VERSION,new_model_requests=0,
                  scope='P022 Codex source-rechecked atomic review candidates; human unapproved, no new model experiment or P013 scoring',
                  parent=dict(path='../run002/packet.json',packet_sha256=PARENT_SHA,
                              execution_history='../run001/ledger.json',files=inventory(parent)),
                  atomicity_audit=dict(path='atomicity-audit.json',file_sha256=AUDIT_SHA),
                  revision_method='Codex source recheck against full canonical articles; split independent facts, retain conditional scope; no new Qwen calls',
                  previous_review_mapping_sha256=old['review_mapping_sha256'])
    mapping = dict(version=VERSION,parent_packet_sha256=PARENT_SHA,audit_file_sha256=AUDIT_SHA,
                   old_claim_count=45,new_claim_count=57,human_approval=None,changes=[])
    proposals = audit['items'];index=0
    for q,prior in zip(packet['questions'],old['questions']):
        result=[]
        for original in prior['codex_source_checked']['claims']:
            item=proposals[index];index+=1
            if (item['question_id'],item['old_claim_id'],item['old_text'],item['source']) != (q['id'],original['id'],original['text'],original['source']):
                raise ValueError('audit order/old claim/source mismatch')
            action=item['action'];children=[];ids=[]
            for number,proposal in enumerate(item['proposed_claims'],1):
                ident=original['id']+'-a'+str(number) if action=='split' else original['id']
                if action=='keep':
                    if proposal['text']!=original['text']:raise ValueError('keep changed text')
                    source=copy.deepcopy(original['source'])
                else:
                    source=source_for(q,original['id'],proposal['source_article_id'],canonical,pages)
                c=dict(id=ident,text=proposal['text'],source=source)
                children.append(c);result.append(c)
                ids.append(dict(proposal_id=proposal['proposal_id'],claim_id=ident))
            mapping['changes'].append(dict(question_id=q['id'],old=copy.deepcopy(original),
                  action=action,reason=item['reason'],new=children,proposal_id_mapping=ids))
        if result:
            answer='\n'.join(c['text'] for c in result)
            for c in result:c['answer_span']=locate(answer,c['text'])
            q['codex_source_checked']=dict(answer=answer,claims=result)
        q['atomic_review']=dict(method='Codex source recheck; not a new model response',mapping='revision-mapping.json')
    if index!=len(proposals) or Counter(i['action'] for i in proposals)!=dict(split=10,restore_scope=2,keep=33):
        raise ValueError('atomicity action count mismatch')
    packet['review_mapping_sha256']=digest(mapping)
    packet['packet_sha256']=digest(packet)
    validate(packet,mapping,old,run001)
    return packet,mapping


def validate(packet,mapping,old,run001):
    validate_review_packet(packet)
    if packet['schema_version']!=2 or packet['review_version']!=VERSION or packet['new_model_requests']!=0:
        raise ValueError('atomic review version/offline boundary')
    if packet['judgements']!=old['judgements']:
        raise ValueError('judgements changed')
    canonical_path=run001/'source/extracted/canonical/hr-v4-handbook.txt'
    if file_hash(canonical_path)!=CANONICAL_SHA:raise ValueError('canonical changed')
    canonical=canonical_path.read_text()
    pages=read(run001/'source/extracted/manifest.json')['documents'][0]['pages']
    rows=mapping['changes'];position=0;seen=set()
    for q,prior,count in zip(packet['questions'],old['questions'],COUNTS):
        checked=q['codex_source_checked'];claims=checked['claims']
        if len(claims)!=count:raise ValueError('question atomic claim count mismatch')
        for name in ['id','question','answerability','source_spans','model_original_attempts','revision','human_approval','status','reviewer']:
            if q[name]!=prior[name]:raise ValueError('historical question provenance changed')
        if count==0:
            if checked!=prior['codex_source_checked']:raise ValueError('absence candidate changed')
        elif checked['answer']!='\n'.join(c['text'] for c in claims):raise ValueError('answer mismatch')
        flat=[]
        for original in prior['codex_source_checked']['claims']:
            row=rows[position];position+=1
            if row['old']!=original or row['question_id']!=q['id']:raise ValueError('old mapping mismatch')
            if row['action']=='keep' and (len(row['new'])!=1 or any(row['new'][0][k]!=original[k] for k in ['id','text','source'])):
                raise ValueError('keep source/text/ID changed')
            for n,c in enumerate(row['new'],1):
                expected=original['id']+'-a'+str(n) if row['action']=='split' else original['id']
                if c['id']!=expected or c['id'] in seen:raise ValueError('new claim ID collision/rule mismatch')
                seen.add(c['id'])
                s=c['source'];a,b=c['answer_span']
                unit=next(u for u in q['source_spans'] if u['article_id']==s['article_id'])
                actual_pages=[p['page_number'] for p in pages if p['start']<s['end'] and p['end']>s['start']]
                if not unit['start']<=s['start']<s['end']<=unit['end'] or s['quote']!=canonical[s['start']:s['end']] or s['quote_sha256']!=hashlib.sha256(s['quote'].encode()).hexdigest() or s['pages']!=actual_pages or s['canonical_sha256']!=CANONICAL_SHA or checked['answer'][a:b]!=c['text']:
                    raise ValueError('atomic claim source/answer span/hash/page mismatch')
            flat.extend(row['new'])
        if flat!=claims:raise ValueError('mapping and question claims differ')
    if position!=45 or len(rows)!=45 or len(seen)!=57:raise ValueError('atomic mapping coverage')


def render(packet,mapping):
    esc=html.escape
    def pretty(x):return '<pre>'+esc(json.dumps(x,ensure_ascii=False,indent=2))+'</pre>'
    def details(label,body,ident=''):
        return '<details'+(' id="'+esc(ident)+'"' if ident else '')+'><summary>'+esc(label)+'</summary>'+body+'</details>'
    origins={c['id']:row for row in mapping['changes'] for c in row['new']}
    parts=['<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>원자 주장 검토 · 질문과 원문 근거</title>']
    parts+=['<style>'+CSS+'</style></head><body><main><header><p class="eyebrow">HR RAG · 검토본 003</p><h1>질문과 원자 주장을 함께 읽기</h1>',
            '<p class="intro">원문을 기준으로 정리한 <strong>미승인 정답 후보</strong>입니다. 각 사실과 조건이 근거에 맞는지 확인해 주세요.</p>',
            '<p class="badge">질문 10개 · 정답 주장 57개 · 판정 후보 18개 · 사람 미승인</p>',
            '<p>run002의 45개 항목을 전수 대조해 10개를 분리하고 2개의 조건을 복원했습니다. 33개는 유지했습니다. 이번 개정의 모델 호출은 <strong>0회</strong>입니다.</p>',
            '<p><a href="../run002/review.html">이전 검토본 002</a> · <a href="../run001/review.html">최초 검토본 001</a> · <a href="revision-mapping.json">구·신 ID와 변경 내역</a></p></header>',
            '<nav aria-label="질문 바로가기"><h2>질문 바로가기</h2><ol>']
    for q in packet['questions']:parts.append('<li><a href="#'+esc(q['id'])+'">'+esc(q['question'])+'</a></li>')
    parts.append('</ol><a href="#judgements">판정 후보 18개</a> · <a href="#experiment">실험 기록·한계</a></nav>')
    parts.append('<p class="guide">gt는 질문·정답 항목, c는 주장 ID이며 청크가 아닙니다. a1·a2·a3은 같은 이전 항목에서 분리된 주장입니다. 조항은 원문 규정의 ID, 페이지는 PDF 페이지 번호입니다. 같은 인용이 여러 독립 사실을 뒷받침할 수 있습니다.</p>')
    for i,q in enumerate(packet['questions'],1):
        parts.append('<section id="'+esc(q['id'])+'" class="question"><p class="eyebrow">질문 '+str(i)+' · '+esc(q['id'])+'</p><h2>'+esc(q['question'])+'</h2>')
        claims=q['codex_source_checked']['claims']
        if claims:parts.append('<h3>정답 원자 클레임과 근거 원문</h3>')
        else:
            parts.append('<h3>문서에 금액 미명시 — 확인 필요</h3><p>'+esc(q['codex_source_checked']['answer'])+'</p><p>실제 회사의 지원 여부를 단정하는 답변이 아닙니다.</p><p><a href="../run001/absence-review.json">전체 원문·정책 목록 대조 기록</a> · <a href="../run001/source/extracted/canonical/hr-v4-handbook.txt">규정집 전문</a> · <a href="../run001/source/policy-inventory.json">정책 목록</a></p>')
        for n,c in enumerate(claims,1):
            s=c['source'];origin=origins[c['id']]
            parts.append('<article class="claim" id="'+esc(c['id'])+'"><h4><span class="number">'+str(n)+'</span> '+esc(c['text'])+'</h4><p class="source-label">근거 원문 · 조항 '+esc(s['article_id'])+' · 페이지 '+', '.join(map(str,s['pages']))+'</p><blockquote>'+esc(s['quote'])+'</blockquote>')
            parts.append(details('주장 ID·원문 위치·해시·개정 내역','<p>현재 '+esc(c['id'])+' ← 이전 '+esc(origin['old']['id'])+'</p><p>'+esc(origin['reason'])+'</p><p>이전 문장: '+esc(origin['old']['text'])+'</p><p>Unicode ['+str(s['start'])+', '+str(s['end'])+'). PDF 좌표가 아닙니다.</p><p><a href="../run002/review.html#'+esc(q['id'])+'">이전 질문 보기</a> · <a href="revision-mapping.json">전체 매핑</a></p>'+pretty(c)))
            parts.append('</article>')
        parts.append('<p class="review-check">확인할 점: 사실·숫자 일치 / 대상·조건·예외 보존 / 질문에 필요한 내용의 충분성. <strong>사람 미승인</strong></p>')
        parts.append(details('과거 모델 원응답·실패·Codex 수정 이력 (run001)',pretty(dict(attempts=q['model_original_attempts'],revision=q['revision']))))
        parts.append(details('이 질문의 지정 원문 전체',''.join('<h4>조항 '+esc(s['article_id'])+'</h4><pre>'+esc(s['text'])+'</pre>' for s in q['source_spans']) or '<p>지정 근거가 없습니다. 전문·정책 목록에서 미명시 여부를 확인해 주세요.</p>'))
        parts.append('</section>')
    parts.append('<section id="judgements"><p class="eyebrow">별도 검토</p><h2>판정 후보 18개</h2><p>E = 지지 · N = 정보 부족 · C = 모순. 통제된 가상 사례이며 모두 사람 미승인입니다.</p>')
    labels={'E':'지지','N':'정보 부족','C':'모순'}
    for i,j in enumerate(packet['judgements'],1):
        parts.append('<article><h3>판정 '+str(i)+' · '+esc(j['category'])+'</h3><p class="source-label">근거</p><blockquote>'+esc(j['premise'])+'</blockquote><p><b>주장</b> '+esc(j['claim'])+'</p><p><b>제안 판정</b> '+esc(j['proposed_label']+' · '+labels[j['proposed_label']])+'</p><p>'+esc(j['reason'])+'</p><small>'+esc(j['id'])+' · 사람 미승인</small></article>')
    parts.append('</section>')
    experiment=('<p><b>과거 run001 측정치</b>: 호출 30회 = 기본 검사 8회 + 반복 검사 6회 + 실제 질문 초안 16회(8개 질문 × 2회). gt09·gt10은 호출 0회입니다.</p>'
                '<ul><li>JSON 형식 통과: 전체 호출 중 28/30회.</li><li>정확한 원문 인용 검증 통과: 전체 호출 중 12/30회.</li><li>실제 질문 초안: 질문 8개 중 정확 인용 성공 0/8개. 각 질문의 두 시도 모두 통과하지 못했습니다.</li></ul>'
                '<p>호출 횟수와 질문 개수는 서로 다른 분모입니다. 이번 run003은 Codex의 원문 재검수이며 새 모델 호출·다운로드·서버 변경은 0회입니다. 과거 Qwen 초안/실패와 Codex 수정 이력을 보존했습니다.</p>'
                '<p>이 자료는 검토·개발 세트입니다. 45개에서 57개로 분모가 바뀌었으므로 같은 평가 버전의 품질 향상으로 비교하지 않습니다. 조건을 각 문장에 반복해도 별도 가산 사실은 아닙니다. 사람 정답 승인은 별도입니다.</p>'
                '<p><a href="packet.json">새 패킷 JSON</a> · <a href="packet-manifest.json">파일 해시 목록</a> · <a href="atomicity-audit.json">동결 원자성 검수</a> · <a href="../run001/ledger.json">과거 호출 기록</a></p>')
    experiment+=details('과거 모델 실행 상세 JSON',pretty(packet['experiment']))
    experiment+=details('원자 주장 개정 내역 JSON',pretty(mapping))
    experiment+=details('패킷·부모·원자성 검수 해시',pretty(dict(packet_sha256=packet['packet_sha256'],parent_packet_sha256=PARENT_SHA,audit_file_sha256=AUDIT_SHA)))
    parts.append(details('실험 기록·한계',experiment,'experiment'))
    parts.append('<footer>새 검토본 자체의 화면 동작은 별도 확인이 필요합니다. 이 문서에는 정답 승인 기능이 없습니다.</footer>')
    parts.append('<script type="application/json" id="packet">'+json.dumps(packet,ensure_ascii=False).replace('<','\\u003c')+'</script></main></body></html>\n')
    return ''.join(parts)


def manifest(out,packet):
    return dict(version=VERSION,packet_sha256=packet['packet_sha256'],parent_packet_sha256=PARENT_SHA,
                atomicity_audit_file_sha256=AUDIT_SHA,
                files={n:file_hash(out/n) for n in ['packet.json','revision-mapping.json','atomicity-audit.json','review.html']})


def verify(out):
    out=out.resolve();parent=out.parent/'run002'
    packet,mapping=build(parent,out/'atomicity-audit.json')
    if read(out/'packet.json')!=packet or read(out/'revision-mapping.json')!=mapping:
        raise ValueError('atomic packet/mapping differs from exact reviewed transformation')
    text=(out/'review.html').read_text()
    embedded=re.search(r'<script type="application/json" id="packet">(.*?)</script>',text,re.S)
    if text!=render(packet,mapping) or not embedded or json.loads(embedded[1])!=packet:
        raise ValueError('atomic HTML/JSON mismatch')
    if read(out/'packet-manifest.json')!=manifest(out,packet):raise ValueError('atomic manifest mismatch')
    return packet


def create(parent,audit_path,out):
    parent,out=parent.resolve(),out.resolve();audit_path=audit_path.resolve()
    if parent.name!='run002' or out.parent!=parent.parent or out.name in ('run001','run002'):
        raise ValueError('atomic review must be a new sibling of run002')
    if out.exists():
        # Even a replay command must not accept a different requested audit/parent.
        load_audit(audit_path)
        packet=verify(out)
    else:
        packet,mapping=build(parent,audit_path)
        stage=Path(tempfile.mkdtemp(prefix='.atomic-',dir=out.parent))
        try:
            (stage/'atomicity-audit.json').write_bytes(audit_path.read_bytes())
            write(stage/'packet.json',packet,immutable=True);write(stage/'revision-mapping.json',mapping,immutable=True)
            (stage/'review.html').write_text(render(packet,mapping))
            write(stage/'packet-manifest.json',manifest(stage,packet),immutable=True)
            verify(stage)
            if out.exists():raise ValueError('atomic review destination appeared during generation')
            stage.rename(out)
        finally:
            if stage.exists():shutil.rmtree(stage)
    print('Unapproved atomic review:',packet['packet_sha256'])
    return packet
