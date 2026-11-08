#!/usr/bin/env python3
"""Extract saved EX09-EX25 run configs without consulting code defaults.

Only reads params/env.yaml, params/agent.yaml, and manifest.json from the
explicitly named run roots. Full parsed config is retained in the JSON so no
reward term or parameter is lost in the comparison view.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

import yaml


DEFAULT_ROOT = Path(r"C:\Users\AI-WS01\orca\workspaces\foothold-lab\sonnet-code\logs\rsl_rl")
RUN_ROOTS = (
    "foothold_s2_diag", "foothold_s2_x11", "foothold_s2_x13", "foothold_s2_x15",
    "foothold_s2_x16n", "foothold_s2_x17", "foothold_s2_x18", "foothold_s2_x19",
    "foothold_s2_x20", "foothold_s2_x21", "foothold_s2_x22", "foothold_s2_x23",
)


class ConfigLoader(yaml.SafeLoader):
    pass


def _python_tag(loader: ConfigLoader, suffix: str, node: yaml.Node) -> Any:
    # Isaac Lab's YAML serializes tuples and slices with Python tags. Decode
    # their contained data only; never import or instantiate serialized code.
    if isinstance(node, yaml.SequenceNode):
        value = loader.construct_sequence(node)
    elif isinstance(node, yaml.MappingNode):
        value = loader.construct_mapping(node)
    else:
        value = loader.construct_scalar(node)
    return {"__yaml_python_tag__": suffix, "value": value}


ConfigLoader.add_constructor(
    "tag:yaml.org,2002:python/tuple",
    lambda loader, node: tuple(loader.construct_sequence(node)),
)
ConfigLoader.add_multi_constructor("tag:yaml.org,2002:python/", _python_tag)


def load_yaml(path: Path) -> Any:
    return yaml.load(path.read_text(encoding="utf-8"), Loader=ConfigLoader)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def get(data: Any, *keys: str) -> Any:
    for key in keys:
        if not isinstance(data, dict) or key not in data:
            return None
        data = data[key]
    return data


def experiment_label(run_name: str) -> str | None:
    match = re.search(r"(?:^|[^a-z])ex(\d{1,2})", run_name.lower())
    if match:
        return f"EX{int(match.group(1)):02d}"
    if run_name.lower() == "diag-g0-open":
        return "EX09"
    if run_name.lower() == "diag-g0-start":
        return "EX10"
    return None


def role(run_name: str) -> str:
    lowered = run_name.lower()
    if "smoke" in lowered or "dry" in lowered:
        return "smoke/dry run, kept separate from primary run"
    if "ex09" in lowered or "diag" in lowered:
        return "diagnostic run; start/open condition from run name"
    if "ex11" in lowered and "zero" in lowered:
        return "EX11 zero estimator"
    if "ex12" in lowered and "learned" in lowered:
        return "EX12 learned estimator"
    if "ex15" in lowered:
        return "paired forward/back leap condition; not labeled pure pronk"
    return "run label from saved run_name"


def terrain_entries(env: Any) -> list[dict[str, Any]]:
    generator = get(env, "scene", "terrain", "terrain_generator") or {}
    sub_terrains = generator.get("sub_terrains") or {}
    return [
        {"name": name, "proportion": cfg.get("proportion"), "function": cfg.get("function")}
        for name, cfg in sub_terrains.items()
        if cfg is not None
    ]


def event_entries(env: Any, *, reset: bool = False) -> list[dict[str, Any]]:
    events = get(env, "events") or {}
    result = []
    for name, cfg in events.items():
        if not isinstance(cfg, dict) or name.startswith("reset") != reset:
            continue
        result.append({"name": name, "function": cfg.get("func"), "params": cfg.get("params")})
    return result


def execution_summary(env: Any, agent: Any) -> dict[str, Any]:
    commands = get(env, "commands") or {}
    command = commands.get("base_velocity")
    action = (get(env, "actions") or {}).get("joint_pos")
    curriculum = get(env, "curriculum") or {}
    terrain_curriculum = curriculum.get("terrain_levels") or curriculum.get("terrain_levels_vel")
    terrain_cfg = get(env, "scene", "terrain") or {}
    generator = terrain_cfg.get("terrain_generator") or {}
    perception = get(agent, "perception") or {}
    rewards = get(env, "rewards") or {}
    return {
        "command": command,
        "reward_terms": [
            {"name": name, "function": cfg.get("func"), "weight": cfg.get("weight"), "params": cfg.get("params")}
            for name, cfg in rewards.items() if isinstance(cfg, dict)
        ],
        "domain_randomization_events": event_entries(env),
        "action": action,
        "perception": {key: perception.get(key) for key in (
            "est_mode", "map_input", "force_gt", "critic_mode", "contract", "oracle_vel_noise"
        )},
        "terrain": {
            "type": terrain_cfg.get("terrain_type"),
            "size": generator.get("size"),
            "rows": generator.get("num_rows"),
            "columns": generator.get("num_cols"),
            "generator_curriculum": generator.get("curriculum"),
            "non_null_sub_terrains": terrain_entries(env),
            "null_sub_terrains": [name for name, cfg in (generator.get("sub_terrains") or {}).items() if cfg is None],
            "promotion_hook": terrain_curriculum,
        },
        "reset_events": event_entries(env, reset=True),
        "terminations": get(env, "terminations"),
    }


def validate_known_cases(runs: list[dict[str, Any]]) -> None:
    by_path = {run["run_dir"].split("/")[-1]: run for run in runs}
    assert by_path["2026-10-21_16-14-13_diag-G0-open"]["experiment"] == "EX09"
    assert by_path["2026-10-21_16-14-13_diag-G0-start"]["experiment"] == "EX10"
    start_ex10 = by_path["2026-10-21_16-14-13_diag-G0-start"]["observed"]["commands"]["base_velocity"]
    start_ex12 = by_path["2026-10-22_01-34-08_ex12-est-learned"]["observed"]["commands"]["base_velocity"]
    assert start_ex10["params"].get("start_mode") is True
    assert start_ex12["params"].get("start_mode") is True
    for name in ("ex20-act-term-v2", "ex21-v2triple", "ex22-v2cmd"):
        run = next(run for run in runs if run["run_name"] == name)
        assert run["observed"]["actions"]["joint_pos"]["class_type"].endswith(":JointPositionAction")
        assert "DelayedJointPositionAction" not in run["observed"]["actions"]["joint_pos"]["class_type"]
    ex22 = next(run for run in runs if run["run_name"] == "ex22-v2cmd")
    assert ex22["observed"]["terrain_curriculum"]["func"].endswith(":terrain_levels_vel")
    assert ex22["observed"]["commands"]["base_velocity"]["class_type"].endswith(":UniformVelocityCommand")
    assert list(ex22["observed"]["commands"]["base_velocity"]["ranges"]["lin_vel_x"]) == [0.4, 1.5]
    ex23 = next(run for run in runs if run["run_name"] == "ex23-g1")
    assert len(ex23["observed"]["execution_summary"]["terrain"]["non_null_sub_terrains"]) == 7
    ex25 = next(run for run in runs if run["run_name"] == "ex25-g0" and run["run_dir"].endswith("23-00-45_ex25-g0"))
    events = ex25["observed"]["execution_summary"]["domain_randomization_events"]
    material = next(event for event in events if "randomize_rigid_body_material" in event["function"])
    mass = next(event for event in events if "randomize_rigid_body_mass" in event["function"])
    assert list(material["params"]["static_friction_range"]) == [0.8, 0.8]
    assert list(material["params"]["dynamic_friction_range"]) == [0.6, 0.6]
    assert list(mass["params"]["mass_distribution_params"]) == [-1.0, 3.0]


def _cell(value: Any) -> str:
    text = json.dumps(value, ensure_ascii=False, separators=(",", ":"), default=list) if not isinstance(value, str) else value
    return text.replace("|", "\\|").replace("\n", " ")


def render_run_table(runs: list[dict[str, Any]]) -> str:
    rows = [
        "| Run | 명령 | 보상 weight | DR 이벤트 함수와 주요 분포 | 행동 지연 | est/map/GT · critic | 지형 종류 · 비율 · 함수 | 승급 hook | reset · 종료 조건 |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    included = [run for run in runs if "smoke" not in run["run_name"] and "dry" not in run["run_name"]]
    for run in included:
        summary = run["observed"]["execution_summary"]
        cmd = summary["command"] or {}
        command = {
            "type": (cmd.get("class_type") or "미기록").split(":")[-1],
            "resample": cmd.get("resampling_time_range"),
            "params": cmd.get("params"),
            "dynamic": cmd.get("dynamic_flags"),
            "stride": cmd.get("flag_stride"),
            "ranges": cmd.get("ranges"),
            "rel_standing": cmd.get("rel_standing_envs"),
            "rel_heading": cmd.get("rel_heading_envs"),
        }
        rewards = ", ".join(f"{item['name']}={item['weight']}" for item in summary["reward_terms"])
        dr = []
        for event in summary["domain_randomization_events"]:
            params = event.get("params") or {}
            selected = {key: params[key] for key in (
                "static_friction_range", "dynamic_friction_range", "mass_distribution_params",
                "com_range", "stiffness_distribution_params", "damping_distribution_params", "scale_range"
            ) if key in params}
            dr.append(f"{event['name']}:{(event.get('function') or '미기록').split(':')[-1]} {_cell(selected)}")
        action = summary["action"] or {}
        action_text = f"{(action.get('class_type') or '미기록').split(':')[-1]} scale={action.get('scale')} clip={action.get('clip')} delay={action.get('max_delay_s', '미기록')}"
        perception = summary["perception"]
        perception_text = ", ".join(f"{key}={value}" for key, value in perception.items())
        terrain = summary["terrain"]
        terrain_text = "; ".join(
            f"{item['name']}={item['proportion']} [{(item.get('function') or '미기록')}]"
            for item in terrain["non_null_sub_terrains"]
        ) or "미기록"
        if terrain["null_sub_terrains"]:
            terrain_text += f"; null={','.join(terrain['null_sub_terrains'])}"
        promotion = terrain["promotion_hook"] or "미기록"
        if isinstance(promotion, dict):
            promotion = f"{promotion.get('func')} params={_cell(promotion.get('params'))}"
        reset_text = "; ".join(f"{event['name']}:{event.get('function')} params={_cell(event.get('params'))}" for event in summary["reset_events"])
        terms = summary["terminations"] or {}
        termination_text = "; ".join(
            f"{name}:{(cfg or {}).get('func')} params={_cell((cfg or {}).get('params'))} timeout={(cfg or {}).get('time_out')}"
            for name, cfg in terms.items()
        ) or "미기록"
        row_name = f"{run['experiment']} · {run['run_dir'].split('/')[-1]} · {run['observed']['max_iterations']}it"
        rows.append("| " + " | ".join(map(_cell, (row_name, command, rewards, "; ".join(dr) or "없음", action_text, perception_text, terrain_text, promotion, f"reset: {reset_text}; end: {termination_text}"))) + " |")
    return "\n".join(rows)


def collect(root: Path) -> list[dict[str, Any]]:
    runs: list[dict[str, Any]] = []
    for run_root in RUN_ROOTS:
        parent = root / run_root
        if not parent.is_dir():
            continue
        for run_dir in sorted(p for p in parent.iterdir() if p.is_dir()):
            env_path = run_dir / "params" / "env.yaml"
            agent_path = run_dir / "params" / "agent.yaml"
            manifest_path = run_dir / "manifest.json"
            if not env_path.is_file() and not agent_path.is_file() and not manifest_path.is_file():
                continue
            env = load_yaml(env_path) if env_path.is_file() else None
            agent = load_yaml(agent_path) if agent_path.is_file() else None
            manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.is_file() else None
            run_name = str(get(agent, "run_name") or run_dir.name)
            sources = {}
            for key, path in (("env", env_path), ("agent", agent_path), ("manifest", manifest_path)):
                if path.is_file():
                    sources[key] = {"path": path.relative_to(root).as_posix(), "sha256": sha256(path)}
                else:
                    sources[key] = None
            runs.append({
                "experiment": experiment_label(run_name),
                "role": role(run_name),
                "run_name": run_name,
                "run_dir": run_dir.relative_to(root).as_posix(),
                "sources": sources,
                "observed": {
                    "resume": get(agent, "resume"),
                    "load_run": get(agent, "load_run"),
                    "load_checkpoint": get(agent, "load_checkpoint"),
                    "initial_state_sha256": get(manifest, "initial_state_sha256"),
                    "env_seed": get(env, "seed"),
                    "agent_seed": get(agent, "seed"),
                    "num_envs": get(env, "scene", "num_envs"),
                    "rollout_steps_per_env": get(agent, "num_steps_per_env"),
                    "max_iterations": get(agent, "max_iterations"),
                    "est_mode": get(agent, "perception", "est_mode"),
                    "map_input": get(agent, "perception", "map_input"),
                    "force_gt": get(agent, "perception", "force_gt"),
                    "critic_mode": get(agent, "perception", "critic_mode"),
                    "perception": get(agent, "perception"),
                    "noise_std": get(agent, "policy", "init_noise_std"),
                    "terrain_type": get(env, "scene", "terrain", "terrain_type"),
                    "terrain_generator": get(env, "scene", "terrain", "terrain_generator"),
                    "terrain_curriculum": get(env, "curriculum", "terrain_levels"),
                    "commands": get(env, "commands"),
                    "rewards": get(env, "rewards"),
                    "actions": get(env, "actions"),
                    "robot": get(env, "scene", "robot"),
                    "events": get(env, "events"),
                    "terminations": get(env, "terminations"),
                    "execution_summary": execution_summary(env, agent),
                    "reset_and_initial_state": {
                        "scene_robot_initial_state": get(env, "scene", "robot", "init_state"),
                        "reset_events": get(env, "events"),
                    },
                    "observations": get(env, "observations"),
                    "ppo_algorithm": get(agent, "algorithm"),
                    "policy": get(agent, "policy"),
                    "manifest_git": get(manifest, "git"),
                    "manifest_checkpoints": get(manifest, "checkpoints"),
                },
                "raw": {"env": env, "agent": agent, "manifest": manifest},
            })
    return runs


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    runs = collect(args.root)
    validate_known_cases(runs)
    result = {
        "schema": "luna24d.saved-training-configs.v1",
        "method": "Read-only extraction from saved env.yaml, agent.yaml, and manifest.json; no code defaults are joined.",
        "source_root_label": "sonnet-code/logs/rsl_rl",
        "scan_roots": list(RUN_ROOTS),
        "runs": runs,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False, default=list) + "\n", encoding="utf-8")
    if args.report:
        existing = args.report.read_text(encoding="utf-8") if args.report.exists() else ""
        begin, end = "<!-- RUN-CONDITION-TABLE-BEGIN -->", "<!-- RUN-CONDITION-TABLE-END -->"
        block = f"{begin}\n\n{render_run_table(runs)}\n\n{end}"
        if begin in existing and end in existing:
            prefix, rest = existing.split(begin, 1)
            _, suffix = rest.split(end, 1)
            report_text = prefix + block + suffix
        else:
            report_text = existing.rstrip() + "\n\n## 실행 조건 전체 행\n\n" + block + "\n"
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(report_text, encoding="utf-8")
    print(f"runs={len(result['runs'])} output={args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
