"""CPU-only view of an existing EX29 training record. No Isaac or GPU imports."""
from pathlib import Path
import hashlib
import json

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

SOURCE = Path("C:/mai/wt/foothold-lab/lead-tmp-start-b/logs/rsl_rl/foothold_s2_23f_topdown/2026-10-24_08-20-33_ex29-td-main/training_trace/update_000100.npz")
OUT = Path(__file__).resolve().parent


def main():
    before = hashlib.sha256(SOURCE.read_bytes()).hexdigest()
    # Display an upright recorded sample for explaining the sensor, not scoring gait.
    # Trace manifest sample_env_ids[6] = 4. Selection is explicitly retained here.
    step, sample = 0, 6
    with np.load(SOURCE, allow_pickle=False) as z:
        depth = z["sensor_depth_m"][step, sample].copy()
        gt = z["gt_map"][step, sample].copy()
        reconstructed = z["refined_map"][step, sample].copy()
        meta = {
            "source": str(SOURCE), "sha256": before,
            "run": "EX-29 START-TD", "update_index": 100,
            "step_index": step, "sample_index": sample, "env_id": 4,
            "terrain_column": int(z["terrain_type"][step, sample]),
            "terrain_level": int(z["terrain_level"][step, sample]),
            "policy_used_gt": bool(z["use_gt"][step, sample]),
            "depth_finite_min_max_m": [float(depth[np.isfinite(depth)].min()), float(depth[np.isfinite(depth)].max())],
            "depth_display_limits_m": [0.2, 3.0],
            "height_display_limits_m": [-1, 1],
            "selection": "env 4, step 0, update 100: upright sample for sensor explanation, not an aggregate or performance verdict",
            "timing": "raw latest sensor frame; perception can hold a prior delivered frame between 10 Hz updates; height maps recorded in the same trace step",
            "modification": "raw arrays unchanged; plotting only; depth >=3 m displayed white; invalid pixels magenta",
        }
    assert depth.shape == (60, 60) and gt.shape == reconstructed.shape == (32, 16)
    assert np.isfinite(gt).all() and np.isfinite(reconstructed).all()
    plt.rcParams.update({"font.family": "Malgun Gothic", "axes.unicode_minus": False, "font.size": 12})
    fig, axes = plt.subplots(1, 3, figsize=(14.7, 5.6), gridspec_kw={"width_ratios": [1.2, 1, 1]})
    fig.patch.set_facecolor("#fffdfa")
    fig.suptitle("실제 깊이 영상과 높이 지도 | EX-29 START-TD · update 100", x=.04, ha="left", fontsize=19, weight="bold", y=.98)
    cmap = plt.get_cmap("gray").copy()
    cmap.set_bad("#cc278c")
    im = axes[0].imshow(np.ma.masked_invalid(depth), cmap=cmap, vmin=.2, vmax=3, interpolation="nearest")
    axes[0].set_title("RayCasterCamera · 60 × 60\n카메라 앞에서 본 깊이", loc="left", pad=12)
    axes[0].set_xlabel("가로 픽셀")
    axes[0].set_ylabel("세로 픽셀")
    fig.colorbar(im, ax=axes[0], shrink=.76, pad=.04, label="카메라 앞쪽 축 깊이 (m)")
    for ax, data, title in zip(axes[1:], (gt, reconstructed), ("정답 높이 지도 · 32 × 16", "TR-Net 복원 지도 · 32 × 16")):
        im = ax.imshow(data, cmap="viridis", vmin=-1, vmax=1, interpolation="nearest", aspect="equal")
        ax.set_title(title + "\n위에서 본 격자", loc="left", pad=12)
        ax.set_xlabel("격자 열")
        ax.set_ylabel("격자 행")
        fig.colorbar(im, ax=ax, shrink=.76, pad=.04, label="지면 높이 - 몸체 높이 (m)")
    fig.text(.04, .115, "환경 4 · step 0 · 지형 열 1 · 레벨 0. 초기 학습의 한 장이며 복원 성능 판정이 아닙니다.", fontsize=12)
    fig.text(.04, .065, "깊이: 가까우면 검정, 3 m 이상은 흰색. 원자료 최대 3.50 m. 지도 두 장은 같은 색 범위를 사용합니다.", fontsize=11)
    fig.subplots_adjust(left=.045, right=.98, bottom=.23, top=.80, wspace=.40)
    target = OUT / "ex29-depth-gt-reconstruction-u100.png"
    fig.savefig(target, dpi=150, facecolor=fig.get_facecolor())
    plt.close(fig)
    after = hashlib.sha256(SOURCE.read_bytes()).hexdigest()
    assert before == after, "source changed while plotting"
    meta["image_sha256"] = hashlib.sha256(target.read_bytes()).hexdigest()
    (OUT / "source.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"image": str(target), "source_unchanged": True, "source_sha256": before}, ensure_ascii=False))


if __name__ == "__main__":
    main()
