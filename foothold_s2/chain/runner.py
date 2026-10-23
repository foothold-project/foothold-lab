"""무인 사슬 실행기: 작업 목록(chain.yaml)을 세션 없이 순서대로 돌린다. 표준 라이브러리 + PyYAML 만 쓴다.

한 작업 = 이름 · GPU · 명령 · 앞 작업(depends_on) · 끝 판정(done) · 재시도. 규칙:
  - 앞 작업이 모두 done 이고 그 GPU 가 비면 띄운다(GPU 하나에 사슬 작업은 하나). 두 작업을 띄우는 사이에 start_gap_s 를 둔다.
  - 「띄움 · 첫 증거 · 끝」 을 chain_status.jsonl 에 한 줄씩 적는다. 판정은 종료 코드만이 아니라 상태 파일 · 산출물 · Traceback 으로 한다.
  - 실패하면 재시도 명령으로 한 번(retries, 기본 1) 이어 돌린다. 그래도 실패면 failed, 그 작업에 기대는 작업은 blocked(막고 기록).
  - 끝 · 실패 · 막힘 · 재시도 · 사슬 끝에 lead 창으로 한 줄 알림(notify.cmd, 입력 확인 도구 mai_resume send).
  - 상태는 chain_state.json 에 매 라운드 저장한다. 실행기가 죽었다 다시 떠도 이어 간다(이미 끝난 작업은 건너뛰고, 돌고 있는 작업은 pid 로 다시 붙는다).
  - 이미 돌고 있는 일(학습 등)은 `adopt: {pid: N}` 으로 붙기만 한다(건드리지 않는다).
  - 세션 · 토큰 없이 돈다. Windows 는 창 없이(CREATE_NO_WINDOW), Linux 는 새 세션(nohup 과 같음).
"""

from __future__ import annotations

import glob
import json
import os
import re
import shlex
import subprocess
import sys
import time

import yaml

IS_WIN = os.name == "nt"
CREATE_NO_WINDOW = 0x08000000
CREATE_NEW_PROCESS_GROUP = 0x00000200
TERMINAL = ("done", "failed", "blocked", "cancelled")

BASH_CANDIDATES = (os.environ.get("FOOTHOLD_BASH", ""), "C:/Program Files/Git/bin/bash.exe",
                   "C:/Program Files/Git/usr/bin/bash.exe")


def find_bash():
    for path in BASH_CANDIDATES:
        if path and os.path.isfile(path):
            return path

    raise FileNotFoundError("Git bash 를 못 찾았다. FOOTHOLD_BASH 에 경로를 준다: %r" % (BASH_CANDIDATES,))


