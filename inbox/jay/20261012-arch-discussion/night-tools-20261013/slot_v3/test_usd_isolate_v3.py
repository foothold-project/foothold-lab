"""Known-answer tests for usd_isolate_run_v3.py (lead 세션 · Claude 하위 작업 · 2026-10-13 밤 · ASTRA 17c §3 counterexamples kept).
A fake isaaclab package copies the real AssetConverterBase.__init__ order (validate, asset check, default-branch assignment with
random.randrange, os.makedirs, files, config dump). Everything lives under the system temp dir. USD_ISOLATE_SCRIPT may point at a
mutated copy; USD_V3_ONLY=U1,U10 runs only those checks. Exit 1 when any check fails.
Hand-computed constants (stdlib random, seed 7): randrange(10000) draws 5305 then 2471; random() after no draw 0.32383276483316237,
after one draw 0.9478653606090632, after two draws 0.3948234964231735 (the last is ASTRA 17c's value)."""
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.environ.get("USD_ISOLATE_SCRIPT", os.path.join(HERE, "usd_isolate_run_v3.py"))
ONLY = {x for x in os.environ.get("USD_V3_ONLY", "").split(",") if x}
TMP = tempfile.mkdtemp(prefix="usdi3_")
R0, R1, R2 = 0.32383276483316237, 0.9478653606090632, 0.3948234964231735
fails = []

