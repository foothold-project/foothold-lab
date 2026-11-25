"""D101 value-only Go2 mirror for the 666-wide EX-41 critic.

The first 52 entries are o45, body linear velocity3, contacts4.  Both
legacy and clean52 assemble those groups in this order.  Ground map is
32x16; foot maps are FL, FR, RL, RR, each 5x5 (start_obs.py).
"""

from __future__ import annotations

import math
import os

import torch
from torch import nn

from rsl_rl.algorithms import PPO

from foothold_s2.models.start_policy import ACTOR_KEY, CRITIC_KEY
from foothold_s2.runners.ex41_valid_storage import ValidRolloutStorage, safe_minibatch_advantage


LEG_SWAP = (1, 0, 3, 2)
JOINT_IDS = tuple(4 * joint + LEG_SWAP[leg] for joint in range(3) for leg in range(4))
JOINT_SIGNS = (-1,) * 4 + (1,) * 8
EXPECTED_JOINT_NAMES = tuple(
    f"{leg}_{joint}_joint"
    for joint in ("hip", "thigh", "calf")
    for leg in ("FL", "FR", "RL", "RR")
)


def assert_joint_order(joint_names) -> None:
    """Reject an env whose policy joint order differs from EX-40 evidence."""
    if tuple(joint_names) != EXPECTED_JOINT_NAMES:
        raise ValueError("EX-41 critic mirror joint_names differ from EX-40 coordinate metadata")


def mirror_policy45(x: torch.Tensor) -> torch.Tensor:
    """The shared Go2 o45 coordinate reflection used by critic and actor."""
    if x.shape[-1] != 45:
        raise ValueError("EX-41 mirror needs 45 policy entries")
    y = x.clone()
    y[..., 0:3] = x[..., 0:3] * x.new_tensor((-1, 1, -1))
    y[..., 3:6] = x[..., 3:6] * x.new_tensor((1, -1, 1))
    y[..., 6:9] = x[..., 6:9] * x.new_tensor((1, -1, -1))
    joint_signs = x.new_tensor(JOINT_SIGNS)
    for lo in (9, 21, 33):
        y[..., lo:lo + 12] = x[..., lo:lo + 12][..., JOINT_IDS] * joint_signs
    return y


def mirror_critic(x: torch.Tensor) -> torch.Tensor:
    if x.shape[-1] != 666:
        raise ValueError("EX-41 mirror needs 666 critic entries")
    y = x.clone()
    # Angular velocity is an axial vector under left-right reflection.
    y[..., 0:45] = mirror_policy45(x[..., 0:45])
    y[..., 45:48] = x[..., 45:48] * x.new_tensor((1, -1, 1))
    y[..., 48:52] = x[..., 48:52][..., list(LEG_SWAP)]
    y[..., 52:564] = x[..., 52:564].reshape(*x.shape[:-1], 32, 16).flip(-1).flatten(-2)
    y[..., 564:664] = x[..., 564:664].reshape(*x.shape[:-1], 4, 5, 5)[..., list(LEG_SWAP), :, :].flip(-1).flatten(-3)
    y[..., 664] = x[..., 664]   # body height delta
    y[..., 665] = -x[..., 665]  # body roll
    return y


def value_loss(value: torch.Tensor, old_value: torch.Tensor, returns: torch.Tensor,
               clip_param: float, clipped: bool) -> torch.Tensor:
    if clipped:
        limited = old_value + (value - old_value).clamp(-clip_param, clip_param)
        return torch.maximum((value - returns).square(), (limited - returns).square()).mean()
    return (value - returns).square().mean()


SCHEDULER_KL_CLIP = None  # off: a per-sample cap of 1.0 moved the lr path of it 0..223 in 15 % of the minibatches
BOUNDS_LOSS_COEF = 0.1  # weight of the action-mean bounds loss (lead 11/14 16:51: about 10 to 20 % of the surrogate gradient)


