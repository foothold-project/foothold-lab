"""Read-only map64 comparison. Run --self-test before aggregating real receipts.

Inputs stay untouched. GPU/Kit/torch are neither imported nor started.
Error = median over envs of that env's mean absolute error while alive.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import re
import statistics
from datetime import datetime

import numpy as np

MODES = ("eval_gt", "eval_pred", "probe_prop_only")
MODE_NAMES = {"eval_gt": "정답", "eval_pred": "복원", "probe_prop_only": "끔"}
COMMANDS = {
    "fwd0.5": [0.5, 0., 0.], "fwd1.0": [1., 0., 0.],
    "spin+1.2": [0., 0., 1.2], "spin-1.2": [0., 0., -1.2],
    "back0.5": [-0.5, 0., 0.], "back1.0": [-1., 0., 0.],
    "side+0.5": [0., 0.5, 0.], "side-0.5": [0., -0.5, 0.],
    "diag-fwd+side+": [0.5, 0.5, 0.], "diag-fwd+side-": [0.5, -0.5, 0.],
    "diag-back+side+": [-0.5, 0.5, 0.], "diag-back+side-": [-0.5, -0.5, 0.],
    "stop": [0., 0., 0.],
}
ERROR_KEYS = {
    "vx": "vx_abs_error_mean_alive_mps", "vy": "vy_abs_error_mean_alive_mps",
    "yaw": "wz_abs_error_mean_alive_radps",
}
METRICS = ("alive", "vx", "vy", "yaw")
PAIRS = {
    "side": ("side+0.5", "side-0.5"),
    "diag-fwd": ("diag-fwd+side+", "diag-fwd+side-"),
    "diag-back": ("diag-back+side+", "diag-back+side-"),
}
DEFAULT_OLD = Path("C:/Users/AI-WS01/s2_lab/ex41_main_20261104_235522/eval/score-watch")
DEFAULT_NEW = Path("D:/mai-tmp/lead/ex42_s0_map64")
PARENT_SHA = "1c6af6319c823c718af4965064f1c312b0d25177f5223a49c323aab3b6f1e613"


def require(ok, message):
    if not ok:
        raise ValueError(message)


def digest(blob):
    return hashlib.sha256(blob).hexdigest()


def write_text(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def write_csv(path, rows):
    require(bool(rows), f"empty table: {path.name}")
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def assignment_hash(level, column):
    return digest(np.asarray(level, dtype="<i8").tobytes() + np.asarray(column, dtype="<i8").tobytes())


def error_median(envs, key):
    values = []
    for env in envs:
        value = env[key]
        if env["samples_alive"] == 0:
            require(value is None, "zero samples must have null error")
            continue
        require(isinstance(value, (int, float)) and not isinstance(value, bool)
                and math.isfinite(value) and value >= 0, f"invalid {key}")
        values.append(float(value))
    require(bool(values), "no alive samples")
    result = statistics.median(values)
    require(result == float(np.median(values)), "independent median mismatch")
    return result, len(values)


def aggregate_cell(row, count):
    envs = sorted(row["per_env"], key=lambda env: env["env"])
    require([env["env"] for env in envs] == list(range(count)), "missing/duplicate env")
    require(row["env_count"] == count, "env denominator differs")
    require(all(type(env["alive_at_end"]) is bool for env in envs), "invalid alive type")
    alive = sum(env["alive_at_end"] for env in envs)
    require(alive == row["alive_envs_at_end"], "survival summary differs")
    out = {"alive": alive}
    for metric, key in ERROR_KEYS.items():
        out[metric], out[metric + "_n"] = error_median(envs, key)
    return out


def reconstruct_vy(command, projection_integral, vx_integral, alive_steps, dt):
    """Invert the producer's dot product; unavailable when cy=0 or no alive samples."""
    cx, cy, _ = command
    if cy == 0 or alive_steps == 0:
        return None
    return (math.hypot(cx, cy) * projection_integral - cx * vx_integral) / (cy * alive_steps * dt)


def make_pairs(rows):
    grouped = {}
    for row in rows:
        grouped.setdefault((row["family"], row["iteration"], row["mode"]), {})[row["command"]] = row
    pairs = []
    for (family, iteration, mode), cells in grouped.items():
        for name, (positive, negative) in PAIRS.items():
            a, b = cells[positive], cells[negative]
            pairs.append({"family": family, "iteration": iteration, "mode": mode, "pair": name,
                          "error_plus_mps": a["vy"], "error_minus_mps": b["vy"],
                          "error_gap_plus_minus_mps": a["vy"] - b["vy"],
                          "signed_vy_plus_mean_mps": a["signed_vy_mean_mps"],
                          "signed_vy_minus_mean_mps": b["signed_vy_mean_mps"],
                          "bias_plus_mps": a["signed_vy_mean_mps"] - .5,
                          "bias_minus_mps": b["signed_vy_mean_mps"] + .5,
                          "paired_common_bias_mps": (a["signed_vy_mean_mps"] + b["signed_vy_mean_mps"]) / 2,
                          "alive_plus": a["alive"], "alive_minus": b["alive"]})
    return pairs


def protocol(doc):
    pose = dict(doc.get("ex41_checkpoint_preparation", {}))
    pose.pop("checkpoint", None)
    # This is checkpoint training state, not the evaluator's forced map mode.
    restored = dict(doc["restored_modes"])
    restored.pop("force_gt_saved", None)
    return {key: doc[key] for key in (
        "task", "envs", "steps", "policy_dt_s", "command_suite", "commands", "dr_off",
        "curriculum_off", "fixed_terrain", "terrain_set", "eval_seed", "terrain_columns",
        "terrain_tiles", "start_offset_max_m",
    )} | {"pose": pose, "restored_modes": restored}


