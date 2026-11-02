"""EX-42 설계 v0.3 에 팀장 결정(D158 Q1 · D160 Q6 문구 · Q7 순서 이유 · D159 Q13 교환 학습 · Q9 4096) 이 들어갔는지 대조한다.

사용: python -X utf8 ex42_decisions_check.py [DESIGN-EX42-TERRAIN-draft.md] [문서 폴더 루트(inbox/jay)]
검사는 단계별 커밋마다 늘어난다. 종료 0 = 전부 · 1 = 어긋남(어느 칸).
"""
import re
import sys
from pathlib import Path

here = Path(__file__).resolve().parent
doc = Path(sys.argv[1]) if len(sys.argv) > 1 else here / "DESIGN-EX42-TERRAIN-draft.md"
root = Path(sys.argv[2]) if len(sys.argv) > 2 else here.parent
text = doc.read_text(encoding="utf-8")
bad = 0
def ok(cond, label):
    global bad
    print(("ok  " if cond else "MISS") + " " + label)
    bad += 0 if cond else 1

m13 = re.search(r"^## 13\. 정할 것.*?$", text, re.M)
m13b = re.search(r"^### 13b\..*?$", text, re.M)
assert m13 and m13b
rows = {}
for line in text[m13.end(): m13b.start()].splitlines():
    mm = re.match(r"\| (Q\d+) \| (.*?) \| (.*?) \| (.*?) \| (.*?) \|$", line)
    if mm:
        rows[mm.group(1)] = (mm.group(2), mm.group(4))
def closed_with(q, d):
    r = rows.get(q)
    ok(r is not None and r[0].startswith("~~") and d in r[1], f"§13 {q} 닫힘 · {d}")

# (B) D158 Q1
closed_with("Q1", "D158")
m42 = re.search(r"^### 4\.2 .*?(?=^### 4\.3 )", text, re.M | re.S)
ok(m42 is not None and "**결정(D158" in m42.group(0) and "학습 열은 Go2" in m42.group(0) and "어려운 쪽" in m42.group(0), "§4.2 결정 문단(D158 · 학습 Go2 축척 · 평가 어려운 쪽)")
ok(m42 is not None and re.search(r"^\| 틈\(gap\) \| 0\.78 \| ", m42.group(0), re.M) is not None, "§4.2 결정 표 학습 열 틈 0.78")
ok(re.search(r"^\*\*D158\*\*: 위 표의 stepping_stones", text, re.M) is not None, "§3.1 D158 축척 생성 문장")

# (C) D160 Q6 문구 · 세 폴더 모든 md
if "**D160**" in text:
    closed_with("Q6", "D160")
    for folder in ("20261101-ex41", "20261102-ex42", "20261101-app"):
        for p in sorted((root / folder).glob("*.md")):
            for n, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
                if re.search(r"26 ?칸", line) and not re.search(r"복원|39|13 칸", line):
                    ok(False, f"{p.name}:{n} 「26 칸」 줄에 복원 · 39 · 13 칸 없음: {line[:60]}")
    ok(True, "D160 「26 칸」 줄마다 복원 기록 언급(세 폴더)")
    ok(not re.search(r"복원[^|\n]{0,12}(제외|빼고 판정|빼는)", text), "설계에 「복원 제외」 꼴 문장 없음")

# (D) Q7 순서 표
if "### 1.1 왜 이 난이도 순서인가" in text:
    m11 = re.search(r"^### 1\.1 .*?(?=^## 2\. )", text, re.M | re.S)
    trows = [l for l in m11.group(0).splitlines() if re.match(r"\| \d+ \| \*\*", l)]
    v04 = "### 1.2 경계표" in text
    names = (["S3-0", "T1", "F1", "T2", "T3", "F2", "T4", "F3", "T5", "옛 T6", "지형 2 판"] if v04
             else ["S3-0", "T1", "T2", "F1", "T3", "F2", "T4", "F3", "T5", "T6", "지형 2 판"])
    ok(len(trows) == 11 and all(nm in r for nm, r in zip(names, trows)), f"§1.1 순서 표 11 행 {len(trows)} · 순서 {'v0.4' if v04 else 'v0.3'}")
    for r in trows:
        cells = [c.strip() for c in r.strip("|").split("|")]
        ok(len(cells) == 4 and len(cells[2]) >= 40 and len(cells[3]) >= 8, f"§1.1 {cells[1][:12]} 이유 · analyst 칸")
    ok("analyst 의견" in m11.group(0).splitlines()[4] if len(m11.group(0).splitlines()) > 4 else False, "§1.1 표 머리에 analyst 의견 열")

