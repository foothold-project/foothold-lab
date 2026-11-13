"""Load the real checkpoint into the real actor on CPU; not a locomotion test."""
import argparse
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import torch
import yaml
from tensordict import TensorDict

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))
from foothold_s2.eval.action_sampling_probe import IsolatedActionPolicy, learned_std
from foothold_s2.models.start_policy import StartActorCritic, OBS_GROUPS
from prepare import DEFAULT_RUN, sha


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--run', type=Path, default=DEFAULT_RUN)
    p.add_argument('--iteration', type=int, default=250)
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    cp = a.run / f'model_{a.iteration}.pt'
    expected = json.loads((a.run / 'manifest.json').read_text())['checkpoints'][cp.name]
    if sha(cp) != expected:
        raise ValueError('checkpoint does not match manifest')
    data = torch.load(cp, map_location='cpu', weights_only=False)
    state = data['model_state_dict']
    dims = (state['actor.0.weight'].shape[1], state['critic.0.weight'].shape[1])
    if dims != (98, 666) or data['ex41_pose_commands'] is not True:
        raise ValueError('expected EX-41 pose command checkpoint')
    obs = TensorDict({'actor_in': torch.zeros(64, dims[0]),
                      'critic_in': torch.zeros(64, dims[1])}, batch_size=[64])
    cfg = yaml.safe_load((a.run / 'params/agent.yaml').read_text())['policy']
    cfg.pop('class_name', None)
    actor = StartActorCritic(obs, OBS_GROUPS, 12, pose_command_dim=2, **cfg)
    actor.load_state_dict(state, strict=True)
    actor.eval()
    with torch.inference_mode():
        mean = actor.act_inference(obs)
        wrapped = IsolatedActionPolicy(actor.act, 'cpu', 42)
        rng = torch.random.get_rng_state().clone()
        sampled = wrapped(obs)
        if not torch.equal(rng, torch.random.get_rng_state()):
            raise ValueError('private action sampling changed global RNG')
        replay = IsolatedActionPolicy(actor.act, 'cpu', 42)(obs)
        if not torch.equal(sampled, replay) or torch.equal(mean, sampled):
            raise ValueError('sampled actions not reproducible or identical to mean')
        std = learned_std(SimpleNamespace(runner=SimpleNamespace(alg=SimpleNamespace(policy=actor))))
        epsilon = torch.empty_like(mean).normal_(generator=torch.Generator().manual_seed(42))
        error = (sampled - (mean + torch.tensor(std) * epsilon)).abs().max().item()
        if error > 1e-6:
            raise ValueError('sample differs from loaded Normal(mean,std)')
    result = {'format': 'foothold-action-pair-cpu-rehearsal/1', 'state': 'PASS',
              'checkpoint': str(cp), 'checkpoint_sha256': expected, 'device': 'cpu',
              'actor_dim': dims[0], 'critic_dim': dims[1], 'num_actions': 12,
              'std': std, 'std_mean': sum(std) / 12, 'strict_state_dict': True,
              'same_seed_replay': True, 'global_rng_unchanged': True,
              'sample_max_abs_error_from_expected_normal': error,
              'scope': 'synthetic zero observation, CPU actor compatibility only; no Kit or locomotion result'}
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
