# -*- coding: utf-8 -*-
"""계획을 실행 기록으로 읽지 않았나. 두 자리에서 본다.

> 분류: 운영
> 작성: 오흥재 (Claude 세션) · 2026-09-15 21:10
> 근거: 실측 (2026-09-15 종합보고서 1차가 계획 문서의 배합을 사실로 실었다)
> 요지: 계획 문서에 경고를 박고, 보고서가 학습 설정을 단정하면 근거 표시를 요구한다
> 상태: 확정

## 무엇이 있었나

`docs/research/terrain-finetune-plan.md` 는 **계획**이다. 거기 설계된
「실패 5종을 각 `proportion 0.1`」 을 보고서가 **실행한 것처럼** 실었다.
실제로 돌린 것은 `gap` 하나 `0.1` 에 기존 험지 6종 `0.9` 다.

발행 전 검증이 **여덟 차례** 돌았는데 못 잡았다. astra 잘못이 아니다.
**계획 문서가 그렇게 적혀 있었으니 본문과 근거가 일치했다.** 일관성 검사는
한결같이 틀린 주장에 구조적으로 무력하다.

## 이 관문이 «못» 하는 일 (먼저 적는다)

**이 관문은 「5종이 아니라 gap 하나였다」를 알아낼 수 없다.** 저장소에 학습
실행 기록이 없기 때문이다. 없는 사실을 기계가 만들어 낼 수는 없다.

경로 검사도 소용없다. 보고서 코드는 계획 문서를 **가리키지 않는다.** 사람이
읽고 손으로 옮겨 적었다. 그래서 이 관문이 하는 일은 둘뿐이다.

1. **계획 문서에 경고를 박아 둔다** · 다음에 읽는 사람과 astra 가 보게
2. **보고서가 학습 설정을 단정하면 근거 표시를 요구한다** · 모르는 것이
   확실해 보이는 것으로 둔갑하지 못하게

진짜 해결은 `#428` 이 실행 기록을 채우고 보고서가 거기서 읽는 것이다.
그때까지 이 관문은 **불확실을 보이게 유지**하는 역할만 한다.
"""
import io
import os
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')

HERE = os.path.dirname(os.path.abspath(__file__))
LAB = os.path.dirname(HERE)

# 문서가 스스로 「나는 계획이다」라고 말하는 자리
_CLASS = re.compile(r'^> 분류:\s*(.+)$', re.M)
# 계획 문서가 달아야 하는 경고
_WARN = re.compile(r'실행 결과로 인용하지 말|실행되지 않았다|계획이다')

# 보고서가 «학습 설정» 을 말하고 있다는 신호
_TRAIN_TALK = re.compile(
    r'proportion|iteration|학습한 틈 폭|학습 배합|학습 지형에'
    r'|비중.{0,14}?0\.\d|학습했습니다|학습 반복')
# 그 절이 근거를 밝히는 방법
_PROV = re.compile(r'팀장 확인|미확인|확인됨|실측|코드에서 확인|#4\d\d|issues/\d+')

_TAG = re.compile(r'(?s)<(script|style)\b.*?</\1>|<[^>]+>')


def text_of(html):
    return re.sub(r'\s+', ' ', _TAG.sub(' ', html))


def plan_docs(root):
    """「분류: 계획」인 문서와, 경고가 달렸는지."""
    out = {}
    for dirpath, _d, files in os.walk(root):
        for f in sorted(files):
            if not f.endswith('.md'):
                continue
            p = os.path.join(dirpath, f)
            head = io.open(p, encoding='utf-8', errors='ignore').read()[:2500]
            m = _CLASS.search(head)
            if m and '계획' in m.group(1):
                out[os.path.relpath(p, root)] = bool(_WARN.search(head))
    return out


def sections(html):
    """보고서를 h2 경계로 자른다. (제목, 그 절의 글자)."""
    parts = re.split(r'(?i)<h2\b', html)
    out = []
    for chunk in parts[1:]:
        t = text_of('<h2' + chunk)
        title = t.strip()[:46]
        out.append((title, t))
    return out


def unsourced(html):
    """학습 설정을 말하면서 근거를 안 밝힌 절."""
    bad = []
    for title, t in sections(html):
        if not _TRAIN_TALK.search(t):
            continue
        if not _PROV.search(t):
            bad.append(title)
    return bad


