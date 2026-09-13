# -*- coding: utf-8 -*-
"""팀 전용 자료실 (빌드 [1.895] 단계). 팀장 지시 2026-08-20.

  왜: 조선대가 준 수업 자료(OT pptx · ROS2 구축 pdf)는 조선대 저작물이라
      공개 웹에 평문으로 올릴 수 없다. 팀원은 웹에서 바로 봐야 한다.
  어떻게: 볼트 chosun/ 의 파일을 AES-GCM 으로 암호화해 assets/secure/ 에 싣고,
      chosun-materials.html 이 브라우저(WebCrypto)에서 비밀번호로 복호화한다.
      PDF 는 blob 으로 페이지 안에서 바로 열리고, pptx 는 복호화 다운로드.
  비밀번호: 저장소에 없다. 로컬 파일(~/.claude/channels/foothold-docs-pass.txt)에서만 읽고,
      파일이 없으면 암호화 재생성을 건너뛴다(기존 산출물 유지) — 노트북 빌드 대응.
"""
import io
import json
import os
import struct

HERE = os.path.dirname(os.path.abspath(__file__))
VAULT = os.path.dirname(HERE)
SRC = __import__('roots').chosun() or os.path.join(VAULT, '07_chosun')
OUT_DIR = os.path.join(VAULT, 'assets', 'secure')
PASS_FILE = os.path.expanduser(r'~\.claude\channels\foothold-docs-pass.txt')

PBKDF2_ITERS = 250000

# 자료 목록: (원본 파일, 제목, 인라인 보기용 PDF(None=원본이 PDF/불가), 등록일, 갈래)
#   pptx 는 «원본.pptx + _view.pdf 변환본» 쌍으로 둔다. 변환본이 chosun/ 에 있으면 자동 연결.
#
#   갈래 (2026-08-26 추가): 'chosun' = 조선대 강의 자료 · 'budget' = 팀 내부 예산.
#   같은 암호·같은 저장소를 쓰되 **보이는 페이지를 가른다.** 예산은 금액이 들어 있어
#   자료실을 여는 모든 팀원에게 무심코 노출되면 안 된다.
ITEMS = [
    ('00_OT_ROS2_Go2_오리엔테이션.pptx', 'OT · ROS2 & Go2 오리엔테이션 (이수혁)',
     '00_OT_ROS2_Go2_오리엔테이션_view.pdf', '2026-08-13', 'chosun'),
    ('01_ROS2_개발환경_구축.pdf', 'ROS2 개발환경 구축 (Ubuntu 24.04)', None, '2026-08-20', 'chosun'),
    ('02_ROS2_Python_프로그래밍.pdf', 'ROS2 Python 프로그래밍 (rclpy 실전 · 50p)', None, '2026-08-23', 'chosun'),
    ('03_TF_좌표계_RViz2_시각화.pdf', 'TF 좌표계 · RViz2 시각화', None, '2026-08-26', 'chosun'),
    # ★ 2026-08-28 신설. 조선대가 강의 PDF 4종을 저장소에서 지우고 이 HTML
    #   런북 하나로 갈아탔다. 지금 강의를 따라가는 데 필요한 정본은 이것이다.
    #   (우리가 가진 PDF 4종은 그대로 둔다. 조선대가 지웠다고 우리가 지울 이유가 없다)
    ('ros2_lecture/ros2_5-25_guide.html', 'ROS2 5~25강 실습 런북 (24절 · 조선대 개편본)',
     None, '2026-08-28', 'chosun'),
    # 실습 코드 전체. 빌드가 미러에서 매번 새로 묶는다 (손 사본 아님).
    #   go2 실습 zip 4종은 upstream 에서 사라진 것을 회수한 것이라 여기가 정본이다.
    ('zip:ros2_lecture', 'ROS2 실습 코드 전체 (설치 스크립트 · 예제 · go2 실습 4종)',
     None, '2026-08-28', 'chosun'),
    ('BUDGET-20260821_예산계획.pdf', '팀 내부 · 예산 계획 v1 (1인 배분표)', None, '2026-08-21', 'budget'),
]