def load_receipt(path, family, iteration):
    raw = path.read_bytes()
    doc = json.loads(raw)
    require(doc["commands"] == COMMANDS, "13 command contract differs")
    require(set(doc["modes"]) == set(MODES), "three map modes required")
    require(doc["envs"] == 64 and doc["steps"] == 300, "expected 64 env x 300 steps")
    require(doc["policy_dt_s"] == .02 and doc["eval_seed"] == 42, "dt/seed differs")
    require(doc.get("dr_mode", {}).get("mode", "off") == "off", "DR-on is not maintenance map64")
    require(doc["checkpoint_iter"] == iteration, "folder/checkpoint iteration differs")
    require(doc["run_identity"]["checkpoint_sha256"] == doc["checkpoint_sha256"], "checkpoint identity differs")
    hashes = set(doc["terrain_hash"].values())
    require(len(doc["terrain_hash"]) == 39 and len(hashes) == 1, "terrain hash incomplete/mixed")
    terrain_hash = next(iter(hashes))
    require(terrain_hash == doc["fixed_terrain"]["assignment_sha256"], "fixed terrain hash differs")
    tiles = sorted(doc["terrain_tiles"], key=lambda t: t["env"])
    require([t["env"] for t in tiles] == list(range(64)), "terrain tiles incomplete")
    require(assignment_hash([t["level"] for t in tiles], [t["column"] for t in tiles]) == terrain_hash,
            "terrain hash recompute mismatch")
    rows, evidence, signed_envs = [], [], []
    for mode in MODES:
        require(set(doc["modes"][mode]) == set(COMMANDS), "command cells incomplete")
        for command, cmd in COMMANDS.items():
            cell = doc["modes"][mode][command]
            key = f"{mode}/{command}"
            require(cell["command"] == cmd, f"command differs: {key}")
            require(cell["policy_steps_x_envs"] == 300 * 64, "policy sample denominator")
            require(cell["gt_used"] == (300 * 64 if mode == "eval_gt" else 0), "actual GT consumption differs")
            metrics = aggregate_cell(cell, 64)
            data_path = path.parent / doc["env_arrays"][key]
            require(data_path.resolve().parent == path.parent.resolve(), "NPZ path outside map64")
            npz_sha = digest(data_path.read_bytes())
            with np.load(data_path, allow_pickle=False) as z:
                envs = sorted(cell["per_env"], key=lambda e: e["env"])
                require(np.array_equal(z["env"], np.arange(64)), "NPZ env order differs")
                require(np.array_equal(z["terrain_level"], [t["level"] for t in tiles])
                        and np.array_equal(z["terrain_col"], [t["column"] for t in tiles])
                        and np.array_equal(z["kind"], [t["kind"] for t in tiles]), "NPZ tiles differ")
                require(str(z["assignment_sha256"].item()) == terrain_hash, "NPZ hash differs")
                identity = json.loads(str(z["run_identity"].item()))
                require(identity == doc["run_identity"], "NPZ run identity differs")
                require(np.array_equal(z["alive_end"], [e["alive_at_end"] for e in envs]), "NPZ survival differs")
                mask = z["alive"]
                require(mask.shape == (300, 64) and mask.dtype == np.bool_, "alive shape/type")
                require(np.array_equal(mask.sum(0), [e["samples_alive"] for e in envs]), "alive sample count differs")
                require(np.array_equal(mask.sum(0), z["alive_steps"]), "NPZ alive_steps differs")
                require(not np.any(mask[1:] & ~mask[:-1]), "alive population resurrects")
                vx = z["vx"]
                require(np.isfinite(vx[mask]).all(), "active vx nonfinite")
                recalculated = [float(np.abs(vx[mask[:, i], i] - cmd[0]).mean())
                                if mask[:, i].any() else None for i in range(64)]
                diffs = [abs(v - e[ERROR_KEYS["vx"]]) for v, e in zip(recalculated, envs) if v is not None]
                require(max(diffs, default=0.) < 2e-6, "raw vx error disagrees with JSON")
                vy_signed, weights = [], []
                for i, env in enumerate(envs):
                    value = reconstruct_vy(cmd, env["command_xy_projection_integral_m"],
                                           float(z["body_vx_integral_m"][i]), env["samples_alive"], float(z["dt"]))
                    if value is not None:
                        require(math.isfinite(value), "signed vy nonfinite")
                        # Jensen's inequality bounds the recovered signed bias by recorded MAE.
                        require(abs(value-cmd[1]) <= env[ERROR_KEYS["vy"]] + 5e-5, "signed vy violates MAE bound")
                        require(abs(value) <= env["body_xy_speed_mean_alive_mps"] + 5e-5, "signed vy violates speed bound")
                        vy_signed.append(value); weights.append(env["samples_alive"])
                        signed_envs.append({"family": family, "iteration": iteration, "mode": mode, "command": command,
                                            "env": i, "alive_steps": env["samples_alive"], "alive_at_end": env["alive_at_end"],
                                            "signed_vy_mean_mps": value, "vy_bias_mps": value-cmd[1],
                                            "projection_integral_m": env["command_xy_projection_integral_m"],
                                            "vx_integral_m": float(z["body_vx_integral_m"][i])})
                metrics.update({"signed_vy_mean_mps": statistics.mean(vy_signed) if vy_signed else None,
                                "signed_vy_median_mps": statistics.median(vy_signed) if vy_signed else None,
                                "signed_vy_pooled_mps": float(np.average(vy_signed, weights=weights)) if vy_signed else None,
                                "signed_vy_n": len(vy_signed)})
                start_hash = digest(z["start_xy"].tobytes())
                starts = z["start_xy"].tolist()
            rows.append({"family": family, "iteration": iteration, "mode": mode, "command": command,
                         **metrics, "envs": 64, "checkpoint_sha256": doc["checkpoint_sha256"],
                         "terrain_hash": terrain_hash, "source": str(path)})
            evidence.append({"cell": key, "npz": str(data_path), "sha256": npz_sha,
                             "start_xy_sha256": start_hash, "start_xy": starts,
                             "vx_recompute_max_difference": max(diffs, default=0.)})
    require(path.read_bytes() == raw, "receipt changed during read")
    return {"family": family, "iteration": iteration, "path": str(path), "json_sha256": digest(raw),
            "checkpoint_sha256": doc["checkpoint_sha256"], "terrain_hash": terrain_hash,
            "checkpoint_force_gt_saved": doc["restored_modes"].get("force_gt_saved"),
            "protocol": protocol(doc), "run_identity": doc["run_identity"],
            "source_sha256": doc["source_sha256"], "rows": rows, "evidence": evidence, "signed_envs": signed_envs}


