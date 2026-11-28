# 규정집 PDF에서 생일휴가 신청 기한 찾기

## 설치와 예제 준비

현재 dev wheel과 같은 가상환경을 활성화하세요. 새 실습 폴더가 필요하면 `rag-lab init --out handbook-practice` 후 `cd handbook-practice`를 실행합니다. 이미 init으로 만든 폴더라면 그 안에서 바로 시작하세요. 기본 예제는 설치물에 포함된 합성 규정집 `documents/handbook.pdf`입니다.

Codex나 Claude Code에는 다음과 같이 요청하세요.

> 설치된 HANDBOOK.md를 따라 기본 규정집에서 “생일 특별휴가는 사용 며칠 전까지 신청해야 하나요?”를 검색해 줘. BM25가 전달한 청크에서 조항과 페이지를 찾아 보여 줘. 준비된 로컬 Qwen 4B로 한 번 답하고, 인용한 원문에서 신청 기한과 승인 조건을 대조해 줘.

같은 가상환경에 PDF 리더를 준비하고 doctor에서 pypdf 6.21.2를 확인하세요.

```sh
pdf_lock=$(python -c 'from importlib.resources import files; print(files("rag_package")/"requirements-pdf.lock")')
python -m pip install --require-hashes -r "$pdf_lock"
rag-lab doctor
```

**내 PDF로 실습할 때**는 별도 새 폴더를 init하고, 내 파일을 그 폴더의 documents 아래 고유한 이름으로 복사하세요. 그 폴더의 handbook-sources.json에서 path와 title을 내 파일에 맞추고 실제 문서라면 synthetic을 false로 설정하세요. 원본 PDF는 그대로 두고 이후 명령은 새 폴더에서 실행합니다.

## 모델 호출 없이 검색 확인

```sh
question='생일 특별휴가는 사용 며칠 전까지 신청해야 하나요?'
rag-lab snapshot --sources handbook-sources.json --out .rag-runs/pdf
rag-lab build --snapshot .rag-runs/pdf --config fixed.json --out .rag-runs/bm25
rag-lab ask --run .rag-runs/bm25 --config fixed.json --question "$question" --out .rag-runs/preview
python -c 'import json; r=json.load(open(".rag-runs/preview/result.json")); print(r["status"]); [print(n, [p["page"] for p in c["pages"]], c["text"]) for n,c in enumerate(r["contexts"], 1)]'
```

snapshot이 ready인지 확인하세요. needs_review이면 PDF 텍스트 추출 상태부터 살펴보세요. fixed.json은 400자, 오버랩 80자, BM25 상위 5개, 문맥 예산 4,000자로 설정돼 있습니다. 출력한 문맥에서 신청 기한이 나오는 조항과 실제 PDF 페이지를 찾으세요.

## 답변 모델을 고르고 규정집으로 미리보기

PDF 실습 폴더에서 아래 두 경로 중 하나를 선택하세요. 출력 폴더 이름은 매번 새 이름을 쓰세요. 설정 명령의 결과에 실제 파일을 가리키는 `commands.pipeline_preview`와 `commands.serve` 명령도 표시됩니다.

**로컬 Ollama**가 이미 실행 중이면 설치된 정확한 별칭을 확인하고 원하는 모델을 지정하세요.

```sh
rag-lab local-models
rag-lab generation-setup --provider ollama --model qwen3:4b --inspect-local --out my-local
```

목록 조회는 tags, 설정의 명시적 조회는 tags와 show만 사용합니다. 실험과 digest가 같을 때만 그 실험의 HF 출처 및 Thinking 설정을 적용합니다. 다른 digest의 HF 출처는 unknown이며, 양자화는 서버가 보고한 경우에만 기록합니다. 별칭만 알고 있으면 --inspect-local 없이도 오프라인 미리보기를 준비할 수 있습니다. 실제 생성 전에는 서버를 확인해 새 출력 폴더에 구성하세요.

**선택 API**는 사용 계정의 모델명과 API 키를 담을 환경변수 이름을 지정합니다. 아래 모델명은 본인 모델명으로 바꾸세요. endpoint는 provider의 기본 URL을 쓰거나 --endpoint로 지정합니다.

