# 1. 검색 평가 기반

완료한 P001의 합성 HR 데이터와 검색 평가 CLI를 보존한 단계다. Python 3.9 이상과 표준 라이브러리만 필요하다.
P002의 단계 분리 요청에 따라 원래 구현 커밋 `4225bb1d6b9bd017a06e81125c4fce9ed1d7f227`의 제품 여섯 파일을 바이트 그대로 복사했다.
평가기·회귀 테스트와 합성 데이터 네 파일만 선별했고 가상환경·캐시·실행 결과는 가져오지 않았다.
제품 코드·데이터·테스트를 수정하지 않았고 이 단계의 README와 stage-manifest.json만 추가했다.
manifest의 source_path는 저장소 기준, destination_path는 이 단계 기준이며 copied_sha256은 최초 복사 원본 hash다.

이 폴더 하나를 별도 위치로 복사한 뒤 아래 명령을 실행할 수 있다. 저장소 루트 제품 코드나 다른 단계에 의존하지 않는다.

```sh
python3 -m unittest discover -s tests -v
python3 scripts/evaluate_retrieval.py --chunks data/synthetic/chunks.jsonl --queries data/synthetic/queries.jsonl --rankings data/synthetic/example_rankings.jsonl --k 5 10 20 --output /tmp/hr-rag-stage1-example.json
```

데이터 스키마·수작업 정답 설명은 `data/synthetic/README.md`에 있다. 수기 예시 순위는 검색 엔진 성능을 뜻하지 않는다.
이전 기준선은 보존하고 다음 단계 기능은 별도 폴더에서 개발한다. Git 하네스·기획·검증 기록은 원래 저장소 루트에서 관리한다.
