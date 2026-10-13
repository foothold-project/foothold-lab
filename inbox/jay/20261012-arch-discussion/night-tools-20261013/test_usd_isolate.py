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
ODD_SRC = '''import importlib.util, importlib.machinery, sys
class OddLoader:
    def __init__(self, path):
        self.path = path
    def create_module(self, spec):
        return None
    def exec_module(self, module):
        exec(compile(open(self.path).read(), self.path, "exec"), module.__dict__)
class Front:
    def find_spec(self, name, path, target=None):
        s = importlib.machinery.PathFinder.find_spec(name, path, target)
        if s is not None and name.endswith("asset_converter_base"):
            return importlib.util.spec_from_loader(name, OddLoader(s.origin), origin=s.origin)
        return s
sys.meta_path.insert(0, Front())
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
    # U7 (10/13 18:51 real gate run): Kit puts its own finder in front, so the launcher's finder is never asked.
    # The user script below does the same before importing; the audit hook must still patch before the first conversion.
    kit = os.path.join(TMP, "user_kit.py")
    open(kit, "w").write("import importlib.machinery, sys\n"
                         "class Front:\n"
                         "    def find_spec(self, name, path, target=None):\n"
                         "        return importlib.machinery.PathFinder.find_spec(name, path, target)\n"
                         "sys.meta_path.insert(0, Front())\n" + USER)
    rootK = os.path.join(TMP, "attemptK").replace("\\", "/")
    envK = dict(os.environ, PYTHONPATH=os.path.join(TMP, "pkg"), FAKE_TMP=os.path.join(TMP, "faketmpK"), PYTHONIOENCODING="utf-8",
                FOOTHOLD_USD_ROOT=rootK)
    rK = subprocess.run([sys.executable, SCRIPT, kit, "7", "extra"], capture_output=True, text=True, env=envK, encoding="utf-8", errors="replace")
    lineK = [x for x in rK.stdout.splitlines() if x.startswith("{")]
    isoK = json.loads(lineK[-1]) if lineK else {}
    pK = os.path.join(rootK, "isolate_state.json")
    stK = json.load(open(pK, encoding="utf-8")) if os.path.exists(pK) else {}
    check("U7 a finder placed in front (as Kit does): still under the attempt root, patched at load by the loader wrap, random unchanged, no fake /tmp folder",
          (rK.returncode, isoK.get("usd", "").startswith(rootK + "/IsaacLab/usd_"), stK.get("patched_by") == "loader",
           isoK.get("after") == plain.get("after"), os.path.exists(os.path.join(TMP, "faketmpK"))), (0, True, True, True, False))
    check("U8 the log says how it patched", "[USD-ISOLATE] patched via loader" in rK.stdout, True)
    # U9: a non-standard loader (neither the loader wrap nor the finder sees it); one later event (the first import of a module not yet loaded; a cached import raises no event) before the
    # conversion lets the audit hook patch in time.
    odd = os.path.join(TMP, "user_odd.py")
    open(odd, "w").write(ODD_SRC + USER.replace("class Cfg:", "import colorsys as _c2\nclass Cfg:"))
    rootO = os.path.join(TMP, "attemptO").replace("\\", "/")
    envO = dict(envK, FOOTHOLD_USD_ROOT=rootO, FAKE_TMP=os.path.join(TMP, "faketmpO"))
    rO = subprocess.run([sys.executable, SCRIPT, odd, "7", "extra"], capture_output=True, text=True, env=envO, encoding="utf-8", errors="replace")
    lineO = [x for x in rO.stdout.splitlines() if x.startswith("{")]
    isoO = json.loads(lineO[-1]) if lineO else {}
    pO = os.path.join(rootO, "isolate_state.json")
    stO = json.load(open(pO, encoding="utf-8")) if os.path.exists(pO) else {}
    check("U9 a non-standard loader: the audit hook patches on the next event, still under the attempt root",
          (rO.returncode, isoO.get("usd", "").startswith(rootO + "/IsaacLab/usd_"), stO.get("patched_by", "").startswith("audit:")), (0, True, True))
finally:
    shutil.rmtree(TMP, ignore_errors=True)
print("FAILS", fails)
sys.exit(1 if fails else 0)
