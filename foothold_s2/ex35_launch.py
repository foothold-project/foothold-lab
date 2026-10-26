"""EX-35 기동 줄 생성기와 인자 영수증 (verifier 막음 1 의 2). 순수 CPU, Kit 없음.

`run_sb.sh` 는 1501 고정이고 S2a · 흩기 · 부모 · p_map_off 를 넣지 않는다. 이 모듈이 EX-35 의 인자를 한 곳에서 정해, 기동 전에 `validate_launch` 로 검증하고
영수증(JSON)을 낸다. 부모 SHA 가 카드와 다르면 거절한다. 학습 기동은 팀장 승인 뒤 lead 가 한다(이 모듈은 줄을 만들 뿐 실행하지 않는다).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from foothold_s2.sol23f_contract import TASKS, resume_budget, validate_launch

PARENT_SHA256 = "4d987818c7e25b89e77b7541feca3ddabedd444c5b20651eb29f3681da040d9d"      # EX-35 카드 v0.3: S-B10 model_1500.pt
PARENT_ITER = 1500
KINDS = ("main", "smoke2")


def sha256_file(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)

    return h.hexdigest()


def build_args(kind, device, parent, end_by, parent_sha=PARENT_SHA256) -> list:
    """train_sb.py 에 줄 인자 목록(결정적). main = m1500 -> m2000 (총 2001), smoke2 = 같은 부모에서 2 회 이어 가기."""
    if kind not in KINDS:
        raise ValueError(f"kind must be one of {KINDS}")
    common = ["--headless", "--device", device, "--num_envs", "3072", "--seed", "42", "--run_name", "ex35-s2a", "--end-by", end_by, "--max-wall-s", "86400",
              "--resume_from", parent, "--command_mode", "s2a", "--clock_scatter", "on", "--p_map_off", "0.1",
              "--judge_world_frame", "on", "--judge_mask_new_task", "off"]

    if kind == "main":
        return common + ["--max_iterations", "2001"]

    return common + ["--max_iterations", "1501", "--smoke-updates", "2"]


def receipt(kind, args, parent, check_sha=True, parent_sha=PARENT_SHA256) -> dict:
    """인자 영수증: 사람이 읽는 값 + validate_launch 통과 + 부모 SHA 대조 + 예상 회차."""
    pairs, i = {}, 0

    while i < len(args):
        tok = args[i]

        if tok.startswith("--") and i + 1 < len(args) and not args[i + 1].startswith("--"):
            pairs[tok[2:]] = args[i + 1]
            i += 2
        else:
            pairs[tok[2:]] = True
            i += 1

    ns = SimpleNamespace(variant="SB", task=TASKS["SB"], agent="rsl_rl_cfg_entry_point", distributed=False, map_input=None, force_gt=False,
                         max_wall_s=float(pairs["max-wall-s"]), end_by=pairs["end-by"], num_envs=int(pairs["num_envs"]), seed=int(pairs["seed"]),
                         max_iterations=int(pairs["max_iterations"]), smoke_updates=int(pairs["smoke-updates"]) if "smoke-updates" in pairs else None,
                         resume_from=pairs["resume_from"], p_map_off=float(pairs["p_map_off"]), command_mode=pairs["command_mode"], clock_scatter=pairs["clock_scatter"])
    validate_launch(ns)
    actual = sha256_file(parent) if check_sha else None

    if check_sha and actual != parent_sha:
        raise ValueError(f"부모 SHA-256 이 카드와 다르다: {actual} != {parent_sha}")
    remaining = 2 if kind == "smoke2" else resume_budget(ns.max_iterations, PARENT_ITER)["remaining"]
    first = PARENT_ITER + 1

    return {"kind": kind, "task": TASKS["SB"], "parent": parent, "parent_sha256": actual, "expected_parent_sha256": parent_sha, "parent_iter": PARENT_ITER,
            "args": pairs, "remaining_updates": remaining, "first_iter": first, "last_iter": first + remaining - 1,
            "contract": "walkturn_v1", "validate_launch": "ok", "note": "기동은 팀장 승인 뒤 lead 가 한다. 이 영수증은 승인이 아니다."}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="EX-35 기동 인자 영수증")
    ap.add_argument("kind", choices=KINDS)
    ap.add_argument("device")
    ap.add_argument("parent")
    ap.add_argument("--end-by", default=None)
    ap.add_argument("--print-args", action="store_true", help="영수증 대신 train_sb.py 인자만 한 줄씩")
    ap.add_argument("--no-sha", action="store_true", help="시험 전용: 부모 파일 SHA 를 재지 않음")
    a = ap.parse_args(argv)
    end_by = a.end_by or (datetime.now(timezone.utc).astimezone() + timedelta(hours=24)).isoformat(timespec="seconds")
    args = build_args(a.kind, a.device, a.parent, end_by)
    rc = receipt(a.kind, args, a.parent, check_sha=not a.no_sha)
    print("\n".join(args) if a.print_args else json.dumps(rc, ensure_ascii=False, indent=1, sort_keys=True))

    return 0


if __name__ == "__main__":
    sys.exit(main())