# (H) v0.4 analyst REVIEW-EX42-Q7-ORDER 막음 A · B · C
if "### 1.2 경계표" in text:
    m11 = re.search(r"^### 1\.1 .*?(?=^### 1\.2 )", text, re.M | re.S).group(0)
    row = {}
    for l in m11.splitlines():
        if re.match(r"\| \d+ \| \*\*", l):
            row[re.search(r"\*\*(.+?)\*\*", l).group(1)] = l
    ok("start_sheet.py:35" in row.get("T2", "") and "딛는 면이 아니다" in row.get("T2", ""), "(A) T2 평균대 낙차 코드 근거 정정")
    ok("미확인" in row.get("T3", "") and "보폭" in row.get("T3", ""), "(A) T3 틈 보폭 근거 정정(미확인)")
    ok("삭제" in row.get("F2", "") and "15-TERRAIN 83" in row.get("F2", ""), "(문구) F2 깃발 문구 삭제 · 연속 지형 깃발 열")
    ok("값 활성화" in row.get("지형 2 판", "") and "D93" in row.get("지형 2 판", ""), "(문구) 지형 2 판 h/roll 값 활성화 · D93")
    for old in ("떨어져도 평지라 틈보다", "0.3 은 보폭 안(hip 간격 0.387 m, §4.1)", "열린 뒤에야 지형 너머 깃발이 뜻을 가진다 ·"):
        ok(old not in text, f"옛 문장 없음: {old[:24]}")
    m12 = re.search(r"^### 1\.2 .*?(?=^## 2\. )", text, re.M | re.S).group(0)
    ok("학습에서 바뀌는 축(하나)" in m12, "(B) §1.2 표 머리 「학습에서 바뀌는 축(하나)」")
    kinds = [l for l in m12.splitlines() if re.match(r"\| (S|L\+|C|K|D|M)\(", l)]
    ok(len(kinds) == 6 and all(len([c for c in l.strip("|").split("|")]) == 5 for l in kinds), f"(B) §1.2 경계 종류 6 행 {len(kinds)}")
    ok("모든 경계에서 늘 잰다" in m12 and "L+" in m12, "(B) 평가 지점 L3/6/9 늘 잼 · 학습 상한은 L+ 경계")
    m62 = re.search(r"^### 6\.2 .*?(?=^## 7\. )", text, re.M | re.S)
    ok(m62 is not None, "(C) §6.2 유지 계약 절")
    if m62:
        s = m62.group(0)
        for kw in ("정지 0.10", "후진 0.14", "옆 0.07", "지도 모드", "추종", "접촉", "되돌림", "yaml:381~394", "실제 종료 에피소드 수", "소급"):
            ok(kw in s, f"(C) §6.2 「{kw}」")
        ok("읽기" in s and "미재측" in s, "(C) §6.2 analyst 숫자는 읽기 · 미재측 표시")
    ok("### 13b-2." in text and "| A 선행 기술" in text and "| B 변경 경계" in text and "| C 유지 계약" in text, "§13b-2 반영 표 A · B · C")
    r7 = rows.get("Q7")
    ok(r7 is not None and not r7[0].startswith("~~") and "v0.4 안을 정본" in r7[1], "§13 Q7 열림 · v0.4 안(종류별 선행 기술) 을 정본으로")

# (E) D159 Q13 교환 학습
if "### 6.1 교환 학습 감시 규칙" in text:
    closed_with("Q13", "D159")
    m61 = re.search(r"^### 6\.1 .*?(?=^## 7\. )", text, re.M | re.S).group(0)
    for kw in ("직전 경계", "반복 폭", "확대를 멈춘다", "보고", "노출된 모든 종류", "D156"):
        ok(kw in m61, f"§6.1 「{kw}」")

# (F) Q9 4096
if "4,096 의 출처" in text:
    closed_with("Q9", "D159")
    ok("4,096 은 별도" not in text, "「4,096 은 별도」 없음")
    m2 = [l for l in text.splitlines() if l.startswith("| M2 업로드 · 메모리 |")]
    ok(len(m2) == 1 and "3,072" in m2[0] and "4,096" not in m2[0], "M2 행 상한 3,072 · 4,096 없음")
    ok(re.search(r"env\.yaml:86", text) is not None and "3072" in text, "3,072 근거 env.yaml:86")

ok(chr(0x2014) not in text, "em dash 없음")
head = text.splitlines()[:5]
ok(all(h.startswith("> ") and k in h for h, k in zip(head, ("분류", "작성", "근거", "요지", "상태"))), "머리 다섯 줄")
print(("ok" if bad == 0 else "FAIL") + f" 어긋남 {bad}")
sys.exit(0 if bad == 0 else 1)
