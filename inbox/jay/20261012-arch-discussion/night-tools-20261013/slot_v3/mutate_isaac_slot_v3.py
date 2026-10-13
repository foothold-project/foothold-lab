"""break-the-guard for test_isaac_slot_v3.py (lead 세션 · Claude 하위 작업 · 2026-10-13 밤). Each mutated copy of isaac_slot_v3.py is written to a
temp folder (never into _eval) and must fail the named checks; only those checks run for that mutant (SLOT_V3_ONLY).
A mutant is a list of (exact text, replacement); every text must occur exactly once in the source. Exit 1 when any mutant is missed."""
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = open(os.path.join(HERE, "isaac_slot_v3.py"), encoding="utf-8").read()
TEST = os.path.join(HERE, "test_isaac_slot_v3.py")
M = [
    ("S1 lock released right after launch", [('        if CONVERT_DONE in text and (found or a.expect_conversions == "0"):', "        if True:")], ["T2"]),
    ("S1b released at the scene line without knowing the folder (17b 2.2)",
     [('        if CONVERT_DONE in text and (found or a.expect_conversions == "0"):', "        if CONVERT_DONE in text:")], ["T8", "A3"]),
    ("S2 registry conflicts ignored", [("            if key in mine and val != me:", "            if False:")], ["T3b"]),
    ("S2b other logs not scanned", [('    cands = [f for d in a.scan_dirs.split(",") if d for pat', '    cands = [f for d in [] if d for pat')], ["T3c"]),
    ("S2c v2 scan patterns (attempts/<tag>.<time>/ and _attempts/ not read)",
     [('SCAN_PATTERNS = ("*.log", "*.log.prev.*", "attempts/*.log*", "attempts/*/*.log*", "_attempts/*.log*", "_attempts/*/*.log*")',
       'SCAN_PATTERNS = ("*.log", "attempts/*.log*")')], ["T3d", "T3e"]),
    ("S2d registry and scan keyed by basename (v2)", [('    mine = {c: k for c, k in found.items() if not c.startswith("unresolved:")}',
                                                       '    mine = {k: k for c, k in found.items() if not c.startswith("unresolved:")}')], ["T3a"]),
    ("S3 an old log is not moved aside", [("    if os.path.exists(a.watch_log):\n        moved", "    if False:\n        moved")], ["T7"]),
    ("S4 the one-USD-folder check dropped", [('    if rc == 0 and len(final) != (0 if a.expect_conversions == "0" else 1):', "    if False:")], ["T5", "T5b"]),
    ("S5 the conversion time limit ignored", [("        if time.time() - t_hold > a.convert_timeout_s:", "        if False:")], ["T6"]),
    ("S6 a folder outside the root accepted at the end", [('    if outside or rec["assigned_outside_root"]:', "    if False:")], ["T9", "A1"]),
    ("S6b root judged by basename only (v2 merged the two paths)",
     [('    return c.startswith("unresolved:") or c != f"{root}/isaaclab/usd_{k}"', '    return c.startswith("unresolved:") or not c.endswith(f"/isaaclab/usd_{k}")')],
     ["A1", "T9"]),
    ("S6c prefix test on unnormalised paths",
     [('    return c.startswith("unresolved:") or c != f"{root}/isaaclab/usd_{k}"', '    return c.startswith("unresolved:") or not c.startswith(root)'),
      ('    return os.path.normcase(os.path.normpath(s)).replace("\\\\", "/").rstrip("/")', '    return os.path.normcase(s).replace("\\\\", "/").rstrip("/")')],
     ["A6"]),
    ("S6d no kill at the scene line", [("    if bad1 and p.poll() is None:", "    if False:")], ["A1", "A2", "A5a", "R4"]),
    ("S6e no watch after the release", [('    if "killed" not in rec and p.poll() is None:', "    if False:")], ["A4", "A5d"]),
    ("S6f the watch ignores outside folders", [('        if bad["outside"] or bad["unassigned"] or bad["hint_without_assigned"] or bad["expect_violation"]:',
                                                '        if bad["unassigned"] or bad["hint_without_assigned"] or bad["expect_violation"]:')], ["A4"]),
    ("S7 stop file ignored while waiting", [('    if a.stop_file and os.path.exists(a.stop_file):\n        return "stop file"',
                                             '    if False:\n        return "stop file"')], ["T10", "T12"]),
    ("S7b deadline ignored", [("    if a.deadline and time.time() > a.deadline:", "    if False:")], ["T11"]),
    ("S8 the child does not get its own USD root", [("    env = dict(os.environ, FOOTHOLD_USD_ROOT=root)", "    env = dict(os.environ)")], ["T13"]),
    ("S9 assigned.jsonl not linked", [('    if unassigned or rec["hint_without_assigned"]:', "    if False:"),
                                      ('    if chk["unassigned"] or chk["hint_without_assigned"]:', "    if False:")], ["A5a", "A5b", "A5c"]),
    ("S9b the watch ignores unassigned folders", [('        if bad["outside"] or bad["unassigned"] or bad["hint_without_assigned"] or bad["expect_violation"]:',
                                                   '        if bad["outside"] or bad["hint_without_assigned"] or bad["expect_violation"]:')], ["A5d"]),
    ("S9c an assigned folder outside the root accepted", [('    if outside or rec["assigned_outside_root"]:', "    if outside:"),
                                                          ('    if chk["outside"] or chk["assigned_outside_root"]:', '    if chk["outside"]:')], ["A8"]),
    ("S10 registry updated without its lock (17c 5)",
     [('    lk, _, why = acquire(registry + ".lock", poll=0.05, timeout=REG_LOCK_WAIT_S)', '    lk, _, why = open(registry + ".nolock", "a+"), 0, ""'),
      ("    finally:\n        release(lk)\n\n\ndef other_logs", "    finally:\n        lk.close()\n\n\ndef other_logs")], ["R1"]),
    ("S11 one shared temp name (17c 5)", [('    tmp = f"{path}.{os.getpid()}.{uuid.uuid4().hex}.tmp"', '    tmp = path + ".tmp"')], ["R3"]),
    ("S12 an unreadable registry treated as empty (v2)", [('        return None, f"registry is not JSON ({ex}); left untouched"', '        return {}, ""')], ["R4"]),
    ("S13 v2 basename registry entries not resolved", [('            elif "/" not in key and key in keys and val != me:', "            elif False:")], ["R5"]),
    ("S14 no case folding", [('    return os.path.normcase(os.path.normpath(s)).replace("\\\\", "/").rstrip("/")',
                              '    return os.path.normpath(s).replace("\\\\", "/").rstrip("/")')], ["A7"]),
    ("S15 no normpath", [('    return os.path.normcase(os.path.normpath(s)).replace("\\\\", "/").rstrip("/")',
                          '    return os.path.normcase(s).replace("\\\\", "/").rstrip("/")')], ["A7"]),
    ("S16 a drive-less /tmp path left unresolved", [('    elif s.startswith("/"):\n        s = os.path.abspath(s)', '    elif False:\n        s = os.path.abspath(s)')],
     ["T9b"]),
    ("S17 importer lines ignored", [('CONVERT_HINT_RE = re.compile(r"\\[(?:isaacsim\\.asset\\.importer\\.\\w+|omni\\.kit\\.asset_converter)\\]")',
                                     'CONVERT_HINT_RE = re.compile(r"(?!x)x")')], ["A5c"]),
    ("S18 an internal gate error leaves the child running", [("    except Exception as ex:  # noqa: BLE001  never leave the child running without the gate",
                                                              "    except ZeroDivisionError as ex:")], ["T14"]),
    ("S19 (17d 2.6) the expected count not enforced by the slot", [('    if rec["expect_violation"]:\n        finish(89)', '    if False:\n        finish(89)'),
                                                                   ('    if chk["expect_violation"]:\n        out.append(89)', '    if False:\n        out.append(89)')],
     ["E2", "E2b", "E2c", "E3"]),
    ("S20 (17d 2.6) expect 0 still waits for a folder at the scene line", [('        if CONVERT_DONE in text and (found or a.expect_conversions == "0"):',
                                                                             '        if CONVERT_DONE in text and found:')], ["E1"]),
    ("S21 (17d 2.6) the expected count not passed to the child (no refusal before the write)",
     [('    env["FOOTHOLD_EXPECT_CONVERSIONS"] = a.expect_conversions', '    pass')], ["E3", "E5"]),
    ("S22 (17d 2.6) expect 0 relaxed to 「no folder is fine」 (only refusal lines count)",
     [('    return expect == "0" and (bool(found) or hint or info["lines"] > 0)', "    return False")], ["E2b", "E2c"]),
    ("S23 (17d 2.6) assigned.jsonl / isolate_state.json not watched after the release", [("        if now != side:", "        if False:")], ["E6"]),
    ("S24 (17d 2.6) expect 0 still requires one folder", [('    if rc == 0 and len(final) != (0 if a.expect_conversions == "0" else 1):', "    if rc == 0 and len(final) != 1:")],
     ["E1"]),
]
tmpd = tempfile.mkdtemp(prefix="slot3_mut_")
res = []
try:
    for k, (name, edits, want) in enumerate(M):
        s = SRC
        for a, b in edits:
            assert s.count(a) == 1, f"{name}: {a!r} occurs {s.count(a)} times"
            s = s.replace(a, b)
        p = os.path.join(tmpd, f"mut_slot3_{k}.py")
        open(p, "w", encoding="utf-8").write(s)
        try:
            r = subprocess.run([sys.executable, "-B", TEST], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=900,
                               env=dict(os.environ, ISAAC_SLOT_SCRIPT=p, SLOT_V3_ONLY=",".join(want), PYTHONDONTWRITEBYTECODE="1"))
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
