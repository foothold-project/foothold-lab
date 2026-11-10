"""P4-2 reset-only orientation diagnostics. Never changes yaw or commands."""
import torch

from foothold_s2.terrains.generator_columns import generator_column_names

STAIRS = ('pyramid_stairs', 'pyramid_stairs_inv', 'stage_stairs')
EDGES_DEG = (0., 15., 45., 75., 90.)


class StairStartHistogram:
    """Cumulative physical reset samples since process start, map independent.

    yaw modulo pi/2 measures orientation relative to the axis-aligned stair
    faces, not which face is physically closest to an off-centre robot.
    Unfolded yaw counts are also kept so fourfold folding cannot hide bias.
    """
    def __init__(self, device):
        self.device = device
        self.counts = torch.zeros(3, 4, device=device, dtype=torch.int64)
        self.yaw_counts = torch.zeros(3, 12, device=device, dtype=torch.int64)
        self.invalid = torch.zeros(3, device=device, dtype=torch.int64)
        self.resets_seen = 0
        self.unclassified = 0

    def add(self, yaw_rad, kind_ids):
        require_shape = yaw_rad.ndim == 1 and kind_ids.shape == yaw_rad.shape
        if not require_shape:
            raise ValueError('stair histogram input shape differs')
        self.resets_seen += yaw_rad.numel()
        self.unclassified += int(((kind_ids < -1) | (kind_ids >= len(STAIRS))).sum())
        finite = torch.isfinite(yaw_rad)
        # bucketize right=True gives [lower, upper); exact 90 folds to zero.
        folded = torch.remainder(yaw_rad.to(torch.float64), torch.pi / 2)
        # Keep the comparison in radians. Converting exact 15deg back to
        # degrees can round down and put a boundary sample in the wrong bin.
        edges = torch.deg2rad(folded.new_tensor(EDGES_DEG[1:-1]))
        bins = torch.bucketize(folded, edges, right=True)
        raw = torch.remainder(yaw_rad.to(torch.float64) + torch.pi, 2 * torch.pi)
        raw_bins = torch.floor(raw / (torch.pi / 6)).long().clamp(0, 11)
        for i in range(3):
            mask = kind_ids == i
            valid = mask & finite
            self.invalid[i] += (mask & ~finite).sum()
            self.counts[i] += torch.bincount(bins[valid], minlength=4)
            self.yaw_counts[i] += torch.bincount(raw_bins[valid], minlength=12)

    def snapshot(self):
        return {'schema': 'ex41-stair-start-angle/1', 'record_only': True,
                'scope': 'physical_reset_events_since_process_start',
                'definition': 'yaw modulo 90deg relative to axis-aligned stair faces; not nearest-face selection',
                'bins_deg': list(EDGES_DEG), 'uniform_expected_fraction': [1/6, 1/3, 1/3, 1/6],
                'unfolded_yaw_edges_deg': list(range(-180, 181, 30)),
                'resets_seen': self.resets_seen, 'unclassified': self.unclassified,
                'sample_count': int(self.counts.sum()),
                'status': 'measured' if int(self.counts.sum()) else 'no_stair_reset_samples',
                'by_terrain': {name: {'counts': self.counts[i].cpu().tolist(),
                    'yaw_counts': self.yaw_counts[i].cpu().tolist(), 'invalid_yaw': int(self.invalid[i])}
                    for i, name in enumerate(STAIRS)}}


def record_reset(env, env_ids):
    """Called by the reset event after reset_base; not by quarantine cache clear."""
    terrain = env.scene.terrain
    cfg = terrain.cfg.terrain_generator
    if not hasattr(env, '_ex41_stair_hist'):
        env._ex41_stair_hist = StairStartHistogram(env.device)
    hist = env._ex41_stair_hist
    if cfg.curriculum is not True:
        env._ex41_stair_hist_error = 'column types unavailable without curriculum tile manifest'
        return
    # The generated terrain config is immutable during this run. Resolve by
    # actual terrain names, not hard-coded env/column numbers.
    if not hasattr(env, '_ex41_stair_columns'):
        names = generator_column_names(cfg)
        env._ex41_stair_columns = torch.tensor([STAIRS.index(n) if n in STAIRS else -1 for n in names],
                                               device=env.device, dtype=torch.long)
    ids = torch.arange(env.num_envs, device=env.device) if env_ids is None else env_ids
    cols = terrain.terrain_types[ids]
    table = env._ex41_stair_columns
    valid_col = torch.isfinite(cols) & (cols == cols.long()) & (cols >= 0) & (cols < len(table))
    safe_col = torch.where(valid_col, cols, torch.zeros_like(cols)).long()
    kinds = torch.where(valid_col, table[safe_col], torch.full_like(safe_col, -2))
    q = env.scene['robot'].data.root_quat_w[ids].to(torch.float64)
    good_q = torch.isfinite(q).all(-1) & ((q.square().sum(-1) - 1.).abs() < 1e-3)
    yaw = torch.atan2(2*(q[:, 0]*q[:, 3]+q[:, 1]*q[:, 2]), 1-2*(q[:, 2].square()+q[:, 3].square()))
    hist.add(torch.where(good_q, yaw, torch.full_like(yaw, float('nan'))), kinds)


def snapshot(env):
    hist = getattr(env, '_ex41_stair_hist', None)
    out = (hist or StairStartHistogram('cpu')).snapshot()
    if hasattr(env, '_ex41_stair_hist_error'):
        out['error'] = env._ex41_stair_hist_error
    return out
