"""Build and replay a strictly unapproved, source-linked human reading packet."""
import difflib
import html
import hashlib
import json
import re
import statistics
from pathlib import Path
from core import read, write, digest, file_hash, locate, validate_review_packet, validate
from prepare import verify_frozen, active_cases
from review_drafts import REFERENCES


def resolve_needle(text, needle):
    positions = [i for i,c in enumerate(text) if not c.isspace()]
    compact = ''.join(text[i] for i in positions)
    target = ''.join(needle.split())
    if compact.count(target) != 1:
        raise ValueError('Codex locator mismatch/ambiguity: ' + needle)
    start = compact.index(target); end = start + len(target)
    return positions[start], positions[end-1] + 1


def corrected(q, canonical_hash, pages=None):
    units = {s['article_id']:s for s in q['source_spans']}
    result = []; answer = '\n'.join(r[0] for r in REFERENCES[q['id']])
    for index, (text, article, needle) in enumerate(REFERENCES[q['id']], 1):
        unit = units[article]; a,b = resolve_needle(unit['text'], needle)
        quote = unit['text'][a:b]
        source_pages = [p['page_number'] for p in pages if p['start'] < unit['start']+b and p['end'] > unit['start']+a] if pages else unit['pages']
        result.append(dict(id=q['id']+'-c%02d'%index, text=text, answer_span=locate(answer,text),
                           source=dict(article_id=article, start=unit['start']+a, end=unit['start']+b,
                                       quote=quote, quote_sha256=hashlib.sha256(quote.encode()).hexdigest(), pages=source_pages,
                                       canonical_sha256=canonical_hash)))
    if len(result)>8:raise ValueError('too many reference claims')
    return dict(answer=answer, claims=result)


def absence_audit(out):
    canonical=(out/'source/extracted/canonical/hr-v4-handbook.txt').read_text()
    inventory=read(out/'source/policy-inventory.json')
    terms=['전기','유류','차량','킬로미터','킬로','km','교통','요금','지급 한도','지원 금액','비용']
    matches={}
    for term in terms:
        matches[term]=[dict(start=m.start(),end=m.end(),context=canonical[max(0,m.start()-60):m.end()+120])
                       for m in re.finditer(re.escape(term),canonical,re.I)]
    policy_text='\n'.join(i['authored_text'] for i in inventory['items'])
    return dict(canonical_sha256=file_hash(out/'source/extracted/canonical/hr-v4-handbook.txt'),
                canonical_characters_scanned=len(canonical),inventory_items_scanned=len(inventory['items']),
                inventory_sha256=file_hash(out/'source/policy-inventory.json'),matches=matches,
                policy_matches={t:len(list(re.finditer(re.escape(t),policy_text,re.I))) for t in terms},
                method='Full canonical and complete policy inventory keyword/amount-context review by Codex; source files supplied for human full-text review',
                limitation='Search-based negative evidence is a review candidate, not proof of real-company benefit absence. Human confirmation required; no fabricated absence span.')


def quote_issues(q, originals):
    units={s['article_id']:s['text'] for s in q['source_spans']};issues=[]
    for attempt in originals:
        value=attempt.get('parsed')
        if not isinstance(value,dict):continue
        seen=set()
        claims=value.get('claims',[])
        if not isinstance(claims,list):continue
        for i,c in enumerate(claims,1):
            if not isinstance(c,dict):continue
            unit=units.get(c.get('unit_id'));quote=c.get('source_quote');answer_quote=c.get('answer_quote')
            if not isinstance(quote,str) or unit is None:
                issues.append(dict(attempt=attempt['artifact'],claim=i,kind='unknown source ID or missing quote'));continue
            key=(c.get('unit_id'),quote)
            if key in seen:issues.append(dict(attempt=attempt['artifact'],claim=i,kind='duplicate source quote'))
            seen.add(key)
            if unit.count(quote)!=1:
                compact=''.join(quote.split())
                kind='source whitespace changed' if compact and ''.join(unit.split()).count(compact)==1 else 'source quote mismatch/ambiguity'
                issues.append(dict(attempt=attempt['artifact'],claim=i,kind=kind))
            if not isinstance(answer_quote,str) or not isinstance(value.get('answer'),str) or value['answer'].count(answer_quote)!=1:
                issues.append(dict(attempt=attempt['artifact'],claim=i,kind='answer quote mismatch/ambiguity'))
    return issues


