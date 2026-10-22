# P005 E2E에서 발견한 생성 metadata 순서 문제

실제 모델 서비스를 정지/재시작한 뒤 Qwen digest·template·parameter 값은 같지만 /api/show의 parameters 문자열 행 순서가 바뀌었다.
P004 generation.check와 setup_generation의 문자열 비교가 이를 변경으로 오판했다. docs/verification/p005/live/retry-metadata-failure.json에 원본 실패를 보존했다.
계약의 모델/옵션은 변경하지 않는다. lock 원문을 유지하고 비교에서만 (parameter명, 값) 쌍을 정렬한다. 중복 stop도 유지하므로 값·개수·digest·template 변경은 계속 거부한다.
P005 실제 재시작/E2E 범위의 결함 수정으로 두 파일을 보수한다. P004 카드·기존 실패/검증 증거는 변경하지 않는다.
P005 보존 검증에서는 이 두 파일을 수정 예외로 명시하고 diff와 새 회귀 테스트를 남긴다. 모델 변경/기획 의미 변경은 없다.