def self_test():
    envs = [{"env": i, "samples_alive": 1 if i != 3 else 0, "alive_at_end": i < 2,
             **{key: ([1., 3., 100., None][i] if metric == "vx" else
                       [0., 0., 0., None][i]) for metric, key in ERROR_KEYS.items()}}
            for i in range(4)]
    cell = {"env_count": 4, "alive_envs_at_end": 2, "per_env": envs}
    result = aggregate_cell(cell, 4)
    require(result["alive"] == 2 and result["vx"] == 3 and result["vx_n"] == 3, "known answer")
    require(result["vy"] == result["yaw"] == 0, "components must remain independent")
    # The fallen env's pre-fall error 100 stays in the median population.
    require(result["vx"] != statistics.median([1., 3.]), "must not silently use survivors only")
    changed = json.loads(json.dumps(cell)); changed["per_env"][2][ERROR_KEYS["vx"]] = float("nan")
    try:
        aggregate_cell(changed, 4)
    except ValueError:
        pass
    else:
        raise AssertionError("NaN not rejected")
    changed = json.loads(json.dumps(cell)); changed["per_env"][2]["env"] = 0
    try:
        aggregate_cell(changed, 4)
    except ValueError:
        pass
    else:
        raise AssertionError("duplicate env not rejected")
    require(assignment_hash([0, 1], [2, 3]) != assignment_hash([0, 2], [2, 3]), "hash mutation")
    # Known signed velocities, alive mask excludes a deliberately extreme post-fall value.
    vx = np.array([.3, .1, 999.]); vy = np.array([-.4, -.2, 999.]); mask = np.array([1, 1, 0], bool)
    for cx, cy in ((0., .5), (0., -.5), (.5, .5), (.5, -.5), (-.5, .5), (-.5, -.5)):
        projection = float((((vx*cx+vy*cy)/math.hypot(cx,cy))*mask).sum()*.02)
        recovered = reconstruct_vy([cx, cy, 0], projection, float((vx*mask).sum()*.02), 2, .02)
        require(abs(recovered - (-.3)) < 1e-12, "signed vy inversion known answer")
    require(reconstruct_vy([1,0,0], 1, 1, 2, .02) is None, "cy zero cannot identify vy")
    return {"known_answer_groups": 8, "status": "PASS", "expected": {"alive": 2, "vx_median": 3., "vy": 0., "yaw": 0., "recovered_signed_vy": -.3}}


def fmt(x, digits=4):
    return f"{x:.{digits}f}"


def table(lines, header, rows):
    escape = lambda s: str(s).replace("|", "\\|").replace("\n", " ")
    lines += ["", "| " + " | ".join(map(escape, header)) + " |",
              "| " + " | ".join(["---"] * len(header)) + " |"]
    lines.extend("| " + " | ".join(map(escape, row)) + " |" for row in rows)
    lines.append("")


def make_figure(out, parent, snapshots):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.colors import LinearSegmentedColormap, TwoSlopeNorm
    cmap = LinearSegmentedColormap.from_list("signed_error", ["#256c73", "#ffffff", "#a94632"])
    images = []
    base = {(r["mode"], r["command"]): r for r in parent["rows"]}
    for run in snapshots:
        current = {(r["mode"], r["command"]): r for r in run["rows"]}
        fig, axes = plt.subplots(1, 4, figsize=(14, 7), constrained_layout=True)
        for ax, metric in zip(axes, METRICS):
            values = np.array([[current[m, c][metric] - base[m, c][metric] for m in MODES] for c in COMMANDS])
            limit = max(float(np.abs(values).max()), .0001)
            im = ax.imshow(values, cmap=cmap, norm=TwoSlopeNorm(vcenter=0, vmin=-limit, vmax=limit), aspect="auto")
            for (y, x), value in np.ndenumerate(values):
                color = "white" if abs(value) > .6 * limit else "#162b2c"
                ax.text(x, y, f"{value:+.0f}" if metric == "alive" else f"{value:+.3f}", ha="center", va="center", fontsize=8, color=color)
            ax.set_xticks(range(3), ["GT", "Pred", "Off"])
            ax.set_yticks(range(13), list(COMMANDS) if metric == "alive" else [])
            ax.set_title({"alive": "Survivors (env/64)", "vx": "vx MAE (m/s)", "vy": "vy MAE (m/s)", "yaw": "yaw-rate MAE (rad/s)"}[metric], fontsize=11)
            fig.colorbar(im, ax=ax, fraction=.05, pad=.04)
        fig.suptitle(f"EX-42 m{run['iteration']} minus EX-41 parent m6000 (= cumulative m12000)\nNegative error difference means smaller recorded error; no pass/fail or noise threshold", fontsize=12)
        name = f"delta_m{run['iteration']}.png"
        fig.savefig(out / name, dpi=160)
        plt.close(fig)
        images.append(name)
    return images


