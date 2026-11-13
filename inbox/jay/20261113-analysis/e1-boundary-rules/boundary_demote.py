"""a76e783d boundary-cell review only. No training imports, adjustment or apply.

R: highest boundary value. Yaw error: lowest boundary value. GT and PRED
keep separate best iterations. At least one map crosses the inclusive threshold
and both deteriorate from their own best. This matches the requested actual
m250 -> m500 example (GT drop .134729, PRED drop .073817).
"""
from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from datetime import datetime
import hashlib
import json
import math
from pathlib import Path
import re

LEDGER = 'a76e783d7b0380115b1559aa49f6e1a6e656e955'
FORMAT = 'analyst-ex42-e1-boundary-demotion/1'
MODES = ('eval_gt', 'eval_pred')
EPS = 1e-12  # Floating subtraction tolerance, not a statistical noise band.


@dataclass(frozen=True)
class CellSpec:
    suite: str
    level: str
    case: str
    metric: str
    threshold: float
    direction: str = 'higher'

    @property
    def cell(self):
        return '/'.join((self.suite, self.level, self.case, self.metric))

    def key(self, mode):
        return '/'.join((self.suite, self.level, mode, self.case, self.metric))


SPECS = tuple(
    [CellSpec('low', level, case, 'R', threshold)
     for level in ('L0', 'L5')
     for case, threshold in (('fwd0.1', .10), ('fwd0.2', .02),
                             ('side+0.2', .03), ('side-0.2', .03),
                             ('side+0.4', .04), ('side-0.4', .04))]
    + [CellSpec('map', 'mixed012', case, 'R', .02) for case in ('side+0.5', 'side-0.5')]
    + [CellSpec('yaw', 'L2', case, metric, threshold, 'lower')
       for case, median, p90 in (('fwd0.5', .02, .05), ('fwd1.0', .03, .06))
       for metric, threshold in (('median_abs_rad', median), ('p90_abs_rad', p90))]
)
MAINTENANCE_CASES = ('fwd0.5', 'fwd1.0', 'spin+1.2', 'spin-1.2', 'back0.5', 'back1.0',
                     'side+0.5', 'side-0.5', 'diag-fwd+side+', 'diag-fwd+side-',
                     'diag-back+side+', 'diag-back+side-', 'stop')
OFF_KEYS = tuple(['map64/' + c for c in MAINTENANCE_CASES]
                 + ['e1_v2/L0/' + c for c in ('fwd0.1', 'fwd0.2', 'side+0.2', 'side-0.2', 'side+0.4', 'side-0.4')]
                 + ['e1_v2/L5/' + c for c in ('fwd0.1', 'fwd0.2')])


def finite(x):
    return type(x) in (int, float) and math.isfinite(x)


