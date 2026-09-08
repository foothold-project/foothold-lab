"""g* 고르기 - FLAT 계열에서 통과율 95% CI «하한» 이 0.95 이상인 틈 중 가장 긴 것.

🔴 점추정이 아니라 하한으로 자른다. 타일이 10개뿐이라 CI 가 넓고,
   관측 95% 가 실제로는 80% 일 수 있다. 그런 틈을 고르면 나중에 턱 때문에 떨어진 몫과
   원래 아슬아슬했던 몫을 못 가른다.
"""
import json, os, subprocess, sys

O = os.environ.get("GAP_OUT", "")
if not O:
    raise SystemExit("GAP_OUT 에 결과 폴더를 지정해야 한다. 예: export GAP_OUT=<볼륨>/experiments/20260907_gap-threshold")
GAPS = [("000", 0.000), ("025", 0.025), ("050", 0.050), ("075", 0.075),
        ("100", 0.100), ("150", 0.150), ("200", 0.200)]
rows, ok = [], []
for tag, g in GAPS:
    d = os.path.join(O, f"flat{tag}_s42")
    mp, cp = os.path.join(d, "manifest.json"), os.path.join(d, f"flat{tag}_steps.csv")
    if not (os.path.exists(mp) and os.path.exists(cp)):
        rows.append((g, None, None, None, "(아직 없음)")); continue
    m = json.load(open(mp))["terrain"]["resolved"]
    jp = os.path.join(d, "metrics.json")
    subprocess.run([sys.executable, os.path.join(os.path.dirname(os.path.abspath(__file__)), "summarize.py"),
                    "--runup", str(m["runup_x_m"]), "--pass_x", str(m["boundary_x_m"]),
                    "--foot_dx", "0.181", "--json", jp, cp],
                   check=True, stdout=subprocess.DEVNULL)
    r = json.load(open(jp))["runs"][0]
    p = r.get("success_rate_env_uniform")
    ci = r.get("success_rate_env_uniform_ci95") or [None, None]
    rows.append((g, p, ci[0], ci[1], "하한>=0.95" if (ci[0] is not None and ci[0] >= 0.95) else ""))
    if ci[0] is not None and ci[0] >= 0.95:
        ok.append(g)

print("틈m | 통과율(env균등) | CI하한 | CI상한 | 후보")
for g, p, lo, hi, note in rows:
    f = lambda v: "-" if v is None else f"{v:.3f}"
    print(f"{g:.3f} | {f(p)} | {f(lo)} | {f(hi)} | {note}")
print()
if ok:
    print(f"g* = {max(ok):.3f} m   (하한 0.95 를 넘긴 틈: {[f'{v:.3f}' for v in ok]})")
else:
    print("g* 없음 - 어느 틈에서도 CI 하한이 0.95 를 못 넘겼다. ③ 높이 축은 틈 0 만 돌린다"
          " (또는 잴 여지가 없으면 생략)")
