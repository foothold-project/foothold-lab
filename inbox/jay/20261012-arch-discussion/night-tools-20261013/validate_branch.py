# 갈래 학습 한 군이 등록한 실행 계약대로 끝났는지 검증 (lead · 2026-10-13 저녁 · ASTRA 17 §4 「밤 학습 스크립트는 아직 준비 완료가 아니다」).
# 확인: guard 요약 (종료 0 · guard 정지 아님) · slot 기록 (변환 잠금 · USD 폴더 하나 · 충돌 없음) · 로그에 Traceback 없음 ·
#       이번 로그에 "[BRANCH] done <tag>" · result.json 의 args 가 요청 (부모 경로 · 시드 · 환경 수 · update · cmdr · tag) 과 같음 ·
#       부모 체크포인트 sha256 이 지금 파일과 같음 · 마지막 상태 iter_from_counter = 부모 iter + update + 1 ·
#       saves.json 마지막이 「save it=<부모+update> last=True」 · 필수 체크포인트 (부모+update-2000 · 부모+update) 존재.
# 통과하면 <tag>/validate_stamp.json 에 attempt · 필수 체크포인트와 result.json 의 sha256 을 남긴다. 재사용은 이 stamp 가
# 지금 파일 해시와 같고 검증이 다시 통과할 때만이다 (파일 존재만으로 재사용하지 않는다).
# 사용: python validate_branch.py --tag T --parent P --seed S --num_envs N --updates U --cmdr on|off [--attempt A] [--stamp] [--reuse_check]
# 종료: 0 통과 · 1 실패 (이유를 한 줄로 출력)
import argparse
import hashlib
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BR = os.environ.get("BRANCH_OUT", os.path.join(HERE, "..", "out", "branch"))


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def check(a):
    d = os.path.join(BR, a.tag)
    try:
        g = json.load(open(os.path.join(BR, f"{a.tag}.guard.json"), encoding="utf-8"))
        if g.get("exit_code") != 0 or g.get("stopped_by_guard"):
            return f"guard exit {g.get('exit_code')} stopped {g.get('stopped_by_guard')}", None
        s = json.load(open(os.path.join(BR, f"{a.tag}.slot.json"), encoding="utf-8"))
        if s.get("slot_rc") != 0 or s.get("conflicts") or len(s.get("usd_final", [])) != 1:
            return f"slot rc {s.get('slot_rc')} usd {s.get('usd_final')} conflicts {s.get('conflicts')}", None
        log = open(os.path.join(BR, f"{a.tag}.log"), encoding="utf-8", errors="replace").read()
        if "Traceback (most recent call last)" in log:
            return "Python Traceback in log", None
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
        if r["meta"].get("parent_sha256") != sha(a.parent):
            return "parent sha256 differs from the file now", None
        m = re.search(r"model_(\d+)\.pt$", a.parent)
        p_it = int(m.group(1))
        end_it = p_it + a.updates
        if r["final_state"].get("iter_from_counter") != end_it + 1:
            return f"final iter_from_counter {r['final_state'].get('iter_from_counter')} want {end_it + 1}", None
        saves = json.load(open(os.path.join(d, "saves.json"), encoding="utf-8"))
        if not saves or saves[-1].get("where") != f"save it={end_it} last=True":
            return f"last save {saves[-1].get('where') if saves else None!r}", None
        need = [f"model_{end_it - 2000}.pt", f"model_{end_it}.pt"]
        for f in need:
            if not os.path.exists(os.path.join(d, f)) or os.path.getsize(os.path.join(d, f)) == 0:
                return f"missing {f}", None
        hashes = {f: sha(os.path.join(d, f)) for f in need + ["result.json"]}
        return "", hashes
    except Exception as ex:  # noqa: BLE001
        return f"unreadable: {type(ex).__name__}: {ex}", None


def main():
    ap = argparse.ArgumentParser()
    for k in ("tag", "parent", "cmdr"):
        ap.add_argument(f"--{k}", required=True)
    for k in ("seed", "num_envs", "updates"):
        ap.add_argument(f"--{k}", type=int, required=True)
    ap.add_argument("--attempt", default="")
    ap.add_argument("--stamp", action="store_true")
    ap.add_argument("--reuse_check", action="store_true", help="pass only if a stamp exists, matches the files now, and validation passes")
    a = ap.parse_args()
    why, hashes = check(a)
    sp = os.path.join(BR, a.tag, "validate_stamp.json")
    if not why and a.reuse_check:
        try:
            st = json.load(open(sp, encoding="utf-8"))
            if st.get("sha256") != hashes:
                why = "stamp does not match the files now"
        except FileNotFoundError:
            why = "no validate stamp"
    if why:
        print(f"INVALID {a.tag}: {why}")
        sys.exit(1)
    if a.stamp:
        json.dump({"attempt": a.attempt, "sha256": hashes}, open(sp, "w", encoding="utf-8"), indent=1)
    print(f"VALID {a.tag} " + " ".join(f"{k}={v[:12]}" for k, v in hashes.items()))
    sys.exit(0)


if __name__ == "__main__":
    main()