def evaluate(now, history):
    """Evaluate verified snapshots. Missing or foreign boundaries are never skipped.

    Parent iteration 0 is deliberately excluded. `history` must otherwise cover
    every 250 boundary in this run; a gap cannot masquerade as a new best.
    Outputs are observations for lead, including HOLD, never learning actions.
    """
    n = now.get('iteration')
    errors = []
    valid_n = type(n) is int and n > 0 and n % 250 == 0
    if not valid_n:
        errors.append('positive local 250-boundary required')
    hist = [s for s in history if s.get('iteration') != 0]
    expected = list(range(250, n, 250)) if valid_n else []
    indices = [s.get('iteration') for s in hist]
    if (any(type(i) is not int for i in indices) or sorted(indices) != expected):
        errors.append('history must contain each earlier local 250-boundary exactly once')
    hist = sorted(hist, key=lambda s: s.get('iteration') if type(s.get('iteration')) is int else -1)
    all_snaps = [*hist, now]
    previous = next((s for s in hist if valid_n and s['iteration'] == n - 250), None)
    for s in all_snaps:
        label = f'm{s.get("iteration")}'
        errors.extend(label + ': ' + str(e) for e in s.get('errors', []))
        errors.extend(label + ': ' + str(e) for e in s.get('provenance_errors', []))
        audit = s.get('audit') or {}
        if not audit:
            errors.append(label + ': verified P1/raw audit missing')
        errors.extend(label + ': ' + str(e) for e in audit.get('errors', []))
        for name in ('plan_sha256', 'score_config_sha256'):
            if (not re.fullmatch('[0-9a-f]{64}', str(s.get(name)))
                    or s.get(name) != now.get(name)):
                errors.append(label + ': ' + name + ' differs or missing')

    rows = []
    for spec in SPECS:
        row = dict(cell=spec.cell, threshold=spec.threshold,
                   unit='ratio' if spec.metric == 'R' else 'rad', direction=spec.direction,
                   state='HOLD', same_direction=False, trigger_modes=[], errors=[])
        for mode in MODES:
            key = spec.key(mode)
            fp = now.get('fingerprints', {}).get(key)
            mode_errors = []
            for s in all_snaps:
                value = s.get('metrics', {}).get(key)
                actual_fp = s.get('fingerprints', {}).get(key)
                if not finite(value):
                    mode_errors.append(f'm{s.get("iteration")}: missing/nonfinite {key}')
                if not fp or actual_fp != fp:
                    mode_errors.append(f'm{s.get("iteration")}: conditions differ {key}')
                elif (fp.get('seed') != 42 or fp.get('envs') != 64 or fp.get('steps') != 300):
                    mode_errors.append(f'm{s.get("iteration")}: seed/denominator differs {key}')
            row['errors'].extend(mode_errors)
            row[mode] = None
            if mode_errors:
                continue
            chooser = max if spec.direction == 'higher' else min
            best = chooser(all_snaps, key=lambda s: s['metrics'][key])
            value = now['metrics'][key]
            best_value = best['metrics'][key]
            delta = best_value - value if spec.direction == 'higher' else value - best_value
            crossed = delta > spec.threshold or math.isclose(delta, spec.threshold, rel_tol=0, abs_tol=EPS)
            old = previous['metrics'].get(key) if previous else None
            row[mode] = dict(value=value, best_value=best_value, best_iteration=best['iteration'],
                             adverse_delta=delta, threshold_crossed=crossed,
                             previous=old, previous_delta=value-old if finite(old) else None)
        # Comparing the maps also requires the same assignment/command/seed.
        if now.get('fingerprints', {}).get(spec.key(MODES[0])) != now.get('fingerprints', {}).get(spec.key(MODES[1])):
            row['errors'].append('GT/PRED evaluation conditions differ')
        if not errors and not row['errors']:
            drops = [row[m]['adverse_delta'] for m in MODES]
            row['same_direction'] = all(d > EPS for d in drops)
            row['trigger_modes'] = [m for m in MODES if row[m]['threshold_crossed']]
            row['state'] = ('FIRST_BOUNDARY' if not hist else
                            'DEMOTE' if row['trigger_modes'] and row['same_direction'] else
                            'ONE_MODE_DROP' if row['trigger_modes'] else 'KEEP')
        rows.append(row)

    from boundary_approved import off_monitor
    off_now = dict(now.get('audit') or {}, iteration=n)
    off_prev = dict(previous.get('audit') or {}, iteration=previous['iteration']) if previous else None
    off = off_monitor(off_now, off_prev)
    if set(off_now.get('off_cells', {})) != set(OFF_KEYS):
        off['missing'].append('exact continuous 21-cell map-off coverage required')
        off['state'] = 'HOLD'
    if errors:
        off['missing'].extend(errors)
        off['state'] = 'HOLD'
    demoted = [r['cell'] for r in rows if r['state'] == 'DEMOTE']
    incomplete = bool(errors or any(r['state'] == 'HOLD' for r in rows) or off['state'] == 'HOLD')
    state = ('HOLD' if incomplete else 'DEMOTE' if demoted else 'BASELINE_ONLY' if not hist else 'NO_DEMOTION')
    # Partial numbers remain visible, but not an actionable partial demotion list.
    if incomplete:
        demoted = []
    return dict(format=FORMAT, rule_commit=LEDGER, iteration=n, state=state,
                apply_ready=False, learning_mutation=False, seed=42,
                history_iterations=indices, errors=errors, cells=rows,
                demoted_cells=demoted, map_off_survival=off,
                unchanged_rules=['maintenance_gt_pred_26', 'wide_cells_existing_judge'],
                history=[dict(iteration=s.get('iteration'), checkpoint_sha256=s.get('checkpoint_sha256'),
                              plan_sha256=s.get('plan_sha256'), score_path=s.get('score_path'),
                              sources=s.get('sources', {}), audit_sources=(s.get('audit') or {}).get('sources', {}))
                         for s in all_snaps])


