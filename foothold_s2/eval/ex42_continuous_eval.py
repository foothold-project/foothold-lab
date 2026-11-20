"""Continuous-only Kit child using the unchanged eval_map_modes implementation.

MAPSWAP flat formula is copied verbatim from planner's approved probe:
/home/jay/mai/tmp/planner/mapprobe1120/run_child_map.py:24-26 (2026-11-20).
No training classes or the three existing mode paths change on disk.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import runpy
import sys

import numpy as np

from foothold_s2.ex42_continuous_cells import COMMANDS, DEFINITION, KINDS, MODES, SEEDS, sha


def flat_map(g):
    if g.ndim != 3 or tuple(g.shape[1:]) != (32, 16):
        raise ValueError('continuous flat map requires 32x16')
    base = g[:, 9:11, :].flatten(1).median(1).values
    return base[:, None, None].expand_as(g).clone()


def wrap_advance(original):
    """Same injection point as MAPSWAP, beneath the evaluator's true-GT error tap."""
    def advance(self, h_prop, h_terr, hist, depth2, tick, first, use_gt, gt_map, *rest):
        if getattr(self, '_continuous_flat', False):
            if gt_map is None or not bool(use_gt.all()):
                raise ValueError('continuous flat requires GT in every env')
            gt_map = flat_map(gt_map)
            self._continuous_flat_calls += 1
        return original(self, h_prop, h_terr, hist, depth2, tick, first, use_gt, gt_map, *rest)
    return advance


def policy_class(base, *, output, steps, seed, checkpoint_sha256):
    """Wrap only this dedicated process; preserve the base policy's model and resets."""
    order = [(m, c) for m in MODES for c in COMMANDS]
    constructed = []

    class ContinuousPolicy(base):
        def __init__(self, runner, n, z_mode=None, act_mode=None, map_mode=None):
            import torch
            if len(constructed) >= len(order) or map_mode != order[len(constructed)][0] or n != 64:
                raise ValueError('continuous policy cell order/env count differs')
            mode, command = order[len(constructed)]
            constructed.append((mode, command))
            runner.perception._continuous_flat = mode == 'probe_flat'
            runner.perception._continuous_flat_calls = 0
            super().__init__(runner, n, z_mode=z_mode, act_mode=act_mode,
                             map_mode='eval_gt' if mode == 'probe_flat' else mode)
            self._cell = (mode, command)
            self._fall, self._timeout = [], []
            self._alive_first = torch.ones(n, dtype=torch.bool, device=runner.device)

        def reset(self, dones):
            import torch
            raw = self.runner.env.unwrapped
            terminated = raw.termination_manager.terminated.bool()
            timeout = raw.termination_manager.time_outs.bool()
            done = dones.bool()
            if (done.shape != self._alive_first.shape or terminated.shape != done.shape or
                    timeout.shape != done.shape or not torch.equal(done, terminated | timeout)):
                raise ValueError('continuous termination manager disagrees with env dones')
            self._fall.append((self._alive_first & terminated).detach().cpu().numpy().copy())
            self._timeout.append((self._alive_first & timeout).detach().cpu().numpy().copy())
            self._alive_first &= ~done
            super().reset(dones)
            if len(self._fall) > steps:
                raise ValueError('continuous child emitted more steps than registered')
            if len(self._fall) == steps:
                mode, command = self._cell
                flat_calls = self.runner.perception._continuous_flat_calls
                if flat_calls != (steps if mode == 'probe_flat' else 0):
                    raise ValueError('continuous flat intervention call count differs')
                path = Path(output) / f'continuous_telemetry_{mode}_{command}.npz'
                tmp = path.with_suffix('.tmp.npz')
                np.savez(tmp, fall=np.stack(self._fall), timeout=np.stack(self._timeout),
                         mode=mode, command=command, seed=seed, checkpoint_sha256=checkpoint_sha256,
                         flat_calls=flat_calls, flat_definition=DEFINITION['flat_map'],
                         producer_sha256=sha(__file__))
                os.replace(tmp, path)
    return ContinuousPolicy


def parse(argv):
    parser = argparse.ArgumentParser(add_help=False)
    for name in ('task', 'checkpoint', 'envs', 'steps', 'modes', 'command-suite', 'commands', 'fixed-level',
                 'mesh-dir', 'ex42-kind-family', 'ex42-kind-name', 'eval-seed', 'ex42-evaluation-plan', 'out', 'device'):
        parser.add_argument('--' + name, required=True)
    parser.add_argument('--fixed-terrain', action='store_true')
    parser.add_argument('--start-yaw-zero', action='store_true')
    args, rest = parser.parse_known_args(argv)
    if (args.envs != '64' or args.steps != '600' or args.modes != ','.join(MODES) or
            args.commands != ','.join(COMMANDS) or args.command_suite != 'core' or
            not args.fixed_terrain or not args.start_yaw_zero or args.ex42_kind_family != 'A' or
            args.ex42_kind_name not in KINDS or int(args.eval_seed) not in SEEDS or
            not 0 <= int(args.fixed_level) <= 9 or
            any(x != '--headless' and not x.startswith('--kit_args=') for x in rest)):
        raise ValueError('continuous child argv differs from registered cells')
    # A probe inherited from another script must not silently alter the four cells.
    if os.environ.get('MAPSWAP') or os.environ.get('S2_MAP_MODE'):
        raise ValueError('continuous child refuses inherited map override')
    return args


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    args = parse(argv)                      # CPU validation before any Kit import
    from foothold_s2.eval import adapters
    from foothold_s2.models.start_perception import StartPerception
    advance, policy, old_argv = StartPerception._advance, adapters.S2Policy, sys.argv
    try:
        StartPerception._advance = wrap_advance(advance)
        adapters.S2Policy = policy_class(policy, output=args.out, steps=600,
                                         seed=int(args.eval_seed), checkpoint_sha256=sha(args.checkpoint))
        sys.argv = ['eval_map_modes', *argv]
        runpy.run_module('foothold_s2.eval.eval_map_modes', run_name='__main__', alter_sys=True)
    finally:
        StartPerception._advance, adapters.S2Policy, sys.argv = advance, policy, old_argv


if __name__ == '__main__':
    main()
