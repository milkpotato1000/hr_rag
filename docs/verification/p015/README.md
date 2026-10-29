# P015 완료 검증

현실적인 가상 HR 규정 Markdown 6개와 대응 PDF 6개를 `2. Document Chunking/data/source-v3/`에 작성했다.
기존 정책은 유지하고, 안내/답변 요령/평가 해설은 별도 authoring-notes로 옮겼다.
문서 분량을 늘리는 새 조건이나 인위적 페이지 나눔 없이 6문서/6페이지로 마무리했다.

## 검증 근거

| 조건 | 실제 근거 | 결과 |
| --- | --- | --- |
| C1 원문·정책 보존 | policy-preservation-audit.json, 새 단계 policy-inventory.json / policy-map.json | 31개 규정 문장, source-v2 비제목 51블록 전수 검토; 새 본문 34문장 출처 대응; 정책 충돌/신규 정책 없음 |
| C2 PDF·추출 | visual-review.json, rendered/ 6 PNG, final-source-validation.json | 모든 페이지 직접 확인; Markdown 전체와 PDF 추출의 비공백 문자/순서 일치; 제목/경고/메타/본문/페이지 번호 보존 |
| C3 정책 위치·인계 | 새 단계 section-map.json / legacy-reference-map.json / handoff-manifest.json | 조항 19개, 문서 길이·원문/캐시/canonical/page hash·정확 인용; 기존 15fact/14질문 새 위치 산출 |
| C4 독립 복사·회귀 | reproducibility.json, source-tests.stderr.txt, regression-retry.json, dependency-audit.json, baseline-inventory.json | 새 테스트 15개 + 기존 107개 × 2 통과; 복사 후 별도 Python+pypdf로 재수집/추출 일치; PDF 재작성 byte 동일; 기존 203개 추적 파일 보존 |
| C5 채택·완료 기록 | 최종 completion.json, P015 실행 로그 | ae8486d360a3963a3d21565266d9ef41c54568f2 정확 채택, 계약/큐/훅과 커밋된 근거 확인 |

`source-tests`는 독립 복사본에서 실행했다. 실제 폰트 없이도 전달된 PDF를 추출할 수 있는 외부 Python
기반 venv를 새로 만들고, pypdf 6.21.2 wheel을 기존 로컬 캐시에서 hash 검증 후 설치했다.
부모 단계의 runtime import, 가상환경·모델·색인 복사는 없다. PDF 재작성만 기존 번들 ReportLab과
AppleGothic 13.0d1e3을 재사용했다. 폰트 파일은 배포하지 않으며 환경 제약은 새 단계 README에 기록했다.

## 실패와 재검증

`failures.json`은 최초 실패를 보존한다.

- 초기 PDF 작성: 기존 AppleGothic에는 OS/2 권한 필드가 없어 작성기의 메타데이터 검사가 중단됐다.
  필드 부재를 null로 기록하고 권한을 추정하지 않도록 수정했다. 출력 공개 전 실패했으며,
  최종 PDF 6개 생성·전 페이지 렌더/직접 확인·재작성 hash 비교를 통과했다.
- 초기 회귀: 원본/후보 107개씩 실행 중 각각 11개 테스트가 sandbox의 localhost bind 제한으로 실패했다.
  `original-regression.*`, `langchain-regression.*`, `regression.json`을 보존했다.
  코드나 검사를 빼지 않고 로컬 소켓을 허용한 환경에서 재실행해 각각 107개 PASS를 확인했다.
- 추출 텍스트의 줄 끝 공백 때문에 최초 staged diff 검사가 경고했다. 기존 P006과 같은
  `.gitattributes` 규칙을 새 단계 추출 TXT에만 적용했다. parser 원문을 잘라 hash/offset을 바꾸지 않았다.
- 의도한 실패 검증: PDF 출력 덮어쓰기, 여섯 번째 편집 문서 누락, PDF/canonical/map 변조,
  페이지 누락/순서 오류, 인용 위치·hash 오류, 손상/암호화 PDF, 중복/NaN JSON, timeout을 거부했다.
  빈/이미지 페이지는 성공이 아닌 needs_review로 남긴다. 새 출력의 원자적 공개와 기존 산출물 보존을 확인했다.

초기 환경 탐색에서 번들 pypdf가 6.10.0인 것을 확인했으며 기존 lock(6.21.2)을 바꾸지 않았다.
fonttools 메타데이터 조회 실패는 해당 라이브러리가 불필요해 설치 없이 처리했다.

## 후속 전달과 한계

P007은 미착수 초안이다. 문서별 canonical 길이는 생일392, 연차461, 재택469, 복지245, 교육202,
출장192자다. 조항 후보19개와 각 위치·길이는 section-map에 있으며 원문에 없는 제목을 추가하지 않았다.
이 자료는 짧아서 800자 등 큰 설정의 차이가 없을 수 있다. P007은 source-v3의 실제 분량을 보고
실험 그리드/질문/정답/holdout·호출 예산을 확정해야 한다. 기존 source-v2의 다중 페이지 fixture는 그대로 남아 있다.

정책 대응은 Codex의 보존 대조이지 사람 승인 Ground Truth가 아니다. legacy-reference-map의 기존
14질문은 관찰된 tuning 자료이며 holdout이나 승인된 새 검색 qrels가 아니다.
이 작업에서 청킹 실험·검색·모델 호출·UI 변경·실제 Drive 접근·main 승격은 수행하지 않았다.

재현 명령은 새 단계 README와 reproducibility.json에 있다. canonical/page map 및 PDF 재작성 hash의
동일성만 주장하며 실행 시간 등 관측 metadata 전체의 byte 동일성을 주장하지 않는다.
