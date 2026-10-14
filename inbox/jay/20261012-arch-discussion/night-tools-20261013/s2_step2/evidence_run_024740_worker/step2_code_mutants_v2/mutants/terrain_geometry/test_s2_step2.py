"""Known-answer CPU tests for S2 learning integration and fake RayCaster."""
import copy
from collections import Counter
import hashlib
import json
import math
import os
from pathlib import Path
import random
from types import SimpleNamespace

os.environ["CUDA_VISIBLE_DEVICES"] = "-1"
import numpy as np
import torch
from torch import nn
from torch.distributions import Normal

from s2_env_adapter import AdapterFault, expected_world_xy, training_map, validate_scanner_config, yaw_from_quat_wxyz
from s2_ppo import PPOConfig, S2PPO, adaptive_lr
from s2_runner import S2Runner, S2RunnerError, _same_state
from s2_terrain_overlay import EncounterLog, TerrainOverlayError, make_overlay
from s2_policy import make_optimizer
from s2_launch_gate import check as launch_check

torch.set_num_threads(2)
ROOT = Path(__file__).parent


def check(label, condition):
    print(("PASS" if condition else "FAIL"), label, flush=True)
    if not condition:
        raise AssertionError(label)


def scanner_cfg():
    return SimpleNamespace(ray_alignment="yaw", offset=SimpleNamespace(pos=(0., 0., 20.)),
        pattern_cfg=SimpleNamespace(ordering="xy", size=(1.6, 1.0), resolution=.1,
                                    direction=(0., 0., -1.)))


class FakeEnv:
    num_envs = 2
    def __init__(self, *, mode_height=0.0, fault=None, reset_at=2):
        self.t = 0
        self.episodes = torch.zeros(2, dtype=torch.long)
        self.tokens = torch.zeros(2, dtype=torch.long)
        self.mode_height = mode_height
        self.fault = fault
        self.reset_at = reset_at
        self.cfg = scanner_cfg()
        self.stale_reset = False
    def get_observations(self):
        t = float(self.t)
        policy = torch.tensor([[t, 0.1], [t+0.2, -0.1]])
        critic = torch.tensor([[t, self.mode_height], [t+0.2, self.mode_height]])
        if self.fault == "critic_nan":
            critic[0, 0] = math.nan
        return {"policy": policy, "single_obs": torch.ones(2, 1), "critic": critic}
    def height_scanner(self):
        pos = torch.tensor([[0., 0., 1.], [1., 0., 1.]])
        xy = expected_world_xy(pos, self.base_yaw_w())
        hits = torch.cat((xy, torch.full((2, 187, 1), .5-self.mode_height-.01*self.t)), dim=-1)
        if self.fault == "sensor_nan":
            hits[0, 0, 2] = math.nan
        return SimpleNamespace(cfg=self.cfg, data=SimpleNamespace(pos_w=pos, ray_hits_w=hits))
    def base_yaw_w(self): return torch.zeros(2)
    def episode_ids(self): return self.episodes
    def frame_tokens(self): return self.tokens
    def step(self, actions):
        self.t += 1
        self.tokens += 1
        prior_episode = int(self.episodes[0])
        events = ([{"kind":"gap","event":"assigned","env_id":0,"episode_id":prior_episode},
                   {"kind":"gap","event":"approach","env_id":0,"episode_id":prior_episode}]
                  if self.t == 1 else
                  [{"kind":"gap","event":"pass","env_id":0,"episode_id":prior_episode}]
                  if self.t == 2 else [])
        done = torch.tensor([self.t == self.reset_at, False])
        if done[0]:
            self.episodes[0] += 1
            if self.stale_reset:
                self.tokens[0] -= 1
            self.mode_height += .3
        reward = torch.ones(2) + torch.rand(2)*.01 + float(np.random.random())*.01 + random.random()*.01
        if self.fault == "reward_nan" and self.t == 3:
            reward[0] = math.nan
        return self.get_observations(), reward, done, {"encounters": events}
    def state_dict(self):
        return {"t": self.t, "episodes": self.episodes.clone(), "tokens": self.tokens.clone(),
                "height": self.mode_height, "fault": self.fault}
    def load_state_dict(self, state):
        self.t = state["t"]
        self.episodes = state["episodes"].clone()
        self.tokens = state["tokens"].clone()
        self.mode_height = state["height"]
        self.fault = state["fault"]