CONV = '''
import os, random
from datetime import datetime


class AssetConverterBase:
    def __init__(self, cfg):
        cfg.validate()
        if not os.path.isfile(cfg.asset_path):
            raise ValueError(f"The asset path does not exist: {cfg.asset_path}")
        self.cfg = cfg
        form = os.environ.get("FAKE_FORM", "")
        if cfg.usd_dir is None:
            time_tag = datetime.now().strftime("%Y%m%d_%H%M%S")
            if form == "odd":
                self._usd_dir = f"{os.environ['FAKE_TMP']}/OtherLab/usd-{time_tag}-{random.randrange(10000)}"
            elif form == "dictodd":
                self.__dict__["_usd_dir"] = f"{os.environ['FAKE_TMP']}/other/x_{random.randrange(10000)}"
            else:
                self._usd_dir = f"{os.environ['FAKE_TMP']}/IsaacLab/usd_{time_tag}_{random.randrange(10000)}"
        else:
            self._usd_dir = cfg.usd_dir
        os.makedirs(self.usd_dir, exist_ok=True)
        with open(os.path.join(self.usd_dir, "go2.usd"), "w") as f:
            f.write("usd")
        with open(os.path.join(self.usd_dir, "config.yaml"), "w") as f:
            f.write("usd_dir: " + str(cfg.usd_dir))

    @property
    def usd_dir(self):
        return self._usd_dir
'''
URDF = '''
from .asset_converter_base import AssetConverterBase


class UrdfConverter(AssetConverterBase):
    def __init__(self, cfg):
        self.kind = "urdf"
        super().__init__(cfg=cfg)
'''
TERR = '''
class TerrainGenerator:
    def __init__(self, cfg, device="cpu"):
        self.cfg = cfg
        self.device = device
'''
USER = '''
import importlib, json, os, random, sys, time
random.seed(int(sys.argv[1]))
mode = sys.argv[2]
from isaaclab.sim.converters.asset_converter_base import AssetConverterBase


class Cfg:
    def __init__(self, asset="go2.urdf", usd_dir=None):
        self.asset_path = os.path.join(os.environ["FAKE_ASSETS"], asset)
        self.usd_dir = usd_dir

    def validate(self):
        pass


out = {"usd": [], "config": [], "error": None, "argv": sys.argv[1:]}
cs, objs = [], []
t0 = time.perf_counter()
try:
    if mode == "one":
        cs = [Cfg()]
        objs = [AssetConverterBase(cs[0])]
    elif mode == "twice_same":
        c = Cfg()
        cs = [c, c]
        objs = [AssetConverterBase(c), AssetConverterBase(c)]
    elif mode == "two_cfgs":
        cs = [Cfg(), Cfg("go2b.urdf")]
        objs = [AssetConverterBase(x) for x in cs]
    elif mode == "missing":
        cs = [Cfg("nope.urdf")]
        objs = [AssetConverterBase(cs[0])]
    elif mode == "explicit":
        cs = [Cfg(usd_dir=sys.argv[3])]
        objs = [AssetConverterBase(cs[0])]
    elif mode == "urdf":
        from isaaclab.sim.converters.urdf_converter import UrdfConverter
        cs = [Cfg()]
        objs = [UrdfConverter(cs[0])]
    elif mode == "copy":
        import importlib.util
        import isaaclab.sim.converters.asset_converter_base as orig_mod
        spec = importlib.util.spec_from_file_location("fake_copy_of_base", orig_mod.__file__)
        cp = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cp)
        cs = [Cfg()]
        objs = [cp.AssetConverterBase(cs[0])]
    elif mode == "reload":
        import isaaclab.sim.converters.asset_converter_base as mod
        mod = importlib.reload(mod)
        cs = [Cfg()]
        objs = [mod.AssetConverterBase(cs[0])]
    elif mode == "custom":
        from datetime import datetime
        d = os.environ["FAKE_TMP"] + "/IsaacLab/usd_" + datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + str(random.randrange(10000))
        out["custom_dir"] = d
        os.makedirs(d, exist_ok=True)
    elif mode == "terrain":
        from isaaclab.terrains.terrain_generator import TerrainGenerator
        class TCfg:
            use_cache = sys.argv[3] == "1"
            cache_dir = sys.argv[4]
            seed = 3
        TerrainGenerator(TCfg(), device="cpu")
    elif mode == "none":
        pass
    elif mode == "bench":
        cs = [Cfg() for _ in range(50)]
        t1 = time.perf_counter()
        objs = [AssetConverterBase(x) for x in cs]
        out["conv_ms"] = (time.perf_counter() - t1) * 1000 / len(cs)
        p = os.path.join(os.environ["FAKE_ASSETS"], "go2.urdf")
        t2 = time.perf_counter()
        for _ in range(5000):
            open(p).close()
        out["open_us"] = (time.perf_counter() - t2) * 1e6 / 5000
    out["usd"] = [o.usd_dir for o in objs]
    out["config"] = [open(os.path.join(o.usd_dir, "config.yaml")).read() for o in objs]
except Exception as ex:
    out["error"] = type(ex).__name__ + ": " + str(ex)
out["elapsed_ms"] = (time.perf_counter() - t0) * 1000
out["cfg_usd_dir_after"] = [x.usd_dir for x in cs]
out["after"] = random.random()
print(json.dumps(out))
'''
FRONT_KIT = ("import importlib.machinery, sys\n"
             "class Front:\n"
             "    def find_spec(self, name, path, target=None):\n"
             "        return importlib.machinery.PathFinder.find_spec(name, path, target)\n"
             "sys.meta_path.insert(0, Front())\n")
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


def want(name):
    return not ONLY or name in ONLY


def check(name, got, exp):
    ok = got == exp
    print(("PASS" if ok else "FAIL"), name, "got", repr(got)[:300], "want", repr(exp)[:200], flush=True)
    if not ok:
        fails.append(name)


def cp(*parts):
    return os.path.normcase(os.path.abspath(os.path.join(*parts))).replace("\\", "/")


pkg = os.path.join(TMP, "pkg", "isaaclab")
for sub in ("", "sim", os.path.join("sim", "converters"), "terrains"):
    os.makedirs(os.path.join(pkg, sub), exist_ok=True)
    open(os.path.join(pkg, sub, "__init__.py"), "w").close()
