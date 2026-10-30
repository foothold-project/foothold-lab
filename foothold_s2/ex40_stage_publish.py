"""Publish pinned EX-40 stage reports to the approved documentation branch.

The score watcher owns this module. It never stages paths outside STAGE_DIR and
never rewrites an existing stage document. Git and Telegram are injectable for
CPU tests; live publication requires an operator prepared, dedicated worktree.
"""

from __future__ import annotations

import json
import math
import os
from pathlib import Path
import subprocess
import sys
import time

from foothold_s2.ex40_score import sha256


BRANCH = "feature/verify-v2-mvp-jay"
STAGE_DIR = Path("inbox/jay/20261031-ex40-stages")
GITHUB = "https://github.com/foothold-project/foothold-lab/blob"
FEET = ("FL_foot", "FR_foot", "RL_foot", "RR_foot")
MODES = ("eval_gt", "probe_prop_only", "eval_pred")
ERRORS = ("vx_abs_error_mean_alive_mps", "vy_abs_error_mean_alive_mps",
          "wz_abs_error_mean_alive_radps")


def _run(repo: Path, *args: str) -> str:
    result = subprocess.run(["git", *args], cwd=repo, text=True,
                            capture_output=True, check=False, timeout=90)
    if result.returncode:
        raise RuntimeError(f"git {args[0]} failed with rc={result.returncode}")
    return result.stdout.strip()


def _validate_repo(repo: Path, branch: str) -> None:
    if branch != BRANCH:
        raise ValueError("unapproved publish branch")
    if Path(_run(repo, "rev-parse", "--show-toplevel")).resolve() != repo.resolve():
        raise ValueError("publish path is not the dedicated git root")
    if _run(repo, "status", "--porcelain"):
        raise ValueError("publish worktree is dirty")
    if _run(repo, "diff", "--cached", "--name-only"):
        raise ValueError("publish index is not empty")


def _sync_remote(repo: Path, branch: str) -> None:
    """Advance a clean docs worktree only when the remote is a fast forward."""
    _run(repo, "fetch", "origin", f"refs/heads/{branch}")
    local = _run(repo, "rev-parse", "HEAD")
    remote = _run(repo, "rev-parse", "FETCH_HEAD")
    if local == remote:
        return
    forward = subprocess.run(["git", "merge-base", "--is-ancestor", local, remote],
                             cwd=repo, capture_output=True, check=False)
    if forward.returncode == 0:
        _run(repo, "merge", "--ff-only", "FETCH_HEAD")
    else:
        backward = subprocess.run(["git", "merge-base", "--is-ancestor", remote, local],
                                  cwd=repo, capture_output=True, check=False)
        if backward.returncode != 0:
            raise RuntimeError("publish worktree and remote branch diverged")


def _atomic(path: Path, row: dict) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(row, ensure_ascii=False, sort_keys=True,
                              indent=2, allow_nan=False) + "\n", encoding="utf-8")
    for attempt in range(200):
        try:
            os.replace(tmp, path)
            return
        except PermissionError:
            if attempt == 199:
                raise
            time.sleep(.01)


def _history(report_root: Path, update: int) -> list[dict]:
    rows = []
    for path in report_root.glob("stage_*_m*.json"):
        row = json.loads(path.read_text(encoding="utf-8-sig"))
        if row["checkpoint_iteration"] <= update:
            rows.append(row)
    rows.sort(key=lambda row: row["checkpoint_iteration"])
    if not rows or rows[-1]["checkpoint_iteration"] != update:
        raise ValueError("current stage report is absent from chart history")
    if len({row["checkpoint_iteration"] for row in rows}) != len(rows):
        raise ValueError("duplicate chart stage")
    return rows


