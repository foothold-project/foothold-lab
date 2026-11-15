"""CPU test double for the registered slot. Never imports or starts Isaac."""
import json
import msvcrt
import os
from pathlib import Path
import subprocess
import sys
import time


def value(items, key):
    return items[items.index(key) + 1]


def main():
    assert os.environ.get("CUDA_VISIBLE_DEVICES") == "-1"
    args = sys.argv[1:]
    sep = args.index("--")
    head, frozen = args[:sep], args[sep + 1:]
    record = Path(value(head, "--record"))
    log = Path(value(head, "--watch_log"))
    lock = Path(value(head, "--lock"))
    registry = Path(value(head, "--registry"))
    usd_root = value(head, "--usd_root")
    attempt = value(head, "--attempt")
    tag = log.name.removesuffix(".log")
    lock.parent.mkdir(parents=True, exist_ok=True)
    registry.parent.mkdir(parents=True, exist_ok=True)
    with lock.open("a+b") as f:
        f.seek(0)
        while True:
            try:
                msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
                break
            except OSError:
                time.sleep(0.03)
        try:
            registry.write_text(json.dumps({"attempt": attempt, "tag": tag, "lock": str(lock)}), encoding="utf-8")
            marker = os.environ.get("FAKE_SLOT_READY")
            if marker:
                Path(marker).write_text(tag, encoding="utf-8")
                release = Path(os.environ["FAKE_SLOT_RELEASE"])
                until = time.time() + 15
                while not release.exists() and time.time() < until:
                    time.sleep(0.03)
            if "--cpu_fixture" not in frozen:
                frozen.insert(frozen.index("--"), "--cpu_fixture")
            done = subprocess.run(frozen, capture_output=True, text=True, env=dict(os.environ, CUDA_VISIBLE_DEVICES="-1"), timeout=60)
            text = done.stdout + done.stderr
            bad_yaml = "wrong_yaml_" in tag
            if bad_yaml and done.returncode == 0:
                text += "AssertionError: train_yaml is not the parent run's\n"
            log.write_text(text + f"C:/cpu/{attempt}/IsaacLab/usd_20261014_120000_1234/go2.usd\n[INFO]: Time taken for scene creation\n", encoding="utf-8")
            rc = done.returncode if done.returncode else (1 if bad_yaml else 0)
            if rc == 0:
                out = Path(value(frozen, "--manifest")).parent / "data" / tag
                out.mkdir(parents=True, exist_ok=True)
                (out / "cells.json").write_text('{"fake":true}', encoding="utf-8")
                (out / "traj.npz").write_bytes(b"identical fake trajectory")
                (out / "meta.json").write_text('{"fake":true}', encoding="utf-8")
                (out / "episodes.csv").write_text("episode,cell,family\n", encoding="utf-8")
            record.write_text(json.dumps({"slot_rc": rc, "state_at_release": "fake", "hold_s": 0.01,
                "registry": str(registry), "lock": str(lock), "usd_root": usd_root,
                "expect_conversions": value(head, "--expect_conversions")}), encoding="utf-8")
            orphan_s = os.environ.get("FAKE_SLOT_ORPHAN_SECONDS")
            if orphan_s and rc == 0:
                subprocess.Popen([sys.executable, "-B", "-c", f"import time; time.sleep({float(orphan_s)})"])
                time.sleep(0.2)
            return rc
        finally:
            f.seek(0)
            msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)


if __name__ == "__main__":
    raise SystemExit(main())