def pid_alive(pid):
    if not pid:
        return False

    if IS_WIN:
        import ctypes

        kernel32 = ctypes.windll.kernel32
        handle = kernel32.OpenProcess(0x1000, False, int(pid))      # PROCESS_QUERY_LIMITED_INFORMATION

        if not handle:
            return False

        code = ctypes.c_ulong()
        ok = kernel32.GetExitCodeProcess(handle, ctypes.byref(code))
        kernel32.CloseHandle(handle)

        return bool(ok) and code.value == 259                        # STILL_ACTIVE

    try:
        os.kill(int(pid), 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True

    return True


def newest(pattern):
    """glob 에 맞는 가장 최근(수정 시각) 경로. 없으면 None."""
    found = glob.glob(pattern, recursive=True)

    return max(found, key=os.path.getmtime) if found else None


def resolve_text(text, gpu):
    """문자열 안의 {gpu} · {device} · {glob:패턴}(가장 최근 일치 경로) · {globname:패턴}(그 경로의 마지막 이름)을 채운다. «지금» 기준, 없으면 오류."""
    text = text.replace("{gpu}", str(gpu)).replace("{device}", "cuda:%s" % gpu)

    def sub(match):
        found = newest(match.group(1))

        if found is None:
            raise FileNotFoundError("glob 에 맞는 것이 없다: %s" % match.group(1))

        return found.replace("\\", "/")

    def sub_name(match):
        found = newest(match.group(1))

        if found is None:
            raise FileNotFoundError("glob 에 맞는 것이 없다: %s" % match.group(1))

        return os.path.basename(found.rstrip("/\\"))

    text = re.sub(r"\{globname:([^}]+)\}", sub_name, text)

    return re.sub(r"\{glob:([^}]+)\}", sub, text)


def default_launcher(argv, cwd, env, log):
    """창 없이 떼어 낸 자식 프로세스. 부모(실행기)가 죽어도 산다."""
    kwargs = {"cwd": cwd, "env": env, "stdin": subprocess.DEVNULL, "stdout": subprocess.DEVNULL,
              "stderr": subprocess.DEVNULL, "close_fds": True}

    if IS_WIN:
        kwargs["creationflags"] = CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP
    else:
        kwargs["start_new_session"] = True

    return subprocess.Popen(argv, **kwargs).pid


def default_notifier(notify_cfg, text):
    """lead 창에 한 줄. 사슬은 기다리지 않는다: 별도 스레드가 입력 확인 도구(mai_resume send)를 불러 «조용한 입력창» 을 기다린다
    (도구가 --wait 초까지 기다리고, 그동안 사람이 치고 있으면 보내지 않고 코드 4 로 끝난다). 결과는 notify_cfg["log"] 에 줄로 남는다.
    실패하면 notify_cfg["retries"](기본 3)번까지 retry_gap_s(기본 120 s) 간격으로 다시 보낸다."""
    import threading

    if not notify_cfg or not notify_cfg.get("cmd"):
        return "no notifier"

    cmd = [str(c).replace("{text}", text) for c in notify_cfg["cmd"]]
    log = notify_cfg.get("log")
    tries = int(notify_cfg.get("retries", 3))
    gap = float(notify_cfg.get("retry_gap_s", 120))
    kwargs = {"cwd": notify_cfg.get("cwd") or None, "capture_output": True, "text": True,
              "timeout": float(notify_cfg.get("timeout_s", 1500)), "stdin": subprocess.DEVNULL}

    if IS_WIN:
        kwargs["creationflags"] = CREATE_NO_WINDOW

    def write(line):
        if log:
            with open(log, "a", encoding="utf-8") as f:
                f.write("%s %s\n" % (time.strftime("%Y-%m-%dT%H:%M:%S"), line))

    def work():
        for attempt in range(1, tries + 1):
            try:
                out = subprocess.run(cmd, **kwargs)
                note = "rc=%s %s" % (out.returncode, (out.stdout or out.stderr or "").strip()[:160])
            except Exception as exc:                                  # noqa: BLE001
                out, note = None, "notify error: %r" % (exc,)

            write("attempt %d %s :: %s" % (attempt, note, text[:100]))

            if out is not None and out.returncode == 0:
                return

            time.sleep(gap)

    threading.Thread(target=work, daemon=False).start()

    return "notify started"


# ---------------------------------------------------------------- 텔레그램 (lead 10/21): 작업의 title · purpose · next 를 띄움 · 첫 증거 · 끝 · 실패 · 막힘마다 보낸다
TG_STATUS = {"launched": "띄움", "relaunched": "재시도 띄움", "first_evidence": "첫 증거", "done": "끝", "failed": "실패",
             "blocked": "막힘", "cancelled": "취소", "guard_wait": "승인 대기", "guard_blocked": "가드로 막힘"}
TG_MAX_ATTEMPTS = 6
DIAG_MAX_ITERATIONS = 1501          # 이름이 diag- 인 작업(지류)은 이 회차를 넘기지 않는다
APPROVAL_FROM_ITERATIONS = 3000     # 이 회차 이상 학습은 상태 폴더 approvals/<작업>.json 이 있어야 띄운다
APPROVAL_KEYS = ("design_commit", "approved_by", "time")
VERDICT_KEYS = ("video_paths", "watched_by", "checklist", "card_path")      # 판정 파일(…verdict….json)이 갖춰야 할 칸


def tg_escape(text):
    """텔레그램 parse_mode HTML: 본문의 & < > 를 이스케이프."""
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def default_tg_sender(tg_cfg, text):
    """outbox 파일에 UTF-8 로 쓰고 tg-send.ps1 을 창 없이 부른다. 성공하면 True (토큰은 만지지 않는다)."""
    outbox = tg_cfg.get("outbox", "C:/ssd-cleanup-logs/tg-outbox.txt")
    script = tg_cfg.get("script", "C:/ssd-cleanup-logs/tg-send.ps1")

    try:
        with open(outbox, "w", encoding="utf-8") as handle:
            handle.write(text)

        flags = 0x08000000 if IS_WIN else 0                                   # CREATE_NO_WINDOW
        done = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", script],
                              creationflags=flags, timeout=90, capture_output=True)

        return done.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def job_max_iterations(job):
    """작업의 총 회차: yaml 의 max_iterations 칸, 없으면 cmd 의 마지막 `--max_iterations N`. 모르면 None."""
    if job.get("max_iterations") is not None:
        return int(job["max_iterations"])

    cmd = job.get("cmd") or []
    tokens = shlex.split(cmd, posix=True) if isinstance(cmd, str) else [str(c) for c in cmd]
    found = None

    for i, token in enumerate(tokens):
        if token == "--max_iterations" and i + 1 < len(tokens):
            try:
                found = int(tokens[i + 1])
            except ValueError:
                pass
        elif token.startswith("--max_iterations="):
            try:
                found = int(token.split("=", 1)[1])
            except ValueError:
                pass

    return found


