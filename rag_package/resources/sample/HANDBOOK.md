# 규정집 PDF에서 생일휴가 신청 기한 찾기

## 설치와 예제 준비

현재 dev wheel과 같은 가상환경을 활성화하세요. 새 실습 폴더가 필요하면 `rag-lab init --out handbook-practice` 후 `cd handbook-practice`를 실행합니다. 이미 init으로 만든 폴더라면 그 안에서 바로 시작하세요. 기본 예제는 설치물에 포함된 합성 규정집 `documents/handbook.pdf`입니다.

first_handbook.py로 첫 검색을 마친 이 practice 폴더에서 준비된 로컬 Qwen으로 같은 질문에 답하려면 `../env/bin/rag-lab first-answer --execute`를 실행하세요. 기존 PDF와 BM25 인덱스를 확인하고 터미널에 인용 원문과 쪽수를 표시합니다. 저장 위치는 first-answer/answer/result.json입니다.

Codex나 Claude Code에는 다음과 같이 요청하세요.

> 설치된 HANDBOOK.md를 따라 기본 규정집에서 “생일 특별휴가는 사용 며칠 전까지 신청해야 하나요?”를 검색해 줘. BM25가 전달한 청크에서 조항과 페이지를 찾아 보여 줘. 준비된 로컬 Qwen 4B로 한 번 답하고, 인용한 원문에서 신청 기한과 승인 조건을 대조해 줘.

같은 가상환경에 PDF 리더를 준비하고 doctor에서 pypdf 6.21.2를 확인하세요.

```sh
pdf_lock=$(python -c 'from importlib.resources import files; print(files("rag_package")/"requirements-pdf.lock")')
python -m pip install --require-hashes -r "$pdf_lock"
rag-lab doctor
```

## 내 문서와 질문으로 시작하기

PDF·UTF-8 TXT·Markdown 파일의 경로와 질문을 직접 지정할 수 있습니다. 실습 폴더에서 generation-setup으로 모델 프로필을 만든 뒤 다음처럼 실행하세요. 아래 경로·제목·질문을 내 문서에 맞게 바꾸세요.

```sh
rag-lab generation-setup --provider ollama --model qwen3:4b --out my-document-model
rag-lab pipeline-setup --llm-config my-document-model/model.json --chunk-config chunk-fixed.json --method bm25 \
  --document "/경로/내 교육 휴가 규정.pdf" --title "교육 휴가 규정" \
  --question "교육 휴가 규정의 문서 식별자와 버전은 무엇인가요?" --out ".rag-runs/내 문서"
```

명시한 파일의 사본, 출처 파일명·SHA-256, 표시 제목을 새 출력 폴더에 저장합니다. 제목을 생략하면 파일명을 표시하고, 기본 분류는 사용자 문서입니다. 가상 자료일 때만 --synthetic을 추가하세요. 출력의 commands.pipeline_preview와 commands.serve를 실행하면 내 문서와 질문이 선택됩니다. 화면에서 질문을 바꾸고 다시 미리보기할 수 있습니다. 실제 생성 전에 BM25가 전달할 본문과 페이지를 읽으려면 같은 설정으로 아래 명령을 사용하세요.

```sh
dir=".rag-runs/내 문서"
rag-lab snapshot --sources "$dir/sources.json" --out "$dir/snapshot"
rag-lab build --snapshot "$dir/snapshot" --config "$dir/search.json" --out "$dir/build"
rag-lab ask --run "$dir/build" --config "$dir/search.json" --question "교육 휴가 규정의 문서 식별자와 버전은 무엇인가요?" --out "$dir/evidence"
```

저장된 evidence/result.json의 contexts에서 페이지와 원문을 확인하세요. Hybrid를 선택할 때는 같은 pipeline-setup에 --method hybrid와 준비된 --embedding-config를 지정하고, 필요하면 --reranker-config도 추가합니다.

**Codex 또는 Claude Code에 줄 요청**

> 내가 지정한 PDF 경로와 질문으로 실습해 줘. 기존 생성 프로필과 BM25를 쓰고, pipeline-setup으로 문서를 새 폴더에 준비해 줘. 내 질문이 뜨는 학습 화면과 전달할 청크의 페이지·원문을 확인해 줘. 실제 모델 호출 전까지만 진행해 줘.