# ★ 2026-08-28. 8/26 에는 실습 코드를 자료실에 «안 넣기로» 했다. 근거 셋이었다.
#   (1) 코드는 읽는 게 아니라 빌드해서 돌린다  (2) 우리 사본은 곧 낡는다
#   (3) 원본을 가리키기만 하는 편이 저작권상 안전하다
#
#   **(3)이 무너졌다.** 조선대가 이력을 통째로 갈아엎어 go2 실습 zip 4종이
#   upstream 에서 사라졌다. 가리킬 원본이 없다. 팀장 노트북 클론에서 회수했다 (#87).
#   가리키기는 이제 «안전» 이 아니라 «위험» 이다.
#
#   그래서 코드도 자료실에 둔다. 다만 (2)는 지킨다. **손으로 사본을 두지 않는다.**
#   빌드가 미러 폴더를 매번 새로 묶으므로(`zip:` 항목) 낡을 수가 없다.
#   (1)도 지킨다. 90개를 낱개로 받게 하지 않고 한 덩이로 준다.
#   저장소를 클론해 쓰는 길은 그대로 안내한다. 자료실은 «없어졌을 때의 보루» 다.
LECTURE_REPO = 'https://github.com/slihump/ros2_lecture'

# 항목별 원본 폴더: 기본은 SRC(조선대), 없으면 04_plan(팀 내부 문서)에서 찾는다 (2026-08-21)
SRC2 = os.path.join(__import__('roots').proj(), '04_plan')


def _pack(rel_dir):
    """미러 폴더를 zip 한 덩이로 묶는다. (파일이름, 바이트) · 없으면 None

    ★ 2026-08-28. 8/26 에는 실습 코드를 자료실에 안 넣기로 했다. 근거 셋 중
      하나가 「원본을 가리키는 편이 안전하다」였는데, **그 원본이 사라졌다.**
      조선대가 이력을 갈아엎어 go2 실습 zip 4종이 upstream 에서 없어졌고
      팀장 노트북 클론에서 겨우 회수했다 (#87).

      그래서 코드도 자료실에 둔다. 다만 **사본을 손으로 두지 않는다.**
      빌드가 미러에서 매번 새로 묶으므로 낡지 않는다 (8/26 근거 2 를 지킨다).
    """
    import io as _io
    import zipfile
    root = os.path.join(SRC, *rel_dir.split('/'))
    if not os.path.isdir(root):
        return None
    buf = _io.BytesIO()
    n_files = 0
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as z:
        for d, _dirs, fs in os.walk(root):
            _dirs[:] = [x for x in _dirs if x != '.git']
            for f in sorted(fs):
                full = os.path.join(d, f)
                # 4.5MB 런북은 따로 올리므로 묶음에서 뺀다
                if f == 'ros2_5-25_guide.html':
                    continue
                arc = os.path.relpath(full, root).replace(os.sep, '/')
                z.write(full, arc)
                n_files += 1
    return n_files, buf.getvalue()


# ★ 2026-09-02 (mai-os#22 묶음 6.6). 암호화 자체는 enc_reuse 가 맡는다.
#   전에는 여기서 빌드마다 salt 를 새로 만들고 전부 다시 암호화했다. 원본이
#   하나도 안 바뀐 날에도 `.enc` 아홉 개가 통째로 달라져, 「이 빌드가 무엇을
#   바꿨는가」를 물을 수 없었다. 난수성은 그대로다 (salt·nonce 는 os.urandom).
#   바뀐 것은 «언제 다시 암호화하는가» 뿐이다.
#
#   ★ 캐시(`enc_cache.json`) 의 지위 · 팀장 결정 2026-09-02
#     · **비공개 로컬 상태다.** 비밀 원문도 비밀번호도 담지 않는다.
#       담는 것은 원문의 sha256 과 크기, 그리고 지금 쓰는 salt 다.
#     · **git 에 올리지 않는다.** 저장소 `.gitignore` 에 정확한 경로로 등록돼 있다.
#     · **공개 배포 대상이 아니다.** `_build` 는 배포 제외 목록(NEVER)에 있다.
#     · **NAS 공개 동기화 대상도 아니다.**
#     · 캐시가 없는 장비는 **최초 한 번 전부 재암호화**한다. 그것이 정상 동작이다.
#     · 따라서 **암호문 바이트의 장비 간 동일성은 보장 대상이 아니다.**
#       재사용이 보장하는 것은 «같은 장비의 같은 작업 공간에서, 입력이 같으면
#       암호문이 그대로» 라는 것뿐이다.
CACHE_PATH = os.path.join(HERE, 'enc_cache.json')   # 비공개. _build 는 배포 제외

