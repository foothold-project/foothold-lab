# -*- coding: utf-8 -*-
"""14쪽 «실패 지형을 나누고, 먼저 시도할 과제를 골랐습니다» 본문 · 팀장 지시 2026-10-02.

13쪽이 「같은 실패였을까요?」 하고 묻는다. 이 장이 그 답이다. 실패는 세 유형이고,
유형마다 영상 한 판 + 그 지형의 네 숫자(종합 · 생존 · 전진 · 추종)를 같이 둔다.

  유형 1  넘어진다                     gap    (생존 21 %)
  유형 2  살아 있지만 못 나아간다        pit    (생존 97 % · 전진 15 %)
  유형 3  느려서 시킨 속도를 못 맞춘다   rails  (전진 51 % · 추종 8 %)

숫자는 손으로 적지 않는다.
  표   : sim/eval/results/20260903-rough10-1.0mps/summary-thr1.5.csv (9/3 진단 · 구규격 1)
  영상 : sim/eval/results/20260911-gallery/web/<terrain>-v1-baseline.mp4 (9/11 갤러리 · 규격 2)
두 날짜의 정책이 같은 체크포인트인지(sha256) 빌드가 확인한다.
«baseline» = NVIDIA 공식 체크포인트: 9/3 run_manifest.json 의 policy_checkpoint,
9/11 cuts/*/1-record.log 의 같은 sha256, gallery.html 의 라벨 「기준선 NVIDIA」,
docs/research/20260928-v2-mvp-report.md 의 「NVIDIA 배포본」으로 확인했다.

쓰는 법 (덱 폴더에서):
  FOOTHOLD_DECK_EXTRA=design.failure_types FOOTHOLD_DECK_EXTRA_CSS=failure_types.css python build_presentation.py
"""
import csv
import html
import io
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent          # 20260929-mvp-presentation
ROOT = HERE.parents[2]                                  # foothold-lab

TITLE = '실패 지형을 나누고, 먼저 시도할 과제를 골랐습니다'
DIAG = 'sim/eval/results/20260903-rough10-1.0mps'       # 9/3 진단 (표)
GAL = 'sim/eval/results/20260911-gallery'               # 9/11 갤러리 (영상)
GALLERY_WEB = '../../../../' + GAL + '/web/'            # output/ 기준 상대경로
POSTER_DIR = HERE / 'assets/failure-types'
POSTER_REL = '../assets/failure-types/'

# 포스터 프레임 (50 fps). 첫 프레임은 세 지형 다 「서 있는 로봇」뿐이라 유형이 안 보인다.
# 실패가 보이는 순간을 trace.csv 로 고르고 눈으로 확인했다 (아래 주석).
POSTER_FRAME = {
    'gap': 75,     # 1.50 s · 앞발이 틈에 빠지고 몸통 높이 0.12 m (기준 0.33 m)
    'pit': 299,    # 5.98 s · 턱에 앞발만 걸친 채 주저앉아 속도 0 · 전진 1.14 m
    'rails': 150,  # 3.00 s · 레일에 다리가 걸려 속도 0.59 m/s (명령 1.0)
}

TYPES = [
    # (지형, 유형 번호, 유형 이름, 같은 유형의 다른 지형)
    ('gap', 1, '넘어진다', 'stepping_stones'),
    ('pit', 2, '살아 있지만 못 나아간다', 'floating_ring'),
    ('rails', 3, '느려서 시킨 속도를 못 맞춘다', None),
]
KO = {'stepping_stones': '디딤돌', 'floating_ring': '고리'}


# ── 원자료 ─────────────────────────────────────────────────────
def pct(v):
    """CSV 의 비율(0.21)을 정수 % 로. 100판이라 정수여야 한다. 아니면 멈춘다."""
    x = float(v) * 100
    assert abs(x - round(x)) < 1e-6, v
    return int(round(x))


def diag():
    """9/3 진단표 (정본 판정 · 방향 임계 1.5 m). 지형 → 네 축 % 와 평균 전진 거리."""
    path = ROOT / DIAG / 'summary-thr1.5.csv'
    rows = {r['terrain']: r for r in csv.DictReader(io.open(path, encoding='utf-8-sig'))}
    out = {}
    for t in ('gap', 'stepping_stones', 'pit', 'rails', 'floating_ring'):
        r = rows[t]
        assert r['episodes'] == '100', (t, r['episodes'])
        out[t] = {
            'overall': pct(r['overall_success_rate']),
            'survival': pct(r['survival_rate']),
            'progress': pct(r['progress_success_rate']),
            'tracking': pct(r['tracking_success_rate']),
            'fwd_m': float(r['mean_forward_progress_m']),
        }
    # 팀장 지시문의 숫자와 원자료가 같은지. 다르면 지시문이 아니라 원자료를 따르되, 멈춰서 알린다.
    assert out['gap']['survival'] == 21, out['gap']
    assert out['pit']['survival'] == 97 and out['pit']['progress'] == 15, out['pit']
    assert out['rails']['progress'] == 51 and out['rails']['tracking'] == 8, out['rails']
    man = json.loads((ROOT / DIAG / 'run_manifest.json').read_text(encoding='utf-8'))
    assert man['command_vx_mps'] == 1.0 and man['eval_duration_s'] == 6.0, man['note']
    assert man['episodes_per_terrain'] == 100 and man['min_progress_m'] == 3.0, man['note']
    assert man['max_velocity_mae_mps'] == 0.25 and man['seed'] == 42, man['note']
    assert 'Isaac-Velocity-Rough-Unitree-Go2-v0' in man['policy_checkpoint'], man['policy_checkpoint']
    return out, man


