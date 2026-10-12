# -*- coding: utf-8 -*-
"""E1 · E2 성능 · 영상 페이지 생성기 (lead · 2026-10-12).

원자료: C:/isaac/ext/go2_rl_robotlab/_eval/out 의 E12-page.csv · E12-summary.json ·
curves/E{1,2}_curves.csv · web_list.csv · web/ 영상. 숫자는 손으로 쓰지 않는다.
출력: site/index.html · site/v/<dir>/<file>.mp4 · site/p/<dir>/<file>.jpg (포스터)
"""
import csv
import json
import os
import shutil
import subprocess
import sys

EV = 'C:/isaac/ext/go2_rl_robotlab/_eval'
OUT = os.path.join(EV, 'out')
HERE = os.path.dirname(os.path.abspath(__file__))
ONLY = set(a for a in sys.argv[1:] if '=' not in a)  # 'novideo' 면 영상 복사 생략
OPT = dict(a.split('=', 1) for a in sys.argv[1:] if '=' in a)
CK = OPT.get('ck', '20499')                     # 이 페이지에 싣는 영상의 체크포인트
MODE = OPT.get('mode', 'main')                  # main = 분석 전체 + 영상 · videos = 영상만
OTHER = OPT.get('other', '')                    # 다른 체크포인트 영상 페이지 주소
SITE = OPT.get('site', os.path.join(HERE, 'site'))

# ---------- 과제 표 ----------
page = list(csv.DictReader(open(os.path.join(OUT, 'E12-page.csv'), encoding='utf-8')))
M = []
for r in page:
    M.append([r['noise'], r['terrain'], r['cell'],
              int(r['E1_19500']), int(r['E2_19500']), r['flag_19500'],
              int(r['E1_20000']), int(r['E2_20000']), r['flag_20000'],
              int(r['E1_20499']), int(r['E2_20499']), r['flag_20499']])

# ---------- 묶음 평균 ----------
G = {}
for g in json.load(open(os.path.join(OUT, 'E12-summary.json'), encoding='utf-8')):
    G[g['group']] = [round(100 * g['e1_mean'], 1), round(100 * g['e2_mean'], 1), g['flags_pp'], g['cells']]

# ---------- 학습 곡선 ----------
KEYS = {'s': 'Train/mean_student_reward', 't': 'Train/mean_teacher_reward',
        'lv': 'Curriculum/terrain_levels', 'ic': 'Episode_Termination/illegal_contact',
        'ns': 'Policy/mean_noise_std'}
C = {}
K = {}
WIN = 25
for run in ('E1', 'E2'):
    rows = list(csv.DictReader(open(os.path.join(OUT, 'curves', f'{run}_curves.csv'), encoding='utf-8')))
    raw = {k: [None if r[col] in ('', 'nan') else float(r[col]) for r in rows] for k, col in KEYS.items()}
    its = [int(r['iteration']) for r in rows]
    assert its == list(range(len(its))), 'iteration 열이 0 부터 빈틈없이 이어져야 한다'
    # 결론 문장용 원값 (평균 내지 않음)
    K[run] = {k: {str(i): round(raw[k][i], 4) for i in (500, 10000, 19999, 20499)} for k in KEYS}
    # 그림용 25 iter 뒤쪽 이동 평균. 20000 의 꺾임이 번지지 않게 20000 을 넘지 않는 창은 20000 앞에서 끊는다
    sm = {k: [] for k in KEYS}
    for k in KEYS:
        a = raw[k]
        for i in range(len(a)):
            lo = max(0, i - WIN + 1)
            if i >= 20000:
                lo = max(lo, 20000)
            w = [v for v in a[lo:i + 1] if v is not None]
            sm[k].append(round(sum(w) / len(w), 4) if w else None)
    keep = [i for i in its if i % 50 == 0 or (i >= 19900 and i % 5 == 0) or i in (19999, 20499)]
    C[run] = {'it': keep, **{k: [sm[k][i] for i in keep] for k in KEYS}}