def symmetry_section(lines, audit, out):
    pairs = audit["pairs"]
    selected = [p for p in pairs if p["family"] == "EX-42" or p["iteration"] == 6000]
    name = lambda p: ("부모 m6000" if p["family"] == "EX-41" else f"EX-42 m{p['iteration']}")
    lines += ["## 3b. 좌우 짝과 부호 있는 vy", "",
              "대칭 열 ΔE = +방향 vy 절대 오차 중앙값 − −방향 vy 절대 오차 중앙값이다. "
              "ΔE<0이면 +방향의 오차가 더 작고, >0이면 −방향의 오차가 더 작다. "
              "0에 가깝더라도 양쪽 모두 못 따라갈 수 있으므로 E+·E−를 같이 둔다. 문턱이나 합격률은 만들지 않았다."]
    table(lines, ["저장본", "지도", "짝", "E+ m/s", "E− m/s", "대칭 ΔE m/s", "끝 생존 + / −"], [
        [name(p), MODE_NAMES[p["mode"]], p["pair"], fmt(p["error_plus_mps"]), fmt(p["error_minus_mps"]),
         f"{p['error_gap_plus_minus_mps']:+.4f}", f"{p['alive_plus']}/64 · {p['alive_minus']}/64"] for p in selected])
    lines += ["부호 있는 평균 vy는 원시 vy 시간열의 직접 재계산이 아니라 저장된 투영 적분에서 복원한 값이다. "
              "평가기 식은 P = Σalive(vx·cx + vy·cy)/sqrt(cx²+cy²)·dt다. "
              "따라서 cy≠0이면 env별 mean(vy) = (sqrt(cx²+cy²)·P − cx·Ivx)/(cy·살아 있던 스텝 수·dt)다. "
              "Ivx는 NPZ body_vx_integral_m이다. 여섯 횡/대각 명령에서 이 식을 썼다. "
              "cy=0인 전진·후진·회전·정지는 이 자료만으로 signed vy를 알 수 없어 미확인으로 남긴다.", "",
              "아래 mean(vy)는 env별 생존 중 평균을 64 env에 같은 비중으로 평균한 값이다. "
              "양수는 몸좌표 +y(side+) 방향이다. 명령 자체가 ±0.5이므로 부호만으로 치우침이라고 하지 않는다. "
              "bias± = mean(vy±) − 명령(±0.5), 공통 치우침 b = (mean(vy+) + mean(vy−))/2다. "
              "b>0이면 짝 전체가 +y쪽, b<0이면 −y쪽으로 기운 기록이다. b=0도 양쪽 추종이 좋다는 뜻은 아니다. "
              "시간 가중 평균과 env별 복원값은 CSV에 별도로 보존했다."]
    table(lines, ["저장본", "지도", "짝", "mean(vy+) m/s", "mean(vy−) m/s", "bias+ / bias− m/s", "공통 b m/s"], [
        [name(p), MODE_NAMES[p["mode"]], p["pair"], f"{p['signed_vy_plus_mean_mps']:+.4f}",
         f"{p['signed_vy_minus_mean_mps']:+.4f}", f"{p['bias_plus_mps']:+.4f} / {p['bias_minus_mps']:+.4f}",
         f"{p['paired_common_bias_mps']:+.4f}"] for p in selected])
    lines += ["**EX-41 경계에서도 부호가 뒤집혔는가**", "",
              "아래는 EX-41 m250~m6000의 인접 경계 사이에서 ΔE 부호가 바뀐 횟수와 위치다. "
              "0으로 반올림하지 않은 원값을 썼고, 1e−12는 부동소수점 0 구분용일 뿐 보행 문턱이 아니다. "
              "저장본마다 정책이 다르므로 이런 방향 뒤집힘은 관측된 이력이지 재측정 폭이나 원인 증거가 아니다."]
    table(lines, ["지도", "짝", "ΔE 최소~최대 m/s", "부호 뒤집힘 수", "인접 회차(로컬)"], [
        [MODE_NAMES[p["mode"]], p["pair"], f"{p['gap_min']:+.4f}~{p['gap_max']:+.4f}", len(p["crossings"]),
         ', '.join(f"{x['before']}→{x['after']}" for x in p["crossings"]) or "없음"] for p in audit["sign_history"]])
    lines += [f"![좌우 오차 차이와 공통 치우침 이력]({out.name}/symmetry_history.png)", "",
              f"[전체 경계 좌우 짝 숫자]({out.name}/symmetry_pairs.csv) · "
              f"[부호 뒤집힘의 전후 값]({out.name}/symmetry_sign_history.json) · "
              f"[env별 signed vy 복원]({out.name}/signed_vy_envs.csv)", ""]
    oracle_path = out / "known_producer_test.json"
    if oracle_path.exists():
        oracle = json.loads(oracle_path.read_text(encoding="utf-8"))
        lines += [f"[CPU 검증] 실제 map_mode_cells.summarize에 답을 아는 vx/vy와 종료 마스크를 넣은 "
                  f"{oracle['cases']}개 입력에서 signed vy 복원값이 예상과 일치했다. "
                  f"최대 수치 차이는 {oracle['max_error_mps']:.3g} m/s다. "
                  f"[시험 코드]({out.name}/verify_known_input.py) · [영수증]({out.name}/known_producer_test.json). "
                  "실제 자료에서도 각 env의 복원된 평균 오차 크기가 기록된 평균 절대오차보다 크지 않은지, "
                  "복원된 평균 vy 크기가 평균 수평 속력보다 크지 않은지 대조했다.", ""]


