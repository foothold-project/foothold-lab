"""Record-only action-mean/sample comparison; no training imports or settings."""
from __future__ import annotations

import torch


def validate(args):
    """Keep formal evaluations deterministic; sampling requires a narrow diagnostic scope."""
    probe = args.action_sampling_probe
    if not probe:
        if args.action_mode != 'mean':
            raise ValueError('sample action requires --action-sampling-probe (record only)')
        return
    if (args.command_suite != 'e1_v2' or args.commands != 'fwd0.1,fwd0.2'
            or args.envs != 64 or args.steps != 300 or args.modes != 'eval_gt,eval_pred'
            or not args.fixed_terrain or args.fixed_level not in (0, 5)
            or args.terrain_set != 'default' or not args.mesh_dir
            or args.dr_mode != 'off' or not args.ex42_evaluation_plan
            or any(getattr(args, k, False) for k in ('axis_v2', 'ex42_maintenance',
                     'terrain_skill', 'terrain_skill_v2', 'push_ladder', 'n21_record_only',
                     'gait_contact_sweep', 'ex42_kind_family', 'ex42_kind_name'))):
        raise ValueError('action probe needs pinned e1_v2 fwd0.1,fwd0.2, GT/PRED, 64 x 300, fixed L0/L5, DR off')
    if type(args.eval_seed) is not int or not 0 <= args.eval_seed < 2**32:
        raise ValueError('action probe seed must be a uint32')


def receipt(args):
    return {'format': 'foothold-action-sampling-probe/1', 'record_only': True,
            'action_mode': args.action_mode, 'latent_mode': 'mean',
            'eval_seed': args.eval_seed, 'action_seed': args.eval_seed,
            'rng': 'isolated_torch_rng_stream' if args.action_mode == 'sample' else 'no_action_sampling',
            'formal_score_eligible': False}


def output_name(args):
    return 'action_probe_map_modes.json' if args.action_sampling_probe else 'map_modes.json'


def learned_std(policy):
    """Read the loaded actor parameter; never substitute the assumed 0.47."""
    actor = policy.runner.alg.policy
    if getattr(actor, 'state_dependent_std', False):
        raise ValueError('this diagnostic requires state-independent action std')
    if hasattr(actor, 'std'):
        std = actor.std.detach()
    elif hasattr(actor, 'log_std'):
        std = actor.log_std.detach().exp()
    else:
        raise ValueError('loaded policy has no action std parameter')
    if std.shape != (12,) or not torch.isfinite(std).all() or not (std > 0).all():
        raise ValueError('invalid loaded action std')
    return std.cpu().tolist()


class IsolatedActionPolicy:
    """Use the existing S2 sample branch without consuming the sensor/reset RNG.

    One private CPU and device stream per mode/command, seeded identically.
    This preserves normal policy sampling, including its own action std, while
    leaving external observation randomization on its original stream.
    """
    def __init__(self, policy, device, seed):
        self.policy = policy
        self.device = torch.device(device)
        self.devices = [self.device.index if self.device.index is not None else torch.cuda.current_device()] if self.device.type == 'cuda' else []
        if self.device.type not in ('cpu', 'cuda'):
            raise ValueError('action probe supports CPU/CUDA only')
        self.cpu_state = torch.Generator(device='cpu').manual_seed(seed).get_state()
        self.device_state = torch.Generator(device=self.device).manual_seed(seed).get_state() if self.devices else None

    def __call__(self, obs):
        with torch.random.fork_rng(devices=self.devices):
            torch.random.set_rng_state(self.cpu_state)
            if self.devices:
                torch.cuda.set_rng_state(self.device_state, self.devices[0])
            action = self.policy(obs)
            self.cpu_state = torch.random.get_rng_state()
            if self.devices:
                self.device_state = torch.cuda.get_rng_state(self.devices[0])
            return action

    def __getattr__(self, name):
        return getattr(self.policy, name)


def wrap(policy, args, device):
    if args.action_sampling_probe and args.action_mode == 'sample':
        return IsolatedActionPolicy(policy, device, args.eval_seed)
    return policy
