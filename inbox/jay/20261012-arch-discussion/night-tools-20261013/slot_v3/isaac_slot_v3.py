# Isaac 실행 관문 v3 (lead 세션 · Claude 하위 작업 작성 · 2026-10-13 밤 · ASTRA 17c §2.2 · §4 · §5 반영). v2 (isaac_slot.py) 는 고치지 않고 둔다.
# v2 결함 (17c 재현):
#   - 루트 안 판정이 로그 전체 문자열에 허용 경로가 한 번 있는지만 봤다. 같은 basename 의 「자기 루트/IsaacLab/usd_K」 와
#     「C:/other/IsaacLab/usd_K」 를 같이 쓰면 하나로 합쳐져 rc 0 · outside [] · conflicts {} 였다.
#   - 루트 밖 경로를 자식이 끝난 뒤에야 94 로 거부했다 (긴 학습이면 끝까지 돈다).
#   - registry 최종 read · merge · write 가 잠금 밖이고 .tmp 이름이 공통이며 키가 basename 이었다 (B 기록 손실 · 서로 다른 절대 루트의
#     같은 basename 을 충돌로 셈).
#   - 로그 스캔이 attempts/*.log* 만 봐서 attempts/<tag>.<시각>/ 하위 로그를 못 읽었다.
# v3:
#   1. 로그에서 USD 변환 폴더를 「앞의 경로까지 붙은 절대 경로」 로 뽑아 하나하나 정규화 (normpath · normcase · 구분자 /) 해서 판정한다.
#      루트 안 = 정확히 <usd_root>/IsaacLab/usd_<날짜>_<시각>_<값>. 상대 경로처럼 풀 수 없는 것은 밖으로 센다.
#      드라이브 없는 /tmp/... 는 이 프로세스의 현재 드라이브로 푼다 (Windows 가 그렇게 연다).
#   2. 장면 생성 줄이 나와 잠금을 풀기 직전에 판정해서, 루트 밖 (94) · assigned 미연결 (91) · 충돌 (96) · registry 오류 (90) 가 있으면
#      자식을 그 자리에서 끝낸다. 잠금을 푼 뒤에도 자식이 끝날 때까지 로그를 이어 읽어 (WATCH_S 마다 새로 붙은 줄만) 새 폴더가
#      루트 밖이거나 assigned 에 없으면 바로 끝낸다. 자식이 끝난 뒤 로그 전체로 최종 재대조한다 (v2 와 같음).
#   3. <usd_root>/assigned.jsonl (usd_isolate_run v2 · v3 가 변환 전에 쓰는 줄) 과 로그의 사용 폴더를 잇는다. 로그 폴더가 assigned 에 없거나,
#      assigned 가 비었는데 변환 흔적 (로그 폴더 또는 importer 로그 줄) 이 있으면 91.
#   4. registry: read · 충돌 확인 · merge · write 를 <registry>.lock 잠금 안에서 하고, 고유 임시 파일 이름 (pid · uuid) 으로 쓴 뒤 os.replace.
#      키는 정규화한 절대 폴더 경로. v2 가 남긴 basename 키는 그 값 (로그 경로) 의 로그를 열어 절대 경로로 다시 대조한다.
#      읽을 수 없거나 JSON 이 아니면 덮어쓰지 않고 90.
#   5. 로그 스캔: --scan_dirs 마다 *.log · *.log.prev.* · attempts/*.log* · attempts/*/*.log* · _attempts/*.log* · _attempts/*/*.log*.
#   6. (ASTRA 17d 2.6) --expect_conversions 0 | 1 (기본 1 = v2 와 같은 「USD 폴더 정확히 하나」). 같은 값을 자식 환경
#      FOOTHOLD_EXPECT_CONVERSIONS 로 넘겨 usd_isolate_run_v3 가 기대 밖 변환을 쓰기 전에 막게 한다.
#      0: 장면 생성 줄만으로 잠금을 풀고 (폴더를 기다리지 않음) USD 폴더 0 개가 정상이다. 그러나 변환 시도 흔적 (assigned.jsonl 의 어떤 줄 ·
#      로그의 USD 폴더 · importer 로그 줄 · isolate_state.json 의 blocked) 이 하나라도 있으면 89. 「폴더 없어도 통과」 가 아니다.
#      1: 실행기가 둘째 변환을 거절한 줄 (refused_unexpected_conversion) 이 있으면 89. 그 밖은 v2 처럼 폴더 정확히 하나 (95).
#      어느 쪽이든 실행기가 막은 일 (isolate_state.json blocked) 이 있으면 89.
# 종료 코드 (v2 와 같은 뜻 · 새 코드 셋): 98 띄우지 않음 (멈춤 · 마감) · 97 변환 상한 · 94 루트 밖 또는 풀 수 없는 USD 폴더 ·
#   89 (새) 변환 시도가 예상 개수를 넘음 또는 실행기가 무언가를 막음 · 91 (새) assigned 와 로그가 이어지지 않음 · 96 다른 실행과 같은 절대 폴더 ·
#   90 (새) 관문이 판정을 끝내지 못함: registry 를 안전하게 갱신하지 못함 (registry_error 칸) 또는 관문 내부 오류 (slot_error 칸 · 자식은 끝냄) ·
#   95 자식 0 인데 USD 폴더 수가 예상 (0 또는 1) 과 다름 · 그 밖 자식 종료 코드. 여럿이면 이 순서로 앞의 것.
# 기록 (--record): v2 칸 (usd_final 등은 이제 절대 경로 목록 · v2 식 basename 은 usd_final_keys) + expect_conversions · assigned ·
#   usd_unassigned · conversion_attempts · expect_violation · killed · registry_error · scan_unreadable · isolate_state 등.
# 사용: v2 와 같다 (+ 선택 --expect_conversions). python isaac_slot_v3.py --watch_log L --record R --usd_root U --attempt A [--lock K
#        --registry G --scan_dirs d1,d2 --stop_file S --deadline E --convert_timeout_s T --expect_conversions 0|1] --
#        python gpu_guard.py ... -- python usd_isolate_run_v3.py <Isaac 스크립트> ...
import argparse
import glob
import json
import os
import re
import subprocess
import sys
import time
import uuid

