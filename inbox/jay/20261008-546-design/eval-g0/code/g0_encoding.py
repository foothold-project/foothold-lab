# G0: height-scan no-hit encoding, legacy vs "finite check then miss value".
#
# Legacy = what the E1 critic (teacher) height block computes today:
#   Isaac Lab envs/mdp/observations.py:292-300  height = sensor.pos_w.z - ray_hits_w.z - offset (offset 0.5)
#   ObsTerm in robot_lab env_cfg.py:225-229     clip (-1, 1), scale 2.5
#   ObservationManager.compute_group :404-407   clip first, then scale
#   RayCaster: a missed ray keeps ray_hits_w = inf (utils/warp/ops.py:71) -> height = -inf -> -1 -> -2.5
#   sensor.pos_w is the base position; the cfg offset (0,0,20) is added to ray_starts only (ray_caster.py:221-224)
# G0 = same formula, but non-finite hit / height is replaced by MISS_VALUE before clip and scale
#   (reference: foothold-lab sim/eval/gap_observations.py height_scan_with_gap, miss_value=+1.0).

import torch

OFFSET = 0.5
CLIP = (-1.0, 1.0)
SCALE = 2.5
MISS_VALUE = 1.0  # design G0: +1 before clip/scale -> +2.5 final


def raw_height(sensor_z: torch.Tensor, hit_z: torch.Tensor, offset: float = OFFSET) -> torch.Tensor:
    """sensor_z: (N,), hit_z: (N, R)."""
    return sensor_z.unsqueeze(1) - hit_z - offset


def legacy_encode(sensor_z, hit_z, offset=OFFSET):
    h = raw_height(sensor_z, hit_z, offset)
    return h.clip(min=CLIP[0], max=CLIP[1]) * SCALE


def g0_encode(sensor_z, hit_z, offset=OFFSET, miss_value=MISS_VALUE):
    h = raw_height(sensor_z, hit_z, offset)
    valid = torch.isfinite(hit_z) & torch.isfinite(h)
    h = torch.where(valid, h, torch.full_like(h, float(miss_value)))
    return h.clip(min=CLIP[0], max=CLIP[1]) * SCALE


def classify(hit_z):
    """Per-ray cause label: 0 finite hit, 1 +inf/-inf (no-hit from the ray caster), 2 NaN."""
    lab = torch.zeros_like(hit_z, dtype=torch.long)
    lab[torch.isinf(hit_z)] = 1
    lab[torch.isnan(hit_z)] = 2
    return lab
