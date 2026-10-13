"""break-the-guard for test_uncr_v4.py: each mutated copy of uncr_revalidate.py or unseen_driver_cmdr_v4.py turns one check off and
must make the named tests fail (lead sub task 10/13 night). Mutants are written next to the originals as _mut_uncr_*.py, run through
test_uncr_v4.py with UNCR_TEST_SKIP_REAL=1 (synthetic roots in the system temp folder only), and removed. CPU only."""
import concurrent.futures as cf
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
RV = "uncr_revalidate.py"
V4 = "unseen_driver_cmdr_v4.py"
M = [
    (RV, "traj shape check off", "    if tr.shape != (T + 1, N, NCH) or tr.dtype != np.float32:", "    if False:", ["R07"]),
    (RV, "negative env check off", "    if neg:", "    if False:", ["R08"]),
    (RV, "required channels in the judgement window not checked", "    if first_bad:", "    if False:", ["R02", "V04"]),
    (RV, "channel 11 NaN after the fall counted as inside the window",
     "        gi = int((~np.isfinite(tr[:jw + 1, e, GROUND_CH])).sum())", "        gi = int((~np.isfinite(tr[:, e, GROUND_CH])).sum())", ["R01", "V02"]),
    (RV, "channel 11 NaN inside the window not held", "    if g_in:", "    if False:", ["R09", "V10"]),
    (RV, "fingerprint form check off", "    for x in fpp:", "    for x in []:", ["R03", "R04", "R05", "R06"]),
    (RV, "hash of zero bytes accepted as a fingerprint", " and v != EMPTY_SHA", "", ["R05"]),
    (RV, "survived but term set accepted", "                if first is not None:", "                if False:", ["R10"]),
    (RV, "fall state after the first term accepted",
     '            if not 0 <= jf <= J or (first is not None and jf > first) or (why == "base_contact" and jf != first):', "            if False:", ["R10b"]),
    (RV, "stamp out hashes not compared", "        diff = [k for k in want if got.get(k) != want[k]]", "        diff = []", ["R11"]),
    (RV, "stamp collection code not compared with the files now",
     "        changed = [f for f in DATA_CODE if f in code and code[f] != code_now.get(f)]", "        changed = []", ["R12"]),
    (RV, "pair comparison off", "        pair_ok = not diff", "        pair_ok, diff = True, []", ["R15", "V05"]),
    (RV, "q_post re-run not compared", "    elif not all(eq.values()):", "    elif False:", ["R14"]),
    (RV, "checkpoint hash not compared",
     '    if ckpt_sha.get(m) is None or meta.get("checkpoint_sha256") != ckpt_sha.get(m) or meta.get("loaded_iter") != spec["iter"]:',
     "    if False:", ["R16"]),
    (RV, "nonfinite action / obs count ignored", '    if cr.get("nonfinite_action_or_obs_count") != 0:', "    if False:", ["R17"]),
    (RV, "slot USD record ignored",
     '    if not isinstance(s.get("usd_final"), list) or len(s["usd_final"]) != 1 or s.get("usd_outside_root") or s.get("conflicts"):',
     "    if False:", ["R18"]),
    (RV, "USD paths in the log not checked one by one", "    if outside:", "    if False:", ["R19"]),
    (RV, "assigned USD folder outside the run root accepted",
     '        if not ud.startswith(usd_root + "/isaaclab/usd_") or not r.get("patched_by"):', "        if False:", ["R24"]),
    (RV, "inputs not hashed again at the end", "    changed = rd.recheck()", "    changed = []", ["R21"]),
    (RV, "report allowed inside the input root", '    if ob == root or ob.startswith(root + "/"):', "    if False:", ["R20"]),
    (RV, "bundle hash without the input files",
     '    bundle = {"root": norm(root), "inputs": rd.inputs, "external": {k: v["sha256"] for k, v in rd.ext.items()}}',
     '    bundle = {"root": norm(root)}', ["V09"]),
    (RV, "traj start vs env origin not checked", "    if dxy > RESET_XY_M + 0.01:", "    if False:", ["R22"]),
    (RV, "fam / cel / epi arrays not checked",
     "    if (fa != 0).any() or (ce != 0).any() or not np.array_equal(epi, np.arange(N) % EPISODES):", "    if False:", ["R23"]),
    (V4, "post alone gets no requested manifest (v3 behaviour)",
     '        requested = set({"diag": DIAG, "full": FULL, "all": MANIFEST}[a.manifest])', "        requested = set()", ["V01", "V03"]),
    (V4, "full gate back to the v3 diag_gate.json booleans", "            ok, why, gate = full_gate(a.reval)",
     '            ok, why, gate = (lambda g: (bool(g.get("diag_runs_valid") and g.get("diag_pair_ok")), "v3 booleans", g))('
     'json.load(open(os.path.join(ROOT, "diag_gate.json"))) if os.path.exists(os.path.join(ROOT, "diag_gate.json")) else {})', ["V06"]),
    (V4, "gate does not compare the bundle hash", '    if fresh["bundle_sha256"] != rv.get("bundle_sha256"):', "    if False:", ["V09"]),
    (V4, "gate does not require 7 valid diag cells", '        if a != "valid" or b != "valid":', "        if False:", ["V10"]),
    (V4, "q_post.py not in CODE", '("q_eval_cmdr.py", "q_metrics.py", "q_post.py", "isaac_slot.py"', '("q_eval_cmdr.py", "q_metrics.py", "isaac_slot.py"', ["V11"]),
    (V4, "out_branch not scanned by isaac_slot", '",".join([ROOT, BR, BR_NEW])', '",".join([ROOT, BR])', ["V11"]),
    (V4, "code and inputs not compared at the end", '    ok, diff = frozen_now()\n    LOG["code_and_inputs_unchanged_at_end"] = ok',
     '    ok, diff = True, []\n    LOG["code_and_inputs_unchanged_at_end"] = ok', ["V12"]),
    (V4, "reuse without revalidation (stamp hashes only, v3 behaviour)", '    return check_alone(tag, True, st.get("attempt"))["verdict"] == "valid"',
     "    return True", ["V13"]),
    (V4, "unpaired cells reported as hold", '            cats["unpaired" if (state == "hold" and c and c.get("pair_ok") is False) else state].append(key)',
     "            cats[state].append(key)", ["V05"]),
    (V4, "a run is stamped although the code moved while it was out",
     '            elif not ok:\n                why = f"code or inputs changed during the run: {diff}"',
     '            elif False:\n                why = f"code or inputs changed during the run: {diff}"', ["V16"]),
    (V4, "no freeze check before a launch",
     '            ok, diff = frozen_now()\n            if not ok:\n                fail(stage, f"code or inputs changed since the driver start',
     '            ok, diff = True, []\n            if not ok:\n                fail(stage, f"code or inputs changed since the driver start', ["V16b"]),
    (V4, "gate ignores which revalidator code made --reval",
     '    if (rv.get("revalidator") or {}).get("sha256") != FROZEN["code"].get("uncr_revalidate.py"):', "    if False:", ["V14"]),
]


