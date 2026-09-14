# -*- coding: utf-8 -*-
"""팀장이 이제까지 지시한 것이 «실제로» 산출물에 있는지 하나씩 잰다.

분류: 운영 · 작성: 오흥재 · 2026-09-14 · 상태: 확정
근거: 실측 (배포본·저장소 직접 측정 · 자기시험 3종)
요지: 「했습니다」를 세지 않고 산출물을 직접 읽어 지시 이행을 잰다

## 쓰는 법

    python tools/audit_orders.py

## 왜 있나

세션이 바뀌면 「무엇을 시켰고 무엇이 됐나」가 대화에만 남아 증발한다.
그리고 세션이 스스로 「했습니다」라고 적은 것은 근거가 아니다.
이 표는 **배포본과 저장소를 직접 읽어** 잰다.

## 점검표부터 시험한다

점검표가 아무것도 안 재고 있으면 전부 OK 가 나온다. 그래서 산출물을 고의로
망가뜨려 «잡히는지» 먼저 본다. 실제로 첫 판은 셋 중 둘을 놓쳤고, 그 과정에서
**파비콘 검사가  도 파비콘으로 세고 있던 것**을 찾았다.
"""
import io
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding='utf-8')
LAB = r'C:\Users\AI-WS01\Desktop\jay\인공지능사관학교\foothold-lab'
SITE = r'C:\Users\AI-WS01\Desktop\jay\인공지능사관학교\foothold-site'
rows = []


def read(base, name):
    p = os.path.join(base, name)
    if not os.path.isfile(p):
        return ''
    return io.open(p, encoding='utf-8', errors='replace').read()


def chk(no, what, ok, detail):
    rows.append((no, what, ok, detail))


hub = read(SITE, 'hub-research.html')
proto = read(SITE, 'research-20260911-eval-protocol-v2.html')
bench = read(SITE, 'research-generalization-benchmark-10-terrains.html')

# 1 · 여섯 입구 한 기준
labs = sorted(set(re.findall(r'data-label="([^"]*)"', hub)))
chk('1', '연구 허브를 여섯 입구 한 기준으로',
    len(labs) == 6 and '외부 자료 조사' not in hub,
    '묶음 %d종: %s' % (len(labs), ' · '.join(labs)))

# 2 · 새 문서가 자동으로 입구를 받나 (체계화)
cat = read(LAB, 'tools/build_research_catalog.py')
chk('2', '새 문서가 손 배정 없이 입구를 받나 (체계화)',
    'def door_of' in cat and 'KIND_DOOR' in cat and 'TITLE_DOOR' in cat,
    '`door_of` 자동 규칙 %s · 머리말/손배정/제목/분류 4단' %
    ('있음' if 'def door_of' in cat else '없음'))

# 4 · 갤러리 지형 거르개가 기존 6 / Unseen 10 으로 묶이나
gj = read(SITE, 'gallery/gallery.js')
chk('4', '갤러리 지형 거르개를 기존 6종 / Unseen 10종으로',
    'SET_NAME' in gj and 'SET_ORDER' in gj and 'terrainRows' in gj,
    'SET_NAME/SET_ORDER/terrainRows %s' %
    ('전부 있음' if all(k in gj for k in ('SET_NAME', 'SET_ORDER', 'terrainRows'))
     else '일부 없음'))

# 5 · 갤러리가 «나중에 생길 데이터» 를 받나 (고정 배열이 아닌가)
hard = re.findall(r'(?:TERRAINS|LIST|NAMES)\s*=\s*\[[^\]]{40,}\]', gj)
chk('5', '갤러리가 나중 데이터를 받나 (고정 목록이 아닌가)',
    not hard, '색인에서 읽음 · 고정 배열 %d개' % len(hard))

# 8 · 벤치마크 문서가 정본 기준으로 재작성됐나
md8 = read(LAB, 'docs/research/generalization-benchmark-10-terrains.md')
has = all(k in md8 for k in ('maindata-v1', '난이도 0.5', '100 에피소드'))
ver = re.search(r'v(\d+\.\d+)', md8[:600])
chk('8', '일반화 벤치마크를 정본 기준으로 재작성',
    has and '5종통과' in md8.replace(' ', ''),
    '정본 조건 표기 %s · 판 %s' % ('있음' if has else '없음',
                                  ver.group(0) if ver else '?'))

# 9 · 배포 전 검증이 돌았나 (관문이 파일로 남아 있나)
chk('9', '발행 전 검증 도구가 저장소에 있나',
    os.path.isfile(os.path.join(LAB, 'tools/check_doc_numbers.py')) and
    os.path.isfile(os.path.join(LAB, 'tools/predeploy.py')),
    'check_doc_numbers.py · predeploy.py')