open(os.path.join(pkg, "sim", "converters", "asset_converter_base.py"), "w").write(CONV)
open(os.path.join(pkg, "sim", "converters", "urdf_converter.py"), "w").write(URDF)
open(os.path.join(pkg, "terrains", "terrain_generator.py"), "w").write(TERR)
assets = os.path.join(TMP, "assets")
os.makedirs(assets)
open(os.path.join(assets, "go2.urdf"), "w").write("<robot/>")
open(os.path.join(assets, "go2b.urdf"), "w").write("<robot name='b'/>")
scripts = {}
for k, body in {"user": USER, "kit": FRONT_KIT + USER, "odd_late": ODD_SRC + USER.replace("class Cfg:", "import colorsys as _c2\n\n\nclass Cfg:"),
                "odd_now": ODD_SRC + USER}.items():
    scripts[k] = os.path.join(TMP, f"user_{k}.py")
    open(scripts[k], "w").write(body)


def run(launcher, case, mode, *extra, root=True, script="user", seed=7, env_extra=None):
    """Returns (rc, parsed json line, stdout+stderr, root path with / , fake tmp)."""
    r = cp(TMP, "roots", case) if root else None
    ft = os.path.join(TMP, "faketmp_" + case)
    env = dict(os.environ, PYTHONPATH=os.path.join(TMP, "pkg"), FAKE_TMP=ft, FAKE_ASSETS=assets, PYTHONIOENCODING="utf-8", PYTHONDONTWRITEBYTECODE="1")
    env.pop("FOOTHOLD_USD_ROOT", None)
    if r:
        env["FOOTHOLD_USD_ROOT"] = r
    env.update(env_extra or {})
    cmd = [sys.executable, "-B"] + ([SCRIPT] if launcher else []) + [scripts[script], str(seed), mode] + list(extra)
    p = subprocess.run(cmd, capture_output=True, text=True, env=env, encoding="utf-8", errors="replace", timeout=120)
    line = [x for x in p.stdout.splitlines() if x.startswith("{")]
    return p.returncode, (json.loads(line[-1]) if line else {}), p.stdout + p.stderr, r, ft


def assigned(r):
    p = os.path.join(r, "assigned.jsonl")
    return [json.loads(x) for x in open(p, encoding="utf-8")] if os.path.exists(p) else []


def state(r):
    p = os.path.join(r, "isolate_state.json")
    return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else {}


def u0(o):
    """first folder the user script reported, lower case with / ; empty when none."""
    xs = o.get("usd") or [""]
    return xs[0].replace("\\", "/").lower()


def low(xs):
    return [x.replace("\\", "/").lower() for x in xs]