def _draw_charts(rows: list[dict], destination: Path, stem: str) -> list[Path]:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    ticks = [row["checkpoint_iteration"] for row in rows]
    names = sorted(rows[-1]["current"]["w15"])
    if len(names) != 39 or any(set(row["current"]["w15"]) != set(names) for row in rows):
        raise ValueError("W15 history is not 13 commands by three modes")
    result = []

    def save(fig, suffix):
        path = destination / f"{stem}_{suffix}.png"
        fig.savefig(path, dpi=150, bbox_inches="tight", metadata={"Software": "EX-40 CPU stage report"})
        plt.close(fig)
        result.append(path)

    survival = np.array([[row["current"]["w15"][name]["alive_envs_at_end"]
                          for row in rows] for name in names], dtype=float)
    fig, ax = plt.subplots(figsize=(max(7, 1.35 * len(rows) + 3), 12))
    image = ax.imshow(survival, vmin=0, vmax=64, cmap="viridis", aspect="auto")
    ax.set(yticks=range(len(names)), yticklabels=names, xticks=range(len(rows)),
           xticklabels=ticks, xlabel="checkpoint update", title="W15 survival by cell /64")
    fig.colorbar(image, ax=ax, label="survivors /64")
    save(fig, "w15_survival")

    fig, axes = plt.subplots(1, 3, figsize=(max(15, 2.2 * len(rows) + 8), 12),
                             sharey=True, constrained_layout=True)
    for ax, field, title in zip(axes, ERRORS, ("vx error m/s", "vy error m/s", "wz error rad/s")):
        values = np.array([[row["current"]["w15"][name]["tracking_medians"][field]
                            for row in rows] for name in names], dtype=float)
        if not np.isfinite(values).any():
            raise ValueError(f"no measured W15 error: {field}")
        image = ax.imshow(values, cmap="magma", aspect="auto")
        ax.set(xticks=range(len(rows)), xticklabels=ticks, xlabel="update", title=title)
        fig.colorbar(image, ax=ax)
    axes[0].set(yticks=range(len(names)), yticklabels=names)
    save(fig, "w15_error")

    fig, axes = plt.subplots(1, 2, figsize=(12, 5), constrained_layout=True)
    for mode in MODES:
        for foot in FEET:
            label = f"{mode}/{foot}"
            for ax, field, multiplier in ((axes[0], "sole_gap_p95_m", 1000),
                                          (axes[1], "mean_fz_over_mg", 1)):
                ax.plot(ticks, [row["current"]["stand"][mode]["feet"][foot][field] * multiplier
                                for row in rows], marker="o", label=label)
    axes[0].set(title="Foot sole gap p95", ylabel="mm", xlabel="update")
    axes[1].set(title="Foot load / mg", ylabel="fraction", xlabel="update")
    axes[1].legend(fontsize=6, bbox_to_anchor=(1.02, 1), loc="upper left")
    save(fig, "stand_feet")

    fig, ax = plt.subplots(figsize=(9, 5))
    for mode in MODES:
        ax.plot(ticks, [row["current"]["stand"][mode]["contact_left_right_gap_median"]
                        for row in rows], marker="o", label=f"stand/{mode}")
    w57_names = sorted(rows[-1]["current"]["w57"])
    for name in w57_names:
        if "left" in name or "right" in name:
            values = [row["current"]["w57"].get(name, {}).get("contact_left_right_gap_median")
                      for row in rows]
            if any(value is not None for value in values):
                ax.plot(ticks, values, alpha=.45, label=f"W57/{name}")
    ax.set(title="Left-right contact difference", xlabel="update", ylabel="fraction")
    ax.legend(fontsize=6, bbox_to_anchor=(1.02, 1), loc="upper left")
    save(fig, "symmetry")

    dr_names = sorted({name for row in rows for name in row["dr_current"].get("actual_samples", {})})
    fig, axes = plt.subplots(max(1, len(dr_names) + 1), 1,
                             figsize=(10, max(4, 2.3 * (len(dr_names) + 1))),
                             constrained_layout=True, squeeze=False)
    axes[0, 0].plot(ticks, [row["dr_current"].get("scale", math.nan) for row in rows], marker="o")
    axes[0, 0].set(title="DR schedule scale", xlabel="update")
    for index, name in enumerate(dr_names, 1):
        ax = axes[index, 0]
        low = [row["dr_current"].get("actual_samples", {}).get(name, {}).get("min", math.nan)
               for row in rows]
        high = [row["dr_current"].get("actual_samples", {}).get(name, {}).get("max", math.nan)
                for row in rows]
        ax.plot(ticks, low, marker="o", label="realized min")
        ax.plot(ticks, high, marker="o", label="realized max")
        ax.set(title=name, xlabel="update")
        ax.legend()
    save(fig, "dr_realized")
    return result


def _document(row: dict, charts: list[Path]) -> str:
    from foothold_s2.ex40_stage_report import markdown
    body = markdown(row).rstrip()
    if "\u2014" in body:
        raise ValueError("em dash in source report")
    links = [f"- 그림 {path.stem}: ![{path.stem}]({path.name})" for path in charts]
    source = row["current"]["source_sha256"]
    lines = [body, "", "## 8. 단계별 그림", "", *links, "",
             "## 9. 실제 완료와 재현 경로", "",
             f"- 저장본 m{row['checkpoint_iteration']} SHA256: `{row['checkpoint_sha256']}`.",
             "- 점수와 그림은 고정된 단계별 원자료에서 생성했다. 반복 폭 안의 생존 차이는 차이 없음으로 기록한다.",
             "- 원자료 SHA256:",
             *[f"  - {name}: `{digest}`" for name, digest in sorted(source.items())],
             "- 그림 SHA256:",
             *[f"  - {path.name}: `{sha256(path)}`" for path in charts],
             "- DR 실현 범위 출처: " + str(row["dr_current"].get("source", "미측")),
             "- 그림의 빈 값은 미측이며 0으로 채우지 않았다.", ""]
    result = "\n".join(lines)
    if "\u2014" in result:
        raise ValueError("em dash in published report")
    return result


