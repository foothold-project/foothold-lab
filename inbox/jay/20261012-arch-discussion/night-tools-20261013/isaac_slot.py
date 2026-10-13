# Isaac 실행 관문 v2 (lead · 2026-10-13 저녁 · ASTRA 17 §6 · 17b §2.2 · §3). 학습 · 평가 · 렌더 등 Isaac 을 띄우는 참여자 모두 거친다.
# v1 결함 (17b): 장면 생성 줄 뒤에 처음 나온 USD 경로를 승인 · 최종 경로를 공용 기록과 다시 대조하지 않음 · 경로를 모르는 채 잠금 해제 ·
#   잠금 대기 중 멈춤 · 마감을 받지 않음 · 실제 공유 쓰기를 예방하지 못하고 사후 감시만 함.
# v2:
#   1. 실행마다 따로인 USD 루트 (--usd_root · 보통 <출력>/usd/<attempt>) 를 자식 환경 FOOTHOLD_USD_ROOT 로 넘긴다. 자식은
#      usd_isolate_run.py 로 띄워야 하고, 그 실행기가 변환 전에 폴더를 이 루트 아래로 정한다 (다른 실행과 공유 쓰기 자체가 없음).
#   2. 공통 OS 잠금 (--lock) 은 보조로 남긴다. 대기 중에도 --stop_file 이 생기거나 --deadline (epoch 초) 이 지나면 자식을
#      띄우지 않고 98 로 끝낸다.
#   3. 잠금은 「장면 생성 줄이 나오고 USD 폴더를 하나 이상 알게 됐을 때」 · 자식이 끝났을 때 · 변환 상한 (97) 때만 푼다.
#   4. 자식이 끝난 뒤 로그의 USD 폴더가 정확히 하나이고 (아니면 95), 그 폴더가 이 실행의 루트 아래이고 (아니면 94),
#      공용 기록 (--registry) · 지정 로그 폴더 (--scan_dirs) 의 다른 실행과 겹치지 않아야 한다 (겹치면 96). 마지막 목록으로 다시 대조한다.
#   5. 감시 로그가 이미 있으면 띄우기 전에 옆으로 옮긴다.
# 기록 (--record): attempt · 명령 · 잠금 대기 · 보유 · 해제 때와 끝날 때의 폴더 · 루트 · 충돌 · 자식 종료 코드 · slot 종료 코드.
# 사용: python isaac_slot.py --watch_log L --record R --usd_root U --attempt A [--lock K --registry G --scan_dirs d1,d2 --stop_file S
#        --deadline E] -- python gpu_guard.py ... --log L ... -- python usd_isolate_run.py <Isaac 스크립트> ...
import argparse
import glob
import json
import os
import re
import subprocess
import sys
import time

import psutil

HERE = os.path.dirname(os.path.abspath(__file__))
CONVERT_DONE = "[INFO]: Time taken for scene creation"
USD_RE = re.compile(r"IsaacLab.usd_(\d{8}_\d{6}_\d+)")


def norm(p):
    return os.path.normcase(os.path.abspath(p)).replace("\\", "/")


def stopped(a):
    if a.stop_file and os.path.exists(a.stop_file):
        return "stop file"
    if a.deadline and time.time() > a.deadline:
        return "deadline"
    return ""


def acquire(path, a, poll=1.0):
    import msvcrt
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    f = open(path, "a+")
    t0 = time.time()
    while True:
        why = stopped(a)
        if why:
            f.close()
            return None, time.time() - t0, why
        try:
            f.seek(0)
            msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
            return f, time.time() - t0, ""
        except OSError:
            time.sleep(poll)


def release(f):
    import msvcrt
    f.seek(0)
    msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
    f.close()


def read(path):
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            return fh.read()
    except FileNotFoundError:
        return ""


def kill_tree(p):
    try:
        parent = psutil.Process(p.pid)
        for c in parent.children(recursive=True):
            c.kill()
        parent.kill()
    except psutil.NoSuchProcess:
        pass


def under_root(text, k, root):
    return f"{root.lower()}/isaaclab/usd_{k}" in text.replace("\\", "/").lower()


