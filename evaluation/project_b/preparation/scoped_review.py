"""P023 pinned scope classification and policy display; no scoring/model execution."""
import copy
import html
import json
from pathlib import Path
import re
import shutil
import tempfile
from core import digest, file_hash, read, validate_review_packet, write
from atomic_review import verify as verify_parent
from review_revision import CANONICAL_SHA, CSS, inventory

VERSION='p023-core-supplement-v1'
PARENT_SHA='946d7181ecf8b45e633a347adbcc241f38dfd5976d80342e34e1da3bf2d87199'
PARENT_FILE_SHA='fec84decf14335151162d9b168db366854a5b4a45d06092230e78f2e124e802b'
AUDIT_SHA='437bcf0eafb6de063db66e992916b7b8c5cfd00ee150490f89e2e84a0b14d0f0'
POLICY_SHA='ea9c1d2da4cc02c5743a56e919e59ed86c6ac474172974e2e5f04640926a7ab8'
COUNTS=[(6,4),(3,0),(8,1),(2,4),(4,0),(3,4),(4,4),(8,2),(0,0),(0,0)]
ROLE_KEYS=['claim_id','role','intent_ids','supplement_kind','reason','clarifies_required_ids']
PRIOR_APPROVAL_IDS=['gt01-c02-a1','gt01-c02-a2','gt01-c02-a3','gt01-c04-a1','gt01-c04-a2']


def load_contract(audit_path,policy_path):
    if file_hash(audit_path)!=AUDIT_SHA:raise ValueError('scope audit differs from adopted plan')
    if file_hash(policy_path)!=POLICY_SHA:raise ValueError('scoring policy differs from adopted plan')
    return read(audit_path),policy_path.read_text()


def build(parent,audit_path,policy_path):
    audit,policy=load_contract(audit_path,policy_path)
    old=verify_parent(parent)
    if old['packet_sha256']!=PARENT_SHA or file_hash(parent/'packet.json')!=PARENT_FILE_SHA:
        raise ValueError('scoped review parent mismatch')
    if (audit['source_packet_sha256'],audit['source_file_sha256'],audit['canonical_sha256'])!=(PARENT_SHA,PARENT_FILE_SHA,CANONICAL_SHA):
        raise ValueError('scope audit provenance mismatch')
    packet=copy.deepcopy(old);packet.pop('packet_sha256')
    packet.update(schema_version=3,review_version=VERSION,
          scope='P023 delegated scope review: 38 required and 19 supplementary claims; global human approval pending; no evaluator execution',
          parent=dict(path='../run003/packet.json',packet_sha256=PARENT_SHA,packet_file_sha256=PARENT_FILE_SHA,
                      execution_history='../run001/ledger.json',files=inventory(parent)),
          scope_review=dict(method='Codex delegated scope review',author=audit['author'],new_model_requests=0,
                            plan_commit='5d3e47774a162e235b7886298a947dccb2be662d',policy_file_sha256=POLICY_SHA),
          scope_audit=dict(path='scope-audit.json',file_sha256=AUDIT_SHA),
          scoring_policy=dict(version=VERSION,path='scoring-policy.md',file_sha256=POLICY_SHA),
          # The inherited atomic metadata and question revision paths are historical.
          inherited_revision_artifacts=dict(question_revision_base='../run003/',
               review_mapping=dict(path='../run003/revision-mapping.json',sha256=old['review_mapping_sha256']),
               atomicity_audit=dict(path='../run003/atomicity-audit.json',file_sha256=old['atomicity_audit']['file_sha256'])))
    mapping=dict(version=VERSION,parent_packet_sha256=PARENT_SHA,parent_file_sha256=PARENT_FILE_SHA,
                 audit_file_sha256=AUDIT_SHA,policy_file_sha256=POLICY_SHA,human_approval=None,changes=[])
    if len(audit['questions'])!=10:raise ValueError('scope question count')
    for q,prior,review in zip(packet['questions'],old['questions'],audit['questions']):
        if (review['question_id'],review['question'],review['answerability'])!=(q['id'],q['question'],q['answerability']):
            raise ValueError('scope question identity mismatch')
        claims=prior['codex_source_checked']['claims']
        if len(claims)!=len(review['claims']):raise ValueError('scope claim coverage mismatch')
        required=[];supplementary=[];roles=[]
        for c,r in zip(claims,review['claims']):
            if (c['id'],c['text'],c['source'])!=(r['claim_id'],r['text'],r['source']):
                raise ValueError('scope audit claim identity/source mismatch')
            role={k:copy.deepcopy(r[k]) for k in ROLE_KEYS}
            roles.append(role)
            if r['role']=='required':required.append(c['id'])
            elif r['role']=='supplementary':supplementary.append(c['id'])
            else:raise ValueError('unknown claim role')
            mapping['changes'].append(dict(question_id=q['id'],claim=copy.deepcopy(c),classification=copy.deepcopy(role)))
        q['answer_rubric']=dict(policy_version=VERSION,intents=copy.deepcopy(review['intents']),
            required_claim_ids=required,supplementary_claim_ids=supplementary,
            required_answer='\n'.join(c['text'] for c in claims if c['id'] in required),
            supplementary_answer='\n'.join(c['text'] for c in claims if c['id'] in supplementary),
            counts=dict(required=len(required),supplementary=len(supplementary),total=len(claims)),claim_roles=roles)
    first=old['questions'][0]['codex_source_checked']['claims']
    packet['prior_human_claim_reviews']=[dict(parent_packet_sha256=PARENT_SHA,parent_review_version=old['review_version'],
          claim=copy.deepcopy(c),status='explicit_human_approval_on_parent_only',
          evidence='User explicitly approved run003 gt01 first five claims, documented in adopted P023 scope review; not blanket new packet approval')
          for c in first if c['id'] in PRIOR_APPROVAL_IDS]
    packet['scope_counts']=dict(required=38,supplementary=19,total=57)
    packet['scope_mapping_sha256']=digest(mapping)
    packet['packet_sha256']=digest(packet)
    validate(packet,mapping,old,audit)
    return packet,mapping,policy


