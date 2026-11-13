"""EX-42 registered continuous-terrain command allocation. No Kit imports.

Flag mode is drawn at episode reset. Within free episodes the 13 velocity slots
are sampled conditionally. Receipts distinguish reset assignments, actual command
resamples and pre-step consumption; all counts are rank-local and cumulative.
"""
from __future__ import annotations

from dataclasses import replace
import hashlib
import json
import math
import os
from pathlib import Path
import tempfile

from foothold_s2.commands.mixed_core import EX39_SLOTS


def read_contract(plan, stage_id):
    if stage_id in ('EX42_0_T0_prime', 'E0', 'E1'):
        return None                       # Preserve approved running/legacy paths and RNG draws.
    stage = next((s for s in plan.document['stages'] if s['id'] == stage_id), {})
    shares = stage.get('shares')
    if not isinstance(shares, dict):
        raise ValueError(f'EX-42 {stage_id} requires explicit stages[].shares')
    if set(shares) != set(EX39_SLOTS) | {'flag'}:
        raise ValueError(f'EX-42 {stage_id} shares needs exactly 13 free slots plus flag')
    if any(type(v) not in (int, float) or not math.isfinite(v) or not 0 <= v <= 1 for v in shares.values()):
        raise ValueError('EX-42 shares must be finite probabilities')
    if not math.isclose(sum(shares.values()), 1., abs_tol=1e-9) or shares['flag'] >= 1:
        raise ValueError('EX-42 shares must sum to 1 and leave a positive free-command mass')
    allocation = plan.document.get('command_allocation', {})
    if allocation.get('conditional_denominator') != 'continuous_environments' or allocation.get('record_both_denominators') is not True:
        raise ValueError('EX-42 command allocation needs continuous and all-env denominators')
    e0 = next(s for s in plan.document['stages'] if s['id'] == 'E0')['terrain']
    kinds = e0.get('kind_task', {}).get('continuous')
    families = {r['family'] for r in e0['exposure_at_E0']['positive'] if r.get('kinds_of') == 'continuous'}
    if not kinds or not families:
        raise ValueError('EX-42 continuous command columns are not declared')
    kind_commands = read_kind_commands(stage)
    return {'stage_id': stage_id, 'shares': dict(shares), 'families': sorted(families),
            'continuous_kinds': sorted(kinds), 'conditional_denominator': 'continuous_environments',
            'mode_selection': 'episode_reset',
            'other_columns': 'kind_task_command_set' if kind_commands else 'unchanged_source_stage',
            **({'kind_commands': kind_commands} if kind_commands else {})}


KIND_COMMAND_NAMES = ('forward_1.0', 'flag')   # E5's C boundary widens this through extend_kind_commands, not here


def read_kind_commands(stage):
    """`stages[].terrain.kind_task.<family>.<kind>` = {command_set, command_weights} for every kind this stage opens
    outside the continuous columns (CG E.3 kind_task row): {"<family>/<kind>": {'family', 'kind', 'flag': weight}}.
    An opened kind without the two cells, a malformed cell, or a cell for a kind the stage does not open is refused;
    nothing falls back to the free 13-slot commands."""
    terrain = stage.get('terrain') or {}
    positive = (terrain.get(f"exposure_at_{stage['id']}") or {}).get('positive') or []
    if any('kinds_of' in r and r['kinds_of'] != 'continuous' for r in positive):
        raise ValueError(f"EX-42 {stage['id']} exposure names a kind list other than continuous")
    opened = [(r['family'], r['kind']) for r in positive if 'kind' in r]
    cells = terrain.get('kind_task') or {}
    declared = {(f, k) for f, kinds in cells.items() for k in kinds}
    if declared - set(opened):
        raise ValueError(f"EX-42 {stage['id']} kind_task commands for kinds it does not open: {sorted(declared - set(opened))}")
    out = {}
    for family, kind in opened:
        cell = (cells.get(family) or {}).get(kind)
        if not isinstance(cell, dict) or set(cell) != {'command_set', 'command_weights'}:
            raise ValueError(f"EX-42 {stage['id']} opens {family}/{kind} without kind_task command_set and command_weights")
        names, weights = cell['command_set'], cell['command_weights']
        if (not isinstance(names, list) or len(set(names)) != len(names) or 'forward_1.0' not in names
                or not set(names) <= set(KIND_COMMAND_NAMES)):
            raise ValueError(f"EX-42 {stage['id']} {family}/{kind} command_set must hold forward_1.0 and only forward_1.0, flag")
        if (not isinstance(weights, dict) or set(weights) != set(names)
                or any(type(v) not in (int, float) or not math.isfinite(v) or not 0 <= v <= 1 for v in weights.values())
                or not math.isclose(sum(weights.values()), 1., abs_tol=1e-9)):
            raise ValueError(f"EX-42 {stage['id']} {family}/{kind} command_weights must match command_set and sum to 1")
        out[f'{family}/{kind}'] = {'family': family, 'kind': kind, 'flag': float(weights.get('flag', 0.0))}
    return out


