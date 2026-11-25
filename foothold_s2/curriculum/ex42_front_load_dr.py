"""F1 front-load DR (lead 2026-11-25 20:23): a 0.3 ~ 0.4 kg load at the front of the trunk, which moves the CoM forward.
Off by default (EX42_FRONT_LOAD_DR unset or 0 registers nothing).

    EX42_FRONT_LOAD_DR=1
    EX42_FRONT_LOAD_DR_PARAMS="mass_lo=0.3,mass_hi=0.4,x=0.25,z=0.0"   (any subset; the rest keep DEFAULTS)

Per env, once at startup (after every other startup event, so after add_base_mass): draw m ~ U(mass_lo, mass_hi), add it to the
base body mass, scale the base inertia by the new / old mass ratio (the same approximation as Isaac Lab's
randomize_rigid_body_mass), and shift the base CoM by m * (p_load - c) / (M + m), p_load = (x, 0, z) in the base frame and c the
current base CoM. The base CoM is restored to a stored baseline on every reset by the EX-40 runtime event (ex40_base_com,
whose baseline can come from the parent checkpoint), so with that event the shift is added after it on the reset rows; without
it the shift is written once at startup. The EX-40 COM readback (offset from its baseline) is recorded before the shift, so
its range check is unchanged. Lines: EX42_FRONT_LOAD_DR where=start (params) and EX42_FRONT_LOAD_DR applied (realized mass and
CoM shift statistics). No Kit import at module level.
"""
from __future__ import annotations

import math
import os

import torch

ENV_SWITCH = "EX42_FRONT_LOAD_DR"
PARAMS_ENV = "EX42_FRONT_LOAD_DR_PARAMS"
DEFAULTS = {"mass_lo": 0.3, "mass_hi": 0.4, "x": 0.25, "z": 0.0}
TERM = "ex42_front_load"


def enabled() -> bool:
    value = os.environ.get(ENV_SWITCH, "")
    if value not in ("", "0", "1"):
        raise ValueError(f"{ENV_SWITCH} must be 0 or 1 (got {value!r})")
    if value != "1" and os.environ.get(PARAMS_ENV, ""):
        raise ValueError(f"{PARAMS_ENV} is set but {ENV_SWITCH} is not 1")
    return value == "1"


def params() -> dict:
    out = dict(DEFAULTS)
    for item in filter(None, (part.strip() for part in os.environ.get(PARAMS_ENV, "").split(","))):
        key, sep, raw = item.partition("=")
        if not sep or key.strip() not in out:
            raise ValueError(f"{PARAMS_ENV} unknown or malformed cell {item!r}")
        try:
            out[key.strip()] = float(raw)
        except ValueError:
            raise ValueError(f"{PARAMS_ENV} invalid number {item!r}") from None
    if (any(not math.isfinite(v) for v in out.values()) or not 0 < out["mass_lo"] <= out["mass_hi"] <= 2.0
            or not 0 < out["x"] <= 0.5 or abs(out["z"]) > 0.2):
        raise ValueError(f"{PARAMS_ENV} needs 0 < mass_lo <= mass_hi <= 2 kg, 0 < x <= 0.5 m, |z| <= 0.2 m")
    return out


def raw_env(env):
    return getattr(env, "unwrapped", env)


def com_shift(load_kg: torch.Tensor, mass_kg: torch.Tensor, com: torch.Tensor, x: float, z: float) -> torch.Tensor:
    """[N] load, [N] base mass before the load, [N, 3] base CoM -> [N, 3] CoM shift of the loaded base."""
    target = com.new_tensor((x, 0.0, z)).expand_as(com)
    return load_kg[:, None] * (target - com) / (mass_kg + load_kg)[:, None]


