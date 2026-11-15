import os
import sys
assert os.environ.get('CUDA_VISIBLE_DEVICES') == '-1'
sys.path.insert(0, 'C:/isaac/ext/go2_rl_robotlab/source/rsl_rl')
import torch
from tensordict import TensorDict
from rsl_rl.modules import ActorCriticMoECTS
from rsl_rl.algorithms.moe_cts import MoECTS
for n in (1, 2, 3, 4, 5):
    obs = TensorDict({'policy': torch.zeros(n, 8), 'critic': torch.zeros(n, 8),
                      'single_obs': torch.zeros(n, 4)}, batch_size=[n])
    policy = ActorCriticMoECTS(obs, {'policy': ['policy'], 'critic': ['critic']}, 2,
                               actor_hidden_dims=[8], critic_hidden_dims=[8],
                               teacher_encoder_hidden_dims=[8], student_encoder_hidden_dims=[8],
                               expert_num=2, latent_dim=4)
    try:
        alg = MoECTS(policy, None, n, teacher_env_ratio=0.75, device='cpu')
    except AssertionError as ex:
        print(f'num_envs={n} ASSERT {ex}', flush=True)
    else:
        print(f'num_envs={n} PASS teacher={alg.teacher_env_idxs.tolist()} student={alg.student_env_idxs.tolist()}', flush=True)
