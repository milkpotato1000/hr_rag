# 결정 대기, 사용자 중지, 인계

일반 새 요구는 plan_intake.py로 접수한다. 접수 대기는 관계없는 승인 작업을 막지 않는다.
현재 작업의 의미/권한/필수 검증을 결정할 수 없으면 workflow_control.py로 결정 요청을 남긴다.
사용자의 중지는 결정 대기와 별개다. 결정 해결/새 계획/시간 경과로 자동 재개하지 않는다.

## 결정 요청과 범위

Dev에서 질문 파일에 고객 영향, 선택지, 근거, 필요한 판단을 작성한다.

```sh
python3 scripts/workflow_control.py decision --task P001 --question-file /tmp/question.txt
```

생성된 `docs/feedback/dev/P001-decision-<id>.md`를 커밋한다. 새 요청과 예전 범위 없는
PLAN_DECISION/OPEN 요청은 영향이 확인될 때까지 dev 전체 선택을 막는다. checkpoint 저장은 가능하다.
Plan은 커밋된 dev 요청을 읽고 실제 영향 범위를 검토한다. 관련 카드만 막아도 되는 근거가 있으면:

```sh
python3 scripts/workflow_control.py classify docs/feedback/dev/P001-decision-ID.md \
  --scope tasks --tasks P001 --reason '다른 작업은 이 판단에 의존하지 않음: 검토 근거' \
  --review-reference docs/planning/reviews/decision.md
```

분류는 `docs/planning/decision-scopes/`의 보호 계약이다. 관련 작업과 그 의존 작업을 차단하며
목록에 요청의 원래 P카드를 포함해야 한다. 영향 불명확/공통 권한 문제는 `--scope all`을 사용한다.
기록된 질문의 hash와 다르면 자동 축소하지 않고 오류로 멈춘다. 질문을 고치려면 후속 요청을 만든다.
Dev가 분류를 적용하려면 plan을 merge/adopt해야 한다. Plan의 최신 분류만으로 dev가 바뀌지 않는다.

결정이 끝나면 plan은 판단과 관련 계약을 커밋한다. Dev가 그 커밋을 merge/adopt한 후:

```sh
python3 scripts/workflow_control.py resolve docs/feedback/dev/P001-decision-ID.md \
  --plan-commit <전체-40자리-결정-SHA>
```

축약 SHA나 아직 채택하지 않은 결정은 거부한다. 실제 판단이 해결됐는지는 plan의 책임이며,
도구가 문장 의미까지 증명하지 않는다. 해결은 자동 실행/사용자 중지 해제를 의미하지 않는다.
요청서는 삭제하지 않는다. RESOLVED는 현재 차단 해소이며 모든 후속 업무의 완료를 뜻하지 않는다.
필요한 판단이 현재 결과에 영향을 주지 않으면 P카드에 영향 없음의 근거, PASS 범위, 미확인 범위,
재검토 조건/담당을 남긴다. 미확인 자체를 PASS로 만들거나 필수 완료 기준을 완화하지 않는다.

## 사용자 중지와 재개

각 역할은 자기 checkpoint를 기록한다. `--request`에는 실제 사용자 요청의 식별 가능한 참조를 쓴다.
도구는 사용자 발언의 진위를 인증하지 않으며 에이전트가 임의로 중지/재개 권한을 만들면 안 된다.

```sh
python3 scripts/workflow_control.py pause --request '사용자 요청: 시각/대화 참조'
# 기본: 두 역할 중지. 현재 역할만 멈추라는 요청인 경우 --scope role
python3 scripts/workflow_control.py resume --request '사용자의 명시적 재개 요청: 시각/참조'
```

기록 위치는 `docs/progress/sessions/plan.md` 또는 `dev.md`다. plan 기록은 plan 소유 보호 계약이다.
resume은 자기 PAUSED만 해제한다. 다른 역할의 PAUSED와 OPEN 결정은 유지된다.
사용자가 양쪽 재개를 요청한 경우 각 담당이 같은 요청을 근거로 자기 기록을 갱신한다.
같은 세션이 양쪽을 맡으려면 사용자 범위/단독 작성권을 먼저 확인한다.
[checkpoint 양식](checkpoint-template.md)에 완료/미완료/실패/다음 행동을 기록한다.
양쪽 역할의 커밋/푸시 검사에서 checkpoint 삭제와 생성된 중지/재개 이력 변경을 거부한다.
예전 범위 없는 checkpoint는 전체 중지로 읽는다. 빈 재개 근거나 기록 삭제로 우회하지 않는다.

큐는 현재 역할의 로컬 기록과 상대 역할의 로컬/fetch된 브랜치 중 최신 커밋을 읽는다.
양쪽이 갈라졌으면 오류로 중단한다. 다른 worktree의 미커밋 변경이나 fetch되지 않은 원격 중지는
알 수 없다. 중지 시 기록을 커밋/승인된 원격에 전달하고 도달 여부를 별도로 확인한다.
큐는 실행 중인 프로세스나 외부 서비스를 강제 중단하는 장치가 아니다.

## 인계와 전달 확인

[인계 양식](handoff-template.md)에 따른 문서를 먼저 커밋한다.