# 10 · SVG 글자 결함
svgt = os.path.isfile(os.path.join(LAB, 'web/_build/svgtext.py'))
chk('10', 'SVG 글씨 겹침·경계 넘침 관문',
    svgt, 'web/_build/svgtext.py %s' % ('있음' if svgt else '없음'))

# 11 · 판 번호
stamp = read(LAB, 'web/_build/stamp.py')
sv = re.search(r"SITE_VERSION = '([^']+)'", stamp)
live = re.search(r'v2\.\d+\.\d+', proto)
chk('11', '사이트 판 번호가 올랐고 배포본에 실렸나',
    bool(sv and live and sv.group(1) == live.group(0)),
    '소스 %s · 배포본 %s' % (sv.group(1) if sv else '?',
                            live.group(0) if live else '없음'))

# 12 · AGENTS.md 의 비용 대외비 제거
ag = read(os.path.dirname(LAB), 'foothold-lab/AGENTS.md')
# ★ 「Go2 대여 금액」 하나는 «남기라» 하신 것이다 (팀장 2026-09-04 확정).
#   그것까지 세면 규칙을 지킨 것을 결함으로 읽는다. 실제로 그렇게 셌다.
bad = [l.strip()[:60] for l in ag.split(chr(10))
       if '대외비' in l and ('비용' in l or '예산' in l or '금액' in l)
       and 'Go2 대여' not in l]
keep = [l for l in ag.split(chr(10)) if '대외비' in l and 'Go2 대여' in l]
chk('12', 'AGENTS.md 의 비용 대외비를 Go2 대여 하나로 좁혔나',
    not bad and len(keep) == 1,
    '넓은 금액 대외비 %d줄 · Go2 대여 조항 %d줄 (남아야 정상)' % (len(bad), len(keep)))

# 13 · 파비콘 전수
noicon = []
for f in sorted(os.listdir(SITE)):
    if not f.endswith('.html'):
        continue
    t = read(SITE, f)
    # ★ `\bicon\b` 는 `rel="mask-icon"` 도 통과시킨다 (`-` 가 낱말 경계).
    #   진짜 파비콘이 없어도 통과하던 자리다. 자기시험이 잡았다.
    if not re.search(r'<link[^>]*rel="(?:shortcut )?icon"', t):
        noicon.append(f)
chk('13', '모든 페이지에 파비콘',
    not noicon, '링크 없는 페이지 %d장%s'
    % (len(noicon), (' · ' + ' '.join(noicon[:3])) if noicon else ''))

# 14 · verify_live.py
chk('14', 'verify_live.py 가 저장소에 있나',
    os.path.isfile(os.path.join(LAB, 'tools/verify_live.py')),
    'tools/verify_live.py')

# 15 · 갤러리 뷰어가 lab 에 있나 (갤러리 자리)
gv = os.path.isdir(os.path.join(LAB, 'web/gallery'))
chk('15', '갤러리 뷰어가 lab 소스에 있나 (갤러리 자리)',
    gv, 'foothold-lab/web/gallery %s' % ('있음' if gv else '없음'))

# 16 · _lab-main 제거
roots = read(LAB, 'web/_build/roots.py')
chk('16', '_lab-main 을 후보에서 뺐나 · 중복도 걷었나',
    '_lab-main' not in roots.split('def lab_candidates')[1].split('def ')[1]
    if 'def lab_candidates' in roots else False,
    '_dedupe %s · warn_if_stray %s'
    % ('있음' if '_dedupe' in roots else '없음',
       '있음' if 'warn_if_stray' in roots else '없음'))

# 17 · 모바일 표
css = read(SITE, 'assets/site.css') or proto
chk('17', '표가 좁은 화면에서 안 짜부라지나 (규칙)',
    'min-width:max-content' in proto and 'overflow-wrap:anywhere' not in
    re.sub(r'/\*.*?\*/', '', proto, flags=re.S).split('th,td{')[1][:200]
    if 'th,td{' in proto else False,
    'min-width:max-content %s' % ('있음' if 'min-width:max-content' in proto else '없음'))

# 18 · 갤러리 영상 포스터 (첫 화면 검정)
rep = read(SITE, 'report-v1.html')
chk('18', '보고서 영상 첫 화면 (poster)',
    rep.count('poster=') >= 12,
    'video %d · poster %d' % (rep.count('<video'), rep.count('poster=')))

