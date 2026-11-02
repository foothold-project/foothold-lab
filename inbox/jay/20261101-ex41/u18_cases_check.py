"""U18 문서가 코드의 경우 이름을 빠짐없이 적었는지 대조한다.

사용: python -X utf8 u18_cases_check.py [문서 md] [저장소 루트(foothold_s2 가 있는 곳)]
- turn_probe_plan.PROTOCOLS 의 모든 경우 이름과 axis_v2_cells.case_specs() 의 모든 칸 이름이 문서에 있어야 한다.
- 머리 다섯 줄 · em dash 없음.
종료 0 = 전부 일치 · 1 = 어긋남. 모듈이 없으면(다른 가지) 2.
"""
import sys
from pathlib import Path

here = Path(__file__).resolve().parent
doc = Path(sys.argv[1]) if len(sys.argv) > 1 else here / "U18-TURN-SIX-CASES-VS-W57.md"
repo = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("D:/mai-wt/foothold-lab/analyst-ex41-score-name-1102")
if not (repo / "foothold_s2" / "eval" / "turn_probe_plan.py").is_file():
    print("turn_probe_plan.py 없음:", repo)
    sys.exit(2)
sys.path.insert(0, str(repo))
from foothold_s2.eval import turn_probe_plan as P  # noqa: E402
from foothold_s2.eval import axis_v2_cells as A  # noqa: E402

text = doc.read_text(encoding="utf-8")
bad = 0

def need(label, token):
    global bad
    ok = token in text
    print(("ok  " if ok else "MISS") + f" {label}: {token}")
    bad += 0 if ok else 1

for name in P.PROTOCOLS:
    need("turn_probe 경우", name)
for name in P.DEFAULT_CASES:
    need("기본 다섯", name)
for spec in A.case_specs():
    need("W57 칸", spec["name"])
need("W57 wz", f"wz {A.TURN_WZ_RADPS:g}")
need("turn_probe wz", f"wz {P.WZ:g}")
need("기록 길이", f"기록 {P.RECORD_S:g} s")
need("앞 구간", f"앞 {P.PRE_S:g} s")
if chr(0x2014) in text:
    print("MISS em dash 있음"); bad += 1
head = text.splitlines()[:5]
if not all(h.startswith("> ") and k in h for h, k in zip(head, ("분류", "작성", "근거", "요지", "상태"))):
    print("MISS 머리 다섯 줄"); bad += 1
print(("ok" if bad == 0 else "FAIL") + f" 어긋남 {bad}")
sys.exit(0 if bad == 0 else 1)