```sh
rag-lab generation-setup --provider openai_chat --model YOUR_MODEL_ID --endpoint https://api.openai.com/v1 --key-env OPENAI_API_KEY --out my-api
```

Anthropic은 --provider anthropic_messages를 선택하세요. 기본 endpoint는 https://api.anthropic.com/v1 이고 키 환경변수 기본 이름은 ANTHROPIC_API_KEY입니다. 설정 및 미리보기는 키를 조회하지 않습니다.

**같은 규정집으로 연결**합니다. 선택한 폴더를 mode에 지정하세요.

```sh
mode=my-local  # API 설정을 선택했다면 my-api
question='생일 특별휴가를 신청하면 누구의 승인을 받아야 하나요?'
rag-lab pipeline --sources handbook-sources.json --chunk-config chunk-fixed.json --search-config "$mode/search.json" --question "$question" --out "$mode-preview"
rag-lab serve --workspace . --sources handbook-sources.json --chunk-config chunk-fixed.json --llm-config "$mode/model.json"
```

미리보기의 generation에서 model과 destination을 확인하세요. 학습 화면의 ‘문서에서 답변까지’에서도 동일 프로필을 선택하고 전송 주소를 확인할 수 있습니다. 준비한 로컬 모델로 실제 생성할 때는 pipeline에 --execute를 붙이고 별도 새 --out을 지정합니다. 화면에서 실제 생성을 허용할 때는 serve에 --allow-model-execution을 지정합니다.

**Codex 또는 Claude Code에 줄 요청**

> 설치된 HANDBOOK.md와 기본 규정집으로 실습해 줘. 내가 선택한 provider와 모델명으로 generation-setup을 실행하고, 출력된 profile과 search 설정으로 같은 질문의 pipeline 미리보기와 학습 화면을 연결해 줘. 선택 모델과 전송 주소를 보여주고 실제 생성 전까지 진행해 줘.

**기존 실습 재현**에는 아래처럼 실측 Qwen digest 전용 spec으로 handbook-model.json을 생성할 수 있습니다. 이어지는 고급 실습에서 이 파일 이름을 사용합니다. 사용자 작성 spec에는 기존 llm-configure를 그대로 사용하세요.

```sh
rag-lab llm-configure --spec handbook-qwen-spec.json --out handbook-model.json --inspect-local
rag-lab llm-configure --spec llm-spec-api.json --out handbook-api.json
```

## 신청 기한의 근거는 몇 위에 들어올까?

위 BM25 미리보기와 같은 PDF snapshot 및 질문을 사용합니다. E5 임베딩과 mMiniLM 리랭커의 준비된 profile.json, 설치본의 requirements-retrieval.lock과 일치하는 SDK가 필요합니다. 두 환경변수에는 본인의 준비된 프로필 **절대경로**를 지정하세요. 아래 명령은 handbook-practice 안에서 실행합니다.

```sh
export E5_PROFILE=/absolute/path/to/e5/prepared/profile.json
export RERANK_PROFILE=/absolute/path/to/mmini/prepared/profile.json
python - <<'PY'
import json, os
from pathlib import Path
template = json.loads(Path('rag-hybrid.json').read_text())
template['chunking'] = json.loads(Path('fixed.json').read_text())['chunking']
template['embedding_config'] = str(Path(os.environ['E5_PROFILE']).resolve(strict=True))
for method in ('dense', 'hybrid'):
    template['retrieval']['method'] = method
    Path(f'handbook-{method}.json').write_text(json.dumps(template, indent=2))
PY
question='생일 특별휴가는 사용 며칠 전까지 신청해야 하나요?'
rag-lab retrieval-preview --config handbook-dense.json
rag-lab build --snapshot .rag-runs/pdf --config handbook-dense.json --out .rag-runs/e5 --execute-retrieval
for method in dense hybrid; do
  rag-lab ask --run .rag-runs/e5 --config "handbook-${method}.json" --question "$question" --out ".rag-runs/${method}" --execute-retrieval
done
rag-lab candidates --build .rag-runs/e5 --result .rag-runs/hybrid --question-id first --n 20 --out .rag-runs/candidates
rag-lab rerank --candidates .rag-runs/candidates --method none --top-k 5 --context-budget-chars 4000 --out .rag-runs/off
rag-lab rerank --candidates .rag-runs/candidates --method cross-encoder --profile "$RERANK_PROFILE" --top-k 5 --context-budget-chars 4000 --execute-reranking --out .rag-runs/on
for mode in off on; do
  rag-lab answer-from-rerank --run ".rag-runs/${mode}" --llm-config llm-local.json --out ".rag-runs/context-${mode}"
done
```

