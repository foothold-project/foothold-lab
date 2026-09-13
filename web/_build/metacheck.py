# -*- coding: utf-8 -*-
"""문서 메타데이터 관문. 신원 없는 문서를 웹에 내보내지 않는다.

  왜 (2026-08-25 실측):
    35개 문서 중 «작성자» 가 있는 것은 6개(17%)뿐이었다. 연구 문서 19개 중
    1개, 루트 문서 10개는 전부 없었다. 누가 무엇을 근거로 썼는지 모르면
    나중에 대조할 수 없고, 틀린 것을 찾아도 물어볼 사람을 모른다.

    «요지» 도 37%뿐이라 주간 다이제스트·큐레이션의 자동 초안이 반쪽이었다.

  표준 (문서 머리의 인용 블록)
      > 분류: 회의록 | 리서치 | 실험 | 계획 | 결정 | 운영 | 현장 | 가이드
      > 작성: 이름 · YYYY-MM-DD HH:MM
      > 근거: 전사 N세그먼트 | 공식 문서 | 실측 | 본인 노트 | 미확인
      > 요지: 한 줄

  이 파일은 **원본 md** 를 본다. 빌드 산출물(html)이 아니다.
  산출물만 고치면 다음 빌드에 되살아나기 때문이다.

  단계: build [3.4] (문체 검사 바로 앞)
"""
import io
import os
import re
import sys

# 분류 어휘. 여기 없는 말을 쓰면 오타로 본다.
KINDS = ('회의록', '리서치', '실험', '계획', '결정', '운영', '현장', '가이드')

FIELD = {
    '분류': re.compile(r'^>\s*분류\s*:\s*(\S+)', re.M),
    '작성': re.compile(r'^>\s*작성\s*:\s*(.+)$', re.M),
    '근거': re.compile(r'^>\s*근거\s*:\s*(.+)$', re.M),
    '요지': re.compile(r'^>\s*요지\s*:\s*(.+)$', re.M),
    # ★ 2026-08-27 추가. 표준은 「다섯 줄」인데 관문은 네 줄만 봤다.
    #   그래서 상태 없는 문서가 통과해 웹으로 나갔다.
    '상태': re.compile(r'^>\s*상태\s*:\s*(\S+)', re.M),
}
STATES = ('초안', '검토중', '확정', '대기', '폐기')

# ★ 2026-08-28 신설: 판(버전).
#
#   왜 필요한가. 규칙이 바뀌었는데 문서가 그대로면 «틀린 정본»이 된다.
#   그리고 틀린 정본은 없느니만 못하다. 팀원이 그대로 따르기 때문이다.
#   그런데 지금은 **바뀐 것을 알 방법이 없다.** 8/9 에 COLLAB 을 본 사람과
#   오늘 본 사람이 같은 문서를 봤는지 구분이 안 된다.
#
#   형식을 번호로 정한 근거. `generalization-benchmark-10-terrains.md` 와
#   `benchmark-repro-protocol.md` 는 **이미 본문에서 v1/v2 를 쓰고 있었다.**
#   («v2 재검», «v1 대비») 팀이 판을 필요로 했는데 표준이 없어 본문에 흩뿌린 것이다.
#   날짜만 쓰면 「몇 번 바뀌었나」가 안 보여 발전 과정이 안 남는다.
#
#   올리는 기준
#     major (v1 -> v2)   결정이 바뀌어 기존 서술이 뒤집힌다
#     minor (v1.0 -> v1.1) 보강·추가. 기존 서술은 그대로 유효하다
#     오타·서식은 올리지 않는다
#
#   면제: 기록물. 회의록·다이제스트·검증 로그는 그때의 사실이라 고치지 않는다.
#   고치지 않으니 판도 이력도 없다.
VER = re.compile(r'^>\s*판\s*:\s*v(\d+)\.(\d+)\s*$', re.M)
VER_HIST = '## 판 이력'
RECORD_PREFIX = ('meetings/', 'digest/')
# 날짜 공지는 그날 보낸 것이라 나중에 고치지 않는다 (팀장 9/2 · 기록물)
RECORD_RE = re.compile(r'notices/\d{4}-\d{2}-\d{2}\.md$')
RECORD_FILES = ('FIELD-CHECK-0813.md', 'VERIFIED.md', 'DRAFT-0813-사전문의.md',
                'report-web.md', '20260826-27-design-session.md',
                'rough-terrain-study-plan.md', 'terrain-rl-study-plan-0818.md')


def is_record(rel):
    """기록물인가. 기록물은 판을 요구하지 않는다."""
    r = rel.replace('\\', '/')
    return (RECORD_RE.search(r) is not None
            or any(x in r for x in RECORD_PREFIX)
            or os.path.basename(r) in RECORD_FILES)
# 작성 시각. 날짜만도 통과하지만 시각까지 있으면 「언제 쓴 글인지」가 분 단위로 남는다.
#   허용: 이름 · 2026-08-27          이름 · 2026-08-27 09:41   (팀장 확정 2026-08-27)
# ★ 2026-08-28 팀장 지적: 「연구 문서마다 발행일 날짜 시간도 하라고 했는데
#   하나도 안 지켜졌다」. 실측 27개 중 시각까지 있는 것은 4개(14%)였다.
#
#   원인은 사람이 아니라 이 정규식이다. 시각 부분이 `(?: ...)?` 로 **선택**이었다.
#   「시각까지 쓰면 좋다」고 문서에는 적혀 있었지만 관문은 한 번도 요구하지 않았다.
#   문서에 적는 것과 강제하는 것이 따로 놀면, 적힌 쪽은 지켜지지 않는다.
#   시각을 **필수**로 바꾼다. 초는 여전히 선택이다.
WRITER = re.compile(r'^\s*(.+?)\s*[·]\s*(20\d{2}-\d{2}-\d{2} \d{2}:\d{2}(?::\d{2})?)\s*$')

