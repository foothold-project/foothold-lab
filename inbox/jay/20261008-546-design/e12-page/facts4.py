# -*- coding: utf-8 -*-
"""4판 사실 계산 (lead · 2026-10-12 밤). 페이지 본문의 %%이름%% 자리에 넣을 값과 표 HTML 을 원자료에서 만든다.

원자료
  - 학습 곡선: _eval/out/curves/E{1,2}_curves.csv
  - 칸 통과율: _eval/out/E12-page.csv
  - 멈추기 판별 값: _eval/out/<tag>/episodes.csv (fr_m20499_flat = noise 끔 · m20499_noise_flat = noise 켬, 둘 다 E1)
  - E1 학습 설정: logs/rsl_rl/go2_moe_cts/<E1 run>/params/env.yaml (학습 때 rsl_rl 이 적은 것)
  - v2 학습 설정 · 성적: foothold-lab models/foothold-v2.env.yaml · foothold-v2.json
  - 신경망 차원: E1 model_20499.pt · models/foothold-v2.pt 의 가중치 모양
"""
import csv
import html
import json
import os
import re
import statistics

import yaml

EV = 'C:/isaac/ext/go2_rl_robotlab/_eval'
OUT = os.path.join(EV, 'out')
E1RUN = 'C:/isaac/ext/go2_rl_robotlab/logs/rsl_rl/go2_moe_cts/2026-10-10_12-47-48_e1_seed42_n8192'
LAB = 'C:/Users/AI-WS01/Desktop/jay/인공지능사관학교/foothold-lab'


