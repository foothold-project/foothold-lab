"""lead 10/14 · ASTRA 17n (v2 단회 재시도) 4 절이 요구한 기동 직전 확인. 읽기만 한다 (쓰기는 표준 출력뿐).
사용: python prelaunch_v2.py <새 tag>  (새 tag 가 이미 있으면 보류 표시)"""
import hashlib, json, os, subprocess, sys, time, glob

E = "C:/isaac/ext/go2_rl_robotlab/_eval"
R = "C:/Users/AI-WS01/Desktop/jay/인공지능사관학교/foothold-lab"
N = R + "/inbox/jay/20261012-arch-discussion/night-tools-20261013"
tag = sys.argv[1] if len(sys.argv) > 1 else ""
out = {"t": time.strftime("%Y-%m-%d %H:%M:%S"), "epoch": int(time.time()), "tag": tag}


def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


def sums(path):
    d = {}
    for ln in open(path, encoding="utf-8").read().splitlines():
        p = ln.strip().split(None, 1)
        if len(p) == 2 and len(p[0]) == 64:
            d[p[1].lstrip("*").replace("\\", "/").rsplit("/", 1)[-1]] = p[0]
    return d


# 1 환경 변수 override
out["env_overrides"] = sorted(k for k in os.environ if k.startswith(("UNCR_", "CE12_", "RAND_")))
# 2 GPU
q = subprocess.run(["nvidia-smi", "--query-gpu=index,uuid,memory.total,memory.used", "--format=csv,noheader,nounits"], capture_output=True, text=True).stdout.strip().splitlines()
gpus = []
for ln in q:
    i, u, t, used = [x.strip() for x in ln.split(",")]
    gpus.append({"index": int(i), "uuid": u, "total_mib": int(t), "used_mib": int(used), "free_mib": int(t) - int(used)})
out["gpus"] = gpus
apps = subprocess.run(["nvidia-smi", "--query-compute-apps=gpu_uuid,pid,process_name", "--format=csv,noheader"], capture_output=True, text=True).stdout.strip().splitlines()
out["compute_apps_python_or_kit"] = [a for a in apps if "python" in a.lower() or "kit" in a.lower() or "isaac" in a.lower()]
# 3 상대가 될 수 있는 프로세스 (tail · 이 조회 자체는 뺀다)
ps = subprocess.run(["powershell", "-NoProfile", "-Command",
    "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'rand_driver|run_dump|unseen_driver|branch_run|isaac_slot|usd_isolate|gpu_guard|dump_native|q_eval|cmdr_eval|kit\\.exe|isaac-sim' -and $_.Name -notmatch 'tail.exe|powershell.exe|bash.exe' } | ForEach-Object { '{0}|{1}|{2}' -f $_.ProcessId,$_.Name,($_.CommandLine -replace '\\s+',' ').Substring(0,[Math]::Min(160,$_.CommandLine.Length)) }"],
    capture_output=True, text=True).stdout.strip().splitlines()
out["counterparty_processes"] = ps
pyps = subprocess.run(["powershell", "-NoProfile", "-Command",
    "Get-Process python,pythonw -ErrorAction SilentlyContinue | ForEach-Object { '{0}|{1}|{2}' -f $_.Id,$_.ProcessName,$_.StartTime }"], capture_output=True, text=True).stdout.strip().splitlines()
out["python_processes"] = pyps


# 4 registry 와 그 로그를 직접 열어 본다
def read_reg(p):
    try:
        d = json.load(open(p, encoding="utf-8"))
    except Exception as ex:
        return {"error": f"{type(ex).__name__}: {ex}"}
    ent = []
    for k, v in d.items():
        v = v if isinstance(v, str) else json.dumps(v)[:200]
        rec = {"key": k[-60:], "log": v[-90:]}
        try:
            with open(v, "rb") as f:
                f.read(2048)
            rec.update(exists=True, readable=True, size=os.path.getsize(v))
        except FileNotFoundError:
            rec.update(exists=False, readable=False)
        except Exception as ex:
            rec.update(exists=True, readable=False, err=type(ex).__name__)
        ent.append(rec)
    return {"n": len(ent), "exists": sum(1 for e in ent if e.get("exists")), "readable": sum(1 for e in ent if e.get("readable")),
            "missing": [e for e in ent if not e.get("exists")][:5], "unreadable": [e for e in ent if e.get("exists") and not e.get("readable")][:5]}


out["legacy_registry"] = read_reg(E + "/slot/isaac_usd_registry.json")
out["v3_registry"] = read_reg(E + "/slot/isaac_usd_registry_v3.json")
# 5 STOP
out["stop_files"] = [p for pat in ("out_ce12/STOP", "out_rand/STOP", "out_uncr_v6/STOP", "out_uncr_v6/HALT_v6.json", "out_branch/STOP", "slot/STOP") for p in glob.glob(E + "/" + pat)]
# 6 새 tag 가 비어 있는지
nat = E + "/out_ce12/native"
out["tag_collision"] = sorted(p for p in glob.glob(nat + "/*") + glob.glob(nat + "/_attempts/*") if tag and tag in os.path.basename(p))
# 7 CE12 해시 (이번 판 SHA256SUMS 대조)
mf = sums(N + "/ce12_mapfix/SHA256SUMS.txt")
mf["dump_native_v2.py"] = "a3da62b8185f4a28aa8623997094c245f603f8cdec7820efaa57ba194ff97c16"  # 17p 후보 A
out["ce12_same_as_17p"] = {f: (sha(f"{E}/ce12/{f}") == h) for f, h in mf.items() if os.path.exists(f"{E}/ce12/{f}")}
out["ce12_missing_in_eval"] = [f for f in mf if not os.path.exists(f"{E}/ce12/{f}")]
# 8 체크포인트
v2 = R + "/models/foothold-v2.pt"
out["v2_checkpoint"] = {"path": v2, "exists": os.path.exists(v2), "sha256": sha(v2) if os.path.exists(v2) else None}
# 9 실제 기록기가 읽는 rsl_rl (isaac311 site-packages)
rl = "C:/Users/AI-WS01/anaconda3/envs/isaac311/Lib/site-packages/rsl_rl/runners/on_policy_runner.py"
out["isaac311_runner"] = {"path": rl, "exists": os.path.exists(rl), "sha256": sha(rl) if os.path.exists(rl) else None}
rl2 = "C:/isaac/ext/go2_rl_robotlab/source/rsl_rl/rsl_rl/runners/on_policy_runner.py"
out["moects_source_runner"] = {"path": rl2, "exists": os.path.exists(rl2), "sha256": sha(rl2) if os.path.exists(rl2) else None}
# 10 새 코드 묶음 후보 (10 파일)
bundle = []
for f in ["adapters.py", "cells.py", "compare_native.py", "dump_native_cts.py", "dump_native_v2.py", "run_dump.py", "validate_dump.py"]:
    bundle.append((sha(f"{E}/ce12/{f}"), f"ce12/{f}"))
for f in ["isaac_slot_v3.py", "usd_isolate_run_v3.py", "gpu_guard.py"]:
    bundle.append((sha(f"{E}/{f}"), f))
out["bundle_lines"] = [f"{h} *{n}" for h, n in bundle]
out["bundle_sha256_of_text"] = hashlib.sha256(("\n".join(out["bundle_lines"]) + "\n").encode("utf-8")).hexdigest()
print(json.dumps(out, ensure_ascii=False, indent=1))
