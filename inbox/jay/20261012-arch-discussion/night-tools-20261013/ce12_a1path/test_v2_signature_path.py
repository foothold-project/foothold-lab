"""CPU path regression using the recorder AST and copied real v2 fixtures."""

import ast
import hashlib
import json
import os
from pathlib import Path
import sys
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path("C:/Users/AI-WS01/.claude/jobs/09bbf294/tmp/codexB4").resolve()
CANDIDATE = Path(os.environ.get("CE12_B4_CANDIDATE", ROOT / "ce12_candidate")).resolve()
FIXTURE = ROOT / "fixture_real"
MUTANT = Path(os.environ.get("CE12_B4_SOURCE", CANDIDATE / "dump_native_v2.py")).resolve()
EXPECTED_PY = Path(os.environ.get("CE12_B4_EXPECT_PY", "C:/Users/AI-WS01/anaconda3/envs/isaac311-moects/python.exe")).resolve()
EXPECTED_ADAPTER_SHA = os.environ.get(
    "CE12_B4_ADAPTER_SHA", "39c1a2930a5992a65229529c49d8e5c278b202c12c534461f24c7ec26dea00c6"
)
CANON = "C:/Users/AI-WS01/Desktop/jay/인공지능사관학교/foothold-lab/models/foothold-v2.env.yaml"
OLD_SHA = "2f1b0c2b011442c790749f2d21121df3ebbb9e6e1389d2c79fc5d64702814805"
NEW_SHA = "dfc1410feaa60af791abca5d9118f6cb90bbfeb03e526281dc03304ebc748996"
YAML_SHA = "a5ef31d626f8cabe850de37bae0aa26782e14e9db3ba61d678dd1210105323e7"


def contained(p):
    return p.resolve().is_relative_to(ROOT)


for _p in (CANDIDATE, FIXTURE, MUTANT, FIXTURE / "signature.json", FIXTURE / "meta.json",
           FIXTURE / "native.npz", FIXTURE / "foothold-v2.env.yaml", FIXTURE / "changed.yaml"):
    if not contained(_p):
        raise SystemExit(f"ISOLATION_FAIL {_p}")
print("B4_TEST_PATHS_OK", ROOT, CANDIDATE, FIXTURE, MUTANT)
print("sys.executable", sys.executable)
if Path(sys.executable).resolve() != EXPECTED_PY:
    raise SystemExit("환경 불일치: interpreter")

sys.path.insert(0, str(CANDIDATE))
import adapters as A  # noqa: E402
import validate_dump as V  # noqa: E402
import numpy as np  # noqa: E402

actual_adapter = Path(A.__file__).resolve()
adapter_sha = hashlib.sha256(actual_adapter.read_bytes()).hexdigest()
print("adapters.__file__", actual_adapter)
print("adapters.sha256", adapter_sha)
if actual_adapter != CANDIDATE / "adapters.py" or adapter_sha != EXPECTED_ADAPTER_SHA:
    raise SystemExit("환경 불일치: adapters path or SHA256")

with np.load(FIXTURE / "native.npz", allow_pickle=False) as _d:
    DATA = {k: [str(x) for x in _d[k]] for k in ("obs_joint_names", "action_joint_names")}
RECORDED = json.loads((FIXTURE / "signature.json").read_text(encoding="utf-8"))
META = json.loads((FIXTURE / "meta.json").read_text(encoding="utf-8"))
TREE = ast.parse(MUTANT.read_text(encoding="utf-8"), filename=str(MUTANT))


def recorder_env_arg():
    found = [n for n in ast.walk(TREE) if isinstance(n, ast.Call)
             and isinstance(n.func, ast.Attribute) and n.func.attr == "add_argument"
             and n.args and isinstance(n.args[0], ast.Constant) and n.args[0].value == "--env_yaml"]
    assert len(found) == 1, "RECORDER_ARG_COUNT"
    default = next(k.value for k in found[0].keywords if k.arg == "default")
    expr = ast.Expression(default)
    ast.fix_missing_locations(expr)
    lab = CANON.rsplit("/models/", 1)[0]
    return eval(compile(expr, str(MUTANT), "eval"), {"os": os, "LAB": lab})