### 선택 PDF에서 미리보기 → 실제 답변 → 다시 열기

실습 가상환경을 활성화한 practice 폴더에서 시작하세요. 아래의 PDF 경로와 질문을 원하는 값으로 바꾸세요. 예시는 S16에서 사용한 합성 교육 휴가 문서이므로 `--synthetic`을 붙였습니다. 본인 문서에는 해당 옵션을 생략하세요. 새 출력 이름을 사용하세요.

```sh
rag-lab generation-setup --provider ollama --model qwen3:4b --inspect-local --out my-pdf-model
rag-lab pipeline-setup --llm-config my-pdf-model/model.json --chunk-config chunk-fixed.json \
  --method bm25 --document "/경로/교육 휴가 규정.pdf" --title "자격시험 교육 휴가 규정" --synthetic \
  --question "교육 휴가 규정의 문서 식별자와 버전은 무엇인가요?" --out "내 문서 실습"
```

두 번째 명령이 출력한 `commands.pipeline_preview` 한 줄을 복사해 그대로 실행하세요. 실제 선택된 sources·chunk-config·search-config·질문이 들어 있습니다. 위 이름을 사용했을 때의 미리보기와 선택 실행은 다음과 같습니다.

```sh
rag-lab pipeline --sources "내 문서 실습/sources.json" --chunk-config "내 문서 실습/chunk.json" \
  --search-config "내 문서 실습/search.json" --question "교육 휴가 규정의 문서 식별자와 버전은 무엇인가요?" --out "내 문서 실습-preview"
```

미리보기에서 질문과 plan.source_fingerprint, plan.generation_profile을 확인한 다음 같은 명령에서 출력 폴더만 새 이름으로 바꾸고 `--execute`를 추가하세요. 아래 마지막 명령은 이미 저장된 답변과 인용 원문을 읽습니다.

```sh
rag-lab pipeline --sources "내 문서 실습/sources.json" --chunk-config "내 문서 실습/chunk.json" \
  --search-config "내 문서 실습/search.json" --question "교육 휴가 규정의 문서 식별자와 버전은 무엇인가요?" --out "내 문서 실습-answer" --execute
rag-lab pipeline-replay --run "내 문서 실습-answer"
```