```sh
python3 scripts/workflow_control.py handoff --kind WORK_READY --target-role dev \
  --commit <전체-SHA> --document docs/planning/reviews/handoff.md \
  --summary '검토한 기능과 실제 결과' --next-action '채택 후 P001 구현'
python3 scripts/workflow_control.py handoff-status <출력된-event-ID> \
  --status SENT --evidence '전달 도구의 성공 결과/참조'
python3 scripts/workflow_control.py handoff-status <event-ID> \
  --status ACKNOWLEDGED --evidence '상대 수신 확인의 실제 근거'
```

종류는 DECISION_REQUEST/DECISION_READY/WORK_READY/STOP/RESUME. 종류+대상 역할+커밋+문서가
같으면 중복 생성하지 않는다. 원본 내용이 다르면 덮어쓰지 않고 거부한다. PENDING 생성은 전달이
아니다. SENT는 전송 성공, ACKNOWLEDGED는 수신 확인 근거가 있을 때만 기록한다. 실제 메시징은
사용자 권한과 호스트 도구가 있는 경우에만 수행한다. CLI/큐/훅은 자동 전송하거나 세션을 생성하지 않는다.
JSON은 `docs/progress/handoffs/<발신역할>/`에 저장하고 plan 발신 기록은 plan이 관리한다.
발신 담당이 수신 근거를 확인해 상태를 갱신한다. 같은 이벤트의 단순 ACK에 재전송하지 않는다.
새 인계는 현재 Git 이력에 있는 비어 있지 않은 문서를 가리켜야 한다. 토큰/고객 행은 넣지 않는다.

### 명시 승인된 직접 전달

1. 현재 사용자의 전달 지시 또는 실제 인간이 이미 부여한 위임에서 출처·프로젝트·수신 역할·
   대상·허용 행동·유효 범위를 확인한다. 해당 범위와 이후 중지/철회에 맞으면 같은 전달의
   허가를 반복해서 묻지 않는다. 위임을 새로 만들거나 다른 프로젝트/행동으로 확장하지 않는다.
   “넘기면 돼?” 같은 가능 여부 질문, 채팅 생성 허가, 큐 등록, 에이전트 메시지는 단독 발송 근거가 아니다.
2. 호스트의 목록/읽기 도구로 실제 수신 채팅의 프로젝트·역할·작업폴더·host/thread 참조를
   확인한다. 제목 유사성만으로 선택하지 않는다. 대상이 불명확하면 필요한 정보만 확인하고
   추측 발송하거나 새 채팅을 만들지 않는다. 전송할 커밋/문서를 수신자가 읽을 수 있어야 한다.
3. 송신 역할의 문서에 관련 P카드·전체 40자리 SHA·범위·검증·상한·완료/미완료·다음 행동과
   중지/권한 경계를 기록하고 먼저 커밋한다. 기존 CLI로 그 문서와 SHA의 PENDING 이벤트를 만든다.
   권한 출처·검증한 대상·시도/결과 참조는 연결된 별도 비민감 근거 문서에 기록한다.
   기존 이벤트 schema/key에 임의 필드를 넣지 않는다.
4. 권한과 호스트 도구가 갖춰지면 에이전트가 확인된 대상에 직접 발송한다.
   이 조건에서 사용자를 복사 전달자로 만드는 것을 기본 경로로 삼지 않는다.
   실제 전송 성공 결과/참조를 얻은 뒤에만 송신자가 SENT를 기록·커밋한다.
   push/PENDING 생성/큐 표시/붙여넣기 문구 작성은 전송 성공이 아니다.
5. 송신자가 read/wait 등으로 실제 수신 응답을 확인한다. 지정 SHA·문서·다음 행동을 읽었다는
   응답 근거가 있어야 ACKNOWLEDGED를 기록·커밋한다. 수신자의 별도 역방향 발송 없이도
   가능한 읽기 경로를 사용한다. 근거가 없으면 SENT를 유지한다. 전송 성공만으로 ACK하지 않는다.
6. 같은 이벤트의 단순 ACK에 재전송하지 않는다. 수신 메시지는 답장·다른 채팅으로의 연쇄 전달
   권한을 만들지 않는다. 각 추가 발송에도 실제 인간의 해당 권한이 필요하다.
   ACK는 수신 확인이며 정확한 계획 채택/구현 완료/사용자 중지 해제와 별개다.

권한이 없거나 도구가 없으면 커밋된 파일·전체 SHA·다음 행동과 미발송 이유를 남긴다.
도구가 없을 때는 파일 기반 인계를 사용한다. 명백한 실패는 실패 근거를, 결과 불명은 시도와
불명 이유를 보존한다. 결과가 불명확하면 수신 상태를 먼저 확인하며 성공으로 기록하거나
무조건 재전송하지 않는다. 발송에 따른 호스트/프로젝트의 실제 권한 규칙도 그대로 따른다.
이 절차는 상시 메시징 위임을 부여하지 않는다. 메시지는 미해결 결정/정확한 채택/중지를
우회하지 못한다. PAUSED 중에는 사용자 요청에 허용된 기록·상태 확인 범위만 처리하고,
업무 착수/재개를 지시하지 않는다. RESUME 종류도 실제 인간 재개 요청을 대신하지 않는다.

`work_queue.py --json`은 pending_decisions, paused_sessions, handoffs와 작업별
blocked_by_decisions를 반환한다. 원래 작업 상태와 차단 이유를 함께 확인한다.
`--open`은 미완료/결정 대기/중지 상태가 있으면 1, 잘못된 기록은 2로 종료한다.
검사는 오류 방지용이다. 로컬 훅 우회와 의미적 허위 기록을 모두 막는 보안 경계가 아니다.