def gallery():
    """9/11 갤러리 · baseline(NVIDIA) · 1.0 m/s 의 세 컷. 같은 체크포인트인지 sha256 으로 확인."""
    man = json.loads((ROOT / GAL / 'manifest.json').read_text(encoding='utf-8'))
    assert man['difficulty'] == 0.5, man['difficulty']
    cells = {}
    for c in man['clips']:
        if c['model'] == 'baseline' and c['speed_mps'] == 1.0 and c['terrain'] in ('gap', 'pit', 'rails'):
            assert c['episodes'] == 100 and c['file'] == f"{c['terrain']}-v1-baseline.mp4", c
            cells[c['terrain']] = c
    assert len(cells) == 3, sorted(cells)
    sha_0903 = json.loads((ROOT / DIAG / 'run_manifest.json').read_text(encoding='utf-8'))['policy_sha256']
    for t in cells:
        log = io.open(ROOT / GAL / 'cuts' / f'{t}-v1-baseline' / '1-record.log', encoding='utf-8', errors='replace').read()
        shas = set(re.findall(r'"policy_sha256":\s*"([0-9a-f]{64})"', log))
        assert shas == {sha_0903}, (t, shas, sha_0903)   # 표와 영상이 같은 NVIDIA 체크포인트
        head = io.open(ROOT / GAL / 'cuts' / f'{t}-v1-baseline' / f'{t}-v1-baseline.trace.csv', encoding='utf-8-sig').read(1200)
        for key, val in (('difficulty', '0.5'), ('command_vx_mps', '1.0'), ('eval_spec_version', '2'), ('eval_duration_s', '6.0')):
            assert f'# {key} = {val}' in head, (t, key, head[:400])
        assert (ROOT / GAL / 'web' / f'{t}-v1-baseline.mp4').exists(), t
    return cells


def poster(terrain):
    """포스터가 없으면 PyAV 로 지정 프레임을 뽑아 둔다. 있으면 그대로 쓴다."""
    POSTER_DIR.mkdir(parents=True, exist_ok=True)
    out = POSTER_DIR / f'{terrain}-nvidia.jpg'
    if not out.exists():
        import av                                       # 빌드 환경에 없으면 여기서 멈춘다 (조용히 빼지 않는다)
        src = ROOT / GAL / 'web' / f'{terrain}-v1-baseline.mp4'
        want = POSTER_FRAME[terrain]
        with av.open(str(src)) as c:
            stream = c.streams.video[0]
            for i, f in enumerate(c.decode(stream)):
                if i == want:
                    img = f.to_image()
                    assert img.width * 9 == img.height * 16, (img.width, img.height)   # 16:9
                    img.save(out, quality=88)
                    break
            else:
                raise AssertionError((terrain, want, '프레임 없음'))
    return POSTER_REL + out.name


# ── 조각 ───────────────────────────────────────────────────────
def split_strip(body):
    """experiment_frame 이 앞에 붙인 다섯 칸 띠를 통째로 떼어 돌려준다 (div 깊이로 끝을 찾는다)."""
    if not body.startswith('<div class="exp-strip"'):
        return '', body
    depth = 0
    for m in re.finditer(r'<div\b|</div>', body):
        depth += 1 if m.group().startswith('<div') else -1
        if depth == 0:
            end = m.end()
            head = body[:end]
            assert head.count('exp-cell') == 5 and head.count('exp-arrow') == 4, (head.count('exp-cell'), head.count('exp-arrow'))
            return head, body[end:]
    raise AssertionError('exp-strip 이 닫히지 않음')


def num(label, value, cls=''):
    return f'<span class="{cls}"><i>{label}</i><b>{value}</b></span>'