def read_review(score_path, run_root, code_root, *, cached=(), audits=None):
    """Reopen all boundaries in the named run; pin checkpoint/plan/P1/raw identity."""
    from copy import deepcopy
    from boundary_read import Reader, load_snapshot, approved_audit
    score_path, run_root, code_root = (Path(p).resolve() for p in (score_path, run_root, code_root))
    match = re.fullmatch(r'm([1-9][0-9]*)', score_path.parent.name)
    n = int(match[1]) if match else 0
    reader = Reader()
    failures = []
    checkpoints = {}
    plan_sha = None
    try:
        startup = reader.json(run_root / 'startup_receipt.json')
        manifest = reader.json(run_root / 'manifest.json')
        plan_sha = startup['plan_sha256']
        reader.bytes(code_root / 'foothold_s2/curriculum/ex42-prep.yaml', plan_sha)
        pins = manifest['checkpoints']
        if not isinstance(pins, dict):
            raise ValueError('run checkpoint pins must be an object')
        checkpoints = pins
        if score_path != (run_root / f'eval/scores/m{n}/ex42_score.json').resolve():
            raise ValueError('requested score is not this run/local boundary')
    except (OSError, ValueError, KeyError, TypeError) as exc:
        failures.append(str(exc))
    cache = {Path(s['score_path']).resolve(): s for s in cached if s and s.get('score_path')}
    snaps = []
    sequence = list(range(250, n + 1, 250)) if n > 0 and n % 250 == 0 else [n]
    for i in sequence:
        path = score_path if i == n else run_root / f'eval/scores/m{i}/ex42_score.json'
        snap = deepcopy(cache[path.resolve()]) if path.resolve() in cache else load_snapshot(path, i, code_root)
        snap['provenance_errors'] = list(failures)
        if snap.get('iteration') != i:
            snap['provenance_errors'].append('snapshot local iteration differs')
        expected = checkpoints.get(f'model_{i}.pt')
        if isinstance(expected, dict):
            expected = expected.get('sha256')
        if (not re.fullmatch('[0-9a-f]{64}', str(expected)) or expected != snap.get('checkpoint_sha256')):
            snap['provenance_errors'].append('checkpoint differs from run/local manifest pin')
        if snap.get('plan_sha256') != plan_sha:
            snap['provenance_errors'].append('score execution plan differs from run startup')
        audit = (audits or {}).get(i)
        snap['audit'] = (deepcopy(audit) if audit is not None else approved_audit(snap)) or {
            'errors': ['positive boundary P1/raw audit unavailable']}
        # A cached audit is usable only for precisely this snapshot identity.
        if (snap['audit'].get('iteration') != i or
                snap['audit'].get('checkpoint_sha256') != snap.get('checkpoint_sha256')):
            snap['provenance_errors'].append('P1/raw audit identity differs from snapshot')
        snaps.append(snap)
    result = evaluate(snaps[-1], snaps[:-1])
    result['run_root'] = str(run_root)
    result['code_root'] = str(code_root)
    result['run_sources'] = reader.sources
    result['created_at'] = datetime.now().astimezone().isoformat()
    result['reader_sources'] = {str(p): hashlib.sha256(p.read_bytes()).hexdigest()
                                for p in (Path(__file__), Path(__file__).with_name('boundary_read.py'),
                                          Path(__file__).with_name('approved_source.py'),
                                          Path(__file__).with_name('boundary_approved.py'))}
    return result


def summary(result):
    cells = ', '.join(result['demoted_cells']) or '없음'
    return (f'm{result["iteration"]}: {result["state"]} · DEMOTE 칸 {cells} · '
            f'지도 끔 {result["map_off_survival"]["state"]} (생존 하한 60/64) · 판단용, 학습 설정 미적용')