# ON by default since lead 11/14 19:28 (set the share to 0 to turn it off: the update is then bit-identical to before):
# a share of the training envs rolls out with a smaller action noise so that
# their reward sees the walk of the mean action (the v28 probe of the mean action drifted 0.10 to 0.81 while every training
# record stayed flat). The scale is part of the policy of those envs, so PPO stays on-policy for each env group (see
# StartActorCritic.noise_scale).
SMALL_NOISE_ENV_SHARE = 0.25     # v28p (lead 11/15 09:26): back to the v28f share while the low-speed rule below is off
SMALL_NOISE_SIGMA_SCALE = 0.2
# v28m (lead 11/15 07:02, ON by default; set the threshold to 0 to turn it off: the share above then applies as in v28l):
# an env whose command has |(vx, vy)| below the threshold rolls out with the small noise for that step, decided again at
# every step from the command it acts on (so on every command resample); the other envs keep a fixed spread share.
SMALL_NOISE_LOWSPEED_CMD = 0.3   # v29-4 (lead 11/15 15:27): the v28n rule is ON (v28p had 0.0 = OFF); 0.0 turns it off again (then only SMALL_NOISE_ENV_SHARE applies)
SMALL_NOISE_REST_SHARE = 0.25
# lead 11/26 01:23 (나): the action-std multiplier of the LOW-SPEED envs only (|cmd_xy| < SMALL_NOISE_LOWSPEED_CMD), from the env
# EX42_SMALL_NOISE_LOW_SIGMA; unset or empty = SMALL_NOISE_SIGMA_SCALE (bit-identical). The fixed-share envs keep SMALL_NOISE_SIGMA_SCALE.
LOWSPEED_SIGMA_ENV = "EX42_SMALL_NOISE_LOW_SIGMA"


def lowspeed_sigma_scale() -> float:
    raw = os.environ.get(LOWSPEED_SIGMA_ENV, "")
    if raw == "":
        return SMALL_NOISE_SIGMA_SCALE
    try:
        value = float(raw)
    except ValueError:
        raise ValueError(f"{LOWSPEED_SIGMA_ENV} must be a number in (0, 1) (got {raw!r})") from None
    if not math.isfinite(value) or not 0.0 < value < 1.0:
        raise ValueError(f"{LOWSPEED_SIGMA_ENV} must be a number in (0, 1) (got {raw!r})")
    return value
# v28p (lead 11/15 09:26, ON by default; set the share to 0 to turn it off: nothing below changes then, bit-identical to v28n/v28f):
# this share of the envs (spread evenly over the env index, same on every rank) acts with the MEAN action (noise exactly 0).
# Their rows are marked invalid for PPO (the existing quarantine mask): no surrogate, value, entropy, bounds, scheduler KL
# and no advantage normalisation statistics. The perception replay is filled for every env, so the perception loss
# (velocity head included) still sees them: the velocity estimate is trained on the walk the noise-free evaluation shows.
MEAN_ACTION_PERCEPTION_SHARE = 0.0


def small_noise_static_share() -> float:
    """Share of the index-spread envs that are always small-noise: the rest share while the low-speed rule is on, else the v28l share."""
    return SMALL_NOISE_REST_SHARE if SMALL_NOISE_LOWSPEED_CMD > 0 else SMALL_NOISE_ENV_SHARE


STAND_SIGMA_ENV = "EX42_SMALL_NOISE_STAND_SIGMA"
# lead 11/26 02:08 (Gk4, planner 02:08): EX42_SMALL_NOISE_LOW_SIGMA applies to the low-speed rows WITH a command (0 < |cmd| , the
# vx vy wz triple not all zero, kl_probe.command_branch convention); the zero-command rows (stand, stop) of the low-speed mask take
# EX42_SMALL_NOISE_STAND_SIGMA, unset or empty = SMALL_NOISE_SIGMA_SCALE. Both unset = the old single-scale rule (bit-identical).
STAND_CMD_EPS = 1e-6


def stand_sigma_scale() -> float:
    raw = os.environ.get(STAND_SIGMA_ENV, "")
    if raw == "":
        return SMALL_NOISE_SIGMA_SCALE
    try:
        value = float(raw)
    except ValueError:
        raise ValueError(f"{STAND_SIGMA_ENV} must be a number in (0, 1) (got {raw!r})") from None
    if not math.isfinite(value) or not 0.0 < value < 1.0:
        raise ValueError(f"{STAND_SIGMA_ENV} must be a number in (0, 1) (got {raw!r})")
    return value


def zero_command_mask(cmd: torch.Tensor) -> torch.Tensor:
    """[num_envs] bool: vx, vy and wz of the command are all zero (stand or stop)."""
    return (cmd[..., :3].abs() <= STAND_CMD_EPS).all(dim=-1)


