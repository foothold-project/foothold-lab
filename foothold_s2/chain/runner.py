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
TERMINAL = ("done", "failed", "blocked")

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
    """lead 창에 한 줄. 실패해도 사슬은 멈추지 않는다(기록만)."""
    if not notify_cfg or not notify_cfg.get("cmd"):
        return "no notifier"

    cmd = [str(c).replace("{text}", text) for c in notify_cfg["cmd"]]
    kwargs = {"cwd": notify_cfg.get("cwd") or None, "capture_output": True, "text": True, "timeout": 60,
              "stdin": subprocess.DEVNULL}

    if IS_WIN:
        kwargs["creationflags"] = CREATE_NO_WINDOW

    try:
        out = subprocess.run(cmd, **kwargs)

        return "rc=%s %s" % (out.returncode, (out.stdout or out.stderr or "").strip()[:200])
    except Exception as exc:                                         # noqa: BLE001
        return "notify error: %r" % (exc,)


class Chain:
    def __init__(self, config, state_dir, launcher=default_launcher, notifier=default_notifier, alive=pid_alive,
                 clock=time.time, sleep=time.sleep, repo_root=None):
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
            for d in j.get("depends_on", []):
                if d not in self.jobs:
                    raise ValueError("%s 가 모르는 작업 %s 에 기댄다" % (j["name"], d))

        self.state_path = os.path.join(state_dir, "chain_state.json")
        self.status_path = os.path.join(state_dir, "chain_status.jsonl")
        self.poll_s = float(config.get("poll_s", 30))
        self.gap_s = float(config.get("start_gap_s", 60))
        self.last_launch = 0.0
        self.state = self._load_state()
        self.ended = False

    # ------------------------------------------------------------------ 상태 · 기록
    def _load_state(self):
        try:
            with open(self.state_path, encoding="utf-8") as f:
                state = json.load(f)
        except (OSError, ValueError):
            state = {}

        for name, job in self.jobs.items():
            st = state.setdefault(name, {"state": "pending", "attempt": 0})

            if job.get("adopt") and st["state"] == "pending":
                st.update(state="running", pid=int(job["adopt"]["pid"]), adopted=True, started=self.clock(),
                          gpu=self._fixed_gpu(job), attempt=1)

        return state

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

        if notify:
            res = self.notifier(self.cfg.get("notify"), "[chain] %s %s %s" % (name, kind, detail))
            rec2 = {"time": rec["time"], "job": name, "event": "notified", "detail": str(res)[:200]}

            with open(self.status_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(rec2, ensure_ascii=False) + "\n")

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
        env.update({"CUDA_DEVICE_ORDER": "PCI_BUS_ID", "DEVICE": "cuda:%s" % gpu, "PYTHONUNBUFFERED": "1"})
        env.update({k: resolve_text(str(v), gpu) for k, v in (self.cfg.get("env") or {}).items()})
        env.update({k: resolve_text(str(v), gpu) for k, v in (job.get("env") or {}).items()})
        pp = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = self.repo_root + (os.pathsep + pp if pp else "")

        return env

    def _launch(self, name, cmd, gpu, attempt):
        job = self.jobs[name]
        argv, rc_file, log = self._argv(job, cmd, gpu, name, attempt)
        os.makedirs(os.path.dirname(os.path.abspath(log)), exist_ok=True)
        pid = self.launcher(argv, job.get("cwd") or self.repo_root, self._env(job, gpu), log)
        st = self.state[name]
        st.update(state="running", pid=pid, gpu=gpu, attempt=attempt, rc_file=rc_file, log=log, started=self.clock(),
                  evidence=False, adopted=False)
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

            if text != "rc=0":
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

    def step(self):
        for name, job in self.jobs.items():
            st = self.state[name]

            if st["state"] == "pending":
                deps = self._deps(name)

                if any(d in ("failed", "blocked") for d in deps):
                    st["state"] = "blocked"
                    bad = [d for d in job.get("depends_on", []) if self.state[d]["state"] in ("failed", "blocked")]
                    self.event(name, "blocked", "앞 작업 실패: %s" % ",".join(bad), notify=True)
                elif all(d == "done" for d in deps):
                    gpu = self._pick_gpu(job)

                    if gpu is not None and self.clock() - self.last_launch >= self.gap_s:
                        try:
                            self._launch(name, job["cmd"], gpu, 1)
                        except Exception as exc:                      # noqa: BLE001
                            st["state"] = "failed"
                            self.event(name, "failed", "띄우지 못함: %r" % (exc,), notify=True)

            elif st["state"] == "running":
                if not st.get("evidence") and self._first_evidence(name):
                    st["evidence"] = True
                    self.event(name, "first_evidence", "", pid=st.get("pid"))

                rc_done = bool(st.get("rc_file")) and os.path.isfile(st["rc_file"])

                if rc_done or not self.alive(st.get("pid")):
                    self._finish(name)

        self._save()

    def _finish(self, name):
        job, st = self.jobs[name], self.state[name]
        ok, problems = self.evaluate(name)
        took = self.clock() - st.get("started", self.clock())
        dur = "%dh%02dm" % (took // 3600, (took % 3600) // 60)

        if ok:
            st.update(state="done", finished=self.clock())
            self.event(name, "done", "gpu %s %s" % (st.get("gpu"), dur), notify=True, problems=[])

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
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


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
