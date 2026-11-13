"""Run reviewer #784's four mutants in isolated CPU-only copies.

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
    ('r6_fwd02_060_to_050', "else .6)]", "else .5)]",
     'test_r6_fwd02_threshold_is_060_not_050'),
    ('r2_median_010_to_015', ">(.1 if k.endswith('median_abs_rad') else .2)]",
     ">(.15 if k.endswith('median_abs_rad') else .2)]",
     'test_r2_median_threshold_is_010_not_015'),
    ('r5_500_to_250', 'iteration>=activated_at+500', 'iteration>=activated_at+250',
     'test_r5_observation_requires_500_updates'),
    ('stand_four_inclusive_to_exclusive', "=(-1,4,True)", "=(-1,4,False)",
     'test_stand_drop_includes_exactly_four_envs'),
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
    source = (source_dir/'boundary_rules.py').read_text(encoding='utf-8')
    evidence = dict(created_at=datetime.now().astimezone().isoformat(),
                    source_sha256=hashlib.sha256(source.encode()).hexdigest(),
                    scope='four requested mutations; CPU; isolated copies', results=[])
    with tempfile.TemporaryDirectory(prefix='rule-mutants-', dir=out) as tmp:
        for name, old, new, expected_test in [('control', None, None, None), *MUTATIONS]:
            root = Path(tmp)/name
            root.mkdir()
            for filename in ('boundary_rules.py', 'test_boundary_rules.py',
                             'test_boundary_thresholds.py'):
                shutil.copyfile(source_dir/filename, root/filename)
            if old is not None:
                if source.count(old) != 1:
                    raise RuntimeError(f'{name}: expected exactly one mutation site')
                (root/'boundary_rules.py').write_text(source.replace(old, new), encoding='utf-8')
            command = [sys.executable, '-B', '-m', 'pytest', 'test_boundary_thresholds.py',
                       '-q', '-p', 'no:cacheprovider', '--basetemp', str(root/'pytest-tmp')]
            env = {**os.environ, 'CUDA_VISIBLE_DEVICES': '', 'PYTHONDONTWRITEBYTECODE': '1'}
            result = subprocess.run(command, cwd=root, env=env, stdin=subprocess.DEVNULL,
                                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                    encoding='utf-8', timeout=60, check=False)
            (out/f'{name}.txt').write_text(result.stdout, encoding='utf-8')
            failed = re.findall(r'^FAILED (.+)$', result.stdout, re.MULTILINE)
            ok = (result.returncode == 0 and re.search(r'\b[1-9][0-9]* passed\b', result.stdout) is not None) if name == 'control' else (
                result.returncode == 1 and any(expected_test in test for test in failed)
                and 'AssertionError' in result.stdout and not re.search(r'^ERROR ', result.stdout, re.MULTILINE))
            evidence['results'].append(dict(name=name, returncode=result.returncode,
                                            verified=ok, failed_tests=failed,
                                            log=str(out/f'{name}.txt')))
            print(f'{name}: rc={result.returncode}, verified={ok}, failed_tests={len(failed)}')
    evidence['all_verified'] = all(row['verified'] for row in evidence['results'])
    (out/'mutation_validation.json').write_text(json.dumps(evidence, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    return 0 if evidence['all_verified'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
