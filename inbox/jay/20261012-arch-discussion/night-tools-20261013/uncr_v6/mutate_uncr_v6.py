"""Break-the-guard checks for test_uncr_v6.py, including frozen_exec and environment checks.
Mutants live only in codexA/mutants while their CPU test runs. Test fixtures remain in codexA."""
import concurrent.futures as cf
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
RV = "uncr_revalidate_v3.py"
V5 = "unseen_driver_cmdr_v6.py"
FZ = "frozen_exec.py"
WORK = "C:/Users/AI-WS01/.claude/jobs/09bbf294/tmp/codexA/mutants"
WAIT_OLD = ("        why = halt_reason()\n        if why:\n            return why\n        _sleep(SLEEP_STEP)\n    return halt_reason()")
WAIT_NEW = "        _sleep(SLEEP_STEP)\n    return \"\""
M = [
    (RV, "meta cell not compared with the fixed contract", "    if canon(cl[0]) != canon(cc):", "    if False:", ["C03"]),
    (RV, "stored command values not compared", "    if vals:", "    if False:", ["C01", "C10", "G05"]),
    (RV, "command arrays shape / dtype / finite not checked", "    if arr_bad:", "    if False:", ["C02"]),
    (RV, "cmd_hist time rule not checked", "    if not (ch == want_h).all():", "    if False:", ["C06"]),
    (RV, "action summary not checked",
     '    if act.shape != (N,) or act.dtype.kind != "f" or not np.isfinite(act).all() or not (act > 0).all():', "    if False:", ["C07"]),
    (RV, "arguments that must be off not checked", "    for k, v in OFF_ARGS.items():", "    for k, v in {}.items():", ["C05"]),
    (RV, "meta heading_hold not checked", '    if meta.get("heading_hold") != META_HEADING_HOLD or "spawn_offset" in meta:', "    if False:", ["C05b"]),
    (RV, "cmd_hist not a required key", '"sw", "act_abs_mean", "cmd_hist")', '"sw", "act_abs_mean")', ["C09"]),
    (RV, "terrain generator source not checked", '    if (meta.get("terrain_set") or {}).get("source_sha256") != TERRAIN_SRC_SHA:', "    if False:", ["C08"]),
    (RV, "q_post / q_metrics not in the frozen recheck", "        rd.code(n, JUDGE[n], loaded[n])", "        pass", ["F01"]),
    (RV, "the revalidator itself not in the frozen recheck", "    rd.code(SELF, JUDGE[SELF], SELF_SHA_AT_LOAD)", "    pass", ["F03"]),
    (RV, "a stale cached judgement module kept", '    if not _JUDGE or any(_JUDGE["sha"][n] != now[n] for n in now):', "    if not _JUDGE:", ["F02"]),
    (RV, "evaluator / metrics / guard differences exempted", "    for role in FIXED_ROLES:", "    for role in ():", ["W02"]),
    (RV, "an unregistered wrapper accepted",
     "        badw = [v for v in vals if not isinstance(v, list) or tuple(v) not in WRAPPER_ALLOWED[role]]", "        badw = []", ["W03"]),
    (RV, "a v3 record may use the v2 registry", '        if os.path.basename(str(s.get("registry") or "")) != V3_REGISTRY_NAME:', "        if False:", ["W04"]),
    (RV, "runner name not matched to the slot version", '    if not any(x.endswith("/" + iso_name) or x == iso_name for x in cmd) or',
     '    if not any("usd_isolate_run" in x for x in cmd) or', ["W05"]),
    (RV, "stamp wrappers not matched to the slot record", '        if (res["roles"]["slot"][0], res["roles"]["isolate"][0]) != want_w:', "        if False:", ["W06"]),
    (RV, "numbers kept for cells that are not valid", ' if verdict == "valid" else {}}', "}", ["P02"]),
    (V5, "slot 94 handled as a plain failure (v4)", "    if rc in PROTECTION_RC:", "    if False:", ["D01"]),
    (V5, "a protection failure does not halt", "            halt(tag, res)", "            pass", ["D01", "D07"]),
    (V5, "HALT ignored by the gate", '    if os.path.exists(HALTF):\n        return False, "HALT_v6.json exists',
     '    if False:\n        return False, "HALT_v6.json exists', ["D10"]),
    (V5, "one GPU retry more than the limit", '        if cls == "gpu" and gpu_retries < GPU_RETRIES:', '        if cls == "gpu" and gpu_retries <= GPU_RETRIES:', ["D04"]),
    (V5, "no GPU precondition before a launch", "        ok, why = gpu_ready()", '        ok, why = True, ""', ["D08"]),
    (V5, "no freeze check right before each launch", '        ok, diff = frozen_now()\n        if not ok:\n            return {"cls": "frozen", "rc": None, "tries": k - 1, "why": f"code or inputs changed before launch {k}: {diff}"}',
     '        ok, diff = True, []\n        if not ok:\n            return {"cls": "frozen", "rc": None, "tries": k - 1, "why": f"code or inputs changed before launch {k}: {diff}"}', ["D05_PRE"]),
    (V5, "no freeze check right after each launch", '        ok, diff = frozen_now()\n        if not ok:\n            return {"cls": "frozen", "rc": rc,',
     '        ok, diff = True, []\n        if not ok:\n            return {"cls": "frozen", "rc": rc,', ["D05b"]),
    (V5, "the wait before a retry ignores STOP", WAIT_OLD, WAIT_NEW, ["D06"]),
    (V5, "the v3 slot is given the v2 registry", '"--lock", LOCK, "--registry", REG_V3,', '"--lock", LOCK, "--registry", REG_V2,', ["L01"]),
    (V5, "folders of the logs in the v2 registry not scanned", "    for d in [ROOT, OLD_ROOT, BR, BR_NEW] + v2_registry_dirs():",
     "    for d in [ROOT, OLD_ROOT, BR, BR_NEW]:", ["L01"]),
    (V5, "out_branch not scanned", "    for d in [ROOT, OLD_ROOT, BR, BR_NEW] + v2_registry_dirs():", "    for d in [ROOT, OLD_ROOT, BR] + v2_registry_dirs():",
     ["L01", "L03"]),
    (V5, "expect_conversions not passed to the slot", '"--expect_conversions", "1", "--",', '"--",', ["L01"]),
    (V5, "the approved old bundle not required", '    if fresh["bundle_sha256"] != OLD_APPROVED["bundle_sha256"]:', "    if False:", ["G04", "P04"]),
    (V5, "the approval file not checked", '    if wrong or not str(ap.get("by") or "").strip():', "    if False:", ["G02", "G03"]),
    (V5, "diag cell verdicts not required by the gate", '        if a != "valid" or b != "valid":', "        if False:", ["G05b"]),
    (V5, "old runs' validity not required by the gate", '            if r.get("verdict") != "valid":', "            if False:", ["G07"]),
    (V5, "manifest registration not required by the gate",
     '    ok, diff = registration()\n    if not ok:\n        return False, f"new execution manifest',
     '    ok, diff = True, []\n    if not ok:\n        return False, f"new execution manifest', ["M02"]),
    (V5, "old partial runs reused by default", 'choices=("no", "yes"), default="no",', 'choices=("no", "yes"), default="yes",', ["M03"]),
    (V5, "post alone without the fixed manifest (v3 behaviour)", '        requested = set({"diag": DIAG, "full": FULL, "all": MANIFEST}[a.manifest])',
     "        requested = set()", ["E01"]),
    (V5, "post uses an old root that is not the approved bundle",
     '        if c and "old" in src.values() and not old_ok and any(trio[m] for m in trio if src[m] == "old"):',
     "        if False:", ["P04"]),
    (V5, "GPU wait leaves no immediate frozen recheck",
     '        ok, diff = frozen_now()\n        if not ok:\n            return {"cls": "frozen", "rc": None, "tries": k - 1, "why": f"code or inputs changed after GPU wait before launch {k}: {diff}"}',
     '        ok, diff = True, []\n        if not ok:\n            return {"cls": "frozen", "rc": None, "tries": k - 1, "why": f"code or inputs changed after GPU wait before launch {k}: {diff}"}', ["D11_CHANGED"]),
    (V5, "slot command omits frozen_exec",
     'PY, "frozen_exec.py", "--manifest", os.path.join(ROOT, "manifest_v6.json"), "--expected-sha", manifest_sha(), "--",',
     'PY, "gpu_guard.py", "--manifest", os.path.join(ROOT, "manifest_v6.json"), "--expected-sha", manifest_sha(), "--",', ["A2_ARG"]),
    (V5, "exit 92 is not protected",
     '97: "no scene line within the conversion limit", 92: "frozen_exec found changed code, input, or manifest"}',
     '97: "no scene line within the conversion limit"}', ["A2_92"]),
    (FZ, "frozen_exec ignores the registered file comparison",
     '        ok, why = verify_manifest(args.manifest, args.expected_sha)',
     '        ok, why = True, ""', ["A2_CHANGED"]),
    (RV, "environment differences ignored",
     '    if different:\n        raise UnsupportedEnvironment("[post-env] 다른 칸: " + ", ".join(different))',
     '    if False:\n        raise UnsupportedEnvironment("[post-env] 다른 칸: " + ", ".join(different))', ["A3_GATE"]),
    (RV, "environment field comparison disabled",
     '    return [key for key, want in expected.items()',
     '    return [key for key, want in {}.items()', ["A3_FIELD_executable"]),
]


