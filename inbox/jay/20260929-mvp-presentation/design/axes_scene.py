# -*- coding: utf-8 -*-
"""두 잣대(축 1 지형 통과 · 축 2 명령 수행) 설명 장 + 21쪽 feet_air_time 애니메이션.

팀장 지시 2026-10-02:
  - 22쪽에 축 정의가 있지만 실험을 다 보고 나서 축을 보여 주니 해석이 안 된다.
    12쪽(4,096 환경) «앞»에 같은 틀(technical-page · 가운데 Go2 · 왼쪽 상자 · 클릭 단계)로 넣는다.
  - 축 1 의 생존 · 전진 · 속도 추종 · 방향 유지를 Go2 애니메이션으로.
  - 축 2 의 명령(전진 · 횡이동 · 회전)을 코드 + 설명 + 움직임으로.
  - feet_air_time 도 중3 이 알아듣게 애니메이션으로.
청자 기준: 중3 이 듣고 이해 + 석사가 보고 「잘했다」 판단. 카드마다 쉬운 한 줄 + 문턱값·코드 줄.

숫자·문턱은 손으로 적지 않고 소스에서 읽는다: 판정식 sim/eval/metrics.py, 명령 범위
models/foothold-v2.env.yaml, 보상 Isaac Lab rewards.py(저장소 밖이라 원문을 그대로 옮겨 적음).
Go2 프레임은 assets/go2-blender/build_v6.py 의 walk_side(864~935) · to_commands(936~959) · commands(720~863).
"""
import html
import re
from pathlib import Path

from .intro_story import make, src
from .experiment_frame import code_lines

HERE = Path(__file__).resolve().parent.parent
ROOT = HERE.parents[2]
GO2 = '../assets/go2-blender/'

AXES_TITLE = '잘 걷는지를, 두 잣대로 잽니다'
FEET_TITLE = '발을 들어 옮기는 경험을 보상 가중치로도 비교했습니다'
ARMY_TITLE = '한 대의 경험을, 4,096개 환경에서 함께 모읍니다'

# ── 판정 문턱을 코드에서 읽는다 (손으로 안 적는다) ───────────────────
def _thresholds():
    rec = (ROOT / 'sim/eval/record_terrain_demo.py').read_text(encoding='utf-8')
    gate = float(re.search(r'--gate_m", type=float, default=([0-9.]+)', rec).group(1))
    drift = float(re.search(r'--max_lateral_drift", type=float, default=([0-9.]+)', rec).group(1))
    mae = float(re.search(r'--max_velocity_mae", type=float, default=([0-9.]+)', rec).group(1))
    met = (ROOT / 'sim/eval/metrics.py').read_text(encoding='utf-8').splitlines()
    line = {name: next(i + 1 for i, l in enumerate(met) if l.startswith(f'def {name}('))
            for name in ('survival_success', 'progress_success', 'tracking_success', 'direction_success')}
    return gate, drift, mae, line

def _yaml_lines():
    y = (ROOT / 'models/foothold-v2.env.yaml').read_text(encoding='utf-8').splitlines()
    start = next(i + 1 for i, l in enumerate(y) if l.strip() == 'heading_command: true' and i > 900)
    end = next(i + 1 for i, l in enumerate(y) if i + 1 > start and l.strip() == 'heading: !!python/tuple') - 1
    return start, end

def _layer(steps, inner, cls=''):
    return f'<div class="tech-layer {cls}" data-only-step="{steps}">{inner}</div>'

def _caption(kicker, h3, p):
    return f'<div class="axes-caption"><small>{kicker}</small><h3>{h3}</h3><p>{p}</p></div>'

GAUGE = ('<svg class="cond-gauge" viewBox="0 0 200 54" aria-hidden="true">'
         '<rect class="band" x="62" y="14" width="76" height="12" rx="2"/>'
         '<line class="axis" x1="10" y1="20" x2="190" y2="20"/>'
         '<line class="cmd" x1="100" y1="8" x2="100" y2="32"/>'
         '<text x="100" y="48">명령 1.0</text><text x="62" y="48" class="lo">0.75</text><text x="138" y="48" class="hi">1.25</text>'
         '<polygon class="needle" points="100,34 95,42 105,42"/></svg>')