각 result.json의 contexts를 위 BM25 예제처럼 읽으세요. BD-03 신청 기한 문장이 온전히 들어간 첫 청크의 순위와 PDF 페이지를 기록하세요. Dense는 의미 벡터로 정렬하고 Hybrid는 BM25와 Dense의 순위를 RRF로 결합합니다. off와 on은 같은 후보 20개 안에서 순위를 비교합니다. 마지막 두 명령은 최종 전달 문맥을 보여줍니다. 실제 인용은 답변을 생성한 S3에서 확인할 수 있습니다.

BGE-M3를 쓰려면 E5_PROFILE을 해당 준비 프로필로 바꾸고 설정 두 개를 다시 만든 뒤 새 출력 디렉터리에 인덱스를 빌드하세요. 리랭커만 바꿀 때는 RERANK_PROFILE에 준비한 BGE 리랭커 경로를 넣고 같은 candidates에 새 출력 디렉터리로 재정렬하면 됩니다.

UI에서는 실습 작업공간에 준비된 프로필을 등록하고 serve의 --embedding-config, --reranker-config 및 --allow-retrieval-execution, --allow-reranking-execution 옵션을 지정합니다. ‘검색과 전달 문맥’에서 질문·검색 방식·임베딩 모델을 선택하고, ‘고정 후보 리랭킹’에서 같은 검색의 후보를 고정한 뒤 ‘리랭커 계산 허용’과 ‘none과 선택 모델 비교’를 사용하세요.

Codex나 Claude Code에 요청할 예시: “같은 PDF와 질문으로 위 명령을 실행해 줘. 검색 방식별로 BD-03 신청 기한을 온전히 담은 첫 청크의 순위·페이지와 최종 전달 여부를 표로 보여줘. 답변 생성은 실행하지 마.”

## 같은 근거에서 생성 모델만 바꾸기

위에서 만든 .rag-runs/on을 두 설정에 공통으로 사용하세요. handbook-model.json은 준비한 로컬 프로필이고 handbook-api.json은 API 프로필입니다. 먼저 둘 다 미리보기로 저장합니다.

```sh
rag-lab answer-from-rerank --run .rag-runs/on --llm-config handbook-model.json --out .rag-runs/local-preview
rag-lab answer-from-rerank --run .rag-runs/on --llm-config handbook-api.json --out .rag-runs/api-preview
rag-lab compare-answers --result local .rag-runs/local-preview --result api .rag-runs/api-preview
```

원하는 프로필 하나를 명시 실행하려면 해당 answer-from-rerank 명령에 --execute를 추가하고 새 출력 디렉터리를 지정하세요. 유료 API를 실제 실행하려면 모델명과 키 환경변수를 먼저 설정하세요. 다른 로컬 모델도 별도 프로필로 등록할 수 있습니다. compare-answers에서 해당 디렉터리를 선택하면 저장된 답변·인용 페이지·관측 토큰·지연을 다시 읽습니다. preview는 생성 전 상태이며 미측정 값은 null입니다.

UI에서는 동일한 재정렬 결과를 열고 모델을 선택해 ‘선택 문맥으로 답변 미리보기’ 또는 ‘선택 문맥으로 실제 답변 생성’을 사용하세요. ‘생성 모델 비교’에서 두 저장 기록을 선택해 질문과 입력 일치 여부부터 확인하세요.