def run(k, item):
    target, name, a, b, want = item
    src = open(os.path.join(HERE, target), encoding="utf-8").read()
    assert src.count(a) == 1, f"{name}: target text found {src.count(a)} times"
    os.makedirs(WORK, exist_ok=True)
    p = os.path.join(WORK, f"_mut_uncr6_{k:02d}.py")
    with open(p, "w", encoding="utf-8") as f:
        f.write(src.replace(a, b))
    env = dict(os.environ, UNCR_TEST_SKIP_REAL="1", CUDA_VISIBLE_DEVICES="-1", PYTHONDONTWRITEBYTECODE="1", PYTHONIOENCODING="utf-8")
    env["UNCR_MUT_ORIGINAL"] = os.path.join(HERE, target)
    env[{RV: "UNCR_REVAL3_SCRIPT", V5: "UNCR_V6_SCRIPT", FZ: "UNCR_FROZEN_SCRIPT"}[target]] = p
    try:
        r = subprocess.run([sys.executable, "-B", os.path.join(HERE, "test_uncr_v6.py")], capture_output=True, text=True, env=env,
                           encoding="utf-8", errors="replace", timeout=1800, cwd=HERE)
        out, rcode = r.stdout, r.returncode
    except subprocess.TimeoutExpired as ex:
        out, rcode = (ex.stdout or ""), "timeout"
        out = out.decode("utf-8", "replace") if isinstance(out, bytes) else out
    finally:
        os.remove(p)
    failed = [ln.split()[1] for ln in out.splitlines() if ln.startswith("FAIL ")]
    caught = rcode == 1 and all(w in failed for w in want)
    return f"{'CAUGHT' if caught else 'MISSED'} {k:02d} [{target}] {name}: exit {rcode} failed {failed} want {want}"


if __name__ == "__main__":
    for target, name, a, b, want in M:  # every target text must exist exactly once before anything runs
        n = open(os.path.join(HERE, target), encoding="utf-8").read().count(a)
        assert n == 1, f"{name}: target text found {n} times"
    if "--validate-only" in sys.argv:
        print("MUTATION TARGETS VALID", len(M))
        sys.exit(0)
    with cf.ThreadPoolExecutor(max_workers=int(os.environ.get("UNCR_MUT_WORKERS", "6"))) as ex:
        res = list(ex.map(lambda kv: run(*kv), enumerate(M)))
    print("\n".join(res))
    print("ALL CAUGHT" if all(x.startswith("CAUGHT") for x in res) else "SOME MISSED")
    sys.exit(0 if all(x.startswith("CAUGHT") for x in res) else 1)
