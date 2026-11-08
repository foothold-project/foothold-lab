"""Render a complete N21 seed-width audit. Refuses partial inputs."""
from pathlib import Path
from collections import Counter
import csv
import argparse
import hashlib
import json
import shutil
import subprocess
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

parser = argparse.ArgumentParser()
parser.add_argument('--audit-dir', type=Path, default=Path('D:/mai-tmp/analyst/n21-seedwidth-1108'))
args = parser.parse_args()
SCRATCH = args.audit_dir
ROOT = Path('D:/mai-wt/foothold-lab/analyst-ex41-score-name-1102')
OUT = ROOT / '_out/reports/N21-seedwidth-1108'
REPORT = ROOT / '_out/reports/REPORT-analyst-N21-seedwidth-1108.md'
d = json.loads((SCRATCH / 'audit.json').read_text(encoding='utf-8'))
assert d['complete'] and d['npz_count'] == 288 and len(d['protocol']) == 12
assert len(d['comparison']) == 102  # 48 survival, 54 error components (stop has two units)
assert all(r['code_head'].startswith('7916a52') and r['gpu'] == 'cuda:0' for r in d['protocol'] if r['eval_seed'] in [43, 44])
OUT.mkdir(parents=True, exist_ok=True)
for p in SCRATCH.iterdir():
    if p.suffix in ['.csv', '.json']:
        if p.resolve() != (OUT / p.name).resolve():
            shutil.copyfile(p, OUT / p.name)
for name in ['n21_seedwidth_1108.py', 'n21_seedwidth_report_1108.py']:
    source = Path(__file__).resolve().parent / name
    if source.resolve() != (OUT / name).resolve():
        shutil.copyfile(source, OUT / name)

MODES = ['eval_gt', 'eval_pred', 'probe_prop_only']
LABEL = {'eval_gt': '정답', 'eval_pred': '복원', 'probe_prop_only': '끔'}
EN = {'eval_gt': 'GT', 'eval_pred': 'Pred', 'probe_prop_only': 'Map off'}
TERRAINS = ['flat', 'continuous']
CMDS = ['fwd0.5', 'fwd1.0', 'spin+1.2', 'spin-1.2', 'back0.5', 'side+0.5', 'side-0.5', 'stop']
comps = d['comparison']
errors = [r for r in comps if r['metric'] != 'alive']
alive = [r for r in comps if r['metric'] == 'alive']

def table(headers, rows):
    def safe(x): return str(x).replace('|', r'\|').replace('\n', ' ')
    return '\n'.join(['| ' + ' | '.join(map(safe, headers)) + ' |',
                      '| ' + ' | '.join(['---'] * len(headers)) + ' |'] +
                     ['| ' + ' | '.join(map(safe, row)) + ' |' for row in rows])

def fmt(x, integer=False):
    return str(int(x)) if integer else f'{x:.4f}'

def span(r, c, integer=False):
    return fmt(r[c + '_min'], integer) + '~' + fmt(r[c + '_max'], integer)

def triplet(r, c, integer=False):
    return ' / '.join(fmt(x, integer) for x in r[c])

def cell(t, m, c, metric):
    return next(r for r in comps if (r['terrain'], r['mode'], r['command'], r['metric']) == (t, m, c, metric))

def plot(name, selections, unit):
    fig, axs = plt.subplots(2, 3, figsize=(14, 7), sharex=True, sharey=True)
    for ti, t in enumerate(TERRAINS):
      for mi, m in enumerate(MODES):
        ax = axs[ti, mi]
        for ci, (cmd, metric) in enumerate(selections):
            r = cell(t, m, cmd, metric)
            for cond, offset, color in [('off', -.14, '#1f648e'), ('on', .14, '#ab480d')]:
                y = ci + offset
                ax.plot([r[cond + '_min'], r[cond + '_max']], [y, y], color=color, linewidth=2.5)
                for i, marker in enumerate(['o', '^', 's']):
                    ax.scatter(r[cond][i], y, s=30, marker=marker, color=color,
                               label=f'{cond}, s{42+i}' if ti == 0 and mi == 0 and ci == 0 else None, zorder=3)
        ax.set_title(t + ' · ' + EN[m])
        ax.set_yticks(range(len(selections)), [c if metric != 'stop_wz' else 'stop yaw' for c, metric in selections])
        ax.grid(axis='x', alpha=.22)
        ax.set_xlabel(unit)
    axs[0, 0].invert_yaxis()
    handles, labels = axs[0, 0].get_legend_handles_labels()
    fig.legend(handles, labels, loc='upper center', bbox_to_anchor=(.5, .955), ncol=6, frameon=False)
    fig.suptitle('Seed-wise values and observed min-max (not confidence intervals)', y=.995)
    fig.tight_layout(rect=(0, 0, 1, .91))
    fig.savefig(OUT / name, dpi=160)
    plt.close(fig)