# ---------- 판정 근거 (사람 말) ----------
AX = {'fwd01': ('vx', 0.1, '전진'), 'fwd02': ('vx', 0.2, '전진'), 'fwd03': ('vx', 0.3, '전진'), 'fwd05': ('vx', 0.5, '전진'),
      'back03': ('vx', -0.3, '후진'), 'left03': ('vy', 0.3, '왼쪽 옆걸음'), 'right03': ('vy', -0.3, '오른쪽 옆걸음'),
      'yawL05': ('wz', 0.5, '왼쪽 제자리 회전'), 'yawR05': ('wz', -0.5, '오른쪽 제자리 회전')}
THR = {'vx': 0.15, 'vy': 0.15, 'wz': 0.20}
AXN = {'vx': '앞뒤 속도', 'vy': '옆 속도', 'wz': '회전 속도'}
UNIT = {'vx': 'm/s', 'vy': 'm/s', 'wz': 'rad/s'}
FALL = {'tilt60': '몸이 60도 넘게 0.2 s 기울어짐', 'base_contact': '몸통이 땅에 닿음'}


def fnum(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return float('nan')


def explain(cell, e):
    """episodes.csv 한 줄 → (판정, 근거 문장, 아슬아슬, 덧붙임, 볼 곳)."""
    import math
    if e['survived'] != 'True':
        ft = fnum(e['fall_t'])
        return ('넘어짐', f"{ft:.1f} s 에 넘어짐 ({FALL.get(e['fall_reason'], e['fall_reason'])})", False, '',
                f"{max(0.0, ft - 2):.0f}~{ft:.0f} s 구간")
    if cell == 'stop03':
        st, dist = fnum(e['stop_t']), fnum(e['stop_dist_m'])
        if e['q2_pass'] == 'True':
            return ('통과', f"5 s 에 명령이 0 이 된 뒤 {st:.2f} s 만에 완전히 섬 · 그 사이 {dist * 100:.0f} cm 움직임 (기준: 1 s 안 · 20 cm 이하)",
                    st > 0.9, '', '5 s 이후')
        if e['q2_cat'] == 'stop_fail':
            if math.isnan(st):
                return ('미달', '5 s 에 명령이 0 이 된 뒤 끝 (10 s) 까지 1 초 내내 완전히 선 구간이 없음 (발을 계속 디디거나 몸이 조금씩 돎)',
                        False, '', '5~10 s · 속도 그래프가 0 근처에서 출렁임')
            if st > 1.0:
                return ('미달', f"5 s 에 명령이 0 이 된 뒤 완전히 서기까지 {st:.2f} s (기준 1 s 안 · {st - 1:.2f} s 늦음) · 그 사이 {dist * 100:.0f} cm 움직임",
                        st <= 1.2, '', f"5~{5 + st + 1:.0f} s · 멈춘 뒤에도 발을 고쳐 디딤")
            return ('미달', f"멈추는 동안 {dist * 100:.0f} cm 움직임 (기준 20 cm 이하)", dist <= 0.22, '', '5 s 이후')
        return ('미달', '앞 5 s 걷기가 기준 미달', False, '', '0~5 s')
    if cell == 'stand':
        return ('통과' if e['q1_pass'] == 'True' else '미달',
                f"제자리 10 s · 미끄러짐 오차 평균 앞뒤 {fnum(e['mae_vx']):.3f} · 옆 {fnum(e['mae_vy']):.3f} m/s · 회전 {fnum(e['mae_wz']):.3f} rad/s",
                False, '', '')
    ax, c, label = AX[cell]
    mean = fnum(e['mean_' + ax])
    ratio = mean / c
    head = f"{label} {abs(c):.2f} {UNIT[ax]} 명령 → 실제 평균 {abs(mean):.2f} {UNIT[ax]} ({ratio * 100:.0f} %)" if ratio >= 0         else f"{label} {abs(c):.2f} {UNIT[ax]} 명령 → 실제 평균이 반대 방향 {mean:+.2f} {UNIT[ax]}"
    mae = {k: fnum(e['mae_' + k]) for k in THR}
    note = ''
    if cell in ('fwd01', 'fwd02'):
        mr = fnum(e['move_ratio'])
        if mr < 0.5:
            note = f"실제로는 거의 서 있음 (명령의 {mr * 100:.0f} %)."
            if cell == 'fwd01':
                note += ' 0.1 m/s 명령은 서 있어도 오차가 0.10 이라 통과로 셉니다 (판정 기준의 맹점).'
    if e['q1_pass'] == 'True':
        close = any(mae[k] > 0.9 * THR[k] for k in THR)
        return ('통과', f"{head} · {AXN[ax]} 오차 평균 {mae[ax]:.3f} (기준 {THR[ax]:.2f} 이하)", close, note, '1 s 이후 전체')
    bad = [k for k in THR if mae[k] > THR[k]]
    if not bad:
        return ('미달', head + ' · 세부 사유 미확인', False, note, '')
    parts = []
    for k in bad:
        extra = '' if k == ax else (' · 명령하지 않은 방향으로 샘' if k != 'wz' else ' · 명령하지 않은 회전이 생김')
        parts.append(f"{AXN[k]} 오차 평균 {mae[k]:.3f} > 기준 {THR[k]:.2f} ({mae[k] - THR[k]:.3f} 넘음){extra}")
    close = all(mae[k] <= 1.1 * THR[k] for k in bad)
    return ('미달', head + ' · ' + ' · '.join(parts), close, note, '1 s 이후 전체 · 속도 그래프의 옅은 주황 = 명령보다 모자란 만큼')

# ---------- 영상 ----------
TER = {'flat': '평지', 'wave': '물결', 'slope_up': '오르막', 'slope_down': '내리막',
       'rough_slope': '거친 경사', 'stairs_up': '계단 오르기', 'stairs_down': '계단 내리기',
       'obstacles': '장애물'}
CELLS = ['stand', 'stop03', 'fwd01', 'fwd02', 'fwd03', 'fwd05', 'back03', 'left03', 'right03', 'yawL05', 'yawR05']
BADV = set()
_af = os.path.join(HERE, 'audit_frames.json')
if os.path.exists(_af) and 'nobad' not in ONLY:
    BADV = {x['file'] for x in json.load(open(_af, encoding='utf-8')) if x['bad']}
V = []
wl = list(csv.DictReader(open(os.path.join(OUT, 'web_list.csv'), encoding='utf-8')))
for r in wl:
    if not r['web']:
        continue
    src = os.path.join(EV, r['web'])
    rel = r['web'].split('out/web/', 1)[1]          # <dir>/<file>.mp4
    d, fn = rel.split('/', 1)
    t = r['title'].split()                          # E1 20499 flat stop03 ep6
    run, ck, fam, cell, ep = t[0], t[1], t[2], t[3], int(t[4][2:])
    if fam.startswith('B:'):
        fam = fam[2:]
    band = 'offplat' in d
    # 판정 줄을 원자료와 맞춰 본다 (episodes.csv · cells.json 의 rule)
    rules = {(c['family'], c['cell']): c['rule'] for c in json.load(open(os.path.join(OUT, d, 'cells.json'), encoding='utf-8'))}
    er = [e for e in csv.DictReader(open(os.path.join(OUT, d, 'episodes.csv'), encoding='utf-8')) if e['family'] == fam and e['cell'] == cell and int(e['episode']) == ep]
    assert len(er) == 1, (d, fam, cell, ep, len(er))
    truth = er[0][rules[(fam, cell)]] == 'True'
    q = r['q_line'].replace('Q 판정: ', '').replace(' (Q-E1 임시 조건 · 현행 정의)', '')
    assert truth == r['q_line'].replace('Q 판정: ', '').startswith('통과'), (d, fam, cell, ep, r['q_line'])
    vd, why, close, note, look = explain(cell, er[0])
    short = q  # HUD 아래 띠와 같은 표기 (예: 미달 · MAE vy 0.151 > 0.15)
    e0 = er[0]
    meas = ''
    if cell in AX and e0['survived'] == 'True':
        ax, c, label = AX[cell]
        mv = fnum(e0['mean_' + ax])
        meas = f"{label} 명령 {abs(c):.2f} {UNIT[ax]} · 실제 평균 {mv:+.2f} ({mv / c * 100:.0f} %)"
    elif cell == 'stop03' and e0['survived'] == 'True':
        st = fnum(e0['stop_t'])
        meas = ('완전히 서기까지 ' + (f"{st:.2f} s" if st == st else '끝까지 못 섬')) + f" · 움직인 거리 {fnum(e0['stop_dist_m']) * 100:.0f} cm"
    assert (vd == '통과') == truth, (d, fam, cell, ep, vd)
    V.append({'run': run, 'ck': ck, 'fam': fam, 'band': band, 'cell': cell, 'ep': ep, 'vd': vd, 'why': why, 'close': close, 'note': note, 'look': look, 'short': short, 'meas': meas, 'bad': d + '/' + fn in BADV,
              'pick': r['pick'], 'q': q, 'ok': q.startswith('통과'),
              'v': f'v/{rel}', 'p': f'p/{rel[:-4]}.jpg', 'mb': round(int(r['web_bytes']) / 1e6, 2),
              'src': src})
famorder = list(TER)
V = [x for x in V if x['ck'] == CK]
V.sort(key=lambda x: (x['band'], famorder.index(x['fam']), CELLS.index(x['cell']), x['ck'], x['run'], x['ep']))

def _sha(p):
    import hashlib
    return hashlib.sha256(open(p, 'rb').read()).hexdigest()


COPIED = []
if 'novideo' not in ONLY:
    for x in V:
        if x['bad']:
            continue
        dst = os.path.join(SITE, x['v'])
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        # 크기만 보면 같은 이름으로 다시 만든 영상을 놓친다 (10/12 재렌더 24 편). 내용으로 비교한다
        fresh = not os.path.exists(dst) or os.path.getsize(dst) != os.path.getsize(x['src']) or _sha(dst) != _sha(x['src'])
        if fresh:
            shutil.copy2(x['src'], dst)
            COPIED.append(x['v'])
        pst = os.path.join(SITE, x['p'])
        os.makedirs(os.path.dirname(pst), exist_ok=True)
        if fresh or not os.path.exists(pst):   # 영상이 바뀌면 포스터도 새로 뜬다
            # 출발 직후보다 걷는 중인 장면이 낫다. stop 은 멈춘 뒤를 보여 준다
            ss = 7.5 if x['cell'] == 'stop03' else 4.0
            dur = float(subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', x['src']],
                                       capture_output=True, text=True, check=True).stdout.strip())
            ss = str(round(min(ss, dur * 0.6), 2))   # 넘어져 일찍 끝난 판은 길이가 짧다
            subprocess.run(['ffmpeg', '-v', 'error', '-y', '-ss', ss, '-i', x['src'], '-frames:v', '1',
                            '-vf', 'scale=640:-2,format=yuvj420p', '-q:v', '5', pst], check=True)
            assert os.path.exists(pst), pst
