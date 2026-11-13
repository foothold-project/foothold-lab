"""Run seven deliberate mistakes only in disposable CPU copies outside the repo."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

CASES = (
    ('fwd01_threshold', "('fwd0.1', .10)", "('fwd0.1', .15)"),
    ('both_maps_must_cross', "'DEMOTE' if row['trigger_modes'] and row['same_direction']",
     "'DEMOTE' if len(row['trigger_modes']) == 2 and row['same_direction']"),
    ('one_map_direction', 'all(d > EPS for d in drops)', 'any(d > EPS for d in drops)'),
    ('only_previous_best', 'best = chooser(all_snaps,', 'best = chooser(all_snaps[-2:],'),
    ('yaw_best_maximum', "chooser = max if spec.direction == 'higher' else min", 'chooser = max'),
    ('exclusive_threshold', 'delta > spec.threshold or math.isclose(delta, spec.threshold, rel_tol=0, abs_tol=EPS)',
     'delta > spec.threshold + EPS'),
    ('ignore_history_errors', "errors.extend(label + ': ' + str(e) for e in s.get('provenance_errors', []))",
     'pass  # ignore provenance'),
)


def run(out):
    source = Path(__file__).resolve().parent
    out = Path(out).resolve()
    if out.is_relative_to(source) or 's2_lab' in out.parts:
        raise ValueError('mutation copies must be outside source and experiment data')
    out.mkdir(parents=True, exist_ok=True)
    results = []
    for name, old, new in CASES:
        dest = out / name
        dest.mkdir(exist_ok=True)
        for file in ('boundary_demote.py', 'boundary_approved.py', 'test_boundary_demote.py'):
            shutil.copyfile(source / file, dest / file)
        path = dest / 'boundary_demote.py'
        text = path.read_text(encoding='utf-8')
        if text.count(old) != 1:
            raise ValueError('mutation target not unique: ' + name)
        path.write_text(text.replace(old, new), encoding='utf-8')
        process = subprocess.run([sys.executable, '-B', '-m', 'pytest', str(dest / 'test_boundary_demote.py'),
            '-q', '-p', 'no:cacheprovider', '--basetemp', str(dest / 'pytest')],
            capture_output=True, text=True,
            env={**os.environ, 'CUDA_VISIBLE_DEVICES': '', 'PYTHONDONTWRITEBYTECODE': '1'})
        (dest / 'result.log').write_text(process.stdout + process.stderr, encoding='utf-8')
        failed = [line for line in process.stdout.splitlines() if line.startswith('FAILED ')]
        row = dict(name=name, returncode=process.returncode, failed_tests=failed,
                   log=str(dest / 'result.log'), detected=process.returncode == 1 and bool(failed))
        results.append(row)
    receipt = dict(source_sha256=hashlib.sha256((source / 'boundary_demote.py').read_bytes()).hexdigest(),
                   all_detected=all(r['detected'] for r in results), mutations=results)
    (out / 'results.json').write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8')
    if not receipt['all_detected']:
        raise AssertionError('mutation survived or collection crashed; inspect results.json')
    print(json.dumps({r['name']: len(r['failed_tests']) for r in results}))
    return receipt


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    run(parser.parse_args().out)