def build_packet(out):
    frozen=verify_frozen(out);inputs=read(out/'inputs.json');ledger=read(out/'ledger.json')
    active_cases(out)
    from runner import Ledger
    Ledger(out,frozen['sha256']).state()
    if ledger['pending'] or ledger['unresolved']:raise ValueError('unresolved model request')
    page_manifest=out/'source/extracted/manifest.json'
    if file_hash(page_manifest)!=read(out/'source/handoff-manifest.json')['files']['extracted/manifest.json']:raise ValueError('page manifest hash mismatch')
    pages=read(page_manifest)['documents'][0]['pages']
    raw={}
    for row in ledger['calls']:
        call=read(out/row['artifact'])
        if digest(call)!=row['artifact_sha256']:raise ValueError('call artifact tamper')
        parsed=call.get('parsed')
        if parsed is None:
            try:parsed=json.loads(call['raw_response']['message']['content'])
            except (KeyError,ValueError):pass
        raw.setdefault(row['case_id'],[]).append(dict(artifact=row['artifact'],sha256=row['artifact_sha256'],
                                                    status=call['status'],raw_response=call.get('raw_response'),
                                                    parsed=parsed,error=call.get('error')))
    questions=[]
    for q in inputs['questions']:
        item=dict(id=q['id'],question=q['question'],answerability=q['answerability'],
                  reviewer='Codex',status='draft',human_approval=None,source_spans=q['source_spans'])
        if q['answerability']=='answerable':
            originals=raw.get(q['id'],[])
            if not originals:raise ValueError('actual model draft missing: '+q['id'])
            draft=corrected(q,inputs['canonical_sha256'],pages)
            item.update(model_original_attempts=originals,codex_source_checked=draft)
            valid=[r for r in originals if r['status']=='valid']
            parsed_drafts=[r for r in originals if isinstance(r.get('parsed'),dict) and isinstance(r['parsed'].get('answer'),str)]
            prior=(parsed_drafts[-1]['parsed']['answer'] if parsed_drafts else '')
            item['revision']=dict(method='Codex source comparison; selected question requirements within max eight atomic claims; not a human-approved gold answer',
                                   changed=prior!=draft['answer'],
                                   answer_diff='\n'.join(difflib.unified_diff(prior.splitlines(),draft['answer'].splitlines(),fromfile='model-original',tofile='codex-source-checked',lineterm='')))
            item['revision']['issues']=sorted({r['error'] for r in originals if r.get('error')})
            item['revision']['claim_diagnostics']=quote_issues(q,originals)
            if q['id']=='gt01' and prior and '수습' not in prior:
                item['revision']['issues'].append('Codex 원문 대조: 모델 답변에서 수습 직원 제외 조건 누락을 확인해 수정본에 복원함.')
            if not valid:item['status']='needs_revision'
            item['human_review_points']=['조건·숫자·부정이 질문에 맞게 빠짐없이 포함됐는지', '원자 주장 경계와 인용의 충분성', '질문 밖 추가 절차를 필수 정답으로 볼지']
        else:
            answer=('제공된 가상 규정집에는 재택근무 전기요금의 월 지원 한도가 명시되어 있지 않습니다.' if q['id']=='gt09'
                    else '제공된 가상 규정집에는 개인 차량 출장의 킬로미터당 유류비 지급액이 명시되어 있지 않습니다.')
            item.update(status='needs_revision',model_original_attempts=[],codex_source_checked=dict(answer=answer,claims=[]),
                        absence_review='absence-review.json',human_review_points=['규정집 전문에서 금액 미명시 여부를 확인해 주세요.', '실제 회사의 지원 여부를 부정하는 답변으로 해석하지 마세요.'],
                        revision=dict(method='Codex entire-document/inventory search review; no model request with empty evidence',changed=None))
        questions.append(item)
    packet=dict(schema_version=1,status='draft',reviewer='Codex',human_approval=None,
                scope='P019 preparation/development set; not blind holdout, human approval, or P013 product evaluation',
                source_canonical_sha256=inputs['canonical_sha256'],frozen_input_sha256=frozen['sha256'],
                model_lock_sha256=file_hash(out/'model-lock.json'),
                prompt_revision_sha256=ledger.get('prompt_revision_sha256'),questions=questions,judgements=read(out/'judgements.json'))
    revision_files=['codex-source-review.json','codex-source-review-v2.json','codex-source-review-v3.json']
    packet['codex_revision_history']=[dict(path=p,sha256=file_hash(out/p)) for p in revision_files]
    if read(out/'p007-index-fingerprints.json')['experiment_manifest_sha256']!=read(out/'p007-inputs.json')['experiment_manifest_sha256']:
        raise ValueError('P007 experiment provenance mismatch')
    packet['p007_handoff']=dict(inputs_sha256=file_hash(out/'p007-inputs.json'),index_fingerprints_sha256=file_hash(out/'p007-index-fingerprints.json'))
    latest=read(out/revision_files[-1])
    for q,saved in zip(questions[:8],latest['questions']):
        if q['id']!=saved['id'] or q['codex_source_checked']!={k:saved[k] for k in ['answer','claims']}:
            raise ValueError('latest Codex review snapshot mismatch')
    calls=[read(out/r['artifact']) for r in ledger['calls']]
    schema_pass=0
    for c in calls:
        try:validate(json.loads(c['raw_response']['message']['content']),c['payload']['format']);schema_pass+=1
        except (KeyError,ValueError,TypeError):pass
    repeats=read(out/'repeat-results.json')
    packet['experiment']=dict(model='qwen3:8b Q4_K_M',requests=len(calls),max_requests=34,
                             cumulative_seconds=ledger['seconds'],schema_valid_calls=schema_pass,
                             exact_quote_valid_calls=sum(c['status']=='valid' for c in calls),
                             repeated_payloads_equal=sum(r['same_payload'] for r in repeats),
                             repeated_normalized_outputs_equal=sum(r['same_output'] for r in repeats),repeat_cases=len(repeats),
                             median_call_seconds=statistics.median(c['seconds'] for c in calls),
                             max_call_seconds=max(c['seconds'] for c in calls),
                             max_sampled_ollama_rss_bytes=max(c['max_sampled_rss_bytes'] for c in calls),
                             memory_scope=calls[0]['memory_scope'],
                             warning='Six smoke cases and their repeats are compatibility evidence, not independent evaluator accuracy. All raw failures retained; human review pending.')
    packet['packet_sha256']=digest(packet)
    validate_review_packet(packet)
    return packet


