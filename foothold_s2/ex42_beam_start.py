"""Opt-in A/balance_beams lateral reset range, decision 5fec6872e.

EX42_BEAM_START_Y: unset/empty/0/off disables, on means 0.10 m,
a number in (0, 0.10] sets D in metres. No new RNG or reset function.
"""
from __future__ import annotations

import math
import os

ENV = 'EX42_BEAM_START_Y'
DEFINITION = ('A/balance_beams root start y relative to the beam-centred mesh reset origin: '
              'uniform U[-D,+D], sampled independently at each reset by the existing column sampler; '
              'x/z/roll/pitch/yaw and all other kinds unchanged; evaluation repeats the same eval_seed per mode')


def half_width(environ=None):
    value = (os.environ if environ is None else environ).get(ENV, '').strip()
    if value in ('', '0', 'off'):
        return None
    try:
        d = .10 if value == 'on' else float(value)
    except ValueError:
        raise ValueError(f'{ENV}: expected on or metres in (0, 0.10]') from None
    if not math.isfinite(d) or not 0 < d <= .10:
        raise ValueError(f'{ENV}: expected on or metres in (0, 0.10]')
    return d


def configure(table, lo, hi):
    """Change just the existing range tensors, never the mesh declaration or RNG."""
    d = half_width()
    if d is None:
        return {}
    columns = [c for c, row in enumerate(table)
               if (row['family'], row['kind']) == ('A', 'balance_beams')]
    if not columns:
        raise ValueError(f'{ENV}: no A/balance_beams columns in this reset table')
    if bool((lo[columns, 1] != 0).any()) or bool((hi[columns, 1] != 0).any()):
        raise ValueError(f'{ENV}: expected the existing beam-centred zero y reset')
    lo[columns, 1], hi[columns, 1] = -d, d
    return {'beam_start_y': {'half_width_m': d, 'columns': columns,
                             'definition': DEFINITION, 'source': '5fec6872e',
                             'env': ENV, 'distribution': 'uniform', 'yaw_changed': False}}


def record_start(result, raw, key):
    """Record actual post-reset local y. OFF does no tensor work and adds no keys."""
    info = result.get('beam_start_y')
    if info is None:
        return
    import torch
    types = raw.scene.terrain.terrain_types
    mask = torch.isin(types, torch.as_tensor(info['columns'], device=types.device))
    ids = mask.nonzero(as_tuple=False).flatten()
    y = (raw.scene['robot'].data.root_pos_w[:, 1] - raw.scene.env_origins[:, 1])[ids]
    # World-coordinate float32 subtraction may cost an ulp at remote mesh columns.
    if not bool(torch.isfinite(y).all()) or bool((y.abs() > info['half_width_m'] + 1e-4).any()):
        raise ValueError('beam start local y outside registered reset range')
    info.setdefault('starts', {})[key] = {'env_ids': ids.cpu().tolist(), 'local_y_m': y.cpu().tolist()}
