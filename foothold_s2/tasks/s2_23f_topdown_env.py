"""SOL-23f TopDown의 8x4 side table을 첫 reset 전에 묶는다."""

import copy
import numpy as np
import torch

from isaaclab.envs import ManagerBasedRLEnv

from foothold_s2.curriculum.terrain_levels_mixed import attach_s2_tables
from foothold_s2.terrains import sol23f_topdown
from foothold_s2.terrains.s2_layout import Layout


class FootholdS223FTopDownEnv(ManagerBasedRLEnv):
    def foothold_state_dict(self):
        # terrain_levels_s2 creates this generator lazily with seed 0.
        if not hasattr(self, "_s2_rng"):
            self._s2_rng = np.random.default_rng(0)
        return {"s2_rng_state": copy.deepcopy(self._s2_rng.bit_generator.state)}

    def foothold_load_state_dict(self, state):
        if "s2_rng_state" not in state:
            raise ValueError("TopDown checkpoint missing curriculum RNG state")
        rng = np.random.default_rng()
        rng.bit_generator.state = copy.deepcopy(state["s2_rng_state"])
        self._s2_rng = rng

    def __init__(self, cfg, render_mode=None, **kwargs):
        sol23f_topdown.SIDE_TABLE.__init__()
        super().__init__(cfg, render_mode=render_mode, **kwargs)
        layout = Layout(sol23f_topdown.PROPORTIONS, sol23f_topdown.NUM_COLS)
        attach_s2_tables(self, sol23f_topdown.SIDE_TABLE, layout)
        terrain = self.scene.terrain
        ids = torch.arange(self.num_envs, device=self.device)
        initial = terrain.terrain_types.clone()
        non_gap = layout.group_by_col[initial.cpu().numpy()] != "gap"
        eligible = ids[torch.as_tensor(non_gap, device=self.device)]
        rng = np.random.default_rng(int(cfg.seed))
        choice = rng.choice(layout.easy_cols, size=len(eligible))
        terrain.terrain_types[eligible] = torch.as_tensor(choice, device=self.device, dtype=initial.dtype)
        terrain.env_origins[eligible] = terrain.terrain_origins[
            terrain.terrain_levels[eligible], terrain.terrain_types[eligible]]
        print("TOPDOWN_INITIAL_TERRAIN " + str({
            "gap_envs": int((~non_gap).sum()), "low_flat_envs": int(non_gap.sum()),
            "num_cols": layout.num_cols, "num_rows": sol23f_topdown.NUM_ROWS,
        }), flush=True)
