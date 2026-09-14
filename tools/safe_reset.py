# -*- coding: utf-8 -*-
"""배포 트리를 되돌리기 «전» 에, 되살릴 수 없는 것이 섞여 있는지 본다.

★ 2026-09-14 사고. 배포 담당 세션이 매 배포 전에 이렇게 했다.

      git checkout -- .
      git status --short | grep '^??' | xargs rm -rf

  다른 세션의 빌드가 배포 트리에 직접 쓰는 일이 반복돼, 「남이 구운 것을 내
  이름으로 올리지 않는다」로 정한 절차였다. 빌드 산출물에는 이것이 옳다.
  다시 구우면 똑같이 나오기 때문이다.

  그런데 배포 트리에는 **이 빌드가 만들지 않는 파일**이 있다 (`OTHER_MADE`).

      report-v1.html          sim/eval/report/make_report.py
      assets/gnav*.html/css   tools/gnav_extract.py
      gallery/                sim/eval/render_gallery.py

  이것들은 다시 구울 소스가 이 빌드에 없다. 작업 트리의 것이 «유일한 새 판»
  일 수 있고, 되돌리면 그대로 사라진다.

  실측: `report-v1.html` 이 81,029바이트(07절 「무엇을 잘하라고 가르쳤나」)에서
  74,431바이트(07절 「재현」)로 돌아가 배포됐다. 오류는 하나도 안 났다.
  빌드는 그 파일을 «보존» 하므로, 되살아난 옛 판을 그대로 지켜서 내보냈다.
  같은 날 `assets/gnav-head.html` 도 같은 자리에서 옛 스냅샷이 나갈 뻔했다.
  **보존은 지우지 않는다는 뜻이지 갱신한다는 뜻이 아니다.**

무엇을 하나
  1. 되돌릴 «대상 이름» 을 전부 찍는다. 수만 세지 않는다.
     (커널: 「지우기 전에 git status --short 로 대상 목록을 먼저 본다」)
  2. 그중 다시 만들 수 없는 파일이 있으면 **세운다.** 커밋하거나 `--keep`
     으로 떠 두라고 말한다.
  3. `--keep` 이면 그 파일들을 떠 두었다가 되돌린 뒤 제자리에 돌려놓는다.

왜 관문이 아니라 «도구» 인가
  사고는 빌드 안이 아니라 빌드 «전» 의 셸 한 줄에서 났다. 빌드 관문은 그
  시점에 아직 안 돈다. 위험한 습관은 막을 자리가 있어야 하고, 그 자리는
  그 습관을 대신하는 도구다.
"""
import ast
import io
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def other_made(repo_root):
    """`build.py` 의 OTHER_MADE 를 «읽어서» 쓴다. 여기에 베껴 적지 않는다.

    베껴 적으면 저쪽에 한 줄 늘 때 여기가 조용히 낡는다. 2026-09-14 하루에
    「같은 규칙이 두 자리에 살면 갈라진다」를 일곱 번 봤다.

    ## 문자열이 아니라 구문으로 읽는다

    첫 판은 `find('OTHER_MADE')` 로 자리를 잡고 첫 중괄호부터 다음 중괄호까지를
    잘라 쉼표로 쪼갰다. 같은 날 저쪽에 `OTHER_MADE_SOURCE` 라는 표가 생기고
    항목마다 주석이 붙자 **주석 글이 파일 이름으로 섞여 들어왔다.** 조용히.
    그러면 `report-v1.html` 을 못 지킨다. 그 파일을 지키려고 만든 도구가.

    그래서 `ast` 로 읽는다. 주석도 중첩도 안 먹는다. set 이든 dict 든
    (dict 면 «키» 가 파일 이름) 둘 다 받는다.
    """
    p = os.path.join(repo_root, 'web', '_build', 'build.py')

    try:
        src = io.open(p, encoding='utf-8', errors='replace').read()
        tree = ast.parse(src)
    except Exception:
        return None

    return _names_from(tree)


def _names_from(tree):
    """`OTHER_MADE` 또는 `OTHER_MADE_SOURCE` 에서 파일 이름을 뽑는다."""
    found = {}

    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        for tgt in node.targets:
            if not isinstance(tgt, ast.Name):
                continue
            if tgt.id not in ('OTHER_MADE', 'OTHER_MADE_SOURCE'):
                continue
            v = node.value
            if isinstance(v, ast.Dict):
                names = {k.value for k in v.keys
                         if isinstance(k, ast.Constant)
                         and isinstance(k.value, str)}
            elif isinstance(v, (ast.Set, ast.List, ast.Tuple)):
                names = {e.value for e in v.elts
                         if isinstance(e, ast.Constant)
                         and isinstance(e.value, str)}
            else:
                continue        # `set(OTHER_MADE_SOURCE)` 같은 파생은 건너뛴다
            if names:
                found[tgt.id] = names

    # 표가 있으면 그것이 정본이다 (거기에 «소스가 어디인가» 도 적혀 있다)
    return found.get('OTHER_MADE_SOURCE') or found.get('OTHER_MADE') or None


