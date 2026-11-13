"""Run reviewer #784's threshold and GT/PRED mutants in isolated CPU copies.

The original source, training run, and evaluator outputs are never modified.
An import error or an empty test run is not counted as a killed mutant.
"""
import argparse
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile


MUTATIONS = (
    ('r6_fwd02_060_to_050', 'boundary_rules.py', "else .6)]", "else .5)]",
     'test_r6_fwd02_threshold_is_060_not_050'),
    ('r2_median_010_to_015', 'boundary_rules.py', ">(.1 if k.endswith('median_abs_rad') else .2)]",
     ">(.15 if k.endswith('median_abs_rad') else .2)]",
     'test_r2_median_threshold_is_010_not_015'),
    ('r5_500_to_250', 'boundary_rules.py', 'iteration>=activated_at+500', 'iteration>=activated_at+250',
     'test_r5_observation_requires_500_updates'),
    ('stand_four_inclusive_to_exclusive', 'boundary_rules.py', "=(-1,4,True)", "=(-1,4,False)",
     'test_stand_drop_includes_exactly_four_envs'),
    ('rollback_default_gt_only', 'boundary_rules.py',
     'def rollback_limits(modes=JUDGE_MODES):', 'def rollback_limits(modes=JUDGE_MODES[:1]):',
     'test_rollback_default_includes_pred_and_excludes_off'),
    ('rollback_consumer_gt_only', 'boundary_rules.py',
     'def regression(current, anchor, modes=JUDGE_MODES):',
     'def regression(current, anchor, modes=JUDGE_MODES[:1]):',
     'test_pred_regression_drives_actual_rollback'),
    ('previous_pred_validity_removed', 'boundary_rules.py',
     "all(previous.get('maintenance_modes',{}).get(m)=='PASS' for m in JUDGE_MODES))",
     'True)', 'test_prior_pred_nonpass_cannot_supply_second_rollback_window'),
    ('raise_previous_pred_guard_removed', 'boundary_rules.py',
     "any(previous.get('maintenance_modes',{}).get(m)!='PASS' for m in JUDGE_MODES)):",
     'False):', 'test_prior_pred_nonpass_cannot_allow_actual_raise'),
    ('judged_mode_missing_guard_removed', 'boundary_rules.py',
     "    if any(statuses.get(m)!='PASS' for m in JUDGE_MODES):errors.append('GT_PRED_maintenance_coverage_missing')",
     '    pass', 'test_missing_judged_mode_verdict_cannot_become_a_treatment'),
    ('thirteen_names_guard_removed', 'boundary_read.py',
     "        if set(rows)!=set(MAINTENANCE_CASES):raise ValueError('maintenance command coverage differs: '+mode)",
     '        pass', 'test_real_parent_requires_all_thirteen_named_commands'),
    ('r5_floor_gt_only', 'boundary_rules.py',
     "all(current[f'low/L{lev}/{mode}/fwd0.2/R']>=.5 for mode in JUDGE_MODES for lev in (0,5))",
     "all(current[f'low/L{lev}/{mode}/fwd0.2/R']>=.5 for mode in JUDGE_MODES[:1] for lev in (0,5))",
     'test_r5_floor_requires_each_gt_pred_cell_at_least_half'),
    ('r5_floor_half_exclusive', 'boundary_rules.py',
     "all(current[f'low/L{lev}/{mode}/fwd0.2/R']>=.5 for mode in JUDGE_MODES for lev in (0,5))",
     "all(current[f'low/L{lev}/{mode}/fwd0.2/R']>.5 for mode in JUDGE_MODES for lev in (0,5))",
     'test_r5_floor_requires_each_gt_pred_cell_at_least_half'),
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    out = args.out.resolve()
    source_dir = Path(__file__).resolve().parent
    if 's2_lab' in out.parts or out == source_dir:
        parser.error('use a separate scratch output directory')
    out.mkdir(parents=True, exist_ok=True)
    sources = {name: (source_dir/name).read_text(encoding='utf-8')
               for name in ('boundary_rules.py', 'boundary_read.py')}
    evidence = dict(created_at=datetime.now().astimezone().isoformat(),
                    source_sha256={name: hashlib.sha256(src.encode()).hexdigest() for name,src in sources.items()},
                    scope='four threshold, four GT/PRED review, two consumer, two R5 floor mutants; CPU; isolated copies', results=[])
    with tempfile.TemporaryDirectory(prefix='rule-mutants-', dir=out) as tmp:
        for name, filename, old, new, expected_test in [('control', None, None, None, None), *MUTATIONS]:
            root = Path(tmp)/name
            root.mkdir()
            for path in source_dir.glob('*.py'):
                shutil.copyfile(path, root/path.name)
            if old is not None:
                source = sources[filename]
                if source.count(old) != 1:
                    raise RuntimeError(f'{name}: expected exactly one mutation site')
                (root/filename).write_text(source.replace(old, new), encoding='utf-8')
            command = [sys.executable, '-B', '-m', 'pytest', 'test_boundary_thresholds.py',
                       'test_boundary_review_followup.py',
                       'test_boundary_r5_pred.py',
                       '-q', '-p', 'no:cacheprovider', '--basetemp', str(root/'pytest-tmp')]
            env = {**os.environ, 'CUDA_VISIBLE_DEVICES': '', 'PYTHONDONTWRITEBYTECODE': '1'}
            result = subprocess.run(command, cwd=root, env=env, stdin=subprocess.DEVNULL,
                                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                    encoding='utf-8', timeout=60, check=False)
            (out/f'{name}.txt').write_text(result.stdout, encoding='utf-8')
            failed = re.findall(r'^FAILED (.+)$', result.stdout, re.MULTILINE)
            ok = (result.returncode == 0 and re.search(r'\b[1-9][0-9]* passed\b', result.stdout) is not None) if name == 'control' else (
                result.returncode == 1 and any(expected_test in test for test in failed)
                and ('AssertionError' in result.stdout or 'Failed: DID NOT RAISE' in result.stdout)
                and not re.search(r'^ERROR ', result.stdout, re.MULTILINE))
            evidence['results'].append(dict(name=name, returncode=result.returncode,
                                            verified=ok, failed_tests=failed,
                                            log=str(out/f'{name}.txt')))
            print(f'{name}: rc={result.returncode}, verified={ok}, failed_tests={len(failed)}')
    evidence['all_verified'] = all(row['verified'] for row in evidence['results'])
    (out/'mutation_validation.json').write_text(json.dumps(evidence, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    return 0 if evidence['all_verified'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
