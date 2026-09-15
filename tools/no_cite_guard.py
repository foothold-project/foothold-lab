# -*- coding: utf-8 -*-
"""「인용하지 말 것」 표시가 붙은 자료를 보고서가 읽으면 세운다.

> 분류: 운영
> 작성: 오흥재 (Claude 세션) · 2026-09-15 01:10
> 근거: 실측 (내가 실제로 그 폴더를 읽어 보고서에 실었다)
> 요지: 결과 폴더의 경고 표시를 기계가 읽고, 보고서 코드가 그 폴더를 가리키면 막는다
> 상태: 확정

## 왜

`sim/eval/results/20260910-difficulty-sweep/` 첫 줄에 이렇게 적혀 있다.

    [규격 1 · 결함] 이 폴더의 gap 성적은 ... 보행 능력을 잰 것이 아닙니다.

폴더 안에 `_결함규격_읽어주세요.md` 도 따로 있다. **그런데 나는 CSV 만 읽고
보고서 05절 표와 00절 한 줄을 그것으로 만들었다.** 경고가 거기 있었는데
안 읽었다. 사람에게 「읽어라」고 적어 둔 것은 기계가 안 읽는다.

## 무엇을 하나

경고를 **기계가 읽는 표시**로 바꾼다. 결과 폴더에 `NO_CITE` 파일을 두거나
README 첫 줄에 「인용하지 말 것」 류의 말이 있으면, 그 폴더를 **보고서 코드가
경로로 가리키는지** 훑어 막는다.

문자열로 「이 폴더 쓰지 마」를 찾지 않는다. **폴더 쪽에 표시가 있고, 코드 쪽에
그 폴더 이름이 있으면** 잡는다. 그래서 다음에 다른 폴더가 상해도 같이 잡힌다.
"""
import io
import os
import re
import sys

sys.stdout.reconfigure(encoding='utf-8')

HERE = os.path.dirname(os.path.abspath(__file__))
LAB = os.path.dirname(HERE)

# 폴더가 「쓰지 말라」고 말하는 방법
MARK_FILE = 'NO_CITE'
WARN = re.compile(
    r'(인용하지\s*(말|않)|성적으로\s*인용하지|쓰지\s*(말|않)|결함\s*규격'
    r'|보행\s*능력을\s*잰\s*것이\s*아)')


def warned(folder):
    """이 결과 폴더가 「인용하지 말 것」이라고 말하나. 말한다면 그 한 줄."""
    p = os.path.join(folder, MARK_FILE)
    if os.path.isfile(p):
        first = io.open(p, encoding='utf-8', errors='ignore').read().strip()
        return first.split('\n')[0][:90] or MARK_FILE

    # README 나 「읽어주세요」 류 파일의 «머리» 만 본다. 본문 깊은 곳의
    # 지나가는 말까지 잡으면 멀쩡한 폴더가 걸린다.
    for name in sorted(os.listdir(folder)):
        low = name.lower()
        if not name.endswith('.md'):
            continue
        if not (low.startswith('readme') or '읽어' in name or '결함' in name):
            continue
        head = io.open(os.path.join(folder, name), encoding='utf-8',
                       errors='ignore').read()[:1200]
        m = WARN.search(head)
        if m:
            line = [l for l in head.split('\n') if m.group(0) in l]
            return (line[0].strip('> ').strip()[:90] if line else name)
    return None


def banned_folders(results_root):
    """표시가 붙은 결과 폴더의 «이름» 들."""
    out = {}
    if not os.path.isdir(results_root):
        return out
    for name in sorted(os.listdir(results_root)):
        p = os.path.join(results_root, name)
        if not os.path.isdir(p):
            continue
        w = warned(p)
        if w:
            out[name] = w
    return out