class Chain:
    def __init__(self, config, state_dir, launcher=default_launcher, notifier=default_notifier, alive=pid_alive,
                 clock=time.time, sleep=time.sleep, repo_root=None, tg_sender=None):
        self.cfg = config
        self.state_dir = state_dir
        os.makedirs(state_dir, exist_ok=True)
        self.launcher, self.notifier, self.alive = launcher, notifier, alive
        self.clock, self.sleep = clock, sleep
        self.repo_root = repo_root or os.getcwd()
        self.jobs = {j["name"]: j for j in config["jobs"]}

        if len(self.jobs) != len(config["jobs"]):
            raise ValueError("작업 이름이 겹친다")

        for j in self.jobs.values():
            for d in list(j.get("depends_on", [])) + list(j.get("after", [])):
                if d not in self.jobs:
                    raise ValueError("%s 가 모르는 작업 %s 에 기댄다" % (j["name"], d))

        self.state_path = os.path.join(state_dir, "chain_state.json")
        self.status_path = os.path.join(state_dir, "chain_status.jsonl")
        self.poll_s = float(config.get("poll_s", 30))
        self.gap_s = float(config.get("start_gap_s", 60))
        self.last_launch = 0.0
        self.state = self._load_state()
        self.ended = False
        tg_cfg = config.get("telegram")
        self.tg_sender = tg_sender or ((lambda text: default_tg_sender(tg_cfg, text)) if tg_cfg else None)
        self.tg_queue = []
        self._verdict_seen = {}

    # ------------------------------------------------------------------ 상태 · 기록
    def _load_state(self):
        try:
            with open(self.state_path, encoding="utf-8") as f:
                state = json.load(f)
        except (OSError, ValueError):
            state = {}

        for name, job in self.jobs.items():
            st = state.setdefault(name, {"state": "pending", "attempt": 0})

            self._adopt_if_declared(job, st)

        return state

    def _adopt_if_declared(self, job, st):
        """`adopt: {pid}` 작업은 «이미 도는 프로세스에 붙는다»: cmd 로 띄우지 않는다. 시작 때와 yaml 을 다시 읽어 새 작업이 더해질 때 둘 다 이 길을 탄다
        (다시 읽기로 더해진 adopt 작업이 cmd 없이 띄워지려다 «cmd 가 비어 있다» 로 실패 처리된 일, 10/21 09:19)."""
        if job.get("adopt") and st["state"] == "pending":
            st.update(state="running", pid=int(job["adopt"]["pid"]), adopted=True, started=self.clock(),
                      gpu=self._fixed_gpu(job), attempt=1)

    def _save(self):
        tmp = self.state_path + ".tmp"

        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self.state, f, ensure_ascii=False, indent=1)

        os.replace(tmp, self.state_path)

    def event(self, name, kind, detail="", notify=False, **extra):
        rec = {"time": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(self.clock())), "job": name, "event": kind,
               "detail": detail}
        rec.update(extra)

        with open(self.status_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

        self._tg_enqueue(name, kind)

        if notify:
            ncfg = dict(self.cfg.get("notify") or {})
            ncfg.setdefault("log", os.path.join(self.state_dir, "notify.log"))
            res = self.notifier(ncfg, "[chain] %s %s %s" % (name, kind, detail))
            rec2 = {"time": rec["time"], "job": name, "event": "notified", "detail": str(res)[:200]}

            with open(self.status_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(rec2, ensure_ascii=False) + "\n")

    # ------------------------------------------------------------------ 텔레그램
    def _tg_text(self, name, kind):
        job, st = self.jobs.get(name) or {}, self.state.get(name) or {}
        title = job.get("title")

        if not title or kind not in TG_STATUS:
            return None

        it, tot = "?", job.get("max_iterations", job_max_iterations(job) if job.get("cmd") else "?")
        pattern = (job.get("done") or {}).get("status_glob")

        if pattern:
            data, _ = self._status_json(pattern)

            if data:
                it, tot = data.get("iter", "?"), data.get("tot_iter", tot)

        started = st.get("started")
        when = time.strftime("%H:%M", time.localtime(started)) if started else "-"
        lines = ["[FOOTHOLD 실험] %s %s" % (TG_STATUS[kind], tg_escape(title)),
                 "목적: %s" % tg_escape(job.get("purpose", "-")),
                 "GPU %s · 시작 %s · 진행 %s/%s" % (st.get("gpu", job.get("gpu", "-")), when, it, tot),
                 "다음: %s" % tg_escape(job.get("next", "-"))]

        return "\n".join(lines)

    def _tg_enqueue(self, name, kind):
        if self.tg_sender is None:
            return

        text = self._tg_text(name, kind)

        if text:
            self.tg_queue.append({"text": text, "attempts": 0, "job": name, "kind": kind})

    def _tg_flush(self):
        """쌓인 메시지를 차례로 보낸다. 하나라도 실패하면 순서를 지키려고 거기서 멈추고 다음 라운드에 다시 (최대 TG_MAX_ATTEMPTS 번)."""
        while self.tg_queue and self.tg_sender is not None:
            item = self.tg_queue[0]

            try:
                ok = bool(self.tg_sender(item["text"]))
            except Exception:                                         # noqa: BLE001
                ok = False

            if ok:
                self.tg_queue.pop(0)
                continue

            item["attempts"] += 1

            if item["attempts"] >= TG_MAX_ATTEMPTS:
                self.tg_queue.pop(0)
                self.event("chain", "tg_dropped", "%s %s 알림을 %d 번 실패해 버림" % (item["job"], item["kind"], TG_MAX_ATTEMPTS))
                continue

            break

    # ------------------------------------------------------------------ 가드 (지류 · 본류, lead 10/21)
    def _approval_ok(self, name):
        path = os.path.join(self.state_dir, "approvals", name + ".json")

        try:
            with open(path, encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, ValueError):
            return False

        return isinstance(data, dict) and all(str(data.get(k) or "").strip() for k in APPROVAL_KEYS)

    def _guard(self, name, job):
        """띄우기 전 점검. 돌려줌: None(통과) 또는 (종류, 사유, 영구 여부).
        (1) 이름이 diag- 인 작업은 max_iterations <= 1501 이어야 한다(모르면 못 띄운다) (2) 3000 회 이상 학습은 approvals/<작업>.json 필수."""
        iters = job_max_iterations(job)

        if name.startswith(("diag-", "diag_")):
            if iters is None or iters > DIAG_MAX_ITERATIONS:
                return ("guard_blocked", "diag- 작업은 max_iterations <= %d 여야 한다 (지금 %s)" % (DIAG_MAX_ITERATIONS, iters), True)

        if iters is not None and iters >= APPROVAL_FROM_ITERATIONS and not self._approval_ok(name):
            return ("guard_wait", "%d 회 이상 학습은 approvals/%s.json(design_commit · approved_by · time)이 있어야 띄운다" % (APPROVAL_FROM_ITERATIONS, name), False)

        return None

    def _verdict_ok(self, path):
        """판정 파일(이름에 verdict · .json)은 VERDICT_KEYS 가 모두 채워져야 인정한다. 아니면 없는 것으로 보고 한 번 알린다."""
        base = os.path.basename(path)

        if "verdict" not in base or not base.endswith(".json"):
            return True

        try:
            mtime = os.path.getmtime(path)
            with open(path, encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, ValueError):
            return False

        missing = [k for k in VERDICT_KEYS if not (isinstance(data, dict) and data.get(k))]

        if missing:
            if self._verdict_seen.get(path) != mtime:
                self._verdict_seen[path] = mtime
                self.event("chain", "verdict_invalid", "%s 에 %s 가 없어 무시함" % (base, ",".join(missing)), notify=True)

            return False

        return True

    # ------------------------------------------------------------------ GPU
    def _fixed_gpu(self, job):
        g = job.get("gpu")

        return g if isinstance(g, int) else None

    def _gpu_busy(self, gpu):
        return any(st["state"] == "running" and st.get("gpu") == gpu for st in self.state.values())

    def _pick_gpu(self, job):
        g = job.get("gpu")
        options = [g] if isinstance(g, int) else list(g if isinstance(g, list) else self.cfg.get("gpus", [0, 1]))

        for opt in options:
            if not self._gpu_busy(opt):
                return opt

        return None

    # ------------------------------------------------------------------ 명령
    def _argv(self, job, cmd, gpu, name, attempt):
        if isinstance(cmd, str):
            cmd = shlex.split(cmd, posix=True)

        cmd = [resolve_text(str(c), gpu) for c in cmd]

        if cmd and cmd[0] == "bash" and IS_WIN:
            cmd[0] = find_bash()

        if cmd and cmd[0] in ("python", "python3"):
            cmd[0] = job.get("python") or self.cfg.get("python") or sys.executable

        rc_file = os.path.join(self.state_dir, "%s.a%d.rc" % (name.replace("/", "_"), attempt))

        try:
            os.remove(rc_file)
        except OSError:
            pass

        log = resolve_text(job.get("log", os.path.join(self.state_dir, "%s.log" % name.replace("/", "_"))), gpu)
        py = self.cfg.get("runner_python") or sys.executable
        wrap = [py, "-m", "foothold_s2.chain.wrap", "--rc", rc_file, "--log", log, "--"] + cmd

        return wrap, rc_file, log

    def _env(self, job, gpu):
        env = dict(os.environ)
        env.update({"CUDA_DEVICE_ORDER": "PCI_BUS_ID", "PYTHONUNBUFFERED": "1"})

        if gpu is not None:
            env["DEVICE"] = "cuda:%s" % gpu

        env.update({k: resolve_text(str(v), gpu) for k, v in (self.cfg.get("env") or {}).items()})
        env.update({k: resolve_text(str(v), gpu) for k, v in (job.get("env") or {}).items()})
        pp = env.get("PYTHONPATH", "")
        root = resolve_text(str(job.get("repo") or self.repo_root), gpu)
        env["PYTHONPATH"] = root + (os.pathsep + pp if pp else "")

        return env

    def _launch(self, name, cmd, gpu, attempt):
        job = self.jobs[name]
        argv, rc_file, log = self._argv(job, cmd, gpu, name, attempt)
        os.makedirs(os.path.dirname(os.path.abspath(log)), exist_ok=True)
        pid = self.launcher(argv, resolve_text(str(job.get("cwd") or job.get("repo") or self.repo_root), gpu),
                            self._env(job, gpu), log)
        st = self.state[name]
        st.update(state="running", pid=pid, gpu=gpu, attempt=attempt, rc_file=rc_file, log=log, started=self.clock(),
                  evidence=False, adopted=False)
        if gpu is not None:
            self.last_launch = self.clock()

        self.event(name, "launched" if attempt == 1 else "relaunched", "pid %s gpu %s attempt %d" % (pid, gpu, attempt),
                   pid=pid, gpu=gpu, attempt=attempt)

    # ------------------------------------------------------------------ 판정
    def _status_json(self, pattern):
        path = newest(resolve_text(pattern, "0"))

        if path is None:
            return None, None

        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f), path
        except (OSError, ValueError):
            return None, path

    def _first_evidence(self, name):
        job, st = self.jobs[name], self.state[name]

        for check in job.get("first_evidence", [{"log_nonempty": True}]):
            if "status_state" in check:
                pat = check.get("status_glob") or (job.get("done") or {}).get("status_glob")
                data, _ = self._status_json(pat) if pat else (None, None)

                if data and data.get("state") in ("running", "done") and int(data.get("iter", 0)) >= int(check.get("min_iter", 0)):
                    return True
            elif "log_contains" in check:
                log = st.get("log") or ""

                if log and os.path.isfile(log) and re.search(check["log_contains"], open(log, encoding="utf-8", errors="replace").read()):
                    return True
            elif "file_exists" in check:
                if glob.glob(resolve_text(check["file_exists"], st.get("gpu", 0))):
                    return True
            elif check.get("log_nonempty"):
                log = st.get("log") or ""

                if log and os.path.isfile(log) and os.path.getsize(log) > 0:
                    return True

        return False

    def evaluate(self, name):
        """끝난 작업의 판정: (통과 여부, 문제 목록). 종료 코드 · 상태 파일 · 산출물 · Traceback."""
        job, st = self.jobs[name], self.state[name]
        done = job.get("done") or {}
        gpu = st.get("gpu", 0)
        problems = []
        rc_file = st.get("rc_file")

        if rc_file and os.path.isfile(rc_file):
            text = open(rc_file, encoding="utf-8").read().strip()

            allowed = ["rc=%s" % c for c in (job.get("accept_rc") or [0])]      # 결과가 «아니오» 여도 일은 정상으로 끝나는 도구(compare_curves 는 판정 실패에 1)

            if text not in allowed:
                problems.append("종료 코드 %s" % text)
        elif rc_file and not st.get("adopted"):
            problems.append("rc 파일 없음(래퍼가 죽었다)")

        if done.get("status_glob"):
            data, path = self._status_json(done["status_glob"])

            if data is None:
                problems.append("상태 파일 없음 %s" % done["status_glob"])
            else:
                if data.get("state") != done.get("status_state", "done"):
                    problems.append("상태 %s (기대 %s)" % (data.get("state"), done.get("status_state", "done")))

                if int(data.get("iter", -1)) < int(done.get("min_iter", 0)):
                    problems.append("iter %s < %s" % (data.get("iter"), done.get("min_iter")))

        for pat in done.get("outputs", []):
            if not glob.glob(resolve_text(pat, gpu), recursive=True):
                problems.append("산출물 없음 %s" % pat)

        logs = done.get("no_traceback", [])
        logs = ([st["log"]] if st.get("log") else []) + [resolve_text(p, gpu) for p in logs]

        for pat in logs:
            for path in glob.glob(pat, recursive=True):
                with open(path, encoding="utf-8", errors="replace") as f:
                    if "Traceback" in f.read():
                        problems.append("Traceback %s" % path)

        return (not problems), problems

    # ------------------------------------------------------------------ 한 라운드
    def _deps(self, name):
        return [self.state[d]["state"] for d in self.jobs[name].get("depends_on", [])]

    def _ready(self, name):
        """띄울 수 있는 상태인가: 앞 작업 done · after 끝남 · require_file 있음. (GPU · 간격은 따로 본다)"""
        job = self.jobs[name]

        if not all(d == "done" for d in self._deps(name)):
            return False

        if not all(self.state[a]["state"] in TERMINAL for a in job.get("after", [])):
            return False

        req = job.get("require_file") or []
        req = [req] if isinstance(req, str) else req

        def present(r):
            path = resolve_text(r, 0)

            return os.path.exists(path) and self._verdict_ok(path)      # 판정 파일은 칸이 갖춰져야 인정 (lead 10/21 가드 3)

        if not all(present(r) for r in req):
            return False

        any_req = job.get("require_any_file") or []                  # 이 중 하나라도 있으면 됨 (예: 판정 통과 또는 실패 파일)

        return (not any_req) or any(present(r) for r in any_req)

    def reload_if_changed(self):
        """yaml 이 바뀌었으면 «아직 안 띄운(pending) 작업» 의 정의를 새 것으로 바꾸고 새 작업을 더한다(실행기를 멈추지 않는다).
        돌고 있거나 끝난 작업의 정의는 그대로 둔다. 읽다 틀리면 옛 설정을 쓰고 reload_failed 를 적는다."""
        path = getattr(self, "config_path", None)

        if not path:
            return

        try:
            mtime = os.path.getmtime(path)
        except OSError:
            return

        if mtime == getattr(self, "_cfg_mtime", None):
            return

        self._cfg_mtime = mtime

        try:
            new = load_config(path)
            names = [j["name"] for j in new["jobs"]]

            if len(set(names)) != len(names):
                raise ValueError("작업 이름이 겹친다")

            for j in new["jobs"]:
                for d in list(j.get("depends_on", [])) + list(j.get("after", [])):
                    if d not in names:
                        raise ValueError("%s 가 모르는 작업 %s 에 기댄다" % (j["name"], d))
        except Exception as exc:                                     # noqa: BLE001
            self.event("chain", "reload_failed", repr(exc)[:300], notify=True)

            return

        changed = []

        for j in new["jobs"]:
            name = j["name"]

            if name not in self.jobs:
                self.jobs[name] = j
                self.state[name] = {"state": "pending", "attempt": 0}
                self._adopt_if_declared(j, self.state[name])
                changed.append(name + "(new)")
            elif self.state[name]["state"] == "pending" and j != self.jobs[name]:
                self.jobs[name] = j
                changed.append(name)

        self.poll_s = float(new.get("poll_s", self.poll_s))
        self.gap_s = float(new.get("start_gap_s", self.gap_s))

        if changed:
            self.event("chain", "reloaded", ",".join(changed))

    def _is_cancelled(self, name):
        """사람이 멈춘 작업: yaml 의 `cancelled: true` 또는 상태 폴더의 `cancel/<작업 이름>` 파일. 이런 작업은 다시 띄우지도 재시도하지도 않는다
        (Rx1 을 멈추자 사슬이 «재시도» 로 되살린 사고, 10/21 14:38)."""
        return bool(self.jobs[name].get("cancelled")) or os.path.exists(os.path.join(self.state_dir, "cancel", name))

    def _apply_resets(self):
        """상태 폴더의 `chain.reset` 파일(작업 이름을 공백 · 쉼표 · 줄바꿈으로 나열)을 읽어, 그 작업(과 그 작업 때문에 막힌 뒤 작업들)을
        failed · blocked · done 에서 pending 으로 되돌린다. 실행기를 재시작하지 않고 다음 라운드에 읽는다. 돌고 있는(running) 작업은
        건드리지 않는다(두 번 띄우지 않으려고). adopt 작업은 되돌려지는 즉시 다시 붙는다. 읽은 파일은 지운다."""
        path = os.path.join(self.state_dir, "chain.reset")

        if not os.path.isfile(path):
            return

        try:
            with open(path, encoding="utf-8") as handle:
                wanted = [w for w in re.split(r"[\s,]+", handle.read()) if w]
            os.remove(path)
        except OSError:
            return

        todo, unknown = [], [w for w in wanted if w not in self.jobs]

        for name in wanted:
            if name in self.jobs and name not in todo:
                todo.append(name)

        grew = True

        while grew:                                                      # 되돌릴 작업에 기대다 막힌 뒤 작업들도 함께
            grew = False

            for name, job in self.jobs.items():
                if name not in todo and self.state[name]["state"] == "blocked" and any(
                        d in todo for d in list(job.get("depends_on", [])) + list(job.get("after", []))):
                    todo.append(name)
                    grew = True

        done, skipped = [], []

        for name in todo:
            if self.state[name]["state"] == "running":
                skipped.append(name)
                continue

            self.state[name] = {"state": "pending", "attempt": 0}
            self._adopt_if_declared(self.jobs[name], self.state[name])
            done.append(name)

        self.event("chain", "reset", "되돌림 %s%s%s" % (",".join(done) or "-", " · 돌고 있어 건너뜀 " + ",".join(skipped) if skipped else "",
                                                       " · 모르는 이름 " + ",".join(unknown) if unknown else ""), notify=bool(unknown or skipped))

    def step(self):
        self.reload_if_changed()
        self._apply_resets()

        for name, job in self.jobs.items():
            st = self.state[name]

            if st["state"] == "pending" and self._is_cancelled(name):
                st.update(state="cancelled", finished=self.clock())
                self.event(name, "cancelled", "취소 표시: 띄우지 않음", notify=True)
                continue

            if st["state"] == "pending":
                if any(d in ("failed", "blocked", "cancelled") for d in self._deps(name)):
                    st["state"] = "blocked"
                    bad = [d for d in job.get("depends_on", []) if self.state[d]["state"] in ("failed", "blocked", "cancelled")]
                    self.event(name, "blocked", "앞 작업 실패: %s" % ",".join(bad), notify=True)

            elif st["state"] == "running":
                if not st.get("evidence") and self._first_evidence(name):
                    st["evidence"] = True
                    self.event(name, "first_evidence", "", pid=st.get("pid"))

                rc_done = bool(st.get("rc_file")) and os.path.isfile(st["rc_file"])

                if rc_done or not self.alive(st.get("pid")):
                    self._finish(name)

        self._launch_ready()
        self._tg_flush()
        self._save()

    def _launch_ready(self):
        """준비된 작업을 priority(작을수록 먼저, 같으면 yaml 순서)로 훑어 빈 GPU 에 띄운다.

        높은 작업이 «지금 띄울 수 있는 상태가 아닐 때만»(GPU 가 차 있거나 아직 준비 전) 낮은 작업이 빈 GPU 를 쓴다.
        단, 높은 작업이 GPU 는 비었는데 «시작 간격» 때문에 미뤄지는 라운드에는 낮은 작업도 기다린다. 선점은 하지 않는다
        (이미 도는 낮은 작업을 내쫓지 않는다).
        """
        order = sorted((n for n, st in self.state.items() if st["state"] == "pending" and self._ready(n)),
                       key=lambda n: (int(self.jobs[n].get("priority", 5)), list(self.jobs).index(n)))

        for name in order:
            job, st = self.jobs[name], self.state[name]

            if job.get("skip_if_done") and job.get("done"):
                ok, _ = self.evaluate(name)                          # 결과가 이미 있으면 돌리지 않는다 (재시작 · Linux 사슬에서 같은 작업을 다시 걸 때)

                if ok:
                    st.update(state="done", finished=self.clock(), skipped=True)
                    self.event(name, "skipped", "done 조건이 이미 충족돼 돌리지 않음" + self._report(name))
                    continue

            blocked = self._guard(name, job)

            if blocked:
                kind, detail, permanent = blocked

                if permanent:
                    st["state"] = "blocked"
                    self.event(name, kind, detail, notify=True)
                elif not st.get("guard_notified"):
                    st["guard_notified"] = True
                    self.event(name, kind, detail, notify=True)

                continue

            wants_gpu = "gpu" in job
            gpu = self._pick_gpu(job) if wants_gpu else None

            if wants_gpu and gpu is None:
                continue                                              # 이 작업이 쓸 GPU 가 차 있음: 다음(낮은) 작업을 본다

            if wants_gpu and self.clock() - self.last_launch < self.gap_s:
                break                                                 # GPU 는 있는데 간격 때문에 미룸: 낮은 작업이 새치기하지 않는다

            try:
                if not job.get("cmd"):
                    raise ValueError("cmd 가 비어 있다")

                self._launch(name, job["cmd"], gpu, 1)
            except Exception as exc:                                  # noqa: BLE001
                st["state"] = "failed"
                self.event(name, "failed", "띄우지 못함: %r" % (exc,), notify=True)

    def _finish(self, name):
        job, st = self.jobs[name], self.state[name]

        if self._is_cancelled(name):                                   # 사람이 멈춘 작업: 끝난 것으로 치지도, 재시도하지도 않는다
            st.update(state="cancelled", finished=self.clock())
            self.event(name, "cancelled", "취소 표시된 작업이 끝남: 재시도 안 함", notify=True)

            return

        ok, problems = self.evaluate(name)
        took = self.clock() - st.get("started", self.clock())
        dur = "%dh%02dm" % (took // 3600, (took % 3600) // 60)

        if ok:
            st.update(state="done", finished=self.clock())
            self.event(name, "done", ("gpu %s %s" % (st.get("gpu"), dur)) + self._report(name), notify=True, problems=[])

            return

        retries = int(job.get("retries", 1))

        if st["attempt"] - 1 < retries:
            cmd = (job.get("retry") or {}).get("cmd") or job.get("cmd")
            self.event(name, "attempt_failed", "; ".join(problems), notify=True)

            try:
                self._launch(name, cmd, st.get("gpu", 0), st["attempt"] + 1)
            except Exception as exc:                                  # noqa: BLE001
                st["state"] = "failed"
                self.event(name, "failed", "재시도를 띄우지 못함: %r" % (exc,), notify=True)

            return

        st.update(state="failed", finished=self.clock())
        self.event(name, "failed", "; ".join(problems), notify=True, problems=problems)

    def _report(self, name):
        """done.report: {file, keys}: 결과 json 의 키 값을 알림 문장에 붙인다 (예: repro verdict)."""
        rep = (self.jobs[name].get("done") or {}).get("report")

        if not rep:
            return ""

        try:
            with open(resolve_text(rep["file"], self.state[name].get("gpu", 0)), encoding="utf-8") as f:
                data = json.load(f)

            return " " + " ".join("%s=%s" % (k, data.get(k)) for k in rep.get("keys", []))
        except (OSError, ValueError, KeyError):
            return " (결과 파일을 못 읽음)"

    def finished(self):
        return all(st["state"] in TERMINAL for st in self.state.values())

    def run(self, max_rounds=None):
        stop_file = os.path.join(self.state_dir, "chain.stop")
        rounds = 0

        while not self.finished():
            if os.path.exists(stop_file):
                self.event("chain", "stopped", "chain.stop 파일: 자식은 그대로 두고 실행기만 끝낸다")

                return 2

            self.step()
            rounds += 1

            if max_rounds is not None and rounds >= max_rounds:
                return 3

            if not self.finished():
                self.sleep(self.poll_s)

        counts = {}

        for st in self.state.values():
            counts[st["state"]] = counts.get(st["state"], 0) + 1

        self.event("chain", "chain_end", json.dumps(counts, ensure_ascii=False), notify=True)

        return 0 if counts.get("failed", 0) == 0 and counts.get("blocked", 0) == 0 else 1


def load_config(path):
    """yaml 을 읽는다. 맨 위 `vars:` 의 ${이름} 을 본문 전체에서 바꾼다(같은 yaml 을 Windows · Linux 에서 쓰도록 경로를 한 곳에 모은다).
    환경 변수 CHAIN_<이름> 이 있으면 그것이 이긴다. 못 푼 ${...} 가 남으면 오류."""
    with open(path, encoding="utf-8") as f:
        text = f.read()

    head = text.split("jobs:", 1)[0]                     # vars 는 jobs 앞에 둔다(jobs 안의 ${..} 는 풀기 전이라 yaml 로 못 읽는다)
    variables = (yaml.safe_load(head) or {}).get("vars", {}) or {}
    values = {}

    for key, value in variables.items():
        values[key] = os.environ.get("CHAIN_" + key, str(value))

    for _ in range(3):                                    # 변수 값이 다른 변수를 가리켜도 된다 (세 번까지)
        values = {k: re.sub(r"\$\{(\w+)\}", lambda m: values.get(m.group(1), m.group(0)), v) for k, v in values.items()}

    text = re.sub(r"\$\{(\w+)\}", lambda m: values.get(m.group(1), m.group(0)), text)
    left = re.findall(r"\$\{\w+\}", text.split("jobs:", 1)[-1])

    if left:
        raise ValueError("풀지 못한 변수: %s" % sorted(set(left)))

    return yaml.safe_load(text)


def main(argv=None):
    import argparse

    parser = argparse.ArgumentParser(description="무인 사슬 실행기")
    parser.add_argument("config")
    parser.add_argument("--state_dir", default=None)
    parser.add_argument("--repo", default=os.getcwd())
    args = parser.parse_args(argv)
    cfg = load_config(args.config)
    state_dir = args.state_dir or cfg.get("state_dir") or os.path.join(os.path.dirname(os.path.abspath(args.config)), "state")
    chain = Chain(cfg, state_dir, repo_root=args.repo)
    chain.config_path = os.path.abspath(args.config)
    chain._cfg_mtime = os.path.getmtime(chain.config_path)
    pid_path = os.path.join(state_dir, "chain.pid")

    if os.path.exists(pid_path):
        try:
            old = int(open(pid_path).read().strip())
        except ValueError:
            old = 0

        if old and old != os.getpid() and pid_alive(old):
            print("이미 실행기가 돈다 pid %d" % old)

            return 4

    with open(pid_path, "w") as f:
        f.write(str(os.getpid()))

    chain.event("chain", "chain_start", "pid %d, 작업 %d 개" % (os.getpid(), len(chain.jobs)))

    return chain.run()


if __name__ == "__main__":
    sys.exit(main())
