"""S2 영상 실행 결과(videos.json)를 build_s2.py --videos 입력으로 바꾼다.

python -I -X utf8 make_video_manifest.py --run <영상 출력 폴더> --episodes <평가 episodes.json> --stage <복사할 폴더> --out <manifest.json>

- 편마다 web.mp4 · poster.jpg 를 「s2-<case_id>-<arm>」 이름으로 복사한다 (원본 이름이 모두 같아서).
- 표시 성분은 영상 실행 자신의 episode.json 점수에서 읽는다: 기준선 도달 = crossed, 끝까지 생존 = not fall.
- 같은 사례의 평가 점수와 다르면 그 차이를 manifest 에 남긴다 (영상은 판정 근거가 아니다).
- 실패한 편은 manifest 에 넣지 않고 failed 목록으로 따로 적는다.
"""
import argparse
import hashlib
import json
import shutil
from pathlib import Path

LAYER_NAMES = {"gap": "gap (틈)", "stepping_stones": "징검다리", "flat": "평지", "stairs_up": "오르막 계단"}
LABELS = {"A_success_B_fail": "차이 예시 · A 성공 B 실패", "A_fail_B_success": "차이 예시 · A 실패 B 성공"}


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--episodes", required=True)
    ap.add_argument("--stage", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    run = Path(a.run)
    index = json.loads((run / "videos.json").read_text(encoding="utf-8"))
    selection = json.loads((run / "selection.json").read_text(encoding="utf-8"))
    assert index["selection_sha256"] == sha(run / "selection.json"), "selection changed"
    slots = {s["slot"]: s for s in selection["slots"]}
    evals = {(r["case_id"], r["arm"]): r for r in
             json.loads(Path(a.episodes).read_text(encoding="utf-8"))["records"]}
    stage = Path(a.stage)
    stage.mkdir(parents=True, exist_ok=True)
    out = []
    for item in index["results"]:
        slot = slots[item["slot"]]
        case = slot["case"]
        assert (item["case_id"], item["arm"]) == (case["case_id"], slot["arm"]), item["slot"]
        d = run / f'{item["slot"]}-{case["case_id"]}-{slot["arm"]}'
        vr = json.loads((d / "video_result.json").read_text(encoding="utf-8"))
        assert vr["files"]["web.mp4"] == sha(d / "web.mp4") and vr["files"]["poster.jpg"] == sha(d / "poster.jpg")
        ep = json.loads((d / "episode.json").read_text(encoding="utf-8"))
        score = ep["score"]
        reached, survived = bool(score["crossed"]), not bool(score["fall"])
        stem = f's2-{case["case_id"]}-{slot["arm"]}'
        mp4, jpg = stage / (stem + ".mp4"), stage / (stem + ".jpg")
        shutil.copy2(d / "web.mp4", mp4)
        shutil.copy2(d / "poster.jpg", jpg)
        ev = evals.get((case["case_id"], slot["arm"]))
        ev_score = None if ev is None or ev.get("missing_reason") else ev["score"]
        same = None if ev_score is None else (
            (bool(ev_score["crossed"]), not bool(ev_score["fall"])) == (reached, survived))
        reason = slot["reason"]
        out.append({"case_id": case["case_id"], "layer": case["family"],
                    "layer_name": LAYER_NAMES.get(case["family"], case["family"]),
                    "seed": case["eval_seed"], "arm": slot["arm"],
                    "selection": "fixed" if reason == "preregistered_fixed" else reason,
                    "selection_label": LABELS.get(reason, reason),
                    "also_reasons": slot.get("also_reasons", []),
                    "mp4": str(mp4), "poster": str(jpg),
                    "mp4_sha256": sha(mp4), "poster_sha256": sha(jpg),
                    "reached": reached, "survived": survived,
                    "fall_reason": score.get("fall_reason", ""),
                    "eval_reached": None if ev_score is None else bool(ev_score["crossed"]),
                    "eval_survived": None if ev_score is None else not bool(ev_score["fall"]),
                    "same_as_eval": same, "slot": item["slot"]})
    Path(a.out).write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    side = {"planned": index["planned"], "completed": index["completed"], "failed": index["failed"],
            "differs_from_eval": [(v["case_id"], v["arm"]) for v in out if v["same_as_eval"] is False]}
    Path(a.out).with_suffix(".summary.json").write_text(json.dumps(side, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({"videos": len(out), **side}, ensure_ascii=False))


if __name__ == "__main__":
    main()