# 자료실 페이지 둘. 같은 암호·같은 저장소를 쓰되 «보이는 항목» 을 갈래로 가른다.
#   금액이 든 문서가 자료실을 여는 모든 팀원에게 무심코 보이면 안 된다.
SECURE_PAGES = (
    ('chosun-materials.html', 'chosun', '팀 자료실 (조선대)',
     '팀 자료실 · 조선대 제공 수업 자료',
     '이 자료는 조선대학교 측 저작물입니다. <b>팀 내부 열람용</b>으로만 제공하며 '
     '비밀번호로 보호됩니다 (비밀번호는 디스코드 리소스 채널). 외부 공유 금지.',
     ''),
    ('budget.html', 'budget', '예산안',
     '예산안 · 프로젝트 지원금 사용 계획',
     '프로젝트 지원금 사용 계획입니다. <b>금액은 대외비</b>이며 자료실과 같은 '
     '비밀번호로 보호됩니다. 절차는 1차·2차·3차 승인을 받고 결제한 뒤 정산입니다.',
     ''),
)


def render_secure_pages(vault=None, out_dir=None):
    """공개 HTML 껍데기를 «순수·결정론적» 으로 만든다 (mai-os#24 · 팀장 결정 2026-09-02).

      ★ 이 함수가 하지 않는 것 (재현 모드에서 호출되므로 경계가 엄격하다)
        비밀번호 읽기 · 보호 문서 평문 읽기 · salt·nonce 생성 · 재암호화 ·
        `.enc` 생성·수정 · `enc_cache.json` 수정 · `.secure-owner` 생성·수정 ·
        manifest 수정 · 실제 볼트나 실제 배포본 수정

      ★ 이 함수가 하는 것
        기존 manifest 를 **읽기 전용** 으로 확인하고, 템플릿에서 HTML 두 장을 쓴다.
        쓰는 곳은 `vault` 뿐이다 (재현 모드에서는 그 vault 자체가 격리 사본이다).

      ★ 오래된 HTML 로 물러서지 않는다
        manifest 가 없거나 · 가리키는 암호문이 없거나 · 태그가 안 맞으면 **실패**한다.
        「예전 것을 그대로 두고 통과」는 조용한 실패다 (원칙 2).
    """
    vault = vault or VAULT
    out_dir = out_dir or os.path.join(vault, 'assets', 'secure')
    man_path = os.path.join(out_dir, 'manifest.json')
    if not os.path.exists(man_path):
        print('  [!] manifest 가 없습니다: %s' % man_path)
        print('      오래된 HTML 로 물러서지 않습니다. 암호화 자산을 먼저 갖추세요')
        return False
    try:
        man = json.load(io.open(man_path, encoding='utf-8'))
    except Exception as e:
        print('  [!] manifest 를 못 읽습니다: %s' % e)
        return False
    # manifest 가 가리키는 암호문이 실제로 있는가 · 태그가 맞는가
    import hashlib
    tags = man.get('tags') or {}
    refs = [it['file'] for it in (man.get('items') or []) if it.get('file')]
    refs += [it['view'] for it in (man.get('items') or []) if it.get('view')]
    refs += list((man.get('notes') or {}).values())
    bad = []
    for rel in sorted(set(refs)):
        p = os.path.join(vault, *rel.split('/'))
        if not os.path.exists(p):
            bad.append('%s 없음' % rel)
            continue
        want = tags.get(rel)
        if want:
            got = hashlib.sha256(io.open(p, 'rb').read()).hexdigest()[:8]
            if got != want:
                bad.append('%s 태그 불일치 (%s != %s)' % (rel, got, want))
    if bad:
        print('  [!] manifest 와 암호문이 어긋납니다 %d건' % len(bad))
        for b in bad[:6]:
            print('     ' + b)
        return False
    made = []
    for out, kind, title, heading, lede, extra in SECURE_PAGES:
        page = (PAGE_TMPL.replace('__KIND__', kind).replace('__TITLE__', title)
                .replace('__HEADING__', heading).replace('__LEDE__', lede)
                .replace('__EXTRA__', extra))
        io.open(os.path.join(vault, out), 'w', encoding='utf-8',
                newline='\n').write(page)
        made.append(out)
    print('  %s 생성 (템플릿에서 결정론적으로 · 암호화 없음)' % ' · '.join(made))
    return True


