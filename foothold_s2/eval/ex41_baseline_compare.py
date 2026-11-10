"""Table only, no verdict: Windows score vs Linux score for the same checkpoint (EX-41 P1 periodic bundle).

usage: python -m foothold_s2.eval.ex41_baseline_compare --windows-score S.json --windows-eval DIR --linux-root DIR [--json OUT]
Rows: judgement lines, components, then per cell: score passed (vs baseline), alive_envs_at_end and
body_vx_integral_median_m from map64/map_modes.json (survival and progress kept apart), stand counts,
W78 side cells (alive_at_end per terrain kind), critic mirror symmetry.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

JUDGEMENT_KEYS = ('evaluation_state', 'maintenance_pass', 'stage_pass', 'safety_stop', 'measurement_state',
                  'judgement_state', 'evaluation_scope', 'auxiliary_missing')


def _read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def _num(x):
    return x if isinstance(x, (int, float)) and not isinstance(x, bool) else None


def _delta(a, b):
    a, b = _num(a), _num(b)
    return None if a is None or b is None else b - a


def build(win_score, win_map, lin_score, lin_map, win_w78=None, lin_w78=None):
    out = {'judgement': {}, 'components': {}, 'cells': {}, 'stand': {}, 'w78_sides': {}, 'symmetry': {}}
    for k in JUDGEMENT_KEYS:
        out['judgement'][k] = {'windows': win_score.get(k), 'linux': lin_score.get(k)}
    for k in sorted(set(win_score.get('components', {})) | set(lin_score.get('components', {}))):
        out['components'][k] = {'windows': win_score.get('components', {}).get(k),
                                'linux': lin_score.get('components', {}).get(k)}
    wm, lm = win_score['metrics'].get('record_counts', {}), lin_score['metrics'].get('record_counts', {})
    judged_w = set(win_score['metrics'].get('maintenance_counts', {}))
    for cell in sorted(set(wm) | set(lm)):
        mode, case = cell.split('/', 1)
        w, l = wm.get(cell, {}), lm.get(cell, {})
        wc = win_map['modes'].get(mode, {}).get(case, {})
        lc = lin_map['modes'].get(mode, {}).get(case, {})
        out['cells'][cell] = {
            'judged': cell in judged_w,
            'passed': {'windows': w.get('passed'), 'linux': l.get('passed'), 'delta': _delta(w.get('passed'), l.get('passed')),
                       'baseline_passed': w.get('baseline_passed'), 'total': w.get('total')},
            'alive_envs_at_end': {'windows': wc.get('alive_envs_at_end'), 'linux': lc.get('alive_envs_at_end'),
                                  'delta': _delta(wc.get('alive_envs_at_end'), lc.get('alive_envs_at_end'))},
            'body_vx_integral_median_m': {'windows': wc.get('body_vx_integral_median_m'),
                                          'linux': lc.get('body_vx_integral_median_m'),
                                          'delta': _delta(wc.get('body_vx_integral_median_m'), lc.get('body_vx_integral_median_m'))},
        }
    for mode in sorted(set(win_score['metrics'].get('stand_counts', {})) | set(lin_score['metrics'].get('stand_counts', {}))):
        w, l = win_score['metrics'].get('stand_counts', {}).get(mode, {}), lin_score['metrics'].get('stand_counts', {}).get(mode, {})
        out['stand'][mode] = {'windows': w.get('passed'), 'linux': l.get('passed'), 'total': w.get('total'),
                              'delta': _delta(w.get('passed'), l.get('passed'))}
    ws = win_score['metrics'].get('w78_v2_periodic_sides', {}).get('cells', {})
    ls = lin_score['metrics'].get('w78_v2_periodic_sides', {}).get('cells', {})
    for mode in sorted(set(ws) | set(ls)):
        for case in sorted(set(ws.get(mode, {})) | set(ls.get(mode, {}))):
            for kind in sorted(set(ws.get(mode, {}).get(case, {}).get('by_terrain_kind', {})) |
                               set(ls.get(mode, {}).get(case, {}).get('by_terrain_kind', {}))):
                w = ws.get(mode, {}).get(case, {}).get('by_terrain_kind', {}).get(kind, {})
                l = ls.get(mode, {}).get(case, {}).get('by_terrain_kind', {}).get(kind, {})
                out['w78_sides'][f'{mode}/{case}/{kind}'] = {
                    'alive_at_end': {'windows': w.get('alive_at_end'), 'linux': l.get('alive_at_end'),
                                     'delta': _delta(w.get('alive_at_end'), l.get('alive_at_end'))},
                    'movement_ratio_median': {'windows': w.get('movement_ratio_median'), 'linux': l.get('movement_ratio_median'),
                                              'delta': _delta(w.get('movement_ratio_median'), l.get('movement_ratio_median'))}}
    wsym = win_score['metrics'].get('critic_mirror_symmetry', {}).get('modes', {})
    lsym = lin_score['metrics'].get('critic_mirror_symmetry', {}).get('modes', {})
    for mode in sorted(set(wsym) | set(lsym)):
        for cell in sorted(set(wsym.get(mode, {})) | set(lsym.get(mode, {}))):
            w, l = wsym.get(mode, {}).get(cell, {}), lsym.get(mode, {}).get(cell, {})
            out['symmetry'][f'{mode}/{cell}'] = {'windows': w.get('symmetry'), 'linux': l.get('symmetry'),
                                                 'delta': _delta(w.get('symmetry'), l.get('symmetry'))}
    out['changed_cells'] = sorted(c for c, v in out['cells'].items()
                                  if v['passed']['delta'] or v['alive_envs_at_end']['delta'])
    return out


def _fmt(x):
    return '-' if x is None else (f'{x:.4g}' if isinstance(x, float) else str(x))


def render(t):
    lines = ['== judgement lines (as recorded, no verdict here)']
    for k, v in t['judgement'].items():
        lines.append(f"  {k}: windows={_fmt(v['windows'])} linux={_fmt(v['linux'])}")
    lines.append('== components')
    for k, v in t['components'].items():
        lines.append(f"  {k}: windows={_fmt(v['windows'])} | linux={_fmt(v['linux'])}")
    lines.append('== map64 cells: passed (baseline) | alive_envs_at_end | body_vx_integral_median_m   [J=judged]')
    for c, v in t['cells'].items():
        p, a, b = v['passed'], v['alive_envs_at_end'], v['body_vx_integral_median_m']
        lines.append(f"  {'J' if v['judged'] else ' '} {c:34s} passed {_fmt(p['windows'])}->{_fmt(p['linux'])} (base {_fmt(p['baseline_passed'])}/{_fmt(p['total'])})"
                     f" | alive {_fmt(a['windows'])}->{_fmt(a['linux'])} | vx {_fmt(b['windows'])}->{_fmt(b['linux'])} (d {_fmt(b['delta'])})")
    lines.append('== stand passed')
    for m, v in t['stand'].items():
        lines.append(f"  {m}: {_fmt(v['windows'])}->{_fmt(v['linux'])} of {_fmt(v['total'])}")
    lines.append('== W78 side cells')
    for c, v in t['w78_sides'].items():
        lines.append(f"  {c}: alive {_fmt(v['alive_at_end']['windows'])}->{_fmt(v['alive_at_end']['linux'])} | ratio {_fmt(v['movement_ratio_median']['windows'])}->{_fmt(v['movement_ratio_median']['linux'])}")
    lines.append('== mirror symmetry')
    for c, v in t['symmetry'].items():
        lines.append(f"  {c}: {_fmt(v['windows'])}->{_fmt(v['linux'])}")
    lines.append(f"cells with a changed passed or alive count: {len(t['changed_cells'])} of {len(t['cells'])}")
    return '\n'.join(lines)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--windows-score', type=Path, required=True)
    p.add_argument('--windows-eval', type=Path, required=True)
    p.add_argument('--linux-root', type=Path, required=True)
    p.add_argument('--json', type=Path)
    a = p.parse_args(argv)
    t = build(_read(a.windows_score), _read(a.windows_eval / 'map64/map_modes.json'),
              _read(a.linux_root / 'score.json'), _read(a.linux_root / 'evaluation/map64/map_modes.json'))
    if a.json:
        a.json.write_text(json.dumps(t, indent=1, sort_keys=True) + '\n', encoding='utf-8')
    print(render(t))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
