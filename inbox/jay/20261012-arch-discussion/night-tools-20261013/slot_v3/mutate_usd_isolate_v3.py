"""break-the-guard for test_usd_isolate_v3.py (lead 세션 · Claude 하위 작업 · 2026-10-13 밤). Each mutated copy of usd_isolate_run_v3.py is written to
a temp folder (never into _eval) and must fail the named checks; only those checks run for that mutant (USD_V3_ONLY).
A mutant is a list of (exact text, replacement); every text must occur exactly once in the source. Exit 1 when any mutant is missed."""
import os
import re
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = open(os.path.join(HERE, "usd_isolate_run_v3.py"), encoding="utf-8").read()
TEST = os.path.join(HERE, "test_usd_isolate_v3.py")
V2_STYLE = ("        if ud is None:\n"
            "            import random as _r\n"
            "            from datetime import datetime as _d\n"
            "            cfg.usd_dir = f\"{ROOT}/IsaacLab/usd_{_d.now().strftime('%Y%m%d_%H%M%S')}_{_r.randrange(10000)}\"\n"
            "            _record(cfg.usd_dir, cfg, \"assigned\", \"\")\n"
            "            ctx[\"mode\"] = \"explicit_inside\"\n"
            "        _CTX[id(self)] = ctx\n")
M = [
    ("I1 cfg.usd_dir set for good and the draw made up front (v2)", [("        _CTX[id(self)] = ctx\n", V2_STYLE)], ["U3", "U10b", "U12"]),
    ("I2 the default folder is not redirected", [("        value = new\n", "        pass\n")], ["U1"]),
    ("I3 an explicit usd_dir outside the root is accepted (v2)",
     [('                _block("cfg.usd_dir is outside the attempt root (refused; no allow list)", ud)', "                pass")], ["U13"]),
    ("I4 no call-stack check at mkdir", [('            if f.f_back is None or f.f_back.f_code is not _STATE["wrap_code"]:', "            if False:")], ["U15", "U18"]),
    ("I5 no folder-name check at mkdir", [('    if "usd_" in s.lower() and DEFAULT_RE.match(s) and not _under_root(_canon(s)):', "    if False:")], ["U19"]),
    ("I6 audit hook not installed", [("    sys.addaudithook(_audit)", "    pass")], ["U9", "U15"]),
    ("I7 loader wrap not installed", [("    _wrap_loader_class()\n", "")], ["U7"]),
    ("I8 terrain cache not reported", [('            if getattr(cfg, "use_cache", False):', "            if False:")], ["U17"]),
    ("I9 an unexpected default form is guessed", [("        if not m:\n            _block(\"the converter's default USD folder has an unexpected form; refusing to guess\", value)\n", "")],
     ["U20"]),
    ("I10 no check that the redirect happened", [('        if ctx["mode"] == "default" and ctx["path"] is None:', "        if False:")], ["U21"]),
    ("I11 only the first class is wrapped (a reloaded module stays bare)",
     [("        if name == TARGET:\n            patch(module, \"loader\")", "        if name == TARGET and not _STATE[\"patched_by\"]:\n            patch(module, \"loader\")")], ["U22"]),
    ("I12 an explicit inside folder is not recorded", [('                _record(c, cfg, "explicit_inside", str(ud))', "                pass")], ["U14"]),
    ("I13 the assigned line is not written", [('        _record(new, ctx["cfg"], "assigned", str(value))', "        pass")], ["U3", "U10b"]),
    ("I14 the _usd_dir descriptor is not installed", [("    C._usd_dir = property(_get_usd_dir, _set_usd_dir, _del_usd_dir)", "    pass")], ["U1", "U10b"]),
    ("I15 no FOOTHOLD_USD_ROOT check", [("    if not ROOT:\n        print", "    if False:\n        print")], ["U5"]),
    ("I16 (17d 2.6) the expected count is not enforced", [('        if EXPECT == "0" or (EXPECT == "1" and n > 1):', "        if False:")], ["U23", "U24"]),
    ("I17 (17d 2.6) expect 1 lets a second conversion through", [('        if EXPECT == "0" or (EXPECT == "1" and n > 1):', '        if EXPECT == "0" or (EXPECT == "1" and n > 2):')],
     ["U24"]),
    ("I18 (17d 2.6) the refusal is not written to assigned.jsonl",
     [('            _record(None, cfg, "refused_unexpected_conversion", None if ud is None else str(ud), {"n": n, "expect": EXPECT})', "            pass")], ["U23"]),
    ("I19 (17d 2.6) any expected value accepted", [('    if EXPECT not in ("0", "1", "any"):', "    if False:")], ["U26"]),
]
tmpd = tempfile.mkdtemp(prefix="usdi3_mut_")
res = []
try:
    for k, (name, edits, want) in enumerate(M):
        s = SRC
        for a, b in edits:
            assert s.count(a) == 1, f"{name}: {a!r} occurs {s.count(a)} times"
            s = s.replace(a, b)
        p = os.path.join(tmpd, f"mut_usdi3_{k}.py")
        open(p, "w", encoding="utf-8").write(s)
        try:
            r = subprocess.run([sys.executable, "-B", TEST], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=900,
                               env=dict(os.environ, USD_ISOLATE_SCRIPT=p, USD_V3_ONLY=",".join(sorted(set(want) | {re.sub(r"[a-z]$", "", w) for w in want})), PYTHONDONTWRITEBYTECODE="1"))
            out, rcode = r.stdout, r.returncode
        except subprocess.TimeoutExpired:
            out, rcode = "", "timeout"
        failed = [ln.split()[1] for ln in out.splitlines() if ln.startswith("FAIL ")]
        caught = (rcode == 1 and all(w in failed for w in want)) or rcode == "timeout"
        res.append(f"{'CAUGHT' if caught else 'MISSED'} {name}: exit {rcode} failed {failed} want {want}")
        print(res[-1], flush=True)
finally:
    shutil.rmtree(tmpd, ignore_errors=True)
print("ALL CAUGHT" if all(x.startswith("CAUGHT") for x in res) else "SOME MISSED")
sys.exit(0 if all(x.startswith("CAUGHT") for x in res) else 1)