plot('linear_error_seed_ranges.png', [('fwd0.5', 'vx'), ('fwd1.0', 'vx'), ('back0.5', 'vx'), ('side+0.5', 'vy'), ('side-0.5', 'vy'), ('stop', 'stop_xy')], 'Median error / residual speed (m/s)')
plot('angular_error_seed_ranges.png', [('spin+1.2', 'wz'), ('spin-1.2', 'wz'), ('stop', 'stop_wz')], 'Median yaw error (rad/s)')

files = ['foothold_s2/eval/eval_map_modes.py', 'foothold_s2/eval/n21_dr_record.py', 'foothold_s2/runners/start_runner.py']
for old in ['d1dfd4f9', '1771ee04']:
    content = subprocess.check_output(['git', 'diff', '--unified=0', old, '7916a52fa07c6774eb59db2b69f4b7a5068cea63', '--', *files], cwd=ROOT)
    (OUT / f'source_diff_{old}_to_7916a52.txt').write_bytes(content)

def category_counts(rows):
    return sum(r['morning_over_width'] for r in rows), sum(not r['morning_over_width'] for r in rows)

lines = [
    '> 분류: A/평가 · N21 시드 간 폭',
    '> 작성: analyst · ' + d['read_at'].replace('T', ' '),
    '> 근거: 같은 m12000 평가 영수증 12개 · NPZ 288개 · seed42/43/44 · 오전 N21 표 재대조',
    '> 요지: 시드별 생존과 추종 오차의 범위를 분리하고, 오전 DR 차이를 그 관측 폭과 비교한다.',
    '> 상태: record_only 기술 통계 · 승급/중단 판정 없음 · GPU/Kit 신규 실행 없음',
    '', '# N21 · 시드 42·43·44 사이의 관측 폭', '',
    '## 먼저 읽을 내용', '',
    f'- [실측] 생존 {len(alive)}칸 중 오전 on/off 차이의 크기가 양쪽 시드 폭보다 큰 칸은 {category_counts(alive)[0]}개, 폭 이하인 칸은 {category_counts(alive)[1]}개다. 추종 오차·정지 잔류 속도 {len(errors)}성분은 각각 {category_counts(errors)[0]}개와 {category_counts(errors)[1]}개다. 정지의 m/s와 rad/s는 별도 성분이다.',
    f'- [실측] 세 시드 모두 같은 방향의 on/off 차이를 보인 오차 성분은 {sum(r["all_positive"] or r["all_negative"] for r in errors)}/{len(errors)}다. 이 수와 위의 폭 비교는 다른 질문이다. 모든 칸의 실제 숫자는 아래 표와 CSV에 있다.',
    '- [해석 한계] 이 폭은 신뢰구간이나 합격선이 아니다. 세 평가 시드에서 관측한 최솟값과 최댓값일 뿐이며, 그 안에 드는 차이를 “효과 없음”이라고 부르지 않는다. 밖에 있는 차이도 통계적 유의성이나 DR 인과 효과로 확정하지 않는다.',
    '- [조건] 같은 정책·L2·64 env·300 step이지만 seed42는 이전 코드 판, 평지 off는 GPU1이다. seed43/44는 고정 7916a52·GPU0이다. 변경된 코드의 평가 경로를 대조했고 아래에 범위를 적었다. 연속 지형 생성 시드도 바뀌므로 순수한 동일 장면 재측정 잡음이 아니다.',
    '', '## 1. 실제로 다른 시드였나', '',
    '영수증 eval_seed, run_identity.eval_seed, 각 NPZ의 run_identity를 각각 대조했다. 아래 12판은 모두 기대한 시드와 일치한다. checkpoint SHA는 모두 `1c6af6319c823c718af4965064f1c312b0d25177f5223a49c323aab3b6f1e613`이다. actor/critic은 같은 저장본이며 새로 학습한 시드 세 개가 아니다.', '',
    table(['지형', 'DR', 'seed', '코드 HEAD', 'GPU', 'NPZ 수'], [[r['terrain'], r['dr'], r['eval_seed'], r['code_head'][:8], r['gpu'], 24] for r in d['protocol']]), '',
    table(['지형', '시드 짝', '질량이 다른 env', '마찰이 다른 env', '밀기 배열이 다른 칸'],
          [[r['terrain'], '/'.join(map(str, r['seeds'])), f"{r['mass_changed_envs']}/64", f"{r['material_changed_envs']}/64", f"{r['push_changed_cells']}/24"] for r in d['physical_seed_checks']]), '',
    table(['지형', 'DR', '시드 짝', 'start_xy 다른 칸', 'vx 시계열 다른 칸'],
          [[t, c, f'{a}/{b}',
            f"{sum(not r['start_xy_equal'] for r in d['array_seed_checks'] if (r['terrain'],r['dr'],r['seeds']) == (t,c,[a,b]))}/24",
            f"{sum(not r['vx_equal'] for r in d['array_seed_checks'] if (r['terrain'],r['dr'],r['seeds']) == (t,c,[a,b]))}/24"]
           for t in TERRAINS for c in ['off', 'on'] for a, b in [(42,43),(42,44),(43,44)]]), '',
    'DR-on 질량 가산 −1~+3 kg·정적/동적 마찰 0.2~1.2 범위와 dynamic≤static을 세 시드 모두 다시 확인했다. 같은 시드에서는 평지/연속 지형의 질량·마찰이 같고, 각 판의 24칸에서도 같은 물성을 재사용한다. 따라서 이를 6개 또는 72개의 독립 물리 시드로 세지 않는다. DR-off의 실제 물성 배열은 여전히 기록에 없어 nominal 물성 실측 검증은 미완이다.', '',
    '영수증의 terrain_hash는 env에 배정된 종류·레벨·열의 해시다. 모든 판에서 같은 배치를 확인했지만 메시 바이트 동일성을 뜻하지 않는다. N21은 `configure_terrain(..., eval_seed)`로 지형 생성기 seed도 바꾼다. 연속 지형의 무작위 기하가 영향을 받는 범위는 이 평가 변동에 포함되며, 메시 자체는 영수증에 보존되지 않았다.', '',
    '## 2. 어떻게 폭을 계산했나', '',
    '1. 각 env의 생존 중 명령 대비 절대오차 평균을 구한 뒤 64 env 중앙값을 구한다. 전진·후진은 vx, 횡 이동은 vy, 회전은 wz다. 정지는 수평 속도와 yaw 절댓값을 따로 쓴다. 중간 종료 env도 살아 있던 구간의 오차에 포함되므로 생존 표를 같이 본다.',
    '2. 그렇게 얻은 seed42/43/44 중앙값 세 개의 min~max가 조건별 시드 범위이며, 폭은 max−min이다. 생존은 각 시드의 끝까지 생존 인원(분모64) 세 개로 같은 계산을 한다. 세 시드의 env를 한데 섞어 중앙값을 다시 만들지 않는다.',
    '3. 오전 차이 Δ42 = on42−off42. 비교 폭 W = max(on 폭, off 폭). 절댓값(Δ42)>W이면 “큼”, 같거나 작으면 “안”으로 적는다[분석 정의]. 한쪽의 작은 폭만 골라 비교하지 않는다. 수치 반올림 전 값으로 계산한다.',
    '4. `comparison.csv`에는 세 개의 on−off 차이와 범위 겹침도 같이 넣었다. “큼”이면서도 새 시드에서 부호가 바뀔 수 있다. 이는 실제 답을 아는 반례로 생성기를 확인했다. 어느 표기도 학습 판정에 연결하지 않는다.', '',
    '## 3. 생존 · 세 시드 인원과 범위', '',
    '인원 단위이며 모든 분모는64다. 각 묶음의 순서는42/43/44. Δ42가 양수면 오전 on에서 더 많이 살아남은 것이다. 생존은 정상 보행·추종 성공을 의미하지 않는다.', '',
]
example = cell('flat', 'eval_pred', 'spin-1.2', 'wz')
key_moves = [r for r in errors if r['command'] in ['fwd1.0', 'side+0.5', 'side-0.5']]
assert all(r['morning_over_width'] and r['all_positive'] for r in key_moves)
assert example['morning_over_width'] and not (example['all_positive'] or example['all_negative'])
concrete = [
    f'- [실측] 평지·연속 지형의 전진1.0·횡±0.5는 지도 셋, 총 {len(key_moves)}칸 모두 세 시드에서 on 오차가 더 컸다. 오전 차이는 모두 폭보다 컸다. 현재 평가의 on 조건에서 큰 오차가 반복 관측됐다는 뜻이며, 학습을 더 해야 하는지의 판정은 아니다.',
    '- [실측 반례] 평지·복원·회전−1.2의 Δ42는 '+fmt(example['delta42'])+' rad/s, 폭은 '+fmt(example['width_max'])+' rad/s라 크기만 보면 “큼”이다. 하지만 시드별 차이는 '+', '.join(f'{x:+.5f}' for x in example['delta_by_seed'])+' rad/s로 부호가 뒤집힌다. 이 칸을 “DR에서 회전 개선”이라고 읽지 않는다.',
]
position = lines.index('## 1. 실제로 다른 시드였나')
lines[position:position] = concrete + ['']
for t in TERRAINS:
    lines += ['### ' + ('평지' if t == 'flat' else '연속 7종 혼합'), '',
              table(['지도·명령', 'off 42/43/44', 'on 42/43/44', 'off 범위', 'on 범위', 'Δ42', 'W', '폭 비교'],
                    [[LABEL[r['mode']]+' · '+r['command'], triplet(r,'off',True),triplet(r,'on',True),span(r,'off',True),span(r,'on',True),fmt(r['delta42'],True),fmt(r['width_max'],True),'큼' if r['morning_over_width'] else '안'] for r in alive if r['terrain']==t]), '']
