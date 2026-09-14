# -*- coding: utf-8 -*-
"""FOOTHOLD 산출물 빌드 · 배포 준비

  볼트(여기)가 유일한 원본이다. foothold-site 는 이 스크립트가 만드는 복사본이므로
  거기서 직접 고치지 말 것. 다음 빌드에 덮어써진다.

  흐름
    _src/curriculum.base.html   (팀원이 쓴 원본, 손대지 않는다)
        └─ enrich.py ─→ curriculum.html   (도식·용어·인쇄CSS 주입)
    나머지 html + assets
        └─ 그대로 복사 ─→ ../../../../foothold-site/

  실행:  python _build/build.py           (빌드만)
         python _build/build.py --check   (빌드 후 볼트=배포 해시 대조)
         python _build/build.py --verify  (+ 외부 사실 주장이 아직 참인지 조회)

  재현 빌드 (mai-os#22 묶음 6.5)
         python _build/build.py --repro --build-time 2026-09-02T12:00:00+09:00 --out <빈폴더>

  ★ 깃발 뜻을 헷갈리지 말 것
    --no-deploy   «live 배포 없음» 이지 «복사 없음» 이 아니다.
                  손으로 주면 복사 자체를 건너뛴다.
    --repro       live 배포를 하지 않는다. 대신 복사 목적지를 --out 으로 돌린다.
                  복사를 «끄지» 않는 이유는 [3.6] 깨진 링크부터 [4] 민감정보까지
                  일곱 관문이 «복사된 배포본» 을 읽기 때문이다. 복사를 끄면
                  그 일곱이 통째로 안 돌아, 검증을 끈 산출물을 비교하게 된다.
                  --out 이 실제 배포본이거나 git 저장소면 exit 2 로 막는다.
    --skip-secure 암호화 자산 생성을 건너뛴다. --repro 는 이것을 강제한다.

  ★ 배포 전에는 --verify 를 돌린다. 남이 관리하는 사실(라이브러리 최신판·공식 문서 문구)은
    우리가 모르는 사이에 바뀌고, 그때 우리 사이트는 조용히 거짓말을 시작한다.
"""
import io, os, re, sys, shutil, hashlib, subprocess
import buildtime

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
# ★ 2026-09-13. 윈도에서 방금 쓴 파일을 검사기가 잠깐 잡아 «가끔»
#   Errno 22 로 죽는다. 오늘만 세 번, 매번 다른 파일이었다.
#   쓰는 자리가 흩어져 있어 한 곳씩 고치면 다음에 또 다른 데서 난다.
#   여기서 한 번 걸어 부류로 막는다. 다시 해서 되면 그 사실을 찍는다.
import safewrite
safewrite.install()
VAULT = os.path.dirname(HERE)                                   # 05_deliverables
def _find_site():
    """foothold-site 클론 위치: 기계마다 볼트가 놓인 깊이가 달라 상대경로 하나로는 못 찾는다.
    실제로 워크스테이션에서 jay/foothold-site 를 가리켜 빌드가 엉뚱한 곳에 쓸 뻔했다(2026-08-11)."""
    cands = [
        *__import__('roots').site_candidates(),
        os.path.expanduser(r"~\Desktop\jay\인공지능사관학교\foothold-site"),
        os.path.expanduser(r"~\OneDrive\Desktop\인공지능사관학교\foothold-site"),
    ]
    for c in cands:
        if os.path.isdir(c):
            return c
    return cands[0]                                             # 없으면 첫 후보 (빌드가 알려준다)


SITE = _find_site()                                             # 인공지능사관학교/foothold-site

# ── 재현 모드 (#22 묶음 6.5) ──────────────────────────────────────────
#   --repro 는 «같은 소스에서 같은 산출이 나오는가» 만 묻는다. 그래서 셋을 강제한다.
#     · secure 건너뜀   암호 난수(os.urandom)는 결정론화 대상이 아니다. 비교에서 뺀다
#     · 실제 배포본 불가침  복사 «목적지» 를 --out 으로 돌린다. 진짜 사이트는 안 건드린다
#     · canonical time 필수  없으면 실패한다. 현재 시각을 쓰면 그것은 재현이 아니다
#
#   ★ 왜 배포를 «건너뛰지» 않고 «돌리는가»
#     [3.6] 깨진 링크부터 [4] 민감정보까지 일곱 관문이 «복사된 배포본» 을 읽는다.
#     복사를 건너뛰면 그 일곱이 통째로 안 돈다. 재현을 보겠다고 관문을 끄면
#     비교 대상이 «관문을 통과하지 못한 산출물» 이 된다 (철칙 4).
#     그래서 복사는 하되 목적지만 바꾸고, 아래 검사로 그 사실을 못 박는다.
REAL_SITE = SITE                                                # 덮어쓰기 전의 진짜 배포본
REPRO = buildtime.configure()
SKIP_SECURE = REPRO or ('--skip-secure' in sys.argv)
NO_DEPLOY = '--no-deploy' in sys.argv

# ★ 2026-09-14 사고. `--out <폴더>` 만 주고 `--repro` 를 빼면 이 값이
#   «아무 데도 안 쓰인다». 목적지가 안 바뀌고 빌드가 진짜 배포본에 그대로
#   쓴다. 오류도 경고도 없다. 부른 사람은 격리된 곳에 쓴다고 믿는다.
#   실측: 동료 세션이 그렇게 세 번 돌렸고, 둘은 관문에서 멈췄지만 마지막
#   하나가 끝까지 가서 남의 배포 저장소에 148개를 썼다. 커밋 직전에
#   본인이 알아채 막았다. 알아채지 못했으면 다음 배포가 통째로 남의 것이
#   된다.
#
#   그 반대 방향은 이미 막혀 있었다 (`--repro` 인데 `--out` 이 없으면 죽는다).
#   한쪽만 막힌 관문은 반대쪽에서 조용히 무너진다 (철칙 4).
if '--out' in sys.argv and not REPRO:
    print('  [!] --out 은 --repro 와 함께만 씁니다.')
    print('      지금처럼 --out 만 주면 그 값이 무시되고 «진짜 배포본» 에 씁니다.')
    print('      격리해서 구우려면:  python _build/build.py --repro --out <빈 폴더>')
    sys.exit(2)
REPRO_OUT = None
if REPRO:
    _i = sys.argv.index('--out') if '--out' in sys.argv else -1
    REPRO_OUT = sys.argv[_i + 1] if _i >= 0 and _i + 1 < len(sys.argv) else None
    if not REPRO_OUT:
        print('  [!] --repro 는 --out <디렉터리> 가 필요합니다 (실제 배포본 보호)')
        sys.exit(2)
    # ★ 답을 아는 검사. --out 이 진짜 배포본이거나 git 저장소면 여기서 선다
    if os.path.abspath(REPRO_OUT) == os.path.abspath(REAL_SITE):
        print('  [!] --out 이 실제 배포본입니다. 재현 빌드는 그곳에 쓰지 않습니다')
        sys.exit(2)
    if os.path.isdir(os.path.join(REPRO_OUT, '.git')):
        print('  [!] --out 이 git 저장소입니다. 재현 빌드는 빈 폴더에만 씁니다')
        sys.exit(2)
    # ★ 2026-09-02. 격리가 조용히 새던 자리를 막는다.
    #   docs_pages.LAB_CANDIDATES 맨 앞이 기기 절대경로여서, 격리 공간에서
    #   빌드해도 이 표를 쓰는 모듈 17개가 «진짜 lab» 을 읽고 썼다. 실측으로
    #   잡았다 (격리 빌드가 실제 lab 의 versions.json 을 v2.1 -> v2.2 로 고쳤다).
    #   재현 모드는 작업 공간 밖 후보를 아예 지운다. 남는 게 없으면 죽는다.
    import docs_pages as _dp0
    _ws = __import__('roots').workspace()
    _lab_in_ws = _dp0.restrict(_ws)
    if not _lab_in_ws:
        print('  [!] 작업 공간(%s) 안에 foothold-lab 이 없습니다.' % _ws)
        print('      재현 빌드는 공간 밖 lab 을 쓰지 않습니다. 사본을 넣고 다시 부르세요')
        sys.exit(2)
    print('  재현 모드 · lab 을 작업 공간 안으로 묶었습니다: %s' % _lab_in_ws)
    SITE = os.path.abspath(REPRO_OUT)
    os.makedirs(SITE, exist_ok=True)


# 배포 대상: 여기 없는 파일은 사이트로 나가지 않는다
PAGES = ['index.html', 'encyclopedia.html', 'curriculum.html', 'setup.html', 'plan.html',
         'collab.html', 'team-access.html', 'brief.html', 'team-intro.html', 'flow.html',
         'vercel.json']
DIRS = ['assets']

# 배포하면 안 되는 것 (개인정보·내부 경로가 들어 있었던 이력이 있다)
NEVER = ['brief-workstation.html', 'quadruped-onepager.html', 'DEPLOY.md', '_src', '_build']

