"""CPU-only W15 full/unit audit. Never imports simulator or writes source data."""
import argparse
import hashlib
import importlib.util
import json
from collections import Counter
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path('D:/mai-tmp/scripter')
FULL = ROOT / 'w15_noise_1107/full_same_code/terrain_skill_v2.json'
PLAN = ROOT / 'w15_noise_plan.json'
RECEIPT = Path('D:/mai-tmp/gpu/results/item_1079.json')
GROUPS = [('eval_gt', 'stairs_side_left'), ('probe_prop_only', 'flat_fwd1.0')]


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def flatten(value, path=''):
    if isinstance(value, dict):
        for k, v in value.items():
            if k not in ('raw_file', 'raw_sha256'):
                yield from flatten(v, f'{path}/{k}')
    elif isinstance(value, list):
        for i, v in enumerate(value):
            yield from flatten(v, f'{path}/{i}')
    elif isinstance(value, (int, float)) and not isinstance(value, bool):
        yield path, value


def compare(target, repeats):
    keys = set(repeats[0])
    assert all(set(r) == keys for r in repeats)
    common = keys & target.keys()
    outside = sum(not min(r[k] for r in repeats) <= target[k] <= max(r[k] for r in repeats)
                  for k in common)
    return len(common), outside, len(keys ^ target.keys())


def self_test():
    assert compare({'a': 14}, [{'a': 13}, {'a': 15}]) == (1, 0, 0)
    assert compare({'a': 16}, [{'a': 13}, {'a': 15}]) == (1, 1, 0)
    assert compare({'b': 16}, [{'a': 13}, {'a': 15}]) == (0, 0, 2)
    print('W56_W15_SELF_TEST_PASS 3')