class FakePolicy(nn.Module):
    def __init__(self, mode):
        super().__init__()
        self.mode = mode
        self.student_moe_encoder = nn.Linear(2, 2)
        self.map_encoder = nn.Linear(374, 2)
        self.actor = nn.Linear(5, 1)
        self.critic = nn.Linear(4, 1)
        self.std = nn.Parameter(torch.ones(1)*.5)
        self.distribution = None
    def param_groups(self):
        return {"student_encoder": list(self.student_moe_encoder.parameters()),
                "map_encoder": list(self.map_encoder.parameters()),
                "actor": list(self.actor.parameters()), "critic": list(self.critic.parameters()),
                "std": [self.std]}
    def get_critic_obs(self, obs): return obs["critic"]
    def act(self, obs):
        m = obs["map"]
        if self.mode == "A" and not bool(torch.all(m == 0)):
            raise ValueError("A map leaked terrain")
        z = self.student_moe_encoder(obs["policy"])
        mz = self.map_encoder(m)
        mu = self.actor(torch.cat((z, obs["single_obs"], mz), -1))
        self.distribution = Normal(mu, self.std.expand_as(mu))
        return self.distribution.sample()
    def evaluate(self, obs):
        z = self.student_moe_encoder(obs["policy"]).detach()
        return self.critic(torch.cat((z, obs["critic"]), -1))
    @property
    def action_mean(self): return self.distribution.mean
    @property
    def action_std(self): return self.distribution.stddev
    @property
    def entropy(self): return self.distribution.entropy().sum(-1)
    def get_actions_log_prob(self, actions): return self.distribution.log_prob(actions).sum(-1)


CFG = PPOConfig(rollout_steps=3, num_envs=2, epochs=2, minibatches=2, clip_param=.2,
                gamma=.99, lam=.95, value_loss_coef=1., entropy_coef=.01,
                max_grad_norm=1., desired_kl=.01, schedule="adaptive", use_clipped_value_loss=True)
ENV_SHA = hashlib.sha256(b"fake-env-v1").hexdigest()


def build(mode="B", *, env=None, encoder_mode="full_freeze", W=None, r=None):
    policy = FakePolicy(mode)
    kwargs = {} if encoder_mode == "full_freeze" else {"encoder_freeze_updates": W, "encoder_lr_ratio": r}
    opt, ctl = make_optimizer(policy, .001, encoder_mode=encoder_mode, **kwargs)
    algo = S2PPO(policy, opt, ctl, CFG)
    return S2Runner(env or FakeEnv(), algo, mode=mode, env_config_sha256=ENV_SHA,
                    geometry_tolerance_m=.02)


