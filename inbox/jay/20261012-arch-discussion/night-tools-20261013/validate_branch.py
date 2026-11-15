# 갈래 학습 한 군이 등록한 실행 계약대로 「이번 시도에서」 끝났는지 검증 v2 (lead · 2026-10-13 저녁 · ASTRA 17 §4 · 17b §2.1 · §2.3).
# v1 결함 (17b): 체크포인트를 열지 않고 해시만 계산 · saves 의 파일 이름 미검사 · slot 의 자식 종료 코드 · 명령 미대조 ·
#   attempt 를 사후 문자열로만 붙임 · 이전 시도의 결과를 새 시도의 성공으로 다시 적을 수 있음 · 금지 오류가 Traceback 뿐.
# v2 확인 (하나라도 어긋나면 무효):
#   slot 기록: attempt 가 --attempt 와 같음 · slot_rc 0 · child_rc 0 · 해제 상태 scene_built · USD 폴더 하나 · 루트 밖 없음 · 충돌 없음 ·
#     명령에 usd_isolate_run.py 와 branch_run.py --tag <tag> 가 있음 · 요청 시각 ≥ --since
#   guard: 종료 0 · guard 정지 아님
#   로그: Traceback 없음 · 로봇 루트 참조 실패 없음 · "[BRANCH] done <tag>"
#   result.json: args (부모 경로 · 시드 · 환경 수 · update · cmdr · tag) · 부모 sha256 이 지금 파일과 같음 · t_start ≥ --since ·
#     iter_from_counter = 부모 iter + update + 1
#   saves.json: 마지막이 「save it=<끝> last=True」 이고 file 이 model_<끝>.pt
#   체크포인트 (CPU 로 엶): 부모+update-2000 · 부모+update 두 파일의 iter · model_state_dict 실수 tensor 유한 ·
#     branch_lib.sha_tensor (정렬한 키) 가 saves.json 의 같은 file 항목 model_sha 와 같음
#   bundle.json · bundle.npz 존재 · bundle 의 부모 sha256 이 부모 파일과 같음
# 통과하면 <tag>/validate_stamp.json 에 attempt 와 파일 해시 (체크포인트 · result · saves · bundle · 로그 · guard · slot) 를 남긴다.
# 재사용 (--reuse_check) 은 stamp 가 있고, 지금 파일 해시가 같고, stamp 를 만든 attempt 의 기록으로 위 검증이 다시 통과할 때만이다.
# 재사용은 원래 attempt 를 그대로 보고하고 새 attempt 로 다시 적지 않는다.
# 사용: python validate_branch.py --tag T --parent P --seed S --num_envs N --updates U --cmdr on|off --attempt A --since EPOCH [--stamp]
#       python validate_branch.py ... --reuse_check
import argparse
import hashlib
import json
import os
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
BR = os.environ.get("BRANCH_OUT", os.path.join(HERE, "..", "out", "branch"))
ROOT_REF = "</World/envs/env_0/Robot>: Unresolved reference"


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def ckpt_check(path, want_iter, want_sha):
    import torch
    sys.path.insert(0, HERE)
    import branch_lib as B
    try:
        ck = torch.load(path, map_location="cpu", weights_only=False)
    except Exception as ex:  # noqa: BLE001
        return f"{os.path.basename(path)} not loadable: {type(ex).__name__}"
    if not isinstance(ck, dict) or "model_state_dict" not in ck:
        return f"{os.path.basename(path)} has no model_state_dict"
    if ck.get("iter") != want_iter:
        return f"{os.path.basename(path)} iter {ck.get('iter')} want {want_iter}"
    sd = ck["model_state_dict"]
    for k, v in sd.items():
        if torch.is_tensor(v) and v.is_floating_point() and not torch.isfinite(v).all():
            return f"{os.path.basename(path)} non-finite {k}"
    if B.sha_tensor(*[sd[k] for k in sorted(sd)]) != want_sha:
        return f"{os.path.basename(path)} tensors differ from the saved model_sha"
    return ""