def _f(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return float('nan')


def _yaml(p):
    return yaml.safe_load(re.sub(r'!!python/[^\s]+', '', open(p, encoding='utf-8').read()))


def _dims():
    """체크포인트 가중치 모양으로 페이지 그림의 차원 숫자를 검증한다 (손으로 쓴 숫자를 지키는 관문)."""
    os.environ.setdefault('KMP_DUPLICATE_LIB_OK', 'TRUE')
    import torch
    e1 = torch.load(os.path.join(E1RUN, 'model_20499.pt'), map_location='cpu', weights_only=False)['model_state_dict']
    v2 = torch.load(os.path.join(LAB, 'models/foothold-v2.pt'), map_location='cpu', weights_only=False)['model_state_dict']
    d = {
        'e1_teacher_in': e1['teacher_encoder.0.network.0.weight'].shape[1],
        'e1_student_in': e1['student_moe_encoder.moe.experts.backbone.network.0.weight'].shape[1],
        'e1_latent': e1['teacher_encoder.0.network.4.weight'].shape[0],
        'e1_actor_in': e1['actor.network.0.weight'].shape[1],
        'e1_critic_in': e1['critic.network.0.weight'].shape[1],
        'e1_experts': e1['student_moe_encoder.moe.gating_network.0.network.6.weight'].shape[0],
        'v2_actor_in': v2['actor.0.weight'].shape[1],
        'v2_critic_in': v2['critic.0.weight'].shape[1],
        'v2_out': v2['actor.6.weight'].shape[0],
    }
    want = {'e1_teacher_in': 275, 'e1_student_in': 450, 'e1_latent': 32, 'e1_actor_in': 77, 'e1_critic_in': 307,
            'e1_experts': 8, 'v2_actor_in': 235, 'v2_critic_in': 235, 'v2_out': 12}
    assert d == want, ('그림의 차원 숫자가 체크포인트와 다르다', d)
    return d


# 보상 항의 쉬운 뜻 (코드 rewards.py · Isaac Lab mdp 를 읽고 쓴 것)
MEAN = {
    'track_lin_vel_xy_exp': '명령한 앞뒤 · 옆 속도를 따라가면 점수. 오차가 0 이면 만점, 0.1 m/s 틀리면 96 %, 0.5 m/s 틀리면 37 %',
    'track_ang_vel_z_exp': '명령한 회전 속도를 따라가면 점수 (계산 방식은 위와 같음)',
    'lin_vel_z_l2': '몸통이 위아래로 튀면 벌점',
    'ang_vel_xy_l2': '몸통이 앞뒤 · 좌우로 출렁이면 벌점',
    'torques': '관절 힘을 많이 쓰면 벌점',
    'acc': '관절이 갑자기 빨라지거나 느려지면 벌점',
    'action_rate_l2': '이번 행동이 바로 전 행동과 크게 다르면 벌점 (떨림 줄이기)',
    'feet_air_time': '발을 0.5 s 넘게 들었다가 디디면 점수 (성큼성큼 걷게 만드는 걸음 보상)',
    'flat_orientation_l2': '몸통이 기울면 벌점',
    'pos_limits': '관절이 움직일 수 있는 끝에 가까워지면 벌점',
    'joint_power': '관절 힘 × 관절 속도 (쓰는 전력) 가 크면 벌점',
    'base_height_l2': '몸통 높이가 목표 0.38 m 에서 벗어나면 벌점',
    'action_smoothness_l2': '행동이 연속 세 step 사이에서 꺾이면 벌점 (더 매끄럽게)',
    'undesired_contacts': '허벅지 · 종아리가 땅에 5 N 넘게 닿으면 벌점',
    'feet_regulation': '발이 땅에 붙은 채 옆으로 빠르게 끌리면 벌점 (발을 들고 옮기게)',
    'hip_pos_penalty_l1': '엉덩이 관절 (다리를 옆으로 벌리는 관절) 이 기본 자세에서 벗어나면 벌점',
    'joint_pos_penalty_l1': '허벅지 · 종아리 관절이 기본 자세에서 벗어나면 벌점',
}
# v2 이름 ↔ E1 이름 (같은 뜻)
PAIR = [('track_lin_vel_xy_exp', 'track_lin_vel_xy_exp', 'track_lin_vel_xy_exp'),
        ('track_ang_vel_z_exp', 'track_ang_vel_z_exp', 'track_ang_vel_z_exp'),
        ('lin_vel_z_l2', 'lin_vel_z_l2', 'lin_vel_z_l2'),
        ('ang_vel_xy_l2', 'ang_vel_xy_l2', 'ang_vel_xy_l2'),
        ('dof_torques_l2', 'joint_torques_l2', 'torques'),
        ('dof_acc_l2', 'joint_acc_l2', 'acc'),
        ('action_rate_l2', 'action_rate_l2', 'action_rate_l2'),
        ('feet_air_time', None, 'feet_air_time'),
        ('flat_orientation_l2', None, 'flat_orientation_l2'),
        ('dof_pos_limits', 'joint_pos_limits', 'pos_limits'),
        (None, 'joint_power', 'joint_power'),
        (None, 'base_height_l2', 'base_height_l2'),
        (None, 'action_smoothness_l2', 'action_smoothness_l2'),
        (None, 'undesired_contacts', 'undesired_contacts'),
        (None, 'feet_regulation', 'feet_regulation'),
        (None, 'hip_pos_penalty_l1', 'hip_pos_penalty_l1'),
        (None, 'joint_pos_penalty_l1', 'joint_pos_penalty_l1')]


def _g(x):
    return '0' if x == 0 else f'{x:+g}'


def _w(x):
    if x is None:
        return '<span class="na">없음</span>'
    if x == 0:
        return '0 <span class="sub">(꺼 둠)</span>'
    return f'{x:+g}'


def build(page, G):
    T = {}
    d = _dims()
    T.update({k: str(v) for k, v in d.items()})

    # ---------- 20000 전후 학습 곡선 ----------
    for run in ('E1', 'E2'):
        rows = list(csv.DictReader(open(os.path.join(OUT, 'curves', f'{run}_curves.csv'), encoding='utf-8')))
        mx = 'Metrics/base_velocity/max_command_x'
        assert _f(rows[19999][mx]) == 0.5 and _f(rows[20000][mx]) == 1.0, (run, '명령 상한이 20000 에서 0.5 → 1.0 이 아니다')
        for k, col in (('rw', 'Train/mean_student_reward'), ('ic', 'Episode_Termination/illegal_contact'), ('ns', 'Policy/mean_noise_std')):
            a = statistics.mean(_f(r[col]) for r in rows[19500:20000] if r[col] not in ('', 'nan'))
            b = statistics.mean(_f(r[col]) for r in rows[20400:20500] if r[col] not in ('', 'nan'))
            if k == 'ic':
                T[f'{run}_{k}_pre'], T[f'{run}_{k}_post'] = f'{a * 100:.1f}', f'{b * 100:.1f}'
            elif k == 'rw':
                T[f'{run}_{k}_pre'], T[f'{run}_{k}_post'] = f'{a:.1f}', f'{b:.1f}'
            else:
                T[f'{run}_{k}_pre'], T[f'{run}_{k}_post'] = f'{a:.2f}', f'{b:.2f}'
    log = open('C:/isaac/ext/go2_rl_robotlab/_runs/e1_seed42_n8192.log', encoding='utf-8', errors='replace').read()
    assert "Command range updated at iter 20000: {'lin_vel_x': [-1.0, 1.0], 'lin_vel_y': [-1.0, 1.0], 'ang_vel_yaw': [-1.5, 1.5]}" in log

    # ---------- 칸별 20000 → 20499 ----------
    TER = {'flat': '평지', 'wave': '물결', 'slope_up': '오르막', 'slope_down': '내리막', 'rough_slope': '거친 경사',
           'stairs_up': '계단 오르기', 'stairs_down': '계단 내리기', 'obstacles': '장애물'}
    CELLK = {'stand': '제자리', 'stop03': '0.3 걷다 멈춤', 'fwd01': '전진 0.1', 'fwd02': '전진 0.2', 'fwd03': '전진 0.3',
             'fwd05': '전진 0.5', 'back03': '후진 0.3', 'left03': '왼쪽 0.3', 'right03': '오른쪽 0.3', 'yawL05': '왼쪽 회전',
             'yawR05': '오른쪽 회전'}
    dr = []
    for r in page:
        for e in ('E1', 'E2'):
            dr.append((int(r[f'{e}_20499']) - int(r[f'{e}_20000']), e, r['noise'], r['terrain'], r['cell'], int(r[f'{e}_20000']), int(r[f'{e}_20499'])))
    T['drop_n'] = str(len(dr))
    T['drop10'] = str(sum(x[0] <= -10 for x in dr))
    T['rise10'] = str(sum(x[0] >= 10 for x in dr))
    stop = [x for x in dr if x[4] == 'stop03' and x[0] <= -10]
    T['drop10_stop'] = str(len(stop))
    worst = sorted(dr)[:8]
    rows = ''.join(
        f'<tr><td>{e}</td><td>{nz}</td><td>{TER[t.replace("·띠", "")]}{" · 띠" if t.endswith("·띠") else ""}</td><td>{CELLK[c]}</td>'
        f'<td class="num">{a}</td><td class="num">{b}</td><td class="num">{dd:+d}</td></tr>'
        for dd, e, nz, t, c, a, b in worst)
    T['worst_rows'] = rows
    g0 = G['Q 주 실행 · noise 끔 · 20000']
    g1 = G['Q 주 실행 · noise 끔 · 20499']
    T['avg_e1_20000'], T['avg_e1_20499'], T['avg_e2_20000'], T['avg_e2_20499'] = str(g0[0]), str(g1[0]), str(g0[1]), str(g1[1])

    # ---------- noise 켬 · 끔 의 멈추기 (E1 model_20499 평지) ----------
    for key, tag in (('off', 'fr_m20499_flat'), ('on', 'm20499_noise_flat')):
        rr = [r for r in csv.DictReader(open(os.path.join(OUT, tag, 'episodes.csv'), encoding='utf-8')) if r['cell'] == 'stop03']
        meta = json.load(open(os.path.join(OUT, tag, 'meta.json'), encoding='utf-8'))['args']
        assert meta['obs_noise'] == (key == 'on') and meta['checkpoint'].endswith('e1_seed42_n8192/model_20499.pt'), (tag, meta['obs_noise'])
        assert len(rr) == 100
        T[f'nz_{key}_pass'] = str(sum(r['q2_pass'] == 'True' for r in rr))
        T[f'nz_{key}_never'] = str(sum(_f(r['stop_t']) != _f(r['stop_t']) for r in rr))
        T[f'nz_{key}_yaw'] = f"{statistics.median(_f(r['stop_yawrate_rms']) for r in rr):.3f}"
        T[f'nz_{key}_spd'] = f"{statistics.median(_f(r['stop_speed_rms']) for r in rr):.3f}"
        T[f'nz_{key}_dist'] = f"{statistics.median(_f(r['stop_dist_m']) for r in rr) * 100:.0f}"
        st = [_f(r['stop_t']) for r in rr if _f(r['stop_t']) == _f(r['stop_t'])]
        T[f'nz_{key}_stopt'] = f'{statistics.median(st):.2f}'
        sd = [r for r in csv.DictReader(open(os.path.join(OUT, tag, 'episodes.csv'), encoding='utf-8')) if r['cell'] == 'stand']
        T[f'nz_{key}_stand'] = str(sum(r['q1_pass'] == 'True' for r in sd))

    # ---------- v2 대 E1 설정 ----------
    e1 = _yaml(os.path.join(E1RUN, 'params/env.yaml'))
    v2 = _yaml(os.path.join(LAB, 'models/foothold-v2.env.yaml'))
    v2card = json.load(open(os.path.join(LAB, 'models/foothold-v2.json'), encoding='utf-8'))
    e1w = {k: v['weight'] for k, v in e1['rewards'].items() if isinstance(v, dict)}
    v2w = {k: v['weight'] for k, v in v2['rewards'].items() if isinstance(v, dict)}
    cur = {v['term_name']: v for v in (x.get('params') for x in e1['curriculum'].values() if isinstance(x, dict)) if v and 'term_name' in v}
    assert set(e1w) == {p[1] for p in PAIR if p[1]} and set(v2w) == {p[0] for p in PAIR if p[0]}, ('보상 항 목록이 바뀌었다', set(e1w), set(v2w))
    rr = []
    for a, b, m in PAIR:
        wa = v2w.get(a) if a else None
        wb = e1w.get(b) if b else None
        cb = _w(wb)
        if b in cur:
            c = cur[b]
            cb = f'{_g(c["initial_weight"])} → {_g(c["final_weight"])} <span class="sub">({c["start_it"]:,}~{c["end_it"]:,} iter 동안 바뀜)</span>'
        if a is None:
            tag = '<span class="vd new">새로 생김</span>'
        elif b is None:
            tag = '<span class="vd gone">빠짐</span>' if (wa or 0) != 0 else '<span class="vd same">둘 다 없음</span>'
        elif wa == wb and b not in cur:
            tag = '<span class="vd same">같음</span>'
        else:
            tag = '<span class="vd diff">세기 다름</span>'
        name = a if (a and b and a == b) else (f'{a} → {b}' if (a and b) else (a or b))
        rr.append(f'<tr><td><code>{html.escape(name)}</code></td><td>{MEAN[m]}</td><td class="num">{_w(wa)}</td><td class="num">{cb}</td><td>{tag}</td></tr>')
    T['reward_rows'] = ''.join(rr)
    T['v2_nrew'] = str(sum(1 for v in v2w.values() if v != 0))
    T['e1_nrew'] = str(len(e1w))
    # 명령
    c1 = e1['commands']['base_velocity']
    rg = c1['ranges']
    T['e1_cmd0'] = f"앞뒤 {rg['lin_vel_x'][0]:+g}~{rg['lin_vel_x'][1]:+g} · 옆 {rg['lin_vel_y'][0]:+g}~{rg['lin_vel_y'][1]:+g} m/s · 회전 {rg['ang_vel_yaw'][0]:+g}~{rg['ang_vel_yaw'][1]:+g} rad/s"
    steps = sorted(c1['command_range_curriculum'], key=lambda x: x['iter'])
    T['e1_cmd_steps'] = ' → '.join(f"{s['iter']:,} iter: 앞뒤 ±{s['lin_vel_x'][1]:g} · 옆 ±{s['lin_vel_y'][1]:g} · 회전 ±{s['ang_vel_yaw'][1]:g}" for s in steps)
    T['e1_resample'] = f"{c1['resampling_time_range'][0]:g}"
    T['e1_limitp'] = f"{c1['limit_vel_prob'] * 100:.0f}"
    T['e1_zero'] = f"{c1['zero_command_curriculum']['end_value'] * 100:.0f}"
    vc = v2card['training']['commands']
    vf = v2card['training']['command_flags']
    T['v2_cmd'] = f"전진 {vc['lin_vel_x'][0]:g}~{vc['lin_vel_x'][1]:g} m/s 만 (후진 · 옆걸음 없음) · 회전 {vc['ang_vel_z'][0]:+g}~{vc['ang_vel_z'][1]:+g} rad/s"
    T['v2_stand'] = f"{vf['rel_standing_envs'] * 100:.0f}"
    T['v2_resample'] = f"{vf['resampling_time_range'][0]:g}"
    # 지형
    tm = v2card['training']['terrain_mix']
    NAME = {'boxes': '상자', 'hf_pyramid_slope': '경사', 'hf_pyramid_slope_inv': '거꾸로 경사', 'omni_gap': '틈 (gap)', 'pyramid_stairs': '계단',
            'pyramid_stairs_inv': '거꾸로 계단', 'rails': '레일', 'random_rough': '울퉁불퉁',
            'wave': '물결', 'slope_up': '오르막', 'slope_down': '내리막', 'rough_slope': '거친 경사', 'stairs_up': '계단 오르기',
            'stairs_down': '계단 내리기', 'obstacles': '장애물', 'stepping_stones': '징검다리 (stepping stones)', 'gap': '틈 (gap)', 'flat': '평지'}
    T['v2_terrain'] = ' · '.join(f'{NAME[k]} {v * 100:.0f} %' for k, v in tm.items())
    st = e1['scene']['terrain']['terrain_generator']['sub_terrains']
    T['e1_terrain'] = ' · '.join(f'{NAME[k]} {v["proportion"] * 100:.0f} %' for k, v in st.items())
    assert st['gap']['proportion'] == 0 and st['stepping_stones']['proportion'] == 0
    # v2 성적 (규격 2 · 난이도 0.5)
    sc = v2card['scores_difficulty_0_5']
    T['v2_gap'] = ' · '.join(f"{k} {v['unseen10']['gap']:.0f} %" for k, v in sc.items())
    T['v2_ss'] = ' · '.join(f"{k} {v['unseen10']['stepping_stones']:.0f} %" for k, v in sc.items())
    T['v2_iter'] = str(v2card['training']['max_iterations'] - 1)
    T['v2_envs'] = f"{v2card['training']['num_envs']:,}"
    # z_t · z_s 어긋남 (tb_latent_json.py 가 학습 기록에서 뽑은 latent.json)
    lat = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'latent.json'), encoding='utf-8'))
    for k, v in lat.items():
        assert v['n'] >= 90, (k, v['n'])
        T[f'lat_{k}'] = f"{v['angle_deg']:.1f}"
    return T


def fill(html_text, T):
    used = set(re.findall(r'%%(\w+)%%', html_text))
    miss = used - set(T)
    assert not miss, ('채울 값이 없는 자리', miss)
    for k in used:
        html_text = html_text.replace(f'%%{k}%%', T[k])
    return html_text
