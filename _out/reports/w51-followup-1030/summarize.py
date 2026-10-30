import csv
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
rows = list(csv.DictReader((HERE / 'cells.csv').open(encoding='utf-8-sig')))
audit = json.loads((HERE / 'audit.json').read_text(encoding='utf-8'))
assert audit['complete'] and audit['cells'] == 468 and audit['all_common_conditions_match']
idx = {(r['policy'], r['variant'], r['rep'], r['map_mode'], r['command']): r for r in rows}
variants = ('w51_base', 'w51_push', 'w51_noise2', 'w51_combo4', 'w51_all6')
maps = ('eval_gt', 'eval_pred', 'probe_prop_only')
lines = ['> 분류: A/평가 · W51 비교군 실측', '> 작성: analyst · 2026-10-31',
         '> 근거: 12개 Kit 실행 · 468개 원자료 칸 · recompute.py 독립 재집계',
         '> 요지: 추가 교란에서 전진 거리 유지와 회전 생존 저하가 함께 나타나며 EX-40 학습 성공을 보장하지 않는다',
         '> 상태: 측정 완료 · GPU 학습/영상/보행 위상 판정 아님', '', '# W51 추가 비교 결과', '',
         '원자료 뿌리: `C:/Users/AI-WS01/s2_lab/basic_gait_runs/eval_actuator/w51_followup_20261030/`. '
         '12실행 모두 rc0, 2026-10-31 00:42:15에 batch_done.json 생성. 감독기 종료코드0을 별도로 확인했다. '
         '코드907fe1ed, seed42, L1, 64환경, 6초, 13명령, 지도3모드. 468칸=29,952 env-case. '
         '생존은 첫 에피소드가 마지막까지 남은 수다. 재료·질량·지형배정·저장본·코드의 비교 공통 해시가 모두 일치한다.', '',
         '조건: base=마찰·질량·관측잡음1배 유지; push=2초/4초에 수평각축Δv±0.5; '
         'noise2=정책 관측4항만2배; combo4=COM±5cm·gain±10%·strength±10%·지연0~15ms; '
         'all6=combo4+push, 관측잡음은1배. all6라는 이름이 잡음2배도 더했다는 뜻은 아니다.', '',
         '## 지도 모드별 모든 명령의 생존 합계', '',
         '아래는 각 모드13명령×64환경=832 중 생존 수다. 서로 다른 명령을 합친 기술통계이며 단일 성공률 관문으로 쓰지 않는다. base 두 재실행은 아래 표와 모든 비교 지표가 같은 값인지 별도로 확인한다.', '',
         '| 정책 | 조건 | GT /832 | PRED /832 | OFF /832 |', '|---|---|---:|---:|---:|']
for p in ('ex38', 'ex39b'):
    for v in variants:
        totals = [sum(int(r['alive_n']) for r in rows if (r['policy'], r['variant'], r['rep'], r['map_mode']) == (p, v, '1', m)) for m in maps]
        lines.append(f'| {p} | {v} | ' + ' | '.join(map(str, totals)) + ' |')
lines += ['', '## 복원 지도 전용(PRED) 대표 명령', '',
          '거리=생존 구간 몸앞방향 속도 적분의 환경 중앙값(m), 세계 좌표 순변위가 아니다. '
          '회전 추종=환경별 살아 있는 구간 실제요속도/명령요속도의 중앙값(무차원), 1이면 일치. '
          '생존은64환경 분모다. 회전 값은 저장된 환경별 평균에서 다시 집계했으며 원시wz 시계열 재계산은 아니다.', '',
          '| 정책 | 조건 | fwd1.0 거리/생존 | 좌spin 추종/생존 | 우spin 추종/생존 | 정지 XY 속도(m/s)/생존 |', '|---|---|---:|---:|---:|---:|']
for p in ('ex38', 'ex39b'):
    for v in variants:
        rr = [idx[p, v, '1', 'eval_pred', c] for c in ('fwd1.0', 'spin+1.2', 'spin-1.2', 'stop')]
        keys = ('body_vx_integral_median_m', 'yaw_follow_median', 'yaw_follow_median', 'xy_speed_env_median_mps')
        vals = [f"{float(r[k]):.3f} / {r['alive_n']}" for r, k in zip(rr, keys)]
        lines.append(f'| {p} | {v} | ' + ' | '.join(vals) + ' |')
lines += ['', '## 재실행 차이와 해석 한계', '']
metrics = ('alive_n', 'body_vx_integral_median_m', 'yaw_follow_median', 'vx_mae_env_median_mps',
           'vy_mae_env_median_mps', 'wz_mae_env_median_radps', 'xy_speed_env_median_mps', 'tilt_mean_alive_rad')
for p in ('ex38', 'ex39b'):
    diffs = {k: [] for k in metrics}
    for key, r in idx.items():
        if key[:3] != (p, 'w51_base', '1'):
            continue
        b = idx[p, 'w51_base', '2', key[3], key[4]]
        for k in metrics:
            if r[k] and b[k]:
                diffs[k].append(abs(float(r[k]) - float(b[k])))
    lines.append(f'- {p} base 두 반복 최대 절대차: ' + ', '.join(f'{k}={max(v):.6g}' for k, v in diffs.items()) + '.')
lines += ['', '같은 seed42 반복은 재실행 확인이다. 그 차이보다 크다고 통계적 유의성이나 새 시드 일반화를 주장하지 않는다. '
          '추가 DR 난수 소비가 이후 잡음 표본을 바꿀 수 있으므로 모든 시간별 관측 잡음의 짝일치는 미확인이다. '
          '발 접촉/위상, 관절하중, 영상은 이번 좁은 측정에 없으며 좋은 보행으로 확정하지 않는다. '
          '2초/4초 밀기는 학습의10~15초보다 빈번하나 크기는D76±1보다 작다. 이 자료로D76 전체 범위의 안전·성공을 판정하지 않는다.', '',
          '상세: [468칸](cells.csv), [기준 대비 차](differences.csv), [지형별 분해](terrain_cells.csv), [검사와 원자료 해시](audit.json).']
(HERE / 'RESULT-W51-followup.md').write_text('\n'.join(lines) + '\n', encoding='utf-8', newline='\n')
files = ['recompute.py', 'summarize.py', 'audit.json', 'cells.csv', 'differences.csv', 'terrain_cells.csv', 'RESULT-W51-followup.md']
(HERE / 'SHA256SUMS.txt').write_text(''.join(hashlib.sha256((HERE / f).read_bytes()).hexdigest() + '  ' + f + '\n' for f in files), encoding='utf-8', newline='\n')
print('\n'.join(lines[14:]))
