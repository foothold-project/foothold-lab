"""R5 raw contract. Recompute contact and foot statistics; hashes alone cannot qualify."""
import json
import math
import re

import numpy as np

FEET = ('FL', 'FR', 'RL', 'RR')
RAW_FORMAT = 'foothold-r5-contact-raw/1'


def recompute(reader, sources, checkpoint):
    if not isinstance(sources, list) or not sources:
        raise ValueError('R5 contact sources absent')
    intervals = {f: [] for f in FEET}
    contributors = {f: set() for f in FEET}
    heights = {f: [] for f in FEET}
    drag = {f: 0 for f in FEET}
    samples = {f: 0 for f in FEET}
    seen = set()
    for source in sources:
        sha = source.get('sha256')
        if not isinstance(sha, str) or re.fullmatch('[0-9a-f]{64}', sha) is None or sha in seen:
            raise ValueError('R5 source SHA missing or duplicated')
        seen.add(sha)
        z = reader.npz(source['path'], sha)
        if (z['format'].item() != RAW_FORMAT or
                z['producer'].item() != 'foothold_s2.eval.ex42_gait_contact' or
                z['contact_definition'].item() != 'norm_Fxyz_gt_1N' or
                z['foot_names'].tolist() != list(FEET) or
                z['window_seconds'].tolist() != [1, 6] or
                not math.isclose(float(z['dt']), .02, rel_tol=0, abs_tol=1e-9)):
            raise ValueError('R5 raw schema/foot order/contact definition differs')
        identity = json.loads(str(z['run_identity'].item()))
        if (identity.get('checkpoint_sha256') != checkpoint or type(identity.get('eval_seed')) is not int
                or identity['eval_seed'] != 42 or identity.get('mode') not in ('eval_gt', 'eval_pred')
                or re.fullmatch('[0-9a-f]{40}', identity.get('code_head', '')) is None):
            raise ValueError('R5 producer checkpoint/seed/mode identity differs')
        command = np.asarray(z['command'], dtype=float)
        if (command.shape != (3,) or not np.isfinite(command).all() or command[2] != 0
                or not .1 <= np.linalg.norm(command[:2]) <= .3):
            raise ValueError('R5 source is not a slow translation trial')
        force = np.asarray(z['force_xyz_n'], dtype=float)
        height = np.asarray(z['foot_height_m'], dtype=float)
        speed = np.asarray(z['foot_xy_speed_mps'], dtype=float)
        alive, contact = z['alive'], z['contact']
        if (force.shape != (300, 64, 4, 3) or height.shape != (300, 64, 4)
                or speed.shape != height.shape or alive.shape != (300, 64)
                or contact.shape != height.shape or alive.dtype != bool or contact.dtype != bool
                or not np.isfinite(force).all() or not np.isfinite(height).all()
                or not np.isfinite(speed).all() or (speed < 0).any()
                or not np.array_equal(alive, np.arange(300)[:, None] < alive.sum(0)[None, :])):
            raise ValueError('R5 raw per-foot sample shape/finite/alive contract differs')
        raw_contact = np.linalg.norm(force, axis=-1) > 1.0
        if not np.array_equal(contact, raw_contact):
            raise ValueError('R5 contact mask differs from norm(Fxyz)>1N')
        # Only complete contact -> flight -> contact intervals inside [1,6) s.
        valid = alive[50:300]
        for i, foot in enumerate(FEET):
            c = raw_contact[50:300, :, i]
            h, v = height[50:300, :, i], speed[50:300, :, i]
            heights[foot].extend(h[valid & ~c].tolist())
            drag[foot] += int((valid & c & (h < .02) & (v > .05)).sum())
            samples[foot] += int(valid.sum())
            for env in range(64):
                mask = c[:int(valid[:, env].sum()), env]
                start = None
                for t in range(1, len(mask)):
                    if mask[t-1] and not mask[t]:
                        start = t
                    elif not mask[t-1] and mask[t] and start is not None:
                        intervals[foot].append((t-start)*.02)
                        contributors[foot].add(env)
                        start = None
    result = {}
    for foot in FEET:
        air = np.asarray(intervals[foot])
        if not len(air) or not heights[foot] or not samples[foot]:
            raise ValueError('R5 complete per-foot intervals or height samples absent: '+foot)
        result[foot] = dict(complete_intervals=len(air), contributing_envs=len(contributors[foot]),
                            single_sample_fraction=float(np.mean(air == .02)),
                            height_median_m=float(np.median(heights[foot])),
                            drag_fraction=drag[foot]/samples[foot],
                            negative_fraction_at_0p5=float(np.mean(air < .5)))
    return result
