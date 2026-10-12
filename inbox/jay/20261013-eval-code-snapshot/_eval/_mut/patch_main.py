p = "d1b_harness.py"
s = open(p, encoding="utf-8").read()
reps = [
 ("ap.add_argument(\"--cond\", default=\"legacy-normal\", choices=[\"legacy-normal\", \"legacy-perm2026\", \"g0plus-normal\", \"g0plus-perm2026\"],\n",
  "ap.add_argument(\"--layout\", default=\"harness\", choices=[\"harness\", \"main\"], help=\"main: validation columns only\")\n"
  "ap.add_argument(\"--main_T\", type=int, default=1000, help=\"main stage: policy steps (20 s)\")\n"
  "ap.add_argument(\"--cond\", default=\"legacy-normal\", choices=[\"legacy-normal\", \"legacy-perm2026\", \"g0plus-normal\", \"g0plus-perm2026\", \"student\"],\n"),
 ("STAGES = args.stages.split(\",\")\n",
  "STAGES = args.stages.split(\",\")\nMAIN = \"main\" in STAGES\nassert not MAIN or (STAGES == [\"main\"] and args.layout == \"main\"), \"main runs alone on the main layout\"\n"),
 ("COLS = VAL_COLS + SMOKE_COLS\n", "COLS = VAL_COLS + SMOKE_COLS if args.layout == \"harness\" else list(VAL_COLS)\n"),
 ("if \"settle\" in STAGES or any(s in STAGES for s in (\"dyn\", \"fall\", \"foot\")):\n",
  "if MAIN or \"settle\" in STAGES or any(s in STAGES for s in (\"dyn\", \"fall\", \"foot\")):\n"),
 ("    u._d1b_g0[:] = args.cond.startswith(\"g0plus\")\n", "    u._d1b_g0[:] = args.cond.startswith(\"g0plus\")  # student: no effect on its inputs\n"),
]
for a, b in reps:
    n = s.count(a)
    assert n == 1, (n, a[:90])
    s = s.replace(a, b)
# wrap the in-process replay tests (they would change the hidden state before the main rollout)
a0 = "    tr1 = short_roll(o1)\n"
a1 = "    RESTORE_OK = s[\"restore1_vs_restore2_hash_equal\"]  # state write; the in-process replay is reported separately\n"
i0, i1 = s.index(a0), s.index(a1) + len(a1)
block = s[i0:i1]
block = "".join(("    " + l if l.strip() else l) for l in block.splitlines(True))
s = s[:i0] + "    if MAIN:\n        RESTORE_OK = True  # pairing across condition processes is checked from the stored hashes\n    else:\n" + block + s[i1:]
# rollout: halt on harness error
a = "def rollout(o, T, act_fn, per_step=None):\n    global REC\n"
assert s.count(a) == 1
s = s.replace(a, "class HarnessHalt(RuntimeError):\n    pass\n\n\ndef rollout(o, T, act_fn, per_step=None, halt=False, grab_hook=None):\n    global REC\n")
a = "            st = REC.grab()\n            REC.put(k + 1, st)\n"
assert s.count(a) == 1
s = s.replace(a, "            st = REC.grab()\n            if grab_hook is not None:\n                grab_hook(k + 1, st)\n"
              "            if halt and (st[\"harness_err\"].any() or st[\"nonfinite_state\"].any()):\n"
              "                bad = np.flatnonzero(st[\"harness_err\"] | st[\"nonfinite_state\"])\n"
              "                raise HarnessHalt(f\"harness error at sample {k + 1}, envs {bad[:20].tolist()}\")\n"
              "            REC.put(k + 1, st)\n")
# body velocities for Q1
a = "            (\"foot_fz\", (4,)), (\"nonfoot_fmax\", ()))}\n"
assert s.count(a) == 1
s = s.replace(a, "            (\"foot_fz\", (4,)), (\"nonfoot_fmax\", ()), (\"vel_b\", (3,)), (\"wz_b\", ()))}\n")
a = "              \"local_all_miss\": torch.isposinf(hs_small.data.ray_hits_w[..., 2]).all(dim=1)}\n"
assert s.count(a) == 1
s = s.replace(a, "              \"local_all_miss\": torch.isposinf(hs_small.data.ray_hits_w[..., 2]).all(dim=1),\n"
              "              \"vel_b\": d.root_lin_vel_b, \"wz_b\": d.root_ang_vel_b[:, 2]}\n")
MAINCODE = open("_mut/main_stage.txt", encoding="utf-8").read()
anchor = "meta[\"t_end\"] = time.strftime(\"%Y-%m-%d %H:%M:%S\")\n"
assert s.count(anchor) == 1
s = s.replace(anchor, MAINCODE + "\n" + anchor)
open(p, "w", encoding="utf-8").write(s)
print("ok")