def validate(packet,mapping,old,audit):
    validate_review_packet(packet)
    if packet['schema_version']!=3 or packet['review_version']!=VERSION or packet['new_model_requests']!=0:
        raise ValueError('scoped review schema/version/offline mismatch')
    for key in ['judgements','experiment','codex_revision_history','model_lock_sha256','prompt_revision_sha256','p007_handoff','frozen_input_sha256']:
        if packet[key]!=old[key]:raise ValueError('historical provenance changed')
    count=0;position=0
    for q,prior,review,expected in zip(packet['questions'],old['questions'],audit['questions'],COUNTS):
        if {k:v for k,v in q.items() if k!='answer_rubric'}!=prior:raise ValueError('original question/claims/answer changed')
        rubric=q['answer_rubric'];claims=q['codex_source_checked']['claims']
        required=rubric['required_claim_ids'];supplementary=rubric['supplementary_claim_ids']
        all_ids=[c['id'] for c in claims]
        if len(set(required+supplementary))!=len(all_ids) or set(required+supplementary)!=set(all_ids):
            raise ValueError('scope must partition each claim exactly once')
        if (len(required),len(supplementary))!=expected or rubric['counts']!=dict(required=expected[0],supplementary=expected[1],total=len(all_ids)):
            raise ValueError('required/supplementary count mismatch')
        for ids,answer in [(required,rubric['required_answer']),(supplementary,rubric['supplementary_answer'])]:
            if ids!=[c['id'] for c in claims if c['id'] in ids] or answer!='\n'.join(c['text'] for c in claims if c['id'] in ids):
                raise ValueError('derived answer/order mismatch')
        if rubric['intents']!=review['intents'] or rubric['policy_version']!=VERSION:
            raise ValueError('scope intent/policy mismatch')
        intents={i['id']:i for i in rubric['intents']}
        if len(intents)!=len(rubric['intents']):raise ValueError('duplicate intent')
        linked=set()
        for intent in intents.values():
            ids=intent['required_claim_ids']
            if not ids or len(ids)!=len(set(ids)) or not set(ids)<=set(required):raise ValueError('intent claims must be required')
            linked.update(ids)
        if linked!=set(required):raise ValueError('required claim has no intent')
        if len(rubric['claim_roles'])!=len(claims):raise ValueError('classification length mismatch')
        for c,role,r in zip(claims,rubric['claim_roles'],review['claims']):
            if role!={k:r[k] for k in ROLE_KEYS}:raise ValueError('classification differs from audit')
            expected_role='required' if c['id'] in required else 'supplementary'
            if role['claim_id']!=c['id'] or role['role']!=expected_role:raise ValueError('classification role mismatch')
            if role['role']=='required':
                if not role['intent_ids'] or any(c['id'] not in intents[i]['required_claim_ids'] for i in role['intent_ids']):raise ValueError('required intent mismatch')
            elif role['intent_ids']:raise ValueError('supplement participates in required coverage')
            if not set(role['clarifies_required_ids'])<=set(required):raise ValueError('clarification target must be required')
            if mapping['changes'][position]!=dict(question_id=q['id'],claim=c,classification=role):raise ValueError('scope mapping mismatch')
            position+=1
        count+=len(claims)
    if count!=57 or len(mapping['changes'])!=57:raise ValueError('scope mapping count')
    history=packet['prior_human_claim_reviews']
    if [r['claim']['id'] for r in history]!=PRIOR_APPROVAL_IDS:raise ValueError('historical approval boundary')
    originals={c['id']:c for c in old['questions'][0]['codex_source_checked']['claims']}
    if any(r['parent_packet_sha256']!=PARENT_SHA or r['claim']!=originals[r['claim']['id']] for r in history):
        raise ValueError('historical approval provenance')


