# 전달 예산이 다른 두 문맥에서 Qwen 4B는 어떻게 답했을까?

**질문** “생일 특별휴가는 사용 며칠 전까지 신청해야 하나요?” 합성 규정집 1쪽 BD-03에서 신청 기한은 **사용 3영업일 전까지**입니다. 팀장 승인은 함께 안내할 수 있는 보충 정보입니다.

고정 400자·겹침 80자, BM25 후보 20·최종 K=5, 리랭커 끔으로 S22의 두 검색 결과를 재사용했습니다. 예산이 4,000자일 때는 청크 5개(실제 2,000자), 400자일 때는 청크 1개(400자)를 전달했습니다. 두 입력에는 “사용 3영업일 전까지 휴가 시스템에서 신청”이 공통으로 들어 있습니다. 400자 입력의 마지막 글자는 ‘팀’이며 팀장 승인 의무까지 쓰인 문장은 4,000자 조건의 두 번째 청크에 있습니다. [검색 원문과 순위](../p032-s22/README.md)

## 실제 답과 인용

| 전달 예산 | 실제 문맥 | 모델이 쓴 답변 전문 | 인용한 검색 순위 |
| --- | --- | --- | --- |
| 4,000자 | 5개 · 2,000자 | 생일 특별휴가는 사용 3영업일 전까지 신청해야 합니다. | 1위와 2위 |
| 400자 | 1개 · 400자 | 사용 3영업일 전까지 | 1위 |

두 답 모두 날짜 단위 ‘영업일’, 일수 ‘3’, 방향과 기한 ‘사용 전까지’를 전달했고, 기술 상태는 모두 `answered`였습니다. 두 조건이 공통으로 인용한 1위 원문 [320, 720)은 “생일 특별휴가는 사용 3영업일 전까지 휴가 시스템에서 신청하고 팀”으로 끝납니다. 신청 기한은 여기서 직접 확인할 수 있습니다. 긴 문맥에서 추가로 인용한 2위 원문 [640, 1040)에는 “팀장의 승인을 받아야 한다”까지 있습니다. 세 인용 모두 실제 전달된 ID와 PDF 원문 위치를 대조했습니다. [전체 인용 ID·원문과 독립 대조](comparison.json)

팀장 승인은 두 답 모두 언급하지 않았습니다. 질문이 요구한 신청 기한은 두 답에 모두 있으므로 승인 생략을 필수 정보 누락으로 세지 않았습니다. 400자 답이 짧아졌지만 이 한 쌍에서 필수 답의 정확성 차이는 관찰되지 않았습니다. 각 조건 실제 생성 1회, 재시도 0회였고 두 실행 모두 완료 후 모델 해제와 소유 서버 종료를 확인했습니다.

## 설치본에서 같은 질문 비교하기

[설치 실습](../../../rag_package/resources/sample/HANDBOOK.md)의 실습 폴더에서 같은 PDF의 snapshot을 준비하고, 기존 로컬 Qwen 4B의 식별자와 생성 설정을 확인한 프로필을 두 조건에 공통으로 지정하세요. 실측에 사용한 프로필은 [모델 설정](../p032-s8/profile.json)에 있습니다. 아래 예시는 이 프로필을 실습 폴더에 `qwen-profile.json`으로 둔 경우입니다.

```sh
question='생일 특별휴가는 사용 며칠 전까지 신청해야 하나요?'
rag-lab snapshot --sources handbook-sources.json --out budget-snapshot
for budget in 4000 400; do
  dir="answer-budget-$budget"
  rag-lab pipeline-setup --llm-config qwen-profile.json --chunk-config chunk-fixed.json \
    --method bm25 --context-budget-chars "$budget" --question "$question" --out "$dir" || break
  rag-lab build --snapshot budget-snapshot --config "$dir/search.json" --out "$dir/index" || break
  rag-lab ask --run "$dir/index" --config "$dir/search.json" --question "$question" --out "$dir/preview" || break
done
```

각 preview/result.json의 contexts에서 페이지·원문·청크 ID를 대조하세요. 실제 생성은 해당 예산의 `rag-lab ask` 명령에 `--execute`를 추가하고 출력 폴더를 새 이름으로 지정합니다. 이번 실측은 두 요청을 순서대로 1회씩만 허용하고, 각 요청 후 모델 해제와 실험용 서버 종료를 확인하는 [실행 코드](experiment.py)를 사용했습니다.