def symmetry_plot(out, pairs):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(3, 2, figsize=(13, 10), constrained_layout=True)
    colors = {"eval_gt": "#226b73", "eval_pred": "#a94b35", "probe_prop_only": "#6e568b"}
    for y, pair in enumerate(PAIRS):
        for x, metric in enumerate(("error_gap_plus_minus_mps", "paired_common_bias_mps")):
            ax = axes[y, x]
            for mode in MODES:
                values = [p for p in pairs if p["pair"] == pair and p["mode"] == mode]
                values.sort(key=lambda p: (6000 if p["family"] == "EX-41" else 12000) + p["iteration"])
                xs = [(6000 if p["family"] == "EX-41" else 12000)+p["iteration"] for p in values]
                ax.plot(xs, [p[metric] for p in values], marker="o", markersize=3, label=mode, color=colors[mode])
                for p in values:
                    if p["family"] == "EX-42":
                        ax.scatter(12000+p["iteration"], p[metric], marker="s", s=32, color=colors[mode])
            ax.axhline(0, color="#555555", linewidth=.7)
            ax.axvline(12000, color="#666666", linestyle=":", linewidth=1)
            ax.set_title(pair + (": MAE(+) minus MAE(-)" if x == 0 else ": paired signed vy bias"))
            ax.set_ylabel("m/s")
            ax.grid(alpha=.2)
            if y == 2:
                ax.set_xlabel("Cumulative updates (EX-41: 6000+local; EX-42: 12000+local)")
    axes[0,0].legend(fontsize=8)
    fig.suptitle("Recorded left/right pair history, not a repeatability band\nDotted line: parent m12000; squares: EX-42 snapshots", fontsize=13)
    fig.savefig(out / "symmetry_history.png", dpi=160)
    plt.close(fig)