def expected_examples(policy):
    """Read the ten fixed table rows for display; do not calculate model scores."""
    rows=[]
    for line in policy.splitlines():
        if not line.startswith('| '):continue
        cells=[v.strip() for v in line.strip().strip('|').split('|')]
        if len(cells)==5 and cells[0] not in ('ID','---'):rows.append(cells)
    expected=['core_all','core_plus_optional','missing_probation','wrong_deadline','wrong_optional','unknown_extra','optional_only','no_claims','duplicate_core','same_deadline_clarification']
    if [r[0] for r in rows]!=expected:raise ValueError('fixed policy example rows mismatch')
    return rows


def render(packet,mapping,policy):
    esc=html.escape
    def pretty(value):return '<pre>'+esc(json.dumps(value,ensure_ascii=False,indent=2))+'</pre>'
    def details(title,body,ident=''):
        return '<details'+(' id="'+esc(ident)+'"' if ident else '')+'><summary>'+esc(title)+'</summary>'+body+'</details>'
    style=CSS+'''\n.rubric-group{margin:22px 0;padding:18px;border:1px solid var(--line);border-radius:12px}.rubric-group.required{border-left:4px solid #237267}.rubric-group.supplementary{border-left:4px solid #96723e;background:#fffdf8}.role-tag{display:inline-block;font-size:.8rem;border:1px solid currentColor;border-radius:5px;padding:0 6px;margin-right:5px}.derived-answer{white-space:pre-wrap;background:#edf5f0;padding:16px;border-radius:8px}.supplementary .derived-answer{background:#faf3e6}.reason{font-size:.9rem;color:var(--muted)}.policy-note{padding:16px;background:#faf3e6;border-radius:8px}.example{font-size:.95rem}.example h4{margin-bottom:8px}.intent-list{padding-left:22px}@media(max-width:600px){.rubric-group{padding:12px}.derived-answer{padding:12px}}'''
    parts=['<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>필수 답변과 보충 안내 · 검토본 004</title><style>'+style+'</style></head><body><main>',
      '<header><p class="eyebrow">HR RAG · 검토본 004</p><h1>필수 답변과 보충 안내</h1>',
      '<p class="intro">질문에 필요한 사실과 유용한 추가 정보를 나눴습니다. 원문 근거와 분류 사유를 함께 확인해 주세요.</p>',
      '<p class="badge">질문 10개 · 필수 38개 / 보충 19개 · 전체 57개 · 미명시 후보 2개 · 모델 호출 0회</p>',
      '<p><b>Codex 위임 분류 검토 완료 · 새 패킷 전체 사람 승인 대기</b></p>',
      '<p class="policy-note">정확한 보충 정보는 빠져도 핵심 점수를 깎지 않고 가산하지도 않습니다. <strong>잘못된 보충 정보는 추가 사실 오류</strong>로 표시합니다. 핵심 점수가 만점이어도 답변 전체가 정답이라는 뜻은 아닙니다.</p>',
      '<p><a href="../run003/review.html">이전 검토본 003</a> · <a href="scope-mapping.json">분류 매핑</a> · <a href="scoring-policy.md">채점 정책 원문</a> · <a href="#policy">정책과 고정 예시</a></p></header>',
      '<nav aria-label="질문 바로가기"><h2>질문 바로가기</h2><ol>']
    for q in packet['questions']:
        c=q['answer_rubric']['counts'];parts.append('<li><a href="#'+esc(q['id'])+'">'+esc(q['question'])+'</a> <small>필수 '+str(c['required'])+' / 보충 '+str(c['supplementary'])+'</small></li>')
    parts.append('</ol><a href="#prior-reviews">이전 항목 승인 이력</a> · <a href="#judgements">판정 후보</a> · <a href="#experiment">실험 기록·한계</a></nav>')
    parts.append('<p class="guide">gt는 질문 항목, c는 주장 ID입니다. 조항과 페이지는 원본 규정집의 위치입니다. 의도 수와 사실 수는 다릅니다. 원래 57개 문장은 보존하고 필수/보충 답변만 별도로 파생했습니다.</p>')
    for i,q in enumerate(packet['questions'],1):
        rubric=q['answer_rubric'];counts=rubric['counts'];claims=q['codex_source_checked']['claims'];by_id={c['id']:c for c in claims};roles={r['claim_id']:r for r in rubric['claim_roles']}
        parts.append('<section class="question" id="'+esc(q['id'])+'"><p class="eyebrow">질문 '+str(i)+' · '+esc(q['id'])+'</p><h2>'+esc(q['question'])+'</h2><p class="badge">필수 '+str(counts['required'])+'개 / 보충 '+str(counts['supplementary'])+'개</p>')
        if not claims:
            parts.append('<h3>문서에 금액 미명시 — 보류 적절성 확인 필요</h3><p>'+esc(q['codex_source_checked']['answer'])+'</p><p>필수 사실이 0개라고 100% 정답으로 처리하지 않습니다. 실제 회사의 미지원이나 0원으로 단정하지 말고, 숫자 생성 여부와 보류의 적절성을 별도로 검토합니다.</p><p><a href="../run001/absence-review.json">전체 원문·정책 목록 대조 기록</a> · <a href="../run001/source/extracted/canonical/hr-v4-handbook.txt">규정집 전문</a></p>')
        else:
            parts.append('<h3>질문 의도</h3><ul class="intent-list">'+''.join('<li>'+esc(it['text'])+' <small>(필수 '+str(len(it['required_claim_ids']))+'개)</small></li>' for it in rubric['intents'])+'</ul>')
            for role,label in [('required','필수'),('supplementary','보충')]:
                ids=rubric['required_claim_ids'] if role=='required' else rubric['supplementary_claim_ids']
                answer=rubric['required_answer'] if role=='required' else rubric['supplementary_answer']
                parts.append('<div class="rubric-group '+role+'" id="'+esc(q['id']+'-'+role)+'"><h3>'+label+(' 답변' if role=='required' else ' 안내 — 없어도 감점 없음')+'</h3>')
                if role=='supplementary':parts.append('<p>보충도 사실 검증 대상입니다. 틀리거나 확인되지 않은 추가 정보는 별도 오류·검토 경고로 남깁니다.</p>')
                parts.append('<div class="derived-answer">'+esc(answer)+'</div>' if answer else '<p>이 질문에 분류된 보충 정보가 없습니다.</p>')
                for n,ident in enumerate(ids,1):
                    c=by_id[ident];r=roles[ident];s=c['source']
                    parts.append('<article class="claim" id="'+esc(ident)+'"><h4><span class="role-tag">'+label+'</span>'+str(n)+'. '+esc(c['text'])+'</h4><p class="reason">분류 사유: '+esc(r['reason'])+'</p>')
                    if r['clarifies_required_ids']:parts.append('<p class="reason">필수 기한의 보충 설명: '+esc(', '.join(r['clarifies_required_ids']))+' · 핵심 중복 가산 없음</p>')
                    parts.append('<p class="source-label">근거 원문 · 조항 '+esc(s['article_id'])+' · 페이지 '+', '.join(map(str,s['pages']))+'</p><blockquote>'+esc(s['quote'])+'</blockquote>')
                    parts.append(details('주장 ID·원문 위치·분류 상세','<p>'+esc(ident)+' · Unicode ['+str(s['start'])+', '+str(s['end'])+')</p>'+pretty(dict(claim=c,classification=r))))
                    parts.append('</article>')
                parts.append('</div>')
        parts.append('<p class="review-check">원문 사실 일치와 질문에서의 필수성은 별도 검토 항목입니다. 새 질문·패킷의 전체 사람 승인은 아직 없습니다.</p>')
        parts.append(details('구버전 전체 답변·모델 원응답·수정 이력',pretty(dict(original_full_answer=q['codex_source_checked']['answer'],attempts=q['model_original_attempts'],revision=q['revision']))))
        parts.append(details('이 질문의 지정 원문 전체',''.join('<h4>조항 '+esc(s['article_id'])+'</h4><pre>'+esc(s['text'])+'</pre>' for s in q['source_spans']) or '<p>지정 근거가 없는 미명시 후보입니다.</p>'))
        parts.append('</section>')
    parts.append('<section id="policy"><h2>채점 정책과 고정 기대 예시</h2><p>정책 버전 '+VERSION+' · 아래는 설명용 기대값이며 실제 모델 결과가 아닙니다. 실제 평가기는 P013의 별도 작업입니다.</p><h3>핵심 P/R/F1</h3><p>R은 고유 필수 정답 수, G는 핵심 범위의 고유 생성 수, M은 동등 매칭 수입니다. TP=M, FP=G−M, FN=R−M. Precision=M/G, Recall=M/R, F1=2M/(G+R)입니다.</p><p>정확한 보충은 핵심 분모·가산에서 제외합니다. 틀린 필수 답변은 핵심 FP/FN에도 반영하고, 틀린 보충은 추가 사실 오류로 표시합니다. 불확실한 범위·판정은 review_required로 남깁니다.</p><h3>전체 생성의 Faithfulness</h3><p>필수·보충·추가 생성 사실 전체가 분모 T입니다. 실제 전달 문맥의 지지 E/T, 정보 부족 U/T, 모순 C/T를 따로 봅니다. 원문에 맞지만 전달 문맥에 없는 보충은 정보 부족일 수 있습니다. 핵심 만점이어도 추가 오류가 있으면 답변 전체 정답으로 요약하지 않습니다.</p><p>생일휴가 gt01은 의도 4개와 필수 사실 6개입니다. 필수6개+참인 신청 경로는 핵심1/1/1, 수습 제외만 누락하면 P=1·R=5/6·F1=10/11입니다. 필수6개에 “팀장 승인 불필요”를 추가하면 핵심1/1/1이어도 additional_factual_error입니다.</p><p>필수 사실이 필요한데 생성이0개이면 P=null·R=0·F1=0입니다. 미명시 질문과 no_claims는 별도 상태로 보며, 미확정·0분모·macro/micro의 전체 규칙은 정책 원문에 있습니다.</p>')
    examples=''
    for ident,answer,grm,score,note in expected_examples(policy):
        examples+='<article class="example"><h4>'+esc(ident)+'</h4><p>생성 내용: '+esc(answer)+'</p><p>G/R/M: '+esc(grm)+' · 핵심 P/R/F1: '+esc(score)+'</p><p>추가 처리: '+esc(note)+'</p></article>'
    parts.append(details('고정 기대 예시 10개 — 실제 모델 결과 아님',examples))
    parts.append(details('채점 정책 원문 전체','<pre>'+esc(policy)+'</pre>'))
    parts.append('</section>')
    history='<p>사용자가 직접 승인한 것은 이전 run003의 아래 다섯 항목입니다. 나머지 항목과 새 패킷 전체의 사람 승인으로 확대하지 않습니다. 현재 분류는 위임된 Codex 검토입니다.</p>'
    for r in packet['prior_human_claim_reviews']:
        c=r['claim'];history+='<article><h4>'+esc(c['id'])+' · 이전 항목 명시 승인</h4><p>'+esc(c['text'])+'</p><blockquote>'+esc(c['source']['quote'])+'</blockquote>'+pretty(r)+'</article>'
    parts.append(details('이전 run003 항목별 사람 승인 이력 5개',history,'prior-reviews'))
    parts.append('<section id="judgements"><h2>판정 후보 18개</h2><p>E=지지 · N=정보 부족 · C=모순. 원래 ID·근거·라벨을 유지한 통제 가상 후보이며 사람 미승인입니다.</p>')
    for j in packet['judgements']:
        parts.append('<article><h3>'+esc(j['id']+' · '+j['category'])+'</h3><p>근거</p><blockquote>'+esc(j['premise'])+'</blockquote><p>주장: '+esc(j['claim'])+'</p><p>제안 판정: '+esc(j['proposed_label'])+' · '+esc(j['reason'])+'</p></article>')
    parts.append('</section>')
    log='<p>이번 run004는 분류·정책 검토본이며 모델 호출·다운로드·서버 변경0회입니다. 과거 run001 호출30회(기본8+반복6+실제질문16), gt09/10 호출0회, 형식28/30·정확인용12/30·실제질문0/8 결과는 역사로 유지합니다.</p><p><a href="packet.json">새 패킷</a> · <a href="packet-manifest.json">파일 해시</a> · <a href="scope-audit.json">동결 분류</a> · <a href="../run001/ledger.json">과거 호출 기록</a></p>'
    log+=details('과거 실험 상세',pretty(packet['experiment']))
    log+=details('분류 매핑 JSON',pretty(mapping))
    log+=details('패킷·정책 해시',pretty(dict(packet_sha256=packet['packet_sha256'],parent_packet_sha256=PARENT_SHA,audit_sha256=AUDIT_SHA,policy_sha256=POLICY_SHA)))
    parts.append(details('실험 기록·한계',log,'experiment'))
    parts.append('<footer>직접 항목 승인·판단 위임·화면 동작 확인은 서로 다른 기록입니다. 새 패킷 전체 정답 승인은 별도로 필요합니다.</footer><script type="application/json" id="packet">'+json.dumps(packet,ensure_ascii=False).replace('<','\\u003c')+'</script></main></body></html>\n')
    return ''.join(parts)


