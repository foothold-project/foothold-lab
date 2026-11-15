"""bf16 판정 비교 (lead 지시, 10/23 Linux 검증일): fp32 mb128(A) 대 bf16+KL fp32 mb256(B) 의 곡선을 같은 iteration 에서 견준다.

판정 규칙은 compare_rule_v1.json 에 결과 전에 고정했고, 결과 json 에 그 파일의 sha256 이 남는다. 이 스크립트는 규칙을 인자로
바꾸지 못한다(파일만 읽는다). Kit · GPU 없이 돈다.

    python foothold_s2/scripts/compare_curves.py --a <runA> --b <runB> [--a2 <runA 다른 시드>] --out result.json

run 폴더 = StartRunner 의 log_dir (tfevents 가 들어 있는 곳).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os

import numpy as np

RULE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "compare_rule_v1.json")


def load_rule(path: str = RULE_PATH) -> tuple[dict, str]:
    raw = open(path, "rb").read().replace(b"\r\n", b"\n")  # 줄끝을 LF 로 맞춰 해시한다: 윈도우(CRLF 체크아웃)와 Linux 가 같은 값
    return json.loads(raw.decode("utf-8")), hashlib.sha256(raw).hexdigest()


def read_scalars(run_dir: str, tags: list[str]) -> dict[str, dict[int, float]]:
    """tfevents → {tag: {iteration: value}}. 같은 iteration 이 여러 번이면 마지막 값."""
    from tensorboard.backend.event_processing.event_accumulator import EventAccumulator

    acc = EventAccumulator(run_dir, size_guidance={"scalars": 0})
    acc.Reload()
    have = set(acc.Tags().get("scalars", []))
    out = {}
    for t in tags:
        if t not in have:
            raise KeyError(f"{run_dir}: 태그 {t} 가 없다 (있는 태그: {sorted(have)[:8]}...)")
        out[t] = {int(e.step): float(e.value) for e in acc.Scalars(t)}
    return out


def block_means(series: dict[int, float], iterations: int, block: int) -> np.ndarray:
    missing = [i for i in range(iterations) if i not in series]
    if missing:
        raise ValueError(f"iteration {missing[:5]}... 이 없다 ({len(missing)} 개): {iterations} 회가 다 있어야 한다")
    v = np.array([series[i] for i in range(iterations)], dtype=np.float64)
    if not np.isfinite(v).all():
        raise ValueError("곡선에 NaN · inf 가 있다")
    return v.reshape(iterations // block, block).mean(axis=1)


def dist(x: np.ndarray, y: np.ndarray, scale: float) -> float:
    return float(np.mean(np.abs(x - y)) / scale)


def verdict(a: dict, b: dict, a2: dict | None, rule: dict) -> dict:
    """a · b · a2 = {tag: {iteration: value}}. 지표마다 D(B,A) 를 잡음 D(A2,A) 와 견준다."""
    n, blk = rule["iterations"], rule["block"]
    if n % blk:
        raise ValueError("iterations 가 block 의 배수가 아니다")
    per, ok_all, weak_all = {}, True, True
    for t in rule["metrics"]:
        ma, mb = block_means(a[t], n, blk), block_means(b[t], n, blk)
        scale = float(np.mean(np.abs(ma))) + 1e-12
        d_ba = dist(mb, ma, scale)
        row = {"D_BA": d_ba, "scale": scale, "blocks_A": ma.tolist(), "blocks_B": mb.tolist()}
        if a2 is not None:
            m2 = block_means(a2[t], n, blk)
            d_noise = dist(m2, ma, scale)
            limit = max(rule["noise_factor"] * d_noise, rule["floor"])
            row.update({"D_noise_A2A": d_noise, "limit": limit, "pass": d_ba <= limit, "blocks_A2": m2.tolist()})
            ok_all &= row["pass"]
        else:
            row.update({"limit": rule["floor_weak"], "weak_pass": d_ba <= rule["floor_weak"]})
            weak_all &= row["weak_pass"]
        per[t] = row
    if a2 is not None:
        v = "pass" if ok_all else "fail"
    else:
        v = "weak_pass (시드 잡음을 못 쟀다)" if weak_all else "fail (잡음 기준 없이도 floor_weak 를 넘는다)"
    return {"verdict": v, "metrics": per}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--a", required=True)
    ap.add_argument("--b", required=True)
    ap.add_argument("--a2", default=None)
    ap.add_argument("--out", required=True)
    ap.add_argument("--require_stamps", action="store_true", help="각 판 폴더의 code_stamp.json(chain.stamp)이 같을 때만 판정")
    args = ap.parse_args()
    rule, sha = load_rule()
    tags = rule["metrics"]
    runs = {"A": args.a, "B": args.b, "A2": args.a2}
    runs = {k: v for k, v in runs.items() if v}

    if args.require_stamps:                                       # 세 판이 «같은 코드» 로 돌았는지 (lead 10/20): 아니면 판정하지 않는다
        from foothold_s2.chain.stamp import compare_stamps

        chk = compare_stamps(runs)

        if not chk["comparable"]:
            res = {"verdict": "판정 불가 · " + chk["reason"].split(":")[0] if "코드 다름" in chk["reason"] else "판정 불가 · " + chk["reason"],
                   "reason": chk["reason"], "stamps": chk["stamps"], "rule_file": os.path.basename(RULE_PATH),
                   "rule_sha256": sha, "runs": {"A": args.a, "B": args.b, "A2": args.a2}}
            os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)

            with open(args.out, "w", encoding="utf-8") as f:
                json.dump(res, f, ensure_ascii=False, indent=1)

            print("VERDICT", res["verdict"], "(", chk["reason"], ")")

            return 0

    res = verdict(read_scalars(args.a, tags), read_scalars(args.b, tags), read_scalars(args.a2, tags) if args.a2 else None, rule)
    res["rule_file"] = os.path.basename(RULE_PATH)
    res["rule_sha256"] = sha
    res["runs"] = {"A": args.a, "B": args.b, "A2": args.a2}
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=1)
    print("VERDICT", res["verdict"], "rule_sha256", sha[:12])
    for t, r in res["metrics"].items():
        print(f"  {t}: D_BA {r['D_BA']:.4f}  limit {r['limit']:.4f}  noise {r.get('D_noise_A2A', float('nan')):.4f}")
    return 0 if res["verdict"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