# ★ 2026-09-13. 배포본에는 «이 빌드가 아닌 다른 생성기» 가 만드는 것이 있다.
#   사람이 손으로 둔 것이 아니다. 지우면 그 생성기를 다시 돌려야 한다.
#   실측: 이 빌드가 아래 넷을 실제로 지웠다 (커밋 전에 되살림).
#
#     assets/gnav.css · gnav.html · gnav-head.html   tools/gnav_extract.py
#     report-v1.html                                  sim/eval/report/make_report.py
#     gallery/                                        sim/eval/render_gallery.py
#                                                     sim/eval/gallery_versions.py
#
#   assets/ 는 통째로 교체되므로 그 안의 것은 «파일 단위» 로 지켜야 한다.
#   폴더 단위로는 못 막는다.
OTHER_MADE = {
    'assets/gnav.css', 'assets/gnav.html', 'assets/gnav-head.html',
    'report-v1.html', 'gallery',
}

# ★ 2026-09-14 팀장 확정: 「lab 에도 갤러리 뷰어가 있어야 하면 그렇게 해」.
#
#   갤러리 폴더는 두 가지가 섞여 있다.
#
#     뷰어 (js · css · html · 시험)   사람이 쓰는 코드 · **정본은 lab**
#     v1/ · versions.json             평가가 만든 데이터 250 MB · site 에 남는다
#
#   전에는 뷰어까지 `foothold-site` 에만 있었다. 「lab 이 정본」과 어긋나고,
#   빌드 관문도 못 본다. 그래서 뷰어만 lab 으로 옮기고 빌드가 **그 파일만**
#   덮어쓴다. 데이터는 손대지 않는다.
GALLERY_VIEWER = [
    'gallery.js', 'gallery.css', 'index.html',
    'view/index.html', 'compare/index.html',
    'test/terrain-rows.test.js',
]


def sha(path):
    return hashlib.sha256(io.open(path, 'rb').read()).hexdigest()[:12]


def build_curriculum():
    """팀원 원본 → 도식·용어·인쇄CSS 주입본"""
    base = os.path.join(VAULT, '_src', 'curriculum.base.html')
    out = os.path.join(VAULT, 'curriculum.html')
    if not os.path.exists(base):
        print('  [!] 원본 없음: _src/curriculum.base.html'); return False
    shutil.copy(base, out)
    r = subprocess.run([sys.executable, os.path.join(HERE, 'enrich.py'), out],
                       capture_output=True, text=True, encoding='utf-8')
    print(re.sub(r'^', '  ', (r.stdout or '').strip(), flags=re.M))
    if r.returncode != 0:
        print('  [!] enrich 실패\n' + (r.stderr or '')); return False
    return True


def guard():
    """민감 파일이 배포 폴더에 있으면 즉시 중단.

    동기화 충돌본(`*.sync-conflict-*`)도 막는다. NAS/Syncthing 이 만든 사본이
    공개 저장소로 새면 옛 내용이 그대로 공개된다. 실제로 5개가 배포 폴더에
    들어와 있었다(2026-08-14 발견, git 에는 안 올라갔다).
    """
    bad = [n for n in NEVER if os.path.exists(os.path.join(SITE, n))]
    bad += [n for n in os.listdir(SITE) if 'sync-conflict' in n]
    if bad:
        print('  [!] 배포 폴더에 있으면 안 되는 것: %s' % ', '.join(bad))
        return False
    return True


def deploy():
    n = 0
    for f in PAGES:
        src = os.path.join(VAULT, f)
        if not os.path.exists(src):
            print('  [!] 없음: %s' % f); continue
        dst = os.path.join(SITE, f)
        # ★ 팀원이 «사이트 통째로» 제출하면 PAGES 에 폴더가 들어온다
        #   (02_team/profiles/<이름>/ -> team-<이름>/). shutil.copy 는 폴더에서 죽는다.
        #   2026-08-26 맹라현 개인 페이지에서 실제로 빌드가 멈췄다.
        if os.path.isdir(src):
            shutil.rmtree(dst, ignore_errors=True)
            shutil.copytree(src, dst)
            n += sum(len(fs) for _, _, fs in os.walk(dst))
            continue
        shutil.copy(src, dst); n += 1

    # 갤러리 뷰어: lab 이 정본이므로 여기서 덮어쓴다.
    # **파일 단위로만** 만진다. `v1/`(250 MB) 과 `versions.json` 은 평가가
    # 만드는 것이라 건드리면 안 된다. 폴더째 복사하면 그것이 날아간다.
    gv = 0
    for rel in GALLERY_VIEWER:
        s = os.path.join(VAULT, 'gallery', rel.replace('/', os.sep))
        if not os.path.isfile(s):
            print('  [!] 갤러리 뷰어 원본이 없습니다: %s' % rel)
            continue
        d2 = os.path.join(SITE, 'gallery', rel.replace('/', os.sep))
        os.makedirs(os.path.dirname(d2), exist_ok=True)
        shutil.copy(s, d2); gv += 1; n += 1
    if gv:
        print('  갤러리 뷰어 %d개 (데이터 v1/ 은 안 건드림)' % gv)

    for d in DIRS:
        s, t = os.path.join(VAULT, d), os.path.join(SITE, d)
        if os.path.isdir(s):
            # ★ 다른 생성기가 만든 것은 지우기 «전에» 떠 두었다가 되돌린다.
            keepsafe = {}
            for rel in OTHER_MADE:
                if not rel.startswith(d + '/'):
                    continue
                fp = os.path.join(SITE, rel.replace('/', os.sep))
                if os.path.isfile(fp):
                    keepsafe[rel] = io.open(fp, 'rb').read()
            shutil.rmtree(t, ignore_errors=True); shutil.copytree(s, t)
            for rel, blob in keepsafe.items():
                fp = os.path.join(SITE, rel.replace('/', os.sep))
                os.makedirs(os.path.dirname(fp), exist_ok=True)
                io.open(fp, 'wb').write(blob)
            if keepsafe:
                print('  다른 생성기 산출물 %d개 지킴: %s'
                      % (len(keepsafe), ' · '.join(sorted(keepsafe))))
            n += sum(len(fs) for _, _, fs in os.walk(t))

    # ★ 2026-08-28 신설. 여기는 «복사» 만 하고 «지우기» 를 안 했다.
    #   그래서 생성 목록에서 빠진 페이지가 배포에 영원히 남는다.
    #   실제 사례: `rough-terrain-study-plan` 은 상태가 「폐기」 라 8/28 에 게시를
    #   막았는데, 그 전에 복사된 html 이 사이트에 남아 계속 서비스되고 있었다.
    #   내용이 92% 같은 확정 문서와 나란히 떠서 어느 쪽이 맞는지 알 수 없었다.
    #   목록에 없는 «생성물» 만 지운다. 손으로 둔 것(assets·설정·git)은 안 건드린다.
    keep = (set(PAGES) | set(DIRS) | OTHER_MADE
            | {'.git', '.gitignore', '.vercel', 'README.md',
               'CNAME', 'vercel.json', 'assets'})
    gone = []
    for f in sorted(os.listdir(SITE)):
        if f in keep or f.startswith('.'):
            continue
        p = os.path.join(SITE, f)
        if os.path.isfile(p) and f.endswith('.html'):
            os.remove(p)
            gone.append(f)
    if gone:
        print('  배포에서 내림 %d장 (생성 목록에 없음): %s'
              % (len(gone), ' · '.join(gone[:6])))
    return n


# ★ 2026-08-28. 배포본에만 «후처리» 가 걸리는 것들. sha 가 다른 것이 정상이다.
#   하위 폴더 페이지는 [3.55] 가 배포본에서만 `assets/` 를 `../assets/` 로 고친다.
#   이걸 모르는 대조는 영원히 «불일치» 를 찍는데, **늘 빨간 관문은 무시당한다.**
#   숨기지 않는다. 왜 다른지를 적어서 보여준다.
POST_PROCESSED = {'team-meang': '하위 폴더 상대경로 보정 [3.55]'}


def check():
    ok = True
    print('\n  볼트 ↔ 배포 대조')
    for f in PAGES:
        if f in POST_PROCESSED:
            print('    %-20s 보정됨 (%s)' % (f, POST_PROCESSED[f]))
            continue
        a, b = os.path.join(VAULT, f), os.path.join(SITE, f)
        if not (os.path.exists(a) and os.path.exists(b)):
            print('    %-20s ★ 한쪽 없음' % f); ok = False; continue
        # 팀원 개인 페이지는 «폴더»로 들어온다(team-meang/). sha() 는 파일만 읽으므로
        # 여기서 죽었다. 2026-08-27: --check 가 통째로 못 돌았다.
        if os.path.isdir(a):
            fa = sorted(os.path.relpath(os.path.join(r, x), a)
                        for r, _, xs in os.walk(a) for x in xs)
            fb = sorted(os.path.relpath(os.path.join(r, x), b)
                        for r, _, xs in os.walk(b) for x in xs)
            same = fa == fb and all(
                sha(os.path.join(a, x)) == sha(os.path.join(b, x)) for x in fa)
            print('    %-20s 폴더 %d개 파일  %s'
                  % (f, len(fa), '일치' if same else '★ 불일치'))
            ok &= same
            continue
        same = sha(a) == sha(b)
        print('    %-20s %s  %s' % (f, sha(a), '일치' if same else '★ 불일치'))
        ok &= same
    return ok