def _send(text_path: Path, telegram_sender: Path) -> bool:
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    attempt = subprocess.run([sys.executable, str(telegram_sender), str(text_path)],
                             capture_output=True, text=True, timeout=90,
                             creationflags=flags, check=False)
    return attempt.returncode == 0 and attempt.stdout.split(maxsplit=1)[:1] == ["0"]


def publish(row: dict, report_root: Path, out_root: Path, repo: Path,
            telegram_sender: Path, *, available_update: int, sender=None,
            branch: str = BRANCH) -> dict:
    """One push attempt per stage, with a failed push retried at the next stage."""
    update = row["checkpoint_iteration"]
    stem = f"RESULT-EX40-{row['stage']}-m{update}"
    state_path = out_root / "stage_reports" / f"stage_{row['stage']}_m{update}.publish.json"
    state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else {}
    if state and state.get("checkpoint_sha256") != row["checkpoint_sha256"]:
        raise ValueError("publish receipt checkpoint differs from current score")
    if state.get("state") == "sent" or state.get("state") == "delivery_uncertain":
        return state
    if state.get("state") == "push_failed" and available_update <= update:
        return state
    _validate_repo(repo, branch)
    _sync_remote(repo, branch)
    folder = repo / STAGE_DIR
    folder.mkdir(parents=True, exist_ok=True)
    doc = folder / f"{stem}.md"
    if not doc.exists():
        charts = _draw_charts(_history(report_root, update), folder, stem)
        doc.write_text(_document(row, charts), encoding="utf-8")
    else:
        charts = sorted(folder.glob(f"{stem}_*.png"))
        existing = doc.read_text(encoding="utf-8")
        if (len(charts) != 5 or "## 9. 실제 완료와 재현 경로" not in existing
                or row["checkpoint_sha256"] not in existing):
            raise ValueError("existing stage document incomplete")
    created = [doc, *charts]
    paths = [path.relative_to(repo).as_posix() for path in created]
    if any(not path.startswith(STAGE_DIR.as_posix() + "/") for path in paths):
        raise ValueError("publish path escaped stage directory")
    _run(repo, "add", "--", *paths)
    staged = _run(repo, "diff", "--cached", "--name-only").splitlines()
    if any(not name.startswith(STAGE_DIR.as_posix() + "/") for name in staged):
        raise ValueError("unowned file staged")
    if staged:
        _run(repo, "commit", "-m", f"EX-40 {row['stage']} m{update} stage result (#555)")
    commit = _run(repo, "rev-parse", "HEAD")
    committed = _run(repo, "show", "--pretty=format:", "--name-only", "HEAD").splitlines()
    if not committed or any(not name.startswith(STAGE_DIR.as_posix() + "/") for name in committed):
        raise ValueError("commit contains a path outside the stage directory")
    if _run(repo, "status", "--porcelain"):
        raise ValueError("publish worktree changed during commit")
    link = f"{GITHUB}/{commit}/{STAGE_DIR.as_posix()}/{doc.name}"
    failure = None
    try:
        _run(repo, "push", "origin", f"HEAD:{branch}")
        remote = _run(repo, "ls-remote", "origin", f"refs/heads/{branch}").split()
        if not remote or remote[0] != commit:
            raise RuntimeError("pushed ref readback differs from local commit")
    except RuntimeError as exc:
        failure = str(exc)
    text_path = out_root / "stage_reports" / f"stage_{row['stage']}_m{update}.publish.telegram.txt"
    if failure:
        message = (f"EX-40 {row['stage']} m{update} 단계 보고 Git push 실패.\n"
                   f"얻은 칸 {len(row['gains'])}, 잃은 칸 {len(row['losses'])}, 차이 없는 칸 {len(row['unchanged'])}.\n"
                   f"재시도는 다음 단계 때. 로컬: {doc}")
    else:
        message = (f"EX-40 {row['stage']} m{update} 단계 결과.\n"
                   f"얻은 칸 {len(row['gains'])}, 잃은 칸 {len(row['losses'])}, 차이 없는 칸 {len(row['unchanged'])}.\n"
                   "다음 단계 주의: 생존 ±3/64 이내는 차이 없음, 연속값 반복 폭 미측.\n"
                   f"GitHub 보고서: {link}")
    text_path.write_text(message + "\n", encoding="utf-8")
    accepted = bool(sender(telegram_sender, text_path)) if sender else _send(text_path, telegram_sender)
    result = {"state": "push_failed" if failure else "sent" if accepted else "delivery_uncertain",
              "stage": row["stage"], "update": update, "commit": commit,
              "checkpoint_sha256": row["checkpoint_sha256"],
              "doc": str(doc), "link": link if not failure else None,
              "push_error": failure, "telegram_accepted": accepted,
              "telegram_sha256": sha256(text_path)}
    _atomic(state_path, result)
    return result