## PDF 청킹 비교 · 같은 질문의 근거가 어디서 끊길까?

앞에서 만든 `.rag-runs/pdf` snapshot을 사용합니다. 이번에는 규칙만 바꿉니다. 고정 크기·재귀·구조 방식 모두 400자, 겹침 80자입니다. 세 설정에 공통으로 BM25 후보 20개, 최종 5개, 전달 예산 4,000자를 사용합니다.

```sh
for method in fixed recursive structure; do
  rag-lab chunk --snapshot .rag-runs/pdf --config "chunk-$method.json" --out ".rag-runs/handbook-chunk-$method" || exit 1
done
python - <<'PY'
import json
from pathlib import Path
template = json.loads(Path('rag-frozen.json').read_text())
for method in ('fixed', 'recursive', 'structure'):
    template['chunk_artifact'] = '.rag-runs/handbook-chunk-' + method
    Path('search-' + method + '.json').write_text(json.dumps(template))
q = [{'id': 'deadline', 'question': '생일 특별휴가는 사용 며칠 전까지 신청해야 하나요?'}]
Path('deadline.json').write_text(json.dumps(q, ensure_ascii=False))
PY
rag-lab compare --snapshot .rag-runs/pdf --configs search-fixed.json search-recursive.json search-structure.json --questions deadline.json --out .rag-runs/handbook-chunk-compare
rag-lab chunk-report --run .rag-runs/handbook-chunk-compare --out .rag-runs/handbook-chunk-report
```

저장된 `.rag-runs/handbook-chunk-report/report.html`에서 세 결과를 읽으세요. 개별 전달 청크는 비교 폴더의 `config-1/answers/deadline/result.json`부터 config-3까지의 contexts에 순서대로 있습니다. PDF 1쪽에서 BD-03을 찾고, 각 청크가 신청 기한만 담았는지 팀장 승인까지 한 문장으로 담았는지 확인하세요. 문자 범위는 정규화 원문의 시작 포함·끝 제외입니다.

UI로 따라가려면 아래 명령으로 새 로컬 실습 서버를 여세요.

```sh
rag-lab serve --workspace . --sources handbook-sources.json --llm-config llm-local.json --chunk-config chunk-fixed.json --chunk-config chunk-recursive.json --chunk-config chunk-structure.json
```

1. ‘문서 준비’에서 규정집을 선택해 snapshot을 만드세요.
2. ‘청킹’의 ‘저장 경계 실험’에서 설정을 하나씩 선택하고 ‘현재 snapshot으로 경계 만들기 / 미리보기’를 누르세요. 청크의 ‘원문 보기’에서 PDF 페이지와 경계를 대조하세요.
3. 저장 청크 세 개를 복수 선택하고 청킹 비교 질문에 위 질문을 넣으세요. ‘검색과 전달 문맥’의 BM25·후보 20·최종 5·예산 4,000을 확인한 뒤 ‘저장 청크 비교 · 답변 미리보기’를 누르세요. 결과 행에서 전달된 근거와 원문을 여세요.

의미 기반 설정과 LLM 설정은 각각 chunk-semantic.json과 chunk-llm.json입니다. 같은 chunk 명령에 별도 출력 경로를 주면 모델 실행 전 미리보기를 확인할 수 있습니다. 앞선 실험에서 E5 의미 경계는 실제 생성됐고, 로컬 Qwen 4B의 LLM 경계는 첫 구간에서 출력 상한에 도달했습니다.

Codex 또는 Claude Code에 요청할 예시: “같은 PDF·질문·BM25에서 세 규칙의 청크를 비교해 줘. 신청 기한과 팀장 승인을 함께 담은 첫 청크의 순위와 PDF 페이지를 알려 주고, 구조 방식이 실제 제목을 인식했는지도 확인해 줘. 답변 모델은 호출하지 마.”

## 장·절·조항 경로를 유지하며 긴 절 나누기