def _kat_render():
    """★ 답을 아는 입력. 순수 렌더가 경계를 지키는지 본다."""
    import tempfile, json as _j, hashlib as _h
    with tempfile.TemporaryDirectory() as d:
        sec = os.path.join(d, 'assets', 'secure')
        os.makedirs(sec)
        # manifest 가 없으면 실패해야 한다 (옛 HTML 로 물러서지 않는다)
        if render_secure_pages(d):
            return False, 'manifest 가 없는데 통과함'
        blob = b'ciphertext'
        io.open(os.path.join(sec, 'a.enc'), 'wb').write(blob)
        tag = _h.sha256(blob).hexdigest()[:8]
        man = {'salt': '00', 'iters': 1, 'check': '00',
               'items': [{'file': 'assets/secure/a.enc'}], 'notes': {},
               'tags': {'assets/secure/a.enc': tag}}
        io.open(os.path.join(sec, 'manifest.json'), 'w',
                encoding='utf-8').write(_j.dumps(man))
        if not render_secure_pages(d):
            return False, '성한 manifest 인데 실패함'
        for out, *_ in SECURE_PAGES:
            if not os.path.exists(os.path.join(d, out)):
                return False, '%s 를 안 만들었다' % out
        # 두 번 불러도 바이트가 같아야 한다 (결정론)
        first = io.open(os.path.join(d, SECURE_PAGES[0][0]), 'rb').read()
        render_secure_pages(d)
        if io.open(os.path.join(d, SECURE_PAGES[0][0]), 'rb').read() != first:
            return False, '두 번 부르면 결과가 달라진다'
        # 암호문이 사라지면 실패
        os.remove(os.path.join(sec, 'a.enc'))
        if render_secure_pages(d):
            return False, '암호문이 없는데 통과함'
        # 태그가 틀리면 실패
        io.open(os.path.join(sec, 'a.enc'), 'wb').write(b'different')
        if render_secure_pages(d):
            return False, '태그가 틀린데 통과함'
        # .enc 와 manifest 를 건드리지 않았는가
        before = _h.sha256(io.open(os.path.join(sec, 'manifest.json'), 'rb').read()).hexdigest()
        io.open(os.path.join(sec, 'a.enc'), 'wb').write(blob)
        render_secure_pages(d)
        after = _h.sha256(io.open(os.path.join(sec, 'manifest.json'), 'rb').read()).hexdigest()
        if before != after:
            return False, 'manifest 를 건드렸다'
        if os.path.exists(os.path.join(os.path.dirname(sec), 'enc_cache.json')):
            return False, '캐시를 만들었다'
    return True, ''


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    ok, why = _kat_render()
    if not ok:
        print('  [!] 자료실 렌더 자기시험 실패: %s' % why)
        return False
    import enc_reuse
    # ★ secure 생성은 «지정된 release 작업 공간» 이 소유한다 (팀장 결정 2026-09-02).
    #   캐시는 git 에 안 올라가므로 워크트리·다른 장비·A/B 사본에는 따라가지
    #   않는다. 그런 곳에서 돌리면 매번 새 salt 로 전부 재암호화하고,
    #   그 결과가 릴리스본과 어긋난 채 배포될 수 있다.
    owner = enc_reuse.is_release_workspace(HERE)
    if not owner:
        print('  이 작업 공간은 secure 소유자가 아닙니다 (기존 산출물 유지)')
        print('     릴리스 공간에서만 돕니다 · _build/.secure-owner 또는 '
              'FOOTHOLD_SECURE_OWNER')
    have_pass = owner and os.path.exists(PASS_FILE)
    manifest = []
    if have_pass:
        ok, why = enc_reuse._kat()
        if not ok:
            print('  [!] 암호문 재사용 자기시험 실패: %s' % why)
            return False
        password = io.open(PASS_FILE, encoding='utf-8').read().strip()
        sess = enc_reuse.Session(OUT_DIR, CACHE_PATH, password, PBKDF2_ITERS)
        print('  %s' % sess.reason)
        for no, (rel, title, viewfn, added, kind) in enumerate(ITEMS, 1):
            # ★ 2026-08-28. ITEMS 항목이 하위 폴더를 가리킬 수 있게 했다.
            #   조선대 미러(`07_chosun/ros2_lecture/`)의 파일을 자료실에 올리려면
            #   필요하다. 사본을 07_chosun 밑에 또 두면 곧 갈라진다.
            #   내려받는 이름과 암호 파일 이름은 basename 을 쓴다.
            if rel.startswith('zip:'):
                packed = _pack(rel[4:])
                if not packed:
                    print('  [!] 묶을 폴더 없음, 건너뜀: %s' % rel)
                    continue
                n_files, data = packed
                fn = rel[4:].split('/')[-1] + '_실습코드.zip'
                sess.put(fn + '.enc', data)
                manifest.append({'no': '%02d' % no,
                                 'file': 'assets/secure/' + fn + '.enc',
                                 'name': fn, 'title': '%s · %d개 파일' % (title, n_files),
                                 'size': len(data), 'added': added, 'kind': kind,
                                 'view': None, 'vkind': None})
                continue
            fn = os.path.basename(rel)
            src = os.path.join(SRC, *rel.split('/'))
            if not os.path.exists(src):
                src = os.path.join(SRC2, *rel.split('/'))
            if not os.path.exists(src):
                print('  [!] 원본 없음, 건너뜀: %s' % rel)
                continue
            data = io.open(src, 'rb').read()
            sess.put(fn + '.enc', data)
            item = {'no': '%02d' % no, 'file': 'assets/secure/' + fn + '.enc', 'name': fn,
                    'title': title, 'size': len(data), 'added': added,
                    'kind': kind, 'view': None}
            # PDF 는 그림으로 그려 보여주고, HTML 은 새 탭으로 연다. 둘 다 «보기» 대상이다.
            #
            # ★ 형식을 여기서 «명시»해 싣는다. 화면 쪽에서 파일 이름으로 알아내지
            #   않는다. 실제로 그렇게 짰다가 잡았다: 실린 이름이 `....pdf.enc` 라
            #   `endsWith('.pdf')` 가 **전부 거짓**이 되어 PDF 5종의 인라인 보기가
            #   통째로 죽을 뻔했다. 추측하지 말고 아는 쪽이 적어 보낸다.
            item['vkind'] = None
            if fn.lower().endswith('.pdf'):
                item['view'], item['vkind'] = item['file'], 'pdf'
            elif fn.lower().endswith('.html'):
                item['view'], item['vkind'] = item['file'], 'html'
            elif viewfn and os.path.exists(os.path.join(SRC, viewfn)):
                vdata = io.open(os.path.join(SRC, viewfn), 'rb').read()
                sess.put(viewfn + '.enc', vdata)
                item['view'] = 'assets/secure/' + viewfn + '.enc'
                item['vkind'] = 'pdf' if viewfn.lower().endswith('.pdf') else 'html'
            manifest.append(item)
        # ★ 저장소 안내(조선대 실습 코드 주소 · 담당자 실명)도 암호 뒤에 둔다.
        #   전에는 페이지 평문 HTML 에 있어서 «소스 보기» 만 해도 보였다.
        #   팀장이 「암호 뒤로」라고 한 그 링크가 공개돼 있었다 (2026-08-27 감사).
        notes = {}
        for kind, html in NOTES.items():
            fn = 'note-%s.enc' % kind
            sess.put(fn, html.encode('utf-8'))
            notes[kind] = 'assets/secure/' + fn
        # ★ 원자적 교체. 새 벌을 다 만든 뒤 한 번에 바꾼다
        reused, fresh = sess.commit({'items': manifest, 'notes': notes})
        print('  암호화 %d건 (AES-GCM, PBKDF2 %d회) · 재사용 %d · 새로 %d'
              % (len(manifest), PBKDF2_ITERS, reused, fresh))
    else:
        # ★ 왜 안 돌았는지 «정확히» 적는다. 이유를 뭉뚱그리면 다음 사람이
        #   비밀번호를 찾아 헤맨다. 실제로는 소유자가 아니었을 뿐일 수 있다.
        why = ('릴리스 소유 작업 공간이 아님' if not owner
               else '비밀번호 파일 없음')
        if not os.path.exists(os.path.join(OUT_DIR, 'manifest.json')):
            print('  [!] %s · 기존 산출물도 없음. 자료실 페이지 생성 건너뜀' % why)
            return True
        print('  %s: 기존 암호화 산출물 유지 (재생성 건너뜀)' % why)

    return render_secure_pages() is not False


