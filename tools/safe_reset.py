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
import io
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def other_made(repo_root):
    """`build.py` 의 OTHER_MADE 를 «읽어서» 쓴다. 여기에 베껴 적지 않는다.

    ★ 베껴 적으면 저쪽에 한 줄 늘 때 여기가 조용히 낡는다. 오늘 하루
      「같은 규칙이 두 자리에 살면 갈라진다」를 일곱 번 봤다.
    """
    p = os.path.join(repo_root, 'web', '_build', 'build.py')
    src = io.open(p, encoding='utf-8', errors='replace').read()
    i = src.find('OTHER_MADE')
    if i < 0:
        return None
    j = src.find('{', i)
    k = src.find('}', j)
    if j < 0 or k < 0:
        return None
    out = set()
    for piece in src[j + 1:k].split(','):
        piece = piece.strip().strip('\'"')
        if piece:
            out.add(piece)
    return out or None


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
