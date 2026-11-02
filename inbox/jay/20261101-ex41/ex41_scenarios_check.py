"""U9 시나리오표가 P7 정본의 기계 블록과 같은 상수를 쓰는지 대조한다.

사용: python -X utf8 ex41_scenarios_check.py [시나리오 md] [P7 md]
종료 0 = 전부 일치 · 1 = 어긋남(어떤 상수인지 출력).
P7 기계 블록(```json)을 읽어 경계 · 문턱을 꺼내고, 시나리오표 본문에 그 값이 그대로 있는지 본다.
문턱을 넓힌 사본(예: 60/64 → 56/64) 은 여기서 걸린다.
"""
import json
import re
import sys
from pathlib import Path

here = Path(__file__).resolve().parent
scen = Path(sys.argv[1]) if len(sys.argv) > 1 else here / "EX41-RESULT-SCENARIOS.md"
p7 = Path(sys.argv[2]) if len(sys.argv) > 2 else here / "P7-GRADUATION-SPEC.md"

p7_text = p7.read_text(encoding="utf-8")
m = re.search(r"```json\s*(\{.*?\})\s*```", p7_text, re.S)
if not m:
    print("P7 기계 블록 없음:", p7)
    sys.exit(1)
spec = json.loads(m.group(1))
text = scen.read_text(encoding="utf-8")

def need(label, token):
    ok = token in text
    print(("ok  " if ok else "MISS") + f" {label}: {token}")
    return ok

checks = []
b1, b2 = spec["boundaries"]
c1, c2 = spec["measured_checkpoints"]
e1, e2 = spec["boundaries_if_extended"]
checks.append(need("경계 1", f"n{b1}"))
checks.append(need("경계 2", f"n{b2}"))
checks.append(need("저장본 1", f"n{c1}"))
checks.append(need("저장본 2", f"n{c2}"))
checks.append(need("연장 경계 1", f"n{e1}"))
checks.append(need("연장 경계 2", f"n{e2}"))
checks.append(need("D57 생존", f"{spec['d57_survival']}/64"))
checks.append(need("D57 오차", f"{spec['d57_error']:g}"))
checks.append(need("상대선 생존", f"{spec['relative_survival_drop']}/64"))
checks.append(need("상대선 오차", f"{spec['relative_error_add']:g}"))
checks.append(need("yaw 한계", f"{spec['yaw_limit_deg']:g}°"))
checks.append(need("yaw 연속", f"{spec['yaw_consecutive']} 연속"))
checks.append(need("서 있기", f"≥ {spec['stand_min_passed']}"))
checks.append(need("use_gt_frac 가정", f"{spec['use_gt_frac_limit_assumed']:g}"))
checks.append(need("판정 칸 수", f"{spec['judged_cells_for_dr']} 칸 판정"))
checks.append(need("기록 칸 수", f"{spec['recorded_cells']} 칸 기록"))
checks.append(need("runtime 졸업 없음", "graduated false") or need("runtime 졸업 없음(대문자)", "graduated False"))
checks.append(need("졸업 파일", "graduation.json"))
checks.append(need("끝 저장본 요청", "final_eval_requests"))
# em dash · 머리 다섯 줄
checks.append((chr(0x2014) not in text) or print("MISS em dash 있음") or False)
head = text.splitlines()[:5]
checks.append(all(h.startswith("> ") and k in h for h, k in zip(head, ("분류", "작성", "근거", "요지", "상태"))) or print("MISS 머리 다섯 줄") or False)
bad = sum(1 for c in checks if not c)
print(f"{'ok' if bad == 0 else 'FAIL'} {len(checks) - bad}/{len(checks)}")
sys.exit(0 if bad == 0 else 1)