# 관문 대상이 아닌 것: 목차·안내 파일
SKIP = {'README.md', 'CONTRIBUTING.md'}


def check_one(path):
    """반환: (ok, [문제 문장])"""
    t = io.open(path, encoding='utf-8', errors='replace').read()
    head = t[:1400]                       # 머리에 있어야 한다. 본문 뒤는 안 본다
    bad = []

    for name, pat in FIELD.items():
        m = pat.search(head)
        if not m:
            bad.append('«%s» 줄이 없습니다' % name)
            continue
        val = m.group(1).strip()
        if not val:
            bad.append('«%s» 가 비었습니다' % name)
            continue
        if name == '분류' and val not in KINDS:
            bad.append('«분류: %s» 는 정해진 말이 아닙니다 (%s)' % (val, ' · '.join(KINDS)))
        if name == '작성' and not WRITER.match(val):
            bad.append('«작성» 은 «이름 · YYYY-MM-DD HH:MM» 형식이어야 합니다 (시각 필수) (지금: %s)' % val[:40])

    # 판 검사. 기록물은 면제한다 (그때의 사실이라 고치지 않으므로 판이 없다).
    if not is_record(path):
        if not VER.search(head):
            bad.append('«판» 줄이 없습니다. 살아 있는 문서는 «> 판: v1.0» 형식으로 판을 답니다')
        elif VER_HIST not in t:
            bad.append('«판» 은 있는데 «%s» 표가 없습니다. 판이 올라간 내력을 남겨야 '
                       '무엇이 언제 바뀌었는지 다음 사람이 압니다' % VER_HIST)

    return (not bad), bad


def grandfathered(here=None):
    """표준 이전 문서 목록. 여기 있는 것은 경고만 하고 배포를 막지 않는다.

    35개 전부가 미비한 상태에서 곧바로 차단하면 빌드가 영원히 안 돈다.
    새 문서는 오늘부터 막고, 기존은 이 목록을 줄여 가며 갚는다.
    목록의 줄 수가 «남은 일» 의 크기다.
    """
    here = here or os.path.dirname(os.path.abspath(__file__))
    p = os.path.join(here, 'metacheck_grandfather.txt')
    if not os.path.exists(p):
        return set()
    out = set()
    for line in io.open(p, encoding='utf-8'):
        line = line.strip()
        if line and not line.startswith('#'):
            out.add(line)
    return out


def main(lab_docs, verbose=True):
    """lab_docs: foothold-lab/docs 경로"""
    if not os.path.isdir(lab_docs):
        print('  [!] 문서 폴더 없음: %s' % lab_docs)
        return False

    targets = []
    for root, dirs, files in os.walk(lab_docs):
        # ★ 2026-08-27: notices 를 빼 놨더니 팀 공지가 표준 검사를 한 번도 안 받았고,
        #   결정과 어긋난 내용(네 줄 · 10MB · 개인 구역)이 그대로 팀에 나갔다.
        #   검사기가 안 보는 곳은 반드시 썩는다. ops 는 내부 메모라 계속 제외한다.
        dirs[:] = [d for d in dirs if d not in ('assets', 'ops')]
        for f in sorted(files):
            if f.endswith('.md') and f not in SKIP:
                targets.append(os.path.join(root, f))

    old = grandfathered()
    blocking, warning = [], []
    for p in targets:
        ok, problems = check_one(p)
        if ok:
            continue
        rel = os.path.relpath(p, lab_docs).replace(os.sep, '/')
        (warning if rel in old else blocking).append((rel, problems))

    n = len(targets)
    print('  문서 %d개 · 갖춤 %d · 유예 %d · 미비 %d'
          % (n, n - len(blocking) - len(warning), len(warning), len(blocking)))

    if warning:
        print('  (유예 %d개는 표준 이전 문서입니다. metacheck_grandfather.txt 에서 줄여갑니다)'
              % len(warning))

    if not blocking:
        return True

    print('  🔴 새 문서인데 메타데이터가 없습니다 %d개' % len(blocking))
    for f, problems in blocking[:14]:
        print('     %-46s %s' % (f, problems[0]))
        for extra in problems[1:3]:
            print('     %-46s %s' % ('', extra))
    if len(blocking) > 14:
        print('     ... 외 %d개' % (len(blocking) - 14))
    print()
    print('     문서 머리에 이 다섯 줄을 넣으세요')
    print('       > 분류: %s' % ' | '.join(KINDS))
    print('       > 작성: 이름 · YYYY-MM-DD HH:MM')
    print('       > 근거: 전사 N세그먼트 | 공식 문서 | 실측 | 본인 노트 | 미확인')
    print('       > 요지: 한 줄')
    return False


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    d = sys.argv[1] if len(sys.argv) > 1 else '.'
    sys.exit(0 if main(d) else 1)
