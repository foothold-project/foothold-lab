import sys; sys.path.insert(0, r"C:/Users/AI-WS01/AppData/Local/Temp/claude/C--Users-AI-WS01-Desktop-jay----------foothold-lab/09bbf294-fda0-4c7b-81c5-e23f793f2be2/figs/six-cases")
from six_table import one
from pathlib import Path
N = Path("C:/mai/wt/foothold-lab/impl-turncases/logs/six_cases")
T = ["b1500", "b50_m1510", "b50_m1550", "a50_m1550"]; H = ["B1500", "흩기 b50 m1510", "흩기 b50 m1550", "안 흩기 a50 m1550"]
C = [("indep_left", "좌 독립"), ("indep_right", "우 독립"), ("fwd_then_left", "전진 → 좌"), ("fwd_then_right", "전진 → 우"), ("right_then_left", "우 → 좌"), ("left_then_right", "좌 → 우")]
print("| 경우 | " + " | ".join(H) + " |"); print("|---" * (len(H) + 1) + "|")
for k, name in C:
    cells = []
    for t in T:
        y, c, _, al = one(N / t / f"arrays_{k}.npz", 1.0)
        cells.append(f"{y:+.2f} / {c:.2f}" + ("" if al == 16 else f" ({al}/16)"))
    print(f"| {name} | " + " | ".join(cells) + " |")
print("| min(좌, 우) 독립 요 크기 | " + " | ".join(f"{min(abs(one(N/t/'arrays_indep_left.npz',1.0)[0]), abs(one(N/t/'arrays_indep_right.npz',1.0)[0])):.2f}" for t in T) + " |")