def run(k, item):
    target, name, a, b, want = item
    src = open(os.path.join(HERE, target), encoding="utf-8").read()
    assert src.count(a) == 1, f"{name}: target text found {src.count(a)} times"
    p = os.path.join(HERE, f"_mut_uncr_{k:02d}.py")
    with open(p, "w", encoding="utf-8") as f:
        f.write(src.replace(a, b))
    env = dict(os.environ, UNCR_TEST_SKIP_REAL="1", CUDA_VISIBLE_DEVICES="-1", PYTHONDONTWRITEBYTECODE="1", PYTHONIOENCODING="utf-8")
    env["UNCR_REVAL_SCRIPT" if target == RV else "UNCR_V4_SCRIPT"] = p
    try:
        r = subprocess.run([sys.executable, "-B", os.path.join(HERE, "test_uncr_v4.py")], capture_output=True, text=True, env=env,
                           encoding="utf-8", errors="replace", timeout=1500, cwd=HERE)
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
    with cf.ThreadPoolExecutor(max_workers=int(os.environ.get("UNCR_MUT_WORKERS", "6"))) as ex:
        res = list(ex.map(lambda kv: run(*kv), enumerate(M)))
    print("\n".join(res))
    print("ALL CAUGHT" if all(x.startswith("CAUGHT") for x in res) else "SOME MISSED")
    sys.exit(0 if all(x.startswith("CAUGHT") for x in res) else 1)