def render(packet):
    esc=html.escape;parts=[]
    for q in packet['questions']:
        parts.append('<section><h2>'+esc(q['id']+' · '+q['question'])+'</h2><p class="status">'+esc(q['status'])+' · Codex 검토 · 사람 미승인</p>')
        parts.append('<h3>Codex 원문 대조 수정본</h3><p>'+esc(q['codex_source_checked']['answer']).replace('\n','<br>')+'</p>')
        if q['revision'].get('issues'):
            parts.append('<p class="status">원응답 검증 문제: '+esc(' / '.join(q['revision']['issues']))+'</p>')
        for c in q['codex_source_checked']['claims']:
            s=c['source'];parts.append('<article><b>'+esc(c['id']+' · '+c['text'])+'</b><p>'+esc(s['article_id']+' · p.'+','.join(map(str,s['pages']))+' · Unicode ['+str(s['start'])+','+str(s['end'])+')')+'</p><blockquote>'+esc(s['quote'])+'</blockquote><small>quote SHA-256 '+esc(s['quote_sha256'])+'</small></article>')
        if not q['source_spans']:parts.append('<p>부재를 가리키는 원문 span은 없습니다. 전문·정책 목록의 검색 대조 결과를 사용한 미승인 후보입니다.</p>')
        parts.append('<details><summary>모델 원응답 및 수정 이력</summary><pre>'+esc(json.dumps(dict(attempts=q['model_original_attempts'],revision=q['revision']),ensure_ascii=False,indent=2))+'</pre></details>')
        parts.append('<details><summary>지정 원문 전체</summary>'+''.join('<h4>'+esc(s['article_id'])+'</h4><pre>'+esc(s['text'])+'</pre>' for s in q['source_spans'])+'</details>')
        parts.append('<p>사람 확인: '+esc(' / '.join(q['human_review_points']))+'</p></section>')
    parts.append('<section><h2>평가기 판정 후보 18개</h2><p>E: 뒷받침 · N: 결정 불가 · C: 모순. 모두 통제된 가상 fixture이며 실제 규정이 아닙니다.</p>')
    for j in packet['judgements']:
        parts.append('<article><h3>'+esc(j['id']+' · '+j['category']+' · 제안 '+j['proposed_label'])+'</h3><blockquote>'+esc(j['premise'])+'</blockquote><p>주장: '+esc(j['claim'])+'</p><p>'+esc(j['reason'])+' · 사람 미승인</p></article>')
    parts.append('</section>')
    if packet.get('experiment'):
        parts.insert(0,'<section><h2>실험 범위와 한계</h2><pre>'+esc(json.dumps(packet['experiment'],ensure_ascii=False,indent=2))+'</pre><p>형식 통과와 근거 인용 통과를 구분하세요. 실패 초안도 숨기지 않고 아래 항목에 보존했습니다.</p></section>')
    embedded=json.dumps(packet,ensure_ascii=False).replace('<','\\u003c')
    return '<!doctype html><html lang="ko"><meta charset="utf-8"><title>P019 사람 검토 패킷</title><style>body{max-width:1040px;margin:48px auto;padding:0 24px;font:16px/1.7 system-ui;color:#182434;background:#f5f7fa}h1,h2{line-height:1.35}section{background:white;border:1px solid #d9e1eb;border-radius:14px;padding:28px;margin:26px 0}article{border-left:3px solid #6886a8;padding:12px 18px;margin:16px 0}blockquote,pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#f1f4f8;padding:14px}small{overflow-wrap:anywhere;color:#526278}summary{cursor:pointer}.status{color:#855600}</style><h1>P019 · 사람 검토용 정답·판정 초안</h1><p>질문 10개 · 판정 후보 18개 · <b>모든 항목 사람 미승인</b></p><p>모델 출력과 Codex 수정본은 승인된 정답이 아닙니다. 이 파일에는 승인 기능이 없습니다. 항목 ID와 아래 패킷 hash를 기준으로 명시적인 검토 의견을 남겨 주세요.</p><p>패킷 SHA-256 <code>'+packet['packet_sha256']+'</code></p><p>이 검토·개발 세트는 독립 blind holdout이 아니며, 6개 smoke 성공은 일반 HR 평가 성능을 보장하지 않습니다. 금액 미명시 후보는 해당 문서의 범위에 한정합니다.</p>'+''.join(parts)+'<script type="application/json" id="packet">'+embedded+'</script></html>\n'


