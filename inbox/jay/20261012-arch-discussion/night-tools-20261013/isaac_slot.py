# Isaac 변환 구간 잠금 (lead · 2026-10-13 저녁 · ASTRA 17 §6). 학습 · 평가 · 렌더 등 Isaac 을 띄우는 모든 참여자가 이것을 거친다.
# 왜: Isaac Lab 의 URDF 변환기는 usd_dir 이 없으면 「변환 시각의 초 + 시드로 정해지는 난수」 로 USD 임시 폴더 이름을 만들고
#     exist_ok=True 로 쓴다 (asset_converter_base.py:66~85). 시작을 60 초 띄워도 변환 시각은 겹칠 수 있다 (10/13 오전 사고).
# 하는 일:
#   1. 공통 OS 잠금 (_eval/slot/isaac_convert.lock · 오늘 밤 참여자 모두 같은 파일) 을 잡은 뒤에만 명령을 띄운다.
#   2. 감시 로그에 Isaac Lab 의 장면 생성 완료 줄 "[INFO]: Time taken for scene creation" 이 나오거나 명령이 끝날 때까지
#      잠금을 쥔다 (첫 USD 경로 줄은 완료 신호가 아니다 · v3.7 (v) 의 실측). 변환 시간 상한을 넘으면 명령을 끝낸다 (97).
#   3. 잠금을 쥔 채로, 로그에 적힌 USD 폴더를 공용 기록 (isaac_usd_registry.json) 과 지정한 로그 폴더의 다른 로그와 대조한다.
#      다른 실행이 같은 폴더를 썼으면 명령을 끝내고 96 으로 마친다 (그 장면은 섞였을 수 있다).
#   4. 명령이 끝난 뒤 로그의 USD 폴더가 정확히 하나가 아니면 (0 개 · 2 개 이상) 종료 코드 0 이어도 95 로 마친다.
#   5. 감시 로그가 이미 있으면 띄우기 전에 옆으로 옮긴다 (예전 판의 완료 줄을 새 판의 완료로 읽지 않게).
# 기록: --record 경로에 잠금 대기 · 보유 시간 · 폴더 · 충돌 · 종료 코드를 JSON 으로 남긴다.
# 사용: python isaac_slot.py --watch_log <로그> --record <json> [--scan_dirs d1,d2] -- <명령 ...>
#       (명령이 그 로그를 써야 한다. 보통 gpu_guard.py --log <로그> -- <Isaac 스크립트>)
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


def acquire(path, poll=1.0):
    import msvcrt
    f = open(path, "a+")
    t0 = time.time()
    while True:
        try:
            f.seek(0)
            msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
            return f, time.time() - t0
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


def other_logs_naming(folders, scan_dirs, me):
    hits = {}
    for d in scan_dirs:
        for f in glob.glob(os.path.join(d, "*.log")) + glob.glob(os.path.join(d, "attempts", "*.log*")):
            if os.path.normcase(os.path.abspath(f)) == os.path.normcase(os.path.abspath(me)):
                continue
            for k in USD_RE.findall(read(f)):
                if k in folders:
                    hits.setdefault(k, []).append(f.replace("\\", "/"))
    return hits


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--watch_log", required=True)
    ap.add_argument("--record", required=True)
    ap.add_argument("--lock", default=os.path.join(HERE, "slot", "isaac_convert.lock"))
    ap.add_argument("--registry", default=os.path.join(HERE, "slot", "isaac_usd_registry.json"))
    ap.add_argument("--scan_dirs", default="")
    ap.add_argument("--convert_timeout_s", type=float, default=1200.0)
    ap.add_argument("cmd", nargs=argparse.REMAINDER)
    a = ap.parse_args()
    cmd = a.cmd[1:] if a.cmd and a.cmd[0] == "--" else a.cmd
    assert cmd, "no command"
    rec = {"cmd": cmd, "watch_log": a.watch_log, "lock": a.lock, "t_request": time.strftime("%Y-%m-%d %H:%M:%S")}
    if os.path.exists(a.watch_log):  # 5
        moved = f"{a.watch_log}.prev.{time.strftime('%Y%m%d-%H%M%S', time.localtime(os.path.getmtime(a.watch_log)))}"
        os.replace(a.watch_log, moved)
        rec["moved_old_log"] = moved
    lk, waited = acquire(a.lock)
    rec["lock_wait_s"] = round(waited, 1)
    t_hold = time.time()
    p = subprocess.Popen(cmd)
    rec["pid"] = p.pid
    state = "exited"
    while True:
        if CONVERT_DONE in read(a.watch_log):
            state = "scene_built"
            break
        if p.poll() is not None:
            break
        if time.time() - t_hold > a.convert_timeout_s:
            state = "convert_timeout"
            kill_tree(p)
            break
        time.sleep(0.5)
    folders = sorted(set(USD_RE.findall(read(a.watch_log))))
    conflicts = {}
    if folders:
        try:
            reg = json.load(open(a.registry, encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
            reg = {}
        me = os.path.abspath(a.watch_log).replace("\\", "/")
        for k in folders:
            if k in reg and reg[k] != me:
                conflicts.setdefault(k, []).append(reg[k])
        dirs = [d for d in a.scan_dirs.split(",") if d]
        for k, v in other_logs_naming(set(folders), dirs, a.watch_log).items():
            conflicts.setdefault(k, []).extend(x for x in v if x not in conflicts.get(k, []))
        for k in folders:
            reg.setdefault(k, me)
        with open(a.registry + ".tmp", "w", encoding="utf-8") as fh:
            json.dump(reg, fh, indent=1)
        os.replace(a.registry + ".tmp", a.registry)
    rec.update({"state_at_release": state, "hold_s": round(time.time() - t_hold, 1), "usd_at_release": folders, "conflicts": conflicts})
    release(lk)
    if conflicts and p.poll() is None:
        kill_tree(p)
    rc = p.wait()
    final = sorted(set(USD_RE.findall(read(a.watch_log))))
    rec.update({"child_rc": rc, "usd_final": final, "t_end": time.strftime("%Y-%m-%d %H:%M:%S")})
    if state == "convert_timeout":
        rc = 97
    elif conflicts:
        rc = 96
    elif rc == 0 and len(final) != 1:
        rc = 95
    rec["slot_rc"] = rc
    with open(a.record, "w", encoding="utf-8") as fh:
        json.dump(rec, fh, ensure_ascii=False, indent=1)
    print(f"SLOT rc={rc} state={state} wait={rec['lock_wait_s']}s hold={rec['hold_s']}s usd={final} conflicts={conflicts}", flush=True)
    sys.exit(rc)


if __name__ == "__main__":
    main()
