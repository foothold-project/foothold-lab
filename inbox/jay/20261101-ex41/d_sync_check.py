"""D129~D154 결정이 EX-41 설계 §13 표와 그 표가 가리키는 문서에 들어갔는지 대조한다.

사용: python -X utf8 d_sync_check.py [WORKLIST.md] [DESIGN-EX41-STAGE2-draft.md] [첫 D] [끝 D]
- WORKLIST 의 「- D1xx 」 행(범위 안) 과 설계 §13 표의 D 행이 같은 집합이어야 한다.
- 표의 「이 문서 자리」 가 「없음」 이 아니면 §13 앞 본문에 그 D 번호가 있어야 한다.
- 표의 「다른 문서」 에 적힌 *.md 는 설계 문서 옆 폴더(20261101-ex41 · 20261102-ex42) 에 있고 그 D 번호를 담아야 한다.
- 여섯 문서 모두 em dash 없음 · 머리 다섯 줄.
종료 0 = 일치 · 1 = 어긋남 · 2 = 입력 없음.
"""
import re
import sys
from pathlib import Path

here = Path(__file__).resolve().parent
wl = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("C:/mai/wt/foothold-lab/view-latest/inbox/jay/20261028-plan/WORKLIST.md")
design = Path(sys.argv[2]) if len(sys.argv) > 2 else here / "DESIGN-EX41-STAGE2-draft.md"
lo = int(sys.argv[3]) if len(sys.argv) > 3 else 129
hi = int(sys.argv[4]) if len(sys.argv) > 4 else 154
for p in (wl, design):
    if not p.is_file():
        print("없음:", p)
        sys.exit(2)

bad = 0
def ok(cond, label):
    global bad
    print(("ok  " if cond else "MISS") + " " + label)
    bad += 0 if cond else 1

wl_ids = set()
for line in wl.read_text(encoding="utf-8").splitlines():
    m = re.match(r"- (D(\d{3})) ", line)
    if m and lo <= int(m.group(2)) <= hi:
        wl_ids.add(m.group(1))
ok(len(wl_ids) > 0, f"WORKLIST 범위 D{lo}~D{hi} 행 {len(wl_ids)} 개")

text = design.read_text(encoding="utf-8")
m = re.search(r"^## 13\. 결정 D\d+~D\d+ 반영 표.*?$", text, re.M)
if not m:
    print("MISS 설계 §13 표 없음"); sys.exit(1)
body, table = text[: m.start()], text[m.start():]
rows = {}
for line in table.splitlines():
    mm = re.match(r"\| (D\d{3}) \| (.*?) \| (.*?) \| (.*?) \| (.*?) \|$", line)
    if mm:
        rows[mm.group(1)] = (mm.group(3).strip(), mm.group(4).strip())
ok(set(rows) == wl_ids, f"표 행 {sorted(rows)} = WORKLIST 행 (빠짐 {sorted(wl_ids - set(rows))} · 남음 {sorted(set(rows) - wl_ids)})")

docs_checked = {design}
folders = [design.parent, design.parent.parent / "20261102-ex42"]
for d, (place, others) in sorted(rows.items()):
    if not place.startswith("없음"):
        ok(re.search(rf"\b{d}\b", body) is not None, f"{d} 설계 본문({place})")
    for name in re.findall(r"[A-Za-z0-9_.-]+\.md", others):
        found = [f / name for f in folders if (f / name).is_file()]
        if not found:
            ok(False, f"{d} 문서 없음 {name}")
            continue
        t = found[0].read_text(encoding="utf-8")
        docs_checked.add(found[0])
        ok(re.search(rf"\b{d}\b", t) is not None, f"{d} in {name}")

for p in sorted(docs_checked):
    t = p.read_text(encoding="utf-8")
    ok(chr(0x2014) not in t, f"em dash 없음 {p.name}")
    head = t.splitlines()[:5]
    ok(all(h.startswith("> ") and k in h for h, k in zip(head, ("분류", "작성", "근거", "요지", "상태"))), f"머리 다섯 줄 {p.name}")
print(("ok" if bad == 0 else "FAIL") + f" 어긋남 {bad}")
sys.exit(0 if bad == 0 else 1)