def verify_packet(out):
    packet=read(out/'packet.json');validate_review_packet(packet)
    expected=build_packet(out)
    if packet!=expected:raise ValueError('packet/model/source/revision mismatch')
    canonical=(out/'source/extracted/canonical/hr-v4-handbook.txt').read_text()
    for q in packet['questions']:
        for c in q['codex_source_checked']['claims']:
            s=c['source'];a,b=c['answer_span']
            if canonical[s['start']:s['end']]!=s['quote'] or hashlib.sha256(s['quote'].encode()).hexdigest()!=s['quote_sha256'] or q['codex_source_checked']['answer'][a:b]!=c['text']:
                raise ValueError('claim offset/quote mismatch')
    report=(out/'review.html').read_text()
    embedded=re.search(r'<script type="application/json" id="packet">(.*?)</script>',report,re.S)
    if not embedded or json.loads(embedded[1])!=packet or report!=render(packet):raise ValueError('JSON/report mismatch')
    if read(out/'absence-review.json')!=absence_audit(out):raise ValueError('absence audit mismatch')
    manifest_path=out/'packet-manifest.json'
    if manifest_path.exists():
        manifest=read(manifest_path)
        expected=dict(packet_sha256=packet['packet_sha256'],json_file_sha256=file_hash(out/'packet.json'),
                      html_file_sha256=file_hash(out/'review.html'),absence_review_sha256=file_hash(out/'absence-review.json'))
        if manifest!=expected:raise ValueError('packet file manifest mismatch')
    return packet


def report(out):
    write(out/'absence-review.json',absence_audit(out),immutable=True)
    packet=build_packet(out);write(out/'packet.json',packet,immutable=True)
    path=out/'review.html';text=render(packet)
    if path.exists() and path.read_text()!=text:raise ValueError('report immutable; create reviewed revision instead')
    path.write_text(text)
    verify_packet(out)
    write(out/'packet-manifest.json',dict(packet_sha256=packet['packet_sha256'],json_file_sha256=file_hash(out/'packet.json'),
                                         html_file_sha256=file_hash(path),absence_review_sha256=file_hash(out/'absence-review.json')),immutable=True)
    print('Unapproved packet:',packet['packet_sha256'])