def conflicts_of(folders, a, me):
    out = {}
    try:
        reg = json.load(open(a.registry, encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        reg = {}
    for k in folders:
        if k in reg and reg[k] != me:
            out.setdefault(k, []).append(reg[k])
    for d in [d for d in a.scan_dirs.split(",") if d]:
        for f in glob.glob(os.path.join(d, "*.log")) + glob.glob(os.path.join(d, "attempts", "*.log*")):
            if norm(f) == me:
                continue
            for k in USD_RE.findall(read(f)):
                if k in folders and f.replace("\\", "/") not in out.get(k, []):
                    out.setdefault(k, []).append(f.replace("\\", "/"))
    return out, reg


def write_reg(a, reg, folders, me):
    for k in folders:
        reg.setdefault(k, me)
    os.makedirs(os.path.dirname(a.registry) or ".", exist_ok=True)
    with open(a.registry + ".tmp", "w", encoding="utf-8") as fh:
        json.dump(reg, fh, indent=1)
    os.replace(a.registry + ".tmp", a.registry)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--watch_log", required=True)
    ap.add_argument("--record", required=True)
    ap.add_argument("--usd_root", required=True)
    ap.add_argument("--attempt", required=True)
    ap.add_argument("--lock", default=os.path.join(HERE, "slot", "isaac_convert.lock"))
    ap.add_argument("--registry", default=os.path.join(HERE, "slot", "isaac_usd_registry.json"))
    ap.add_argument("--scan_dirs", default="")
    ap.add_argument("--stop_file", default="")
    ap.add_argument("--deadline", type=float, default=0.0)
    ap.add_argument("--convert_timeout_s", type=float, default=1200.0)
    ap.add_argument("cmd", nargs=argparse.REMAINDER)
    a = ap.parse_args()
    cmd = a.cmd[1:] if a.cmd and a.cmd[0] == "--" else a.cmd
    assert cmd, "no command"
    root = norm(a.usd_root)
    me = norm(a.watch_log)
    rec = {"attempt": a.attempt, "cmd": cmd, "watch_log": me, "usd_root": root, "lock": a.lock, "t_request": time.strftime("%Y-%m-%d %H:%M:%S"),
           "t_request_epoch": time.time()}

    def finish(rc):
        rec["slot_rc"] = rc
        rec["t_end"] = time.strftime("%Y-%m-%d %H:%M:%S")
        os.makedirs(os.path.dirname(os.path.abspath(a.record)), exist_ok=True)
        with open(a.record, "w", encoding="utf-8") as fh:
            json.dump(rec, fh, ensure_ascii=False, indent=1)
        print(f"SLOT rc={rc} attempt={a.attempt} state={rec.get('state_at_release')} usd={rec.get('usd_final')} conflicts={rec.get('conflicts')}", flush=True)
        sys.exit(rc)

    if os.path.exists(a.watch_log):  # 5
        moved = f"{a.watch_log}.prev.{time.strftime('%Y%m%d-%H%M%S', time.localtime(os.path.getmtime(a.watch_log)))}"
        os.replace(a.watch_log, moved)
        rec["moved_old_log"] = moved
    lk, waited, why = acquire(a.lock, a)
    rec["lock_wait_s"] = round(waited, 1)
    if lk is None:
        rec["state_at_release"] = f"not launched ({why})"
        finish(98)
    t_hold = time.time()
    env = dict(os.environ, FOOTHOLD_USD_ROOT=root)
    p = subprocess.Popen(cmd, env=env)
    rec["pid"] = p.pid
    state = "exited"
    while True:
        text = read(a.watch_log)
        if CONVERT_DONE in text and USD_RE.search(text):
            state = "scene_built"
            break
        if p.poll() is not None:
            break
        if time.time() - t_hold > a.convert_timeout_s:
            state = "convert_timeout"
            kill_tree(p)
            break
        time.sleep(0.5)
    at_rel = sorted(set(USD_RE.findall(read(a.watch_log))))
    conf, reg = conflicts_of(at_rel, a, me)
    write_reg(a, reg, at_rel, me)
    rec.update({"state_at_release": state, "hold_s": round(time.time() - t_hold, 1), "usd_at_release": at_rel})
    release(lk)
    if conf and p.poll() is None:
        kill_tree(p)
    rc = p.wait()
    text = read(a.watch_log)
    final = sorted(set(USD_RE.findall(text)))
    conf2, reg2 = conflicts_of(final, a, me)  # 17b 2.2: the final list is checked again
    for k, v in conf2.items():
        for x in v:
            if x not in conf.get(k, []):
                conf.setdefault(k, []).append(x)
    write_reg(a, reg2, final, me)
    outside = [k for k in final if not under_root(text, k, root)]
    rec.update({"child_rc": rc, "usd_final": final, "usd_outside_root": outside, "conflicts": conf,
                "usd_changed_after_release": final != at_rel})
    if state == "convert_timeout":
        finish(97)
    if conf:
        finish(96)
    if rc == 0 and len(final) != 1:
        finish(95)
    if rc == 0 and outside:
        finish(94)
    finish(rc)


if __name__ == "__main__":
    main()
