"""CPU connected driver→slot double→frozen CLI proof. No GPU or Isaac code executes."""
import copy
import json
import msvcrt
import os
from pathlib import Path
import runpy
import subprocess
import sys
import threading
import time

HERE = Path(__file__).parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
from s1043_manifest import CANDIDATE_FILES, approval_binding, canonical_hash, launch_errors, sha256


def check(label, ok):
    print(("PASS" if ok else "FAIL"), label, flush=True)
    if not ok:
        raise AssertionError(label)


def approved_fixture():
    folder = ROOT / "fixture_17r_e" / f"run_{time.strftime('%Y%m%d_%H%M%S')}_{os.getpid()}"
    folder.mkdir(parents=True, exist_ok=True)
    m = json.loads((HERE / "manifest_s1043.json").read_text(encoding="utf-8"))
    c = m["contract"]
    paths = c["paths"]
    for key in paths:
        if key == "registry":
            paths[key] = str(folder / "registry/isaac_usd_registry_v3.json")
        elif key in ("convert_lock", "run_lease"):
            paths[key] = str(folder / "locks" / Path(paths[key]).name)
        elif key == "compare_report":
            paths[key] = str(folder / "reports/bundle_compare.json")
        else:
            paths[key] = str(folder / key)
    sentinel = folder / "fixture_input.txt"
    sentinel.write_text("FROZEN ORIGINAL\n", encoding="utf-8")
    c["fixture_inputs"] = {"sentinel": {"path": str(sentinel), "sha256": sha256(sentinel)}}
    c["runtime"].update(torch="CPU_FIXTURE_ONLY", isaac="CPU_FIXTURE_ONLY")
    c["device"].update(gpu_index=0, gpu_uuid="GPU-CPU-FIXTURE", CUDA_VISIBLE_DEVICES="0")
    m["contract_sha256"] = canonical_hash(c)
    report = {"verdict": "SAME", "contract_sha256": m["contract_sha256"], "bundle_sha256": {
        f"{arm}_{fn}": c["inputs"][c["branches"][arm]["bundle_json" if fn == "bundle.json" else "bundle_npz"]]["sha256"]
        for arm in ("off", "on") for fn in ("bundle.json", "bundle.npz")}}
    report_file = Path(paths["compare_report"])
    report_file.parent.mkdir(parents=True, exist_ok=True)
    report_file.write_text(json.dumps(report), encoding="utf-8")
    e = m["execution"]
    e.update(contract_sha256=m["contract_sha256"], attempt="cpu-normal-e", stage="A", gpu_index=0,
             approval_id=f"cpu-normal-e-{os.getpid()}", log_name="17r_normal", restart_scope="single_start_no_reuse",
             termination_policy={"terminate_grace_s": 0.5, "partial_result": "held"},
             gpu_uuid="GPU-CPU-FIXTURE", CUDA_VISIBLE_DEVICES="0", diagnostic_repeat_original=False,
             deadline_epoch=time.time() + 3600, risk_limit={"max_child_launches": 20,
             "max_retries_per_run": 1, "max_wall_s": 1800},
             approval_path=str(folder / "approval.json"), comparison_report_sha256=sha256(report_file),
             run_lease_participants_confirmed=True, convert_lock_shared_confirmed=True,
             candidate_hashes={name: sha256(HERE / name) for name in CANDIDATE_FILES})
    approval = {"approved": True, "by": "CPU_FIXTURE_ONLY", "approved_at": "fixture",
                "reviewed": approval_binding(m)}
    Path(e["approval_path"]).write_text(json.dumps(approval, sort_keys=True), encoding="utf-8")
    e["approval_sha256"] = sha256(e["approval_path"])
    manifest = folder / "manifest.json"
    manifest.write_text(json.dumps(m, ensure_ascii=False), encoding="utf-8")
    return m, manifest, e["approval_sha256"], sentinel