def stage_commands(plan, stage_id):
    """The stage's own command profile `stages[].commands` = {shares, ranges, turn_overlay}, validated; None when the
    row has none (the stage keeps the stage-zero profile). shares: the 13 free slots, sum 1. ranges: exactly the
    stage-zero range keys. turn_overlay: {fraction, wz_abs} for the reverse / side / diagonal slots."""
    stage = next((s for s in plan.document['stages'] if s['id'] == stage_id), {})
    cell = stage.get('commands')
    return None if cell is None else validate_commands(plan, cell, stage_id)


def validate_commands(plan, cell, stage_id):
    """One `commands` cell (a stage row's, or a segment adjustment's) as the validated profile."""
    number = lambda v: type(v) in (int, float) and math.isfinite(v)   # noqa: E731
    if not isinstance(cell, dict) or set(cell) != {'shares', 'ranges', 'turn_overlay'}:
        raise ValueError(f'EX-42 {stage_id} commands needs exactly shares, ranges and turn_overlay')
    shares, ranges, overlay = cell['shares'], cell['ranges'], cell['turn_overlay']
    if (not isinstance(shares, dict) or set(shares) != set(EX39_SLOTS) or any(not number(v) or not 0 <= v <= 1 for v in shares.values())
            or not math.isclose(sum(shares.values()), 1., abs_tol=1e-9)):
        raise ValueError(f'EX-42 {stage_id} commands.shares needs the 13 free slots as probabilities that sum to 1')
    if not isinstance(ranges, dict) or set(ranges) != set(plan.document['stage_zero']['ranges']):
        raise ValueError(f'EX-42 {stage_id} commands.ranges needs exactly the stage-zero range keys')
    for key, pair in ranges.items():
        if (not isinstance(pair, list) or len(pair) != 2 or any(not number(v) for v in pair) or not pair[0] < pair[1]
                or (key.endswith('_abs') and pair[0] < 0)):
            raise ValueError(f'EX-42 {stage_id} commands.ranges.{key} must be [low, high] with low < high (absolute ranges from 0)')
    if (not isinstance(overlay, dict) or set(overlay) != {'fraction', 'wz_abs'} or not number(overlay['fraction'])
            or not 0 < overlay['fraction'] <= 1 or not isinstance(overlay['wz_abs'], list) or len(overlay['wz_abs']) != 2
            or any(not number(v) for v in overlay['wz_abs']) or not 0 < overlay['wz_abs'][0] < overlay['wz_abs'][1]):
        raise ValueError(f'EX-42 {stage_id} commands.turn_overlay needs fraction in (0, 1] and wz_abs [low, high] above 0')
    return {'shares': {k: float(v) for k, v in shares.items()},
            'ranges': {k: (float(v[0]), float(v[1])) for k, v in ranges.items()},
            'turn_overlay': (float(overlay['fraction']), float(overlay['wz_abs'][0]), float(overlay['wz_abs'][1]))}