def cited_in(paths, names):
    """그 폴더 이름을 «경로로» 가리키는 코드 줄을 찾는다.

    그냥 이름이 글자로 적힌 것은 안 센다. 문서가 「그 폴더는 결함이다」라고
    적는 것까지 잡으면 경고문 자체가 위반이 된다. 따옴표 안이거나
    경로 구분자와 함께 있는 것만 센다.
    """
    hits = []
    for p in paths:
        if not os.path.isfile(p):
            continue
        src = io.open(p, encoding='utf-8', errors='ignore').read()
        for i, line in enumerate(src.split('\n'), 1):
            if line.lstrip().startswith('#'):
                continue                      # 주석은 설명이다
            for n in names:
                if re.search(r'["\'][^"\']*' + re.escape(n) + r'|'
                             + re.escape(n) + r'\s*[/\\]', line):
                    hits.append((p, i, n, line.strip()[:76]))
    return hits


def _selftest(tmp=None):
    """관문 자신을 먼저 시험한다. 실제로 틀렸던 모양을 넣는다."""
    import shutil
    import tempfile
    root = tmp or tempfile.mkdtemp(prefix='nocite-')
    try:
        res = os.path.join(root, 'results')
        for n in ('good-run', 'bad-run', 'marked-run'):
            os.makedirs(os.path.join(res, n), exist_ok=True)
        io.open(os.path.join(res, 'good-run', 'README.md'), 'w',
                encoding='utf-8').write('# 정상\n> 요지: 잘 쟀다\n')
        io.open(os.path.join(res, 'bad-run', 'README.md'), 'w',
                encoding='utf-8').write(
                    '> [규격 1 · 결함] 이 폴더의 성적은 보행 능력을 잰 것이 아닙니다.\n# 스윕\n')
        io.open(os.path.join(res, 'marked-run', MARK_FILE), 'w',
                encoding='utf-8').write('센서가 고장난 채로 쟀다\n')

        bad = []
        got = banned_folders(res)
        if set(got) != {'bad-run', 'marked-run'}:
            bad.append('표시 찾기 (기대 bad-run/marked-run · 결과 %s)' % sorted(got))

        code = os.path.join(root, 'page.py')
        io.open(code, 'w', encoding='utf-8').write(
            'p = os.path.join(R, "bad-run", "sweep.csv")\n'
            '# bad-run 은 결함이라 안 쓴다\n'
            'q = os.path.join(R, "good-run", "x.csv")\n')
        hits = cited_in([code], set(got))
        if len(hits) != 1 or hits[0][2] != 'bad-run':
            bad.append('인용 찾기 (기대 bad-run 1건 · 결과 %s)'
                       % [(h[2], h[1]) for h in hits])
        if any(h[1] == 2 for h in hits):
            bad.append('주석 줄을 위반으로 셌다')

        if bad:
            print('  [!] 자기시험 실패: %s' % ' · '.join(bad))
            return False
        print('  자기시험 3/3 통과 (표시 두 방식 · 주석 제외)')
        return True
    finally:
        if not tmp:
            shutil.rmtree(root, ignore_errors=True)


def check(results_root, code_paths):
    names = banned_folders(results_root)
    if not names:
        print('  인용 금지 표시가 붙은 결과 폴더 없음')
        return True
    hits = cited_in(code_paths, set(names))
    print('  인용 금지 폴더 %d개 · 보고서 코드가 가리키는 곳 %d곳'
          % (len(names), len(hits)))
    for n, why in sorted(names.items()):
        print('     %-34s %s' % (n, why))
    if hits:
        print('  [X] 보고서가 인용 금지 자료를 읽습니다:')
        for p, i, n, line in hits:
            print('       %s:%d  (%s)' % (os.path.relpath(p, LAB), i, n))
            print('         %s' % line)
    return not hits


if __name__ == '__main__':
    if not _selftest():
        raise SystemExit(1)
    res = os.path.join(LAB, 'sim', 'eval', 'results')
    code = [os.path.join(LAB, 'sim', 'eval', 'report', f)
            for f in ('measure.py', 'page.py', 'audit.py', 'make_report.py')]
    raise SystemExit(0 if check(res, code) else 1)