def manifest(out,packet):
    return dict(version=VERSION,parent_packet_sha256=PARENT_SHA,parent_file_sha256=PARENT_FILE_SHA,
                packet_sha256=packet['packet_sha256'],scope_audit_file_sha256=AUDIT_SHA,scoring_policy_file_sha256=POLICY_SHA,
                files={n:file_hash(out/n) for n in ['packet.json','scope-audit.json','scoring-policy.md','scope-mapping.json','review.html']})


def verify(out):
    out=out.resolve();packet,mapping,policy=build(out.parent/'run003',out/'scope-audit.json',out/'scoring-policy.md')
    if read(out/'packet.json')!=packet or read(out/'scope-mapping.json')!=mapping:raise ValueError('scoped packet/mapping mismatch')
    text=(out/'review.html').read_text();embedded=re.search(r'<script type="application/json" id="packet">(.*?)</script>',text,re.S)
    if text!=render(packet,mapping,policy) or not embedded or json.loads(embedded[1])!=packet:raise ValueError('scoped HTML/JSON mismatch')
    if read(out/'packet-manifest.json')!=manifest(out,packet):raise ValueError('scoped manifest mismatch')
    return packet


def create(parent,audit_path,policy_path,out):
    parent,out=parent.resolve(),out.resolve();audit_path,policy_path=audit_path.resolve(),policy_path.resolve()
    if parent.name!='run003' or out.parent!=parent.parent or out.name in ('run001','run002','run003'):
        raise ValueError('scoped review must be a new sibling of run003')
    if out.exists():
        load_contract(audit_path,policy_path);packet=verify(out)
    else:
        packet,mapping,policy=build(parent,audit_path,policy_path)
        stage=Path(tempfile.mkdtemp(prefix='.scope-',dir=out.parent))
        try:
            (stage/'scope-audit.json').write_bytes(audit_path.read_bytes());(stage/'scoring-policy.md').write_bytes(policy_path.read_bytes())
            write(stage/'packet.json',packet,immutable=True);write(stage/'scope-mapping.json',mapping,immutable=True)
            (stage/'review.html').write_text(render(packet,mapping,policy));write(stage/'packet-manifest.json',manifest(stage,packet),immutable=True)
            verify(stage)
            if out.exists():raise ValueError('scoped output appeared during generation')
            stage.rename(out)
        finally:
            if stage.exists():shutil.rmtree(stage)
    print('Unapproved required/supplementary review:',packet['packet_sha256'])
    return packet