[선택한 PDF의 실제 답변·페이지·원문 대조](https://github.com/milkpotato1000/hr_rag/blob/dev/docs/verification/p032-s26/README.md)

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

앞에서 generation-setup으로 만든 my-local/model.json을 사용합니다. API를 선택했다면 my-api/model.json을 지정하세요. 환경변수에는 model-prepare 또는 model-import가 만든 profile.json의 경로를 지정합니다. 공백이 있는 경로도 인용부호로 감싸면 됩니다.

```sh
export E5_PROFILE='/path/to/e5/prepared/profile.json'
export BGE_PROFILE='/path/to/bge/prepared/profile.json'
export RERANK_PROFILE='/path/to/mmini/prepared/profile.json'
preset() {
  rag-lab pipeline-setup --llm-config my-local/model.json --chunk-config chunk-fixed.json --top-k 5 --candidate-k 20 --context-budget-chars 4000 "$@"
}
preset --method bm25 --out bm25-off
preset --method dense --embedding-config "$E5_PROFILE" --out dense-e5
preset --method hybrid --embedding-config "$E5_PROFILE" --out hybrid-e5
preset --method hybrid --embedding-config "$BGE_PROFILE" --out hybrid-bge
preset --method hybrid --embedding-config "$E5_PROFILE" --reranker-config "$RERANK_PROFILE" --out hybrid-e5-on
```

각 결과의 commands.pipeline_preview와 commands.serve를 실습 폴더에서 실행하세요. 첫 명령은 같은 승인권자 질문의 실행 계획을 보여줍니다. 두 번째 명령은 ‘문서에서 답변까지’의 기본 선택과 후보 수·K·예산을 해당 구성으로 맞춥니다. 프로필만 일반 serve에 등록한 경우에는 화면에서 직접 선택하세요. 구성 생성은 모델 파일의 해시와 역할을 확인하고 가중치는 기존 위치에 둡니다.

**임베딩만 비교**하려면 hybrid-e5와 hybrid-bge에서 같은 질문의 BD-03 첫 전달 순위와 문장 포함 여부를 대조하세요. **리랭커만 비교**하려면 hybrid-e5와 hybrid-e5-on의 후보 목록이 같은지 먼저 확인하고 최종 문맥 순위를 비교하세요. 미리보기에는 순위 실측이 없으므로 실제 관찰에는 저장한 실행의 pipeline-compare를 사용합니다.

다음은 신청 기한의 순위를 실제로 계산할 때 사용하는 단계별 명령입니다. 설치본 requirements-retrieval.lock의 SDK가 필요합니다.

```sh
question='생일 특별휴가는 사용 며칠 전까지 신청해야 하나요?'
rag-lab retrieval-preview --config dense-e5/search.json
rag-lab build --snapshot .rag-runs/pdf --config dense-e5/search.json --out .rag-runs/e5 --execute-retrieval
for method in dense hybrid; do
  rag-lab ask --run .rag-runs/e5 --config "${method}-e5/search.json" --question "$question" --out ".rag-runs/${method}" --execute-retrieval
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

아래에서는 규정집 계층 청킹과 E5 Hybrid, mMiniLM을 선택합니다.

```sh
rag-lab pipeline-setup --llm-config my-local/model.json --chunk-config chunk-handbook.json --method hybrid --embedding-config "$E5_PROFILE" --reranker-config "$RERANK_PROFILE" --out handbook-selected
question='생일 특별휴가는 사용 며칠 전까지 신청해야 하나요?'
selected_pipeline() {
  rag-lab pipeline --sources handbook-sources.json --chunk-config handbook-selected/chunk.json --search-config handbook-selected/search.json --reranker-profile handbook-selected/reranker.json --question "$question" "$@"
}
selected_pipeline --out .rag-runs/pipeline-plan
```

미리보기에서 생성 모델·전송 주소, 모델 작업 상한, 단계별 출력 폴더를 확인하세요. 실제 실행은 새 경로로 한 번 시작합니다.

```sh
selected_pipeline --out .rag-runs/pipeline-live --execute
rag-lab pipeline-replay --run .rag-runs/pipeline-live
```

BM25는 --method bm25로, API는 --llm-config my-api/model.json으로 새 구성을 만들 수 있습니다. 명시 실행하면 질문과 최종 문맥이 미리보기에 표시된 주소로 전송됩니다. 답변의 citations에서 chunk_id·heading_path·pages·start·end·quote를 보고 chunks와 rerank의 최종 문맥을 대조하세요. 실패한 실행은 pipeline.json의 failed_stage와 해당 단계 파일에서 확인하고 보존하세요.

Codex 또는 Claude Code에 줄 요청 예시: “내 규정집 PDF를 handbook-v1으로 나누고 E5 Hybrid와 mMiniLM, 준비한 로컬 Qwen으로 신청 기한을 찾아줘. 실행 전 미리보기에서 모델과 전송 주소를 확인하고, 최종 답변의 인용을 PDF 원문과 대조해 줘.”

## 브라우저에서 같은 통합 파이프라인 쓰기

pipeline-setup이 출력한 serve 명령으로 시작하세요. 이전 통합 실행을 다시 열려면 그 명령 끝에 --pipeline-run .rag-runs/pipeline-live를 추가합니다. 여러 프로필을 선택지로 등록하는 기존 serve 방식도 사용할 수 있습니다.

‘문서에서 답변까지’에서 원문, 질문, 청킹, 검색, 임베딩, 재정렬 모델과 생성 프로필을 선택합니다. ‘선택 구성 미리보기’로 예정 작업과 전송 주소를 확인하세요. 실제 실행을 원하면 서버에 --allow-model-execution을 추가합니다. Dense·Hybrid에는 --allow-retrieval-execution, 리랭커에는 --allow-reranking-execution, 의미·LLM 청킹에는 --allow-chunking-execution도 필요합니다. 다시 미리보기한 뒤 ‘이 구성으로 실제 실행’을 눌러야 모델이 동작합니다.

‘저장된 통합 결과 → 저장 결과 열기’에서 답변 아래 인용을 펼치면 제목 경로·페이지·문자 범위·원문을 읽을 수 있습니다. 이전 결과를 여는 동작은 모델을 호출하지 않습니다. 세부 검색이나 청킹 비교는 왼쪽 실습 메뉴에서 진행하세요.

## 같은 질문에서 청킹 방식 하나만 바꾸기

같은 규정집·질문·생성 프로필에서 BM25와 리랭커 끔을 유지하세요. 고정 400/80으로 저장한 통합 실행 하나와 재귀 400/80으로 저장한 실행 하나를 준비합니다. 통합 실행 화면의 ‘두 통합 실행 비교’에서 왼쪽과 오른쪽을 선택하거나 CLI에 두 결과 폴더를 지정하세요.

```sh
rag-lab pipeline-compare --runs .rag-runs/fixed-run .rag-runs/recursive-run
```

위 경로를 실제 저장한 두 통합 실행 폴더로 바꾸세요. 질문과 원문이 같은지 확인하고, 변경 항목이 chunk.method 하나인지 읽으세요. BD-03 문장이 각 실행에서 몇 번째 문맥에 들어갔는지 펼쳐 보세요. 청크 ID가 달라도 문서·페이지·문자 범위로 같은 문장을 찾을 수 있습니다. 끝으로 답변에 등장하는 조건을 실제 인용문과 대조하세요. 질문도 바꿨다면 답변 차이에 질문의 영향이 섞입니다. 비교와 재열기는 저장 파일만 읽습니다.

### 원문을 두 가지로 나눠 보고 모델에게 고르게 하기

짧은 PDF에서 조항 제목과 조건이 함께 남는지 비교할 수 있습니다. 작업 폴더에 아래 내용을 `chunk-choice.json`으로 저장하세요. `llm_config`는 chunking 역할이 설정된 프로필 경로입니다. 아래 명령의 snapshot은 자기 PDF로 만든 통합 미리보기의 snapshot 폴더입니다.

```json
{"schema_version":1,"method":"llm","partition_mode":"candidate_choice","llm_config":"llm-chunking.json","size_chars":150,"overlap_chars":0,"unit_max_chars":150}
```

```sh
rag-lab chunk --snapshot '내 문서 실습-preview/snapshot' --config chunk-choice.json --out choice-preview
```

`choice-preview/preview.json`의 requests에서 각 후보의 pieces를 읽으세요. 각 조각에는 원문과 시작·끝 위치가 들어 있습니다. 앞에서 채운 안과 뒤에서 채운 안이 같으면 모델 호출을 건너뜁니다. 실제 모델 프로필을 준비한 뒤 새 출력 폴더로 같은 명령에 `--execute-chunking`을 추가하면 선택 ID와 청크가 저장됩니다. 통합 실습에서도 `pipeline --chunk-config chunk-choice.json`으로 같은 설정을 선택할 수 있습니다.

같은 후보와 메시지에서 출력 형식만 제한하려면 위 설정에 `"candidate_format":"ollama_enum"`을 추가하세요. 로컬 Ollama 요청의 `format.properties.candidate_id.enum`에 현재 창의 후보 번호가 들어갑니다. 설치본 미리보기의 `requests[0].request.body.format`에서 확인할 수 있습니다. 수신한 번호와 원문 피복은 실행 후에도 검사합니다. [교육휴가 PDF 단일 요청 실측](https://github.com/milkpotato1000/hr_rag/blob/dev/docs/verification/p032-s18/README.md)

## 같은 PDF에서 크기·겹침·전달 예산 비교하기

Codex 또는 Claude Code에 다음과 같이 요청할 수 있습니다.

> 같은 생일 특별휴가 신청 기한 질문과 BM25를 유지해 줘. 고정 400자·겹침 80자 기준에서 크기만 240자, 겹침만 0자, 전달 예산만 400자로 바꾼 세 결과를 비교해 줘. 각각 PDF 1쪽 BD-03이 검색 몇 위이고 신청 행위와 기한이 함께 전달되는지 원문을 보여 줘. 생성 호출은 하지 마.

실습 폴더에서 아래 명령을 실행하세요. 미지정 값은 기존 청킹 설정에서 읽고, 결과는 각각 새 폴더에 저장합니다.

```sh
for variant in baseline size overlap budget; do
  case "$variant" in
    baseline) set -- ;;
    size) set -- --size-chars 240 ;;
    overlap) set -- --overlap-chars 0 ;;
    budget) set -- --context-budget-chars 400 ;;
  esac
  rag-lab pipeline-setup --llm-config llm-local.json --chunk-config chunk-fixed.json --method bm25 \
    --question "생일 특별휴가는 사용 며칠 전까지 신청해야 하나요?" "$@" --out "$variant"
