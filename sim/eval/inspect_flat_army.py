"""대군 촬영 MP4를 av와 numpy로 전수 검사하고 JSON 메타를 갱신한다."""
import argparse, glob, json, os, statistics
import av
import numpy as np

p = argparse.ArgumentParser(); p.add_argument("output_dir"); args = p.parse_args()
failed = []
for video in sorted(glob.glob(os.path.join(args.output_dir, "flat_army_*.mp4"))):
    c = av.open(video)
    means = [float(np.asarray(f.to_ndarray(format="gray"), dtype=np.float32).mean()) for f in c.decode(video=0)]
    c.close(); black = sum(x < 10 for x in means)
    alternating = len(means) > 1 and all((means[i] < 10) != (means[i + 1] < 10) for i in range(len(means) - 1))
    meta_path = os.path.splitext(video)[0] + ".json"
    with open(meta_path, encoding="utf-8") as f: meta = json.load(f)
    check = {"decoded_frames": len(means), "black_threshold_mean_gray": 10.0, "black_frames": black, "alternating_black": alternating, "mean_gray_min": min(means), "mean_gray_max": max(means), "mean_gray_mean": statistics.mean(means), "preview_frames": meta["frame_inspection"]["preview_frames"], "passed": len(means) == meta["frames"] and black == 0 and not alternating}
    meta["frame_inspection"] = check
    with open(meta_path, "w", encoding="utf-8") as f: json.dump(meta, f, ensure_ascii=False, indent=2)
    print(f"{os.path.basename(video)}: frames={len(means)} black={black} alternating={alternating} passed={check['passed']}")
    if not check["passed"]: failed.append(video)
if failed: raise SystemExit("FAILED: " + ", ".join(failed))