lines += ['## 4. 추종 오차 중앙값 · 세 시드 범위', '',
          'Δ42가 양수면 오전 on의 오차가 더 컸다는 뜻이다. “같은 방향”은 42·43·44 모두 on−off가 양수(+), 음수(−)인지이며, 섞이면 “혼합”이다. 단위가 다른 정지 성분은 합산하지 않는다.', '',
          '![속도 오차의 시드별 범위](N21-seedwidth-1108/linear_error_seed_ranges.png)', '',
          '![회전 오차의 시드별 범위](N21-seedwidth-1108/angular_error_seed_ranges.png)', '',
          '점은 각 시드, 선분은 관측 min~max다. 신뢰구간이 아니다. 파랑은off, 갈색은on이다.', '']
for t in TERRAINS:
    lines += ['### ' + ('평지' if t=='flat' else '연속 7종 혼합'), '',
              table(['지도·명령·성분', '단위', 'off min~max', 'on min~max', 'Δ42', 'W', '폭 비교', '세 시드 방향'],
                    [[LABEL[r['mode']]+' · '+r['command']+' · '+r['metric'], r['unit'], span(r,'off'),span(r,'on'),fmt(r['delta42']),fmt(r['width_max']), '큼' if r['morning_over_width'] else '안', '+' if r['all_positive'] else '−' if r['all_negative'] else '혼합/0'] for r in errors if r['terrain']==t]), '']