def _selftest():
    """관문 자신을 먼저 시험한다. 실제로 틀렸던 모양을 넣는다."""
    import shutil
    import tempfile
    root = tempfile.mkdtemp(prefix='planrec-')
    bad = []
    try:
        # ── 계획 문서 찾기 ──────────────────────────────────────────
        os.makedirs(os.path.join(root, 'research'), exist_ok=True)
        io.open(os.path.join(root, 'research', 'a-plan.md'), 'w',
                encoding='utf-8').write(
                    '# 계획\n> 분류: 계획\n> 상태: 확정\n\n본문\n')
        io.open(os.path.join(root, 'research', 'b-plan.md'), 'w',
                encoding='utf-8').write(
                    '# 계획\n> 분류: 계획\n\n> 이 문서는 계획이다. '
                    '실행 결과로 인용하지 말 것.\n')
        io.open(os.path.join(root, 'research', 'c-run.md'), 'w',
                encoding='utf-8').write('# 실험\n> 분류: 실험\n\n본문\n')
        got = plan_docs(root)
        if set(os.path.basename(k) for k in got) != {'a-plan.md', 'b-plan.md'}:
            bad.append('계획 문서 찾기 (결과 %s)' % sorted(got))
        if got.get(os.path.join('research', 'a-plan.md')) is not False:
            bad.append('경고 없는 계획을 못 잡음')
        if got.get(os.path.join('research', 'b-plan.md')) is not True:
            bad.append('경고 있는 계획을 잡음 (오탐)')

        # ── 근거 없는 절 찾기 ───────────────────────────────────────
        #   ★ 실제로 틀렸던 문장을 그대로 넣는다.
        cases = [
            # 학습 설정을 말하는데 근거가 없다 -> 잡아야 한다
            ('<h2>03 레시피</h2><p>신규 5종의 비중을 각각 0.1로 넣었습니다.</p>',
             1),
            # 같은 말인데 근거가 있다 -> 통과
            ('<h2>03 레시피</h2><p class="prov">근거는 팀장 확인입니다.</p>'
             '<p>gap의 비중을 0.1로 넣었습니다.</p>', 0),
            # 이슈 번호로 밝혀도 통과
            ('<h2>03 레시피</h2><p>iteration 1,500회. 기록은 '
             '<a href="https://x/issues/428">#428</a> 대기.</p>', 0),
            # 학습 설정 이야기가 아니면 안 본다
            ('<h2>06 실패</h2><p>속도추종 기준은 0.25 m/s입니다.</p>', 0),
            # 태그 안의 글자를 본문으로 세지 않는다
            ('<h2>07 곡선</h2><p>그림입니다.</p>'
             '<img alt="proportion 0.1 도해">', 0),
        ]
        for i, (html, want) in enumerate(cases, 1):
            got_n = len(unsourced(html))
            if got_n != want:
                bad.append('절 검사 %d (기대 %d · 결과 %d)' % (i, want, got_n))

        if bad:
            print('  [!] 자기시험 실패:')
            for x in bad:
                print('      ' + x)
            return False
        print('  자기시험 %d/%d 통과 (계획 찾기 3 · 경고 2 · 절 검사 %d)'
              % (3 + 2 + len(cases), 3 + 2 + len(cases), len(cases)))
        return True
    finally:
        shutil.rmtree(root, ignore_errors=True)


def check(docs_root, report_html):
    ok = True

    plans = plan_docs(docs_root)
    missing = sorted(k for k, warned in plans.items() if not warned)
    print('  「분류: 계획」 문서 %d장 · 경고 없는 것 %d장'
          % (len(plans), len(missing)))
    for k in missing:
        print('     [X] %s · 「실행 결과로 인용하지 말 것」이 없습니다' % k)
        ok = False

    if os.path.isfile(report_html):
        html = io.open(report_html, encoding='utf-8', errors='ignore').read()
        bad = unsourced(html)
        print('  보고서에서 학습 설정을 근거 없이 단정한 절 %d곳' % len(bad))
        for t in bad:
            print('     [X] %s' % t)
            ok = False
    else:
        print('  [!] 보고서를 못 찾음: %s' % report_html)

    return ok


if __name__ == '__main__':
    if not _selftest():
        raise SystemExit(1)
    raise SystemExit(0 if check(
        os.path.join(LAB, 'docs'),
        os.path.join(LAB, 'sim', 'eval', 'results', 'report-v1',
                     'report-v1.html')) else 1)