def command_adjust_limits(plan, stage_id):
    """`stages[].command_adjust_limits`: the outer lines of every `commands` cell for a segment adjustment, validated.
    {ranges: {key: (low, high)}, turn_overlay: (fraction_max, wz low, wz high), shares: {slot: (low, high)}}; a cell the
    row does not name is limited to its `commands` value. None when the row has no limits. The start profile must lie
    inside them."""
    stage = next((s for s in plan.document['stages'] if s['id'] == stage_id), {})
    cell, base = stage.get('command_adjust_limits'), stage_commands(plan, stage_id)
    if cell is None:
        return None
    pair = lambda v: (isinstance(v, list) and len(v) == 2 and all(type(x) in (int, float) and math.isfinite(x) for x in v)   # noqa: E731
                      and v[0] <= v[1])
    if base is None or not isinstance(cell, dict) or set(cell) != {'ranges', 'turn_overlay', 'shares'}:
        raise ValueError(f'EX-42 {stage_id} command_adjust_limits needs a commands profile and exactly ranges, turn_overlay, shares')
    ranges, overlay, shares = cell['ranges'], cell['turn_overlay'], cell['shares']
    if (not isinstance(ranges, dict) or not set(ranges) <= set(base['ranges']) or not all(pair(v) for v in ranges.values())
            or not isinstance(shares, dict) or not set(shares) <= set(base['shares']) or not all(pair(v) for v in shares.values())
            or not isinstance(overlay, dict) or set(overlay) != {'fraction_max', 'wz_abs'} or not pair(overlay['wz_abs'])
            or type(overlay['fraction_max']) not in (int, float) or not 0 < overlay['fraction_max'] <= 1):
        raise ValueError(f'EX-42 {stage_id} command_adjust_limits names an unknown cell or a malformed [low, high]')
    out = {'ranges': {k: tuple(map(float, ranges.get(k, v))) for k, v in base['ranges'].items()},
           'shares': {k: tuple(map(float, shares.get(k, (v, v)))) for k, v in base['shares'].items()},
           'turn_overlay': (float(overlay['fraction_max']), float(overlay['wz_abs'][0]), float(overlay['wz_abs'][1]))}
    fraction, low, high = base['turn_overlay']
    if (any(not out['ranges'][k][0] <= v[0] < v[1] <= out['ranges'][k][1] for k, v in base['ranges'].items())
            or any(not out['shares'][k][0] <= v <= out['shares'][k][1] for k, v in base['shares'].items())
            or fraction > out['turn_overlay'][0] or not out['turn_overlay'][1] <= low < high <= out['turn_overlay'][2]):
        raise ValueError(f'EX-42 {stage_id} commands start outside command_adjust_limits')
    return out


def configure_env(env_cfg, contract):
    if contract is None:
        return
    term = env_cfg.commands.base_velocity
    if term.force_flag_provider is not None or term.flag_stride != 0:
        raise ValueError('EX-42 registered shares conflict with another flag allocator')
    term.dynamic_flags = True             # Allocate FlagState for every possible selected env.