기본 구조 설정은 일반 제목 규칙을 사용합니다. 규정집의 코드가 붙은 제목을 구분하려면 설치 샘플 `chunk-handbook.json`의 `heading_profile: handbook-v1`을 선택하세요. ‘제1장 … [BD]’, ‘제1절 … [BD-S1]’, ‘BD-03 신청 기한과 승인’처럼 장 코드·절 번호가 일치하고 독립된 한 줄인 제목을 지원합니다. 태그 없는 목차의 장 목록은 앞부분 원문으로 유지합니다. 조항 제목은 같은 코드의 절 아래에서만 인식하며 명사형 짧은 표제를 전제로 합니다. 문장 중간의 코드, ‘BD-03에 따라’ 같은 참조, 마침표나 서술형 ‘다’로 끝나는 줄은 조항 제목으로 취급하지 않습니다. 이 형식을 사용하지 않는 문서에는 일반 구조 설정이 적합합니다.

긴 조항 안에서는 재귀 방식으로 계속 분할합니다. 겹침은 같은 하위 섹션 안에서만 적용됩니다. 제목을 검색 본문 앞에 복사하지 않고 heading_path에 기록하므로 원문 페이지와 문자 위치를 대조할 수 있습니다. 인식된 제목이 없으면 경로는 비고 재귀 분할로 진행됩니다.

앞의 PDF 청킹 비교 실습을 마친 폴더에서 다음을 실행하세요.

```sh
rag-lab chunk --snapshot .rag-runs/pdf --config chunk-handbook.json --out .rag-runs/handbook-hierarchy
python - <<'PY'
import json
from pathlib import Path
cfg = json.loads(Path('rag-frozen.json').read_text())
cfg['chunk_artifact'] = '.rag-runs/handbook-hierarchy'
Path('search-hierarchy.json').write_text(json.dumps(cfg))
PY
rag-lab compare --snapshot .rag-runs/pdf --configs search-structure.json search-hierarchy.json --questions deadline.json --out .rag-runs/heading-compare
rag-lab chunk-report --run .rag-runs/heading-compare --out .rag-runs/heading-report
```

UI의 serve 명령에 `--chunk-config chunk-handbook.json`을 추가하세요. ‘청킹 → 저장 경계 실험’에서 ‘structure · 규정집 계층’을 선택하고 현재 snapshot의 경계를 만드세요. BD-03 청크의 제목 경로, 문자 범위, ‘원문 보기’를 차례로 확인하세요.

## 선택한 구성으로 PDF부터 답변까지 실행하기

앞서 만든 handbook-sources.json과 handbook-model.json을 사용합니다. 준비한 임베딩·리랭커 profile.json의 절대경로를 E5_PROFILE과 RERANK_PROFILE에 지정하세요. 검색 템플릿에서 검색 방식·후보 수·최종 K·문맥 예산·생성 프로필을 선택하고, 청킹은 --chunk-config에서 선택합니다.

```sh
python - <<'PY'
import json, os
from pathlib import Path
cfg = json.loads(Path('rag-hybrid.json').read_text())
cfg['embedding_config'] = str(Path(os.environ['E5_PROFILE']).resolve(strict=True))
cfg['llm_config'] = 'handbook-model.json'
Path('pipeline-search.json').write_text(json.dumps(cfg, indent=2))
PY
question='생일 특별휴가는 사용 며칠 전까지 신청해야 하나요?'
selected_pipeline() {
  rag-lab pipeline --sources handbook-sources.json --chunk-config chunk-handbook.json --search-config pipeline-search.json --reranker-profile "$RERANK_PROFILE" --question "$question" "$@"
}
selected_pipeline --out .rag-runs/pipeline-plan
```

미리보기에서 생성 모델·전송 주소, 모델 작업 상한, 단계별 출력 폴더를 확인하세요. 실제 실행은 새 경로로 한 번 시작합니다.

```sh
selected_pipeline --out .rag-runs/pipeline-live --execute
rag-lab pipeline-replay --run .rag-runs/pipeline-live
```