def tests():
    assert os.environ["CUDA_VISIBLE_DEVICES"] == "-1"
    torch.manual_seed(11); np.random.seed(11); random.seed(11)
    e = FakeEnv()
    scanner = e.height_scanner()
    validate_scanner_config(scanner.cfg)
    check("ray index x-fast and no 20m re-add", expected_world_xy(scanner.data.pos_w, e.base_yaw_w())[0, 1, 0] == -0.7 and
          training_map(scanner, mode="B", yaw_w=e.base_yaw_w(), geometry_tolerance_m=.02)[0][0, 0] == 0)
    yaw = yaw_from_quat_wxyz(torch.tensor([[math.sqrt(.5), 0., 0., math.sqrt(.5)]]))
    check("yaw 90 ray geometry", torch.allclose(yaw, torch.tensor([math.pi/2]), atol=1e-6))
    bad = copy.deepcopy(scanner); bad.cfg.pattern_cfg.ordering = "yx"
    try: training_map(bad, mode="B", yaw_w=e.base_yaw_w(), geometry_tolerance_m=.02)
    except AdapterFault: check("ray order mismatch rejected", True)
    else: check("ray order mismatch rejected", False)
    a = training_map(FakeEnv(mode_height=0).height_scanner(), mode="A", yaw_w=e.base_yaw_w(), geometry_tolerance_m=.02)[0]
    a2 = training_map(FakeEnv(mode_height=.7).height_scanner(), mode="A", yaw_w=e.base_yaw_w(), geometry_tolerance_m=.02)[0]
    b = training_map(FakeEnv(mode_height=0).height_scanner(), mode="B", yaw_w=e.base_yaw_w(), geometry_tolerance_m=.02)[0]
    b2 = training_map(FakeEnv(mode_height=.7).height_scanner(), mode="B", yaw_w=e.base_yaw_w(), geometry_tolerance_m=.02)[0]
    check("A terrain information blocked", torch.equal(a, a2) and bool(torch.all(a == 0)))
    check("B terrain information changes", not torch.equal(b, b2))
    runner = build("B")
    batch, audit = runner.collect()
    check("rollout map snapshot and bootstrap time", batch is not None and audit["rollout_maps"].shape == (6, 374)
          and audit["bootstrap_map"].shape == (2, 374) and
          not torch.equal(audit["rollout_maps"][:2], audit["rollout_maps"][2:4]) and
          not torch.equal(audit["rollout_maps"][4:6], audit["bootstrap_map"]))
    check("reset uses new episode map", abs(float(batch["obs"]["map"][4, 0])-.32) < 1e-6 and
          abs(float(batch["obs"]["map"][2, 0])-.01) < 1e-6)
    check("runner logs assigned and encountered separately", audit["encounters"]["gap_assigned"] == 1 and
          audit["encounters"]["gap_approach"] == 1 and audit["encounters"]["gap_pass"] == 1)
    seen = []
    original_act = runner.algo.policy.act
    def traced(obs):
        seen.append(obs["map"].detach().clone())
        return original_act(obs)
    runner.algo.policy.act = traced
    update = runner.algo.update(batch, 0)
    used = torch.cat(seen)
    expected = batch["obs"]["map"].repeat(CFG.epochs, 1)
    rows = lambda x: Counter(tuple(row.tolist()) for row in x)
    check("all minibatches use saved map", used.shape == expected.shape and rows(used) == rows(expected))
    check("fixed step count and PPO-only loss", update["optimizer_steps"] == CFG.epochs*CFG.minibatches
          and update["loss_terms"] == ("ppo_surrogate", "ppo_value", "entropy")
          and runner.algo.ctl.steps_total == 4)
    check("adaptive LR parent thresholds", adaptive_lr(.001, .03, .01, "adaptive") == max(1e-5,.001/1.5)
          and adaptive_lr(.001, .001, .01, "adaptive") == .001*1.5)
    stale = FakeEnv(); stale.stale_reset = True
    r = build(env=stale).update_once()
    check("reset stale sensor frame invalid before update", r["status"] == "invalid" and
          "reset reused previous sensor frame" in r["stop_reason"] and r["optimizer_steps"] == 0)
    nan = build(env=FakeEnv(fault="sensor_nan")).update_once()
    check("sensor NaN holds both-arm gate", nan["status"] == "invalid" and
          nan["fault_counts"]["ray_packet_bad"] > 0 and nan["optimizer_steps"] == 0)
    critic = build(env=FakeEnv(fault="critic_nan")).update_once()
    check("critic NaN holds before update", critic["status"] == "invalid" and
          critic["fault_counts"]["critic_input_nonfinite"] > 0)
    try:
        reward = build(env=FakeEnv(fault="reward_nan")).update_once()
        reward_held = reward["status"] == "invalid" and reward["other_nonfinite"]["reward"] > 0 and reward["optimizer_steps"] == 0
    except Exception:
        reward_held = False
    check("reward NaN gate blocks update", reward_held)
    torch.manual_seed(55)
    arm_a = build("A")
    torch.manual_seed(55)
    arm_b = build("B")
    check("A and B same update plan and control rule", arm_a.plan["ppo"] == arm_b.plan["ppo"] and
          arm_a.plan["encoder_mode"] == arm_b.plan["encoder_mode"] and
          _same_state(arm_a.algo.policy.state_dict(), arm_b.algo.policy.state_dict()) and
          arm_a.update_once()["optimizer_steps"] == arm_b.update_once()["optimizer_steps"])
    mid = build()
    mid.algo.ctl.begin_update(0, mid.algo.lr)
    try: mid.save(ROOT.parent / "forbidden_mid_update.pt")
    except S2RunnerError: check("checkpoint during update refused", True)
    else: check("checkpoint during update refused", False)
    # Independent continuation from the same checkpoint includes torch, numpy,
    # python and fake environment state, not only weights and optimizer.
    torch.manual_seed(87); np.random.seed(87); random.seed(87)
    first = build()
    first.update_once()
    checkpoint = ROOT.parent / "fixture_s2_step2" / "resume.pt"
    first.save(checkpoint)
    continued = first.update_once()
    weights = copy.deepcopy(first.algo.policy.state_dict())
    control = first.algo.ctl.state_dict()
    environment = first.env.state_dict()
    rng_next = (torch.rand(1), np.random.random(), random.random())
    second = build()
    second.load(checkpoint)
    resumed = second.update_once()
    rng_replayed = (torch.rand(1), np.random.random(), random.random())
    check("resume bit identical policy optimizer env and RNG", _same_state(weights, second.algo.policy.state_dict()) and
          _same_state(control, second.algo.ctl.state_dict()) and
          _same_state(environment, second.env.state_dict()) and
          continued["base_lr"] == resumed["base_lr"] and
          torch.equal(rng_next[0], rng_replayed[0]) and rng_next[1:] == rng_replayed[1:])
    wrong = build("A")
    try: wrong.load(checkpoint)
    except S2RunnerError: check("different arm resume rejected", True)
    else: check("different arm resume rejected", False)
    changed_rule = build("B", encoder_mode="schedule", W=1, r=.1)
    try: changed_rule.load(checkpoint)
    except S2RunnerError: check("different encoder rule resume rejected", True)
    else: check("different encoder rule resume rejected", False)
    terrain = SimpleNamespace(sub_terrains={k: SimpleNamespace(proportion=v) for k,v in
        (("flat", .5),("slope", .5),("gap", 0.),("stepping_stones", 0.))})
    overlay = make_overlay(terrain, gap_proportion=.1, stones_proportion=.1)
    check("terrain geometry from CPU probe and parent untouched", overlay.sub_terrains["gap"].gap_width_range == (.10,.25)
          and overlay.sub_terrains["stepping_stones"].stone_width_range == (.50,.70)
          and terrain.sub_terrains["gap"].proportion == 0.)
    encounters = EncounterLog()
    encounters.record("gap", "assigned", 0, 0); encounters.record("gap", "approach", 0, 0)
    encounters.record("gap", "pass", 0, 0)
    check("allocation distinct from encounter and outcome", encounters.report()["gap_assigned"] == 1 and
          encounters.report()["gap_approach"] == 1 and encounters.report()["gap_pass"] == 1)
    try: encounters.record("stepping_stones", "fall", 1, 0)
    except TerrainOverlayError: check("outcome without approach rejected", True)
    else: check("outcome without approach rejected", False)
    approval = ROOT.parent / "fixture_s2_step2" / "approval.json"
    deadline = 9999999999.0
    approval.write_text(json.dumps({"approved":True,"by":"CPU_FIXTURE","approved_at":"fixture",
        "reviewed":{"plan_sha256":"a"*64,"env_config_sha256":"b"*64,
                    "code_sha256":"c"*64,"deadline_epoch":deadline}}),encoding="utf-8")
    check("approval draft gate known answer", len(launch_check(approval,plan_sha256="a"*64,
          env_sha256="b"*64,code_sha256="c"*64,deadline_epoch=deadline))==64)
    try: launch_check(approval,plan_sha256="x"*64,env_sha256="b"*64,code_sha256="c"*64,deadline_epoch=deadline)
    except ValueError: check("approval plan mutation rejected", True)
    else: check("approval plan mutation rejected", False)
    denied = ROOT.parent / "fixture_s2_step2" / "denied.json"
    denied.write_text(json.dumps({**json.loads(approval.read_text(encoding="utf-8")), "approved": False}), encoding="utf-8")
    try: launch_check(denied,plan_sha256="a"*64,env_sha256="b"*64,code_sha256="c"*64,deadline_epoch=deadline)
    except ValueError: check("unapproved launch denied", True)
    else: check("unapproved launch denied", False)


if __name__ == "__main__":
    tests()