done
rag-lab snapshot --sources handbook-sources.json --out size-lab-pdf
for variant in baseline size overlap budget; do
  rag-lab build --snapshot size-lab-pdf --config "$variant/search.json" --out "$variant/index"
  rag-lab ask --run "$variant/index" --config "$variant/search.json" \
    --question "생일 특별휴가는 사용 며칠 전까지 신청해야 하나요?" --out "$variant/search"
done
```

각 search/result.json의 candidates 순위, contexts의 전달 원문과 페이지, excluded의 예산 제외 사유를 대조하세요. 청크 크기와 전달 예산은 문자 수이고, 모델 입력 창은 토큰 수입니다. [네 구성의 검색 결과와 BD-03 원문 비교](https://github.com/milkpotato1000/hr_rag/blob/dev/docs/verification/p032-s22/README.md)

## 임베딩 두 개와 리랭커 세 조건을 따로 비교하기

질문은 “생일 특별휴가는 사용 며칠 전까지 신청해야 하나요?”입니다. PDF 1쪽 BD-03에서 ‘사용 3영업일 전까지 휴가 시스템에서 신청’이 들어간 첫 순위와 ‘팀장의 승인을 받아야 한다’까지 포함하는 첫 순위를 따로 읽으세요. 생일휴가 조항의 두 청크는 앞쪽 구절을 공유합니다.

설치 안내의 검색 SDK를 준비하고, 아래 환경변수에 model-prepare가 출력한 각 profile.json의 절대경로를 지정하세요. E5_PROFILE은 multilingual-e5-small, BGE_PROFILE은 bge-m3, MINI_RERANK_PROFILE은 mmarco-mMiniLMv2-L12-H384-v1, BGE_RERANK_PROFILE은 bge-reranker-v2-m3입니다. 다음 명령은 준비된 모델로 CPU 추론을 수행합니다. 새 실습 폴더에서 시작하세요.

```sh
question='생일 특별휴가는 사용 며칠 전까지 신청해야 하나요?'
rag-lab snapshot --sources handbook-sources.json --out pair-pdf
for model in e5 bge; do
  case "$model" in
    e5) profile="$E5_PROFILE" ;;
    bge) profile="$BGE_PROFILE" ;;
  esac
  dir="pair-$model"
  rag-lab pipeline-setup --llm-config llm-local.json --chunk-config chunk-fixed.json --method hybrid \
    --embedding-config "$profile" --top-k 5 --candidate-k 20 --context-budget-chars 4000 \
    --question "$question" --out "$dir" || break
  rag-lab build --snapshot pair-pdf --config "$dir/search.json" --out "$dir/index" --execute-retrieval || break
  rag-lab ask --run "$dir/index" --config "$dir/search.json" --question "$question" \
    --out "$dir/search" --execute-retrieval || break