def apply_front_load(env, env_ids, asset_cfg, mass_lo, mass_hi, x, z):
    """Startup event: add the load to the base mass and inertia, keep the CoM shift on env for the reset wrapper."""
    asset = env.scene[asset_cfg.name]
    body = int(asset_cfg.body_ids[0]) if not isinstance(asset_cfg.body_ids, slice) else None
    if body is None or len(asset_cfg.body_ids) != 1:
        raise ValueError("EX42_FRONT_LOAD_DR needs exactly the base body")
    view = asset.root_physx_view
    n = env.scene.num_envs
    ids = torch.arange(n, device="cpu")
    masses = view.get_masses().clone()
    inertias = view.get_inertias().clone()
    coms = view.get_coms().clone()
    before = masses[:, body].clone()
    # own generator: the global torch RNG stream (and everything drawn after it) stays as without the switch
    seed = int(getattr(getattr(raw_env(env), "cfg", None), "seed", 0) or 0) + 7919 * (1 + int(os.environ.get("RANK", "0") or 0))
    load = mass_lo + (mass_hi - mass_lo) * torch.rand(n, generator=torch.Generator().manual_seed(seed))
    masses[:, body] = before + load
    inertias[:, body] = inertias[:, body] * (masses[:, body] / before)[:, None]
    shift = com_shift(load, before, coms[:, body, :3], x, z)
    view.set_masses(masses, ids)
    view.set_inertias(inertias, ids)
    raw = getattr(env, "unwrapped", env)
    raw._ex42_front_load_shift = shift.clone()
    raw._ex42_front_load_body = body
    if not getattr(raw, "_ex42_front_load_reset_owned", False):
        coms[:, body, :3] += shift
        view.set_coms(coms, ids)
    if int(os.environ.get("RANK", "0") or 0) == 0:
        print("EX42_FRONT_LOAD_DR applied envs=%d load_kg=[%.4f,%.4f] base_mass_kg=[%.3f,%.3f] com_dx_m=[%.5f,%.5f] "
              "com_dz_m=[%.5f,%.5f] com_path=%s" % (
                  n, float(load.min()), float(load.max()), float(masses[:, body].min()), float(masses[:, body].max()),
                  float(shift[:, 0].min()), float(shift[:, 0].max()), float(shift[:, 2].min()), float(shift[:, 2].max()),
                  "after_ex40_base_com_reset" if getattr(raw, "_ex42_front_load_reset_owned", False) else "startup"),
              flush=True)


def _after_reset_com(func):
    def reset(env, env_ids, **kwargs):
        func(env, env_ids, **kwargs)
        raw = getattr(env, "unwrapped", env)
        shift = getattr(raw, "_ex42_front_load_shift", None)
        if shift is None:
            raise ValueError("EX42_FRONT_LOAD_DR reset ran before its startup event")
        asset = env.scene[kwargs["asset_cfg"].name]
        rows = (torch.arange(env.scene.num_envs, device="cpu") if env_ids is None or isinstance(env_ids, slice)
                else torch.as_tensor(env_ids, dtype=torch.long, device="cpu").flatten())
        coms = asset.root_physx_view.get_coms().clone()
        coms[rows, raw._ex42_front_load_body, :3] += shift[rows]
        asset.root_physx_view.set_coms(coms, rows)
    reset.__wrapped__ = func
    reset.ex42_front_load = True
    return reset


class _ResetOwnedFlag:
    """Startup-mode marker run first: tells apply_front_load the CoM is written by the reset wrapper."""

    @staticmethod
    def mark(env, env_ids):
        getattr(env, "unwrapped", env)._ex42_front_load_reset_owned = True


def register(env_cfg, term_cfg_class=None, entity_cfg_class=None) -> bool:
    if not enabled():
        return False
    p = params()
    if term_cfg_class is None:
        from isaaclab.managers import EventTermCfg as term_cfg_class
    if entity_cfg_class is None:
        from isaaclab.managers import SceneEntityCfg as entity_cfg_class
    events = env_cfg.events
    if getattr(events, TERM, None) is not None:
        raise ValueError(f"{ENV_SWITCH} registered twice")
    reset_com = getattr(events, "ex40_base_com", None)
    if reset_com is not None:
        if getattr(reset_com.func, "ex42_front_load", False):
            raise ValueError(f"{ENV_SWITCH} wrapped ex40_base_com twice")
        reset_com.func = _after_reset_com(reset_com.func)
        setattr(events, TERM + "_reset_owned", term_cfg_class(func=_ResetOwnedFlag.mark, mode="startup", params={}))
    setattr(events, TERM, term_cfg_class(
        func=apply_front_load, mode="startup",
        params={"asset_cfg": entity_cfg_class("robot", body_names="base"), **p}))
    print("EX42_FRONT_LOAD_DR where=start mass_kg=[%g,%g] x_m=%g z_m=%g com_path=%s" % (
        p["mass_lo"], p["mass_hi"], p["x"], p["z"],
        "after_ex40_base_com_reset" if reset_com is not None else "startup"), flush=True)
    return True