def check(a, attempt):
    d = os.path.join(BR, a.tag)
    try:
        s = json.load(open(os.path.join(BR, f"{a.tag}.slot.json"), encoding="utf-8"))
        if s.get("attempt") != attempt:
            return f"slot attempt {s.get('attempt')!r} want {attempt!r}", None
        if s.get("slot_rc") != 0 or s.get("child_rc") != 0 or s.get("state_at_release") != "scene_built":
            return f"slot rc {s.get('slot_rc')} child_rc {s.get('child_rc')} state {s.get('state_at_release')}", None
        if len(s.get("usd_final", [])) != 1 or s.get("usd_outside_root") or s.get("conflicts"):
            return f"slot usd {s.get('usd_final')} outside {s.get('usd_outside_root')} conflicts {s.get('conflicts')}", None
        cmd = [str(x).replace("\\", "/") for x in s.get("cmd", [])]
        if not any(x.endswith("usd_isolate_run.py") for x in cmd) or not any(x.endswith("branch_run.py") for x in cmd):
            return "slot cmd is not usd_isolate_run.py + branch_run.py", None
        if "--tag" not in cmd or cmd[cmd.index("--tag") + 1] != a.tag:
            return "slot cmd tag differs", None
        if s.get("t_request_epoch", 0) < a.since:
            return "slot record is older than this attempt", None
        g = json.load(open(os.path.join(BR, f"{a.tag}.guard.json"), encoding="utf-8"))
        if g.get("exit_code") != 0 or g.get("stopped_by_guard"):
            return f"guard exit {g.get('exit_code')} stopped {g.get('stopped_by_guard')}", None
        log = open(os.path.join(BR, f"{a.tag}.log"), encoding="utf-8", errors="replace").read()
        if "Traceback (most recent call last)" in log:
            return "Python Traceback in log", None
        if ROOT_REF in log:
            return "robot root reference unresolved in log", None
        if f"[BRANCH] done {a.tag}" not in log:
            return "log has no [BRANCH] done line for this tag", None
        r = json.load(open(os.path.join(d, "result.json"), encoding="utf-8"))
        ra = r["meta"]["args"]
        want = {"seed": a.seed, "num_envs": a.num_envs, "updates": a.updates, "cmdr": a.cmdr, "tag": a.tag}
        for k, v in want.items():
            if ra.get(k) != v:
                return f"result arg {k}={ra.get(k)!r} want {v!r}", None
        if os.path.normcase(os.path.abspath(ra.get("parent", ""))) != os.path.normcase(os.path.abspath(a.parent)):
            return f"result parent {ra.get('parent')!r}", None
        psha = sha(a.parent)
        if r["meta"].get("parent_sha256") != psha:
            return "parent sha256 differs from the file now", None
        if time.mktime(time.strptime(r["meta"]["t_start"], "%Y-%m-%d %H:%M:%S")) < a.since - 1:
            return "result is older than this attempt", None
        p_it = int(re.search(r"model_(\d+)\.pt$", a.parent).group(1))
        end_it = p_it + a.updates
        if r["final_state"].get("iter_from_counter") != end_it + 1:
            return f"final iter_from_counter {r['final_state'].get('iter_from_counter')} want {end_it + 1}", None
        saves = json.load(open(os.path.join(d, "saves.json"), encoding="utf-8"))
        if not saves or saves[-1].get("where") != f"save it={end_it} last=True" or saves[-1].get("file") != f"model_{end_it}.pt":
            return f"last save {saves[-1].get('where') if saves else None!r} file {saves[-1].get('file') if saves else None!r}", None
        by = {x.get("file"): x for x in saves}
        need = [(end_it - 2000), end_it]
        for it in need:
            f = f"model_{it}.pt"
            if f not in by:
                return f"no save record for {f}", None
            why = ckpt_check(os.path.join(d, f), it, by[f].get("model_sha"))
            if why:
                return why, None
        for f in ("bundle.json", "bundle.npz"):
            if not os.path.exists(os.path.join(d, f)):
                return f"missing {f}", None
        if json.load(open(os.path.join(d, "bundle.json"), encoding="utf-8"))["meta"].get("parent_sha256") != psha:
            return "bundle parent sha256 differs", None
        files = {f"{a.tag}/model_{it}.pt": os.path.join(d, f"model_{it}.pt") for it in need}
        files.update({f"{a.tag}/{f}": os.path.join(d, f) for f in ("result.json", "saves.json", "bundle.json", "bundle.npz")})
        files.update({f"{a.tag}{e}": os.path.join(BR, f"{a.tag}{e}") for e in (".log", ".guard.json", ".slot.json")})
        return "", {k: sha(v) for k, v in files.items()}
    except Exception as ex:  # noqa: BLE001
        return f"unreadable: {type(ex).__name__}: {ex}", None


def main():
    ap = argparse.ArgumentParser()
    for k in ("tag", "parent", "cmdr"):
        ap.add_argument(f"--{k}", required=True)
    for k in ("seed", "num_envs", "updates"):
        ap.add_argument(f"--{k}", type=int, required=True)
    ap.add_argument("--attempt", default="")
    ap.add_argument("--since", type=float, default=0.0)
    ap.add_argument("--stamp", action="store_true")
    ap.add_argument("--reuse_check", action="store_true")
    a = ap.parse_args()
    sp = os.path.join(BR, a.tag, "validate_stamp.json")
    if a.reuse_check:
        try:
            st = json.load(open(sp, encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
            print(f"INVALID {a.tag}: no validate stamp")
            sys.exit(1)
        a.since = st.get("since", 0.0)
        why, hashes = check(a, st.get("attempt", ""))
        if not why and st.get("sha256") != hashes:
            why = "stamp does not match the files now"
        if why:
            print(f"INVALID {a.tag}: {why}")
            sys.exit(1)
        print(f"REUSE {a.tag} attempt {st.get('attempt')} (original attempt kept)")
        sys.exit(0)
    if not a.attempt:
        print(f"INVALID {a.tag}: --attempt is required")
        sys.exit(1)
    why, hashes = check(a, a.attempt)
    if why:
        print(f"INVALID {a.tag}: {why}")
        sys.exit(1)
    if a.stamp:
        json.dump({"attempt": a.attempt, "since": a.since, "sha256": hashes, "t": time.strftime("%Y-%m-%d %H:%M:%S")},
                  open(sp, "w", encoding="utf-8"), indent=1)
    print(f"VALID {a.tag} attempt {a.attempt}")
    sys.exit(0)


if __name__ == "__main__":
    main()