BM25로 간단히 시작하려면 fixed.json의 llm_config를 준비한 생성 프로필로 바꾼 사본을 --search-config에 주고 --reranker-profile을 생략하세요. 유료 API는 llm_config를 해당 프로필로 바꾸면 됩니다. 명시 실행하면 질문과 최종 문맥이 미리보기에 표시된 주소로 전송됩니다. 답변의 citations에서 chunk_id·heading_path·pages·start·end·quote를 보고 chunks와 rerank의 최종 문맥을 대조하세요. 실패한 실행은 pipeline.json의 failed_stage와 해당 단계 파일에서 확인하고 보존하세요.

Codex 또는 Claude Code에 줄 요청 예시: “내 규정집 PDF를 handbook-v1으로 나누고 E5 Hybrid와 mMiniLM, 준비한 로컬 Qwen으로 신청 기한을 찾아줘. 실행 전 미리보기에서 모델과 전송 주소를 확인하고, 최종 답변의 인용을 PDF 원문과 대조해 줘.”

## 브라우저에서 같은 통합 파이프라인 쓰기

준비한 프로필 JSON을 실습 폴더 안에 두세요. 임베딩·리랭커 프로필을 복사할 때 local_path는 기존 모델 디렉터리의 절대경로로 유지합니다. 아래 명령은 앞에서 저장한 통합 실행 결과를 등록하고, 새 질문을 미리보기로 살펴볼 수 있게 합니다.

```sh
rag-lab serve --workspace . --sources handbook-sources.json --llm-config handbook-model.json --chunk-config chunk-fixed.json --chunk-config chunk-handbook.json --embedding-config embedding-e5.json --reranker-config reranker-bge.json --pipeline-run .rag-runs/pipeline-live
```

임베딩과 리랭커 옵션에는 사용할 실제 프로필 파일명을 지정하세요. API 설정도 선택하려면 --llm-config를 한 번 더 지정하세요. 처음 실습해 저장 결과가 없다면 --pipeline-run 옵션을 생략하세요.

‘문서에서 답변까지’에서 원문, 질문, 청킹, 검색, 임베딩, 재정렬 모델과 생성 프로필을 선택합니다. ‘선택 구성 미리보기’로 예정 작업과 전송 주소를 확인하세요. 실제 실행을 원하면 서버에 --allow-model-execution을 추가합니다. Dense·Hybrid에는 --allow-retrieval-execution, 리랭커에는 --allow-reranking-execution, 의미·LLM 청킹에는 --allow-chunking-execution도 필요합니다. 다시 미리보기한 뒤 ‘이 구성으로 실제 실행’을 눌러야 모델이 동작합니다.

‘저장된 통합 결과 → 저장 결과 열기’에서 답변 아래 인용을 펼치면 제목 경로·페이지·문자 범위·원문을 읽을 수 있습니다. 이전 결과를 여는 동작은 모델을 호출하지 않습니다. 세부 검색이나 청킹 비교는 왼쪽 실습 메뉴에서 진행하세요.

## 같은 질문에서 청킹 방식 하나만 바꾸기

같은 규정집·질문·생성 프로필에서 BM25와 리랭커 끔을 유지하세요. 고정 400/80으로 저장한 통합 실행 하나와 재귀 400/80으로 저장한 실행 하나를 준비합니다. 통합 실행 화면의 ‘두 통합 실행 비교’에서 왼쪽과 오른쪽을 선택하거나 CLI에 두 결과 폴더를 지정하세요.

```sh
rag-lab pipeline-compare --runs .rag-runs/fixed-run .rag-runs/recursive-run
```

위 경로를 실제 저장한 두 통합 실행 폴더로 바꾸세요. 질문과 원문이 같은지 확인하고, 변경 항목이 chunk.method 하나인지 읽으세요. BD-03 문장이 각 실행에서 몇 번째 문맥에 들어갔는지 펼쳐 보세요. 청크 ID가 달라도 문서·페이지·문자 범위로 같은 문장을 찾을 수 있습니다. 끝으로 답변에 등장하는 조건을 실제 인용문과 대조하세요. 질문도 바꿨다면 답변 차이에 질문의 영향이 섞입니다. 비교와 재열기는 저장 파일만 읽습니다.
