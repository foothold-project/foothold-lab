"""촬영 화풍(조명 · 채도 · 이름) 한 곳. 팀장 확정(RULES-HUB 4 절, 10/27 01:1x 「1.25로 확정」 「L4 좋다」)을 값 하나로 두고 모든 기록기가 이 파일에서 기본값을 가져온다.
값의 출처: runner-26a/inbox/jay/20261023-experiments/runner-26a/record_25e_l4sat125_26m.py STYLE_ARGS.
다른 화풍(inherit 등)은 --allow-unapproved-style 을 줄 때만 허용하고, 영수증 style 에 UNAPPROVED 로 남는다. 합성기 · 프레임 검사 · seq_video 검증은 require_approved 로 그런 영수증을 실패로 끝낸다.
이 파일은 import 시 표준 라이브러리만 쓴다(Kit 은 조명을 실제로 적용하는 함수 안에서만 불러온다). 기록기는 파일 경로로 불러온다(load_video_style 예시는 아래 LOADER_SNIPPET)."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from typing import Any

APPROVED_STYLE = {
    "lighting_profile": "dome_plus_three_point",
    "dome_intensity": 0.05,
    "three_point_intensity": 100.0,
    "three_point_angle_deg": 12.0,
    "three_point_elevation_deg": 45.0,
    "three_point_shadows": True,
    "overlay_saturation": 1.25,
}
LABEL = "L4_sat125"
STYLE_ID = LABEL + "_" + hashlib.sha256(json.dumps(APPROVED_STYLE, sort_keys=True).encode()).hexdigest()[:8]
APPROVED_STYLE_IDS = (STYLE_ID,)
# runner-26a STYLE_ARGS 와 같은 값(명령줄로 넘길 때)
STYLE_ARGS = ("--lighting-profile", "dome_plus_three_point", "--dome-intensity", "0.05", "--three-point-intensity", "100",
              "--three-point-angle-deg", "12", "--three-point-elevation-deg", "45", "--three-point-shadows", "--overlay-saturation", "1.25")
# 기록기는 이 파일을 아래 세 줄로 불러온다(파일 위치 기준이라 cwd 의 다른 foothold_s2 사본과 섞이지 않는다; video25/ 안의 기록기는 parent.parent):
#   import importlib.util as _u, pathlib as _p
#   _s = _u.spec_from_file_location("video_style", _p.Path(__file__).resolve().parent / "video_style.py")
#   video_style = _u.module_from_spec(_s); _s.loader.exec_module(video_style)
NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9.-]*-[a-z0-9]+_[A-Za-z0-9_+-]+_L[0-9]+_env[0-9]+-m[0-9]+-[a-z0-9_]+-1x$")


def add_style_args(parser: argparse.ArgumentParser) -> None:
    """조명 · 채도 인자와 --allow-unapproved-style. 기본값은 승인 화풍."""
    A = APPROVED_STYLE
    parser.add_argument("--lighting-profile", choices=("inherit", "current_plus_directional", "three_point", "dome", "dome_plus_three_point"), default=A["lighting_profile"])
    parser.add_argument("--directional-light-intensity", type=float)
    parser.add_argument("--directional-light-angle-deg", type=float, default=1.0)
    parser.add_argument("--directional-light-azimuth-deg", type=float, default=45.0)
    parser.add_argument("--directional-light-elevation-deg", type=float, default=45.0)
    parser.add_argument("--directional-light-shadows", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--three-point-intensity", type=float, default=A["three_point_intensity"])
    parser.add_argument("--three-point-angle-deg", type=float, default=A["three_point_angle_deg"])
    parser.add_argument("--three-point-elevation-deg", type=float, default=A["three_point_elevation_deg"])
    parser.add_argument("--three-point-shadows", action=argparse.BooleanOptionalAction, default=A["three_point_shadows"])
    parser.add_argument("--dome-intensity", type=float, default=A["dome_intensity"])
    parser.add_argument("--overlay-saturation", type=float, choices=(1.0, 1.25, 1.5), default=A["overlay_saturation"],
                        help="바닥 정보 그래픽(overlay 마커)만의 채도 배수. 기록기에 그런 그래픽이 없으면 기록만 한다")
    parser.add_argument("--allow-unapproved-style", action="store_true", help="승인 화풍이 아닌 값을 허용한다(영수증 style.approved=false)")


def _values(args: Any) -> dict:
    return {"lighting_profile": args.lighting_profile, "dome_intensity": args.dome_intensity,
            "three_point_intensity": args.three_point_intensity, "three_point_angle_deg": args.three_point_angle_deg,
            "three_point_elevation_deg": args.three_point_elevation_deg, "three_point_shadows": bool(args.three_point_shadows),
            "overlay_saturation": args.overlay_saturation}


def resolve_style(args: Any, parser: argparse.ArgumentParser | None = None) -> dict:
    """인자 값을 승인 화풍과 대조해 영수증용 style 기록을 만든다. 다르고 허용 인자가 없으면 거절."""
    vals = _values(args)
    approved = all(vals[k] == v for k, v in APPROVED_STYLE.items())
    allow = bool(getattr(args, "allow_unapproved_style", False))
    if not approved and not allow:
        msg = "승인 화풍(%s)이 아닌 조명 · 채도 값: %s. 정말 필요하면 --allow-unapproved-style" % (STYLE_ID, {k: vals[k] for k in vals if vals[k] != APPROVED_STYLE[k]})
        if parser is not None:
            parser.error(msg)
        raise ValueError(msg)
    sid = STYLE_ID if approved else "UNAPPROVED_" + hashlib.sha256(json.dumps(vals, sort_keys=True).encode()).hexdigest()[:8]
    return {"style_id": sid, "approved": approved, "values": vals, "approved_values": APPROVED_STYLE}


def require_approved(meta: dict, where: str = "") -> dict:
    """영수증 · review.json 의 style.style_id 가 승인 값이 아니면(없으면 포함) ValueError. 합성기 · 프레임 검사 · seq_video 검증이 부른다."""
    style = (meta or {}).get("style") if isinstance(meta, dict) else None
    sid = style.get("style_id") if isinstance(style, dict) else (meta or {}).get("style_id") if isinstance(meta, dict) else None
    if sid not in APPROVED_STYLE_IDS:
        raise ValueError("%s style_id %r 가 승인 화풍 %s 가 아니다" % (where or "receipt", sid, APPROVED_STYLE_IDS))
    return style if isinstance(style, dict) else {"style_id": sid}


def video_name(canon_label: str, set_kind: str, level: int, env: int, iteration: int, segment: str = "seq", speed: str = "1x") -> str:
    """<정본>-<지형종류>_L<레벨>_env<번호>-m<회차>-<구간>-<배속> (확장자 없음). 성공 · 실패 낱말을 넣지 않는다."""
    name = "%s-%s_L%d_env%d-m%d-%s-%s" % (canon_label, set_kind, int(level), int(env), int(iteration), segment, speed)
    if not NAME_RE.match(name) or re.search(r"success|fail|fell", name, re.I):
        raise ValueError("규칙 이름이 아니다: %r" % name)
    return name


# ---- 아래는 record_25e_x31.py 에서 옮긴 조명 적용 코드(그대로, 이름 유지) ----
def lighting_profile_settings(profile: str = "inherit", *, intensity: float | None = None,
                              angle_deg: float = 1.0, azimuth_deg: float = 45.0,
                              elevation_deg: float = 45.0, shadows: bool = True,
                              three_point_intensity: float | None = None,
                              three_point_angle_deg: float = 12.0,
                              three_point_elevation_deg: float = 45.0,
                              three_point_shadows: bool = True,
                              dome_intensity: float | None = None) -> dict[str, Any]:
    """Validate inherited, three-point, dome, or mixed scene lighting candidates."""
    supported = ("inherit", "current_plus_directional", "three_point", "dome",
                 "dome_plus_three_point")
    if profile not in supported:
        raise ValueError("lighting profile must be one of " + ", ".join(supported))
    reference = {"inherit_probe_mean_rgb8": 76.1, "v2_flat_probe_mean_rgb8": 183.0,
                 "sun_5000_shadows_on_probe_mean_rgb8": 224.9,
                 "sun_5000_shadows_off_probe_mean_rgb8": 222.3,
                 "target_probe_mean_rgb8": 150.0,
                 "target_scope": "between inherit and v2_flat; do not infer from intensity alone"}
    if profile == "inherit":
        if intensity is not None or three_point_intensity is not None or dome_intensity is not None:
            raise ValueError("light intensities require a non-inherit profile")
        return {"profile": "inherit", "explicit_directional_light": False,
                "brightness_calibration": "not_requested", "brightness_reference": reference}
    if profile == "current_plus_directional":
        if intensity is None or not math.isfinite(float(intensity)) or float(intensity) <= 0:
            raise ValueError("current_plus_directional requires a positive explicit intensity")
        if not math.isfinite(float(angle_deg)) or not 0.0 <= float(angle_deg) <= 180.0:
            raise ValueError("directional angle must be from 0 through 180 degrees")
        if not math.isfinite(float(azimuth_deg)) or not math.isfinite(float(elevation_deg)):
            raise ValueError("direction angles must be finite")
        if not 0.0 < float(elevation_deg) < 90.0:
            raise ValueError("directional source elevation must be between 0 and 90 degrees")
        return {"profile": profile, "explicit_directional_light": True,
                "intensity": float(intensity), "angle_deg": float(angle_deg),
                "azimuth_deg": float(azimuth_deg), "elevation_deg": float(elevation_deg),
                "shadows": bool(shadows), "brightness_calibration": "pending_still_review",
                "brightness_reference": reference}

    needs_three_point = profile in ("three_point", "dome_plus_three_point")
    needs_dome = profile in ("dome", "dome_plus_three_point")
    tp_intensity = (50.0 if three_point_intensity is None else float(three_point_intensity))
    dom_intensity = (0.05 if dome_intensity is None else float(dome_intensity))
    if needs_three_point and (not math.isfinite(tp_intensity) or tp_intensity <= 0):
        raise ValueError("three-point intensity must be positive and finite")
    if needs_dome and (not math.isfinite(dom_intensity) or dom_intensity <= 0):
        raise ValueError("dome intensity must be positive and finite")
    if not math.isfinite(float(three_point_angle_deg)) or not 0.0 <= float(three_point_angle_deg) <= 180.0:
        raise ValueError("three-point angle must be from 0 through 180 degrees")
    if not math.isfinite(float(three_point_elevation_deg)) or not 0.0 < float(three_point_elevation_deg) < 90.0:
        raise ValueError("three-point elevation must be between 0 and 90 degrees")
    return {"profile": profile, "explicit_directional_light": needs_three_point,
            "three_point": ({"count": 3, "intensity": tp_intensity, "angle_deg": float(three_point_angle_deg),
                             "azimuths_deg": [45.0, 165.0, 285.0],
                             "elevation_deg": float(three_point_elevation_deg),
                             "shadows": bool(three_point_shadows)} if needs_three_point else None),
            "dome": ({"intensity": dom_intensity} if needs_dome else None),
            "brightness_calibration": "pending_still_review",
            "brightness_reference": reference}


def apply_lighting_to_stage(stage: Any, profile: dict[str, Any]) -> dict[str, Any]:
    """Apply the selected lights to a USD stage without requiring Kit for CPU tests."""
    if profile.get("profile") == "inherit":
        return dict(profile)
    from pxr import Gf, Sdf, UsdGeom, UsdLux

    profile_name = profile.get("profile")
    if profile_name == "current_plus_directional":
        profile = dict(profile)
        profile["three_point"] = {"count": 1, "intensity": float(profile["intensity"]),
                                  "angle_deg": float(profile["angle_deg"]),
                                  "azimuths_deg": [float(profile["azimuth_deg"])],
                                  "elevation_deg": float(profile["elevation_deg"]),
                                  "shadows": bool(profile["shadows"])}
        profile["dome"] = None

    created = []
    dome_cfg = profile.get("dome")
    if dome_cfg:
        path = Sdf.Path("/World/RunnerDomeLight")
        dome = UsdLux.DomeLight.Define(stage, path)
        dome.CreateIntensityAttr(float(dome_cfg["intensity"]))
        created.append({"prim_path": str(path), "type": "DomeLight",
                        "intensity": float(dome_cfg["intensity"])})
    three = profile.get("three_point")
    if three:
        directions = []
        for index, azimuth in enumerate(three["azimuths_deg"], start=1):
            if profile_name == "current_plus_directional":
                path = Sdf.Path("/World/RunnerDirectionalLight")
            else:
                path = Sdf.Path(f"/World/RunnerThreePointLight_{index}")
            light = UsdLux.DistantLight.Define(stage, path)
            light.CreateIntensityAttr(float(three["intensity"]))
            light.CreateAngleAttr(float(three["angle_deg"]))
            shadow_api = UsdLux.ShadowAPI.Apply(light.GetPrim())
            shadow_api.CreateShadowEnableAttr(bool(three["shadows"]))
            az = math.radians(float(azimuth))
            el = math.radians(float(three["elevation_deg"]))
            source = Gf.Vec3d(math.cos(el) * math.cos(az),
                              math.cos(el) * math.sin(az), math.sin(el))
            rays = -source
            rotation = Gf.Rotation(Gf.Vec3d(0.0, 0.0, -1.0), rays)
            xform = UsdGeom.Xformable(light.GetPrim())
            xform.ClearXformOpOrder()
            xform.AddOrientOp().Set(Gf.Quatf(rotation.GetQuat()))
            directions.append({"prim_path": str(path), "azimuth_deg": float(azimuth),
                               "source_xyz": list(source), "rays_xyz": list(rays)})
            created.append({"prim_path": str(path), "type": "DistantLight",
                            "intensity": float(three["intensity"]),
                            "angle_deg": float(three["angle_deg"]), "shadows": bool(three["shadows"])})
    return dict(profile, prims=created, brightness_calibration="pending_still_review")


def hide_nonselected_robot_roots(stage: Any, robot_prim_template: str,
                                selected_env_id: int, expected_env_count: int, keep_env_ids=()) -> dict[str, Any]:
    """Hide non-selected cloned robot visuals using USD visibility only.

    The articulated robots, sensors, terrain and policy environment remain in
    the stage. Only the root Imageable visibility attribute is authored.
    """
    from pxr import UsdGeom

    template = str(robot_prim_template).replace("{ENV_REGEX_NS}", "/World/envs/env_.*")
    if "env_.*" not in template:
        raise ValueError(f"robot prim template has no env namespace wildcard: {template}")
    prefix, suffix = template.split("env_.*", 1)
    pattern = re.compile(r"^" + re.escape(prefix) + r"env_(\d+)" + re.escape(suffix) + r"$")
    roots: dict[int, Any] = {}
    for prim in stage.Traverse():
        match = pattern.match(str(prim.GetPath()))
        if match:
            env_id = int(match.group(1))
            if env_id in roots:
                raise ValueError(f"duplicate robot root for env {env_id}")
            roots[env_id] = prim
    expected_ids = set(range(int(expected_env_count)))
    if set(roots) != expected_ids:
        missing = sorted(expected_ids - set(roots))
        extra = sorted(set(roots) - expected_ids)
        raise ValueError(f"robot root inventory mismatch; missing={missing}, extra={extra}")
    if not 0 <= int(selected_env_id) < int(expected_env_count):
        raise ValueError("selected env id is outside the robot inventory")

    hidden_paths = []
    for env_id, prim in sorted(roots.items()):
        if env_id == int(selected_env_id) or env_id in tuple(keep_env_ids):
            continue
        imageable = UsdGeom.Imageable(prim)
        if not imageable:
            raise ValueError(f"robot root is not imageable: {prim.GetPath()}")
        imageable.MakeInvisible()
        hidden_paths.append(str(prim.GetPath()))
    return {"enabled": True, "method": "usd_imageable_visibility",
            "physics_or_policy_config_changed": False,
            "selected_env_id": int(selected_env_id),
            "environment_count": int(expected_env_count),
            "visible_robot_root": str(roots[int(selected_env_id)].GetPath()),
            "hidden_robot_roots": hidden_paths}


def define_target_marker(stage: Any, *, path: str = "/World/RunnerSelectedEnvMarker",
                         radius_m: float = 0.06, height_above_root_m: float = 0.08) -> tuple[Any, dict[str, Any]]:
    """Create a render-only, non-colliding marker which follows one captured robot."""
    from pxr import Gf, Sdf, UsdGeom

    sphere = UsdGeom.Sphere.Define(stage, Sdf.Path(path))
    sphere.CreateRadiusAttr(float(radius_m))
    sphere.CreateDisplayColorAttr([Gf.Vec3f(1.0, 0.82, 0.02)])
    xform = UsdGeom.Xformable(sphere.GetPrim())
    translate = xform.AddTranslateOp()
    return translate, {"enabled": True, "method": "render_only_usd_sphere",
                       "prim_path": path, "radius_m": float(radius_m),
                       "height_above_root_m": float(height_above_root_m),
                       "collision_or_rigid_body_api_added": False}


def update_target_marker(translate_op: Any, root_pos_w: Any,
                         height_above_root_m: float = 0.08) -> tuple[float, float, float]:
    """Move the marker above the selected robot without changing its state."""
    from pxr import Gf

    x, y, z = (float(value) for value in root_pos_w[:3])
    position = (x, y, z + float(height_above_root_m))
    translate_op.Set(Gf.Vec3d(*position))
    return position


def apply_lighting_profile(profile: dict[str, Any]) -> dict[str, Any]:
    """Apply optional USD lighting; inherited scene lighting stays untouched."""
    if profile.get("profile") == "inherit":
        return dict(profile)
    import omni.usd
    return apply_lighting_to_stage(omni.usd.get_context().get_stage(), profile)