def lowspeed_scale(cmd: torch.Tensor, threshold: float, static: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    """Per-env action-std multiplier [num_envs, 1 or A]: low-speed rows with a command -> lowspeed_sigma_scale(), low-speed rows with a
    zero command -> stand_sigma_scale(), the other rows -> static. Returns (scale, low mask, low-and-zero-command mask)."""
    low = lowspeed_noise_mask(cmd[..., :2], threshold)
    stand = low & zero_command_mask(cmd)
    move_s, stand_s = lowspeed_sigma_scale(), stand_sigma_scale()
    scale = torch.where(low[:, None], torch.where(stand[:, None], torch.full_like(static, stand_s), torch.full_like(static, move_s)),
                        static)
    return scale, low, stand


def lowspeed_noise_mask(cmd_xy: torch.Tensor, threshold: float) -> torch.Tensor:
    """[num_envs] bool: the command speed (vx vy norm) is below the threshold (a standing command counts); threshold 0 selects none."""
    return cmd_xy.norm(dim=-1) < threshold


def small_noise_mask(num_envs: int, share: float) -> torch.Tensor:
    """Which envs roll out with the small noise: spread evenly over the env index (no rng, same on every rank).
    Exactly floor(num_envs * share) envs; share 0 selects none."""
    if not 0.0 <= share < 1.0:
        raise ValueError("small noise env share must be in [0, 1)")
    index = torch.arange(num_envs, dtype=torch.float64)
    return torch.floor((index + 1) * share + 1e-9) > torch.floor(index * share + 1e-9)


def mean_action_mask(num_envs: int, share: float, device=None) -> torch.Tensor | None:
    """[num_envs] bool: the envs that act with the mean action (and stay out of PPO), or None when the share is 0."""
    if not share:
        return None
    return small_noise_mask(num_envs, share).to(device)


def small_noise_scale(num_envs: int, share: float, scale: float, device=None) -> torch.Tensor | None:
    """[num_envs, 1] action-std multiplier, or None when the share is 0 (nothing changes)."""
    if not share:
        return None
    if not 0.0 < scale < 1.0:
        raise ValueError("small noise sigma scale must be in (0, 1)")
    mask = small_noise_mask(num_envs, share)
    return torch.where(mask, torch.tensor(scale), torch.tensor(1.0)).to(torch.float32).reshape(-1, 1).to(device)


def clip_scheduler_kl(kl: torch.Tensor, clip: float | None) -> torch.Tensor:
    """Per-sample KL as the adaptive-lr input: one sample far past the cap must not decide the mean for the batch
    (v28 it 224: three samples of one env at KL 3,700 to 4,700 moved the mean to 0.14 and the lr to its floor)."""
    return kl if clip is None else kl.clamp(max=clip)


class CriticMirrorPPO(PPO):
    """Ordinary PPO while off; when enabled only the value loss gets mirrors.

    Mirrored old values were never stored.  Therefore the mirror branch uses
    an unclipped squared return loss.  The original branch retains PPO's
    configured clipping.  The two value losses are averaged to keep scale.
    The actor uses the original all-parameter PPO gradient clip before mirror
    critic gradients are substituted and clipped separately.  Actor data are
    neither mirrored nor repeated.  Symmetry, RND and recurrence are rejected for
    this specialized update.  Multi-GPU averages the actor gradient and the
    mirrored critic gradient across ranks; an empty mini batch contributes zero
    gradients, so every rank exchanges and steps the same number of times.
    """

    mirror_enabled = False
    actor_mirror_weight = 0.0
    actor_mirror_aug = False     # F2 EX42_ACTOR_MIRROR_AUG: mirrored samples join the surrogate (off = the same bytes as before)
    kl_audit = None
    # Per-sample KL cap for the adaptive learning rate only (PPO loss, ratio clip and the audited KL stay raw).
    # None restores the installed uncapped mean.
    scheduler_kl_clip = SCHEDULER_KL_CLIP
    # Mean actions past the env clip never reach the env (they only move the log-prob), so nothing stops them from
    # growing. sum_dims relu(|mu| - limit)^2 is zero inside the limit. The runner sets the limit from clip_actions (None = off).
    bounds_loss_coef = BOUNDS_LOSS_COEF
    bounds_loss_limit = None
    mean_action_mask = None      # [num_envs] bool set by the runner: these envs act with the mean action and are not PPO samples
    # EX-42 BC prior (ex42_bc_prior, lead 2026-11-21 17:21): a frozen parent actor and beta, set by the runner from
    # EX42_BC_PRIOR_CKPT / EX42_BC_PRIOR_BETA. None = off (the update is the same bytes as before).
    bc_prior = None
    bc_beta = 0.0
    bc_ratio_updates = 10        # lead 17:36 (a): grad-norm ratio ||d BC|| / ||d surrogate|| on the actor, the first 10 updates
    _bc_updates_seen = 0

    def act(self, obs):
        if self.kl_audit is not None:
            self.kl_audit.observe("capture_rollout", self.storage.step)
        if self.storage.noise_scale_env is not None:      # the update sets per-row scales; a rollout is per env
            self.policy.noise_scale = self.storage.noise_scale_env
            if self.storage.noise_scale_steps is not None:   # low-speed rule: the scale of every step is kept for the update
                self.storage.noise_scale_steps[self.storage.step] = self.storage.noise_scale_env
        actions = super().act(obs)
        if self.mean_action_mask is not None:             # noise exactly 0: the policy mean; the rows are invalid for PPO (see process_env_step)
            actions[self.mean_action_mask] = self.transition.action_mean[self.mean_action_mask]
        return actions

    def init_storage(self, training_type, num_envs, num_transitions_per_env, obs, actions_shape):
        self.storage = ValidRolloutStorage(training_type, num_envs, num_transitions_per_env,
                                           obs, actions_shape, self.device)

    def process_env_step(self, obs, rewards, dones, extras):
        valid = extras.get("ex41_ppo_valid")
        if valid is None:
            raise ValueError("EX-41 PPO validity mask missing from quarantine step")
        valid = torch.as_tensor(valid, device=self.storage.valid.device, dtype=torch.bool).flatten()
        if valid.shape != (self.storage.num_envs,):
            raise ValueError("EX-41 PPO validity mask shape differs from env count")
        if self.mean_action_mask is not None:
            valid = valid & ~self.mean_action_mask.to(valid.device)
        step = self.storage.step
        self.storage.valid[step].copy_(valid)
        super().process_env_step(obs, rewards, dones, extras)
        if self.kl_audit is not None:
            self.kl_audit.observe("after_env_step", dones)
        if not bool(valid.all()):
            # A quarantined transition is a terminal boundary.  This also
            # prevents its next-state value from entering the previous GAE.
            bad = ~valid
            self.storage.rewards[step, bad] = 0
            self.storage.values[step, bad] = 0
            self.storage.dones[step, bad] = 1
            self.storage.actions_log_prob[step, bad] = 0
            self.storage.mu[step, bad] = 0
            self.storage.sigma[step, bad] = 1

    def compute_returns(self, obs):
        last_valid = self.storage.valid[-1]
        if bool(last_valid.all()):
            last_values = self.policy.evaluate(obs).detach()
        else:
            # Never evaluate a quarantined final observation.  An extreme but
            # finite critic input can overflow to Inf, and PPO's 0 * Inf in
            # the terminal bootstrap would then poison earlier valid GAE.
            last_values = torch.zeros_like(self.storage.values[-1])
            if bool(last_valid.any()):
                last_values[last_valid] = self.policy.evaluate(obs[last_valid]).detach()
        self.storage.compute_returns(last_values, self.gamma, self.lam, normalize_advantage=False)
        valid = self.storage.valid.unsqueeze(-1)
        if not self.normalize_advantage_per_mini_batch:
            # Preserve the installed normalization path when all rows are valid.
            if bool(valid.all()):
                advantage = self.storage.advantages
                self.storage.advantages = (advantage - advantage.mean()) / (advantage.std() + 1e-8)
            elif bool(valid.any()):
                advantage = self.storage.advantages[valid]
                mean = advantage.mean()
                std = advantage.std() if advantage.numel() > 1 else advantage.new_zeros(())
                self.storage.advantages = torch.where(valid, (self.storage.advantages - mean) / (std + 1e-8), 0)
            else:
                self.storage.advantages.zero_()

    def _average_gradients(self, parameters) -> None:
        """Mean of the ranks' gradients; a missing gradient counts as zero so every rank sends the same size."""
        if not self.is_multi_gpu:
            return
        parameters = tuple(parameters)
        flat = torch.cat([(p.grad if p.grad is not None else torch.zeros_like(p)).reshape(-1) for p in parameters])
        torch.distributed.all_reduce(flat, op=torch.distributed.ReduceOp.SUM)
        flat /= self.gpu_world_size
        offset = 0
        for param in parameters:
            param.grad = flat[offset:offset + param.numel()].view_as(param).clone()
            offset += param.numel()

    def _exchange_empty_batch(self) -> None:
        """This rank had no valid row for a slot. It repeats the other ranks' exchanges in the same order with
        zero contributions (adaptive-lr KL, actor gradient, critic gradient) and takes the same step."""
        if self.desired_kl is not None and self.schedule == "adaptive":
            kl = torch.zeros((), device=self.device)
            torch.distributed.all_reduce(kl, op=torch.distributed.ReduceOp.SUM)
            kl /= self.gpu_world_size
            if self.gpu_global_rank == 0:
                if kl > self.desired_kl * 2.0:
                    self.learning_rate = max(1e-5, self.learning_rate / 1.5)
                elif 0 < kl < self.desired_kl / 2.0:
                    self.learning_rate = min(1e-2, self.learning_rate * 1.5)
            lr_tensor = torch.tensor(self.learning_rate, device=self.device)
            torch.distributed.broadcast(lr_tensor, src=0)
            self.learning_rate = lr_tensor.item()
            for group in self.optimizer.param_groups:
                group["lr"] = self.learning_rate
        for param in self.policy.parameters():
            param.grad = torch.zeros_like(param)
        self._average_gradients(self.policy.parameters())
        nn.utils.clip_grad_norm_(self.policy.parameters(), self.max_grad_norm)
        critic_params = tuple(self.policy.critic.parameters())
        for param in critic_params:
            param.grad = torch.zeros_like(param)
        self._average_gradients(critic_params)
        nn.utils.clip_grad_norm_(critic_params, self.max_grad_norm)
        self.optimizer.step()

    def update(self) -> dict[str, float]:
        if self.kl_audit is None:
            return self._update_impl()
        self.kl_audit.observe("begin_update")
        try:
            return self._update_impl()
        finally:
            self.kl_audit.observe("end_update")

    def _update_impl(self) -> dict[str, float]:
        parameters = tuple(self.policy.parameters())
        if not bool(torch.stack([torch.isfinite(param).all() for param in parameters]).all()):
            skipped = float(self.num_learning_epochs * self.num_mini_batches)
            self.storage.clear()
            result = {"value_function": 0.0, "surrogate": 0.0, "entropy": 0.0,
                      "ppo_skipped_batches": skipped, "ppo_nonfinite_parameters": 1.0}
            if self.mirror_enabled:
                result.update(value_mirror=0.0, value_combined=0.0)
            return result
        if not self.mirror_enabled:
            if self.bc_prior is not None:
                raise ValueError("EX-42 BC prior needs the critic-mirror update loop (the installed PPO.update path has no place for it)")
            if self.actor_mirror_weight or self.actor_mirror_aug:
                raise ValueError("EX-42 actor mirror needs the critic-mirror update loop")
            safe_norm = self.normalize_advantage_per_mini_batch
            if safe_norm:
                # Installed PPO normalizes after sampling.  Move the same
                # operation into the valid-row generator so a singleton can
                # bypass its undefined unbiased standard deviation.
                self.storage.normalize_per_batch_safely = True
                self.normalize_advantage_per_mini_batch = False
            try:
                result = super().update()
            finally:
                self.storage.normalize_per_batch_safely = False
                self.normalize_advantage_per_mini_batch = safe_norm
            actual = self.storage.yielded_batches
            expected = self.num_learning_epochs * self.num_mini_batches
            if actual:
                result = {key: value * expected / actual for key, value in result.items()}
            result["ppo_skipped_batches"] = float(self.storage.skipped_batches)
            return result
        if self.symmetry or self.rnd or self.policy.is_recurrent:
            raise ValueError("EX-41 critic mirror supports feed-forward PPO without symmetry or RND")
        total_v = total_m = total_combined = total_s = total_e = total_b = total_over = mu_max = 0.0
        total_bc, total_bc_n, bc_batches = 0.0, 0, 0
        total_actor_mirror = 0.0
        actor_mirror_rows = actor_mirror_all_rows = 0
        mirror_grad_ratio_sum = mirror_grad_ratio_n = 0.0
        mirror_select = bool(self.actor_mirror_weight or self.actor_mirror_aug)
        total_aug, aug_rows, aug_all_rows, aug_ratio_dev = 0.0, 0, 0, 0.0
        ratio_sum, ratio_n = 0.0, 0
        measure_ratio = self.bc_prior is not None and self._bc_updates_seen < self.bc_ratio_updates
        self.storage.yield_skipped = self.is_multi_gpu
        batches = self.storage.mini_batch_generator(self.num_mini_batches, self.num_learning_epochs)
        for batch in batches:
            if batch is None:
                if mirror_select and self.is_multi_gpu:
                    # Match the extra selected-row count collective on every
                    # rank, including a rank whose valid minibatch is empty.
                    selected_global = torch.zeros((), device=self.device)
                    torch.distributed.all_reduce(selected_global)
                self._exchange_empty_batch()
                continue
            (obs, actions, old_value, advantage, returns, old_logp, old_mu, old_sigma, hidden, masks) = batch
            if mirror_select:
                selected = self.storage.batch_actor_mirror_mask
                if selected is None:
                    raise ValueError("EX-42 actor mirror rollout mask was not stored")
                selected_n = int(selected.sum())
                actor_mirror_rows += selected_n
                actor_mirror_all_rows += selected.numel()
                if self.is_multi_gpu:
                    selected_global = torch.tensor(float(selected_n), device=self.device)
                    torch.distributed.all_reduce(selected_global)
                    actor_mirror_scale = self.gpu_world_size * selected_n / max(float(selected_global), 1.0)
                else:
                    actor_mirror_scale = 1.0
            if self.normalize_advantage_per_mini_batch:
                with torch.no_grad():
                    advantage = safe_minibatch_advantage(advantage)
            if self.storage.noise_scale_env is not None:
                self.policy.noise_scale = self.storage.batch_noise_scale
            self.policy.act(obs, masks=masks, hidden_state=hidden[0])
            logp = self.policy.get_actions_log_prob(actions)
            value = self.policy.evaluate(obs, masks=masks, hidden_state=hidden[1])
            mu, sigma, entropy = self.policy.action_mean, self.policy.action_std, self.policy.entropy
            if self.desired_kl is not None and self.schedule == "adaptive":
                with torch.inference_mode():
                    kl = clip_scheduler_kl(torch.sum(torch.log(sigma / old_sigma + 1.0e-5)
                                                     + (old_sigma.square() + (old_mu - mu).square())
                                                     / (2.0 * sigma.square()) - 0.5, dim=-1),
                                           self.scheduler_kl_clip).mean()
                    if self.is_multi_gpu:
                        torch.distributed.all_reduce(kl, op=torch.distributed.ReduceOp.SUM)
                        kl /= self.gpu_world_size
                    if self.gpu_global_rank == 0:
                        if kl > self.desired_kl * 2.0:
                            self.learning_rate = max(1e-5, self.learning_rate / 1.5)
                        elif 0 < kl < self.desired_kl / 2.0:
                            self.learning_rate = min(1e-2, self.learning_rate * 1.5)
                    if self.is_multi_gpu:
                        lr_tensor = torch.tensor(self.learning_rate, device=self.device)
                        torch.distributed.broadcast(lr_tensor, src=0)
                        self.learning_rate = lr_tensor.item()
                    for group in self.optimizer.param_groups:
                        group["lr"] = self.learning_rate
            ratio = torch.exp(logp - old_logp.squeeze())
            surrogate = torch.maximum(-advantage.squeeze() * ratio,
                                      -advantage.squeeze() * ratio.clamp(1.0 - self.clip_param, 1.0 + self.clip_param)).mean()
            if self.actor_mirror_aug:
                # concat-batch mean of the original rows and the mirrored mask rows (rsl_rl data augmentation form)
                from foothold_s2.runners.ex42_actor_mirror import mirrored_surrogate_rows
                aug_rows_value, aug_ratio = mirrored_surrogate_rows(self.policy, obs, actions, old_logp, advantage, self.clip_param)
                aug_sum = torch.where(selected, aug_rows_value, torch.zeros_like(aug_rows_value)).sum()
                surrogate = (surrogate * ratio.numel() + aug_sum) / (ratio.numel() + selected_n)
                aug_rows += selected_n
                aug_all_rows += selected.numel()
                total_aug += float(aug_sum.detach())
                aug_ratio_dev += float((aug_ratio.detach()[selected] - 1.0).abs().sum())
            original_value = value_loss(value, old_value, returns, self.clip_param, self.use_clipped_value_loss)
            mirrored = obs.clone()
            mirrored[CRITIC_KEY] = mirror_critic(obs[CRITIC_KEY])
            mirror_value = self.policy.evaluate(mirrored, masks=masks, hidden_state=hidden[1])
            mirror_loss = (mirror_value - returns).square().mean()
            combined_value = 0.5 * (original_value + mirror_loss)
            base_loss = surrogate + self.value_loss_coef * original_value - self.entropy_coef * entropy.mean()
            if self.actor_mirror_weight:
                from foothold_s2.runners.ex42_actor_mirror import actor_mirror_loss
                actor_sym = actor_mirror_loss(self.policy, obs, mu, selected)
                if selected_n and getattr(self, "_actor_mirror_updates_seen", 0) < 10:
                    actor_params = tuple(q for q in self.policy.actor.parameters() if q.requires_grad)
                    sym_grad = torch.autograd.grad(actor_sym, actor_params, retain_graph=True, allow_unused=True)
                    sur_grad = torch.autograd.grad(surrogate, actor_params, retain_graph=True, allow_unused=True)
                    norm = lambda grads: torch.sqrt(sum((g.square().sum() for g in grads if g is not None), torch.zeros((), device=mu.device)))
                    denominator = float(norm(sur_grad))
                    if denominator > 0:
                        mirror_grad_ratio_sum += self.actor_mirror_weight * actor_mirror_scale * float(norm(sym_grad)) / denominator
                        mirror_grad_ratio_n += 1
                base_loss = base_loss + self.actor_mirror_weight * actor_mirror_scale * actor_sym
                total_actor_mirror += float(actor_sym.detach()) * selected_n
            if self.bounds_loss_limit is not None and self.bounds_loss_coef:
                excess = torch.relu(mu.abs() - self.bounds_loss_limit)
                bounds = excess.square().sum(dim=-1).mean()      # sum over action dims, mean over samples (rl_games shape)
                base_loss = base_loss + self.bounds_loss_coef * bounds
                total_b += float(bounds.detach())
                total_over += float((excess > 0).float().mean().detach())
                mu_max = max(mu_max, float(mu.detach().abs().max()))
            if self.bc_prior is not None:
                from foothold_s2.runners.ex42_bc_prior import bc_loss, slow_mask
                with torch.no_grad():
                    prior_mu = self.bc_prior.act_inference(obs)
                bc, bc_n = bc_loss(mu, prior_mu, slow_mask(obs[ACTOR_KEY]))
                if measure_ratio and bc_n:
                    actor_params = [q for q in self.policy.actor.parameters() if q.requires_grad]
                    g_bc = torch.autograd.grad(bc, actor_params, retain_graph=True, allow_unused=True)
                    g_s = torch.autograd.grad(surrogate, actor_params, retain_graph=True, allow_unused=True)
                    norm = lambda gs: torch.sqrt(sum((g.square().sum() for g in gs if g is not None), torch.zeros(())))  # noqa: E731
                    n_s = float(norm(g_s))
                    if n_s > 0:
                        ratio_sum += float(norm(g_bc)) / n_s; ratio_n += 1
                base_loss = base_loss + self.bc_beta * bc
                total_bc += float(bc.detach()); total_bc_n += bc_n; bc_batches += 1
            self.optimizer.zero_grad()
            base_loss.backward(retain_graph=True)
            self._average_gradients(self.policy.parameters())
            # Preserve the exact unaugmented PPO clip for actor and std.
            nn.utils.clip_grad_norm_(self.policy.parameters(), self.max_grad_norm)
            critic_params = tuple(self.policy.critic.parameters())
            critic_grads = torch.autograd.grad(self.value_loss_coef * combined_value, critic_params)
            for param, grad in zip(critic_params, critic_grads, strict=True):
                param.grad = grad
            self._average_gradients(critic_params)
            nn.utils.clip_grad_norm_(critic_params, self.max_grad_norm)
            self.optimizer.step()
            total_v += float(original_value.detach())
            total_m += float(mirror_loss.detach())
            total_combined += float(combined_value.detach())
            total_s += float(surrogate.detach())
            total_e += float(entropy.mean().detach())
        self.storage.yield_skipped = False
        if self.storage.noise_scale_env is not None:
            self.policy.noise_scale = self.storage.noise_scale_env
        count = self.storage.yielded_batches
        skipped = self.storage.skipped_batches
        self.storage.clear()
        count = max(count, 1)
        result = {"value_function": total_v / count, "value_mirror": total_m / count,
                  "value_combined": total_combined / count,
                  "surrogate": total_s / count, "entropy": total_e / count,
                  "ppo_skipped_batches": float(skipped)}
        if self.storage.noise_scale_env is not None:
            shown = self.storage.noise_scale_env if self.storage.noise_scale_steps is None else self.storage.noise_scale_steps
            result.update(small_noise_env_share=float((shown < 1).float().mean()),
                          small_noise_sigma_scale=float(shown.min()))
        if self.bounds_loss_limit is not None and self.bounds_loss_coef:
            result.update(bounds_loss=total_b / count, mu_over_limit_frac=total_over / count, mu_abs_max=mu_max)
        if self.bc_prior is not None:
            result.update(bc_prior_loss=total_bc / max(bc_batches, 1), bc_prior_samples=float(total_bc_n))
            ratio = f" grad_ratio_raw={ratio_sum / ratio_n:.6g} grad_ratio_weighted={self.bc_beta * ratio_sum / ratio_n:.6g}" if ratio_n else ""
            if ratio_n:
                result.update(bc_prior_grad_ratio_raw=ratio_sum / ratio_n)
            self._bc_updates_seen += 1
            if getattr(self, "gpu_global_rank", 0) == 0:
                print(f"EX42_BC_PRIOR beta={self.bc_beta} loss={total_bc / max(bc_batches, 1):.6g} samples={total_bc_n} "
                      f"batches={bc_batches}{ratio}", flush=True)
        if self.actor_mirror_aug:
            if self.is_multi_gpu:
                totals = torch.tensor((total_aug, aug_rows, aug_all_rows, aug_ratio_dev), dtype=torch.float64, device=self.device)
                torch.distributed.all_reduce(totals)
                total_aug, aug_rows, aug_all_rows, aug_ratio_dev = totals.tolist()
            result["actor_mirror_aug_surrogate"] = total_aug / max(aug_rows, 1)
            result["actor_mirror_aug_fraction"] = aug_rows / max(aug_all_rows, 1)
            result["actor_mirror_aug_ratio_abs_dev"] = aug_ratio_dev / max(aug_rows, 1)
            self._actor_mirror_aug_updates_seen = getattr(self, "_actor_mirror_aug_updates_seen", 0) + 1
            if getattr(self, "gpu_global_rank", 0) == 0 and self._actor_mirror_aug_updates_seen <= 10:
                print(f"EX42_ACTOR_MIRROR_AUG on update={self._actor_mirror_aug_updates_seen} rows={int(aug_rows)} "
                      f"fraction={result['actor_mirror_aug_fraction']:.6g} surrogate_mirror={result['actor_mirror_aug_surrogate']:.6g} "
                      f"ratio_abs_dev={result['actor_mirror_aug_ratio_abs_dev']:.6g}", flush=True)
                if result["actor_mirror_aug_fraction"] < 0.05:
                    print("EX42_ACTOR_MIRROR_AUG warning=mask_fraction_below_0.05", flush=True)
        if self.actor_mirror_weight:
            if self.is_multi_gpu:
                totals = torch.tensor((total_actor_mirror, actor_mirror_rows, actor_mirror_all_rows,
                                       mirror_grad_ratio_sum, mirror_grad_ratio_n),
                                      dtype=torch.float64, device=self.device)
                torch.distributed.all_reduce(totals)
                (total_actor_mirror, actor_mirror_rows, actor_mirror_all_rows,
                 mirror_grad_ratio_sum, mirror_grad_ratio_n) = totals.tolist()
            result["actor_mirror"] = total_actor_mirror / max(actor_mirror_rows, 1)
            result["actor_mirror_mask_fraction"] = actor_mirror_rows / max(actor_mirror_all_rows, 1)
            ratio = mirror_grad_ratio_sum / mirror_grad_ratio_n if mirror_grad_ratio_n else float("nan")
            if mirror_grad_ratio_n:
                result["actor_mirror_grad_ratio_weighted"] = ratio
            self._actor_mirror_updates_seen = getattr(self, "_actor_mirror_updates_seen", 0) + 1
            if getattr(self, "gpu_global_rank", 0) == 0:
                print(f"Mean actor_mirror loss {result['actor_mirror']:.6g} mask_fraction={result['actor_mirror_mask_fraction']:.6g} "
                      f"grad_ratio_weighted={ratio:.6g}", flush=True)
                if result["actor_mirror_mask_fraction"] < 0.05:
                    print("EX42_ACTOR_MIRROR warning=mask_fraction_below_0.05", flush=True)
        return result