import psutil

HERE = os.path.dirname(os.path.abspath(__file__))
CONVERT_DONE = "[INFO]: Time taken for scene creation"
# A USD conversion folder name; the path written in front of it (same line) is taken back to the nearest stop character: whitespace,
# quotes, @, <>, |, brackets, ( ) , ; = * ? and a colon that is not a drive letter.
ANCHOR_RE = re.compile(r"IsaacLab[/\\]+usd_(\d{8}_\d{6}_\d+)(?!\d)", re.I)
STOP_CHARS = " \t\r\n\f\v@\"'<>|(),;=*?`[]{}:"
ASCII_ALNUM = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
# log lines of the asset importers that only appear when a conversion runs
CONVERT_HINT_RE = re.compile(r"\[(?:isaacsim\.asset\.importer\.\w+|omni\.kit\.asset_converter)\]")
SCAN_PATTERNS = ("*.log", "*.log.prev.*", "attempts/*.log*", "attempts/*/*.log*", "_attempts/*.log*", "_attempts/*/*.log*")
REG_LOCK_WAIT_S = 300.0
WATCH_S = 2.0
LINE_CAP = 1 << 20


def norm(p):
    return os.path.normcase(os.path.abspath(p)).replace("\\", "/")


def canon(p):
    """Absolute, normalised, case-folded path with / separators; None when the text is not an absolute path."""
    s = str(p).strip().replace("\\", "/")
    if re.match(r"^[A-Za-z]:/", s) or s.startswith("//"):
        pass
    elif s.startswith("/"):
        s = os.path.abspath(s)  # drive-less root path (Isaac's /tmp default): the current drive, as Windows opens it
    else:
        return None
    return os.path.normcase(os.path.normpath(s)).replace("\\", "/").rstrip("/")


def folders_in(text):
    """{canonical folder path, or 'unresolved:<raw>' : basename key} for every USD conversion folder named in text."""
    raw = {}
    for m in ANCHOR_RE.finditer(text):
        s = m.start()
        seg = text[max(text.rfind("\n", 0, s) + 1, s - 4096):s]
        j = max(seg.rfind(ch) for ch in STOP_CHARS) + 1
        if j >= 2 and seg[j - 1] == ":" and seg[j - 2].isalpha() and seg[j - 2] in ASCII_ALNUM and (j == 2 or seg[j - 3] not in ASCII_ALNUM):
            j -= 2  # drive letter
        raw.setdefault(seg[j:] + m.group(0), m.group(1))
    out = {}
    for r, k in raw.items():
        c = canon(r)
        out[c if c else "unresolved:" + r] = k
    return out