def _names_selftest():
    """이 읽기를 쓰기 전에 시험한다. 첫 판이 실제로 틀렸던 모양을 넣는다."""
    dict_src = (
        "OTHER_MADE_SOURCE = {@"
        "    # 배포본에서 뽑는다. 관문 [3.478] 이 다시 굽는다.@"
        "    'assets/gnav.css': '다시 구워짐',@"
        "    # lab 에서 구워 복사한다@"
        "    'report-v1.html': '유일본 · 커밋이 소스',@"
        "}@OTHER_MADE = set(OTHER_MADE_SOURCE)").replace('@', chr(10))

    cases = [
        ("맨 set", "OTHER_MADE = {'a.html', 'b/c.css'}",
         {'a.html', 'b/c.css'}),
        ("주석 붙은 dict (첫 판이 여기서 틀렸다)", dict_src,
         {'assets/gnav.css', 'report-v1.html'}),
        ("남의 중괄호에 안 속는다",
         ("X = {'not-this'}@OTHER_MADE = {'yes.html'}").replace('@', chr(10)),
         {'yes.html'}),
        ("아무것도 없으면 None", "Y = 1", None),
    ]

    bad = []
    for name, src, want in cases:
        try:
            got = _names_from(ast.parse(src))
        except Exception as e:
            got = 'Error: %s' % e
        if got != want:
            bad.append('%s (기대 %s · 결과 %s)' % (name, want, got))

    if bad:
        print('  [!] OTHER_MADE 읽기 자기시험 실패:')
        for b in bad:
            print('      ' + b)
        return False

    print('  OTHER_MADE 읽기 자기시험 %d/%d 통과' % (len(cases), len(cases)))
    return True


def run(args, cwd):
    return subprocess.run(args, cwd=cwd, capture_output=True, text=True,
                          encoding='utf-8', errors='replace')


def status(site):
    out = run(['git', 'status', '--short'], site).stdout.splitlines()
    changed, untracked = [], []
    for ln in out:
        if not ln.strip():
            continue
        rel = ln[3:].strip().strip('"')
        (untracked if ln.startswith('??') else changed).append(rel)
    return changed, untracked


def covered(rel, names):
    """`gallery` 같은 폴더 이름도 그 아래 파일을 덮는 것으로 본다."""
    return any(rel == n or rel.startswith(n.rstrip('/') + '/') for n in names)


def _selftest():
    ok = True
    if covered('gallery/view/index.html', {'gallery'}) is not True:
        print('  [!] 폴더 이름이 하위 파일을 못 덮는다'); ok = False
    if covered('report-v1.html', {'report-v1.html'}) is not True:
        print('  [!] 같은 이름을 못 덮는다'); ok = False
    if covered('report-v1-notes.html', {'report-v1.html'}) is not False:
        print('  [!] 접두어가 같은 남의 파일을 덮는다'); ok = False
    if covered('assets/gnav.css', {'assets/gnav.css'}) is not True:
        print('  [!] 경로 있는 이름을 못 덮는다'); ok = False
    print('  자가검증 %s' % ('4/4 통과' if ok else '실패'))
    return ok


def main(argv):
    if not _selftest():
        print('  [!] 이 도구 자체가 틀렸습니다. 고치기 전에는 쓰지 마십시오')
        return 2
    site = os.path.abspath(argv[1]) if len(argv) > 1 else None
    if not site or not os.path.isdir(os.path.join(site, '.git')):
        print('  쓰는 법: python tools/safe_reset.py <배포본 경로> [--keep] [--yes]')
        return 2
    keep = '--keep' in argv
    yes = '--yes' in argv

    names = other_made(os.path.dirname(HERE))
    if not names:
        print('  [!] build.py 에서 OTHER_MADE 를 못 읽었습니다.')
        print('      무엇이 되살릴 수 없는지 모르는 채로는 안 지웁니다.')
        return 2

    changed, untracked = status(site)
    if not changed and not untracked:
        print('  이미 깨끗합니다. 할 일 없음')
        return 0

    # ★ 수를 세지 않고 이름을 찍는다. 이 한 줄이 오늘 사고를 막았을 것이다.
    print('  되돌릴 파일 %d개 · 지울 파일 %d개' % (len(changed), len(untracked)))
    risky = [r for r in changed + untracked if covered(r, names)]
    for rel in changed[:12]:
        print('    되돌림  %s' % rel)
    if len(changed) > 12:
        print('    …그리고 %d개 더' % (len(changed) - 12))
    for rel in untracked[:12]:
        print('    지움    %s' % rel)

    if risky:
        print()
        print('  [!] 이 빌드가 «만들지 않는» 파일이 %d개 섞여 있습니다.' % len(risky))
        for rel in risky:
            print('        %s' % rel)
        print('      되돌리면 다시 구울 소스가 없습니다. 그대로 사라집니다.')
        if not keep:
            print('      먼저 커밋하거나, --keep 으로 떠 두고 되돌리십시오.')
            return 1

    saved = {}
    if keep:
        for rel in risky:
            fp = os.path.join(site, rel.replace('/', os.sep))
            if os.path.isfile(fp):
                saved[rel] = io.open(fp, 'rb').read()
        if saved:
            print('  %d개를 떠 두었습니다' % len(saved))

    if not yes:
        print()
        print('  실제로 되돌리려면 --yes 를 붙이십시오 (지금은 보기만 했습니다)')
        return 0

    run(['git', 'checkout', '--', '.'], site)
    for rel in untracked:
        fp = os.path.join(site, rel.replace('/', os.sep))
        if os.path.isdir(fp):
            shutil.rmtree(fp, ignore_errors=True)
        elif os.path.isfile(fp):
            os.remove(fp)
    for rel, blob in saved.items():
        fp = os.path.join(site, rel.replace('/', os.sep))
        os.makedirs(os.path.dirname(fp) or '.', exist_ok=True)
        io.open(fp, 'wb').write(blob)
    if saved:
        print('  떠 둔 %d개를 제자리에 돌려놓았습니다' % len(saved))

    left = status(site)
    print('  되돌린 뒤: 변경 %d · 새 파일 %d' % (len(left[0]), len(left[1])))
    return 0


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.exit(main(sys.argv))
