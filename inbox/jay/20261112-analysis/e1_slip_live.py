#!/usr/bin/env python3
"""Read-only CPU TensorBoard comparison, manually refreshed, no Isaac imports.

The fixed 50-update definitions were supplied by lead-lx on 2026-11-12:
mean(abs(slip_i)/linear_i, i=41..50) in [0.02, 0.08];
mean(linear_new[31..50]) >= 0.90 * mean(linear_control[31..50]).
Later windows are measurements only, not newly authorized execution gates.
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime
import hashlib
import json
import math
from pathlib import Path
import shlex
import statistics
import tempfile

LIN = 'Episode_Reward/track_lin_vel'
ANG = 'Episode_Reward/track_ang_vel'
SLIP = 'Episode_Reward/ex41_foot_slip'
REWARD = 'Train/mean_reward'
LENGTH = 'Train/mean_episode_length'
TERRAIN = 'Curriculum/terrain_levels'
BAD = 'Episode_Termination/bad_orientation'
BELOW = 'Episode_Termination/foot_below_ground'
INVALID = 'Episode_Termination/ex41_invalid'
TIMEOUT = 'Episode_Termination/time_out'
METRICS = {'slip_weighted': SLIP, 'track_lin_vel': LIN, 'track_ang_vel': ANG,
           'total_reward': REWARD, 'episode_length': LENGTH, 'terrain_level': TERRAIN,
           'bad_orientation': BAD, 'foot_below_ground': BELOW,
           'ex41_invalid': INVALID, 'time_out': TIMEOUT}
LABELS = {'slip_weighted': '미끄럼 가중 보상', 'track_lin_vel': '몸 XY 속도 추종 보상',
          'track_ang_vel': '회전 속도 추종 보상', 'total_reward': '전체 에피소드 보상',
          'episode_length': '에피소드 길이(step)', 'terrain_level': '지형 레벨',
          'bad_orientation': '마지막 종료: 기울기 초과(비율)',
          'foot_below_ground': '마지막 종료: 발 지하(비율)',
          'ex41_invalid': '마지막 종료: 무효 값 격리(비율)', 'time_out': '마지막 종료: 시간 만료(비율)'}
DEFAULT_CONTROL = '/home/jay/data/foothold/s2_lab/ex42_main_20261111_114505/main/EX-42-B-E1_20261111_114505'
SELECTED = set(METRICS.values()) | {'Loss/learning_rate', 'Loss/kl_probe/ppo_mean', 'Policy/mean_noise_std'}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def finite(x):
    return x is not None and math.isfinite(x)


def exact_mean(series, tag, start, end):
    values = [series.get(tag, {}).get(i) for i in range(start, end + 1)]
    return statistics.fmean(values) if values and all(finite(v) for v in values) else None


def ratio(a, b):
    return a / b if finite(a) and finite(b) and b > 0 else None


def unweighted(value, weight):
    # This is an episode-integrated cost / maximum episode duration, not per-step cost.
    return value / weight if finite(value) and weight != 0 else None


def read_events(folder):
    from tensorboard.backend.event_processing.event_accumulator import EventAccumulator
    paths = sorted(Path(folder).glob('events.out.tfevents.*'))
    if not paths:
        raise ValueError(f'no TensorBoard event files: {folder}')
    data, receipts = {}, []
    # Snapshot only bytes present at open time. Live appends do not change our input.
    with tempfile.TemporaryDirectory(prefix='e1-slip-tb-') as temporary:
        for index, source in enumerate(paths):
            with source.open('rb') as stream:
                size = source.stat().st_size
                raw = stream.read(size)
            if len(raw) != size:
                raise ValueError(f'event file shrank while reading: {source}')
            snap = Path(temporary) / f'events.out.tfevents.snapshot{index}'
            snap.write_bytes(raw)
            acc = EventAccumulator(str(snap), size_guidance={'scalars': 0},
                                   purge_orphaned_data=False).Reload()
            receipts.append({'path': str(source), 'prefix_bytes': size, 'prefix_sha256': sha(raw)})
            for tag in acc.Tags()['scalars']:
                if tag.endswith('/time') or not (tag.startswith('Episode_Reward/') or tag in SELECTED):
                    continue
                dest = data.setdefault(tag, {})
                for event in acc.Scalars(tag):
                    if event.step < 1:
                        continue
                    value = float(event.value)
                    if not finite(value):
                        raise ValueError(f'nonfinite scalar: {source}, {tag}, {event.step}')
                    if event.step in dest and dest[event.step] != value:
                        raise ValueError(f'conflicting duplicate scalar: {tag}, {event.step}')
                    dest[event.step] = value
    if not data:
        raise ValueError(f'no selected iteration scalars: {folder}')
    return data, receipts


def run_metadata(folder):
    import yaml
    root = Path(folder)
    required = ['manifest.json', 'startup_receipt.json', 'params/env.yaml']
    raw = {name: (root / name).read_bytes() for name in required}
    manifest = json.loads(raw['manifest.json'])
    startup = json.loads(raw['startup_receipt.json'])
    env = yaml.load(raw['params/env.yaml'], Loader=yaml.BaseLoader)
    args = manifest['run']['cli_args']
    info = {
        'path': str(root), 'git_head': manifest['git']['head'],
        'source_root': str(Path(manifest['files']['imported_paths']['foothold_s2']).parents[1]),
        'parent_sha256': startup['parent']['checkpoint_sha256'],
        'parent_cumulative_update': startup['parent']['cumulative_update'],
        'seed': int(env['seed']), 'num_envs_per_rank': int(env['scene']['num_envs']),
        'distributed': args['distributed'], 'scalar_scope': 'rank0 only',
        'dt': float(env['sim']['dt']) * int(env['decimation']),
        'max_episode_seconds': float(env['episode_length_s']),
        'slip_weight': float(env['rewards']['ex41_foot_slip']['weight']),
        'initial_state_sha256': manifest.get('initial_state_sha256'),
        'terrain_manifest_path': args.get('ex42_terrain_manifest'),
        'input_files': {k: {'sha256': sha(v), 'bytes': len(v)} for k, v in raw.items()},
    }
    if info['terrain_manifest_path']:
        terrain_raw = Path(info['terrain_manifest_path']).read_bytes()
        info['terrain_manifest_sha256'] = sha(terrain_raw)
    else:
        raise ValueError('missing terrain manifest identity')
    # PyTorch stores process-local storage IDs in these YAML binaries. Compare values,
    # not serialized object IDs. weights_only=True and map_location=cpu are mandatory.
    for bound in ['lo', 'hi']:
        params = env.get('events', {}).get('reset_base', {}).get('params', {})
        if isinstance(params.get(bound), list):
            params[bound] = normalize_reset_tensor(params[bound])
    # No arbitrary Python constructors are invoked by YAML BaseLoader.
    return info, env


def normalize_reset_tensor(value):
    import base64
    import io
    import torch
    storage = torch.load(io.BytesIO(base64.b64decode(value[0][0])),
                         weights_only=True, map_location='cpu')
    tensor = torch.empty(0, dtype=storage.dtype, device='cpu').set_(
        storage, int(value[1]), tuple(map(int, value[2])), tuple(map(int, value[3])))
    numbers = tensor.tolist()
    return {'shape': list(tensor.shape), 'values_sha256': sha(json.dumps(numbers).encode())}


def differences(a, b, prefix=''):
    if isinstance(a, dict) and isinstance(b, dict):
        return [row for key in sorted(set(a) | set(b))
                for row in differences(a.get(key), b.get(key), f'{prefix}.{key}'.strip('.'))]
    return [] if a == b else [{'field': prefix, 'control': a, 'candidate': b}]


def checkpoint(c, b, end):
    start = end - 49
    values = [ratio(abs(c.get(SLIP, {}).get(i, float('nan'))), c.get(LIN, {}).get(i))
              for i in range(end - 9, end + 1)]
    share = statistics.fmean(values) if all(finite(x) for x in values) else None
    c_lin = exact_mean(c, LIN, end - 19, end)
    b_lin = exact_mean(b, LIN, end - 19, end)
    tracking = ratio(c_lin, b_lin)
    full = all(all(i in series.get(tag, {}) for i in range(start, end + 1))
               for series in [c, b] for tag in METRICS.values())
    formal = end == 50
    return {
        'start': start, 'end': end, 'complete_window': full, 'formal_50_check': formal,
        'slip_share_last10': share,
        'slip_share_ratio_of_means_reference': ratio(
            abs(exact_mean(c, SLIP, end - 9, end) or 0), exact_mean(c, LIN, end - 9, end))
            if share is not None else None,
        'candidate_track_last20': c_lin, 'control_track_last20': b_lin,
        'tracking_ratio_last20': tracking, 'tracking_threshold': .9 * b_lin if b_lin is not None else None,
        'penalty_check': ('INCOMPLETE' if share is None or not full else
                          ('PASS' if .02 <= share <= .08 else 'FAIL') if formal else 'REFERENCE_ONLY'),
        'tracking_check': ('INCOMPLETE' if tracking is None or not full else
                           ('PASS' if tracking >= .9 else 'FAIL') if formal else 'REFERENCE_ONLY'),
    }


def iteration_rows(c, b, cw, bw):
    last = max((max(v) for v in c.values() if v), default=0)
    rows = []
    for i in range(1, last + 1):
        row = {'iteration': i}
        for label, series, weight in [('candidate', c, cw), ('control', b, bw)]:
            row.update({f'{label}_{name}': series.get(tag, {}).get(i) for name, tag in METRICS.items()})
            slip = series.get(SLIP, {}).get(i)
            reward_terms = [values.get(i) for tag, values in series.items() if tag.startswith('Episode_Reward/')]
            all_present = reward_terms and all(finite(v) for v in reward_terms)
            positive = sum(max(v, 0) for v in reward_terms) if all_present else None
            absolute = sum(abs(v) for v in reward_terms) if all_present else None
            row[f'{label}_slip_cost_normalized'] = unweighted(slip, weight)
            magnitude = abs(slip) if finite(slip) else None
            row[f'{label}_slip_share_tracking'] = ratio(magnitude, series.get(LIN, {}).get(i))
            row[f'{label}_slip_share_positive_reference'] = ratio(magnitude, positive)
            row[f'{label}_slip_share_absolute_reference'] = ratio(magnitude, absolute)
            row[f'{label}_reward_per_step_reference'] = ratio(series.get(REWARD, {}).get(i), series.get(LENGTH, {}).get(i))
        rows.append(row)
    if not rows:
        raise ValueError('no candidate iteration data')
    return rows


def f(value, percent=False):
    if value is None:
        return '없음'
    return f'{value * 100:.3f}%' if percent else f'{value:.6f}'


def table(headers, rows):
    def escape(value):
        return str(value).replace('|', '\\|').replace('\n', ' ')
    return '\n'.join('| ' + ' | '.join(map(escape, row)) + ' |' for row in
                     [headers, ['---'] * len(headers), *rows]) + '\n'


def plot(rows, output):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(3, 3, figsize=(16, 11), constrained_layout=True)
    x = [row['iteration'] for row in rows]
    specs = [('slip_weighted', 'Weighted slip reward', 'reward / max episode s'),
             ('slip_share_tracking', 'Slip / linear tracking', 'ratio'),
             ('track_lin_vel', 'Linear XY tracking reward', 'reward / max episode s'),
             ('track_ang_vel', 'Yaw tracking reward', 'reward / max episode s'),
             ('total_reward', 'Episode return (rolling buffer)', 'reward'),
             ('episode_length', 'Episode length (rolling buffer)', 'steps'),
             ('terrain_level', 'Terrain level', 'level'),
             ('bad_orientation', 'Latest episode: bad orientation', 'env fraction'),
             ('foot_below_ground', 'Latest episode: foot below ground', 'env fraction')]
    for ax, (key, title, unit) in zip(axes.flat, specs):
        for label, color in [('control', '#245C7C'), ('candidate', '#B44E24')]:
            y = [r[f'{label}_{key}'] if r[f'{label}_{key}'] is not None else float('nan') for r in rows]
            ax.plot(x, y, label=label, color=color, linewidth=1.5)
        ax.set(title=title, xlabel='Local update (same parent)', ylabel=unit)
        ax.grid(alpha=.22)
        for boundary in range(50, x[-1] + 1, 50):
            ax.axvline(boundary, color='#555555', alpha=.3, linewidth=.6)
        if key == 'slip_share_tracking':
            ax.axhspan(.02, .08, color='#32936F', alpha=.15, label='50-update check band')
        if key == 'slip_weighted':
            ax.text(.03, .05, 'Control weight=0; raw slip cost unavailable', transform=ax.transAxes, fontsize=8)
        ax.legend(fontsize=8)
    fig.suptitle(f'E1 slip comparison | rank0 only | updates 1-{x[-1]} | unsmoothed', fontsize=15)
    fig.savefig(output, dpi=155)
    plt.close(fig)


def render(snapshot, output):
    output.mkdir(parents=True, exist_ok=True)
    c, b = [{tag: {int(k): v for k, v in values.items()} for tag, values in snapshot[name]['scalars'].items()}
            for name in ['candidate', 'control']]
    cm, bm = [snapshot[name]['metadata'] for name in ['candidate', 'control']]
    rows = iteration_rows(c, b, cm['slip_weight'], bm['slip_weight'])
    last = rows[-1]['iteration']
    checks = [checkpoint(c, b, end) for end in range(50, ((last - 1) // 50 + 1) * 50 + 1, 50)]
    with (output / 'iterations.csv').open('w', newline='', encoding='utf-8') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)
    window_rows = []
    for check in checks:
        end = min(check['end'], last)
        for name, tag in METRICS.items():
            bv, cv = exact_mean(b, tag, check['start'], end), exact_mean(c, tag, check['start'], end)
            window_rows.append({'start': check['start'], 'end_observed': end, 'end_target': check['end'],
                                'metric': name, 'control': bv, 'candidate': cv,
                                'candidate_minus_control': cv - bv if cv is not None and bv is not None else None})
        bv = unweighted(exact_mean(b, SLIP, check['start'], end), bm['slip_weight'])
        cv = unweighted(exact_mean(c, SLIP, check['start'], end), cm['slip_weight'])
        window_rows.append({'start': check['start'], 'end_observed': end, 'end_target': check['end'],
                            'metric': 'slip_cost_normalized', 'control': bv, 'candidate': cv,
                            'candidate_minus_control': cv - bv if bv is not None and cv is not None else None})
    with (output / 'windows50.csv').open('w', newline='', encoding='utf-8') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(window_rows[0]), lineterminator='\n')
        writer.writeheader()
        writer.writerows(window_rows)
    result = {'schema': 'foothold-e1-slip-live/1', 'generated_at': snapshot['generated_at'],
              'latest_candidate_iteration': last, 'checks': checks, 'control_raw_slip_cost': None,
              'control_raw_slip_reason': 'weight zero; contact/foot velocity training trace not recorded',
              'fall_event_ratio': None, 'fall_event_reason': 'only latest-ended-episode reason fractions are logged',
              'runner_crosscheck': snapshot.get('runner_crosscheck', {'status': 'runner numeric result pending'})}
    (output / 'summary.json').write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + '\n')
    plot(rows, output / 'comparison.png')
    first = checks[0]
    finding = ('`미측정`: 50회 판정 구간이 아직 모두 기록되지 않았다.' if not first['complete_window'] else
               f"`확인됨`: 50회 벌점 몫 {f(first['slip_share_last10'], True)} · {first['penalty_check']}, "
               f"추종 유지 {f(first['tracking_ratio_last20'], True)} · {first['tracking_check']}. "
               '이는 의뢰한 두 항의 결과다. 전체 기동 승인이나 실제 미끄럼 감소 판정을 대신하지 않는다.')
    sections = [
        '# E1 발 미끄럼 재학습 · 같은 회차 비교',
        '> 분류: 실험\n> 작성: 오흥재 · ' + snapshot['generated_at'][:10] +
        '\n> 근거: 두 실행의 TensorBoard · env.yaml · startup_receipt · 11/12 lead 판정 정의'
        '\n> 요지: 50회 판정 두 항과 학습 곡선을 같은 회차로 비교'
        '\n> 상태: CPU 재계산 확인됨 · 학습 기동 판정 전체를 대신하지 않음\n> 판: v1.0',
        f"생성 시각 `{snapshot['generated_at']}`. 재학습 기록은 로컬 **{last}회**까지 읽었다. "
        '표와 그림의 숫자는 생성기가 원자료에서 읽었다. 두 판 모두 rank0 기록이므로 전체 GPU 합산 평균이 아니다.',
        finding,
        '## 고정한 50회 점검',
        '벌점 몫은 `mean(abs(slip_i) / track_lin_i, i=41..50)`, 허용 2~8%다. '
        '추종 유지는 재학습 31~50회 평균이 대조군 같은 구간의 90% 이상인지 본다. '
        '50회 이후 표의 같은 계산은 참고 기록이며 새 자동 승인 조건이 아니다. '
        '분모가 0 이하이거나 회차가 하나라도 비면 판정하지 않는다.',
        table(['경계', '50회 창', '벌점 몫 마지막 10회', '벌점 판정', '추종 마지막 20회 대조→재학습',
               '추종 비율', '추종 판정'],
              [[v['end'], '완료' if v['complete_window'] else '미완료', f(v['slip_share_last10'], True),
                v['penalty_check'], f(v['control_track_last20']) + ' → ' + f(v['candidate_track_last20']),
                f(v['tracking_ratio_last20'], True), v['tracking_check']] for v in checks]),
        '## 50회마다 같은 구간 평균',
        '불완전한 마지막 창은 관측된 회차까지만 표시한다. `없음`은 0이 아니다. '
        '종료 열은 사건 수를 센 넘어짐 비율이 아닌, 환경별 마지막 종료 원인 비율이다.',
        table(['회차', '지표', '대조군', '재학습', '재학습−대조군'],
              [[f"{v['start']}~{v['end_observed']} / 목표 {v['end_target']}", LABELS.get(v['metric'], '미끄럼 비용 적분/최대 시간'),
                f(v['control']), f(v['candidate']), f(v['candidate_minus_control'])] for v in window_rows]),
        '![학습 곡선](comparison.png)',
        '## 원자료와 비교 조건',
        table(['조건', '대조군', '재학습'], [[key, bm.get(key), cm.get(key)] for key in
              ['path', 'git_head', 'parent_sha256', 'parent_cumulative_update', 'seed', 'num_envs_per_rank',
               'distributed', 'dt', 'max_episode_seconds', 'slip_weight', 'terrain_manifest_path', 'terrain_manifest_sha256']]),
        'env.yaml 전체를 자료로 읽어 대조한 차이. reset 범위 텐서는 저장 객체 ID 대신 CPU에서 복원한 수치 SHA로 비교했다:',
        table(['필드', '대조군', '재학습'], [[v['field'], v['control'], v['candidate']] for v in snapshot['env_differences']]),
        '## 숫자를 읽는 법과 남은 자료',
        '- `Episode_Reward`는 가중과 dt를 적용한 에피소드 합을 최대 에피소드 시간으로 나눈 값이다. '
        '`Train/mean_reward`는 최근 종료 에피소드의 합계 평균이므로 두 종류를 직접 나눠 벌점 몫으로 삼지 않는다. '
        '참고 분모인 양의 항 합과 모든 항 절댓값 합 대비 비율은 `iterations.csv`에 있다.',
        '- 대조군 foot_slip 가중이 0이므로 TensorBoard의 가중 보상은 0이다. 원시 접촉·발 XY 속도 기록은 '
        '**없음**이다. 비용을 0으로 채우지 않았다. 재학습의 `slip_cost_normalized`는 가중 보상을 가중으로 '
        '나눈 에피소드 적분 비용/최대 에피소드 시간이며, 환경 스텝 전체 평균과는 다르다. '
        '동일 체크포인트 평가로 얻을 미끄럼 비용은 후속 자료다.',
        '- `track_lin_vel`은 모든 명령에서의 몸 XY 속도 추종 보상이다. 전진 명령만 따로 잰 오차가 아니다. '
        '사용자가 고정한 추종 점검의 대리 지표로 쓰되, 실제 전진 거리·발 미끄럼 감소를 이 값만으로 확정하지 않는다.',
        '- 시작 직후 보상과 에피소드 길이가 함께 오르는 것은 에피소드가 길어지는 초기 집계 영향도 있다. '
        '짧은 곡선 상승 전체를 새 보행 학습의 효과라고 단정하지 않는다. 단일 시드 비교의 차이는 재측정 폭과 구분되지 않았다.',
        '- `bad_orientation`, `foot_below_ground`, `ex41_invalid`, `time_out`을 분리했다. '
        '같은 종료에 여러 원인이 잡힐 수 있어 합계나 `1-time_out`을 넘어짐 사건 비율로 해석하지 않는다. '
        '실제 50회 구간의 넘어짐 사건 수/종료 사건 수는 미측정이다.',
        '- 각 파일을 읽기 시작한 길이만큼 CPU 임시 사본으로 읽었다. 입력 경로·prefix 바이트 수·SHA는 '
        '`tb_snapshot.json`에 있다. 뒤에 쓰이는 이벤트를 이어 붙여 한 번의 결과로 섞지 않는다. '
        '같은 tag·회차에 서로 다른 값이 중복되면 오류로 멈춘다. `/time` 태그는 회차 축에서 제외한다.',
        '## 코드 근거',
        f"- [실행한 발 미끄럼 비용 식](https://github.com/foothold-project/foothold-lab/blob/{cm['git_head']}/foothold_s2/rewards/w86.py#L117). "
        '[작업과 고정한 계산 정의](https://github.com/foothold-project/foothold-lab/issues/725).',
        f"- 실제 실행 코드 `{cm['source_root']}`: `foothold_s2/rewards/w86.py:117` 접촉 발 XY 속도제곱 합; "
        '`foothold_s2/rewards/w86_runtime.py:258` 비용 계산; `:356` 누적 요약; '
        '`foothold_s2/scripts/ex42_training_entry.py:935` EX42 flush는 회차 확인만 수행; '
        '`foothold_s2/runners/start_runner.py:241` rank0만 로그 기록.',
        '- `/home/jay/mai/projects/IsaacLab/source/isaaclab/isaaclab/managers/reward_manager.py:119` '
        '에피소드 정규화, `:146` 가중0 건너뜀, `:150` 가중×dt; '
        '`managers/termination_manager.py:144` 마지막 종료 원인 평균, `:174` 종료 때만 갱신.',
        '- `/home/jay/miniforge3/envs/isaac311/lib/python3.11/site-packages/rsl_rl/runners/on_policy_runner.py:184` '
        '에피소드 로그의 회차 평균, `:231` 최근 종료 에피소드 보상·길이 평균.',
        '## runner 교차 확인',
        '```json\n' + json.dumps(result['runner_crosscheck'], ensure_ascii=False, indent=2) + '\n```',
        '## 갱신',
        '수동 한 줄만 실행한다. 새로운 1000회 실행은 `--candidate`와 `--out`을 그 실행 전용으로 바꾼다. '
        '독립 실행 둘을 하나의 학습 곡선으로 이어 붙이지 않는다.',
        '```bash\n' + snapshot['refresh_command'] + '\n```',
        '고정된 숫자만 재현하려면 같은 생성기에 `--snapshot tb_snapshot.json --out <다른 폴더>`를 준다. '
        '원자료·학습 코드·프로세스는 바꾸지 않는다.',
        '## 이력\n\n| 판 | 변경 |\n| --- | --- |\n| v1.0 | 50회 고정 정의 · 같은 회차 비교 · 없는 비용 명시 |',
    ]
    (output / 'REPORT-E1-slip-live.md').write_text('\n\n'.join(sections) + '\n', encoding='utf-8')
    (output / 'tb_snapshot.json').write_text(json.dumps(snapshot, ensure_ascii=False, separators=(',', ':'), allow_nan=False) + '\n')
    files = sorted(p for p in output.iterdir() if p.is_file() and p.name != 'SHA256SUMS')
    (output / 'SHA256SUMS').write_text(''.join(f'{sha(p.read_bytes())}  {p.name}\n' for p in files))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--candidate', type=Path)
    group.add_argument('--snapshot', type=Path)
    parser.add_argument('--control', type=Path, default=Path(DEFAULT_CONTROL))
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--runner-result', type=Path, help='Independent runner JSON: slip_share_last10, tracking_ratio_31_50')
    args = parser.parse_args()
    if args.snapshot:
        snapshot = json.loads(args.snapshot.read_text())
    else:
        for run in [args.candidate, args.control]:
            if args.out.resolve().is_relative_to(run.resolve()):
                raise ValueError('output must be outside both training run directories')
        snapshot = {'generated_at': datetime.now().astimezone().isoformat(timespec='seconds')}
        envs = {}
        for name, path in [('candidate', args.candidate), ('control', args.control)]:
            scalars, receipts = read_events(path)
            meta, envs[name] = run_metadata(path)
            snapshot[name] = {'metadata': meta, 'event_files': receipts, 'scalars': scalars}
        cmeta, bmeta = [snapshot[k]['metadata'] for k in ['candidate', 'control']]
        for field in ['parent_sha256', 'parent_cumulative_update', 'seed', 'num_envs_per_rank',
                      'dt', 'max_episode_seconds', 'initial_state_sha256', 'terrain_manifest_sha256']:
            if cmeta[field] != bmeta[field]:
                raise ValueError(f'comparison identity mismatch: {field}')
        snapshot['env_differences'] = differences(envs['control'], envs['candidate'])
        snapshot['refresh_command'] = 'CUDA_VISIBLE_DEVICES=\'\' PYTHONDONTWRITEBYTECODE=1 ' + shlex.join([
            '/home/jay/miniforge3/envs/isaac311/bin/python', str(Path(__file__).resolve()),
            '--candidate', str(args.candidate.resolve()), '--control', str(args.control.resolve()), '--out', str(args.out.resolve())])
        # Keep only the control prefix actually compared; all selected raw scalars are retained.
        limit = max(max(v) for v in snapshot['candidate']['scalars'].values())
        snapshot['control']['scalars'] = {tag: {i: v for i, v in vals.items() if i <= limit}
                                          for tag, vals in snapshot['control']['scalars'].items()}
    if args.runner_result:
        raw = args.runner_result.read_bytes()
        reported = json.loads(raw)
        series = [{tag: {int(i): v for i, v in values.items()} for tag, values in snapshot[k]['scalars'].items()}
                  for k in ['candidate', 'control']]
        our = checkpoint(*series, 50)
        cross = {'path': str(args.runner_result), 'sha256': sha(raw), 'items': {}}
        for runner_key, ours_key in [('slip_share_last10', 'slip_share_last10'),
                                     ('tracking_ratio_31_50', 'tracking_ratio_last20')]:
            reported_value, ours = reported[runner_key], our[ours_key]
            cross['items'][runner_key] = {'runner': reported_value, 'analyst': ours,
                'matches_abs_1e-7': finite(ours) and finite(reported_value) and abs(ours - reported_value) <= 1e-7}
        snapshot['runner_crosscheck'] = cross
    result = render(snapshot, args.out)
    print(json.dumps({'out': str(args.out), 'latest': result['latest_candidate_iteration'],
                      'checks': result['checks']}, ensure_ascii=False, allow_nan=False))


if __name__ == '__main__':
    main()