done
```

각 search/result.json에서 retrieval_trace.dense와 retrieval_trace.bm25를 읽고, candidates의 결합 순위와 contexts의 실제 전달 원문을 확인하세요. 리랭커 비교에서는 E5의 결합 후보를 한 번 고정해 세 조건에 같은 입력을 전달합니다.

```sh
rag-lab candidates --build pair-e5/index --result pair-e5/search --question-id first --n 20 --out pair-candidates
rag-lab rerank --candidates pair-candidates --method none --top-k 5 --context-budget-chars 4000 --out pair-off
rag-lab rerank --candidates pair-candidates --method cross-encoder --profile "$MINI_RERANK_PROFILE" \
  --execute-reranking --top-k 5 --context-budget-chars 4000 --out pair-mini
rag-lab rerank --candidates pair-candidates --method cross-encoder --profile "$BGE_RERANK_PROFILE" \
  --execute-reranking --top-k 5 --context-budget-chars 4000 --out pair-bge-rerank
```

세 result.json에서 candidate_fingerprint가 같은지 확인한 뒤 selection.ranking과 selection.contexts를 대조하세요. 모델별 점수의 척도가 달라서 근거 순위와 실제 전달 여부를 비교합니다. [같은 질문의 실측 표와 원문](https://github.com/milkpotato1000/hr_rag/blob/dev/docs/verification/p032-s24/README.md)
