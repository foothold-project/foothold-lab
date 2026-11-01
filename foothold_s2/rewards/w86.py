"""W86 CPU-testable preparation. No live reward/curriculum registration.

Costs are positive with negative weights. Existing terms must not be registered
a second time. Air time is a signed reward for a future positive weight.
Inputs must already use explicit feet/joint names and compatible world frames.
"""
import math
import torch
from foothold_s2.rewards import core

PREREGISTERED = ('knee_effort_margin', 'joint_limit_margin', 'feet_air_time', 'foot_slip')
MAINTAINED_WEIGHTS = {'collision': -10., 'action_smoothness': -.01,
                      'joint_power': -2e-5, 'stumble': -1.}
INITIAL_WEIGHTS = {'zero_yaw': -.5, 'swing': -.5, **MAINTAINED_WEIGHTS,
                   **{name: 0. for name in PREREGISTERED}}


def zero_yaw_l1(yaw_rate_body, command_yaw, heading_active):
    if not torch.isfinite(command_yaw).all():
        raise ValueError('nonfinite yaw command')
    active = (command_yaw.abs() < 1e-6) & ~heading_active.bool()
    if (active & ~torch.isfinite(yaw_rate_body)).any():
        raise ValueError('nonfinite active yaw rate')
    return torch.where(active, yaw_rate_body.abs(), torch.zeros_like(yaw_rate_body))


def ahead_points_body(feet_xy_body, command_body, distances):
    """N,F,2 -> N,F,K,2. Pure yaw produces a different tangent per foot.

    The consumer transforms these samples to world and raycasts the actual
    collision mesh. It must not confuse them with the existing foot-centred ray.
    """
    tangent = torch.stack((-feet_xy_body[..., 1], feet_xy_body[..., 0]), dim=-1)
    velocity = command_body[:, None, :2] + command_body[:, None, 2:3]*tangent
    direction = velocity / torch.linalg.vector_norm(velocity, dim=-1, keepdim=True).clamp_min(1e-8)
    return feet_xy_body[:, :, None, :] + direction[:, :, None, :]*distances[None, None, :, None]


def swing_target(ground_below_world, ground_ahead_world, clearance=.08):
    """Highest valid support + clearance; any missing required ray invalidates a foot.

    Return a finite placeholder AND validity. A placeholder is never evidence
    of real ground. The consumer must log invalid-ray counts, not discard them.
    """
    if not math.isfinite(clearance) or clearance <= 0:
        raise ValueError('clearance must be finite and positive')
    if ground_ahead_world.shape[:-1] != ground_below_world.shape or ground_ahead_world.shape[-1] == 0:
        raise ValueError('ground samples must have shape [N,F,K], K>0')
    valid = torch.isfinite(ground_below_world) & torch.isfinite(ground_ahead_world).all(dim=-1)
    safe_ahead = torch.where(torch.isfinite(ground_ahead_world), ground_ahead_world, torch.zeros_like(ground_ahead_world))
    target = torch.maximum(torch.nan_to_num(ground_below_world), safe_ahead.amax(dim=-1)) + clearance
    return torch.where(valid, target, torch.zeros_like(target)), valid


def swing_clearance_cost(foot_bottom_z_world, target_z_world, foot_velocity_xy_world,
                         contact, ray_valid, moving_command, tanh_multiplier=2.):
    """Spot inner squared-error cost, no exp/sigma, negative config weight.

    Contact does not gate this cost: dragging contact feet are included. The
    contact argument remains for the paired diagnostic interface only.
    Terrain-relative target and moving/valid masks are our design changes.
    """
    if tanh_multiplier < 0 or not math.isfinite(tanh_multiplier):
        raise ValueError('invalid swing shaping parameters')
    finite = (torch.isfinite(foot_bottom_z_world) & torch.isfinite(target_z_world)
              & torch.isfinite(foot_velocity_xy_world).all(-1))
    active = ray_valid.bool() & finite & moving_command[:, None].bool()
    error = torch.where(active, foot_bottom_z_world-target_z_world, torch.zeros_like(target_z_world))
    speed = torch.linalg.vector_norm(torch.nan_to_num(foot_velocity_xy_world), dim=-1)
    cost = (error.square()*torch.tanh(tanh_multiplier*speed)).sum(-1)
    return cost


def stumble_cost(foot_forces_world, min_force_n=0.):
    """Existing START term, never an additional registered reward.

    Optional force floor is for paired diagnostic logging, not a default change.
    """
    if not torch.isfinite(foot_forces_world).all() or not math.isfinite(min_force_n) or min_force_n < 0:
        raise ValueError('invalid stumble forces or floor')
    if min_force_n == 0:
        return core.stumble(foot_forces_world)
    norm = torch.linalg.vector_norm(foot_forces_world, dim=-1)
    ratio = torch.linalg.vector_norm(foot_forces_world[..., :2], dim=-1) > 4*foot_forces_world[..., 2].abs()
    return (ratio & (norm > min_force_n)).any(-1).float()


def collision_cost(body_forces_world, threshold=.1):
    return core.collision_count(torch.linalg.vector_norm(body_forces_world, dim=-1), threshold)