# 조선대 실습 코드는 저장소를 그대로 쓴다. 자료실 페이지에 길만 놓는다.
#   PDF 와 달리 코드는 읽는 게 아니라 빌드해서 돌린다. 사본을 두면 곧 낡는다.
_REPO_BOX = '''<div class="item" style="background:var(--dim-soft,#e6f2ef)">
<b>실습 코드는 저장소에서 바로 받습니다</b>
<div class="m">PDF 와 달리 코드는 읽는 게 아니라 빌드해서 돌립니다. 여기 사본을 두면
조선대가 갱신할 때마다 낡습니다. 원본을 그대로 씁니다.</div>
<pre style="background:var(--paper,#f4f2ec);border:1px solid var(--rule,#d8d4c8);
border-radius:5px;padding:.7rem .9rem;font-size:.82rem;overflow-x:auto;margin:.4rem 0"
>git clone https://github.com/slihump/ros2_lecture.git
cd ros2_lecture/ubuntu_practice</pre>
<div class="m">설치 스크립트는 <code>00_setup_scripts/</code>, ROS2 실습 패키지는
<code>ros2_ws/src/</code> 에 있습니다. 갱신은 <code>git pull</code> 한 번입니다.
접근이 안 되면 조선대 이수혁 팀장에게 계정 권한을 요청하세요.</div>
<a href="https://github.com/slihump/ros2_lecture" target="_blank" rel="noopener"
   style="display:inline-block;margin-top:.3rem;padding:.4rem .9rem;font-weight:700;
   border:1px solid var(--dim,#0e7a6e);border-radius:5px;color:var(--dim,#0e7a6e);
   text-decoration:none">저장소 열기</a>
</div>'''

