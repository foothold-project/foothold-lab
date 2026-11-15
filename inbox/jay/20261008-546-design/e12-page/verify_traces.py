# -*- coding: utf-8 -*-
"""영상 HUD 가 읽은 기록(parquet, lab 93 열)에서 판정값을 lead 가 따로 다시 계산해 episodes.csv 와 맞춘다.

이동 cell : 첫 1 s 를 뺀 창에서 |vx - cmd_vx| · |vy - cmd_vy| · |wz - cmd_wz| 평균 (MAE)
stop03    : 명령이 0 이 된 뒤 (t >= 5 s) 평면 속도 < 0.05 이고 |wz| < 0.10 이 50 표본 내내 이어지는 첫 시작점까지의 시간
결과: verify_traces.json · 어긋난 영상 목록
"""
import csv
import json
import os
import sys

import numpy as np
import pandas as pd

OUT = 'C:/isaac/ext/go2_rl_robotlab/_eval/out'
sel = json.load(open(os.path.join(OUT, 'hud_sel.json'), encoding='utf-8'))
cache = {}


def episode(tag, fam, cell, ep):
    if tag not in cache:
        cache[tag] = {(r['family'], r['cell'], int(r['episode'])): r
                      for r in csv.DictReader(open(os.path.join(OUT, tag, 'episodes.csv'), encoding='utf-8'))}
    return cache[tag][(fam, cell, ep)]


def f(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return float('nan')


rows = []
for s in sel:
    tag = s['tag']
    name = os.path.basename(s['parquet'])[:-8]          # flat_stop03_ep006
    head, ep = name.rsplit('_ep', 1)
    ep = int(ep)
    fam, cell = head.rsplit('_', 1)
    e = episode(tag, fam, cell, ep)
    d = pd.read_parquet(s['parquet'])
    t = d['t_s'].to_numpy()
    vx, vy, wz = d['vx_mps'].to_numpy(), d['vy_mps'].to_numpy(), d['base_wz_rps'].to_numpy()
    cx, cy, cw = d['cmd_vx_mps'].to_numpy(), d['cmd_vy_mps'].to_numpy(), d['cmd_wz_rps'].to_numpy()
    r = {'key': s['key'], 'cell': cell, 'n': len(t), 't_end': round(float(t[-1]), 2)}
    if cell == 'stop03':
        sp = np.hypot(vx, vy)
        ok = (sp < 0.05) & (np.abs(wz) < 0.10)
        j0 = int(np.searchsorted(t, 5.0 - 1e-6))
        st = float('nan')
        for j in range(j0, len(t) - 49):
            if ok[j:j + 50].all():
                st = round(float(t[j] - t[j0]), 2)
                break
        r.update(mine_stop_t=st, csv_stop_t=f(e['stop_t']))
        a, b = r['mine_stop_t'], r['csv_stop_t']
        r['match'] = bool((np.isnan(a) and np.isnan(b)) or (not np.isnan(a) and not np.isnan(b) and abs(a - b) <= 0.021))
    elif cell != 'stand':
        w = t >= 1.0 - 1e-9
        m = {k: round(float(np.mean(np.abs(v[w] - c[w]))), 4) for k, v, c in (('vx', vx, cx), ('vy', vy, cy), ('wz', wz, cw))}
        r.update({f'mine_mae_{k}': v for k, v in m.items()})
        r.update({f'csv_mae_{k}': round(f(e[f'mae_{k}']), 4) for k in ('vx', 'vy', 'wz')})
        r['match'] = bool(all(abs(m[k] - f(e[f'mae_{k}'])) <= 0.006 for k in ('vx', 'vy', 'wz'))) if e['survived'] == 'True' else None
    else:
        r['match'] = None
    rows.append(r)

json.dump(rows, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'verify_traces.json'), 'w', encoding='utf-8'),
          ensure_ascii=False, indent=1)
chk = [r for r in rows if r['match'] is not None]
bad = [r for r in chk if not r['match']]
print('videos', len(rows), 'checked', len(chk), 'mismatch', len(bad))
for r in bad[:30]:
    print(r)