def markdown(result):
    def fmt(v):
        return '미확인' if v is None else f'{v:.6f}'
    def modes(row, mode):
        data = row.get(mode)
        if data is None:
            return '미확인'
        return (f'{fmt(data["value"])} / {fmt(data["best_value"])} @m{data["best_iteration"]}'
                f' / {fmt(data["adverse_delta"])}')
    lines = ['## a76e 경계 칸 내림', '', summary(result), '',
             'GT·PRED는 각각 자기 최고 경계와 비교한다. 한 지도 이상 문턱 도달 + 두 지도 모두 같은 방향 악화이면 DEMOTE.',
             'R은 최댓값, yaw 오차는 최솟값이 기준이다. 부모는 제외하고 m250부터 전 경계를 사용한다.',
             '표의 각 지도 열: 현재 / 최고값 @회차 / 불리한 변화량. 유지26칸·넓힌 범위 판정은 기존 규칙 그대로다.', '',
             '| 칸 | 단위 | 문턱 | GT | PRED | 상태 |', '|---|---|---|---|---|---|']
    for r in result['cells']:
        lines.append('| ' + ' | '.join((r['cell'], r['unit'], fmt(r['threshold']),
                                        modes(r, 'eval_gt'), modes(r, 'eval_pred'), r['state'])) + ' |')
    lines += ['', '지도 끔은 추종 하락으로 내리지 않는다. 연속21칸 생존60/64, 같은 칸 두 경계 미달 검토 규칙을 보존한다.', '',
              '| 지도 끔 연속 지형 칸 | 끝 생존 | 직전 | 판정 |', '|---|---|---|---|']
    for r in result['map_off_survival']['items']:
        lines.append(f'| {r["cell"]} | {r["survival"]}/64 | {r["previous"]} | {r["judgement"]} |')
    issues = result['errors'] + [e for r in result['cells'] for e in r['errors']] + result['map_off_survival']['missing']
    lines += ['', '증거 오류: ' + json.dumps(issues, ensure_ascii=False),
              '', 'DEMOTE는 칸을 「배우는 중」으로 읽는 보고 줄이다. 보상 변경·저장본 복원·학습 중단을 실행하지 않는다.']
    return '\n'.join(lines) + '\n'


def write_review(result, out):
    out = Path(out).resolve()
    roots = [Path(result[k]).resolve() for k in ('run_root', 'code_root') if result.get(k)]
    if 's2_lab' in out.parts or any(out.is_relative_to(root) for root in roots):
        raise ValueError('output must be outside training/evaluation trees')
    out.mkdir(parents=True, exist_ok=True)
    (out / 'demotion.json').write_text(json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False) + '\n', encoding='utf-8')
    (out / 'demote.txt').write_text(summary(result) + '\n', encoding='utf-8')
    text = ['# E1 최고 경계 대비 내림 판독', '> 분류: A/평가',
            f'> 작성: analyst-lx · {datetime.now():%Y-%m-%d %H:%M}', '> 근거: 원장 ' + LEDGER,
            '> 요지: ' + summary(result), '> 상태: CPU 원자료 재계산 · 판단용 · 학습 설정 미적용', '', markdown(result)]
    (out / 'DEMOTE.md').write_text('\n'.join(text).rstrip() + '\n', encoding='utf-8')
    fields = ['cell', 'unit', 'threshold', 'direction', 'state', 'same_direction']
    values = ('value', 'best_value', 'best_iteration', 'adverse_delta', 'threshold_crossed', 'previous', 'previous_delta')
    fields += [m + '_' + k for m in MODES for k in values]
    with (out / 'demote_cells.csv').open('w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fields, lineterminator='\n')
        writer.writeheader()
        for row in result['cells']:
            writer.writerow({**{k: row[k] for k in fields[:6]},
                             **{m + '_' + k: (row.get(m) or {}).get(k) for m in MODES for k in values}})


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for flag in ('score', 'run-root', 'code-root', 'out'):
        p.add_argument('--' + flag, type=Path, required=True)
    a = p.parse_args()
    result = read_review(a.score, a.run_root, a.code_root)
    write_review(result, a.out)
    print(summary(result))
    return 2 if result['state'] == 'HOLD' else 0


if __name__ == '__main__':
    raise SystemExit(main())