# 암호 해제 뒤에만 주입되는 안내. 평문 HTML 에 두지 않는다.
NOTES = {'chosun': _REPO_BOX}



PAGE_TMPL = '''<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex">
<title>__TITLE__ · FOOTHOLD</title>
<style>
body{font-family:'Pretendard','Malgun Gothic','Segoe UI',system-ui,sans-serif;
  background:var(--paper,#f4f2ec);color:var(--ink,#16202a);margin:0;font-size:15px}
.top{position:sticky;top:0;z-index:60;background:var(--paper,#f4f2ec);
  border-bottom:1px solid var(--rule,#d8d4c8)}
.top .row{max-width:1040px;margin:0 auto;padding:.6rem 1.2rem;display:flex;
  align-items:center;gap:.9rem}
.top a{color:inherit;text-decoration:none;font-weight:700;font-size:.85rem}
.wrap{max-width:1040px;margin:0 auto;padding:28px 20px 80px}
h1{font-size:32px;font-weight:800;letter-spacing:-.02em;line-height:1.25;
  margin:.3em 0 .35em}
.note{font-size:15px;color:var(--ink-2,#3d4a58);line-height:1.75}
.gatebox{display:flex;align-items:center;justify-content:center;
  min-height:max(300px, calc(100vh - 21rem));padding:1.5rem 0}
.gate{border:1px solid var(--rule,#d8d4c8);
  background:var(--card,#fbfaf6);padding:26px 24px;border-radius:8px;
  width:100%;max-width:440px}
.gate>b{font-size:.9rem;letter-spacing:-.01em}
.gate input{width:100%;box-sizing:border-box;padding:.6rem .8rem;font-size:16px;border:1px solid var(--rule,#d8d4c8);
  border-radius:5px;margin:.4rem 0;background:var(--paper,#fff);color:inherit}
.gate button{padding:.55rem 1.2rem;font-weight:800;border:none;border-radius:5px;
  background:var(--dim,#0e7a6e);color:#fff;cursor:pointer;font-size:.9rem}
.gate .err{color:#b3452c;font-size:.8rem;min-height:1.2em}
.item{border:1px solid var(--rule,#d8d4c8);border-radius:8px;background:var(--card,#fbfaf6);
  padding:16px 18px;margin:14px 0}
.item .no{display:inline-block;background:var(--ink,#16202a);color:var(--paper,#fff);font-size:.68rem;font-weight:800;padding:.15rem .45rem;border-radius:3px;margin-right:.55rem;letter-spacing:.06em;vertical-align:.08em}
.item b{font-size:.98rem}
.item .m{font-size:.75rem;color:var(--ink-3,#6b7683);margin:.2rem 0 .6rem}
.item button{margin-right:.5rem;padding:.4rem .9rem;font-weight:700;border:1px solid var(--dim,#0e7a6e);
  border-radius:5px;background:transparent;color:var(--dim,#0e7a6e);cursor:pointer}
.pdfbox{margin-top:10px;max-height:82vh;overflow-y:auto;border-radius:6px}
#list{display:none}
</style>
</head>
<body>
<div class="top"><div class="row"><a href="index.html">← 표지로</a>
<span style="font-size:.8rem;color:#6b7683">FOOTHOLD · __TITLE__</span></div></div>
<div class="wrap">
<h1>__HEADING__</h1>
<p class="note">__LEDE__</p>

<div class="gatebox" id="gatebox">
<div class="gate" id="gate">
  <b>비밀번호</b>
  <input type="password" id="pw" placeholder="팀 비밀번호" autocomplete="off">
  <div class="err" id="err"></div>
  <button id="go">열기</button>
</div>
</div>

<div id="list"></div>
<div id="extra"></div>
__EXTRA__
</div>
<script>
let MAN=null, KEY=null;
async function loadMan(){
  if(!MAN) MAN = await (await fetch('assets/secure/manifest.json?t='+Date.now(), {cache:'no-store'})).json();
  return MAN;
}
async function deriveKey(pw, saltHex, iters){
  const salt = Uint8Array.from(saltHex.match(/../g).map(h=>parseInt(h,16)));
  const base = await crypto.subtle.importKey('raw', new TextEncoder().encode(pw),
    'PBKDF2', false, ['deriveKey']);
  return crypto.subtle.deriveKey({name:'PBKDF2', salt, iterations:iters, hash:'SHA-256'},
    base, {name:'AES-GCM', length:256}, false, ['decrypt']);
}
// 캐시 버스터는 «파일마다» 다르다 (mai-os#22 묶음 6.6).
//   전에는 salt 앞자리를 썼다. 그때는 빌드마다 salt 가 새로 나왔으니 그것이
//   곧 «이 빌드의 판» 이었다. 이제 입력이 같으면 salt 를 이어쓰므로, 바뀐
//   파일 하나가 옛 주소를 그대로 갖게 되어 브라우저가 옛 암호문을 붙잡는다.
//   그래서 manifest 가 파일별 태그(v)를 싣고, 없으면 salt 로 물러선다.
//   태그는 «암호문» 의 해시 앞자리다. 내려받으면 누구나 계산할 수 있는 값이라
//   원문에 대해 아무것도 말하지 않는다.
function _tag(url){
  if(MAN.tags && MAN.tags[url]) return MAN.tags[url];
  return MAN.salt.slice(0,8);
}
async function decryptFile(url){
  const buf = new Uint8Array(await (await fetch(url+'?v='+_tag(url), {cache:'no-store'})).arrayBuffer());
  const nonce = buf.slice(0,12), ct = buf.slice(12);
  return new Uint8Array(await crypto.subtle.decrypt({name:'AES-GCM', iv:nonce}, KEY, ct));
}
document.getElementById('go').addEventListener('click', async ()=>{
  const err = document.getElementById('err'); err.textContent='';
  try{
    const man = await loadMan();
    KEY = await deriveKey(document.getElementById('pw').value, man.salt, man.iters);
    const cb = Uint8Array.from(man.check.match(/../g).map(h=>parseInt(h,16)));
    await crypto.subtle.decrypt({name:'AES-GCM', iv:cb.slice(0,12)}, KEY, cb.slice(12));
  }catch(e){ err.textContent='비밀번호가 맞지 않습니다.'; KEY=null; return; }
  // 앵커(gatebox)째로 숨긴다. gate 만 숨기면 min-height 380px 빈칸이 남는다
  document.getElementById('gatebox').style.display='none';
  const list = document.getElementById('list'); list.style.display='block';
  const KIND='__KIND__';
  // 암호 뒤에 둔 안내(저장소 주소 · 담당자). 해제해야만 보인다.
  if(MAN.notes && MAN.notes[KIND]){
    try{
      const nb = await decryptFile(MAN.notes[KIND]);
      document.getElementById('extra').innerHTML = new TextDecoder().decode(nb);
    }catch(e){ console.error('note', e); }
  }
  for(const it of MAN.items.filter(x=>(x.kind||'chosun')===KIND)){
    const d = document.createElement('div'); d.className='item';
    d.innerHTML = '<span class="no">'+it.no+'</span><b>'+it.title+'</b>'
      +'<div class="m">'+it.name+' · '+(it.size/1048576).toFixed(1)+' MB · 등록 '+it.added+'</div>';
    const dl = document.createElement('button'); dl.textContent='다운로드 (원본)';
    dl.onclick = async ()=>{
      const data = await decryptFile(it.file);
      const a = document.createElement('a');
      a.href = URL.createObjectURL(new Blob([data]));
      a.download = it.name; a.click();
    };
    d.appendChild(dl);
    // 2026-08-28: 자료실이 PDF 만 다룰 수 있었다. 조선대가 강의 PDF 4종을 지우고
    //   4.5MB 짜리 HTML 런북 하나로 갈아탔으므로 형식을 넓힌다.
    //   그림으로 그려 보여주는 것(pdf.js)은 PDF 에만 되고, HTML 은 새 탭으로 연다.
    const isPdf = it.vkind === 'pdf';
    if(it.view && isPdf){
      const v = document.createElement('button'); v.textContent='여기서 보기';
      v.onclick = async ()=>{
        let box = d.querySelector('.pdfbox');
        if(box){ box.remove(); d.querySelector('.close').remove(); return; }
        v.disabled = true; v.textContent = '여는 중...';
        try{
          const data = await decryptFile(it.view);
          const pdfjs = await import('/assets/vendor/pdfjs/pdf.min.mjs');
          pdfjs.GlobalWorkerOptions.workerSrc = '/assets/vendor/pdfjs/pdf.worker.min.mjs';
          const doc = await pdfjs.getDocument({data}).promise;
          box = document.createElement('div'); box.className='pdfbox';
          const cl = document.createElement('button'); cl.className='close';
          cl.textContent='닫기'; cl.style.display='block'; cl.style.margin='8px 0';
          cl.onclick = ()=>{ box.remove(); cl.remove(); };
          d.appendChild(box); d.appendChild(cl);
          const wpx = Math.min(d.clientWidth - 4, 920);
          for(let n=1; n<=doc.numPages; n++){
            const pg = await doc.getPage(n);
            const base = pg.getViewport({scale:1});
            const scale = wpx / base.width * (window.devicePixelRatio||1);
            const vp = pg.getViewport({scale});
            const cv = document.createElement('canvas');
            cv.width = vp.width; cv.height = vp.height;
            cv.style.width = '100%'; cv.style.display='block';
            cv.style.border = '1px solid var(--rule,#d8d4c8)'; cv.style.marginBottom='6px';
            box.appendChild(cv);
            await pg.render({canvasContext:cv.getContext('2d'), viewport:vp}).promise;
          }
        }catch(e){ const er=document.createElement('div'); er.style.cssText='color:#b3452c;font-size:.8rem;margin-top:6px'; er.textContent='열기 실패: '+e.message; d.appendChild(er); console.error('viewer', e); }
        v.disabled = false; v.textContent = '여기서 보기';
      };
      d.appendChild(v);
    }
    if(it.view){
      // ★ 2026-08-28. HTML 은 «여기서 보기» 를 먼저 준다. 모바일에서 새 탭이
      //   팝업 차단에 막히기 때문이다 (팀장 실사용에서 확인).
      if(!isPdf){
        const hv = document.createElement('button'); hv.textContent='여기서 보기';
        hv.onclick = async ()=>{
          let box = d.querySelector('.htmlbox');
          if(box){ box.remove(); const c=d.querySelector('.hclose'); if(c) c.remove(); return; }
          hv.disabled = true; hv.textContent = '여는 중...';
          try{
            const data = await decryptFile(it.view);
            const url = URL.createObjectURL(new Blob([data],{type:'text/html;charset=utf-8'}));
            box = document.createElement('iframe'); box.className='htmlbox';
            box.src = url; box.setAttribute('sandbox','allow-scripts');
            box.style.cssText='display:block;width:100%;height:78vh;margin-top:10px;border:1px solid var(--rule,#d8d4c8);border-radius:6px;background:#fff';
            const cl = document.createElement('button'); cl.className='hclose';
            cl.textContent='닫기'; cl.style.cssText='display:block;margin:8px 0';
            cl.onclick = ()=>{ box.remove(); cl.remove(); URL.revokeObjectURL(url); };
            d.appendChild(box); d.appendChild(cl);
          }catch(e){ const er=document.createElement('div');
            er.style.cssText='color:#b3452c;font-size:.8rem;margin-top:6px';
            er.textContent='열기 실패: '+e.message; d.appendChild(er); }
          hv.disabled = false; hv.textContent = '여기서 보기';
        };
        d.appendChild(hv);
      }
      const nt = document.createElement('button'); nt.textContent='새 탭에서 보기';
      nt.onclick = async ()=>{
        // ★ 창을 «먼저» 연다. 복호화(await) 뒤에 열면 사용자 제스처 맥락이
        //   끊겨 모바일 브라우저가 팝업으로 막는다. 실제로 막혔다.
        const w = window.open('', '_blank');
        nt.disabled = true; nt.textContent = '여는 중...';
        try{
          const data = await decryptFile(it.view);
          const mime = isPdf ? 'application/pdf' : 'text/html;charset=utf-8';
          const url = URL.createObjectURL(new Blob([data],{type:mime}));
          if(w && !w.closed){ w.location = url; }
          else { throw new Error('팝업이 막혔습니다. 위의 «여기서 보기» 를 쓰세요'); }
        }catch(e){ if(w && !w.closed) w.close();
          const er=document.createElement('div');
          er.style.cssText='color:#b3452c;font-size:.8rem;margin-top:6px';
          er.textContent='열기 실패: '+e.message; d.appendChild(er); }
        nt.disabled = false; nt.textContent = '새 탭에서 보기';
      };
      d.appendChild(nt);
    }
    list.appendChild(d);
  }
});
document.getElementById('pw').addEventListener('keydown', e=>{
  if(e.key==='Enter') document.getElementById('go').click();
});
</script>
</body>
</html>
'''

if __name__ == '__main__':
    main()