def axes_slide():
    gate, drift, mae, line = _thresholds()
    cards = [
        ('조건 1', '생존', '넘어지지 않았다', '몸통이 바닥에 닿아 판이 끝나면 실패',
         f'survival_success · metrics.py:{line["survival_success"]}', ''),
        ('조건 2', '전진', f'{gate:g} m 선을 넘었다', '출발점에서 앞으로 간 거리',
         f'forward_progress_m ≥ {gate:g} · :{line["progress_success"]}', ''),
        ('조건 3', '속도 추종', '시킨 속도로 갔다', f'명령 속도와 실제 속도의 평균 차이 {mae:g} m/s 안',
         f'velocity_mae_mps ≤ {mae:g} · :{line["tracking_success"]}', GAUGE),
        ('조건 4', '방향 유지', '진로를 지켰다', f'{gate:g} m 지점에서 옆으로 {drift:g} m 안',
         f'gate_lateral_drift_m ≤ {drift:g} · :{line["direction_success"]}', ''),
    ]
    cond = '<div class="axes-cards cond-cards">'
    for i, (k, h, easy, hard, code, extra) in enumerate(cards, 1):
        cond += (f'<article class="cond-card" data-on-from="{i}"><small>{k}</small><h3>{h}</h3>'
                 f'<p class="easy">{easy}</p><p class="hard">{hard}</p>{extra}<code>{code}</code></article>')
    cond += '</div>'
    track = (f'<svg class="axes-track" viewBox="0 0 1120 170" aria-hidden="true">'
             '<path class="ground" d="M0 95 H560 L560 140 H640 L640 95 H1120"/>'
             '<path class="ground-fill" d="M560 95 L560 140 H640 L640 95 Z"/>'
             '<line class="tick" x1="276" y1="78" x2="276" y2="112"/><text x="276" y="132">출발</text>'
             f'<line class="tick goal" x1="820" y1="66" x2="820" y2="112"/><text class="goal" x="820" y="132">전진 {gate:g} m</text>'
             '<text class="gap-label" x="600" y="162">틈</text>'
             '<g class="lane"><line x1="0" y1="150" x2="1120" y2="150"/><line x1="0" y1="166" x2="1120" y2="166"/>'
             f'<text x="1118" y="146" class="lane-label">위에서 본 진로 · 차선 ±{drift:g} m</text></g></svg>'
             '<i class="lane-dot"><b></b></i>')
    ystart, yend = _yaml_lines()
    code = html.escape('\n'.join(code_lines('models/foothold-v2.env.yaml', ystart, yend)))
    cmd = ('<div class="axes-cards cmd-cards">'
           '<article class="cond-card cmd-card" data-from="720"><small>명령 1 · vₓ</small><h3>앞으로</h3><p class="easy">전진 속도를 시킵니다</p><code>lin_vel_x 0.4 ~ 1.5 m/s</code></article>'
           '<article class="cond-card cmd-card locked" data-from="768"><small>명령 2 · vᵧ</small><h3>옆으로</h3><p class="easy">횡이동 · 이번 학습은 0 으로 잠금</p><code>lin_vel_y 0.0 ~ 0.0</code></article>'
           '<article class="cond-card cmd-card" data-from="816"><small>명령 3 · ωz</small><h3>제자리 회전</h3><p class="easy">도는 속도를 시킵니다</p><code>ang_vel_z −1.0 ~ 1.0 rad/s</code></article>'
           '</div>')
    codecard = (f'<figure class="exp-code axes-code"><figcaption>models/foothold-v2.env.yaml:{ystart}–{yend} · 학습에 준 명령 범위</figcaption>'
                f'<pre>{code}</pre></figure>')
    nine = ('<div class="axes-nine"><small>축 2 · 평지 아홉 칸 · 명령에만 반응시킨다 (지형을 섞으면 원인이 안 갈린다)</small>'
            '<div><b>정지</b><span>4초 걷다 명령 0 → 넘어지지 않나 (낙상 ≤ 3 %)</span></div>'
            '<div><b>유지</b><span>20초 내내 명령 0 → 안 넘어지고 · 안 미끄러지고(≤ 0.005 m/s) · 관절이 안 떨리나(≤ 0.01)</span></div>'
            '<div><b>회전</b><span>제자리 회전 → 안 넘어지고(낙상 ≤ 10 %) · 명령 네 크기(±0.5 · ±1.0 rad/s)를 각각 따라 도나(≥ 0.40)</span></div>'
            '<p>두 잣대를 <b>다</b> 통과해야 다음 판으로 · 체크포인트 1500 · 2000 · 2500 · 3000 에서 전부</p></div>')
    body = ('<div class="technical-world axes-world">'
            + track
            + f'<canvas class="axes-player" width="1600" height="1200" aria-label="Go2 옆모습 걷기와 명령 애니메이션"></canvas>'
            + f'<img class="axes-print" src="{GO2}go2-side_walk-v6.png" alt="Go2 옆모습">'
            + _layer('0 1 2 3 4', _caption('축 1 · 지형 통과', '건넜는가?', '한 판마다 네 가지를 묻습니다.<br>하나라도 아니면 그 판은 실패입니다.'))
            + _layer('5', _caption('축 1 · 성공의 정의', '넷 다 만족해야 성공', '16종 지형 × 3속도 × 100판<br>= 모델당 <b>4,800판</b> · 같은 조건'))
            + _layer('6 7', _caption('축 2 · 명령 수행', '시키는 대로<br>움직였는가?', '평지에서 명령만 바꿔 봅니다.<br>지형을 섞으면 원인이 안 갈립니다.'))
            + _layer('0 1 2 3 4 5', cond, 'axes-axis1')
            + _layer('5', '<p class="axes-next">성공률이 낮다 ≠ 넘어졌다 · 넷 중 하나만 깨져도 실패</p>')
            + _layer('6 7', cmd + codecard, 'axes-axis2')
            + _layer('7', nine)
            + '<p class="axes-note">설명용 도식 · 축척 · 속도 · 발 궤적은 실측이 아닙니다 · 판정 코드 sim/eval/metrics.py</p>'
            + '</div>')
    spoken = ('학습에 앞서 「잘 걷는다」를 무엇으로 셀지 정했습니다. 잣대는 둘입니다. 첫째, 험한 지형을 건넜는가. '
              '(클릭) 건넜다고 치려면 네 가지를 한꺼번에 물었습니다. 첫째, 살아남았는가. 몸통이 바닥에 닿아 판이 끝나면 실패입니다. '
              f'(클릭) 둘째, 앞으로 갔는가. {gate:g}미터 선을 넘어야 합니다. '
              f'(클릭) 셋째, 시킨 속도를 따랐는가. 명령 속도와 실제 속도의 차이가 평균 {mae:g}미터 매 초 안이어야 합니다. 느려지면 건너도 실패입니다. '
              f'(클릭) 넷째, 진로를 지켰는가. {gate:g}미터 지점에서 옆으로 {drift:g}미터 넘게 벗어나면 실패입니다. '
              '(클릭) 이 넷을 모두 만족해야 그 판은 성공입니다. 16종 지형에 세 속도, 각 100판, 모델당 4,800판을 같은 조건으로 쟀습니다. '
              '그래서 뒤에 나올 성공률이 낮다고 해서 곧 넘어졌다는 뜻은 아닙니다. '
              '(클릭) 둘째 잣대는 명령입니다. 앞으로, 옆으로, 제자리 회전. 몸체 기준 속도 세 개가 명령이고, 학습에서 어떤 범위를 줬는지는 설정 파일 그대로입니다. '
              '이번 학습은 횡이동을 0 으로 잠갔습니다. '
              '(클릭) 이 잣대는 평지에서 따로 잽니다. 정지, 유지, 회전 아홉 칸이고, 두 잣대를 다 통과해야 다음 판으로 올렸습니다.')
    return make('학습과 평가', AXES_TITLE, body, spoken,
                src('성공 판정식 · 축 2 아홉 칸 · 근거', '../../../../docs/research/20260928-v2-mvp-report.md'),
                kind='intro authored technical-page axes-page', steps=7,
                note='Go2 옆모습 걷기는 build_v6.py 의 설명용 기구학(gait_pose)이지 정책 출력이 아니다. 네 조건의 문턱은 record_terrain_demo.py 기본값과 metrics.py 함수에서 읽었다. 명령 범위는 foothold-v2.env.yaml 의 실제 줄이다.')