for x in V:
    x.pop('src')

data = {'M': M, 'G': G, 'C': C, 'K': K, 'V': V, 'MODE': MODE, 'CK': CK, 'OTHER': OTHER}
tpl = open(os.path.join(HERE, 'page.html'), encoding='utf-8').read()
if MODE == 'videos':
    tpl = tpl.replace('<title>E1 · E2 시뮬 평가</title>', f'<title>E1 · E2 영상 {CK}</title>')
html = tpl.replace('/*__DATA__*/', 'const D = ' + json.dumps(data, ensure_ascii=False, separators=(',', ':')) + ';')
# 4판: 본문의 %%이름%% 자리를 원자료에서 계산한 값으로 채운다 (facts4.py · 손으로 쓴 숫자 없음)
import facts4
html = facts4.fill(html, facts4.build(page, G))
os.makedirs(SITE, exist_ok=True)
open(os.path.join(SITE, 'index.html'), 'w', encoding='utf-8', newline='\n').write(html)
tot = sum(x['mb'] for x in V)
print(json.dumps({'cells': len(M), 'groups': len(G), 'curve_pts': len(C['E1']['it']), 'videos': len(V), 'video_MB': round(tot, 1),
                  'copied': len(COPIED), 'html_KB': round(len(html.encode('utf-8')) / 1024, 1)}, ensure_ascii=False))
for v in COPIED:
    print('copied', v)
