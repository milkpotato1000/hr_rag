# P031 사전 준비 검토 — 2026-11-28

현재 DRAFT이며 실행 인계가 아니다. 원래 사용자 목표의 설치·공개 모델 선택·선택적 LLM API 연결을 구현 가능한 준비 경로로 잇는다. P013/P014 평가기 보류와 P029 C4 미완료를 보존한다. P030 완료 커밋 및 최종 인터페이스 대조가 남았다.

## 확인한 입력과 호환성

네 모델의 고정 revision/file recipe는 p031-*-source-metadata.json에 있다. 공개 설정 JSON의 실제 bytes를 다시 읽어 크기·Git blob OID를 대조하고 p031-config-source-verification.json에 원문·SHA256을 기록했다. BGE-M3 조사 role embedding_dense는 준비 profile의 embedding에 매핑한다. 두 embedding의 차원·pooling·모듈, 두 reranker의 단일 logit classifier는 현재 runtime 검사 조건과 일치한다. 가중치·tokenizer load·추론·품질은 아직 검증하지 않았다.

읽은 dev 작업 소스의 SHA256은 다음과 같다. P030 작업 중 관찰값이므로 최종 커밋에서 다시 대조한다.

| 파일 | SHA256 |
| --- | --- |
| embedding.py | 785e51f8005e0c91189925177adefab3a4738e4bdc095e3b50a854c974afc945 |
| reranker.py | ea7ddb53a1878ddad2a8997be3a34df84c43149bc180c42ac2ba570a0d2a2fdd |
| workspace.py | f773e8aceee081631352ec6644d23217a5cd38a32d65a48883ceebae8f97871f |
| llm/config.py | 26138bf93acb5afff267a41e03b79e0cfb7e0bb22928ccc42845158255191516 |
| ui_registry.py | e4930a0f0a1b9d6aed8637effaa6d75b5ef664e9577cee739de6dc2de7449e12 |

runtime profile의 strict fields를 유지하고 source-provenance.json의 hash를 file_manifest에 넣는 경로를 선택했다. 모델 폴더 내 JSON sidecar는 기존 검사를 통과할 수 있지만 실제 생성 도구의 파일 집합·hash·load 연결은 dev가 검증한다. source-plan은 고정 recipe와 canonical hash를 함께 검증하며 hash 일치 자체를 임의 모델 신뢰로 사용하지 않는다. LFS 원본은 내용 SHA256, 일반 Git 파일은 blob 헤더를 포함한 OID로 확인한다.

## 완료 기준별 필요한 증거

| 기준 | dev에서 필요한 검증 |
| --- | --- |
| C1 준비 흐름 | 오프라인 catalog/plan, 명시 metadata·download·conversion, import/check, 새 profile 생성과 local/API/mixed LLM spec. 기본 preview의 외부 요청·키 읽기·추론0 |
| C2 무결성과 실패 | 변조 계획·파일 집합·OID/LFS·경로·부분 실패·중단·publication 실패; 실제 tiny tensor 변환의 key/dtype/shape/value 보존; tiny 생성 export를 기존 SDK worker로 읽기; 원본/runtime 제한 보존 |
| C3 설치 연결 | source-free wheel/sdist, core-only catalog/config/doctor, init 샘플 manifest, 생성 profile의 UI 등록·선택·미검증 표시, 최신 source에 대한 전체 회귀와 과거 artifact 보존, dev 원격 전달 |

현재 doctor는 retrieval config에서 generation/evaluation만 검사한다. 후속 계약에서 별도 role profile 입력과 v2 chunking 검사, 선택 의존성 상태를 명시했다. ready_for_offline과 실제 모델 검증을 구분하며, UI registry를 손으로 편집하는 절차를 학습 기본값으로 두지 않는다.

## 다음 검토 경계

P030 최종 C1~C3·설치/UI·회귀·원격 커밋을 확인한 뒤 위 소스와 새 config/등록 경로를 대조한다. 차이가 있으면 계약을 수정하고 READY SHA를 확정해 기존 dev에 전달한다. 이 검토만으로 다운로드나 평가기 실행을 시작하지 않는다. 실 사전학습 모델 E2E와 사용자가 지정할 Drive 문서 연결은 남은 최종 목표이며 fixture 완료로 대체하지 않는다.