def effort_margin_cost(torque, effort_limits, ratio=.9):
    # Limits must come from this asset/actuator, not a robot-wide guessed scalar.
    if not torch.isfinite(effort_limits).all() or not (effort_limits > 0).all():
        raise ValueError('effort limits must be positive and finite')
    if not torch.isfinite(torque).all() or not math.isfinite(ratio) or not 0 <= ratio <= 1:
        raise ValueError('invalid torque or effort margin ratio')
    return torch.relu(torque.abs()/effort_limits-ratio).square().sum(-1)


def joint_limit_cost(position, lower, upper, margin=.05):
    if not torch.isfinite(lower).all() or not torch.isfinite(upper).all() or not (upper > lower).all():
        raise ValueError('invalid joint limits')
    if not torch.isfinite(position).all() or not math.isfinite(margin) or margin <= 0:
        raise ValueError('margin must be positive')
    return (torch.relu(lower+margin-position).square() + torch.relu(position-upper+margin).square()).sum(-1)


def air_time_term(air_time_at_touchdown, first_contact, moving_command, threshold=.5):
    """Signed air-time reward for a positive weight, currently preregistered zero."""
    active = first_contact.bool() & moving_command[:, None].bool()
    if not math.isfinite(threshold) or (active & ~torch.isfinite(air_time_at_touchdown)).any():
        raise ValueError('invalid active air time or threshold')
    return torch.where(active, air_time_at_touchdown-threshold, torch.zeros_like(air_time_at_touchdown)).sum(-1)


def slip_cost(foot_velocity_xy_world, contact):
    active = contact.bool()
    if (active & ~torch.isfinite(foot_velocity_xy_world).all(-1)).any():
        raise ValueError('nonfinite active slip velocity')
    safe = torch.where(active[..., None], foot_velocity_xy_world, torch.zeros_like(foot_velocity_xy_world))
    return safe.square().sum((-1, -2))


def smoothness_cost(action, previous, previous2):
    return core.action_smoothness_l2(action, previous, previous2)


def energy_cost(torque, joint_velocity):
    return core.joint_power(torque, joint_velocity)


def propose_weights(changes, *, reason, evidence, current_weights=None):
    """Pure W72 handoff record. Does not mutate an env, YAML, ledger or manager.

    Bounds are preparation proposals (-.5 and -1 initial weights). Activation
    and performance rules must be reviewed/approved in the later W72 adapter.
    """
    if not reason or not evidence:
        raise ValueError('a boundary decision requires reason and evidence')
    if set(changes) & set(PREREGISTERED):
        raise ValueError('preregistered zero terms cannot be enabled by this path')
    if not set(changes) <= {'swing', 'stumble'}:
        raise ValueError('only swing and stumble weights belong to this prepared interface')
    before = dict(INITIAL_WEIGHTS if current_weights is None else current_weights)
    if set(before) != set(INITIAL_WEIGHTS) or any(not math.isfinite(v) for v in before.values()):
        raise ValueError('current weights must contain the complete finite preparation contract')
    if before['zero_yaw'] != INITIAL_WEIGHTS['zero_yaw'] or any(before[k] != 0 for k in PREREGISTERED):
        raise ValueError('current weights violate fixed yaw or preregistered zero terms')
    if any(before[k] != value for k, value in MAINTAINED_WEIGHTS.items() if k != 'stumble'):
        raise ValueError('current weights changed maintained terms')
    if not -.5 <= before['swing'] <= 0 or not -1 <= before['stumble'] <= 0:
        raise ValueError('current weights outside proposed interval')
    weights = before.copy()
    for name, value in changes.items():
        lo, hi = (-.5, 0.) if name == 'swing' else (-1., 0.)
        if not math.isfinite(value) or not lo <= value <= hi:
            raise ValueError(f'{name} outside preregistered proposed interval')
        weights[name] = value
    return {'before': before, 'weights': weights, 'reason': reason, 'evidence': evidence,
            'execution_connected': False, 'requires_boundary_adapter_review': True}


def foot_metrics(foot_bottom_z_world, ground_below_world, velocity_xy_world,
                 contact, moving_command, drag_height=.02, drag_speed=.05):
    """Per-frame numerators/denominators, accumulate per foot over each episode.

    No aggregate percentage is produced without its denominator. Thresholds
    are recording proposals; they are not promotion gates.
    """
    valid = (torch.isfinite(foot_bottom_z_world) & torch.isfinite(ground_below_world)
             & torch.isfinite(velocity_xy_world).all(-1))
    moving = moving_command[:, None].bool() & valid
    swing = ~contact.bool() & moving
    stance = contact.bool() & moving
    height = torch.where(valid, foot_bottom_z_world-ground_below_world, torch.zeros_like(ground_below_world))
    speed = torch.linalg.vector_norm(torch.nan_to_num(velocity_xy_world), dim=-1)
    return {'valid': valid, 'height_m': height, 'swing_frames': swing.int(),
            'contact_moving_frames': stance.int(),
            'drag_frames': (stance & (height < drag_height) & (speed > drag_speed)).int(),
            'low_swing_frames': (swing & (height < drag_height) & (speed > drag_speed)).int(),
            'invalid_frames': (~valid).int()}