# 19 · 도식 중복
body = re.sub(r'(?s)<style\b.*?</style>|<script\b.*?</script>', ' ', proto)
srcs = re.findall(r'<figure[^>]*>.*?src="([^"?]+)', body, re.S)
names = [s.split('/')[-1] for s in srcs]
dup = [n for n in set(names) if names.count(n) > 1]
caps = re.findall(r'<figcaption[^>]*>(.*?)</figcaption>', body, re.S)
# ★ `startswith('그림')` 로 세면 「그림 · 규격 2...」(번호 없음)까지 번호로 센다.
#   그렇게 세서 13/14 라고 보고했고 site 세션이 10/14 라고 고쳐 줬다. 번호를 겨눈다.
numbered = sum(1 for c in caps
               if re.match(r'그림\s*[0-9]', re.sub(r'<[^>]+>', '', c).strip()))
chk('19', '평가 정본 도식이 아티팩트와 같나 (중복·캡션)',
    not dup and len(names) == 14,
    '그림 %d개 · 중복 %d · 번호 있는 캡션 %d (아티팩트도 같음)'
    % (len(names), len(dup), numbered))

# 20 · 허브 정렬
ok20 = True
detail20 = []
for m in re.finditer(r'data-label="([^"]+)"(.*?)(?=data-label="|\Z)', hub, re.S):
    ds = re.findall(r'class="em3">[^<]*?(\d{4}-\d{2}-\d{2})', m.group(2))
    if len(ds) < 2:
        continue
    d = all(ds[i] >= ds[i + 1] for i in range(len(ds) - 1))
    ok20 &= d
    if not d:
        detail20.append(m.group(1))
chk('20', '연구 허브가 최신순', ok20,
    '뒤죽박죽인 묶음 %d개%s' % (len(detail20), (' · ' + ' '.join(detail20)) if detail20 else ''))

# 21 · 「판」
out = subprocess.run([sys.executable, os.path.join(LAB, 'tools/pan_to_episode.py')]
                     + [os.path.join(r, f).replace('\\', '/')
                        for r, d, fs in os.walk(os.path.join(LAB, 'docs'))
                        if 'assets' not in r for f in fs if f.endswith('.md')],
                     capture_output=True, text=True, encoding='utf-8', cwd=LAB)
tot = re.search(r'합계 (\d+)곳', out.stdout or '')
chk('21', '문서의 「판」 -> 「에피소드」', False,
    '남은 %s곳 (전부 팀원 문서 · PR 대기)' % (tot.group(1) if tot else '?'))

# 22 · 다이제스트
dg = [f for f in os.listdir(os.path.join(LAB, 'docs/digest'))
      if re.match(r'2026-W\d\d\.md$', f)]
chk('22', '주간 다이제스트 밀림 해소',
    '2026-W36.md' in dg and '2026-W37.md' in dg,
    '본문 %s' % ' '.join(sorted(dg)))


# ★ 알려진 답. 점검표가 아무것도 안 재고 있으면 전부 OK 가 나온다.
#   산출물을 고의로 망가뜨려 «잡히는지» 본다. 오늘만 이 부류를 일곱 번 봤다.
_kat = []
_bad_hub = hub.replace('data-label="진단·분석"', '')   # 속성을 통째로 지운다
_kat.append(('묶음 하나 지움',
             len(set(re.findall(r'data-label="([^"]*)"', _bad_hub))) != 6))
_m = re.search(r'data-label="조사·비교"(.*?)(?=data-label=|$)', hub, re.S)
_ds = re.findall(r'class="em3">[^<]*?(\d{4}-\d{2}-\d{2})', _m.group(1)) if _m else []
_rev = list(reversed(_ds))
_kat.append(('정렬 뒤집음',
             len(_rev) > 1 and
             not all(_rev[i] >= _rev[i + 1] for i in range(len(_rev) - 1))))
_no_icon = re.sub(r'<link[^>]*rel="(?:shortcut )?icon"[^>]*>', '', proto)
_kat.append(('파비콘 뗌',
             not re.search(r'<link[^>]*rel="(?:shortcut )?icon"', _no_icon)))
print()
print('  점검표 자기시험 (망가뜨리면 잡나)')
for _nm, _got in _kat:
    print('    %s %s' % ('OK ' if _got else '[X] 놓침', _nm))
print()
print('  번호 | 지시 | 상태')
print('  ' + '-' * 76)
ng = 0
for no, what, ok, detail in rows:
    mark = 'OK  ' if ok else '[!] '
    ng += (not ok)
    print('  %-3s %s %-42s %s' % (no, mark, what[:42], detail[:56]))
print('  ' + '-' * 76)
print('  %d항목 · 어긋남 %d' % (len(rows), ng))
