# 첫 설치에서 규정집 답변 모델 고르기

실습 폴더에서 generation-setup으로 모델을 지정하면 model.json과 이를 가리키는 search.json이 새 폴더에 함께 생성됩니다. 출력된 pipeline_preview 명령으로 같은 PDF와 질문의 모델·전송 주소를 확인하고 serve 명령으로 선택한 프로필을 학습 UI에 등록합니다. [설치된 안내서와 복사할 명령](../../../rag_package/resources/sample/HANDBOOK.md)

| 설치본에서 선택한 경로 | 확인한 내용 |
| --- | --- |
| Ollama · qwen3:4b | 소유한 시험 서버의 tags/show만 조회. 기록된 digest가 일치하면 실험 출처·옵션 적용. 같은 별칭에 다른 digest를 주면 HF 출처 unknown, Thinking 옵션 생략, 양자화는 서버가 보고한 값 |
| OpenAI Chat | 키 없는 환경에서 시험 모델명을 설정하고 HTTPS 전송 대상과 모델명 확인 |
| Anthropic Messages | 같은 PDF·질문으로 provider를 바꾸고 해당 HTTPS 전송 대상과 모델명 확인 |

새 venv에 wheel을 설치하고 소스 트리 밖에서 세 경로의 출력 명령을 실행했습니다. pipeline 미리보기와 저장 결과 재열기가 일치했고 serve가 선택 모델을 등록했습니다. UI 등록은 설치 서버의 bootstrap 응답으로 확인했습니다. 실제 모델 추론, 키 조회, 유료 호출은 0회입니다. API 모델의 계정 사용 가능 여부와 응답 품질은 이번 시험 범위 밖입니다. [모드별 관찰값](verified.json) · [실습 검증 코드](practice.py) · [회귀 결과](regression.log)