# ── 21쪽 · feet_air_time ────────────────────────────────────────
REWARD_SNIPPET = '''first_contact = contact_sensor.compute_first_contact(env.step_dt)[:, sensor_cfg.body_ids]
last_air_time = contact_sensor.data.last_air_time[:, sensor_cfg.body_ids]
reward = torch.sum((last_air_time - threshold) * first_contact, dim=1)
# no reward for zero command
reward *= torch.norm(env.command_manager.get_command(command_name)[:, :2], dim=1) > 0.1'''

def _feet_cfg():
    out = {}
    for tag in ('v1', 'v2'):
        y = (ROOT / f'models/foothold-{tag}.env.yaml').read_text(encoding='utf-8').splitlines()
        i = next(k for k, l in enumerate(y) if l.strip() == 'feet_air_time:')
        block = y[i:i + 40]
        thr = float(next(l for l in block if 'threshold:' in l).split(':')[1])
        w = float(next(l for l in block if l.strip().startswith('weight:')).split(':')[1])
        end = i + next(k for k, l in enumerate(block) if l.strip().startswith('weight:')) + 1
        out[tag] = dict(threshold=thr, weight=w, start=i + 1, end=end)
    return out

def feet_air_body(old_body):
    cfg = _feet_cfg()
    thr = cfg['v2']['threshold']
    chart = re.search(r'<div class="rr-reward-chart">.*?</div>(?=<p class="rr-condition")', old_body, re.S)
    assert chart, 'rr-reward-chart 없음'
    tail = old_body[chart.end():]
    tail = re.sub(r'</div></div>$', '', tail)
    rows = ''.join(f'<div class="fat-row" data-leg="{leg}"><span>{name}</span><div class="fat-bar"><i></i><em></em></div><b class="fat-badge"></b></div>'
                   for leg, name in [('FL', '앞왼발'), ('FR', '앞오른발'), ('RL', '뒤왼발'), ('RR', '뒤오른발')])
    body = ('<div class="rr-wrap fat-wrap"><div class="fat-grid">'
            '<div class="fat-scene"><div class="fat-stage">'
            '<canvas class="fat-player" width="1600" height="1200" aria-label="Go2 옆모습 걷기 · 발 공중 시간"></canvas>'
            f'<img class="fat-print" src="{GO2}go2-side_walk-v6.png" alt="Go2 옆모습"></div>'
            f'<div class="fat-bars">{rows}<small>막대: 발이 공중에 있는 시간 · 세로선: 문턱 {thr:g} s · 내려놓는 순간 +/−</small></div>'
            f'<p class="fat-mode"><span data-m="0">발을 들어 옮긴다 → 공중 {thr:g} s 를 넘기면 <b class="ok">보상 +</b></span>'
            f'<span data-m="1">짧게 짧게 뗀다 → {thr:g} s 에 못 미쳐 <b class="bad">보상 −</b></span></p></div>'
            '<div class="fat-side"><h3>feet_air_time</h3>'
            f'<p>발을 땅에서 뗀 뒤 다시 내려놓기까지의 시간을 잽니다. {thr:g}초보다 길면 점수를, 짧으면 벌점을 줍니다. '
            '서 있으라는 명령(0)일 때는 점수가 없습니다.<small>발 높이나 착지 위치를 직접 보상하는 항은 아닙니다. 기존 Isaac Lab 보상항이고 가중치만 비교했습니다.</small></p>'
            f'<figure class="exp-code fat-code"><figcaption>isaaclab_tasks · locomotion/velocity/mdp/rewards.py:41–45 · threshold {thr:g} · '
            f'weight v1 {cfg["v1"]["weight"]:g} → v2 {cfg["v2"]["weight"]:g} (foothold-v2.env.yaml:{cfg["v2"]["start"]}–{cfg["v2"]["end"]})</figcaption>'
            f'<pre>{html.escape(REWARD_SNIPPET)}</pre></figure>'
            + chart.group(0) + '</div></div>' + tail + '</div>')
    return body

def apply(slides):
    titles = [s['title'] for s in slides]
    assert AXES_TITLE not in titles
    i = titles.index(ARMY_TITLE)
    slides.insert(i, axes_slide())
    feet = next(s for s in slides if s['title'] == FEET_TITLE)
    feet['body'] = feet_air_body(feet['body'])
    feet['kind'] = (feet.get('kind', '') + ' feetair-page').strip()
    feet['spoken'] = ('발 체공 시간, feet_air_time 은 발을 뗀 뒤 다시 내려놓기까지의 시간입니다. 0.5초보다 길면 점수, 짧으면 벌점입니다. '
                      '발을 들어 옮기라는 뜻이지 끌라는 뜻이 아닙니다. 새 보상항을 만든 것이 아니라 Isaac Lab 에 있던 항의 가중치만 비교했습니다. '
                      + feet['spoken'])
    return slides
