"""S0 연쇄 드라이버 (순수 파이썬, Kit 를 직접 띄우지 않고 `run_kit.sh` 를 부른다).

세 판(NVIDIA · v2 · E1) x 축 1 (6 묶음) · 축 2 (1) · 축 3 (칸 풀어쓰기) 를 GPU 둘에 나눠 돈다.

  python -m foothold_s2.eval.s0_chain --root <결과 폴더> [--policies e1,v2,nvidia] [--gpus 0,1]

규칙
  - 이미 끝나 점검까지 통과한 일은 건너뛴다 (이어 돌리기).
  - 끝났다는 판정은 종료 코드가 아니라 `manifest.check_run_dir` (Traceback 과 줄 수).
  - 두 Isaac 을 띄우는 사이에 `START_GAP_S` 초를 둔다 (USD 임시 폴더 충돌 전례).
  - 실패한 일은 한 번 더 시도하고, 그래도 안 되면 기록하고 다음으로 간다 (한 건 실패로 전체가 서지 않는다).
  - 학습은 하지 않는다. 평가만.
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import threading
import time

from foothold_s2.eval import cells, manifest

START_GAP_S = 60

# 판 이름 -> (run_eval --policy 값, 체크포인트). E1 은 sha256 c8951b79 ... 2df47e8.
CHECKPOINTS = {
    "e1": ("e1", "C:/Users/AI-WS01/s2_lab/step1_run_b2/fixtures/model_20000.pt"),
    "v2": ("v2", "C:/isaac/IsaacLab/logs/rsl_rl/unitree_go2_gap_nvidia/"
                 "2026-09-25_17-29-36_20260925_v2g2-feetair01_seed42_iter3000/model_3000.pt"),
    "nvidia": ("nvidia", "C:/isaac/IsaacLab/logs/rsl_rl/unitree_go2_gap_nvidia/"
                         "nvidia_pretrained_source/nvidia_pretrained.pt"),
}


def _cmd_text(cmd):
    return ",".join(("%g" % c) for c in cmd)


def expand_jobs(policy, root, include_axes=("axis1", "axis2", "axis3"), vy_obs=None,
                axis1_dir_override=None):
    """한 판의 모든 일. 각 일: name, out(폴더), args(run_eval 인자), raw(원자료 이름), rows(기대 줄 수)."""
    kind, ckpt = CHECKPOINTS[policy]
    base = ["--policy", kind, "--checkpoint", ckpt, "--label", policy]
    jobs = []

    if "axis1" in include_axes:
        for set_name, names in cells.AXIS1_SETS.items():
            for speed in cells.AXIS1_SPEEDS:
                out = os.path.join(axis1_dir_override or os.path.join(root, policy, "axis1"),
                                   set_name, "v%s" % speed)
                jobs.append(dict(name="%s/axis1/%s/v%s" % (policy, set_name, speed), out=out,
                                 args=["axis1"] + base + ["--set", set_name, "--speed", str(speed)],
                                 raw="axis1_raw.csv", rows=cells.AXIS1_PARAMS["episodes"] * len(names)))

    if "axis2" in include_axes:
        jobs.append(dict(name="%s/axis2" % policy, out=os.path.join(root, policy, "axis2"),
                         args=["axis2"] + base, raw="axis2_cells.csv", rows=len(cells.AXIS2_CELLS)))

    if "axis3" in include_axes:
        for row in cells.axis3_table(vy_obs=vy_obs):
            if row["status"] != "measure":
                continue

            names = [n for n in cells.TERRAIN_GROUPS[row["group"]] if n not in cells.START_SHEETS]

            for cmd in row["commands"]:
                tag = "%s_%s_%s" % (row["group"], row["direction"], _cmd_text(cmd).replace(",", "_"))
                args = ["axis3"] + base + ["--group", row["group"], "--cmd", _cmd_text(cmd),
                                           "--direction", row["direction"]]

                if row.get("basis") == cells.VY_ASSUMED_LABEL:
                    args += ["--cmd_basis", cells.VY_ASSUMED_LABEL]

                jobs.append(dict(name="%s/axis3/%s" % (policy, tag),
                                 out=os.path.join(root, policy, "axis3", tag), args=args,
                                 raw="axis3_raw.csv",
                                 rows=cells.AXIS3_PARAMS["episodes"] * len(names)))

    return jobs


def job_done(job):
    """끝나 점검까지 통과했나 (종료 코드가 아니라 산출물로)."""
    rc = os.path.join(job["out"], "rc.txt")

    if not os.path.isfile(rc):
        return False

    ok, _problems = manifest.check_run_dir(job["out"], job["rows"], job["raw"])

    return ok


class Scheduler:
    def __init__(self, jobs, gpus, root, run_kit):
        self.queue = list(jobs)
        self.gpus = gpus
        self.root = root
        self.run_kit = run_kit
        self.lock = threading.Lock()
        self.last_start = 0.0
        self.log_path = os.path.join(root, "s0_chain.log")
        self.status_path = os.path.join(root, "s0_status.jsonl")

    def log(self, text):
        line = "%s %s" % (time.strftime("%F %T"), text)

        with self.lock, open(self.log_path, "a", encoding="utf-8") as handle:
            handle.write(line + "\n")

        print(line, flush=True)

    def take(self):
        with self.lock:
            return self.queue.pop(0) if self.queue else None

    def wait_gap(self):
        while True:
            with self.lock:
                wait = self.last_start + START_GAP_S - time.time()

                if wait <= 0:
                    self.last_start = time.time()
                    return

            time.sleep(min(wait, 5))

    def run_job(self, job, gpu):
        for attempt in (1, 2):
            if os.path.isdir(job["out"]):
                shutil.rmtree(job["out"], ignore_errors=True)

            self.wait_gap()
            self.log("start %s gpu%d try%d" % (job["name"], gpu, attempt))
            env = dict(os.environ, DEVICE="cuda:%d" % gpu)
            code = subprocess.call(["bash", self.run_kit, job["out"]] + job["args"], env=env,
                                   creationflags=0x08000000 if os.name == "nt" else 0)
            os.makedirs(job["out"], exist_ok=True)

            with open(os.path.join(job["out"], "rc.txt"), "w", encoding="utf-8") as handle:
                handle.write("rc=%s\n" % code)

            ok, problems = manifest.check_run_dir(job["out"], job["rows"], job["raw"])
            self.log("end %s gpu%d rc=%s ok=%s %s" % (job["name"], gpu, code, ok, problems))

            with self.lock, open(self.status_path, "a", encoding="utf-8") as handle:
                handle.write(json.dumps(dict(name=job["name"], gpu=gpu, attempt=attempt, rc=code,
                                             ok=ok, problems=problems, at=time.strftime("%F %T")),
                                        ensure_ascii=False) + "\n")

            if ok:
                return True

        return False

    def worker(self, gpu):
        while True:
            job = self.take()

            if job is None:
                return

            if job_done(job):
                self.log("skip %s (이미 통과)" % job["name"])
                continue

            self.run_job(job, gpu)


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True)
    parser.add_argument("--policies", default="e1,v2,nvidia")
    parser.add_argument("--axes", default="axis1,axis2,axis3")
    parser.add_argument("--gpus", default="0,1")
    parser.add_argument("--e1_axis1_dir", default=None,
                        help="E1 축 1 을 이미 돌려 둔 폴더 (<set>/v<speed>). 있으면 거기를 쓴다")
    args = parser.parse_args(argv)

    os.makedirs(args.root, exist_ok=True)
    run_kit = os.path.join(manifest.EVAL_DIR, "run_kit.sh").replace("\\", "/")
    jobs = []

    for policy in args.policies.split(","):
        override = args.e1_axis1_dir if policy == "e1" else None
        jobs += expand_jobs(policy, args.root, tuple(args.axes.split(",")),
                            axis1_dir_override=override)

    gpus = [int(g) for g in args.gpus.split(",")]
    sched = Scheduler(jobs, gpus, args.root, run_kit)
    sched.log("chain start: %d 일, GPU %s" % (len(jobs), gpus))
    threads = [threading.Thread(target=sched.worker, args=(g,)) for g in gpus]

    for t in threads:
        t.start()

    for t in threads:
        t.join()

    sched.log("chain end")
    pending = [j["name"] for j in jobs if not job_done(j)]
    sched.log("통과 못 한 일 %d: %s" % (len(pending), pending))

    return 0 if not pending else 1


if __name__ == "__main__":
    sys.exit(main())