def card(terrain, n, name, kin, d, easy, hot, fine, cell):
    v = d[terrain]
    po = poster(terrain)
    src = GALLERY_WEB + f'{terrain}-v1-baseline.mp4'
    cls = lambda k: 'bad' if k == hot else ('ok' if k == fine else '')
    kin_html = ''
    if kin:
        k = d[kin]
        kin_html = (f'<small class="ft-kin">{KO[kin]}({kin})도 같은 유형 · 생존 {k["survival"]}% · 전진 {k["progress"]}%</small>')
    else:
        kin_html = '<small class="ft-kin">이 유형은 rails 하나</small>'
    return (
        f'<figure class="film ft-card ft-t{n}">'
        f'<div class="ft-head"><b>유형 {n}</b><span>{name}</span><code>{terrain}</code></div>'
        f'<video controls playsinline preload="metadata" muted loop data-autoplay="muted" poster="{po}" src="{src}"></video>'
        f'<figcaption>{easy}</figcaption>'
        '<div class="ft-nums">'
        + num('생존', f'{v["survival"]}%', cls('survival'))
        + num('전진', f'{v["progress"]}%', cls('progress'))
        + num('속도 추종', f'{v["tracking"]}%', cls('tracking'))
        + num('종합', f'{v["overall"]}%', cls('overall'))
        + num('평균 전진', f'{v["fwd_m"]:.1f} m')
        + '</div>' + kin_html + '</figure>')


# ── 장 ────────────────────────────────────────────────────────
def apply(slides):
    d, man = diag()
    cells = gallery()
    s = next(x for x in slides if x['title'] == TITLE)
    head, _old = split_strip(s['body'])
    assert head, '14쪽 앞에 experiment_frame 의 띠가 있어야 한다 (모듈 순서)'

    g, p, r = d['gap'], d['pit'], d['rails']
    cards = (
        card('gap', 1, '넘어진다', 'stepping_stones', d,
             f'틈에 앞발이 빠지며 몸이 꺼집니다. 100판 중 {100 - g["survival"]}판이 6초를 못 버티고 넘어졌습니다.',
             'survival', None, cells['gap'])
        + card('pit', 2, '살아 있지만 못 나아간다', 'floating_ring', d,
               f'넘어지지는 않습니다. 그런데 턱에 걸려 주저앉아, 3 m 통과선을 넘은 판이 100판 중 {p["progress"]}판뿐입니다.',
               'progress', 'survival', cells['pit'])
        + card('rails', 3, '느려서 시킨 속도를 못 맞춘다', None, d,
               f'앞으로는 갑니다. 그런데 레일에 걸려 주춤하느라, 시킨 1.0 m/s 를 맞춘 판이 100판 중 {r["tracking"]}판입니다.',
               'tracking', 'progress', cells['rails'])
    )
    finding = ('<p class="ft-finding">유형이 다르면 처방도 다릅니다 · 다섯 지형을 나눠 탐색하되, '
               '넘어지는 유형의 gap 부터 시작했습니다</p>')
    cond = ('<p class="ft-cond">'
            f'숫자 · 2026-09-03 진단 · NVIDIA 공식 체크포인트 (Isaac-Velocity-Rough-Unitree-Go2-v0) · '
            f'{man["command_vx_mps"]:.1f} m/s · {man["eval_duration_s"]:.0f}초 · 지형당 {man["episodes_per_terrain"]}판 · '
            f'통과선 {man["min_progress_m"]:.0f} m · 속도 오차 {man["max_velocity_mae_mps"]} m/s · 방향 임계 1.5 m · '
            '구규격 1 (빗나간 광선을 -1 로 읽던 때) · 최신 성과와 직접 비교 금지 · '
            '영상 · 2026-09-11 갤러리 · 같은 체크포인트 · 난이도 0.5 · 1.0 m/s · 각 한 판의 예시'
            '</p>')
    body = head + '<div class="ft-grid">' + cards + '</div>' + finding + cond
    assert '—' not in body and '씨앗' not in body, 'em dash · 씨앗 금지'
    s['body'] = body
    s['kind'] = (s.get('kind', '') + ' ft-page').strip()
    s['source'] = (f'<a href="../../../../{DIAG}/summary-thr1.5.csv" target="_blank" rel="noopener">'
                   '진단표 2026-09-03 · summary-thr1.5.csv</a> · '
                   f'<a href="../../../../{GAL}/manifest.json" target="_blank" rel="noopener">'
                   '영상 · 2026-09-11 갤러리 manifest.json</a>')
    s['spoken'] = (
        '같은 실패가 아니었습니다. 세 유형으로 갈립니다. '
        f'첫째, 틈과 디딤돌에서는 넘어집니다. 틈에서는 100판 중 {g["survival"]}판만 6초를 버텼습니다. '
        f'둘째, pit과 고리에서는 넘어지지 않는데 나아가지 못합니다. pit은 {p["survival"]}판이 살아남았지만 3미터를 간 판은 {p["progress"]}판입니다. '
        f'셋째, rails에서는 앞으로는 가는데 레일에 걸려 주춤하느라 명령 속도를 못 맞춥니다. {r["progress"]}판이 3미터를 넘었지만 속도를 맞춘 판은 {r["tracking"]}판입니다. '
        '유형이 다르면 처방도 다릅니다. 그래서 다섯 과제를 나눠 탐색하되, 넘어지는 유형의 gap부터 집중했습니다.')
    return 1
