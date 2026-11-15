"""사슬 실행기를 창 없이 떼어 띄운다 (세션이 끝나도 산다).

    python -m foothold_s2.chain.start <chain.yaml> [--state_dir DIR]

Windows: pythonw.exe(있으면) + CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP (DETACHED_PROCESS 와 같이 쓰면 창이 뜬다).
Linux: 새 세션(nohup 과 같음). systemd --user 로 두려면 `chain.service` 를 쓴다.
띄운 뒤 10 초 안에 상태 폴더의 chain_status.jsonl 에 chain_start 가 적히는지 확인하고 pid 를 출력한다.
"""

import argparse
import os
import subprocess
import sys
import time

from foothold_s2.chain import runner


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("config")
    parser.add_argument("--state_dir", default=None)
    args = parser.parse_args(argv)
    cfg = runner.load_config(args.config)
    state_dir = args.state_dir or cfg.get("state_dir") or os.path.join(os.path.dirname(os.path.abspath(args.config)), "state")
    os.makedirs(state_dir, exist_ok=True)
    py = sys.executable

    if runner.IS_WIN:
        pyw = os.path.join(os.path.dirname(py), "pythonw.exe")
        py = pyw if os.path.isfile(pyw) else py

    repo = os.getcwd()
    env = dict(os.environ, PYTHONPATH=repo + os.pathsep + os.environ.get("PYTHONPATH", ""))
    cmd = [py, "-m", "foothold_s2.chain.runner", os.path.abspath(args.config), "--state_dir", state_dir, "--repo", repo]
    kwargs = {"cwd": repo, "env": env, "stdin": subprocess.DEVNULL, "stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL,
              "close_fds": True}

    if runner.IS_WIN:
        kwargs["creationflags"] = runner.CREATE_NO_WINDOW | runner.CREATE_NEW_PROCESS_GROUP
    else:
        kwargs["start_new_session"] = True

    status = os.path.join(state_dir, "chain_status.jsonl")
    before = os.path.getsize(status) if os.path.exists(status) else 0
    pid = subprocess.Popen(cmd, **kwargs).pid
    deadline = time.time() + 10

    while time.time() < deadline:
        if os.path.exists(status) and os.path.getsize(status) > before and "chain_start" in open(status, encoding="utf-8").read():
            print("chain runner pid %d, 상태 폴더 %s" % (pid, state_dir))

            return 0

        time.sleep(0.5)

    print("10 초 안에 chain_start 가 안 적혔다 (pid %d). 상태 폴더 %s 를 확인" % (pid, state_dir))

    return 1


if __name__ == "__main__":
    sys.exit(main())
