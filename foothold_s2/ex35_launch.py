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

from foothold_s2.sol23f_contract import RESUME_PARENTS, REVERT_SEEDS, TASKS, resume_budget, validate_launch

PARENT_SHA256 = "4d987818c7e25b89e77b7541feca3ddabedd444c5b20651eb29f3681da040d9d"      # EX-35 카드 v0.3: S-B10 model_1500.pt
PARENT_ITER = 1500
EXTEND_PARENT_SHA256 = "eba0fbdd7e8cdb2f4a3750ee1125e55063fbb36eb9d1377692fad26f850fb548"      # EX-35 model_2000.pt (W19: 같은 조건 계속의 부모)
EXTEND_PARENT_ITER = 2000
EXTEND_MAX_TO_ITER = 3000                                                                # extend 가 갈 수 있는 마지막 저장본 번호(총 회차 = 번호 + 1 = 3001)
KINDS = ("main", "smoke2", "extend", "extend_smoke2", "revert")
PARENT_BY_KIND = {"main": (PARENT_SHA256, PARENT_ITER), "smoke2": (PARENT_SHA256, PARENT_ITER),
                  "extend": (EXTEND_PARENT_SHA256, EXTEND_PARENT_ITER), "extend_smoke2": (EXTEND_PARENT_SHA256, EXTEND_PARENT_ITER),
                  "revert": (PARENT_SHA256, PARENT_ITER)}     # revert 의 기본 부모(판정 파일이 다른 허용 저장본을 가리키면 parent_sha 로 바꾼다)
REVERT_DEFAULT_SEED = REVERT_SEEDS[0]
REVERT_PARENTS = {PARENT_SHA256: PARENT_ITER}    # 되돌림 허용 부모(직전 PASS 저장본). extend 의 부모 m2000 은 넣지 않는다: HOLD 저장본에서 시드만 바꾼 계속이 되기 때문
assert all(sha in RESUME_PARENTS and RESUME_PARENTS[sha] == it for sha, it in REVERT_PARENTS.items())


def check_kind_options(kind, parent_sha=None, seed=None):
    """--parent-sha · --seed 는 revert 전용이다. 다른 kind 에 주면 조용히 무시하거나 부모가 바뀌지 않게 거절한다."""
    if kind != "revert":
        if parent_sha is not None or seed is not None:
            raise ValueError(f"--parent-sha · --seed 는 revert 전용이다({kind} 에는 줄 수 없다)")
    elif parent_sha is not None and parent_sha not in REVERT_PARENTS:
        raise ValueError(f"revert 의 부모 sha 는 {sorted(REVERT_PARENTS)} 중 하나여야 한다: {parent_sha}")
assert all(sha in RESUME_PARENTS and RESUME_PARENTS[sha] == it for sha, it in PARENT_BY_KIND.values())


def sha256_file(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)

    return h.hexdigest()


def build_args(kind, device, parent, end_by, parent_sha=None, to_iter=EXTEND_MAX_TO_ITER, seed=None) -> list:
    """train_sb.py 에 줄 인자 목록(결정적). main = m1500 -> m2000 (총 2001), smoke2 = 같은 부모에서 2 회 이어 가기.
    extend = m2000 -> m<to_iter> (같은 env · 명령 구성 · 시드 · 흩기 · 판정 인자, 총 회차 = to_iter + 1, to_iter 2001..3000), extend_smoke2 = m2000 에서 2 회."""
    if kind not in KINDS:
        raise ValueError(f"kind must be one of {KINDS}")
    check_kind_options(kind, parent_sha, seed)
    common = ["--headless", "--device", device, "--num_envs", "3072", "--seed", str(seed if kind == "revert" and seed is not None else REVERT_DEFAULT_SEED if kind == "revert" else 42), "--run_name", "ex35-s2a", "--end-by", end_by, "--max-wall-s", "86400",
              "--resume_from", parent, "--command_mode", "s2a", "--clock_scatter", "on", "--p_map_off", "0.1",
              "--judge_world_frame", "on", "--judge_mask_new_task", "off"]

    if kind == "main":
        return common + ["--max_iterations", "2001"]

    if kind == "extend":
        if not EXTEND_PARENT_ITER < int(to_iter) <= EXTEND_MAX_TO_ITER:
            raise ValueError(f"extend 의 to_iter 는 {EXTEND_PARENT_ITER + 1}..{EXTEND_MAX_TO_ITER} 이어야 한다: {to_iter}")

        return common + ["--max_iterations", str(int(to_iter) + 1)]

    if kind == "revert":
        p_iter = REVERT_PARENTS[parent_sha or PARENT_SHA256]
        if not p_iter < int(to_iter) <= EXTEND_MAX_TO_ITER or int(to_iter) - p_iter > 1500:
            raise ValueError(f"revert 의 to_iter 는 {p_iter + 1}..{min(p_iter + 1500, EXTEND_MAX_TO_ITER)} 이어야 한다: {to_iter}")
        if int(common[common.index("--seed") + 1]) not in REVERT_SEEDS:
            raise ValueError(f"revert 의 시드는 원래 시드 42 로 고정한다(D21): {REVERT_SEEDS}")

        return common + ["--max_iterations", str(int(to_iter) + 1)]

    return common + ["--max_iterations", "1501", "--smoke-updates", "2"]


