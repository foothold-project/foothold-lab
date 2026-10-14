"""lead 10/14 09:2x · 작업자 B4 후보의 독립 재실행. 후보와 원본을 읽기만 하고 lead 변이는 codexB4/lead_check/ 에만 쓴다.
정상 시험을 두 환경에서, lead 가 만든 변이 셋을 같은 시험으로. CAUGHT 는 실패한 시험 목록이 want 와 같을 때만 센다."""
import hashlib, os, shutil, subprocess, sys
from pathlib import Path

ROOT = Path("C:/Users/AI-WS01/.claude/jobs/09bbf294/tmp/codexB4").resolve()
CAND = ROOT / "ce12_candidate"
TEST = CAND / "test_v2_signature_path.py"
OUT = ROOT / "lead_check"
LOG = Path("C:/Users/AI-WS01/.claude/jobs/09bbf294/tmp/codexw/leadB4")
PY_M = Path("C:/Users/AI-WS01/anaconda3/envs/isaac311-moects/python.exe")
PY_I = Path("C:/Users/AI-WS01/anaconda3/envs/isaac311/python.exe")
assert not OUT.exists(), "lead_check already exists"
OUT.mkdir()
LOG.mkdir(exist_ok=True)

orig = Path("C:/isaac/ext/go2_rl_robotlab/_eval/ce12/dump_native_v2.py").read_bytes()
cand = (CAND / "dump_native_v2.py").read_bytes()
assert hashlib.sha256(orig).hexdigest() == "251220254fc70b7b0adf1bbd2dd85d998c0218a38595c9c598ef3d626015be82"
assert hashlib.sha256(cand).hexdigest() == "a3da62b8185f4a28aa8623997094c245f603f8cdec7820efaa57ba194ff97c16"
olines, clines = orig.decode("utf-8").splitlines(), cand.decode("utf-8").splitlines()
extra = [l for l in clines if l not in olines]
assert len(clines) == len(olines) + 1 and len(extra) == 1, extra
print("DIFF_ONE_LINE:", extra[0])
fix = extra[0]

src = cand.decode("utf-8")
(OUT / "m_revert.py").write_text(src.replace(fix + "\n", "", 1), encoding="utf-8")
(OUT / "m_wrong_direction.py").write_text(src.replace(fix, 'args.env_yaml = os.path.abspath(args.env_yaml).replace("/", "\\\\")', 1), encoding="utf-8")
(OUT / "m_lower_drive.py").write_text(src.replace(fix, 'args.env_yaml = os.path.abspath(args.env_yaml).replace("\\\\", "/").replace("C:/", "c:/", 1)', 1), encoding="utf-8")

for p in (OUT, CAND, TEST):
    assert p.resolve().is_relative_to(ROOT)
adapter_sha = hashlib.sha256((CAND / "adapters.py").read_bytes()).hexdigest()


def run(name, py, source, want, rc_expected):
    env = dict(os.environ, CUDA_VISIBLE_DEVICES="-1", PYTHONDONTWRITEBYTECODE="1", CE12_B4_CANDIDATE=str(CAND),
               CE12_B4_SOURCE=str(source), CE12_B4_ADAPTER_SHA=adapter_sha, CE12_B4_EXPECT_PY=str(py))
    r = subprocess.run([str(py), "-B", str(TEST)], cwd=ROOT, env=env, capture_output=True, text=True, encoding="utf-8", errors="replace")
    (LOG / f"{name}.log").write_text(r.stdout + r.stderr, encoding="utf-8")
    failed = [l.split()[1] for l in r.stdout.splitlines() if l.startswith("FAIL ")]
    passed = [l.split()[1] for l in r.stdout.splitlines() if l.startswith("PASS ")]
    bad = [x for x in ("ModuleNotFoundError", "ImportError", "SyntaxError", "Traceback", "환경 불일치") if x in (r.stdout + r.stderr)]
    ok = r.returncode == rc_expected and failed == want and not bad
    print(f"{'OK  ' if ok else 'BAD '} {name}: rc={r.returncode} pass={passed} failed={failed} want={want} bad={bad}")
    return ok


res = [
    run("normal_moects", PY_M, CAND / "dump_native_v2.py", [], 0),
    run("normal_isaac311", PY_I, CAND / "dump_native_v2.py", [], 0),
    run("m_revert", PY_M, OUT / "m_revert.py", ["P1", "P2", "P3"], 1),
    run("m_wrong_direction", PY_M, OUT / "m_wrong_direction.py", ["P1", "P2", "P3"], 1),
    run("m_lower_drive", PY_M, OUT / "m_lower_drive.py", ["P1", "P2", "P3"], 1),
]
print("LEAD_SUMMARY", sum(1 for x in res if x), "/", len(res))
sys.exit(0 if all(res) else 1)