def is_outside(c, k, root):
    return c.startswith("unresolved:") or c != f"{root}/isaaclab/usd_{k}"


def stopped(a):
    if a.stop_file and os.path.exists(a.stop_file):
        return "stop file"
    if a.deadline and time.time() > a.deadline:
        return "deadline"
    return ""


def acquire(path, a=None, poll=1.0, timeout=None):
    """msvcrt lock on byte 0 of path. With a: gives up at a stop file or deadline. With timeout: gives up after it."""
    import msvcrt
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    f = open(path, "a+")
    t0 = time.time()
    while True:
        why = stopped(a) if a is not None else ""
        if not why and timeout is not None and time.time() - t0 > timeout:
            why = "timeout"
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


def read_bytes(path):
    try:
        with open(path, "rb") as fh:
            return fh.read()
    except FileNotFoundError:
        return b""


def kill_tree(p):
    try:
        parent = psutil.Process(p.pid)
        for c in parent.children(recursive=True):
            c.kill()
        parent.kill()
    except psutil.NoSuchProcess:
        pass


def read_assigned(root):
    """(set of canonical usd_dir written by the launcher, refused list, unreadable line count, file exists,
    {"lines": non-empty lines, "attempts": assigned or explicit_inside lines (v2 lines have no kind and count here),
     "unexpected": refused_unexpected_conversion lines (17d 2.6)})."""
    info = {"lines": 0, "attempts": 0, "unexpected": []}
    try:
        with open(os.path.join(root, "assigned.jsonl"), encoding="utf-8", errors="replace") as fh:
            lines = fh.read().splitlines()
    except FileNotFoundError:
        return set(), [], 0, False, info
    used, refused, bad = set(), [], 0
    for ln in lines:
        if not ln.strip():
            continue
        info["lines"] += 1
        try:
            j = json.loads(ln)
            if j.get("kind") == "refused_unexpected_conversion":
                info["unexpected"].append({"n": j.get("n"), "asset_path": j.get("asset_path")})
                continue
            c = canon(j["usd_dir"])
        except (ValueError, KeyError, TypeError, AttributeError):
            bad += 1
            continue
        if c is None:
            bad += 1
        elif j.get("kind") == "explicit_outside_refused":
            refused.append(c)
        else:
            used.add(c)
            info["attempts"] += 1
    return used, refused, bad, True, info


def read_blocked(root):
    """isolate_state.json blocked entries written by usd_isolate_run_v3 (what the launcher refused); [] when none or no file."""
    try:
        with open(os.path.join(root, "isolate_state.json"), encoding="utf-8") as fh:
            return list(json.load(fh).get("blocked") or [])
    except (OSError, ValueError, AttributeError):
        return []


def expect_violation(expect, found, hint, info, blocked):
    """17d 2.6: with 0, any trace of a conversion attempt (a USD folder in the log, an importer line, any assigned.jsonl line) is a
    violation. With either value, a launcher refusal (refused_unexpected_conversion line) or block (isolate_state.json) is one.
    With 1, a second conversion that the launcher did not refuse shows as a second folder: 95 at the end, as in v2."""
    if blocked or info["unexpected"]:
        return True
    return expect == "0" and (bool(found) or hint or info["lines"] > 0)


def _load_registry(path):
    """(dict, '') or (None, error). A missing or empty file is an empty registry; anything unreadable is left alone."""
    try:
        with open(path, encoding="utf-8") as fh:
            txt = fh.read()
    except FileNotFoundError:
        return {}, ""
    except OSError as ex:
        return None, f"registry unreadable: {type(ex).__name__}: {ex}"
    if not txt.strip():
        return {}, ""
    try:
        reg = json.loads(txt)
    except json.JSONDecodeError as ex:
        return None, f"registry is not JSON ({ex}); left untouched"
    if not isinstance(reg, dict):
        return None, "registry is not a JSON object; left untouched"
    return reg, ""


def _write_registry(path, reg):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    tmp = f"{path}.{os.getpid()}.{uuid.uuid4().hex}.tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(reg, fh, indent=1)
        for _ in range(100):
            try:
                os.replace(tmp, path)
                return ""
            except PermissionError:  # a reader without delete sharing holds it for a moment
                time.sleep(0.1)
        return "registry replace kept failing (PermissionError)"
    except OSError as ex:
        return f"registry write failed: {type(ex).__name__}: {ex}"
    finally:
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass


def registry_update(registry, mine, me):
    """Under <registry>.lock: read, list entries naming one of my folders for another log, add mine, write (unique temp + replace).
    mine: {canonical folder: basename key}. Returns (conflicts {folder: [log]}, v2 basename entries to resolve [(key, log)], error)."""
    lk, _, why = acquire(registry + ".lock", poll=0.05, timeout=REG_LOCK_WAIT_S)
    if lk is None:
        return {}, [], f"registry lock not acquired ({why} after {REG_LOCK_WAIT_S:.0f} s)"
    try:
        reg, err = _load_registry(registry)
        if err:
            return {}, [], err
        conf, legacy = {}, []
        keys = set(mine.values())
        for key, val in reg.items():
            if key in mine and val != me:
                conf.setdefault(key, []).append(val)
            elif "/" not in key and key in keys and val != me:
                legacy.append((key, val))
        changed = False
        for c in mine:
            if c not in reg:
                reg[c] = me
                changed = True
        return conf, legacy, (_write_registry(registry, reg) if changed else "")
    finally:
        release(lk)


def other_logs(a, me, extra=()):
    seen, out = set(), []
    cands = [f for d in a.scan_dirs.split(",") if d for pat in SCAN_PATTERNS for f in glob.glob(os.path.join(d, *pat.split("/")))]
    for f in cands + list(extra):
        n = norm(f)
        if n == me or n in seen or n.endswith(".lock") or not os.path.isfile(f):
            continue
        seen.add(n)
        out.append(f)
    return out


def scan_logs(a, me, mine, legacy):
    """Other logs (scan dirs and the logs behind v2 basename registry entries) naming one of my folders exactly."""
    out, unreadable = {}, []
    keys = set(mine.values())
    legacy_logs = [v for _, v in legacy]
    missing = sorted({v for v in legacy_logs if not os.path.isfile(v)})
    for f in other_logs(a, me, extra=legacy_logs):
        try:
            text = read_bytes(f).decode("utf-8", "replace")
        except OSError:
            unreadable.append(norm(f))
            continue
        if not any(k in text for k in keys):
            continue
        for c in folders_in(text):
            if c in mine and norm(f) not in out.get(c, []):
                out.setdefault(c, []).append(norm(f))
    return out, unreadable, missing


def check(a, root, me, text, found):
    used, refused, bad, exists, info = read_assigned(root)
    blocked = read_blocked(root)
    mine = {c: k for c, k in found.items() if not c.startswith("unresolved:")}
    conf, legacy, err = registry_update(a.registry, mine, me) if mine else ({}, [], "")
    scan, unreadable, legacy_missing = scan_logs(a, me, mine, legacy)
    for c, logs in scan.items():
        for x in logs:
            if x not in conf.get(c, []):
                conf.setdefault(c, []).append(x)
    hint = bool(CONVERT_HINT_RE.search(text))
    return {"outside": sorted(c for c, k in found.items() if is_outside(c, k, root)),
            "unassigned": sorted(c for c in mine if c not in used),
            "assigned": sorted(used), "assigned_refused": refused, "assigned_bad_lines": bad, "assigned_file": exists,
            "assigned_outside_root": sorted(c for c in used if not c.startswith(root + "/")),
            "convert_hint": hint, "hint_without_assigned": hint and not used,
            "conversion_attempts": info["attempts"], "unexpected_refused": info["unexpected"], "launcher_blocked": blocked,
            "expect_violation": expect_violation(a.expect_conversions, found, hint, info, blocked),
            "conflicts": conf, "registry_error": err, "scan_unreadable": unreadable, "legacy_registry_missing_logs": legacy_missing}


def reasons(chk):
    out = []
    if chk["outside"] or chk["assigned_outside_root"]:
        out.append(94)
    if chk["expect_violation"]:
        out.append(89)
    if chk["unassigned"] or chk["hint_without_assigned"]:
        out.append(91)
    if chk["conflicts"]:
        out.append(96)
    if chk["registry_error"]:
        out.append(90)
    return out


def _stamp(path):
    try:
        st = os.stat(path)
        return st.st_mtime_ns, st.st_size
    except OSError:
        return None