try:
    if want("U1") or want("U2") or want("U3"):
        rc0, plain, _, _, _ = run(False, "plain1", "one", root=False)
        rc1, iso, out1, r, ft = run(True, "a1", "one")
        if want("U1"):
            check("U1 isolated run: exit 0, the folder is <root>/IsaacLab/usd_<time>_5305, script argv passed",
                  (rc1, u0(iso).startswith(r + "/isaaclab/usd_"), u0(iso).endswith("_5305"), iso.get("argv")),
                  (0, True, True, ["7", "one"]))
        if want("U2"):
            check("U2 single conversion: Python random afterwards equals the original (one draw, 0.9478653606090632)", (plain.get("after"), iso.get("after")), (R1, R1))
        if want("U3"):
            a = assigned(r)
            check("U3 assigned.jsonl has one line (kind assigned) naming the folder used; cfg.usd_dir stays None during and after the conversion (config dump)",
                  (len(a), a[0]["usd_dir"] if a else None, a[0].get("kind") if a else None, iso.get("cfg_usd_dir_after"), iso.get("config"), plain.get("config", [""])[0]),
                  (1, iso.get("usd", [None])[0], "assigned", [None], ["usd_dir: None"], "usd_dir: None"))
    if want("U4"):
        _, i1, _, r1, _ = run(True, "u4a", "one")
        _, i2, _, r2, _ = run(True, "u4b", "one")
        check("U4 two attempts never share a folder (different roots)", (low(i1["usd"])[0].startswith(r1), low(i2["usd"])[0].startswith(r2), i1["usd"] != i2["usd"]), (True, True, True))
    if want("U5"):
        check("U5 no FOOTHOLD_USD_ROOT: refuse to run (exit 2)", run(True, "u5", "one", root=False)[0], 2)
    if want("U6"):
        _, _, _, _, ft0 = run(False, "u6p", "one", root=False)
        _, _, _, _, ft1 = run(True, "u6i", "one")
        check("U6 the fake /tmp IsaacLab folder is used by the plain run only", (os.path.isdir(os.path.join(ft0, "IsaacLab")), os.path.exists(ft1)), (True, False))
    if want("U7") or want("U8"):
        rcK, isoK, outK, rK, ftK = run(True, "kit", "one", script="kit")
        if want("U7"):
            check("U7 a finder placed in front (as Kit does): under the root, patched by the loader wrap, random unchanged, no fake /tmp folder",
                  (rcK, u0(isoK).startswith(rK + "/isaaclab/usd_"), state(rK).get("patched_by"), isoK.get("after"), os.path.exists(ftK)),
                  (0, True, "loader", R1, False))
        if want("U8"):
            check("U8 the log says how it patched", "[USD-ISOLATE] patched via loader" in outK, True)
    if want("U9"):
        rcO, isoO, outO, rO, ftO = run(True, "oddlate", "one", script="odd_late")
        check("U9 a non-standard loader with one later event before the conversion: the audit hook patches in time, under the root",
              (rcO, isoO.get("error"), u0(isoO).startswith(rO + "/isaaclab/usd_"), state(rO).get("patched_by", "").startswith("audit:")),
              (0, None, True, True))
    if want("U10"):
        _, p2, _, _, _ = run(False, "plain2", "twice_same", root=False)
        _, i2, _, r, _ = run(True, "twice", "twice_same")
        a = assigned(r)
        check("U10 (17c 3) the same cfg twice, original: two different folders (_5305, _2471), random afterwards 0.3948234964231735",
              ([x[-5:] for x in p2.get("usd", [])], p2.get("after")), (["_5305", "_2471"], R2))
        check("U10b (17c 3) the same cfg twice, isolated: two different folders under the root (_5305, _2471), the same random value, cfg.usd_dir stays None, two assigned lines",
              ([x[-5:] for x in i2.get("usd", [])], all(x.startswith(r + "/isaaclab/usd_") for x in low(i2.get("usd", []))), i2.get("after"),
               i2.get("cfg_usd_dir_after"), [x["usd_dir"] for x in a]),
              (["_5305", "_2471"], True, R2, [None, None], i2.get("usd")))
    if want("U11"):
        _, p3, _, _, _ = run(False, "plain3", "two_cfgs", root=False)
        _, i3, _, r, _ = run(True, "twocfg", "two_cfgs")
        check("U11 two different cfgs: two folders under the root (_5305, _2471), random afterwards equals the original 0.3948234964231735",
              ([x[-5:] for x in i3.get("usd", [])], all(x.startswith(r + "/isaaclab/usd_") for x in low(i3.get("usd", []))), p3.get("after"), i3.get("after")),
              (["_5305", "_2471"], True, R2, R2))
    if want("U12"):
        _, p4, _, _, _ = run(False, "plain4", "missing", root=False)
        _, i4, _, r, _ = run(True, "missing", "missing")
        check("U12 a missing asset: the same ValueError, no draw before the asset check (random afterwards 0.32383276483316237), nothing assigned",
              ((p4.get("error") or "")[:10], (i4.get("error") or "")[:10], p4.get("after"), i4.get("after"), assigned(r)), ("ValueError", "ValueError", R0, R0, []))
    if want("U13"):
        res13 = []
        for sub, outside in (("a", os.path.join(TMP, "elsewhere_a", "custom_usd").replace("\\", "/")),
                             ("b", os.path.join(TMP, "elsewhere_b", "IsaacLab", "usd_20261013_000000_1").replace("\\", "/"))):
            _, i5, _, r, _ = run(True, "explout" + sub, "explicit", outside)
            a = assigned(r)
            res13.append(((i5.get("error") or "").split(":")[0], "cfg.usd_dir is outside the attempt root" in (i5.get("error") or ""),
                          [x.get("kind") for x in a], [x.get("usd_dir") for x in a], os.path.exists(os.path.dirname(outside) if sub == "a" else os.path.join(TMP, "elsewhere_b"))))
        check("U13 (17c 3) cfg.usd_dir set outside the root (a plain folder, and one shaped like the default): refused for that reason with UsdIsolationError before any write, recorded as explicit_outside_refused",
              res13, [("UsdIsolationError", True, ["explicit_outside_refused"], [cp(TMP, "elsewhere_a", "custom_usd")], False),
                      ("UsdIsolationError", True, ["explicit_outside_refused"], [cp(TMP, "elsewhere_b", "IsaacLab", "usd_20261013_000000_1")], False)])
    if want("U14"):
        rr = cp(TMP, "roots", "explin")
        inside = rr + "/custom_usd"
        _, i6, _, r, _ = run(True, "explin", "explicit", inside)
        a = assigned(r)
        check("U14 cfg.usd_dir set inside the root: used as given, recorded as explicit_inside",
              (i6.get("error"), low(i6.get("usd") or []), [x.get("kind") for x in a], [x.get("usd_dir") for x in a]), (None, [inside], ["explicit_inside"], [inside]))
    if want("U15"):
        _, i7, out7, r, ft = run(True, "oddnow", "one", script="odd_now")
        st = state(r)
        check("U15 (17c 3) a non-standard loader and an immediate conversion: stopped at the first conversion with UsdIsolationError, nothing made under the fake /tmp, blocked recorded",
              ((i7.get("error") or "").split(":")[0], os.path.exists(ft), len(st.get("blocked", [])) >= 1,
               "without the isolation wrapper" in (st.get("blocked") or [{}])[0].get("why", ""), "[USD-ISOLATE] BLOCKED" in out7),
              ("UsdIsolationError", False, True, True, True))
    if want("U16"):
        _, i8, _, r, _ = run(True, "urdf", "urdf")
        check("U16 a subclass calling super().__init__(cfg=cfg): under the root, one assigned line, random as one draw",
              (i8.get("error"), u0(i8).startswith(r + "/isaaclab/usd_"), len(assigned(r)), i8.get("after")), (None, True, 1, R1))
    if want("U17"):
        cache = os.path.join(TMP, "terrcache").replace("\\", "/")
        _, t1, _, r1, _ = run(True, "terr1", "terrain", "1", cache)
        _, t0, _, r0, _ = run(True, "terr0", "terrain", "0", cache)
        w1 = state(r1).get("warnings", [])
        check("U17 a TerrainGenerator with use_cache=True is reported (cache_dir, not under the root); use_cache=False is not",
              (t1.get("error"), [w.get("cache_dir") for w in w1], [w.get("cache_dir_under_root") for w in w1], state(r0).get("warnings", [])),
              (None, [cache], [False], []))
    if want("U18"):
        _, i9, _, r, ft = run(True, "copy", "copy")
        check("U18 a second copy of the converter module loaded under another name: its unwrapped __init__ is stopped before any write",
              ((i9.get("error") or "").split(":")[0], os.path.exists(ft)), ("UsdIsolationError", False))
    if want("U19"):
        _, i10, _, r, ft = run(True, "custom", "custom")
        cd = i10.get("custom_dir", "")
        check("U19 code outside the converter making an IsaacLab/usd_<time>_<n> folder outside the root: refused, the folder not made",
              ((i10.get("error") or "").split(":")[0], bool(cd) and os.path.exists(cd)), ("UsdIsolationError", False))
    if want("U20"):
        _, i11, _, r, ft = run(True, "odd_form", "one", env_extra={"FAKE_FORM": "odd"})
        check("U20 the converter's default folder has another form (a version change): refused before any write, not guessed",
              ((i11.get("error") or "").split(":")[0], os.path.exists(ft), assigned(r)), ("UsdIsolationError", False, []))
    if want("U21"):
        _, i12, _, r, ft = run(True, "dict_form", "one", env_extra={"FAKE_FORM": "dictodd"})
        check("U21 the default folder set without going through the redirect: the run stops with UsdIsolationError",
              ((i12.get("error") or "").split(":")[0],), ("UsdIsolationError",))
    if want("U22"):
        _, i13, _, r, ft = run(True, "reload", "reload", script="kit")
        check("U22 the converter module reloaded behind a Kit-like front finder (a new class object): the new class is wrapped too, under the root",
              (i13.get("error"), u0(i13).startswith(r + "/isaaclab/usd_"), os.path.exists(ft)), (None, True, False))
    # ---- ASTRA 17d 2.6: expected number of conversions ----
    if want("U23"):
        rc, i14, _, r, ft = run(True, "exp0", "one", env_extra={"FOOTHOLD_EXPECT_CONVERSIONS": "0"})
        a = assigned(r)
        check("U23 (17d 2.6) expect 0 and an unexpected conversion: refused at the converter's entry with UsdIsolationError, before the draw "
              "(random afterwards 0.32383276483316237), no folder anywhere (fake /tmp, root/IsaacLab), one refused_unexpected_conversion line",
              ((i14.get("error") or "").split(":")[0], "was not expected" in (i14.get("error") or ""), i14.get("after"), os.path.exists(ft),
               os.path.exists(os.path.join(r, "IsaacLab")), [(x.get("kind"), x.get("usd_dir"), x.get("n")) for x in a]),
              ("UsdIsolationError", True, R0, False, False, [("refused_unexpected_conversion", None, 1)]))
    if want("U24"):
        rc, i15, _, r, ft = run(True, "exp1", "twice_same", env_extra={"FOOTHOLD_EXPECT_CONVERSIONS": "1"})
        made = sorted(os.listdir(os.path.join(r, "IsaacLab"))) if os.path.isdir(os.path.join(r, "IsaacLab")) else []
        check("U24 (17d 2.6) expect 1 and the same cfg converted twice: the first goes under the root (_5305), the second is refused at entry "
              "(one draw, random afterwards 0.9478653606090632), one folder made, no fake /tmp",
              ((i15.get("error") or "").split(":")[0], "converter run 2 was not expected" in (i15.get("error") or ""), i15.get("after"),
               [x[-5:] for x in made], os.path.exists(ft), [x.get("kind") for x in assigned(r)]),
              ("UsdIsolationError", True, R1, ["_5305"], False, ["assigned", "refused_unexpected_conversion"]))
    if want("U25"):
        rc, i16, _, r, ft = run(True, "exp0none", "none", env_extra={"FOOTHOLD_EXPECT_CONVERSIONS": "0"})
        check("U25 expect 0 and no conversion: runs normally, nothing assigned", (rc, i16.get("error"), assigned(r), i16.get("after")), (0, None, [], R0))
    if want("U26"):
        check("U26 an expected count that is not 0, 1 or any: refuse to run (exit 2)",
              run(True, "exp2", "one", env_extra={"FOOTHOLD_EXPECT_CONVERSIONS": "2"})[0], 2)
    if not ONLY:
        for case in ("one", "twice_same", "two_cfgs"):
            _, pp, _, _, _ = run(False, "tp_" + case, case, root=False)
            _, ii, _, _, _ = run(True, "ti_" + case, case)
            print(f"INFO time {case}: conversion calls {pp.get('elapsed_ms', 0):.2f} ms plain, {ii.get('elapsed_ms', 0):.2f} ms with the launcher (fake converter, CPU)")
        _, pb, _, _, _ = run(False, "bench_p", "bench", root=False)
        _, ib, _, _, _ = run(True, "bench_i", "bench")
        print(f"INFO bench (fake converter, CPU): {pb.get('conv_ms', 0):.3f} -> {ib.get('conv_ms', 0):.3f} ms per conversion, "
              f"{pb.get('open_us', 0):.2f} -> {ib.get('open_us', 0):.2f} us per open() (audit hook on every event)")
finally:
    shutil.rmtree(TMP, ignore_errors=True)
print("FAILS", fails)
sys.exit(1 if fails else 0)
