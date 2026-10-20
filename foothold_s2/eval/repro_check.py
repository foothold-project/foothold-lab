"""S0 표본 재현 (isaac311 판): S0 기준선은 isaac311-moects 로 쟀다. 환경을 isaac311(rsl-rl-lib 3.1.2)로 통일하기 전에
같은 입력이 같은 값을 내는지 본다 (lead SC-9).

  - v2 · NVIDIA 축 1 rough6 0.5 m/s 6 칸: 판 단위로 모든 열이 S0 와 문자열까지 같다 (비트 일치)
  - v2 축 2 시드 42 아홉 칸: 값 · 문턱 · 통과가 S0 와 같다
  (E1 은 isaac311 로 못 돈다: robot_lab · rsl_rl 포크가 moects 에만 있음 → v2 · NVIDIA 로 재현)
결과는 `<out>/repro_result.json` 의 verdict ("match" · "mismatch" · "error"). 불일치여도 종료 코드는 0 이다: v2 기준 판을 같은 환경에서 다시 재므로 S1 대 v2 비교는
재현 결과와 상관없이 성립해서, 사슬을 막지 않고 알림 문장에 verdict 만 싣는다 (lead 10/20 21:xx).

    python -m foothold_s2.eval.repro_check --out <폴더>        (GPU 는 환경 변수 DEVICE=cuda:N, run_kit.sh 와 같다)
"""

import argparse
import json
import os
import subprocess
import sys

from foothold_s2.eval import manifest, s0_chain

S0_ROOT = "C:/Users/AI-WS01/s2_lab/eval_new/s0"
S0_V2_AXIS1 = S0_ROOT + "/v2/axis1/rough6/v0.5/axis1_raw.csv"
S0_NV_AXIS1 = S0_ROOT + "/nvidia/axis1/rough6/v0.5/axis1_raw.csv"
S0_V2_AXIS2 = S0_ROOT + "/v2/axis2/axis2_cells.csv"
# E1 은 isaac311 로 못 돈다: E1 정책(MoE-CTS student)이 robot_lab 과 그 rsl_rl 포크(C:/isaac/ext/go2_rl_robotlab/source/rsl_rl)를 쓰고,
# isaac311 에는 둘 다 없다. 그래서 같은 설치 rsl_rl 3.1.2 로 도는 v2 · NVIDIA 로 재현한다 (E1 평가는 isaac311-moects 에 남는다).


def compare_rows(new_rows, old_rows, key_cols):
    """두 표를 key_cols 로 맞대 모든 열이 같은지. 반환: dict(ok, joined, only_new, only_old, differing_keys, differing_cols)."""
    def index(rows):
        return {tuple(str(r[c]) for c in key_cols): r for r in rows}

    new, old = index(new_rows), index(old_rows)
    keys = sorted(set(new) & set(old))
    diff_keys, diff_cols = [], set()

    for k in keys:
        cols = [c for c in old[k] if str(new[k].get(c)) != str(old[k][c])]

        if cols:
            diff_keys.append(list(k))
            diff_cols.update(cols)

    only_new, only_old = len(set(new) - set(old)), len(set(old) - set(new))

    return {"ok": not diff_keys and not only_new and not only_old and bool(keys), "joined": len(keys),
            "only_new": only_new, "only_old": only_old, "differing_keys": diff_keys[:10],
            "differing_cols": sorted(diff_cols)}


def run_kit(out, args):
    run = os.path.join(manifest.EVAL_DIR, "run_kit.sh").replace("\\", "/")

    return subprocess.call([s0_chain.find_bash(), run, out] + args, env=dict(os.environ))


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    parser.add_argument("--skip_run", action="store_true", help="이미 있는 결과만 비교 (시험용)")
    args = parser.parse_args(argv)
    os.makedirs(args.out, exist_ok=True)
    v2_kind, v2_ckpt = s0_chain.CHECKPOINTS["v2"]
    nv_kind, nv_ckpt = s0_chain.CHECKPOINTS["nvidia"]
    runs = [  # (이름, 폴더, run_eval 인자, 새 결과 파일, S0 파일, 맞대는 열)
        ("v2_axis1_rough6_v0.5", ["axis1", "--policy", v2_kind, "--checkpoint", v2_ckpt, "--label", "v2",
                                  "--set", "rough6", "--speed", "0.5"], "axis1_raw.csv", S0_V2_AXIS1,
         ("terrain", "env_id", "episode")),
        ("nvidia_axis1_rough6_v0.5", ["axis1", "--policy", nv_kind, "--checkpoint", nv_ckpt, "--label", "nvidia",
                                      "--set", "rough6", "--speed", "0.5"], "axis1_raw.csv", S0_NV_AXIS1,
         ("terrain", "env_id", "episode")),
        ("v2_axis2_seed42", ["axis2", "--policy", v2_kind, "--checkpoint", v2_ckpt, "--label", "v2", "--seed", "42"],
         "axis2_cells.csv", S0_V2_AXIS2, ("cell",))]
    result = {"checks": {}, "rc": {}}

    for name, run_args, new_name, old_path, keys in runs:
        out = os.path.join(args.out, name)

        if not args.skip_run:
            result["rc"][name] = run_kit(out, run_args)

        new_path = os.path.join(out, new_name)

        if not os.path.isfile(new_path):
            result["checks"][name] = {"ok": False, "problem": "새 결과 없음 %s" % new_path}
            continue

        result["checks"][name] = compare_rows(manifest.read_csv(new_path), manifest.read_csv(old_path), keys)

    result["ok"] = all(c["ok"] for c in result["checks"].values()) and len(result["checks"]) == len(runs)
    missing = [n for n, c in result["checks"].items() if "problem" in c]
    result["verdict"] = "error" if missing else ("match" if result["ok"] else "mismatch")

    with open(os.path.join(args.out, "repro_result.json"), "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=1)

    print("REPRO", result["verdict"], json.dumps(result["checks"], ensure_ascii=False)[:800], flush=True)

    return 0                                                          # 판정은 verdict 로, 사슬은 막지 않는다


if __name__ == "__main__":
    sys.exit(main())
