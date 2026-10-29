'use strict';
const $ = id => document.getElementById(id);
const isExperiment = document.body.dataset.view === 'experiment';
let running = false;
const reasons = {model_abstained:'모델이 근거 부족으로 판단했습니다. 필요한 근거가 실제로 있었는지도 확인하세요.',invalid_model_response:'모델 응답 또는 인용 검증에 실패해 답변을 보류했습니다. trace에서 실패 사유를 확인하세요.',no_context:'전달할 문맥이 없어 모델을 호출하지 않았습니다.',provider:'모델 연결 또는 응답 오류입니다. Ollama 실행 상태를 확인한 뒤 다시 시도하세요.',timeout:'모델 요청 시간이 초과됐습니다. 로드 상태를 확인한 뒤 다시 시도하세요.',execution:'색인·lock 또는 실행 환경을 확인하세요.',input:'입력과 설정을 확인하세요.'};
let lastResult = null;
function node(tag, text, className) {const el=document.createElement(tag); if(text!==undefined)el.textContent=text;if(className)el.className=className;return el;}
function detailsFor(chunk, label, score) {const d=node('details'), s=node('summary');s.append(node('span',label,'rank'),document.createTextNode(chunk.title||chunk.chunk_id));if(score!==undefined)s.append(node('span',Number(score).toFixed(4),'score'));d.append(s,node('p',chunk.text),node('div',`${chunk.chunk_id} · 문서 ${chunk.document_id} · v${chunk.version}\n${chunk.source}`,'source'));return d;}
function render(result){
 lastResult=result;$('empty').hidden=true;$('result').hidden=false;
 const statusNames={answered:'답변 생성',abstained:'답변 보류',error:'실행 오류'};
 $('status').textContent=statusNames[result.status]||'알 수 없는 상태';$('status').className='badge '+result.status;
 $('answer').textContent=result.answer;$('reason').textContent=reasons[result.reason]||'원문 인용을 확인하고, 답변에 필요한 조건이 모두 있는지 대조하세요.';
 const t=result.trace||{};
 $('citations').replaceChildren();for(const c of result.citations||[]){const box=node('div',undefined,'citation');box.append(node('b',c.title),node('blockquote',c.quote),node('div',`${c.chunk_id} · ${c.document_id} · v${c.version}\n${c.source}`,'source'));$('citations').append(box);}
 $('candidates').replaceChildren();const candidates=t.candidates||[];$('candidate-count').textContent=`${candidates.length}개 후보`;
 candidates.forEach((c,i)=>$('candidates').append(detailsFor(c,String(i+1).padStart(2,'0'),c.score)));
 if(!candidates.length)$('candidates').append(node('p','검색 결과가 없거나 검색을 완료하지 못했습니다.','muted'));
 $('contexts').replaceChildren();for(const c of t.contexts||[])$('contexts').append(detailsFor(c,'전달'));
 $('context-count').textContent=`${(t.contexts||[]).length}개 · ${t.context_chars||0} / ${t.settings?.max_context_chars??'—'}자`;
 $('excluded').replaceChildren();for(const c of t.excluded||[])$('excluded').append(node('div',`제외 · ${c.chunk_id} — ${c.reason==='outside_top_k'?'top-k 밖':`청크 전체 ${c.chars}자가 남은 예산을 초과`}`));
 $('timings').replaceChildren();for(const [key,label]of [['retrieval','검색 전체'],['context','문맥 조립'],['generation','생성 전체'],['total','전체 실행']]){const box=node('div',undefined,'timing');box.append(node('span',label),node('b',t.timings_ms?.[key]!==undefined?(t.timings_ms[key]/1000).toFixed(2)+' s':'—'));$('timings').append(box);}
 const g=t.generation, r=t.retrieval||{};
 const seconds=(value,unit=1000)=>typeof value==='number'?(value/unit).toFixed(3)+' s':'—';
 $('model-info').replaceChildren();const lines=[`구현: ${t.comparison?.implementation||'—'} · 실행 ID ${t.comparison?.run_id||'—'}`,`검색: ${t.retriever||'—'} · top-k ${t.settings?.top_k??'—'} · 생성 호출 ${t.generation_calls??0}회`,g?`모델: ${g.model} · digest ${g.digest}`:'모델: 호출하지 않음 또는 실행 전 실패',`프롬프트: ${t.prompt?.system_version||'—'} · ${t.prompt?.system_sha256||'—'}`,g?`설정: ${JSON.stringify(g.request?.options??{})} · think=false · stream=false`:'',`질문 임베딩 ${seconds(r.embedding_ms)} · 검색 ${seconds(r.search_ms)} · 생성 모델 로드 ${seconds(g?.observations?.load_duration,1e9)}`,`인용 구조: ${t.citation_structure_valid===true?'통과':t.citation_structure_valid===false?'실패':'검사 대상 없음'} · 의미 지지: 자동 판정하지 않음`];for(const line of lines.filter(Boolean))$('model-info').append(node('div',line));
 $('trace').textContent=JSON.stringify(t,null,2);
}
for(const button of document.querySelectorAll('[data-example]'))button.addEventListener('click',()=>{$('question').value=button.dataset.example;$('question').focus();});
let lastPair = null;
function busy(value) {
 running=value;
 for(const el of document.querySelectorAll('#ask-form input, #ask-form select, #ask-form textarea, #ask-form button, #download, #download-pair'))el.disabled=value;
 for(const link of document.querySelectorAll('[data-app-nav]')){link.setAttribute('aria-disabled',String(value));if(value)link.setAttribute('tabindex','-1');else link.removeAttribute('tabindex');}
 if(!value)$('navigation-notice').hidden=true;
}
for(const link of document.querySelectorAll('[data-app-nav]'))link.addEventListener('click',e=>{if(running){e.preventDefault();$('navigation-notice').hidden=false;}});
// A restored browser document must not present a previous request as a new run.
window.addEventListener('pageshow',event=>{if(event.persisted)window.location.reload();});
function settings(){return {question:$('question').value,retriever:$('retriever').value,top_k:Number($('top-k').value),max_context_chars:Number($('context-budget').value),implementation:isExperiment?$('implementation').value:'langchain'};}
async function requestRun(compare){
 if(running || (compare && !isExperiment))return;const body=settings();busy(true);lastResult=null;lastPair=null;
 $('result').hidden=true;if(isExperiment){$('comparison').hidden=true;$('pair-results').replaceChildren();}$('empty').hidden=true;$('activity').hidden=false;
 const start=Date.now();const tick=()=>{$('activity').textContent=`${compare?'Direct → LangChain 비교':isExperiment?'선택한 구현 실행':'LangChain 실행'} 중… ${Math.floor((Date.now()-start)/1000)}초`;};tick();const timer=setInterval(tick,1000);
 try{
  const response=await fetch(compare?'/api/compare':'/api/ask',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});const data=await response.json();
  if(compare && Array.isArray(data.results)){
   lastPair=data;$('comparison').hidden=false;$('pair-results').replaceChildren();
   const [a,b]=data.results.map(x=>x.result.trace||{});
   const same=(key)=>JSON.stringify(a[key])===JSON.stringify(b[key]);
   $('pair-summary').textContent=`corpus ${a.corpus_sha256||'—'} · ${body.retriever} / K=${body.top_k} / 예산=${body.max_context_chars} · 검색 순위·점수 ${same('candidates')?'동일':'차이/실패'} · 전달 문맥 ${same('contexts')?'동일':'차이/실패'} · 제외 문맥 ${same('excluded')?'동일':'차이/실패'}`;
   for(const row of data.results){const r=row.result,card=node('article',undefined,'panel');card.append(node('h3',`${row.order}. ${row.implementation} · ${(row.wall_ms/1000).toFixed(2)}초`),node('p',`${r.status} · ${r.reason||'정상'}`),node('p',r.answer));
    for(const c of r.citations||[])card.append(node('b',c.title),node('blockquote',c.quote));
    const button=node('button','검색·문맥·trace 자세히 보기','subtle');button.type='button';button.addEventListener('click',()=>{render(r);$('result').scrollIntoView({behavior:'smooth'});});card.append(button);$('pair-results').append(card);}
  }else {if(!data||!['answered','abstained','error'].includes(data.status))throw Error('invalid server response');render(data);}
  $('activity').textContent=`완료 · ${((Date.now()-start)/1000).toFixed(1)}초. 각 결과의 누락·보류·오류를 함께 확인하세요.`;
 }catch(error){render({status:'error',answer:'로컬 서버 응답을 받지 못했습니다.',citations:[],reason:'provider',trace:{error:{kind:'provider',message:String(error)}}});$('activity').textContent='연결 오류 · 다시 실행할 수 있습니다.';}
 finally{clearInterval(timer);busy(false);refreshStatus();}
}
$('ask-form').addEventListener('submit',e=>{e.preventDefault();requestRun(false);});
$('compare')?.addEventListener('click',()=>{if($('ask-form').reportValidity())requestRun(true);});
$('download-pair')?.addEventListener('click',()=>{if(!lastPair)return;const url=URL.createObjectURL(new Blob([JSON.stringify(lastPair,null,2)],{type:'application/json'}));const a=node('a');a.href=url;a.download='naive-rag-comparison.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);});
if(isExperiment)fetch('/api/decision').then(r=>r.json()).then(d=>{$('decision').textContent=`P011 비교 판정: ${d.decision} · 권장 구현: ${d.selected_implementation}. 현재 기본 학습은 LangChain입니다.`;}).catch(()=>{$('decision').textContent='과거 판정 파일을 불러오지 못했습니다. 현재 기본 학습은 LangChain입니다.';});
$('download').addEventListener('click',()=>{if(!lastResult)return;const url=URL.createObjectURL(new Blob([JSON.stringify(lastResult,null,2)],{type:'application/json'}));const a=node('a');a.href=url;a.download='naive-rag-result.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);});
function refreshStatus(){return fetch('/api/status').then(r=>r.json()).then(s=>{$('runtime').textContent=s.status==='error'?'환경 확인 실패 · 실행 시 오류를 확인하세요':`${s.runtime.state==='running'?'● 모델 서비스 실행 중':s.runtime.state==='external'?'● 공유 로컬 모델 서비스 연결됨':'○ 모델 서비스 정지'} · ${s.index_files_present?'색인 파일 준비됨':'색인 파일 없음'}`;}).catch(()=>{$('runtime').textContent='○ 로컬 서버 연결을 확인하세요';});}
refreshStatus();