class CommandShares:
    def __init__(self, contract, source_stage):
        self.contract = contract
        free_mass = 1. - contract['shares']['flag']
        self.free_stage = replace(source_stage, shares={k: contract['shares'][k]/free_mass for k in EX39_SLOTS})
        self.kind_keys = sorted(contract.get('kind_commands', {}))
        # One stage per kind bundle: forward exactly 1.0, no heading, no turn overlay (CG E.3 kind_task row).
        self.kind_stages = [replace(source_stage, id=f'KIND_{key}', shares={'forward': 1.0},
                                    ranges={**source_stage.ranges, 'forward_vx': (1.0, 1.0)}, low_forward_fraction=0.0,
                                    heading_arm=None, turn_overlay=None) for key in self.kind_keys]
        self.names = (*EX39_SLOTS, 'flag')
        self.pending_counts = None
        self.count_origin_update = 0

    def attach(self, raw, term, runtime):
        import torch
        if not term.cfg.dynamic_flags or term.cfg.force_flag_provider is not None:
            raise ValueError('EX-42 command shares need exclusive dynamic flag allocation')
        table = raw._ex42_column_table
        self.column_continuous = torch.tensor([
            row['family'] in self.contract['families'] and row['kind'] in self.contract['continuous_kinds']
            for row in table], dtype=torch.bool, device=raw.device)
        self.raw, self.term, self.runtime = raw, term, runtime
        # Column -> kind bundle index (-1: no bundle). A mesh column holds one (family, kind).
        by_kind = {(row['family'], row['kind']): i for i, row in enumerate(
            self.contract['kind_commands'][key] for key in self.kind_keys)}
        self.column_kind = torch.tensor([by_kind.get((row['family'], row['kind']), -1) for row in table],
                                        dtype=torch.long, device=raw.device)
        if bool(((self.column_kind >= 0) & self.column_continuous).any()):
            raise ValueError('EX-42 a column is both continuous and a kind bundle')
        missing = sorted(set(range(len(self.kind_keys))) - set(self.column_kind.tolist()))
        if missing:
            raise ValueError(f"EX-42 kind bundle without a mesh column: {[self.kind_keys[i] for i in missing]}")
        runtime.plan.stages = [runtime.plan.stages[0], self.free_stage, *self.kind_stages]
        rows = 2 + len(self.kind_keys)        # all, continuous, then one denominator per kind bundle
        self.counts = {name: torch.zeros((rows, width), dtype=torch.long, device=raw.device)
                       for name, width in [('reset_modes', 2), ('samples', 14), ('steps', 14)]}
        if self.pending_counts is not None:
            self._restore_counts(self.pending_counts)
            self.pending_counts = None

    def continuous(self):
        columns = self.raw.scene.terrain.terrain_types.long()
        if bool(((columns < 0) | (columns >= len(self.column_continuous))).any()):
            raise ValueError('EX-42 command shares terrain column is outside the mesh table')
        return self.column_continuous[columns]

    def _add(self, name, ids, labels):
        import torch
        eligible = self.continuous()[ids]
        count = self.counts[name]
        count[0] += torch.bincount(labels, minlength=count.shape[1])
        count[1] += torch.bincount(labels[eligible], minlength=count.shape[1])
        if self.kind_keys:
            kind = self.column_kind[self.raw.scene.terrain.terrain_types.long()[ids]]
            for i in range(len(self.kind_keys)):
                count[2 + i] += torch.bincount(labels[kind == i], minlength=count.shape[1])

    def reset(self, ids):
        import torch
        eligible = self.continuous()[ids]
        self.runtime.env_stage[ids] = eligible.long()
        self.term.is_flag_env[ids[~eligible]] = False
        selected = ids[eligible]
        # No draws for other terrain, and no implicit flags assigned there.
        choices = torch.rand(len(selected), generator=self.term.gen, device=self.term.gen.device) < self.contract['shares']['flag']
        self.term.is_flag_env[selected] = choices.to(self.term.is_flag_env.device)
        # Kind bundles draw after the continuous columns, so the continuous flag draws keep their stream.
        if self.kind_keys:
            kind = self.column_kind[self.raw.scene.terrain.terrain_types.long()[ids]]
            for i, key in enumerate(self.kind_keys):
                chosen = ids[kind == i]
                flags = torch.rand(len(chosen), generator=self.term.gen, device=self.term.gen.device) \
                    < self.contract['kind_commands'][key]['flag']
                self.term.is_flag_env[chosen] = flags.to(self.term.is_flag_env.device)
                self.runtime.env_stage[chosen[~flags.to(chosen.device)]] = 2 + i    # a flag env stays with the flag allocator
        self._add('reset_modes', ids, self.term.is_flag_env[ids].long())

    def samples(self, ids, slots):
        import torch
        labels = (torch.full_like(ids, len(EX39_SLOTS)) if slots is None else slots.long())
        if bool(((labels < 0) | (labels >= len(self.names))).any()):
            raise ValueError('EX-42 command sample has no valid slot')
        self._add('samples', ids, labels)

    def pre_step(self):
        import torch
        ids = torch.arange(self.raw.num_envs, device=self.raw.device)
        labels = torch.where(self.term.is_flag_env, len(EX39_SLOTS), self.term.slot_current)
        if bool(((labels < 0) | (labels >= len(self.names))).any()):
            raise ValueError('EX-42 consumed command has no sampled slot')
        self._add('steps', ids, labels)

    def state_dict(self):
        counts = ({k: v.cpu().tolist() for k,v in self.counts.items()} if hasattr(self, 'counts')
                  else self.pending_counts)
        return {'contract': self.contract, 'counts': counts}

    def _restore_counts(self, counts):
        import torch
        if not isinstance(counts, dict) or set(counts) != set(self.counts):
            raise ValueError('EX-42 command counts missing')
        for key, target in self.counts.items():
            value = torch.as_tensor(counts[key], device=target.device)
            if value.shape != target.shape or value.dtype != torch.int64 or bool((value < 0).any()):
                raise ValueError('EX-42 command counts invalid')
            target.copy_(value)

    def load_state_dict(self, state):
        if not isinstance(state, dict) or state.get('contract') != self.contract:
            raise ValueError('EX-42 command allocation continuation contract differs')
        if hasattr(self, 'counts'):
            self._restore_counts(state.get('counts'))
        else:
            self.pending_counts = state.get('counts')

    def restart_counts(self, iteration):
        # A shared DDP checkpoint only stores rank 0. Never copy its observed counts to rank 1.
        # Sampling RNG is restored by the existing command_rng path; these are record-only counters.
        for count in self.counts.values():
            count.zero_()
        self.count_origin_update = iteration

    def write(self, folder, iteration, checkpoint, *, plan_sha, stage_id):
        cumulative = {}
        for name, count in self.counts.items():
            names = ('free', 'flag') if name == 'reset_modes' else self.names
            cumulative[name] = {}
            for denominator, values in zip(('all', 'continuous', *(f'kind:{k}' for k in self.kind_keys)), count.cpu().tolist()):
                total = sum(values)
                cumulative[name][denominator] = {'counts': dict(zip(names, values)), 'total': total,
                    'fractions': {k: v/total if total else None for k,v in zip(names, values)}}
        rank = int(os.environ.get('RANK', '0'))
        doc = {'format': 'ex42-command-shares/1', 'stage_id': stage_id, 'iteration': iteration,
               'rank': rank, 'world_size': int(os.environ.get('WORLD_SIZE','1')),
               'plan_sha256': plan_sha, 'configured': self.contract, 'cumulative': cumulative,
               'count_origin_update': self.count_origin_update,
               'checkpoint': ({'path': str(Path(checkpoint).resolve()),
                               'sha256': hashlib.sha256(Path(checkpoint).read_bytes()).hexdigest()}
                              if checkpoint is not None else None),
               'checkpoint_binding': 'consumer must bind the saved model and manifest for this plan/stage/iteration',
               'counting': 'rank-local cumulative since count_origin_update; resume starts a new count segment'}
        target = Path(folder)/f'command_shares_{iteration}_rank{rank}.json'
        if target.exists():
            # A process that died between this record and its save left the name behind; the run came back to the
            # iteration from an earlier save. Keep the old record out of the judges' glob and write the live counts.
            aside = target.parent/'superseded'
            aside.mkdir(exist_ok=True)
            index = len(list(aside.glob(f'{target.stem}.*.json')))
            os.replace(target, aside/f'{target.stem}.{index}.json')
        fd, temp = tempfile.mkstemp(dir=target.parent, prefix='.command-shares-')
        try:
            with os.fdopen(fd,'w',encoding='utf-8') as stream:
                json.dump(doc,stream,sort_keys=True,allow_nan=False)
                stream.flush();os.fsync(stream.fileno())
            os.link(temp,target)                    # Existing boundary evidence is never overwritten.
        finally:
            os.unlink(temp)
        return doc