def receipt(kind, args, parent, check_sha=True, parent_sha=None) -> dict:
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
    check_kind_options(kind, parent_sha, None)
    parent_sha_default, parent_iter = PARENT_BY_KIND[kind]
    parent_sha = parent_sha or parent_sha_default
    parent_iter = REVERT_PARENTS[parent_sha] if kind == "revert" else parent_iter
    validate_launch(ns, verify_parent=check_sha)
    actual = sha256_file(parent) if check_sha else None

    if check_sha and actual != parent_sha:
        raise ValueError(f"부모 SHA-256 이 카드와 다르다: {actual} != {parent_sha}")
    remaining = 2 if kind.endswith("smoke2") else resume_budget(ns.max_iterations, parent_iter)["remaining"]
    first = parent_iter + 1

    return {"kind": kind, "task": TASKS["SB"], "parent": parent, "parent_sha256": actual, "expected_parent_sha256": parent_sha, "parent_iter": parent_iter,
            "args": pairs, "remaining_updates": remaining, "first_iter": first, "last_iter": first + remaining - 1,
            "contract": "walkturn_v1", "validate_launch": "ok", "note": "기동은 팀장 승인 뒤 lead 가 한다. 이 영수증은 승인이 아니다.",
            **({"decision_basis": "확정 D21: 되돌림 시드 42 유지. D06: 같은 조건 상한은 부모 뒤 1500회, 기본 to_iter 3000."} if kind == "revert" else {})}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="EX-35 기동 인자 영수증")
    ap.add_argument("kind", choices=KINDS)
    ap.add_argument("device")
    ap.add_argument("parent")
    ap.add_argument("--end-by", default=None)
    ap.add_argument("--to-iter", type=int, default=EXTEND_MAX_TO_ITER, help="extend 전용: 마지막 저장본 번호(2001..3000, 기본 3000)")
    ap.add_argument("--seed", type=int, default=None, help=f"revert 전용: 원 시드 유지(기본 {REVERT_DEFAULT_SEED}, 허용 {REVERT_SEEDS})")
    ap.add_argument("--parent-sha", default=None, help="revert 전용: 부모 저장본 sha256(판정 파일이 가리키는 직전 단계, 허용표 안, 기본 m1500)")
    ap.add_argument("--print-args", action="store_true", help="영수증 대신 train_sb.py 인자만 한 줄씩")
    ap.add_argument("--no-sha", action="store_true", help="시험 전용: 부모 파일 SHA 를 재지 않음")
    a = ap.parse_args(argv)
    end_by = a.end_by or (datetime.now(timezone.utc).astimezone() + timedelta(hours=24)).isoformat(timespec="seconds")
    args = build_args(a.kind, a.device, a.parent, end_by, parent_sha=a.parent_sha, to_iter=a.to_iter, seed=a.seed)
    rc = receipt(a.kind, args, a.parent, check_sha=not a.no_sha, parent_sha=a.parent_sha)
    text = "\n".join(args) if a.print_args else json.dumps(rc, ensure_ascii=False, indent=1, sort_keys=True)
    sys.stdout.buffer.write((text + "\n").encode("utf-8"))    # Windows 텍스트 모드의 CRLF 변환을 피한다(줄끝 LF 고정)
    sys.stdout.flush()

    return 0


if __name__ == "__main__":
    sys.exit(main())
