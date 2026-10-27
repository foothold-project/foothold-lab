"""In-scene overlay for the 25e recorder (lead, 10/25).

Draws with IsaacLab VisualizationMarkers so everything is rendered by Isaac Sim in the
same camera frame as the robot (not a 2D paste):
  - command / actual base velocity arrows: IsaacLab green (command) and blue (actual) arrows,
    same construction as UniformVelocityCommand._debug_vis_callback
  - yaw arcs above the body: green = commanded yaw rate, blue = actual yaw rate
  - foot trails attached to the feet (last 1.5 s), bigger dot while in contact
  - height scan points on the ground: GT map (gt_map_scan ray hits) white, reconstructed map
    (refined) orange at base_z + value; the map the policy did NOT use is drawn grey
  - foot scan points (foot_scan_0..3 ray hits) cyan
  - attention: top-k map tokens by last-layer attention of the prop token, red, size by weight
"""
from __future__ import annotations

import colorsys
from collections import deque
import copy
import math
from typing import Any

FOOT_COLORS = ((0.95, 0.25, 0.25), (1.0, 0.65, 0.1), (0.3, 0.85, 0.35), (0.75, 0.4, 0.95))
TRAIL_STEPS = 75
ATTN_TOPK = 16
MAP_X, MAP_Y = 32, 16
LEGEND = ("green arrow/arc = command  blue = actual  |  white dots = GT map  orange = reconstructed map  "
          "(grey = not used by policy)  |  cyan = foot scan  |  red = attention top16  |  trail = last 1.5 s")


def adjust_saturation(color: tuple[float, float, float], multiplier: float) -> tuple[float, float, float]:
    """Scale HSV saturation only, preserving the source hue and value."""
    if not math.isfinite(multiplier) or multiplier < 1.0 or multiplier > 1.5:
        raise ValueError("overlay saturation multiplier must be between 1.0 and 1.5")
    rgb = tuple(float(channel) for channel in color)
    if len(rgb) != 3 or any(not math.isfinite(channel) or not 0.0 <= channel <= 1.0 for channel in rgb):
        raise ValueError("overlay RGB channels must be finite values from 0 through 1")
    if multiplier == 1.0:
        return rgb
    hue, saturation, value = colorsys.rgb_to_hsv(*rgb)
    return tuple(colorsys.hsv_to_rgb(hue, min(1.0, saturation * multiplier), value))


def _sphere_cfg(path: str, protos: dict[str, tuple[float, tuple[float, float, float]]],
                saturation_multiplier: float = 1.0):
    import isaaclab.sim as sim_utils
    from isaaclab.markers import VisualizationMarkersCfg
    return VisualizationMarkersCfg(prim_path=path, markers={
        name: sim_utils.SphereCfg(radius=r, visual_material=sim_utils.PreviewSurfaceCfg(
            diffuse_color=adjust_saturation(c, saturation_multiplier),
            emissive_color=adjust_saturation(c, saturation_multiplier)))
        for name, (r, c) in protos.items()})


