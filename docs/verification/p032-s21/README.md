# 공개 dev에서 시작한 첫 PDF 검색

macOS의 새 폴더에서 공개 GitHub dev를 익명 HTTPS로 복제하고 Python 3.13.15로 README의 첫 실습을 실행했습니다. 사용자 Git 설정과 인증 도우미를 제외했고, 비어 있는 pip 캐시와 공개 PyPI를 사용했습니다. 빌드와 실습 환경을 각각 새로 만들고 기존 해시 잠금 파일로 빌드 도구 네 개와 pypdf를 내려받았습니다. 설치 출처 기록의 wheel 경로 및 SHA-256도 빌드 산출물과 일치했습니다. [첫 검증](public.json) · [README 포함 최종 대조](verified.json)

질문은 **“생일 특별휴가는 사용 며칠 전까지 신청해야 하나요?”**였습니다. BM25가 전달한 다섯 청크 중 2위에서 PDF 1쪽 BD-03의 다음 문장을 확인했습니다.

> 생일 특별휴가는 사용 3영업일 전까지 휴가 시스템에서 신청하고 팀장의 승인을 받아야 한다.

S20의 로컬 설치와 질문·PDF 해시·검색 설정이 같았고, 전달한 다섯 청크의 순서·본문·페이지도 일치했습니다. 이번 관찰은 검색 결과이며 생성 호출은 0회입니다. [S20 대조 자료](../p032-s20/verified.json)

## 직접 재현

Git과 Python 3.11 이상이 있는 macOS/Linux에서, 새 폴더 이름을 사용하세요. 아래 명령은 이 검증에서 사용한 공개 소스 버전을 지정합니다.

```sh
git clone --branch dev https://github.com/milkpotato1000/hr_rag.git rag-lab-source
cd rag-lab-source
git checkout --detach 36557ec9964ce7c61eaf8311111ab64848e04b25
python3 scripts/first_handbook.py --out ../rag-lab-first
```

설치 및 검색 상태는 생성된 폴더의 `first-run.json`, 전달 청크 전문은 `practice/evidence/result.json`에서 확인하세요. 익명 Git·빈 캐시·공개 인덱스를 강제한 검증 환경은 [검증 스크립트](verify.py)에 있습니다.
