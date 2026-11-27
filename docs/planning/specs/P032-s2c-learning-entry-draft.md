# P032 S2c 학습 시작점과 설치 안내 정리 초안

2026-11-28 DRAFT. S2b recovery001의40문항 결과는 확인했으나 dev의 보고서·UI·학습 안내·원격 마감은 진행 중이다. 해당 완료 commit과 변경 파일을 검토한 뒤 준비 완료 여부를 정한다. 현재 S2b 계약에 자동 추가되는 범위가 아니다.

## 사용자에게 필요한 결과

사용자는 Codex 또는 Claude Code로 독립 실습 폴더를 만들고 문서→모델→청킹→검색→선택 리랭커→답변으로 진행할 수 있어야 한다. 지금 구현된 CLI·설정·저장 결과가 어디에 있는지와 실제 검증된 범위가 학습 시작점에서 명확해야 한다. 초기 P024 설계 JSON이나 하네스 내부 작업 순서가 일반 학습자의 첫 실행 경로가 되지 않도록 정리한다.

## 검토한 현재 혼동

[전체 목표 감사](../reviews/P032-package-completion-gap-audit-20261128.md)에 더해 현재 `docs/learning/rag-package/README.md`를 읽었다. 상단에는 실행 불가 JSON과 초기 P024/BM25 실습을 중심으로 설명하고, 현재 설치 시작 링크는 맨 아래에 있다. S1 실제 결과 링크와 과거 미검증 설명이 함께 있다. 일반 사용자용 답변 흐름에 보류된 평가기가 필수 후속 단계처럼 보일 수 있다. `rag_package/resources/sample/START_HERE.md`는 실제 init 실행 경로를 제공하므로 이 경로와 학습 문서가 일치해야 한다.

`rag_package/workspace.py`는 resources/manifest.json의 hash로 복사 파일을 검증한다. 따라서 START_HERE 수정은 문서 파일뿐 아니라 resource manifest와 새 배포물/설치 재현을 함께 확인해야 한다. 실제 검색에 사용한 이전 wheel을 덮어쓰거나 새 문서 wheel로 실행한 것으로 소급 표시하지 않는다.

## 정리 범위 후보

- 학습 README의 첫 경로를 현재 설치→init→START_HERE의 작동하는 preview와 최신 저장 비교 읽기로 구성한다. 일반 실습 경로와 저장소 기여자의 plan/dev 규칙을 구분하되 기존 AGENTS/CLAUDE·보류·채택 규칙은 변경하지 않는다.
- 로컬 공개 LLM / 선택 유료 API를 동등한 설정 경로로 설명한다. 실행 가능한 spec→llm-configure→doctor와 실제 호출 선택을 연결하고, P024 example_only 자료는 명시적인 역사적 설계 참고로 남긴다. 코딩 도구 구독과 LLM API 자격을 혼동하지 않는다.
- S1 검색5행·리랭커3행, S2a 모델0 준비, S2b 첫 실패와 복구 후4방식 실제40검색을 서로 연결한다. 실제 LLM 청킹/범용 생성/API·Drive 실연결은 여전히 미검증이며 평가기는 보류다. 작은 학습 세트 결과를 일반 성능으로 확대하지 않는다.
- UI·models-and-support·install-current·model-chunking·experiments 중 현재 범위를 잘못 표현한 문장을 완료 증거에 맞춰 수정한다. 원래 단계의 검증 이력은 보존하고 “당시 범위/이후 결과”를 구분한다. 같은 안내를 여러 페이지에 복제하기보다 시작점과 근거 링크를 정한다.
- init의 START_HERE도 현재 지원 기능·실행권한·설치/SDK 점검의 한계를 맞춘다. doctor의 metadata 검사만으로 모든 설치 파일과 실제 import가 검증됐다고 표현하지 않는다. 실제 복구 실험의 추가 검증은 별도 evidence 절차이며 doctor 기능을 새로 구현하는 범위가 아니다.
- Codex와 Claude Code 요청 예시는 같은 독립 폴더의 CLI/설정을 사용하게 하고 특정 개인 절대경로나 `hr_rag_dev` 폴더가 있어야만 실행되는 지시를 없앤다. 로컬에 있는 규칙을 존중하되 init이 하네스를 설치한다고 쓰지 않는다. 두 제품 UI 실사용 검증을 예시 프롬프트 존재만으로 주장하지 않는다.

## 검증과 완료 후보

제품 알고리즘·HTTP adapter·모델 profile/default·허용 상한·기존 GT/평가 정책은 바꾸지 않는다. 모델·가중치 다운로드·LLM/API/Ollama/Drive·평가기 호출0, 실제 재실험0이다. 문서/번들 resource만 바꾼 경우 관련 resource manifest와 새 wheel/sdist를 만들고 기존 실제 실험 배포물은 보존한다. 별도 새 설치 위치에서 source 없는 cwd·init·문서의 core-only preview 명령을 실행하여 명령/경로/placeholder/예상 상태를 검증한다. 이미 준비된 build 도구를 재사용하며 SDK 재설치나 모델 환경 조작을 끼워 넣지 않는다.

Markdown 상대 링크·문서 내 명령과 CLI help의 일치, 시작점부터 두 모드 설정의 도달성, 학습 예시의 실제 숫자/분모/한계, resource hash·새 배포물 hash·설치 경로를 기록한다. 모델 없는 명령 검증으로 실제 답변 생성 성공을 주장하지 않는다. 필요한 관련 검사만 실행하며 문서 수정 때문에 이미 끝난 실제40검색을 반복하지 않는다.

새 문서의 구현 commit·배포물 hash·독립 설치 기록과 정상 personal/dev 전달이 완료 증거다. main/PyPI 승격은 포함하지 않는다. P032 전체 완료가 아니며 실제 생성/LLM 청킹/Drive 선택과 P029 C4는 남는다. S2b 마감 문서에서 이미 해결한 항목은 중복 편집하지 않고 차이만 반영한다.
