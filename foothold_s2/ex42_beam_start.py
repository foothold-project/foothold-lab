"""Opt-in A/balance_beams lateral reset range, decision 5fec6872e.

EX42_BEAM_START_Y: unset/empty/0/off disables, on means 0.10 m,
a number in (0, 0.10] sets D in metres. No new RNG or reset function.
Evaluation reads EX42_BEAM_START_Y_EVAL only, never the training value.
Official flags keep midpoint unless EX42_BEAM_START_Y_FLAG=1 is explicit.
"""
from __future__ import annotations

import math
import os

ENV = 'EX42_BEAM_START_Y'
EVAL_ENV = 'EX42_BEAM_START_Y_EVAL'
FLAG_ENV = 'EX42_BEAM_START_Y_FLAG'
DEFINITION = ('A/balance_beams root start y relative to the beam-centred mesh reset origin: '
              'uniform U[-D,+D], sampled independently at each reset by the existing column sampler; '
              'x/z/roll/pitch/yaw and all other kinds unchanged; evaluation repeats the same eval_seed per mode')


def half_width(environ=None, *, key=ENV):
    if key is None:
        return None
    value = (os.environ if environ is None else environ).get(key, '').strip()
    if value in ('', '0', 'off'):
        return None
    try:
        d = .10 if value == 'on' else float(value)
    except ValueError:
        raise ValueError(f'{key}: expected on or metres in (0, 0.10]') from None
    if not math.isfinite(d) or not 0 < d <= .10:
        raise ValueError(f'{key}: expected on or metres in (0, 0.10]')
    return d


def configure(table, lo, hi, *, key=ENV):
    """Change just the existing range tensors, never the mesh declaration or RNG."""
    d = half_width(key=key)
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
                             'env': key, 'distribution': 'uniform', 'yaw_changed': False}}


def configure_flag_reset(event, mounted):
    """Pin every old range, then optionally reopen just beam y with the eval-only D."""
    from foothold_s2.terrains.ex42_column_reset import build_column_table, pin_column_reset_midpoint
    value = os.environ.get(FLAG_ENV, '0').strip()
    if value not in ('', '0', '1'):
        raise ValueError(f'{FLAG_ENV}: expected empty, 0 or 1')
    d = half_width(key=EVAL_ENV)
    if value == '1' and d is None:
        raise ValueError(f'{FLAG_ENV}=1 requires {EVAL_ENV} in (0, 0.10]')
    pin_column_reset_midpoint(event)
    if value == '1':
        table = build_column_table(mounted['column_family'])
        mounted.update(configure(table, event.params['lo'], event.params['hi'], key=EVAL_ENV))
    if d is not None or value == '1':
        mounted['beam_start_policy'] = {
            'mode': 'uniform' if value == '1' else 'midpoint',
            'requested_half_width_m': d, 'effective_half_width_m': d if value == '1' else 0.0,
            'selector_env': FLAG_ENV, 'evaluation_env': EVAL_ENV,
            'definition': 'official flag reset: all axes midpoint; only A/balance_beams y may use the eval-only range',
            'source': 'lead-lx 2026-11-21 00:34 · PR929 review', 'yaw_changed': False}


def flag_receipt_fields(mounted, seed):
    """No new fields when evaluation is off, including when only training is on."""
    return {key: dict(mounted[key], eval_seed=seed)
            for key in ('beam_start_policy', 'beam_start_y') if key in mounted}


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
