# 내 PDF에서 신청 기한 찾기

설치된 `rag-lab`과 같은 가상환경의 Python을 사용하세요. 이 실습은 텍스트를 추출할 수 있는 가상 규정집 PDF 한 개를 읽습니다. 아래 경로만 본인 파일 위치로 바꾸세요. PDF 자체는 설치물에 포함되지 않습니다.

Codex 또는 Claude Code에는 이렇게 요청할 수 있습니다.

> 이 폴더의 HANDBOOK.md를 따라 내 가상 규정집 PDF로 BM25 검색을 준비해 줘. 질문은 “생일 특별휴가는 사용 며칠 전까지 신청해야 하나요?”야. 먼저 전달할 청크와 페이지를 보여 주고, 설정한 로컬 모델로 한 번 답한 다음 인용문에서 기한이 어떤 행위에 걸리는지 확인해 줘.

## 새 폴더와 PDF 준비

`rag-lab`을 설치한 가상환경을 활성화한 뒤 시작합니다. PDF 의존성이 없다면 같은 환경에 설치물의 `requirements-pdf.lock`을 사용하세요.

```sh
pdf_lock=$(python -c 'from importlib.resources import files; print(files("rag_package")/"requirements-pdf.lock")')
python -m pip install --require-hashes -r "$pdf_lock"
rag-lab init --out handbook-practice
cd handbook-practice
rag-lab doctor
cp "/경로/내 규정집.pdf" documents/handbook.pdf
```

`doctor`의 PDF 항목에서 설치 버전 6.21.2를 확인합니다. `handbook-sources.json`에는 PDF의 상대경로와 문서 제목이 들어 있습니다. 다른 실제 문서를 넣을 때는 제목과 `synthetic` 표시를 문서에 맞게 수정하세요.

## 모델 호출 없이 검색 확인

```sh
question='생일 특별휴가는 사용 며칠 전까지 신청해야 하나요?'
rag-lab snapshot --sources handbook-sources.json --out .rag-runs/pdf
rag-lab build --snapshot .rag-runs/pdf --config fixed.json --out .rag-runs/bm25
rag-lab ask --run .rag-runs/bm25 --config fixed.json --question "$question" --out .rag-runs/preview
python -c 'import json; r=json.load(open(".rag-runs/preview/result.json")); print(r["status"]); [print(n, [p["page"] for p in c["pages"]], c["text"]) for n,c in enumerate(r["contexts"], 1)]'
```

snapshot이 ready인지 확인하세요. needs_review이면 PDF 텍스트 추출 상태부터 살펴보세요. fixed.json은 400자, 오버랩 80자, BM25 상위 5개, 문맥 예산 4,000자로 설정돼 있습니다. 출력한 문맥에서 신청 기한이 나오는 조항과 실제 PDF 페이지를 찾으세요.

## 로컬 모델로 한 번 답하기

`handbook-qwen-spec.json`에는 로컬 모델 별칭·주소·출처와 Thinking 설정이 있습니다. 이 실습의 별칭은 기존 Ollama에 등록된 `qwen3:4b`이며 Qwen3-4B-Thinking-2507의 Q4_K_M 변환본을 전제로 합니다. 다른 모델을 쓴다면 실제 별칭과 출처를 먼저 수정하세요. 실행 중인 로컬 Ollama의 모델 정보를 조회해 프로필을 만든 뒤 같은 검색 결과에 질문합니다.

```sh
rag-lab llm-configure --spec handbook-qwen-spec.json --out handbook-model.json --inspect-local
rag-lab doctor --llm-config handbook-model.json
rag-lab ask --run .rag-runs/bm25 --config handbook-local.json --question "$question" --out .rag-runs/answer --execute
python -c 'import json; r=json.load(open(".rag-runs/answer/result.json")); print(r["status"], r.get("error")); a=r.get("answer") or {}; print(a.get("answer")); [print([p["page"] for p in c["pages"]], c["quote"]) for c in a.get("citations",[])]'
```

handbook-local.json은 fixed.json과 같은 검색 설정에서 `llm_config`만 handbook-model.json으로 바꿉니다. PDF의 BD-03과 답변을 나란히 읽으세요. “사용 3영업일 전까지”가 **신청**을 수식하는지, 팀장 승인 완료에도 별도 시한을 부여했는지 확인합니다. 실패했다면 result.json의 status·failed_stage·error와 provider_result를 확인하세요.

## 유료 API 설정만 확인하기

```sh
rag-lab llm-configure --spec llm-spec-api.json --out handbook-api.json
rag-lab doctor --llm-config handbook-api.json
```

샘플 모델명은 미설정 표시이며 doctor가 종료 코드 3을 반환할 수 있습니다. 이 두 명령은 키를 읽거나 문서를 전송하지 않습니다. 실제 제공자를 선택할 때는 spec의 모델명과 키 환경변수 이름을 설정하고 RAG 설정의 `llm_config`를 생성한 API 프로필로 연결합니다. PDF snapshot과 BM25 build는 공유할 수 있습니다.

CLI 실행 기록은 위 result.json에서 읽습니다. 같은 문서로 UI에서 별도 실습하려면 `rag-lab serve --workspace . --sources handbook-sources.json --llm-config handbook-model.json`을 실행하고 터미널의 주소에서 문서·검색 미리보기를 선택하세요. UI는 자체 작업 기록을 사용합니다.

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
