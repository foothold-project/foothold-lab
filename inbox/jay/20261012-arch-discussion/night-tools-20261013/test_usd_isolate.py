"""Known-answer tests for usd_isolate_run.py with a fake isaaclab package that copies the real converter's path logic
(lead 10/13 evening). USD_ISOLATE_SCRIPT may point at a mutated copy. Exit 1 when any check fails."""
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.environ.get("USD_ISOLATE_SCRIPT", os.path.join(HERE, "usd_isolate_run.py"))
TMP = tempfile.mkdtemp(prefix="usdi_", dir=HERE)
fails = []

CONV = '''
import os, random
from datetime import datetime
class AssetConverterBase:
    def __init__(self, cfg):
        if cfg.usd_dir is None:
            time_tag = datetime.now().strftime("%Y%m%d_%H%M%S")
            self._usd_dir = f"{os.environ['FAKE_TMP']}/IsaacLab/usd_{time_tag}_{random.randrange(10000)}"
        else:
            self._usd_dir = cfg.usd_dir
        os.makedirs(self._usd_dir, exist_ok=True)
        open(os.path.join(self._usd_dir, "go2.usd"), "w").write("usd")
'''
USER = '''
import json, random, sys
random.seed(int(sys.argv[1]))
from isaaclab.sim.converters.asset_converter_base import AssetConverterBase
class Cfg:
    usd_dir = None
    asset_path = "go2.urdf"
c = AssetConverterBase(Cfg())
print(json.dumps({"usd": c._usd_dir, "after": random.random(), "argv": sys.argv[1:]}))
'''


def check(name, got, want):
    ok = got == want
    print(("PASS" if ok else "FAIL"), name, "got", repr(got)[:220], "want", repr(want)[:120])
    if not ok:
        fails.append(name)


pkg = os.path.join(TMP, "pkg", "isaaclab", "sim", "converters")
os.makedirs(pkg)
for d in (os.path.join(TMP, "pkg", "isaaclab"), os.path.join(TMP, "pkg", "isaaclab", "sim"), pkg):
    open(os.path.join(d, "__init__.py"), "w").close()
open(os.path.join(pkg, "asset_converter_base.py"), "w").write(CONV)
user = os.path.join(TMP, "user_script.py")
open(user, "w").write(USER)


def run(launcher, root=None, seed=7):
    env = dict(os.environ, PYTHONPATH=os.path.join(TMP, "pkg"), FAKE_TMP=os.path.join(TMP, "faketmp"), PYTHONIOENCODING="utf-8")
    env.pop("FOOTHOLD_USD_ROOT", None)
    if root:
        env["FOOTHOLD_USD_ROOT"] = root
    cmd = [sys.executable] + ([SCRIPT] if launcher else []) + [user, str(seed), "extra"]
    r = subprocess.run(cmd, capture_output=True, text=True, env=env, encoding="utf-8", errors="replace")
    line = [x for x in r.stdout.splitlines() if x.startswith("{")]
    return r.returncode, (json.loads(line[-1]) if line else {}), r.stdout + r.stderr


try:
    rc0, plain, _ = run(False)
    root = os.path.join(TMP, "attemptA").replace("\\", "/")
    rc1, iso, out1 = run(True, root)
    check("U1 isolated run: exit 0, USD folder under the attempt root with the IsaacLab component, script argv passed",
          (rc1, iso.get("usd", "").startswith(root + "/IsaacLab/usd_"), iso.get("argv")), (0, True, ["7", "extra"]))
    check("U2 Python random after the converter is the same with and without the launcher (one draw kept)",
          iso.get("after") == plain.get("after") and plain.get("after") is not None, True)
    a = [json.loads(x) for x in open(os.path.join(root, "assigned.jsonl"), encoding="utf-8")]
    check("U3 the assigned folder is recorded before use and matches the folder used", (len(a), a[0]["usd_dir"] if a else None), (1, iso.get("usd")))
    rootB = os.path.join(TMP, "attemptB").replace("\\", "/")
    rc2, isoB, _ = run(True, rootB)
    check("U4 two attempts never share a folder (different roots)", isoB.get("usd") != iso.get("usd") and isoB.get("usd", "").startswith(rootB), True)
    rc3, _, out3 = run(True, None)
    check("U5 no FOOTHOLD_USD_ROOT: refuse to run (exit 2)", rc3, 2)
    check("U6 the fake /tmp IsaacLab folder is not used by isolated runs", os.path.exists(os.path.join(TMP, "faketmp")) and
          len(os.listdir(os.path.join(TMP, "faketmp", "IsaacLab"))) == 1, True)  # only the plain run made one
finally:
    shutil.rmtree(TMP, ignore_errors=True)
print("FAILS", fails)
sys.exit(1 if fails else 0)
