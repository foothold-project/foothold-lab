"""EX-42 설계 §13 표의 Q 마다 §13c 쉬운 판이 네 칸(무엇을 정하나 · 왜 지금 · 고르면 무엇이 달라지나 · 숫자 예) 을 갖췄는지 대조한다.
닫힌 Q(표 물음 칸이 ~~ 로 시작) 는 §13c 에 「결정」 칸(D 번호 포함) 이 더 있어야 한다.

사용: python -X utf8 ex42_q_easy_check.py [DESIGN-EX42-TERRAIN-draft.md]
종료 0 = 전부 · 1 = 어긋남(어느 Q · 어느 칸).
"""
import re
import sys
from pathlib import Path

here = Path(__file__).resolve().parent
doc = Path(sys.argv[1]) if len(sys.argv) > 1 else here / "DESIGN-EX42-TERRAIN-draft.md"
text = doc.read_text(encoding="utf-8")
bad = 0
def ok(cond, label):
    global bad
    print(("ok  " if cond else "MISS") + " " + label)
    bad += 0 if cond else 1

m13 = re.search(r"^## 13\. 정할 것.*?$", text, re.M)
m13b = re.search(r"^### 13b\..*?$", text, re.M)
m13c = re.search(r"^### 13c\..*?$", text, re.M)
m14 = re.search(r"^## 14\..*?$", text, re.M)
if not (m13 and m13c and m14):
    print("MISS §13 · §13c · §14 머리 가운데 없음"); sys.exit(1)
table = text[m13.end(): (m13b.start() if m13b else m13c.start())]
open_q, closed_q = [], []
for line in table.splitlines():
    mm = re.match(r"\| (Q\d+) \| (.*?) \|", line)
    if mm:
        (closed_q if mm.group(2).startswith("~~") else open_q).append(mm.group(1))
ok(len(open_q) + len(closed_q) >= 13, f"§13 열린 Q {len(open_q)} {open_q} · 닫힌 Q {len(closed_q)} {closed_q}")
easy = text[m13c.start(): m14.start()]
blocks = dict(re.findall(r"^#### (Q\d+) [^\n]*\n(.*?)(?=^#### Q\d+ |\Z)", easy, re.M | re.S))
labels = ("무엇을 정하나", "왜 지금", "고르면 무엇이 달라지나", "숫자 예")
for q in open_q + closed_q:
    b = blocks.get(q)
    if b is None:
        ok(False, f"{q} 쉬운 판 없음"); continue
    for lab in labels:
        mm = re.search(rf"^- \*\*{lab}\*\*: (.+)$", b, re.M)
        ok(mm is not None and len(mm.group(1)) >= 20, f"{q} 「{lab}」 칸")
        if lab == "숫자 예" and mm:
            ok(re.search(r"\d", mm.group(1)) is not None, f"{q} 숫자 예에 숫자")
    if q in closed_q:
        mm = re.search(r"^- \*\*결정\*\*: (.+)$", b, re.M)
        ok(mm is not None and re.search(r"D1\d\d", mm.group(1)) is not None, f"{q} 닫힘 → 「결정」 칸에 D 번호")
extra = sorted(set(blocks) - set(open_q) - set(closed_q))
ok(not extra, f"§13c 에만 있는 Q {extra}")
ok("4,096" not in easy and "4096" not in easy, "§13c 에 4,096 없음(D159 기본 3,072)")
ok(chr(0x2014) not in text, "em dash 없음")
head = text.splitlines()[:5]
ok(all(h.startswith("> ") and k in h for h, k in zip(head, ("분류", "작성", "근거", "요지", "상태"))), "머리 다섯 줄")
print(("ok" if bad == 0 else "FAIL") + f" 어긋남 {bad}")
sys.exit(0 if bad == 0 else 1)