def report(audit, out, n21_rows, script):
    parent = audit["parent"]
    snapshots = audit["snapshots"]
    base = {(r["mode"], r["command"]): r for r in parent["rows"]}
    history = audit["history_ranges"]
    artifact = out.name
    lines = ["> 분류: A/평가 · EX-42 0 단계 경계 비교", f"> 작성: analyst · {audit['generated_at']}",
             "> 근거: EX-41 map64 부모와 경계 기록 · EX-42 완료 map64 · JSON/NPZ 직접 재집계",
             "> 요지: 생존과 vx·vy·yaw 속도 오차를 따로 비교한다. 지형 배치 해시와 조건을 먼저 확인한다.",
             "> 상태: record_only · 승급/중단 판정 없음 · CPU 분석만", "", "# EX-42 0 단계 map64 경계 비교", "",
             f"현재 완료되어 포함된 EX-42 저장본은 {', '.join('m'+str(r['iteration']) for r in snapshots)}이다. "
             "EX-41 부모는 로컬 m6000, 누적 m12000이다. EX-42 m100은 부모 뒤 추가 100회이며 EX-41 m100과 같은 시점이 아니다.", "",
             "표의 숫자는 생성기가 원자료에서 읽었다. EX-41 m250~m5750은 서로 다른 학습 상태의 기록으로, 그 최솟값~최댓값을 같은 정책의 재측정 폭이라고 부르지 않는다.", "",
             "## 먼저 읽을 기록", "",
             "각 성분이 서로 반대로 움직일 수 있으므로 한 점수로 합치지 않았다. 아래는 전진·좌우 횡이동·뒤 대각 이동의 해당 속도 성분이다. "
             "모두 절대 오차 중앙값(m/s)이며, 낮을수록 이 기록에서 명령과 가깝다. 판정이나 원인 추론은 하지 않는다."]
    lookup = {r["iteration"]: {(v["mode"], v["command"]): v for v in r["rows"]} for r in snapshots}
    table(lines, ["지도", "명령·성분", "부모"] + [f"EX-42 m{r['iteration']}" for r in snapshots], [
        [MODE_NAMES[mode], command+" · "+metric, fmt(base[mode,command][metric])] +
        [fmt(lookup[r["iteration"]][mode,command][metric]) for r in snapshots]
        for command,metric in (("fwd1.0","vx"),("side+0.5","vy"),("side-0.5","vy"),
                               ("diag-back+side+","vy"),("diag-back+side-","vy")) for mode in MODES])
    latest = max(r["iteration"] for r in snapshots)
    latest_pairs = [p for p in audit["pairs"] if p["family"] == "EX-42" and p["iteration"] == latest]
    side = [p for p in latest_pairs if p["pair"] == "side"]
    back = [p for p in latest_pairs if p["pair"] == "diag-back"]
    lines += [f"[실측에서 복원] 최신 m{latest}의 횡이동 짝 공통 vy 치우침은 지도 셋에서 "
              f"{min(p['paired_common_bias_mps'] for p in side):+.4f}~{max(p['paired_common_bias_mps'] for p in side):+.4f} m/s, "
              f"뒤 대각 짝은 {min(p['paired_common_bias_mps'] for p in back):+.4f}~{max(p['paired_common_bias_mps'] for p in back):+.4f} m/s다. "
              "양수는 몸좌표 +y 방향이다. 명령을 뺀 짝의 치우침 정의와 복원 한계는 3b절에 적었다.", ""]
    lines += ["## 1. 먼저 비교 조건", "",
             f"[실측] 포함된 {len(audit['runs'])}판의 39칸 지형 배치 해시는 모두 `{parent['terrain_hash']}`다. "
             "JSON의 해시만 읽지 않고 각 NPZ의 level·column·kind와 64칸 표를 대조했고, level/column 배열에서 해시를 다시 만들었다. "
             "이 해시는 지형 배치이지 메시 기하 전체의 해시가 아니다. 메시 바이트의 동일성은 미확인이다.", "",
             f"[실측] 부모와 각 판의 동일 칸 NPZ start_xy 차이 최댓값은 "
             f"{max(e['start_xy_parent_max_abs_diff_m'] for r in audit['runs'] for e in r['evidence']):.8f} m다. "
             "같은 시작 좌표인 것은 확인했지만, 이것만으로 모든 물리 상태가 같다고 단정하지 않는다."]
    table(lines, ["항목", "부모와 EX-42"], [
        ["환경·시간", "64 env · 300 step · dt 0.02 s = 6초"],
        ["지형", "연속 7종 · 23열 · L0/L1/L2 = 23/23/18 env · 별도 평지 칸 없음"],
        ["명령·지도", "13개 고정 명령 × 정답/복원/끔 = 39칸 · 독립 reset"],
        ["시드·관측", "eval_seed 42 · actor 98 / critic 666 · pose_cmd [0,0]"],
        ["DR 표시", "dr_off=[physics_material, add_base_mass] 동일 · 물성 실측 배열은 이 map64에 없음"],
        ["지형 승급", "평가 중 terrain_levels 계열 curriculum 끔 · 고정 칸"],
        ["차이", "EX-41 GPU1 / EX-42 GPU0, 실행 코드 HEAD 다름. 엄격한 동일 실행 조건의 인과 비교는 불가"],
        ["정책", "다른 학습 저장본. 부모 SHA·각 저장본 SHA는 입력 목록에 기록"],
    ])
    table(lines, ["판", "회차", "code HEAD", "GPU", "저장된 force_gt", "JSON SHA 앞12", "평가 설정 대조"], [
        [r["family"], r["iteration"], r["run_identity"]["code_head"][:8], r["run_identity"]["device"], r["checkpoint_force_gt_saved"], r["json_sha256"][:12], "일치" if r["protocol_matches_parent"] else "불일치: "+','.join(r["protocol_differences"])]
        for r in audit["runs"]])
    lines += ["저장본의 force_gt_saved는 EX-41 m250~5500에서 True, m5750·부모 m6000·현재 EX-42에서 False다. "
              "이는 학습 저장 상태의 차이이며 평가기의 지도 선택과 구분한다. 모든 포함 판에서 실제 gt_used는 정답 19200/19200, "
              "복원·끔 0/19200임을 확인했다. 과거 범위에는 이런 학습 상태 변화도 들어 있다.", "",
              "평가 코드 변경: 부모 432e2f10 → EX-42 eae0bed7에서 N21 DR 선택 경로가 추가됐다. "
              "extended 13명령과 map_mode_cells.summarize의 오차 식은 바뀌지 않았다. DRMode의 off 경로는 begin/step/collect에서 즉시 반환한다. "
              "StartRunner 변경은 EX-42 학습·저장·부모 이식 경로다. 다만 CPU 소스 대조는 GPU 재현 실험을 대신하지 않는다. "
              f"전체 diff는 [{artifact}/source_diff.txt]({artifact}/source_diff.txt)에 남겼다. "
              "이 소스 대조는 eae0bed7 범위다. 후속 재생성 때 다른 HEAD가 들어오면 위 입력 표를 보고 별도 대조해야 한다.", "",
              "## 2. 숫자의 뜻", "",
              "- 생존은 마지막 스텝까지 종료되지 않은 env 수 / 64다. 성공률이나 목표 도달률이 아니다.",
              "- vx·vy·yaw 열은 각 env가 살아 있던 스텝의 절대 추종 오차 평균을 먼저 구한 뒤, env들 사이 중앙값을 구한다. "
              "vx·vy는 m/s, yaw는 yaw 각도 오차가 아니라 wz 각속도 오차(rad/s)다.",
              "- 명령이 0인 성분도 계산한다. 예를 들어 전진 중 vy는 옆으로 새는 속도, wz는 원치 않는 회전이다. 정지는 세 성분 모두 잔류 속도다.",
              "- 넘어진 env도 넘어지기 전 자료는 오차 중앙값에 남긴다. 마지막까지 살아남은 env만 고르지 않는다. "
              "종료 뒤 자료는 제외하므로 조기 종료가 낮은 오차처럼 보일 수 있어 생존을 반드시 함께 읽는다.",
              "- vx·생존·살아 있던 스텝 수는 NPZ로 다시 계산했다. vy/wz 시간열은 NPZ에 없어 JSON의 env별 평균을 재집계했다. "
              "부호 있는 vy는 식으로 복원 가능한 횡/대각 칸만 3b절에 따로 적었다. 보행 위상·발 미끄럼·영상 판독은 이번 표에 없다.", "",
              "## 3. 부모와 EX-42 저장본을 나란히", "",
              "오차 칸은 `부모 → 현재 (현재−부모)`다. 음수는 이번 기록에서 오차가 작다는 뜻이다. "
              "통계적 개선이나 다음 단계 통과를 뜻하지 않는다. 원래 정밀도와 분모는 CSV에 보존했다."]
    for run in snapshots:
        current = {(r["mode"], r["command"]): r for r in run["rows"]}
        lines += ["", f"### EX-42 m{run['iteration']}"]
        alive_delta = [r["alive"]-base[r["mode"],r["command"]]["alive"] for r in run["rows"]]
        lines += ["", f"[실측] 생존이 부모보다 많은/같은/적은 칸: {sum(v>0 for v in alive_delta)}/{sum(v==0 for v in alive_delta)}/{sum(v<0 for v in alive_delta)} (39칸)."]
        for mode in MODES:
            lines += ["", f"**{MODE_NAMES[mode]} ({mode})**"]
            values = []
            for cmd in COMMANDS:
                old, now = base[mode, cmd], current[mode, cmd]
                values.append([cmd, f"{old['alive']}/64 → {now['alive']}/64", *[
                    f"{fmt(old[m])} → {fmt(now[m])} ({now[m]-old[m]:+.4f})" for m in ("vx", "vy", "yaw")]])
            table(lines, ["명령", "끝 생존", "vx 오차 m/s", "vy 오차 m/s", "wz 오차 rad/s"], values)
        lines += [f"![성분별 기록 차이]({artifact}/delta_m{run['iteration']}.png)", ""]
    symmetry_section(lines, audit, out)
    lines += ["## 4. EX-41 경계 기록의 범위", "",
              "EX-41 로컬 m250~m5750의 23개 저장본 범위다. 부모 m6000은 위 비교표에 따로 뒀다. "
              "이 범위에는 학습 진행·단계/DR 변경·코드 변경이 함께 들어 있다. 재측정 잡음·허용 오차로 쓰지 않는다. "
              f"24개 EX-41 저장본의 936칸 전체 숫자는 [cells.csv]({artifact}/cells.csv), 경계별 출처는 [inputs.json]({artifact}/inputs.json)에 있다."]
    table(lines, ["지도", "명령", "끝 생존 min~max /64", "vx 오차 min~max m/s", "vy 오차 min~max m/s", "wz 오차 min~max rad/s"], [
        [MODE_NAMES[r["mode"]], r["command"], f"{r['alive_min']}~{r['alive_max']}",
         *[f"{fmt(r[m+'_min'])}~{fmt(r[m+'_max'])}" for m in ("vx","vy","yaw")]] for r in history])
    lines += ["## 5. 오전 N21 시드 폭은 참고치만", "",
              "N21은 같은 부모의 seed42/43/44, 별도 평지 또는 연속 지형 L2, 대표 8명령이다. "
              "현재 표는 연속 7종의 L0~2 혼합·13명령이다. 지형 배치·명령 범위·시드 조건이 달라 N21 폭을 EX-42 차이의 합격선이나 유의성 기준으로 쓰지 않는다. "
              "특히 back1.0과 대각 4명령에는 N21 대응 칸이 없다. 아래는 연속 지형 off/on 각각의 관측 폭만 옮겼다. "
              "N21의 stop 선형값은 vx가 아닌 수평 속력이며 다른 성분으로 표기한다."]
    table(lines, ["지도", "명령", "성분·단위", "off 세 시드 폭", "on 세 시드 폭"], [
        [MODE_NAMES[r["mode"]], r["command"], r["metric"]+" · "+r["unit"], fmt(float(r["off_width"])), fmt(float(r["on_width"]))]
        for r in n21_rows if r["terrain"] == "continuous"])
    lines += ["## 6. 재현·미도착 자료", "",
              f"현재 대기/제외 목록: `{json.dumps(audit['pending'], ensure_ascii=False)}`. JSON이 없거나 일부만 기록된 판은 0점으로 채우지 않는다. "
              "완료된 JSON과 39 NPZ가 들어온 뒤 같은 명령을 다시 실행하면 m500·m750·m1000까지 자동 포함한다. 자동 GPU 실행·상주 감시는 하지 않는다.", "",
              "```powershell", "$env:PYTHONUTF8='1'; $env:PYTHONDONTWRITEBYTECODE='1'",
              f"& 'C:/Users/AI-WS01/anaconda3/envs/isaac311/python.exe' '{script.as_posix()}' --self-test",
              f"& 'C:/Users/AI-WS01/anaconda3/envs/isaac311/python.exe' '{script.as_posix()}'",
              "```", "",
              f"[실측] 답 아는 입력 {audit['self_test']['known_answer_groups']}묶음 PASS: 생존/중앙값/성분 분리/조기 종료 전 자료 유지/NaN·중복 env 거절/지형 해시 돌연변이/부호 있는 vy 복원과 식별 불가 조건. "
              f"실제 {len(audit['runs'])}판·{sum(len(r['evidence']) for r in audit['runs'])} NPZ를 대조했다. "
              "입력 JSON과 NPZ 해시, 출처, 실행 코드 HEAD, env별 분모는 기계 판독 파일에 남겼다.", "",
              f"- [전체 칸·분모]({artifact}/cells.csv)", f"- [부모 대비 성분별 차이와 EX-41 과거 범위]({artifact}/comparison.csv)",
              f"- [조건·입력·NPZ 검증]({artifact}/inputs.json)", f"- [답 아는 입력 결과]({artifact}/self_test.json)",
              f"- [재생성 코드]({artifact}/recompute.py)", f"- [산출물 해시]({artifact}/SHA256SUMS)",
              "- [고정 지형 배치 해시 식 · fixed_terrain.py:91](https://github.com/foothold-project/foothold-lab/blob/eae0bed799dce0e39b04d157ad4e3e79ecb87653/foothold_s2/eval/fixed_terrain.py#L91)",
              "- [성분별 env 평균 식 · map_mode_cells.py:157](https://github.com/foothold-project/foothold-lab/blob/eae0bed799dce0e39b04d157ad4e3e79ecb87653/foothold_s2/eval/map_mode_cells.py#L157)",
              "- [DR off 즉시 반환 경로 · eval_dr_mode.py:520](https://github.com/foothold-project/foothold-lab/blob/eae0bed799dce0e39b04d157ad4e3e79ecb87653/foothold_s2/eval/eval_dr_mode.py#L520)",
              "", "판정: 없음. 현재 자료에서 관측된 숫자를 기록했으며 보행 개선·퇴행의 원인과 통계적 확실성은 미확인이다."]
    write_text(out.parent / "REPORT-analyst-ex42-s0-map64-1108.md", "\n".join(lines)+"\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--old-root", type=Path, default=DEFAULT_OLD)
    parser.add_argument("--new-root", type=Path, default=DEFAULT_NEW)
    parser.add_argument("--out", type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument("--n21", type=Path, default=Path(__file__).resolve().parent.parent / "N21-seedwidth-1108/comparison.csv")
    parser.add_argument("--max-iteration", type=int, default=1000)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    tested = self_test()
    if args.self_test:
        print(json.dumps(tested)); return
    args.out.mkdir(parents=True, exist_ok=True)
    parent_path = args.old_root / "model_6000_1c6af6319c82/evaluation/map64/map_modes.json"
    parent = load_receipt(parent_path, "EX-41", 6000)
    require(parent["checkpoint_sha256"] == PARENT_SHA, "wrong parent SHA")
    runs, pending = [], []
    for iteration in range(250, 6000, 250):
        paths = list(args.old_root.glob(f"model_{iteration}_*/evaluation/map64/map_modes.json"))
        require(len(paths) == 1, f"EX-41 m{iteration}: expected exactly one receipt, got {len(paths)}")
        runs.append(load_receipt(paths[0], "EX-41", iteration))
    runs.append(parent)
    snapshots = []
    discovered = {}
    for directory in args.new_root.glob("model_*"):
        match = re.fullmatch(r"model_(\d+)", directory.name)
        if match and int(match[1]) <= args.max_iteration:
            discovered[int(match[1])] = directory / "map64/map_modes.json"
    for iteration in sorted(set(discovered) | {i for i in (100,250,500,750,1000) if i <= args.max_iteration}):
        path = discovered.get(iteration, args.new_root / f"model_{iteration}/map64/map_modes.json")
        if not path.exists():
            pending.append({"iteration": iteration, "reason": "map_modes.json not arrived"}); continue
        try:
            run = load_receipt(path, "EX-42", iteration)
        except (ValueError, OSError, KeyError) as exc:
            pending.append({"iteration": iteration, "reason": type(exc).__name__+": "+str(exc)}); continue
        snapshots.append(run); runs.append(run)
    require(bool(snapshots), "no complete EX-42 checkpoint")
    pstarts = {e["cell"]: e["start_xy"] for e in parent["evidence"]}
    for run in runs:
        diff = [key for key in parent["protocol"] if run["protocol"][key] != parent["protocol"][key]]
        run["protocol_differences"] = diff
        run["protocol_matches_parent"] = not diff
        require(not diff, f"evaluation protocol mismatch {run['family']} m{run['iteration']}: {diff}")
        require(run["terrain_hash"] == parent["terrain_hash"], "parent terrain hash differs")
        for e in run["evidence"]:
            e["start_xy_parent_max_abs_diff_m"] = float(np.abs(np.asarray(e["start_xy"])-pstarts[e["cell"]]).max())
            e.pop("start_xy")
    rows = [row for run in runs for row in run["rows"]]
    ranges = []
    for mode in MODES:
        for command in COMMANDS:
            entries = [r for r in rows if r["family"] == "EX-41" and r["iteration"] < 6000 and r["mode"] == mode and r["command"] == command]
            ranges.append({"mode": mode, "command": command, "checkpoints": len(entries),
                           **{m+s: f(r[m] for r in entries) for m in METRICS for s,f in (("_min",min),("_max",max))}})
    base = {(r["mode"], r["command"]): r for r in parent["rows"]}
    hmap = {(r["mode"], r["command"]): r for r in ranges}
    comparisons = []
    for run in snapshots:
        for row in run["rows"]:
            key = row["mode"], row["command"]
            for metric in METRICS:
                comparisons.append({"ex42_iteration": run["iteration"], "mode": key[0], "command": key[1], "metric": metric,
                                    "unit": "env/64" if metric == "alive" else "rad/s" if metric == "yaw" else "m/s",
                                    "parent": base[key][metric], "current": row[metric], "delta": row[metric]-base[key][metric],
                                    "ex41_history_min": hmap[key][metric+"_min"], "ex41_history_max": hmap[key][metric+"_max"],
                                    "inference": "record_only_no_noise_threshold"})
    pairs = make_pairs(rows)
    sign_history = []
    for mode in MODES:
        for pair in PAIRS:
            series = sorted([p for p in pairs if p["family"] == "EX-41" and p["mode"] == mode and p["pair"] == pair], key=lambda p:p["iteration"])
            flips = [{"before": a["iteration"], "after": b["iteration"], "before_gap": a["error_gap_plus_minus_mps"], "after_gap": b["error_gap_plus_minus_mps"]}
                     for a,b in zip(series,series[1:]) if a["error_gap_plus_minus_mps"]*b["error_gap_plus_minus_mps"] < 0
                     and min(abs(a["error_gap_plus_minus_mps"]),abs(b["error_gap_plus_minus_mps"]))>1e-12]
            sign_history.append({"mode":mode,"pair":pair,"gap_min":min(p["error_gap_plus_minus_mps"] for p in series),
                                 "gap_max":max(p["error_gap_plus_minus_mps"] for p in series),"crossings":flips})
    write_csv(args.out / "signed_vy_envs.csv", [e for r in runs for e in r.pop("signed_envs")])
    write_csv(args.out / "symmetry_pairs.csv", pairs)
    write_text(args.out / "symmetry_sign_history.json", json.dumps(sign_history,ensure_ascii=False,indent=2)+"\n")
    audit = {"generated_at": datetime.now().isoformat(timespec="seconds"), "parent": parent, "snapshots": snapshots,
             "runs": runs, "history_ranges": ranges, "pending": pending, "self_test": tested,
             "pairs": pairs, "sign_history": sign_history}
    with args.n21.open(encoding="utf-8-sig", newline="") as stream:
        n21_rows = list(csv.DictReader(stream))
    audit["n21_reference"] = {"path": str(args.n21), "sha256": digest(args.n21.read_bytes()), "use": "reference_only_not_threshold"}
    write_csv(args.out / "cells.csv", rows)
    write_csv(args.out / "comparison.csv", comparisons)
    write_csv(args.out / "ex41_history_ranges.csv", ranges)
    write_text(args.out / "inputs.json", json.dumps(audit, ensure_ascii=False, indent=2, allow_nan=False)+"\n")
    write_text(args.out / "self_test.json", json.dumps(tested, indent=2)+"\n")
    make_figure(args.out, parent, snapshots)
    symmetry_plot(args.out, pairs)
    report(audit, args.out, n21_rows, Path(__file__).resolve())
    paths = [p for p in args.out.iterdir() if p.is_file() and p.name != "SHA256SUMS"]
    paths.append(args.out.parent / "REPORT-analyst-ex42-s0-map64-1108.md")
    write_text(args.out / "SHA256SUMS", "".join(f"{digest(p.read_bytes())}  {p.relative_to(args.out) if p.parent==args.out else '../'+p.name}\n" for p in sorted(paths)))
    print(json.dumps({"runs": len(runs), "cells": len(rows), "ex42": [r["iteration"] for r in snapshots], "pending": pending,
                      "report": str(args.out.parent / "REPORT-analyst-ex42-s0-map64-1108.md")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