def audit():
    full, plan, receipt = read(FULL), read(PLAN), read(RECEIPT)
    gate_path = Path('D:/mai-wt/foothold-lab/scripter-ex42-w52w53/foothold_s2/eval/ex42_w78_gate.py')
    spec = importlib.util.spec_from_file_location('w56_g11', gate_path)
    gate = importlib.util.module_from_spec(spec); spec.loader.exec_module(gate)
    reported_gate = read(Path('D:/mai-tmp/scripter/W15-G11-gate-1107.json'))
    assert receipt['id'] == 1079 and receipt['rc'] == 0
    assert full['state'] == 'done'
    assert full['run_identity']['code_head'] == plan['code_head']
    assert full['checkpoint_sha256'] == '02876f9b1835d2b9c9b2079193ba14924d1f3853c3ecee70e16e43cb23d60955'
    assert {m: len(v) for m, v in full['modes'].items()} == {
        'eval_gt': 80, 'eval_pred': 80, 'probe_prop_only': 80}
    files = [{'path': str(p), 'sha256': sha(p)} for p in (FULL, PLAN, RECEIPT)]
    groups = []
    for mode, case in GROUPS:
        paths = [ROOT / f'w78units/m750/units/{mode}/{case}/terrain_skill_v2.json']
        paths += [Path(j['done_file']) for j in plan['jobs']
                  if j['title'].startswith(f'W15 m750 {mode} {case} ')]
        assert len(paths) == 3
        units = [read(p) for p in paths]
        assert gate.compare_split(units[0], [units[0]])['state'] == 'PASS'
        gate_result = gate.compare_split(full, [units[0]], repeats=units[1:])
        assert gate_result == reported_gate[f'{mode}/{case}']
        identity_keys = ['state', 'checkpoint_sha256', 'source_sha256', 'run_identity',
                         'envs', 'dt_s', 'eval_seed', 'levels', 'start_angles_deg',
                         'ex41_environment_preparation', 'ex41_checkpoint_preparation',
                         'dr_off', 'curriculum_off']
        for p, u in zip(paths, units):
            files.append({'path': str(p), 'sha256': sha(p)})
            for key in identity_keys:
                assert full[key] == u[key], (p, key)
            assert u['cases'][case] == full['cases'][case]
        expected = {f'L{l}_a{a:03d}_{case}' for l in (2, 5) for a in (0, 30, 60, 90)}
        assert all(set(u['modes'][mode]) == expected for u in units)
        common = outside = keydiff = repeat_changed = 0
        categories = Counter()
        rows = []
        raw_hashes = []
        denominator_diff_rows = 0
        for key in sorted(expected):
            target = full['modes'][mode][key]
            source = [u['modes'][mode][key] for u in units]
            denominator_diff_rows += gate._denominators(target) != gate._denominators(source[0])
            for field in ('level', 'stair_start_angle_deg', 'case', 'requested_kinds',
                          'terrain_tiles', 'terrain_assignment_sha256', 'phase_steps'):
                assert all(target[field] == s[field] for s in source), (key, field)
            for root, row in ((FULL.parent, target), (paths[0].parent, source[0])):
                raw = root / row['raw_file']
                actual = sha(raw)
                assert actual == row['raw_sha256'], raw
                raw_hashes.append({'path': str(raw), 'sha256': actual})
            t, rs = dict(flatten(target)), [dict(flatten(s)) for s in source]
            n, bad, missing = compare(t, rs)
            common += n; outside += bad; keydiff += missing
            repeat_changed += sum(len({r[k] for r in rs}) != 1 for k in rs[0])
            for k in t.keys() ^ rs[0].keys():
                categories['swing_clearance_m' if '/swing_clearance_m/' in k else k] += 1
            for kind, a in target['by_terrain_kind'].items():
                b = source[0]['by_terrain_kind'][kind]
                rows.append({'row': key, 'kind': kind, 'focus': kind in target['requested_kinds'],
                    'env_count': a['env_count'], 'full_alive': a['alive_at_end'],
                    'unit_alive': b['alive_at_end'], 'full_R': a['movement_ratio_median'],
                    'unit_R': b['movement_ratio_median'],
                    'R_delta': a['movement_ratio_median'] - b['movement_ratio_median'],
                    'full_drag_ratio': a['drag_ratio_of_contact'],
                    'unit_drag_ratio': b['drag_ratio_of_contact']})
        focus = [r for r in rows if r['focus']]
        groups.append({'mode': mode, 'case': case, 'common_numeric_fields': common,
            'g11': gate_result, 'g11_same_input_control': 'PASS',
            'denominator_different_rows': denominator_diff_rows,
            'outside_repeat_envelope': outside, 'repeat_changed_fields': repeat_changed,
            'numeric_key_symmetric_difference': keydiff, 'key_difference_categories': dict(categories),
            'all_kind_cells': len(rows), 'alive_changed_cells': sum(r['full_alive'] != r['unit_alive'] for r in rows),
            'focus_cells': len(focus), 'focus_alive_changed_cells': sum(r['full_alive'] != r['unit_alive'] for r in focus),
            'focus_full_alive_sum': sum(r['full_alive'] for r in focus),
            'focus_unit_alive_sum': sum(r['unit_alive'] for r in focus),
            'focus_env_count_sum': sum(r['env_count'] for r in focus),
            'focus_max_abs_R_delta': max(abs(r['R_delta']) for r in focus),
            'manifest_sha_full': full['checkpoint_manifest_sha256'],
            'manifest_sha_repeats': [u['checkpoint_manifest_sha256'] for u in units],
            'identity_equal_keys': identity_keys, 'rows': rows, 'raw_hashes': raw_hashes})
    return {'at': datetime.now(timezone(timedelta(hours=9))).isoformat(),
        'status': 'NOT_EQUIVALENT_IN_TESTED_GROUPS', 'full_rows': 240,
        'duration_s': receipt['ended'] - receipt['started'], 'receipt': receipt,
        'files': files, 'groups': groups,
        'g11_source': {'path': str(gate_path), 'sha256': sha(gate_path)},
        'scope': 'Two selected mode/case groups, each eight level/angle cells and three unit repeats. No all-group repeat or causal claim.'}


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('--self-test', action='store_true')
    p.add_argument('--output', type=Path); a = p.parse_args()
    if a.self_test:
        self_test()
    else:
        assert a.output
        data = audit()
        a.output.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        print(json.dumps({'status': data['status'], 'duration_s': data['duration_s'],
            'groups': [{k:v for k,v in g.items() if k not in ('rows','raw_hashes','identity_equal_keys')}
                       for g in data['groups']]}, ensure_ascii=False, indent=2))