def watch(p, a, root, pos, seen):
    """After the lock is released: read only what the log gains; stop the child as soon as a new folder is outside the root or not in
    assigned.jsonl, an importer line shows up with assigned.jsonl empty, or (17d 2.6) a conversion attempt goes past the expected
    count or the launcher blocks something (assigned.jsonl / isolate_state.json are looked at again whenever they change).
    A line longer than LINE_CAP is skipped here (the final full read still sees it)."""
    carry, skipping = b"", False
    side_files = [os.path.join(root, "assigned.jsonl"), os.path.join(root, "isolate_state.json")]
    side = [_stamp(f) for f in side_files]
    while p.poll() is None:
        time.sleep(WATCH_S)
        now = [_stamp(f) for f in side_files]
        if now != side:
            side = now
            info, blocked = read_assigned(root)[4], read_blocked(root)
            if expect_violation(a.expect_conversions, {}, False, info, blocked):
                kill_tree(p)
                return {"outside": [], "unassigned": [], "hint_without_assigned": False, "expect_violation": True,
                        "unexpected_refused": info["unexpected"], "launcher_blocked": blocked}
        try:
            size = os.path.getsize(a.watch_log)
        except OSError:
            continue
        if size < pos:
            pos, carry, skipping = 0, b"", False
        if size == pos:
            continue
        try:
            with open(a.watch_log, "rb") as fh:
                fh.seek(pos)
                chunk = fh.read(size - pos)
        except OSError:
            continue
        pos += len(chunk)
        buf = carry + chunk
        cut = buf.rfind(b"\n")
        if cut < 0:
            carry = b"" if (skipping or len(buf) > LINE_CAP) else buf
            skipping = skipping or len(buf) > LINE_CAP
            continue
        head, carry = buf[:cut + 1], buf[cut + 1:]
        if skipping:
            nl = head.find(b"\n")
            head, skipping = head[nl + 1:], False
        text = head.decode("utf-8", "replace")
        new = {c: k for c, k in folders_in(text).items() if c not in seen}
        hint = bool(CONVERT_HINT_RE.search(text))
        if not new and not hint:
            continue
        seen.update(new)
        asg = read_assigned(root)
        used = asg[0]
        bad = {"outside": sorted(c for c, k in new.items() if is_outside(c, k, root)),
               "unassigned": sorted(c for c in new if not c.startswith("unresolved:") and c not in used),
               "hint_without_assigned": hint and not used,
               "expect_violation": expect_violation(a.expect_conversions, new, hint, asg[4], read_blocked(root))}
        if bad["outside"] or bad["unassigned"] or bad["hint_without_assigned"] or bad["expect_violation"]:
            kill_tree(p)
            return bad
    return None


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
    ap.add_argument("--expect_conversions", choices=["0", "1"], default="1")
    ap.add_argument("cmd", nargs=argparse.REMAINDER)
    a = ap.parse_args()
    cmd = a.cmd[1:] if a.cmd and a.cmd[0] == "--" else a.cmd
    assert cmd, "no command"
    root = norm(a.usd_root)
    me = norm(a.watch_log)
    rec = {"slot_version": "v3", "attempt": a.attempt, "cmd": cmd, "watch_log": me, "usd_root": root, "lock": a.lock,
           "registry": a.registry, "expect_conversions": a.expect_conversions, "t_request": time.strftime("%Y-%m-%d %H:%M:%S"),
           "t_request_epoch": time.time()}

    def finish(rc):
        rec["slot_rc"] = rc
        rec["t_end"] = time.strftime("%Y-%m-%d %H:%M:%S")
        os.makedirs(os.path.dirname(os.path.abspath(a.record)), exist_ok=True)
        with open(a.record, "w", encoding="utf-8") as fh:
            json.dump(rec, fh, ensure_ascii=False, indent=1)
        print(f"SLOT rc={rc} attempt={a.attempt} state={rec.get('state_at_release')} usd={rec.get('usd_final')} conflicts={rec.get('conflicts')}",
              flush=True)
        sys.exit(rc)

    if os.path.exists(a.watch_log):
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
    env["FOOTHOLD_EXPECT_CONVERSIONS"] = a.expect_conversions  # 17d 2.6: usd_isolate_run_v3 refuses a conversion past this before any write
    p = subprocess.Popen(cmd, env=env)
    rec["pid"] = p.pid
    try:
        run(a, rec, p, lk, t_hold, root, me, finish)
    except SystemExit:
        raise
    except Exception as ex:  # noqa: BLE001  never leave the child running without the gate
        import traceback
        kill_tree(p)
        rec["slot_error"] = f"{type(ex).__name__}: {ex}"
        rec["slot_traceback"] = traceback.format_exc()[-4000:]
        try:
            rec["child_rc"] = p.wait(timeout=60)
        except subprocess.TimeoutExpired:
            rec["child_rc"] = None
        finish(90)


