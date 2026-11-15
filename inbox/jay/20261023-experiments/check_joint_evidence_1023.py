"""Read existing NPZ only. Recheck SOL-23e statistics and hashes without Kit/Torch."""
import csv
import hashlib
import json
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent


def periods(contact, times):
    starts = np.flatnonzero((~contact[:-1]) & contact[1:]) + 1
    return np.diff(times[starts])


def main():
    # Known input: touchdown at .02, .06, .10 gives .04-second periods.
    c = np.array([0, 1, 0, 1, 0, 1], dtype=bool)
    assert np.allclose(periods(c, np.arange(6) * .02), [.04, .04])
    assert periods(np.ones(6, dtype=bool), np.arange(6)).size == 0
    rows = list(csv.DictReader((HERE / 'ROM-contact-sol-23e.csv').open(encoding='utf-8-sig')))
    checked = []
    for row in rows:
        path = Path(row['source_npz'])
        assert hashlib.sha256(path.read_bytes()).hexdigest() == row['source_sha256']
        with np.load(path, allow_pickle=False) as d:
            sel = d['seg'] == 1
            tail = sel & (d['t'] >= d['t'][sel][0] + 1.5)
            fi = list(d['foot_names']).index(row['foot'] + '_foot')
            values = {
                'actual_vx_tail_mps': d['vx'][tail].mean(),
                'contact_fraction': d['foot_contact'][sel, fi].mean(),
                'median_touchdown_period_s': np.median(periods(d['foot_contact'][sel, fi], d['t'][sel])),
                'foot_z_p95_p05_m': np.diff(np.percentile(d['foot_z'][sel, fi], [5, 95]))[0],
            }
            for joint in ('hip', 'thigh', 'calf'):
                ji = list(d['joint_names']).index(row['foot'] + '_' + joint + '_joint')
                values[joint + '_rom_p95_p05_deg'] = np.diff(np.percentile(np.rad2deg(d['joint_pos'][sel, ji]), [5, 95]))[0]
            for key, value in values.items():
                assert np.isclose(value, float(row[key]), atol=1e-9), (row['run'], row['foot'], key, value, row[key])
            checked.append({'run': row['run'], 'foot': row['foot'], **{k: float(v) for k, v in values.items()}})
    print(json.dumps({'known_inputs': 2, 'rows_checked': len(checked), 'checks_per_row': 7,
                      'hashes_match': True, 'rows': checked}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