lines += ['## 5. 어디까지 말할 수 있나', '',
          '- [실측] 해당 m12000 정책을 같은 명령·레벨·표본 길이에서 평가했을 때의 관측 폭을 얻었다. 64 env·6초를 3회 평가했으며, 학습 시드 일반화 시험은 아니다. 시드 범위는 샘플을 더 얻으면 넓어질 수 있다.',
          '- [한계] 오전 on은d1dfd4f9, off는1771ee04, 이번 반복은7916a52다. source_sha256 비교와 git diff에서 on 평가기에 대한 변경은 off 모드 허용·영수증이고, start_runner 변경은 EX42 학습 전이·회차 경로다. 이번 N21 평가 호출 경로의 바뀐 처치는 찾지 못했으나 모든 판이 동일 바이너리였다고 적지 않는다. diff 원문은 산출 폴더에 보존했다.',
          '- [한계] 평지 off seed42는GPU1, seed43/44는GPU0이다. 따라서 세 시드의 폭에 장치·실행 비결정성이 함께 섞일 수 있다. 같은 seed on/off도 DR의 추가 난수 소비 때문에 초기 자세·관측 잡음 궤적이 같지 않다.',
          '- [한계] DR은 마찰 하나가 아니라 질량·COM·이득·세기·지연·밀기 묶음이다. 명령 시작 2초에 단 한 번 미는 평가이므로 정지 오차에는 밀기 뒤 회복 움직임이 들어간다. 어느 DR 성분이 차이를 만들었는지는 이 표로 분리할 수 없다.',
          '- [한계] 연속 지형 혼합은 계단15+역형계단15+boxes12+rough12+경사4+역경사4+stage_stairs2다. 전체64의 폭이 희소한 종류별 안정성을 보증하지 않는다. 어려운 L5/L9, 장시간, 명령 전환, 실기는 범위 밖이다.',
          '- [한계] vx와 생존은 NPZ 원시 시계열에서 다시 셌다. vy/wz 원시 시계열은 이 NPZ에 없으므로 JSON의 env별 요약을 재집계한 수준이다. 영상·접촉 위상·발 미끄럼을 새로 판독하지 않았으며, 숫자만으로 보행 품질 또는 넘어짐 원인을 단정하지 않는다.', '',
          '## 6. 재현과 근거', '',
          table(['항목', '근거'], [
              ['원자료·해시', 'N21-seedwidth-1108/audit.json inputs · JSON12/NPZ288 · 원자료는 읽기만'],
              ['시드→지형/환경', 'runner-ex42-w65-7916a52/foothold_s2/eval/eval_map_modes.py:157 · n21_dr_record.py:167'],
              ['시드→각 명령 reset', '같은 eval_map_modes.py:399~408 · 평균 행동 :465'],
              ['밀기 시드·시각', '같은 eval_dr_mode.py:171~174 · readback.push_events[0], 모든 셀 2.0초'],
              ['지형 생성기의 seed', 'C:/isaac/isaaclab/source/isaaclab/isaaclab/terrains/terrain_generator.py:139~148 · :363'],
              ['오전 대조', 'REPORT-analyst-N21-1108.md · N21-1108/audit.json, seed42 48칸 생존·54오차 성분 일치'],
              ['CSV', 'cells.csv: 각 시드값 · comparison.csv: 폭·차이 · seed_array_checks.csv: 실제 배열 비교'],
              ['생성기', 'N21-seedwidth-1108/n21_seedwidth_1108.py · n21_seedwidth_report_1108.py'],
              ['답을 아는 입력', str(d['known_answer_tests'])+'건: 중앙값·폭 경계·부호 반전·0폭·행 비교·단위 분리·비유한값 거절'],
          ]), '',
          '집계기에서 입력 해시를 보존하고, JSON↔NPZ의 시드·체크포인트·GPU·생존·alive 샘플 수를 대조했다. 모든 오차 중앙값은 NumPy와 표준 라이브러리 statistics.median의 두 계산이 일치했다. 결과 후 임계값을 넓히거나 승급 판정을 만들지 않았다.', '',
          '재현: 보존한 `n21_seedwidth_1108.py --out <집계 폴더>` 실행 뒤 `n21_seedwidth_report_1108.py --audit-dir <집계 폴더>`를 실행한다. CPU Python은 `C:/Users/AI-WS01/anaconda3/envs/isaac311/python.exe`. 입력은 위 원자료 경로 그대로 필요하다.', '']
REPORT.write_text('\n'.join(lines), encoding='utf-8')
for p in [REPORT, *OUT.glob('*.csv')]:
    assert '\u2014' not in p.read_text(encoding='utf-8-sig')
manifest = []
for p in sorted(OUT.iterdir()):
    if p.is_file() and p.name != 'SHA256SUMS':
        if p.suffix != '.png':
            p.write_bytes(p.read_bytes().replace(b'\r\n', b'\n'))
        manifest.append(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+p.name)
(OUT/'SHA256SUMS').write_text('\n'.join(manifest)+'\n', encoding='utf-8')
print(json.dumps({'report':str(REPORT),'error_larger_within':category_counts(errors),'survival_larger_within':category_counts(alive),
                  'error_disjoint_intervals':sum(r['intervals_disjoint'] for r in errors)},ensure_ascii=False))