if __name__ == '__main__':
    print('원본 : %s' % VAULT)
    print('배포 : %s\n' % SITE)
    # 이 빌드가 «foothold-lab» 이 아닌 트리에서 돌면 이름을 댄다 (roots 참조).
    __import__('roots').warn_if_stray()
    # ★ 맨 앞이어야 한다 (mai-os#24). 손 관리 페이지를 소스에서 새로 만든다.
    #   나중에 돌면 그 빌드의 주입물을 통째로 지운다.
    #   여기가 있어야 주입물이 쌓일 수 없다 (실측: 빈 CSS 껍데기가 빌드마다 +1 로
    #   77개까지, 옛 테마 부트 스크립트가 27개까지 불어나 있었다).
    print('[0.6] 손 관리 페이지를 소스에서 생성')
    import handpages
    if not handpages.main(VAULT):
        print('  [!] 손 관리 페이지를 못 만들었습니다. 배포를 중단합니다.')
        sys.exit(1)

    print('[0] 슬라이드 병합 (팀소개 + 킥오프)')
    r = subprocess.run([sys.executable, os.path.join(HERE, 'merge_deck.py')],
                       capture_output=True, text=True, encoding='utf-8')
    print(re.sub(r'^', '  ', (r.stdout or '').strip(), flags=re.M))
    if r.returncode != 0:
        print('  [!] 병합 실패\n' + (r.stderr or '')); sys.exit(1)

    print('\n[1] 커리큘럼 생성')
    if not build_curriculum():
        sys.exit(1)

    print('\n[1.05] 발표 덱 생성 (_src/pitch.base.html → pitch.html)')
    _pb = os.path.join(VAULT, '_src', 'pitch.base.html')
    if os.path.exists(_pb):
        sys.path.insert(0, HERE)
        import roles as _roles
        _ph = _roles.expand(io.open(_pb, encoding='utf-8').read())
        if '<!--ROLES:pitch-->' in _ph:
            print('  [!] 역할 카드를 못 채웠습니다 (ROLES.md 를 못 읽음)')
            sys.exit(1)
        io.open(os.path.join(VAULT, 'pitch.html'), 'w', encoding='utf-8',
                newline='\n').write(_ph)
        print('  pitch.html 재생성 (정본 = _src + docs/ROLES.md)')

    sys.path.insert(0, HERE)
    import docs_pages as _dp0
    _lab0 = next((p for p in _dp0.LAB_CANDIDATES
                  if os.path.isdir(os.path.join(p, 'docs'))), None)

    # ★ 2026-08-29 신설. 관계표가 8/28 한 시점의 «사진» 이었다. 새 문서가 들어오면
    #   그 사진에 안 찍힌다. 오늘 걷어낸 「손 관리 마스터」와 같은 부류다.
    #   매 빌드마다 문서를 다시 훑어 그린다. 사람 판정은 overrides 가 지키고,
    #   규칙과 어긋나면 조용히 덮지 않고 보고한다.
    # 시간 입력이 buildtime 밖에서 새는지 (#22 묶음 6.5).
    #   모았다가 아니라 계속 모여 있는가를 묻는다 (철칙 4).
    print('\n[1.33] 시간 입력 관문 (buildtime 한 곳인가)')
    import timecheck
    if not timecheck.main():
        print('  [!] 시간 입력이 새고 있습니다. 배포를 중단합니다.')
        sys.exit(1)

    # 판 원장. 문서가 바뀌면 소수점이 저절로 붙는다 (#112).
    #   md 를 건드리지 않는다. 정본은 docs/ops/versions.json 이다.
    #   첫 실행은 기준선만 기록하고 판을 올리지 않는다.
    print('\n[1.34] 판 원장 (문서가 바뀌면 소수점을 붙인다)')
    import vercheck
    #   ★ --repro 는 공유 입력(foothold-lab)에도 쓰지 않는다.
    #     A 의 쓰기가 B 의 입력을 바꾸면 A/B 비교가 독립이 아니다.
    if vercheck.main(write=not REPRO) is None:
        print('  [!] 판 원장을 못 만들었습니다. 배포를 중단합니다.')
        sys.exit(1)

    print('\n[1.35] 문서 관계표 다시 그리기 (유형 · 작업 영역 · 참조 · 활동)')
    import docgraph
    if not docgraph.main(_lab0, write=not REPRO):
        print('  [!] 관계표를 못 만들었습니다'); sys.exit(1)

    # ★ 2026-08-27 신설. md 문서 안의 `[문구](경로.md)` 를 «웹의 진짜 페이지»로
    #   잇는 연결표. 게시기마다 손으로 치환 규칙을 적어 넣던 것을 한 곳에 모았다.
    #   어떤 md 든 렌더되기 «전에» 만들어져 있어야 한다.
    print('\n[1.4] md -> 웹 연결표 작성')
    import mdlinks
    mdlinks.build(_lab0)
    print('  연결 규칙 %d개 (lab %s)'
          % (len(mdlinks._MAP), '찾음' if _lab0 else '못 찾음'))

    print('\n[1.5] 백과 용어 사전 보강')
    import glossary
    base = os.path.join(VAULT, '_src', 'encyclopedia.base.html')
    if os.path.exists(base):
        src = io.open(base, encoding='utf-8').read()
        io.open(os.path.join(VAULT, 'encyclopedia.html'), 'w', encoding='utf-8').write(
            glossary.apply(src))
    else:
        print('  [!] _src/encyclopedia.base.html 없음. 보강 건너뜀')

    print('\n[1.7] 팀원 가이드 생성 (02_team/TEAM_ACCESS.md → team-access.html)')
    import team_access
    h = team_access.build()
    print('  %d bytes · 섹션 %d · 표 %d' % (len(h), h.count('<section'), h.count('<table')))

    print('\n[1.72] 설계도 페이지 (04_plan/PLAN.md → plan.html)')
    import plan_page
    h2 = plan_page.build()
    print('  %d bytes · 표 %d' % (len(h2), h2.count('<table')))

    print('\n[1.73] 협업 규칙 페이지 (lab docs/COLLAB.md → collab.html)')
    import collab_page
    h3 = collab_page.build()
    print('  %d bytes · SVG %d' % (len(h3), h3.count('<svg')))

    print('\n[1.74] 프로젝트 흐름 페이지 (lab docs/FLOW.md → flow.html)')
    import flow_page
    h4 = flow_page.build()
    print('  %d bytes · 표 %d · SVG %d' % (len(h4), h4.count('<table'), h4.count('<svg')))

    # ★ 매 빌드마다 확인한다. 문서(DESIGN.md §1-0)에만 적어두면 지켜지지 않는다. 
    #   실제로 규칙만 쓰고 CSS 에는 안 넣은 채로 하루를 보냈다.
    print('\n[1.75] 브랜드 변수(--brand) 확인')
    import brandvar
    brandvar.main()

    print('\n[1.8] setup.html 코드 문법 강조')
    import hl_setup
    hl_setup.main()

    # ★ 새 문서를 위해 이 파일을 고칠 일은 없다. lab docs/research/ 를 훑어서 발견한다.
    print('\n[1.78] lab 문서 자동 게시 (docs/research/ → 웹)')
    import docs_pages
    made, rcards = docs_pages.build()
    for f in made:
        if f not in PAGES:
            PAGES.insert(PAGES.index('vercel.json'), f)
    if docs_pages.inject_index(VAULT, rcards):
        print('  표지에 연구 기록 섹션 갱신')

    # ★ 다크모드·파비콘·검색이 이 페이지에도 적용되도록 관문·주입 단계보다 앞에서 만든다
    #   (처음엔 [1.88] 뒤에 있었고, 그 판은 테마 변수를 못 받아 검색 오버레이가 깨질 수 있었다)
    print('\n[1.895] 팀 자료실 (조선대 자료 암호화)')
    import secure_docs
    if SKIP_SECURE:
        # ★ 2026-09-02 (mai-os#24 · 팀장 결정). 암호화는 건너뛰되 «공개 HTML 껍데기» 는
        #   템플릿에서 다시 만든다. 전에는 통째로 건너뛰어 그 두 장만 옛 파일이
        #   남았고, 주입 공백이 빌드마다 한 자씩 늘어 연속 빌드 동일성이 깨졌다.
        #   알려진 예외를 남긴 채로 «전체 재현 성공» 을 선언하지 않는다.
        #
        #   render_secure_pages 는 순수·결정론적이다. 비밀번호를 읽지 않고,
        #   salt·nonce 를 만들지 않고, .enc·manifest·캐시·소유 표식을 건드리지 않는다.
        print('  암호화 건너뜀 (--repro / --skip-secure) · 공개 HTML 만 템플릿에서 생성')
        if not secure_docs.render_secure_pages(VAULT):
            print('  [!] 자료실 페이지를 만들지 못했습니다. 배포를 중단합니다.')
            sys.exit(1)
    else:
        secure_docs.main()
    if os.path.exists(os.path.join(VAULT, 'chosun-materials.html')) and 'chosun-materials.html' not in PAGES:
        PAGES.insert(PAGES.index('vercel.json'), 'chosun-materials.html')
    # 발표 덱 (팀장 지시 2026-08-20 킥오프): 존재하면 게이트·복사 대상에 포함
    if os.path.exists(os.path.join(VAULT, 'pitch.html')) and 'pitch.html' not in PAGES:
        PAGES.insert(PAGES.index('vercel.json'), 'pitch.html')

    # 자동화 지도 (팀 공유용). 손으로 쓴 페이지라 생성하지 않고 게이트·복사만 태운다.
    if os.path.exists(os.path.join(VAULT, 'automation.html')) and 'automation.html' not in PAGES:
        PAGES.insert(PAGES.index('vercel.json'), 'automation.html')

    # 팀원 개인 소개 페이지. 표지 팀 카드에서 이름을 누르면 여기로 온다.
    #   생성된 페이지도 다크모드·문체 검사·검색 색인을 받아야 하므로 관문보다 앞에서 만든다.
    print('\n[1.897] 팀원 개인 소개 페이지')
    import teamprofiles
    ok_tp, tp_made = teamprofiles.main(VAULT, None)
    if not ok_tp:
        print('  [!] 팀 섹션 주입 실패. 배포를 중단합니다.')
        sys.exit(1)
    for f in tp_made:
        if f not in PAGES:
            PAGES.insert(PAGES.index('vercel.json'), f)

    print('\n[1.76] 팔레트 ↔ brand 토큰 정본 대조')
    import tokencheck, darkmode
    if not tokencheck.main(darkmode.LIGHT, darkmode.DARK):
        print('\n  [!] 색이 브랜드 정본과 다릅니다. 배포를 중단합니다.')
        sys.exit(1)

    # ★ 생성 단계([1]~[1.8]) 전부가 끝난 뒤에 주입한다. 앞 단계가 파일을 다시 쓰면 주입분이 사라진다.
    print('\n[1.79] 문구 ↔ brand VOICE 정본 대조')
    import voicecheck
    if not voicecheck.main(VAULT, PAGES):
        print('\n  [!] 브랜드 문구 규정을 어겼습니다. 배포를 중단합니다.')
        sys.exit(1)

    print('\n[1.82] 웹 ASCII 도식 검사 (세션 규칙 2)')
    import asciicheck
    if not asciicheck.main(VAULT, PAGES):
        print('\n  [!] 도식을 SVG·표로 바꾸고 다시 빌드하세요. 배포를 중단합니다.')
        sys.exit(1)

    print('\n[1.85] 다크모드 + 사용자 토글 주입 (DESIGN-GUIDE §2)')
    if not darkmode.main(VAULT, PAGES):
        sys.exit(1)

    # ★ 다크모드 뒤에 온다. 앞에 두면 파비콘의 브랜드 색(#0e7a6e)까지 변수로 치환돼
    #   mask-icon 이 깨진다(리터럴 색만 받는다). 실제로 한 번 그렇게 나왔다.
    print('\n[1.87] 브랜드 정본 자산 적용 (파비콘 · 워드마크)')
    import brandmark
    if not brandmark.main(VAULT, PAGES):
        sys.exit(1)

    # 새로 등록된 문서에 NEW 를 자동으로. 등록일은 공개 저장소 git, 판정은 브라우저 현재 시각.
    print('\n[1.88] NEW 배지 (등록 후 일정 기간 자동 표시)')
    import newbadge
    newbadge.main(VAULT, PAGES, SITE)

    # 모든 페이지가 최종 내용을 갖춘 뒤에 색인을 뜬다. 앞에 두면 색인이 낡는다.
    # ★ 2026-09-13. 색인이 «배포본에만 있는 페이지» 도 읽게 배포 경로를 준다.
    #   갤러리와 종합 보고서는 다른 생성기가 배포본에 직접 만든다. 볼트에
    #   없으니 여기서 알려 주지 않으면 검색에서 통째로 빠진다.
    #   그 페이지를 하나라도 못 찾으면 배포가 선다. 조용히 빠지면 검색에서
    #   사라지는데 아무도 모른다.
    #   ★ 2026-09-13 정정. 여기에 `SITE` 를 주면 **재현 빌드가 죽는다.**
    #     재현 모드에서 `SITE` 는 «빈 출력 폴더» 라 그 넷이 있을 리 없고,
    #     관문이 «하나도 못 찾았다» 로 배포를 세운다 (실측: 이 줄 때문에
    #     재현 빌드가 [1.8994] 에서 멈췄다).
    #     그 페이지들은 이 빌드의 «산출» 이 아니라 «입력» 이다. 어디로
    #     내보내든 읽는 자리는 언제나 진짜 배포본이다. 그래서 REAL_SITE 다.
    import searchbox as _sb0
    _sb0.SITE_DIR = REAL_SITE
    print('\n[1.89] 사이트 검색 (색인 생성 + 검색창 주입)')
    import searchbox
    searchbox.main(VAULT, PAGES)

    # ★ 2026-08-26 신설 (SITE-REVIEW §6-2). 자기 자신에 대한 사실을 손으로 쓰면
    #   반드시 어긋난다. 실제로 덱 「10장」(실제 12장) · 안건 「5건」(실제 6건) ·
    #   「현 단계 W1」(08-12 이후 미갱신)이 웹에 떠 있었다.
    #   외부 사실은 claims.py 가 지키는데 «우리 자신에 대한 사실»은 아무도 안 지켰다.
    #
    #   ★ 위치가 중요하다. index 를 쓰는 모든 단계(docs_pages · newbadge ·
    #     searchbox) «뒤»에 둔다. 중간에 두면 뒤 단계가 덮어써도 못 잡는다.
    #     처음 [1.74b] 에 뒀다가 docs_pages 가 덱 장수를 되돌려 놓았고,
    #     관문은 그 전에 통과 도장을 찍어 실서버에 틀린 숫자가 나갔다.
    # ★ 2026-08-27 신설. 팀장 지적: 「문서화 한 것은 단순히 문서만 남기라는 것이
    #   아니고 그 내용을 바탕으로 웹에 반영을 해야한다.」
    #   브레인스토밍·기획서·WBS 를 md 로만 써두고 웹에서 읽을 수 없는 상태였다.
    # WORKFLOW.md 는 스스로 「흐름의 정본」이라 선언해 놓고 웹에 없었다.
    #   문서를 만들어 놓고 가리키지 않으면 없는 것과 같다 (2026-08-27 감사).
    print('\n[1.8954] foothold-wiki 이식 (#72 1단계)')
    import wiki_import
    if wiki_import.main():
        for _wf in [x[1] for x in wiki_import.PAGES]:
            if _wf not in PAGES:
                PAGES.insert(PAGES.index('vercel.json'), _wf)

    print('\n[1.8955] 운영 문서 게시 (작업 흐름 · 개인 계획 · 결정 · 공지)')
    import ops_pages as _op
    _opm = _op.build()
    print('  %d개: %s' % (len(_opm), ' · '.join(m[0] for m in _opm)))
    for _f, _t in _opm:
        if _f not in PAGES:
            PAGES.insert(PAGES.index('vercel.json'), _f)

    print('\n[1.896] 산출물 문서 게시 (lab deliverables/*.md -> 웹)')
    import deliverables_docs as _dd
    _made = _dd.build()
    if not _made:
        print('  [!] 산출물 문서를 하나도 못 만들었습니다. 배포를 중단합니다.')
        sys.exit(1)
    print('  %d개: %s' % (len(_made), ' · '.join(m[1][:14] for m in _made)))

    # ★ 2026-09-09 신설. 바로 위 단계가 lab 에서 «발표본 실물» 을 통째로
    #   복사한다. [1.87] 이 박아 둔 파비콘이 그때 덮여 사라졌다.
    #   실측: 그 한 장만 파비콘 없이 나갔고, 검증도 PAGES(루트만) 를 봐서
    #   못 잡았다. 주입 · 워드마크 · 검증 셋 다 같은 사각지대였다.
    #   여기서 다시 적용하고, 이번에는 주소가 «그 페이지에서 열리는가» 까지
    #   주소가 열리는지까지는 [3.555] 에서 본다. 상대경로 보정이 [3.55] 라
    #   여기서 보면 멀쩡한 team-meang 을 위반으로 잡는다.
    print('\n[1.8965] 브랜드 재적용 (덮어쓴 뒤 · 공개 전수)')
    import brandmark as _bm2
    if not _bm2.main(VAULT, PAGES):
        print('\n  [!] 브랜드 자산이 빠졌습니다. 배포를 중단합니다.')
        sys.exit(1)
    # #77: WBS 표를 웹에. md 재생성 직후라야 마커가 안 지워진다.
    print('[1.897] WBS 표 주입 (xlsx -> 웹)')
    import wbs_web
    wbs_web.main(VAULT)
    for _f, _t, _st in _made:
        if _f not in PAGES:
            PAGES.insert(PAGES.index('vercel.json'), _f)

    # ★ 2026-08-26 신설. 정보 구조 (팀장 확정: 띠 + 바로가기 + 허브).
    #   ★ 2026-08-29: 「허브 5」를 손으로 박아 뒀다가 여섯째(#71)를 더하고도
    #     화면이 5라고 말했다. 숫자는 ia.HUBS 에서 센다.
    #   ia.py 가 «모든 페이지가 어디 속하는지» 의 유일한 표다. 미배정이 하나라도
    #   있으면 여기서 선다. 2026-08-25 사고(자료실이 어느 허브에도 못 들어가
    #   1클릭에서 3클릭으로 밀린 것)의 재발 방지다.
    print('\n[1.8975] CSS 무결성 (잘린 선택자 · 틀 규칙)')
    import csscheck
    if not csscheck.main():
        print('  [!] 허브 CSS 가 조용히 깨졌습니다. 배포를 중단합니다.')
        sys.exit(1)

    import ia as _ia0
    print('\n[1.898] 정보 구조: 허브 %d · 표지 · 전역 상단바' % len(_ia0.HUBS))
    import hubgen
    if not hubgen.main():
        print('  [!] 배정되지 않은 페이지가 있습니다. 배포를 중단합니다.')
        sys.exit(1)
    # #74-6: 등록만 되고 파일이 없는 페이지가 조용히 지나가지 않게
    #
    #   ★ 2026-09-03 순서 정정 (foothold-lab#137). 이 검사가 hubgen «앞» 에 있었다.
    #     hubgen 이 deliverables.html 을 만드는데, 그보다 먼저 «없다» 고 판정해
    #     이전 빌드의 파일이 남아 있지 않은 트리에서는 여기서 죽었다.
    #     검사를 지우거나 예외를 두지 않는다. 만든 «뒤» 에 그대로 본다.
    import ia as _iag
    _ghost = _iag.ghost_pages()
    if _ghost:
        print('  [!] 등록됐는데 파일이 없습니다: %s' % ' · '.join(_ghost))
        sys.exit(1)
    for _hf in [h[3] for h in hubgen.ia.HUBS] + ['budget.html', 'deliverables.html']:
        if os.path.exists(os.path.join(VAULT, _hf)) and _hf not in PAGES:
            PAGES.insert(PAGES.index('vercel.json'), _hf)

    # ★ 실측 (팀장 8/31): 검색이 예산안·wiki 이식 페이지에 없었다.
    #   [1.8] 검색 주입은 «그때의 PAGES» 만 받아, 뒤에 추가된 페이지를 놓친다.
    #   목록이 다 찬 지금 다시 한 번 돌려 전 페이지에 넣는다.
    print('\n[1.8986] 검색 재주입 (뒤늦게 추가된 페이지까지)')
    import searchbox as _sb2
    _sb2.main(VAULT, PAGES)

    #   ★ 9/1 실측 (#75 가 열려 있던 진짜 이유): NEW 배지도 같은 함정이었다.
    #   [1.88] 은 허브가 «생기기 전» 에 돌아, 표지에는 배지가 뜨는데 허브
    #   6장에는 하나도 안 떴다 (렌더 실측: 표지 2 · 허브 0).
    #   PAGES 는 11개짜리 고정 목록이라 그것만 돌면 나중에 생긴 문서가
    #   통째로 빠진다. 이 시점에는 볼트에 최종본이 다 있으니 전부 훑는다.
    print('\n[1.8988] NEW 배지 재주입 (허브가 생긴 뒤 · 볼트 전수)')
    import newbadge as _nb2
    _all = sorted(f for f in os.listdir(VAULT)
                  if f.endswith('.html') and f not in NEVER)
    _nb2.main(VAULT, _all, SITE)

    # ★ 2026-08-27 신설. 결정이 자주 바뀌는 시기라, 팀원이 지금 보는 페이지가
    print('\n[1.8987] 라이트 오버라이드 보정 (토글 3종 세트 · 원본에)')
    import themefix
    themefix.main(VAULT)

    #   «어느 판인지» 를 알 수 있어야 회의에서 서로 다른 판을 놓고 다투지 않는다.
    print('\n[1.8985] 판 번호 · 갱신 시각 띠')
    import stamp
    # 시간 입력은 buildtime 한 곳에서만 나온다 (#22 묶음 6.5).
    #   전에는 여기서 PowerShell Get-Date 를 불러 매 빌드 값이 달랐다.
    _when = buildtime.stamp()
    if not re.match(r'^20\d\d-\d\d-\d\d \d\d:\d\d$', _when or ''):
        print('  [!] 시각을 못 읽었습니다: %r' % _when)
        sys.exit(1)
    if not stamp.main(_when):
        sys.exit(1)

    # 문서가 어느 이슈를 따르는지 (#111 · 팀장 9/1). 글자로 있던 «#94» 를
    #   전 페이지에서 링크로 만든다. 머리 띠의 «이슈» 딱지도 여기서 링크가 된다.
    #   반드시 stamp 뒤다. 띠를 먼저 붙여야 그 안의 번호까지 잡힌다.
    print('\n[1.8984] 이슈 번호를 링크로 (볼트 전수)')
    import issuelink
    if not issuelink.main(VAULT):
        print('  [!] 이슈 링크 주입이 실패했습니다. 배포를 중단합니다.')
        sys.exit(1)

    print('\n[1.899] 자기 참조 사실 집계 (덱 장수 · 안건 수 · 단계)')
    import selfclaim
    if not selfclaim.main():
        print('  [!] 자기 참조 사실이 어긋납니다. 배포를 중단합니다.')
        sys.exit(1)

    # ★ 2026-09-09 신설. 바로 위 [1.899] 가 홈에 «현황 띠» 를 «쓴다».
    #   그런데 색인은 [1.8986] 에서 이미 만들어졌다. 그래서 화면에 있는
    #   「기간 5주차 · 다음 마일스톤 D-21 · 미결 안건 6건」 을 검색하면 0건이었다.
    #   이 저장소가 되풀이해 겪은 부류다. 앞 단계가 본 것을 뒤 단계가 바꾼다.
    print('\n[1.8994] 검색 재주입 (자기 참조 띠가 쓰인 뒤)')
    import searchbox as _sb3
    if not _sb3.main(VAULT, PAGES):
        print('\n  [!] 검색 재주입이 실패했습니다. 배포를 중단합니다.')
        sys.exit(1)

    # ★ 같은 실수를 «부류로» 막는다. 개별 단계를 금지하는 조항은 다음번에
    #   다른 단계가 같은 일을 해서 무력해진다. 결과만 본다:
    #   화면에 있는 글자가 색인에 있는가. 없으면 색인 뒤에 쓴 단계가 있는 것이다.
    print('\n[1.8995] 색인 신선도 (색인이 지금 페이지를 담고 있는가)')
    import indexfresh
    if not indexfresh.main(VAULT, PAGES):
        print('\n  [!] 색인이 낡았습니다. 배포를 중단합니다.')
        sys.exit(1)

    if '--verify' in sys.argv:
        print('\n[1.9] 사실 주장 검증 (외부 원본을 실제로 조회)')
        import claims
        if not claims.verify():
            print('\n  [!] 사이트가 사실이 아닌 내용을 담고 있습니다. 배포를 중단합니다.')
            sys.exit(1)

    # ★ 2026-09-05 신설. [1.79] 와 [1.82] 는 위에서 이미 한 번 돌지만, 그 자리의
    #   PAGES 는 «아직 다 차지 않은» 목록이다. 아래 [1.8954] wiki 이식 ·
    #   [1.8955] 운영 문서 · [1.896] 산출물 · [1.898] 허브 가 그 뒤에 더 넣는다.
    #   실측 2026-09-04: 관문은 54장만 보고 통과를 찍었고, 못 본 55장 안에
    #   ASCII 도식 위반 3건이 살아 있었다 (notice-20260826 1 · tech-cv 2).
    #   앞의 호출은 «빨리 실패» 용으로 그대로 두고, 여기서 **완성된 목록**으로
    #   다시 본다. 이 저장소가 [1.8986] 검색 «재주입» 에서 쓴 것과 같은 관용이다.
    print('\n[1.8991] 문구 · ASCII 재검사 (뒤늦게 추가된 페이지까지)')
    print('  대상 %d장 (앞 관문이 본 것보다 나중에 늘어난 것 포함)' % len(PAGES))
    if not voicecheck.main(VAULT, PAGES):
        print('\n  [!] 브랜드 문구 규정을 어겼습니다. 배포를 중단합니다.')
        sys.exit(1)
    if not asciicheck.main(VAULT, PAGES):
        print('\n  [!] 도식을 SVG·표로 바꾸고 다시 빌드하세요. 배포를 중단합니다.')
        sys.exit(1)

    # ★ 2026-09-08 감사 F-05. 주입기가 모든 페이지에 같은 스크립트를 넣는데
    #   그 스크립트가 만지는 요소는 페이지마다 있기도 없기도 했다. 로드 즉시
    #   죽는 페이지에서는 «뒤따르는 스크립트가 통째로 멈춘다». 완성된 목록으로 본다.
    print('\n[1.8992] 없는 요소를 만지는 스크립트 검사')
    import jsnullcheck
    if not jsnullcheck.main(VAULT, PAGES):
        print('\n  [!] 스크립트가 없는 요소를 만집니다. 배포를 중단합니다.')
        sys.exit(1)

    # ★ 2026-09-09 신설. 색인에 «있느냐» 말고 «앞에 나오느냐» 를 본다.
    #   라이브에서 「rails」 를 치니 12칸이 전부 파일이름 순이었고 정작
    #   rails 진단 문서 셋은 하나도 없었다. 색인 관문은 그걸 못 잡는다.
    print('\n[1.8993] 검색 순위 검사 (화면에 나가는 JS 를 그대로 돌린다)')
    import searchrank
    if not searchrank.main(VAULT):
        print('\n  [!] 검색 순위가 알려진 답과 다릅니다. 배포를 중단합니다.')
        sys.exit(1)

    print('\n[2] 배포 금지 파일 점검')
    if not guard():
        sys.exit(1)
    print('  민감 파일 없음')

    # ★ 2026-08-27 신설. vercel.json 이 /assets/* 에 immutable 1년 캐시를 건다.
    #   그런데 우리는 같은 이름 위에 계속 덮어쓴다. 그래서 도식을 다시 그려
    #   배포해도 **이미 한 번 본 사람에게는 옛 그림이 그대로 남았다.**
    #   (팀장 지적: "도식화 그림은 왜 안 바뀌었나?" 파일은 바뀌어 있었다.)
    #   주소 뒤에 내용 해시를 붙여 «내용이 바뀌면 주소도 바뀌게» 한다.
    print('\n[2.5] 자산 주소에 내용 해시 (캐시가 옛 그림을 붙잡지 않게)')
    import assetver
    if not assetver.main(VAULT):
        print('  [!] 자산 주소를 못 고쳤습니다. 배포를 중단합니다.')
        sys.exit(1)

    print('\n[3] 복사')
    if NO_DEPLOY:
        print('  건너뜁니다 (--no-deploy)')
    else:
        if REPRO:
            print('  재현 모드 · 실제 배포본(%s) 대신 %s 로 씁니다'
                  % (os.path.basename(REAL_SITE), SITE))
        print('  %d개 반영' % deploy())

    # ★ 복사한 뒤에 검사한다. 볼트가 아니라 **실제로 공개될 파일**을 봐야 한다.
    #   foothold-site 는 PUBLIC 이고, 한 번 push 하면 되돌려도 히스토리에 남는다.
    #   (2026-08-05 워크스테이션 LAN 주소가 이 문 없이 공개 저장소로 나갔다.)
    # 문체 관문. 팀장이 여러 번 지적했는데도 계속 들어갔다.
    #   "쓰지 말자" 를 문서에만 적으면 안 지켜진다. 빌드가 막는다.
    # 문서에 «누가 · 언제 · 무엇을 근거로» 가 없으면 나중에 대조할 수 없다.
    #   2026-08-25 실측: 35개 중 작성자 표기가 있는 것은 6개(17%)뿐이었다.
    #   전부 미비인 상태라 곧바로 차단하면 빌드가 안 돈다. 유예 목록을 두어
    #   새 문서만 막고, 기존은 metacheck_grandfather.txt 를 줄여 가며 갚는다.
    # ★ 2026-09-13. 팀장이 세 번째로 지적한 뒤에 넣었다.
    #   「또 Claude AI Slop 인 문단의 width 를 일부만 쓰네? 규칙 AGENTS.md 에
    #    넣으라고 했지?」
    #   찾아보니 규칙은 `AGENTS.md` 214줄에 **이미 있었다.** 그런데 코드 세
    #   곳이 어기고 있었고 아무도 안 막았다.
    #   **적는 것과 강제하는 것은 다른 일이다.** 적힌 쪽만 있으면 안 지켜진다.
    print('\n[3.41] 문단 폭 검사 (max-width 를 문단에 걸었는가)')
    import widthcheck
    if not widthcheck.main(VAULT):
        print('\n  [!] 문단에 폭 제한이 걸려 있습니다. 배포를 중단합니다.')
        sys.exit(1)

    print('\n[3.4] 문서 메타데이터 검사 (분류 · 작성 · 근거 · 요지)')
    import metacheck
    import roots as _r34
    _lab_docs = os.path.join(_r34.lab() or '', 'docs')
    if not metacheck.main(_lab_docs):
        print('\n  [!] 메타데이터 없는 새 문서가 있습니다. 배포를 중단합니다.')
        sys.exit(1)

    # ★ 라이트 오버라이드 보정은 [1.8987](복사 전, 원본에)로 옮겼다.
    #   여기(복사 뒤)서 배포본만 고치면 원본·배포 해시가 어긋난다 (실측).

    # ★ 2026-09-09 신설. 하위 세션이 «없는 사람 이름» 으로 문서 넷을 올렸다.
    #   출처는 그 세션 시스템 프롬프트의 이메일 주소였고, 로컬파트를 사람
    #   이름처럼 읽었다. 세션은 이름을 알 수 없다. 적으라고 하면 지어낸다.
    #   lab 은 PR 관문으로 막았지만 여기는 lab 문서를 «읽어» 웹에 올린다.
    #   승격 경로로 들어온 문서는 그 PR 관문을 통과한 적이 없을 수 있다.
    print('\n[3.42] 작성자 검사 (docs/ROLES.md 에 있는 사람인가)')
    import authorcheck
    if not authorcheck.main(VAULT, PAGES):
        print('\n  [!] 작성자 표기가 어긋납니다. 배포를 중단합니다.')
        sys.exit(1)

    # ★ 2026-09-09 신설. 오늘만 같은 실수를 네 번 봤다. PAGES 는 루트만 담는데
    #   그것을 도는 코드는 자기가 「배포 전부」를 본다고 믿는다. 하위 폴더와
    #   assets/ 아래 페이지가 빠져 「검사했다」가 거짓이 된다 (감사 F-03 · 파비콘 3곳).
    #   개별 자리를 고치면 다섯 번째가 온다. 자리가 «늘어나는» 것을 막는다.
    print('\n[3.43] 페이지 순회 정본 검사 (PAGES 대신 public_pages)')
    import pagesloop
    if not pagesloop.main(VAULT, PAGES):
        print('\n  [!] 페이지 순회가 정본을 안 씁니다. 배포를 중단합니다.')
        sys.exit(1)

    # ★ 2026-09-09 신설. 동료 세션이 자기 관문에서 「0개 검사하고 통과」를 찾아
    #   알려 왔다. 그 잣대를 내 관문에 대보니 넷이 같았고, 전체를 세니 열넷이었다.
    #   「검사할 것이 없었다」와 「위반이 없었다」는 다른 사실인데 같은 출력을 냈다.
    #   목록이 비는 순간 관문이 조용히 무력해진다. 그리고 목록은 실제로 빈다.
    print('\n[3.44] 관문 자체 검사 (대상이 0개일 때 통과라고 말하는가)')
    import emptycheck
    if not emptycheck.main(VAULT, PAGES):
        print('\n  [!] 눈먼 관문이 새로 생겼습니다. 배포를 중단합니다.')
        sys.exit(1)
    # ★ 2026-09-13 신설. 연구 허브의 거르개가 라이브에서 한 줄도 안 걸렀다.
    #   스크립트는 제대로 돌아 29행을 `hidden` 으로 껐는데, 그 29행이 전부
    #   화면에 남아 있었다 (display:grid). `[hidden]` 은 브라우저 «기본» 시트라
    #   제작자 CSS 의 `.ev3{display:grid}` 한 줄에 진다. 특이도가 아니라 출처로
    #   진다. 그래서 CSS 를 들여다봐도 충돌로 안 보인다.
    #   만든 쪽은 `!c.hidden` 을 세어 「37 -> 8」 을 얻었고 그 수는 «맞다».
    #   속성은 정확히 8이다. 그런데 그것은 화면이 아니다 (커널 원칙 3).
    print('\n[3.445] hidden 숨김 안전망 검사 (CSS 가 숨김을 이기는가)')
    import hiddencheck
    if not hiddencheck.main(VAULT, PAGES):
        print('\n  [!] hidden 이 CSS 에 집니다. 배포를 중단합니다.')
        sys.exit(1)

    print('\n[3.45] 브랜드 정합 검사 (그라데이션 · 그림자 · 토글 · hex)')
    import brandcheck
    if not brandcheck.report(SITE):
        print('  [!] 브랜드 정합이 명부보다 나빠졌습니다. 배포를 중단합니다.')
        sys.exit(1)


    #   ★ 9/1 신설. 검색·파비콘·NEW 배지가 «주입기는 성공을 보고했는데 결과가
    #   없는» 조용한 실패를 세 번 냈다. 주입기를 믿지 말고 완성본을 세어 본다.
    # ★ 2026-09-02 신설 (mai-os#24). 주입 블록의 소유 마커가 성한지 전수 검사.
    #   짝 없는 마커는 다음 빌드의 제거 정규식이 «남의 본문» 을 먹는 자리다.
    #   실제로 newbadge 가 brief 본문 18,000자를, darkmode 가 52장에서
    #   500~600자를 지우고 있었다. 오류가 안 나는 실패다 (원칙 2).
    #   ★ 볼트가 아니라 «배포될 파일» 에서 센다. 주입기들이 다 돈 뒤라야
    #     최종 상태를 볼 수 있다 (철칙 4).
    print('\n[3.462] 주입 소유 마커 검사 (짝 · 중복 · 고아 · 제거 범위)')
    import markercheck
    if not markercheck.main(SITE):
        print('  [!] 소유 마커가 성하지 않습니다. 배포를 중단합니다.')
        sys.exit(1)

    # ★ 2026-09-03 신설 (mai-os#24 · setup 이관). 내용 보존.
    #   계산 스타일 관문은 «화면이 같은가» 만 본다. 코드 한 줄이 바뀌거나 링크
    #   주소가 달라져도 상자 크기가 같으면 «차이 0» 으로 통과한다. 이관의 진짜
    #   위험은 그쪽이다. 사람이 복사해서 실행하는 코드가 조용히 변질되는 것.
    #   손 내용은 이관 직전 고정본 지문과, 생성물은 정본 입력과 견준다.
    print('\n[3.4625] 손 관리 페이지 내용 보존 검사 (본문 · 코드 · 링크 · 제목)')
    import contentcheck
    if not contentcheck.main(SITE):
        print('  [!] 손으로 쓴 내용이 달라졌습니다. 배포를 중단합니다.')
        sys.exit(1)

    # ★ 2026-09-02 신설 (mai-os#24). CSS 변수 순환 참조.
    #   :root 와 html[data-theme=...] 는 같은 요소라 --x:var(--x) 는 순환이고
    #   CSS 가 그 토큰을 무효로 만든다. 화면에서 색이 조용히 죽는다.
    print('\n[3.463] CSS 변수 순환 참조 검사')
    import varcycle
    if not varcycle.main(SITE):
        print('  [!] 순환 참조가 있습니다. 배포를 중단합니다.')
        sys.exit(1)

    print('\n[3.46] 완비 검사 (모든 페이지가 공통 부품 한 벌을 갖췄는가)')
    import completecheck
    if not completecheck.main(SITE):
        print('  [!] 공통 부품이 빠진 페이지가 있습니다. 배포를 중단합니다.')
        sys.exit(1)

    # ★ 2026-09-03 신설 (foothold-lab#156). 「N」 이라 적고 N 개를 안 그린 자리.
    #   실측: 연구 허브가 「후속 과제 8」 옆에 칩 6개였고 #66 rails · #65 gap 이
    #   자취 없이 사라졌다. 링크는 안 깨지고 빌드도 통과하니 아무 소리도 안 났다.
    #   관문이 먼저 자기시험을 통과해야 남을 검사한다 (커널 원칙 1).
    print('\n[3.47] 수와 그림 일치 검사 (N 이라 적고 N 개를 그렸는가)')
    import chipcheck
    _ck_ok, _ck_why = chipcheck._kat()
    if not _ck_ok:
        print('  [!] 관문 자기시험 실패: %s. 배포를 중단합니다.' % _ck_why)
        sys.exit(1)
    if not chipcheck.main(SITE):
        print('  [!] 적은 수와 그린 수가 다릅니다. 배포를 중단합니다.')
        sys.exit(1)

    print('\n[3.5] 문체 검사: em dash 금지')
    import dashcheck
    # ★ 2026-08-28. 웹만 보던 관문을 이슈까지 넓혔다. 같은 날 규칙을 못박고서
    #   이슈 코멘트 한 곳에서 뚫렸다. 규칙이 사는 자리를 다 세야 한다.
    _lab_dash = next((p for p in _dp0.LAB_CANDIDATES
                      if os.path.isdir(os.path.join(p, "docs"))), None)
    if not dashcheck.report(SITE, strict=True, lab=_lab_dash):
        print('\n  [!] 문체 규칙 위반입니다. 배포를 중단합니다.')
        sys.exit(1)

    # ★ 2026-08-26 신설. 죽은 링크는 눌러야만 보이고, 우리는 안 눌러본다.
    #   실제로 research-visual-evidence -> training-benchmarks 가 죽어 있었다.
    #   docs/research/ 안에서 `research-` 접두사를 빼먹으면 나는 부류다.
    # 하위 폴더 페이지는 최상위 기준 경로를 그대로 받으면 전부 깨진다.
    #   team-meang/index.html 의 링크 12개가 그렇게 404 였다 (2026-08-27 감사).
    print('\n[3.55] 하위 폴더 페이지 상대경로 보정')
    import subpaths
    subpaths.main(SITE)


    # ★ 2026-09-09 신설. 파비콘 «주소가 그 페이지에서 열리는가» 는 여기서만
    #   물을 수 있다. 바로 위 [3.55] 가 하위 폴더 상대경로를 보정하기 때문에
    #   그 앞에서 검사하면 멀쩡한 team-meang 을 위반으로 잡는다.
    #   파일에 favicon 글자가 있는 것과 그 주소가 404 가 아닌 것은 다른 사실이다.
    print('\n[3.555] 파비콘 주소 검사 (그 페이지에서 실제로 열리는 경로인가)')
    import brandmark as _bm3
    if not _bm3.verify_favicon(SITE, PAGES):
        print('\n  [!] 파비콘 주소가 어긋납니다. 배포를 중단합니다.')
        sys.exit(1)
    print('\n[3.6] 깨진 내부 링크 검사')
    import linkcheck
    if not linkcheck.main(SITE):
        print('\n  [!] 죽은 링크가 있습니다. 배포를 중단합니다.')
        sys.exit(1)

    # ★ 2026-08-27 신설. 죽은 링크는 잡았지만 «아예 링크가 되지 못한 것»은
    #   아무도 안 봤다. `[프로젝트 보고서](../REPORT.md)` 가 글자 그대로 나간
    #   자리가 배포본 10개에 36곳이었다. 읽는 사람에게는 깨진 글씨다.
    print('\n[3.65] 마크다운 원문 노출 검사')
    if not mdlinks.gate(SITE):
        print('\n  [!] 마크다운 원문이 화면에 나갑니다. 배포를 중단합니다.')
        sys.exit(1)
    # ★ 2026-08-28 신설. 팀장이 여러 번 지적한 「표가 틀어진다」의 원인을 잡았다.
    #   모바일 CSS 의 `table{display:block}` 이 표를 내용 너비로 줄인다.
    #   넓은 표는 우연히 꽉 차 보이고 좁은 표만 왼쪽으로 쏠린다.
    #   크롬 실측: 컨테이너 700px 에서 display:block 51% · display:table 100%.
    #   먼저 안 감싼 표에 가로 스크롤 래퍼를 붙이고, 그 다음 두 층위를 본다.
    print('\n[3.56] 표 정렬 (스크롤 래퍼 · 블록 규칙)')
    import tablefix
    # ★ 볼트에도 건다. 처음에 배포에만 걸었더니 볼트 마스터 4장이 갈라져
    #   `--check` 의 볼트 대조가 상시 «불일치» 를 찍었다. 늘 빨간 관문은 무시당한다.
    tablefix.fix(VAULT)
    tablefix.fix(SITE)
    if not tablefix.main(SITE):
        print('\n  [!] 표가 폭에 안 맞습니다. 배포를 중단합니다.')
        sys.exit(1)

    # ★ 2026-08-28 신설. FLOW 를 v2.0 으로 다시 쓰자 절 번호가 통째로 밀렸다.
    #   링크는 안 깨졌으므로 [3.6] 은 통과했다. 깨진 것은 «그 안의 몇 번째 절인가» 다.
    #   더 고약한 쪽은 «절은 있는데 뜻이 바뀐» 경우다. §3 은 남았지만 증류가 아니다.
    print('\n[3.62] 절 참조 검사 (그 절이 있는가 · 딱지가 제목과 맞는가)')
    import xrefcheck
    if not xrefcheck.main():
        print('\n  [!] 절 참조가 어긋납니다. 배포를 중단합니다.')
        sys.exit(1)
    # ★ 2026-08-27 신설. 사실은 문서에만 있는 것이 아니라 생성기와 손으로 관리하는
    #   마스터 HTML 에도 박혀 있다. 거기 박힌 것은 md 를 고쳐도 안 바뀐다.
    #   collab.html 의 foothold-rl 한 줄이 md 수정에도 살아남은 것이 그 사례다.
    print('\n[3.7] 폐기된 사실 검사 (생성기 · 마스터 · 배포본)')
    import stalecheck
    if not stalecheck.main(SITE):
        print('\n  [!] 폐기된 사실이 웹으로 나갑니다. 배포를 중단합니다.')
        sys.exit(1)


    # ★ 2026-08-28 신설. 누수 방지 장치가 누수되는 것을 막는다.
    #   LEDGER 는 「그거 어떻게 됐어?」의 답인데 최종 갱신이 8/20 에 멈춰 있었다.
    #   그 사이 이슈 30개가 열렸는데 원장은 몰랐다.
    #   날짜만 보면 «날짜만 고치는» 것을 못 잡으므로 열린 이슈와 대조한다.
    #   ★ 이 둘은 `gh` 로 «살아 있는 GitHub 상태» 를 읽는다. 시간과 같은 부류의
    #     비결정 입력이라, 소스가 같아도 A · B 가 갈릴 수 있다. 그래서 재현
    #     모드는 **소리 내어** 건너뛴다. 조용히 통과시키지 않는다.
    print('\n[3.8] 원장 최신성 검사 (LEDGER 가 지금을 담고 있는가)')
    import ledgercheck
    if REPRO:
        print('  건너뜁니다 (재현 모드). gh 가 읽는 살아 있는 이슈 목록은 비결정 입력입니다')
    elif not ledgercheck.main():
        print('\n  [!] 원장이 낡았습니다. 배포를 중단합니다.')
        print('      다음 세션이 여기서 이어야 합니다. 낡으면 같은 자리에서 못 잇습니다.')
        sys.exit(1)

    # ★ 2026-08-28 신설. 역할 배치가 세 군데(정본 · COLLAB · GitHub 라벨)에 적혀
    #   있었고, 8/27 에 8갈래로 바꿨을 때 발표 덱 두 장만 옛 5분야로 남았다.
    #   덱은 이제 정본에서 «생성»되지만, 덱 밖에 손으로 적힌 옛 이름이 남을 수
    #   있으므로 게시물 전체를 함께 본다 (커널 철칙 4).
    # ★ 2026-09-09 신설. 「머지는 됐는데 웹에 없는 문서」를 센다.
    #   팀장이 본 문서를 웹에서 못 찾은 일이 있었고, 같은 상태가 19건이었다.
    #   그 수가 어디에도 안 보인 것이 문제였다. 세되 «세우지는 않는다».
    #   승격이 늦은 것은 내용 결함이 아니라 일이 밀린 것이고, 배포를 막으면
    #   밀린 일이 사이트 전체를 인질로 잡는다.
    print('\n[3.85] 승격 대기 (머지됐는데 웹에 없는 문서)')
    import promoteage
    promoteage.main()

    print('\n[3.9] 역할 배치 검사 (정본 · COLLAB · 라벨 · 게시물)')
    import roles as _rl
    if REPRO:
        print('  건너뜁니다 (재현 모드). gh 가 읽는 라벨 목록은 비결정 입력입니다')
    elif not _rl.main(VAULT):
        print('\n  [!] 역할 배치가 어긋납니다. 배포를 중단합니다.')
        sys.exit(1)

    # ★ 2026-09-14 신설. 도해 «안» 에서 글자가 겹치는지 본다.
    #   팀장이 「글씨 겹침」을 지적했고 실제로 두 도해가 겹쳐 있었다. 그중
    #   하나는 같은 그림의 옛 사본이라 한쪽만 고쳐져 있었다. 눈으로는 못 잡는다.
    print('[3.473] 도해 안 바깥 자원 검사 (<img> 로 불리면 안 불려온다)')
    sys.path.insert(0, os.path.join(HERE, '..', '..', 'tools'))
    import svg_embed_images
    if not svg_embed_images._selftest():
        print('  [!] 자기시험 실패. 이 검사를 믿을 수 없습니다'); sys.exit(1)
    if not svg_embed_images.check(os.path.join(HERE, '..', '..', 'docs', 'assets', 'visual')):
        print('  [!] 도해가 바깥 그림을 가리킵니다. 배포를 중단합니다.')
        sys.exit(1)

    print('[3.474] 도해 여백 검사 (viewBox 가 실측 기준과 같은가)')
    sys.path.insert(0, os.path.join(HERE, '..', '..', 'tools'))
    import svg_pad
    if not svg_pad._selftest():
        print('  [!] 자기시험 실패. 이 검사를 믿을 수 없습니다'); sys.exit(1)
    if not svg_pad.check(os.path.join(HERE, '..', '..', 'docs', 'assets', 'visual')):
        print('  [!] 도해 여백이 기준과 다릅니다. 배포를 중단합니다.')
        print('      `python tools/svg_pad.py --write docs/assets/visual` 로 맞춥니다')
        sys.exit(1)

    # ★ 2026-09-14 신설. 팀장이 「웹에 들어가면 SVG 컬러가 이전 컬러로
    #   돌아갔다」고 잡았다. 실제로 봤다. 페이지는 다크인데 도해만 라이트였다.
    #   `<img>` 안의 도해는 격리된 문서라 이 페이지의 data-theme 이 안 닿고,
    #   도해는 OS 설정만 보고 있었다. 정하는 자리가 둘인데 서로 몰랐던 것.
    #   이제 테마마다 파일을 굽고 토글이 갈아끼운다. 여기서 그것을 다시 잰다.
    # 2026-09-14 site 세션이 잡았다. 「보존이 갱신도 막는다」.
    #   `assets/gnav-head.html` 은 lab 에 없고 배포본에서 뽑아 쓰는 스냅샷인데,
    #   지우지 않으려고 OTHER_MADE 에 넣어 둔 것이 **다시 굽는 것도 막았다.**
    #   그래서 바에 fh-figs 를 넣어도 스냅샷은 옛것이라, 그 스냅샷을 박아 쓰는
    #   페이지(report-v1)만 다크에서 도해가 안 갈렸다. 오류는 하나도 안 났다.
    #
    #   문자열을 찾지 않는다. **지금 배포본에서 다시 뽑아 바이트로 견준다.**
    #   그래서 다음에 바에 무엇이 더 붙어도 이 관문이 같이 잡는다.
    print('[3.478] 전역바 스냅샷이 지금 바와 같은가')
    import gnav_extract
    _nav, _css, _head = gnav_extract.extract(SITE)
    _stale = []
    for _n, _t in (('gnav.css', _css), ('gnav.html', _nav + '\n'),
                   ('gnav-head.html', _head)):
        _p = os.path.join(SITE, 'assets', _n)
        _old = (io.open(_p, encoding='utf-8').read()
                if os.path.isfile(_p) else None)
        if _old != _t:
            io.open(_p, 'w', encoding='utf-8').write(_t)
            _stale.append('%s (%d -> %d바이트)'
                          % (_n, len(_old.encode('utf-8')) if _old else 0,
                             len(_t.encode('utf-8'))))
    print('  스냅샷 3장 · 낡아서 다시 구운 것 %d장%s'
          % (len(_stale), (': ' + ' · '.join(_stale)) if _stale else ''))

    print('[3.477] 도해 테마 검사 (사이트 토글을 따라오는가)')
    import svg_theme
    _nt, _np, _plate = svg_theme.mark_pages(SITE)
    print('  표시: 테마 짝 %d곳 · 밝은 판 %d곳 (다크 색 미정 %d종)'
          % (_nt, _np, len(_plate)))
    if not svg_theme._selftest():
        print('  [!] 자기시험 실패. 이 검사를 믿을 수 없습니다'); sys.exit(1)
    if not svg_theme.check(SITE):
        print('  [!] 도해가 사이트 테마를 못 따라갑니다. 배포를 중단합니다.')
        print('      `python tools/svg_theme.py --write` 로 짝을 굽습니다')
        sys.exit(1)

    print('[3.475] 영상 규격 검사 (썸네일 · 폰 재생 속성)')
    import videocheck
    if not videocheck.main(SITE):
        print('  [!] 영상 규격이 어긋납니다. 배포를 중단합니다.')
        sys.exit(1)

    print('\n[3.48] 도해 글자 검사 (겹침 · 틀 밖)')
    import svgtext
    if not svgtext.main(VAULT):
        print('\n  [!] 도해 안에서 글자가 겹칩니다. 배포를 중단합니다.')
        sys.exit(1)
    print('[3.476] 렌더 검사 (마크다운 문법이 글자로 보이는가)')
    import rendercheck
    if not rendercheck.main(SITE):
        print('  [!] 문법이 글자로 보입니다. 배포를 중단합니다.')
        sys.exit(1)


    # ★ 2026-09-14 신설. 문서 표의 숫자를 원장과 «값으로» 대조한다.
    #   손으로 옮긴 숫자는 틀려도 소리가 안 난다. 표는 멀쩡해 보이고 빌드도
    #   통과하고 읽는 사람은 그 숫자를 믿는다. 문자열을 찾는 관문은 조작한
    #   보고서 5종을 다 통과시킨 적이 있어(2026-09-12) 이것은 재측정으로 만들었다.
    #   고의 오류 7종을 넣어 7/7 검출을 확인했다.
    print('\n[3.86] 문서 숫자 대조 (원장 실측과 같은가)')
    _cdn = os.path.join(os.path.dirname(VAULT), 'tools', 'check_doc_numbers.py')
    if not os.path.isfile(_cdn):
        print('  건너뜁니다 (대조기가 없습니다)')
    else:
        _r = subprocess.run([sys.executable, _cdn], capture_output=True,
                            text=True, encoding='utf-8', errors='replace')
        for _ln in ((_r.stdout or '') + (_r.stderr or '')).rstrip().split('\n'):
            if _ln.strip():
                print('  ' + _ln.strip())
        if _r.returncode != 0:
            print('\n  [!] 문서의 숫자가 원장과 다릅니다. 배포를 중단합니다.')
            sys.exit(1)

    print('\n[4] 민감정보 검사: 공개 저장소로 나갈 파일')
    import scan
    if not scan.report(SITE):
        sys.exit(1)

    if '--check' in sys.argv:
        sys.exit(0 if check() else 1)