def run(a, rec, p, lk, t_hold, root, me, finish):
    state = "exited"
    while True:
        data = read_bytes(a.watch_log)
        text = data.decode("utf-8", "replace")
        found = folders_in(text)
        if CONVERT_DONE in text and (found or a.expect_conversions == "0"):  # expect 0: no folder to wait for
            state = "scene_built"
            break
        if p.poll() is not None:
            break
        if time.time() - t_hold > a.convert_timeout_s:
            state = "convert_timeout"
            kill_tree(p)
            break
        time.sleep(0.5)
    chk1 = check(a, root, me, text, found)
    bad1 = reasons(chk1)
    rec.update({"state_at_release": state, "hold_s": round(time.time() - t_hold, 1), "usd_at_release": sorted(found),
                "check_at_release": chk1})
    if bad1 and p.poll() is None:
        kill_tree(p)
        rec["killed"] = {"at": "scene_line", "codes": bad1, "t": time.strftime("%Y-%m-%d %H:%M:%S")}
    release(lk)
    if "killed" not in rec and p.poll() is None:
        w = watch(p, a, root, len(data), set(found))
        if w:
            rec["killed"] = dict(w, at="after_release", t=time.strftime("%Y-%m-%d %H:%M:%S"))
    rc = p.wait()
    text = read_bytes(a.watch_log).decode("utf-8", "replace")
    final = folders_in(text)
    chk2 = check(a, root, me, text, final)
    conf = {k: list(v) for k, v in chk1["conflicts"].items()}
    for k, v in chk2["conflicts"].items():
        for x in v:
            if x not in conf.get(k, []):
                conf.setdefault(k, []).append(x)
    outside = sorted(set(chk1["outside"]) | set(chk2["outside"]))
    unassigned = sorted(set(chk1["unassigned"]) | set(chk2["unassigned"]))
    try:
        iso = json.load(open(os.path.join(root, "isolate_state.json"), encoding="utf-8"))
    except (OSError, ValueError):
        iso = None
    rec.update({"child_rc": rc, "usd_final": sorted(final), "usd_final_keys": sorted(set(final.values())), "usd_outside_root": outside,
                "usd_unassigned": unassigned, "assigned": chk2["assigned"], "assigned_refused": chk2["assigned_refused"],
                "assigned_bad_lines": chk2["assigned_bad_lines"], "assigned_outside_root": chk2["assigned_outside_root"],
                "convert_hint": chk2["convert_hint"], "hint_without_assigned": chk1["hint_without_assigned"] or chk2["hint_without_assigned"],
                "conflicts": conf, "registry_error": chk1["registry_error"] or chk2["registry_error"],
                "scan_unreadable": sorted(set(chk1["scan_unreadable"]) | set(chk2["scan_unreadable"])),
                "legacy_registry_missing_logs": sorted(set(chk1["legacy_registry_missing_logs"]) | set(chk2["legacy_registry_missing_logs"])),
                "usd_changed_after_release": sorted(final) != sorted(found), "isolate_state": iso,
                "conversion_attempts": chk2["conversion_attempts"], "unexpected_refused": chk2["unexpected_refused"],
                "launcher_blocked": chk2["launcher_blocked"],
                "expect_violation": bool(chk1["expect_violation"] or chk2["expect_violation"] or rec.get("killed", {}).get("expect_violation"))})
    if state == "convert_timeout":
        finish(97)
    if outside or rec["assigned_outside_root"]:
        finish(94)
    if rec["expect_violation"]:
        finish(89)
    if unassigned or rec["hint_without_assigned"]:
        finish(91)
    if conf:
        finish(96)
    if rec["registry_error"]:
        finish(90)
    if rc == 0 and len(final) != (0 if a.expect_conversions == "0" else 1):
        finish(95)
    finish(rc)


if __name__ == "__main__":
    main()
