"""산출물 기록 (41 §10). command.txt · run_manifest.json · CSV · 실행 뒤 점검.

순수 파이썬 (torch 는 있으면 환경 기록에만 쓴다).

실행 뒤 점검 `check_run_dir` 이 중요하다. Isaac 은 예외 뒤에도 종료 코드 0 을 내므로
「끝났다」는 종료 코드가 아니라 로그의 Traceback 과 산출물 줄 수로 판정한다.
"""

import csv
import hashlib
import json
import os
import platform
import subprocess
import sys
import time

EVAL_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(os.path.dirname(EVAL_DIR))


def file_sha256(path):
    digest = hashlib.sha256()

    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)

    return digest.hexdigest()


GATES_RELPATH = "inbox/jay/20261019-design/evidence/baselines/gates-v1.json"


def gates_record(path=None):
    """어느 판정 규칙 파일로 판정하나 (ASTRA-F F2): 경로와 sha256. 줄끝을 LF 로 맞춰 해시해 Windows(CRLF)와 Linux 가 같은 값이다."""
    import hashlib

    path = path or os.path.join(REPO_ROOT, GATES_RELPATH)

    try:
        raw = open(path, "rb").read().replace(b"\r\n", b"\n")

        return {"path": GATES_RELPATH if path.endswith(GATES_RELPATH) else path, "sha256_lf": hashlib.sha256(raw).hexdigest(),
                "bytes": len(raw)}
    except OSError as error:
        return {"path": path, "sha256_lf": None, "error": str(error)}


def harness_record():
    """이 하네스가 어느 판인가: 커밋 + 소스 파일 해시 (커밋 전 변경도 해시에는 잡힌다)."""
    files = {}

    for name in sorted(os.listdir(EVAL_DIR)):
        if name.endswith(".py"):
            files[name] = file_sha256(os.path.join(EVAL_DIR, name))

    try:
        commit = subprocess.check_output(["git", "-C", REPO_ROOT, "rev-parse", "HEAD"],
                                         stderr=subprocess.DEVNULL).decode().strip()
        dirty = bool(subprocess.check_output(
            ["git", "-C", REPO_ROOT, "status", "--porcelain", "--", "foothold_s2/eval"],
            stderr=subprocess.DEVNULL).decode().strip())
    except Exception as error:  # noqa: BLE001
        commit, dirty = "<못 읽음: %s>" % error, None

    return {"git_commit": commit, "eval_dir_dirty": dirty, "files_sha256": files}


def environment_record():
    """무엇 위에서 돌았나. 하나가 안 읽혀도 실행을 죽이지 않고 사유를 적는다."""
    record = {}

    def attempt(key, fn):
        try:
            record[key] = fn()
        except Exception as error:  # noqa: BLE001
            record[key] = "<못 읽음: %s>" % error

    attempt("python", platform.python_version())
    attempt("platform", platform.platform())
    attempt("hostname", platform.node())

    def torch_info():
        import torch

        return {"torch": torch.__version__, "cuda": torch.version.cuda,
                "gpus": [torch.cuda.get_device_name(i) for i in range(torch.cuda.device_count())]}

    attempt("torch", torch_info)
    attempt("isaaclab", lambda: __import__("isaaclab").__version__)

    return record


def write_command_txt(out_dir, argv, started):
    path = os.path.join(out_dir, "command.txt")

    with open(path, "w", encoding="utf-8") as handle:
        handle.write(" ".join(_quote(a) for a in argv) + "\n")
        handle.write("# started %s\n" % started)

    return path


def append_exit(out_dir, code):
    with open(os.path.join(out_dir, "command.txt"), "a", encoding="utf-8") as handle:
        handle.write("# exit %s at %s\n" % (code, time.strftime("%Y-%m-%d %H:%M:%S")))


def _quote(arg):
    return '"%s"' % arg if " " in arg else arg


def write_json(path, obj):
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(obj, handle, ensure_ascii=False, indent=2, default=str)


def write_csv(path, rows, fieldnames=None):
    """행 목록을 CSV 로. 열 순서는 처음 나온 순서이고, 행마다 열이 다르면 죽는다.

    None 은 빈 칸이다 («못 쟀다» 와 0 을 구별).
    """
    if not rows and not fieldnames:
        raise ValueError("행이 없는 CSV 는 쓰지 않습니다: %s" % path)

    names = list(fieldnames or rows[0].keys())

    for row in rows:
        if set(row.keys()) != set(names):
            raise ValueError("열이 어긋난 행: %r 대 %r" % (sorted(row), sorted(names)))

    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=names)
        writer.writeheader()

        for row in rows:
            writer.writerow({k: ("" if row[k] is None else row[k]) for k in names})

    return path


def read_csv(path):
    with open(path, newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def check_run_dir(out_dir, expected_rows, raw_name, log_name="run.log"):
    """실행이 정말 끝났나. 종료 코드는 믿지 않는다.

    통과 조건: 원자료 CSV 가 있고 줄 수가 기대와 같고, manifest 가 있고,
    로그에 Traceback 이 없다. 돌려주는 것은 `(통과 여부, 사유 목록)`.
    """
    problems = []
    raw_path = os.path.join(out_dir, raw_name)
    excluded = set()
    if raw_name == "axis3_raw.csv":
        record_path = os.path.join(out_dir, "run_manifest.json")
        if os.path.isfile(record_path):
            with open(record_path, encoding="utf-8") as handle:
                record = json.load(handle)
            if record.get("excluded_start_terrains"):
                from foothold_s2.eval import cells
                try:
                    excluded = set(record["excluded_start_terrains"])
                    plan = record["start_plan"]
                    count = record["episodes_per_terrain"]
                    with open(os.path.join(out_dir, "axis3_starts.json"), encoding="utf-8") as handle:
                        persisted = json.load(handle)
                    valid = (record["group"] == "sparse" and record["axis3_rule"] == "sparse_short"
                             and set(plan) == set(cells.TERRAIN_GROUPS["sparse"]) and persisted == plan
                             and excluded == {n for n, r in plan.items() if r["status"] == "no_start"}
                             and all(plan[n]["origin"] is None and plan[n]["eligible"] is False for n in excluded)
                             and isinstance(count, int) and count > 0 and expected_rows == len(plan) * count)
                    if not valid:
                        raise ValueError("제외 근거 불일치")
                    expected_rows -= len(excluded) * count
                except (KeyError, TypeError, OSError, ValueError):
                    problems.append("시작점 제외 기록 불일치")

    if not os.path.isfile(raw_path):
        problems.append("원자료 %s 없음" % raw_name)
    else:
        rows = read_csv(raw_path)
        n = len(rows)
        if any(row.get("terrain") in excluded for row in rows):
            problems.append("시작점 없는 지형의 판정 원자료가 있음")

        if n != expected_rows:
            problems.append("원자료 줄 수 %d, 기대 %d" % (n, expected_rows))

    if not os.path.isfile(os.path.join(out_dir, "run_manifest.json")):
        problems.append("run_manifest.json 없음")

    log_path = os.path.join(out_dir, log_name)

    if os.path.isfile(log_path):
        with open(log_path, encoding="utf-8", errors="replace") as handle:
            text = handle.read()

        count = text.count("Traceback")

        if count:
            problems.append("로그에 Traceback %d 줄" % count)
    else:
        problems.append("로그 %s 없음" % log_name)

    return (not problems), problems


def argv_for_record():
    return [sys.executable] + sys.argv
