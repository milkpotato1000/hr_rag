"""Synthetic, unapproved fixtures frozen before model calls; not company rules."""
from core import ATOM, GROUND, VERIFY, MATCH


def smokes():
    p = '입사 후 3개월이 지난 재직자는 연 1일 생일휴가를 신청할 수 있다. 수습 중인 직원은 대상에서 제외한다.'
    rows = [dict(id='smoke-atoms', role='atoms', units=[dict(id='s1', text=p)], schema=ATOM,
                 expected_quotes=['입사 후 3개월이 지난 재직자는 연 1일 생일휴가를 신청할 수 있다.', '수습 중인 직원은 대상에서 제외한다.'])]
    for label, claim in [('E', '수습 중인 직원은 생일휴가 대상에서 제외된다.'),
                         ('N', '생일휴가는 사용 3영업일 전까지 신청한다.'),
                         ('C', '수습 중인 직원도 생일휴가 대상이다.')]:
        rows.append(dict(id='smoke-' + label, role='verify', units=[dict(id='s1', text=p)],
                         claim=claim, schema=VERIFY, expected_label=label))
    rows.append(dict(id='smoke-match', role='match', units=[], schema=MATCH,
                     left='이월한 연차는 다음 해 3월 31일까지 사용한다.',
                     right='다음 해 3월 31일이 이월 연차의 사용 기한이다.', expected_equivalent=True))
    rows.append(dict(id='smoke-draft', role='ground', units=[dict(id='s1', text=p)], schema=GROUND,
                     question='생일휴가의 자격과 일수, 제외 대상은?', required_fragments=['3개월', '1일', '수습', '제외']))
    return rows


def judgements():
    groups = [
        ('숫자', '가상 fixture: 이월 가능한 연차는 최대 5일이다.',
         ['이월 가능한 연차는 최대 5일이다.', '이월 연차의 사용 기한은 3월 31일이다.', '이월 가능한 연차는 최대 10일이다.']),
        ('부정', '가상 fixture: 재택근무일에는 식대를 지급하지 않는다.',
         ['재택근무일에는 식대가 지급되지 않는다.', '사무실 출근일 식대는 1만 원이다.', '재택근무일에도 식대를 지급한다.']),
        ('조건·예외', '가상 fixture: 입사 후 3개월이 지난 재직자는 생일휴가 대상이지만 수습 중인 직원은 제외한다.',
         ['입사 후 3개월이 지났더라도 수습 중이면 생일휴가 대상에서 제외된다.', '수습 중인 직원의 급여는 90%다.', '입사 후 3개월이 지났으면 수습 중이어도 생일휴가 대상이다.']),
        ('기한', '가상 fixture: 출장 팀장 승인은 출발 5영업일 전에 받는다.',
         ['출장은 출발 5영업일 전에 팀장 승인을 받는다.', '출장비 정산 기한은 귀국 후 7일이다.', '출장 팀장 승인은 출발 후에 받아도 된다.']),
        ('다중 근거', '가상 fixture A: 생일휴가는 생일이 속한 달에 사용한다.\n가상 fixture B: 사용 3영업일 전까지 신청한다.',
         ['생일휴가는 생일이 속한 달에 사용하고 사용 3영업일 전까지 신청한다.', '생일휴가 승인자는 인사팀장이다.', '생일휴가는 생일이 속한 달의 다음 달에만 사용하고 당일 신청한다.']),
        ('근거 없음', '가상 fixture: 이 문서에는 재택 전기요금 지원 금액이 명시되어 있지 않다.',
         ['이 문서만으로 재택 전기요금 지원 금액을 알 수 없다.', '회사는 실제로 재택 전기요금 지원금을 지급하지 않는다.', '이 문서에는 재택 전기요금 지원 금액이 명시되어 있다.']),
    ]
    reasons = {'E': '전제가 주장을 직접 뒷받침합니다.', 'N': '전제에 해당 사실을 결정할 정보가 없습니다.', 'C': '전제와 주장이 같은 조건에서 양립할 수 없습니다.'}
    rows = []
    for group, premise, claims in groups:
        for label, claim in zip(['E', 'N', 'C'], claims):
            rows.append(dict(id='judge%02d' % (len(rows) + 1), category=group, premise=premise,
                             claim=claim, proposed_label=label, reason=reasons[label],
                             provenance='controlled synthetic fixture; not factual HR policy',
                             status='draft', reviewer='Codex', human_approval=None))
    return rows