def main():
    assert os.environ.get("CUDA_VISIBLE_DEVICES") == "-1"
    m, manifest, digest, sentinel = approved_fixture()
    check("approved CPU fixture gate", launch_errors(m, approved_digest=digest) == [])
    driver = HERE / "cmdr_eval_driver_s1043.py"
    old_argv = sys.argv
    try:
        sys.argv = [str(driver), "--manifest", str(manifest), "--expect_self_sha", sha256(driver),
                    "--approved_digest", digest, "--log", "17r_normal"]
        ns = runpy.run_path(str(driver), run_name="connected_cpu_probe")
    finally:
        sys.argv = old_argv
    g = ns["start"].__globals__
    Path(g["OUT"]).mkdir(parents=True, exist_ok=True)
    original_sleep = time.sleep
    time.sleep = lambda seconds: original_sleep(min(seconds, .01))
    g["unseen_running"] = lambda: False
    g["live_runs"] = lambda tags: []
    g["training_running"] = lambda: False
    g["foreign_isaac"] = lambda *args, **kwargs: []
    g["gpu_preflight"] = lambda: {"gpu_index": "0", "uuid": "GPU-CPU-FIXTURE", "free_mib": 8192}
    def ready(label):
        if label not in g["LOG"]["ckpt"]:
            model = g["MODELS"][label][0]
            g["LOG"]["ckpt"][label] = {"path": model, "sha256": sha256(model)}
        return True
    g["ready"] = ready
    g["validate"] = lambda *args, **kwargs: ""
    g["fingerprint"] = lambda tag: {"synthetic": "same"}
    fake_slot = HERE / "fake_slot_17r.py"
    pause = {"ready": None, "release": None}
    orphan = {"seconds": None}
    def fake_popen(argv, cwd=None, env=None):
        e = dict(env or os.environ, CUDA_VISIBLE_DEVICES="-1")
        if pause["ready"]:
            e["FAKE_SLOT_READY"] = str(pause["ready"])
            e["FAKE_SLOT_RELEASE"] = str(pause["release"])
        if orphan["seconds"]:
            e["FAKE_SLOT_ORPHAN_SECONDS"] = str(orphan["seconds"])
        return subprocess.Popen([sys.executable, "-B", str(fake_slot)] + argv[2:], cwd=cwd, env=e)
    g["POPEN"] = fake_popen
    try:
        check("both branch completion", g["training_done"]() == "")
        g["start"]()
        check("start pins and parent ready", bool(g["P0"]) and "p20000" in g["LOG"]["ckpt"])
        # The actual log lock is held after start. A second OS handle must fail.
        lock = Path(g["OUT"]) / "17r_normal.lock"
        with lock.open("a+b") as other:
            other.seek(0)
            try:
                msvcrt.locking(other.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError:
                blocked = True
            else:
                blocked = False
                other.seek(0)
                msvcrt.locking(other.fileno(), msvcrt.LK_UNLCK, 1)
        check("actual OS log lock", blocked)
        check("start tests connected", g["tests"](g["P0"]) is True)
        check("slot registry written", Path(m["contract"]["paths"]["registry"]).exists())
        records = list(Path(m["contract"]["paths"]["slot_records"]).glob("*.json"))
        check("frozen CLI reached", any("READY_CPU_NO_CHILD" in p.read_text(encoding="utf-8", errors="replace") for p in Path(g["OUT"]).glob("cq_test_*.log")))
        print("NORMAL_CONNECTED_PASS", len(g["TRIES"]), "slot tries", flush=True)
        on_only = copy.deepcopy(m)
        on_only["contract"]["inputs"]["off_result"]["path"] = str(manifest.parent / "missing_off_result.json")
        on_only["contract_sha256"] = canonical_hash(on_only["contract"])
        g["MANIFEST"] = on_only
        check("true on-only training refused", "off" in g["training_done"]())
        g["MANIFEST"] = m
        for name, mutate in (("approval limit", lambda x: x["execution"]["risk_limit"].__setitem__("max_child_launches", 21)),
                             ("candidate code", lambda x: x["execution"]["candidate_hashes"].__setitem__("frozen_exec_s1043.py", "0" * 64))):
            bad = copy.deepcopy(m)
            mutate(bad)
            g["MANIFEST"] = bad
            try:
                g["gate"](name, "p20000")
            except SystemExit as exc:
                blocked = exc.code == 4
            else:
                blocked = False
            check(name + " gate blocked", blocked)
            g["MANIFEST"] = m
            g["LOG"].pop("stopped", None)
        # A wrapper that exits before a CPU grandchild must retain the run lease until the grandchild exits.
        orphan["seconds"] = 3
        orphan_tag = "cq_test_deadbeef_g0t123456p123_ka_orig2"
        orphan_cmd = g["q"]("q_eval.py", orphan_tag, m["contract"]["parent"]["path"], "flat", "stop03", 100, True, 1000)
        began = time.monotonic()
        orphan_rc, _ = g["guarded"](orphan_tag, orphan_cmd, tries=1, ck="p20000")
        orphan["seconds"] = None
        check("connected orphan descendant lease", orphan_rc == 0 and time.monotonic() - began >= 2.5)
        # Mutation occurs only after the fake slot has acquired the real conversion lock and signalled readiness.
        ready_file = manifest.parent / "slot_ready.txt"
        release_file = manifest.parent / "slot_release.txt"
        for path in (ready_file, release_file):
            if path.exists():
                path.unlink()
        pause.update(ready=ready_file, release=release_file)
        tag = "cq_test_deadbeef_g0t123456p123_ka_copy"
        cmd = g["q"]("q_eval_cmdr.py", tag, m["contract"]["parent"]["path"], "flat", "stop03", 100, True, 1000)
        outcome = {}
        thread = threading.Thread(target=lambda: outcome.update(zip(("rc", "tries"), g["guarded"](tag, cmd, tries=1, ck="p20000"))))
        thread.start()
        until = time.time() + 20
        while not ready_file.exists() and time.time() < until:
            original_sleep(.05)
        check("fake slot actually waiting", ready_file.exists() and thread.is_alive())
        def held(path):
            with Path(path).open("a+b") as f:
                f.seek(0)
                try:
                    msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
                except OSError:
                    return True
                f.seek(0)
                msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
                return False
        check("shared conversion OS lock", held(m["contract"]["paths"]["convert_lock"]))
        check("run lease OS lock during slot", held(m["contract"]["paths"]["run_lease"]))
        reg = json.loads(Path(m["contract"]["paths"]["registry"]).read_text(encoding="utf-8"))
        check("registry names active attempt", reg.get("tag") == tag)
        sentinel.write_text("MUTATED AFTER SLOT WAIT\n", encoding="utf-8")
        release_file.write_text("go", encoding="utf-8")
        thread.join(timeout=30)
        check("slot wait input mutation caught", not thread.is_alive() and outcome.get("rc") == 92)
        sentinel.write_text("FROZEN ORIGINAL\n", encoding="utf-8")
        print("MUTANT_CAUGHT slot_wait_input", flush=True)
    finally:
        time.sleep = original_sleep


if __name__ == "__main__":
    main()
