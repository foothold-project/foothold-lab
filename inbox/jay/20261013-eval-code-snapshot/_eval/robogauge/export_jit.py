# Export MoE-CTS student checkpoints (model_*.pt) to the TorchScript format RoboGauge loads.
# CPU only. Uses the repo's own exporter (rsl_rl.utils.exporter_cts.export_cts_policy_as_jit),
# the same function the training runner calls before submitting to the RoboGauge server.
# Run with: CUDA_VISIBLE_DEVICES= isaac311-moects python export_jit.py <ckpt> <out_pt>
import os
import sys

os.environ.setdefault("CUDA_VISIBLE_DEVICES", "")

import torch
import yaml
from tensordict import TensorDict

from rsl_rl.modules import ActorCriticMoECTS
from rsl_rl.utils.exporter_cts import export_cts_policy_as_jit


def main(ckpt_path: str, out_path: str) -> None:
    assert not torch.cuda.is_available(), "GPU must be hidden for export"
    run_dir = os.path.dirname(ckpt_path)
    with open(os.path.join(run_dir, "params", "agent.yaml"), encoding="utf-8") as f:
        agent = yaml.unsafe_load(f)
    pcfg = dict(agent["policy"])
    pcfg.pop("class_name")

    sd = torch.load(ckpt_path, map_location="cpu", weights_only=False)["model_state_dict"]
    # Shapes from the checkpoint itself (no env needed).
    # student encoder input = policy obs (history), actor input = latent + single_obs, teacher input = critic obs
    num_actor_obs = sd["student_moe_encoder.moe.gating_network.0.network.0.weight"].shape[1]
    assert num_actor_obs == sd["student_moe_encoder.moe.experts.backbone.network.0.weight"].shape[1]
    num_single_obs = sd["actor.network.0.weight"].shape[1] - int(pcfg["latent_dim"])
    num_critic_obs = sd["teacher_encoder.0.network.0.weight"].shape[1]
    num_actions = sd["std"].shape[0] if "std" in sd else sd["log_std"].shape[0]
    print(f"[export] actor_obs={num_actor_obs} single_obs={num_single_obs} critic_obs={num_critic_obs} actions={num_actions}")

    obs = TensorDict(
        {
            "policy": torch.zeros(1, num_actor_obs),
            "critic": torch.zeros(1, num_critic_obs),
            "single_obs": torch.zeros(1, num_single_obs),
        },
        batch_size=[1],
    )
    obs_groups = {"policy": ["policy"], "critic": ["critic"]}
    policy = ActorCriticMoECTS(obs, obs_groups, num_actions, **pcfg)
    print(f"[export] load_state_dict: {policy.load_state_dict(sd, strict=True)}")
    policy.eval()

    out_dir, fname = os.path.split(out_path)
    export_cts_policy_as_jit(
        policy,
        actor_obs_normalizer=policy.actor_obs_normalizer,
        single_obs_normalizer=policy.single_obs_normalizer,
        path=out_dir,
        filename=fname,
    )

    # Known-answer check: JIT (history kept internally) must equal the eager student path
    # fed with the same feature-blocked history that Isaac Lab builds (oldest -> newest per term).
    jit = torch.jit.load(out_path)
    jit.reset()
    torch.manual_seed(0)
    hist_len = num_actor_obs // num_single_obs
    dims = [3, 3, 3, num_actions, num_actions, num_actions]
    frames = []
    max_err = 0.0
    with torch.no_grad():
        for t in range(hist_len + 5):
            x = torch.randn(1, num_single_obs) * 0.5
            frames.append(x)
            y_jit = jit(x)
            # eager: build history (zeros before first frame)
            window = ([torch.zeros(1, num_single_obs)] * hist_len + frames)[-hist_len:]
            blocks = []
            off = 0
            for d in dims:
                blocks.append(torch.cat([w[:, off:off + d] for w in window], dim=-1))
                off += d
            hist = torch.cat(blocks, dim=-1)
            latent, _ = policy.student_moe_encoder(hist)
            y_eager = policy.actor(torch.cat([latent, x], dim=-1))
            max_err = max(max_err, float((y_jit - y_eager).abs().max()))
    print(f"[export] jit-vs-eager max abs err over {hist_len + 5} steps: {max_err:.3e}")
    assert max_err < 1e-4, "JIT export does not match eager policy"
    print(f"[export] saved {out_path}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