class SceneOverlay:
    def __init__(self, raw: Any, robot: Any, foot_ids: Any, perception: Any,
                 env_index: int = 0, saturation_multiplier: float = 1.0) -> None:
        import torch
        from isaaclab.markers import VisualizationMarkers
        from isaaclab.markers.config import BLUE_ARROW_X_MARKER_CFG, GREEN_ARROW_X_MARKER_CFG

        self.torch = torch
        self.raw, self.robot, self.foot_ids = raw, robot, foot_ids
        self.env_index = int(env_index)
        self.saturation_multiplier = float(saturation_multiplier)
        adjust_saturation((0.5, 0.5, 0.5), self.saturation_multiplier)
        self.device = robot.data.root_pos_w.device
        self.goal = VisualizationMarkers(self._saturated_marker_cfg(
            GREEN_ARROW_X_MARKER_CFG, "/Visuals/v25e/goal_vel"))
        self.cur = VisualizationMarkers(self._saturated_marker_cfg(
            BLUE_ARROW_X_MARKER_CFG, "/Visuals/v25e/cur_vel"))
        self.arrow_scale = tuple(GREEN_ARROW_X_MARKER_CFG.markers["arrow"].scale)
        self.arcs = VisualizationMarkers(_sphere_cfg("/Visuals/v25e/yaw_arcs", {
            "cmd": (0.005, (0.1, 0.9, 0.2)), "act": (0.005, (0.15, 0.35, 1.0))},
            self.saturation_multiplier))
        self.trail = VisualizationMarkers(_sphere_cfg("/Visuals/v25e/foot_trail", {
            f"f{i}": (0.002, c) for i, c in enumerate(FOOT_COLORS)}, self.saturation_multiplier))
        self.maps = VisualizationMarkers(_sphere_cfg("/Visuals/v25e/map_points", {
            "gt": (0.003, (0.2, 1.0, 0.3)), "pred": (0.0019, (0.25, 0.6, 1.0)),
            "gt_off": (0.003, (0.2, 1.0, 0.3)), "pred_off": (0.0019, (0.25, 0.6, 1.0)),
            "foot": (0.0026, (1.0, 0.9, 0.05)), "err": (0.0022, (1.0, 0.12, 0.12))},
            self.saturation_multiplier))
        # GT = green dots, reconstructed = blue wireframe (rows and columns of the 32x16 grid),
        # red vertical sticks where |reconstructed - GT| > 2 cm, foot scan = yellow dots  # used / unused drawn the same; HUD says which map the policy used
        self.attn = VisualizationMarkers(_sphere_cfg("/Visuals/v25e/attention", {
            "a": (0.008, (1.0, 0.28, 0.0))}, self.saturation_multiplier))
        # 10/25 lead review: map points / foot scan / attention dots clutter the scene.
        # They move to the 2D map panel (compose_25e.py); the scene keeps arrows, arcs, footprints.
        self.attn_rows: list = []
        self.history: deque = deque(maxlen=TRAIL_STEPS)
        self.attn_store: dict[str, Any] = {}
        self.gt_check: list[float] = []
        self.attn_hook_ok = False
        ie = getattr(perception, "ie", None)
        self.map_visible = bool(ie is not None and getattr(ie, "use_map", False)
                                and not getattr(ie, "mask_map_tokens", False))
        if ie is not None and getattr(ie, "use_map", False):
            torch.backends.mha.set_fastpath_enabled(False)
            layer = ie.attn.layers[-1]
            original = layer.self_attn.forward
            store = self.attn_store

            def forward(query, key, value, *args, **kwargs):
                kwargs["need_weights"] = True
                kwargs["average_attn_weights"] = True
                out, weights = original(query, key, value, *args, **kwargs)
                store["w"] = weights.detach()
                return out, weights

            layer.self_attn.forward = forward
            self.attn_hook_ok = True

    def _saturated_marker_cfg(self, cfg: Any, prim_path: str) -> Any:
        """Copy a marker config and adjust its authored diffuse/emissive colors."""
        result = copy.deepcopy(cfg)
        result.prim_path = prim_path
        for marker in result.markers.values():
            material = getattr(marker, "visual_material", None)
            if material is None:
                continue
            for name in ("diffuse_color", "emissive_color"):
                color = getattr(material, name, None)
                if color is not None:
                    setattr(material, name, adjust_saturation(tuple(color), self.saturation_multiplier))
        return result

    def record_step(self, foot_xyz: Any, contact: Any) -> None:
        self.history.append((foot_xyz.copy(), contact.copy()))
        w = self.attn_store.get("w")
        if w is not None and w.shape[-1] == 1 + (MAP_X // 2) * (MAP_Y // 2):
            self.attn_rows.append([round(float(v), 5) for v in w[self.env_index, 0, 1:].tolist()])
        else:
            self.attn_rows.append(None)

    def _yaw(self) -> float:
        import math
        w, x, y, z = self.robot.data.root_quat_w[self.env_index].tolist()
        return math.atan2(2 * (w * z + x * y), 1 - 2 * (y * y + z * z))

    def _arc(self, center: Any, yaw: float, rate: float, radius: float) -> list[list[float]]:
        import math
        span = max(-2.4, min(2.4, rate * 1.2))
        n = 40
        return [[center[0] + radius * math.cos(yaw + span * k / (n - 1)),
                 center[1] + radius * math.sin(yaw + span * k / (n - 1)), center[2]] for k in range(n)]

    def draw(self, command: Any, map_snapshot: dict[str, Any]) -> dict[str, Any]:
        import numpy as np
        import isaaclab.utils.math as math_utils
        torch = self.torch
        dev = self.device
        info: dict[str, Any] = {}
        base = self.robot.data.root_pos_w[self.env_index:self.env_index + 1].clone()
        quat = self.robot.data.root_quat_w[self.env_index:self.env_index + 1]
        top = base.clone()
        top[:, 2] += 0.5

        def arrow(xy):
            s = torch.tensor(self.arrow_scale, device=dev).repeat(1, 1)
            s[:, 0] *= torch.linalg.norm(xy, dim=1) * 3.0
            heading = torch.atan2(xy[:, 1], xy[:, 0])
            z = torch.zeros_like(heading)
            q = math_utils.quat_mul(quat, math_utils.quat_from_euler_xyz(z, z, heading))
            return s, q

        cmd_t = torch.tensor([list(command[:2])], device=dev, dtype=torch.float32)
        s, q = arrow(cmd_t)
        self.goal.visualize(top, q, s)
        s, q = arrow(self.robot.data.root_lin_vel_b[self.env_index:self.env_index + 1, :2])
        self.cur.visualize(top, q, s)

        yaw = self._yaw()
        c = base[0].tolist()
        c[2] += 0.30
        pts = self._arc(c, yaw, float(command[2]), 0.24) + self._arc(c, yaw, float(self.robot.data.root_ang_vel_b[self.env_index, 2]), 0.30)
        idx = [0] * 40 + [1] * 40
        scl = [[1.0] * 3] * 39 + [[2.6] * 3] + [[1.0] * 3] * 39 + [[2.6] * 3]
        self.arcs.visualize(torch.tensor(pts, device=dev), marker_indices=torch.tensor(idx, device=dev),
                            scales=torch.tensor(scl, device=dev))

        if self.history:
            tp, ti, ts = [], [], []
            hist = list(self.history)
            for k, (feet, contact) in enumerate(hist):
                nxt = hist[k + 1][0] if k + 1 < len(hist) else feet
                for f in range(4):
                    for a in (0.0, 0.34, 0.67):  # interpolate so the dots read as a thin line
                        p = (feet[f] * (1 - a) + nxt[f] * a).tolist()
                        p[2] = p[2] - 0.018
                        tp.append(p)
                        ti.append(f)
                        ts.append([1.4] * 3 if (contact[f] and a == 0.0) else [1.0] * 3)
            if not tp:
                tp, ti, ts = [[0.0, 0.0, -50.0]], [0], [[0.01] * 3]
            self.trail.visualize(torch.tensor(tp, device=dev), marker_indices=torch.tensor(ti, device=dev),
                                 scales=torch.tensor(ts, device=dev))

        if not self.map_visible:
            info["used_gt"] = bool(map_snapshot.get("use_gt", False)) if map_snapshot else False
            info["policy_map_tokens"] = "masked_or_absent"
            return info

        sensors = self.raw.scene.sensors
        hits = sensors["gt_map_scan"].data.ray_hits_w[self.env_index].detach()
        valid = torch.isfinite(hits).all(dim=1)
        base_z = float(base[0, 2])
        used_gt = bool(map_snapshot.get("use_gt", True)) if map_snapshot else True
        mp, mi = [hits[valid] + torch.tensor([0.0, 0.0, 0.006], device=dev)], [torch.full((int(valid.sum()),), 0 if used_gt else 2, device=dev)]  # 0 gt, 2 gt_off
        if map_snapshot and map_snapshot.get("gt_map") is not None and np.asarray(map_snapshot["gt_map"]).size == MAP_X * MAP_Y:
            gt_obs = np.asarray(map_snapshot["gt_map"], dtype=np.float32).reshape(-1)
            rel = np.clip((hits[:, 2] - base_z).cpu().numpy(), -1.0, 1.0)
            ok = np.isfinite(rel)
            if ok.any():
                self.gt_check.append(float(np.abs(rel[ok] - gt_obs[ok]).max()))
        refined = map_snapshot.get("refined_map") if map_snapshot else None
        if refined is not None and np.asarray(refined).size == MAP_X * MAP_Y:
            pz = torch.tensor(np.asarray(refined, dtype=np.float32).reshape(-1), device=dev) + base_z
            pred = hits.clone()
            pred[:, 2] = pz
            g3 = pred.reshape(MAP_X, MAP_Y, 3)
            wires = []
            for a in (0.0, 0.25, 0.5, 0.75):
                wires.append((g3[:-1] * (1 - a) + g3[1:] * a).reshape(-1, 3))        # lines along x
                wires.append((g3[:, :-1] * (1 - a) + g3[:, 1:] * a).reshape(-1, 3))  # lines along y
            wire = torch.cat(wires)
            wire = wire[torch.isfinite(wire).all(dim=1)] + torch.tensor([0.0, 0.0, 0.006], device=dev)
            mp.append(wire)
            mi.append(torch.full((len(wire),), 1, device=dev))
            diff = pz - hits[:, 2]
            bad = valid & torch.isfinite(diff) & (diff.abs() > 0.02)
            if bool(bad.any()):
                sticks = []
                for a in torch.linspace(0, 1, 6, device=dev):
                    q = hits[bad].clone()
                    q[:, 2] = hits[bad, 2] + a * diff[bad]
                    sticks.append(q)
                mp.append(torch.cat(sticks) + torch.tensor([0.0, 0.0, 0.006], device=dev))
                mi.append(torch.full((6 * int(bad.sum()),), 5, device=dev))
            info["recon_err_cells_over_2cm"] = int(bad.sum())
        for i in range(4):
            fh = sensors[f"foot_scan_{i}"].data.ray_hits_w[self.env_index].detach()
            fv = torch.isfinite(fh).all(dim=1)
            mp.append(fh[fv] + torch.tensor([0.0, 0.0, 0.004], device=dev))
            mi.append(torch.full((int(fv.sum()),), 4, device=dev))
        self.maps.visualize(torch.cat(mp), marker_indices=torch.cat(mi))

        w = self.attn_store.get("w")
        if w is not None and w.shape[-1] == 1 + (MAP_X // 2) * (MAP_Y // 2):
            row = w[self.env_index, 0, 1:]
            k = min(ATTN_TOPK, row.numel())
            vals, tok = torch.topk(row, k)
            grid = hits.reshape(MAP_X, MAP_Y, 3)
            centers = []
            for t in tok.tolist():
                i, j = divmod(t, MAP_Y // 2)
                cell = grid[2 * i:2 * i + 2, 2 * j:2 * j + 2].reshape(-1, 3)
                cell = cell[torch.isfinite(cell).all(dim=1)]
                centers.append(cell.mean(dim=0) if len(cell) else base[0])
            cpos = torch.stack(centers) + torch.tensor([0.0, 0.0, 0.03], device=dev)
            sc = (0.5 + 1.0 * vals / vals.max().clamp_min(1e-9)).unsqueeze(1).repeat(1, 3)
            self.attn.visualize(cpos, scales=sc)
            info["attn_top_weight"] = float(vals[0])
            info["attn_prop_self"] = float(w[self.env_index, 0, 0])
        info["used_gt"] = used_gt
        return info