def recorder_path(raw):
    assignments = [n for n in ast.walk(TREE) if isinstance(n, ast.Assign)
                   and any(isinstance(t, ast.Attribute) and isinstance(t.value, ast.Name)
                           and t.value.id == "args" and t.attr == "env_yaml" for t in n.targets)]
    if not assignments:
        return raw
    assert len(assignments) == 1, "RECORDER_NORMALIZER_COUNT"
    expr = ast.Expression(assignments[0].value)
    ast.fix_missing_locations(expr)
    return eval(compile(expr, str(MUTANT), "eval"), {"os": os, "args": SimpleNamespace(env_yaml=raw)})


_load_yaml = A.load_loose_yaml
_sha = A.sha256_file


def signature(path, changed=False):
    copy = FIXTURE / ("changed.yaml" if changed else "foothold-v2.env.yaml")
    with patch.object(A, "load_loose_yaml", side_effect=lambda _path: _load_yaml(str(copy))), \
         patch.object(A, "sha256_file", side_effect=lambda _path: _sha(str(copy))):
        adapter = A.V2Adapter.from_env_yaml(DATA["obs_joint_names"], 1, DATA["action_joint_names"], env_yaml=path)
        sig = adapter.signature()
        return json.loads(json.dumps(dict(sig, signature_sha256=A.signature_sha256(sig)), ensure_ascii=False))


def check_p1():
    raw = recorder_env_arg()
    assert raw == META["env_yaml"], "P1_DEFAULT_NOT_RECORDED"
    assert "\\" in raw and "/" in raw, "P1_NOT_MIXED"
    now = signature(A.V2_ENV_YAML)
    got = signature(recorder_path(raw))
    assert now["signature_sha256"] == NEW_SHA, "P1_APPROVER_SHA"
    assert got == now, "P1_DEFAULT_VS_APPROVER"
    assert got["source"]["foothold-v2.env.yaml"] == {"path": CANON, "sha256": YAML_SHA}, "P1_SOURCE"


def check_p2():
    now = signature(A.V2_ENV_YAML)
    diff = sorted(k for k in set(RECORDED) | set(now) if RECORDED.get(k) != now.get(k))
    assert RECORDED["signature_sha256"] == OLD_SHA, "P2_RECORDED_SHA"
    assert diff == ["signature_sha256", "source"], f"P2_RECORDED_DIFF {diff}"
    assert RECORDED["source"]["foothold-v2.env.yaml"]["sha256"] == YAML_SHA, "P2_CONTENT"
    assert signature(recorder_path(recorder_env_arg())) == now, "P2_CANDIDATE_VS_APPROVER"


def check_p3():
    samples = [CANON, CANON.replace("/", "\\"), recorder_env_arg()]
    got = [signature(recorder_path(x)) for x in samples]
    assert all(x == got[0] for x in got), "P3_SLASH_VARIANTS"
    assert got[0]["source"]["foothold-v2.env.yaml"]["path"] == CANON, "P3_CANON_PATH"


def check_p4():
    path = recorder_path(CANON)
    first = signature(path)
    changed = signature(path, changed=True)
    assert first["source"]["foothold-v2.env.yaml"]["path"] == changed["source"]["foothold-v2.env.yaml"]["path"], "P4_SAME_PATH"
    assert first["source"]["foothold-v2.env.yaml"]["sha256"] == YAML_SHA, "P4_ORIGINAL_HASH"
    assert changed["source"]["foothold-v2.env.yaml"]["sha256"] != YAML_SHA, "P4_CHANGED_HASH"
    assert first["signature_sha256"] != changed["signature_sha256"], "P4_CONTENT_DISTINCT"


def main():
    failures = []
    for name, fn in (("P1", check_p1), ("P2", check_p2), ("P3", check_p3), ("P4", check_p4)):
        try:
            fn()
            print("PASS", name)
        except Exception as exc:
            failures.append(name)
            print("FAIL", name, f"{type(exc).__name__}: {exc}")
    print(f"SUMMARY {4 - len(failures)}/4 PASS failed {failures}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
