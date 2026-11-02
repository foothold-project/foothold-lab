"""CURRICULUM-GATES 의 「EX-42 지형 커리큘럼 정본 (D163)」 절을 대조한다.
단계 ID 열 개(E0 · E1 · E1F · E2 · E3 · E4 · E5 · M · E6a · E6b) · 단계마다 열두 행 · YAML 칸 표 · 예시 YAML(합 1.0 · 망각 방지 하한).

사용: python -X utf8 ex42_canon_check.py [CURRICULUM-GATES.md]
종료 0 = 전부 · 1 = 어긋남(어느 칸).
"""
import re
import sys
from pathlib import Path

here = Path(__file__).resolve().parent
doc = Path(sys.argv[1]) if len(sys.argv) > 1 else here.parent / "20261026-experiments" / "CURRICULUM-GATES.md"
text = doc.read_bytes().decode("utf-8").replace("\r\n", "\n")
bad = 0
def ok(cond, label):
    global bad
    print(("ok  " if cond else "MISS") + " " + label)
    bad += 0 if cond else 1

STAGES = ["E0", "E1", "E1F", "E2", "E3", "E4", "E5", "M", "E6a", "E6b"]
ROWS = ["지형 종류", "레벨", "치수", "env 몫", "바꾸는 축 하나", "유지 칸", "망각 방지 몫", "승급 문턱", "최대 회차", "연장", "평가 칸", "영상"]

m0 = re.search(r"^## EX-42 지형 커리큘럼 정본 \(D163.*?$", text, re.M)
m1 = re.search(r"^## v0\.6c 이전 원문 보존", text, re.M)
if not (m0 and m1 and m1.start() > m0.start()):
    print("MISS 정본 절 머리 · 끝 없음"); sys.exit(1)
sec = text[m0.start(): m1.start()]
ok("D163" in sec and "D158" in sec and "D159" in sec and "D160" in sec, "머리에 D163 · D158 · D159 · D160")

# E.1
e1 = re.search(r"^### E\.1 .*?(?=^### E\.2 )", sec, re.M | re.S)
ids = re.findall(r"^\| \*\*(E\d[a-zA-Z]*|M)\*\* \|", e1.group(0), re.M) if e1 else []
ok(ids == STAGES, f"E.1 단계 ID 열 개 순서 {ids}")

# E.2 단계표
e2 = re.search(r"^### E\.2 .*?(?=^### E\.3 )", sec, re.M | re.S)
blocks = dict(re.findall(r"^#### (E\d[a-zA-Z]*|M) [^\n]*\n(.*?)(?=^#### |\Z)", e2.group(0), re.M | re.S)) if e2 else {}
ok(sorted(blocks) == sorted(STAGES), f"E.2 단계표 열 개 {sorted(blocks)}")
for sid in STAGES:
    b = blocks.get(sid, "")
    rows = [(c[1].strip(), c[2].strip()) for c in (l.split("|") for l in b.splitlines() if l.startswith("| ")) if len(c) >= 4]
    rows = [r for r in rows if r[0] not in ("행", "---")]
    labels = [re.sub(r"\(.*?\)", "", r[0]).strip() for r in rows]
    ok(labels == ROWS, f"{sid} 열두 행 순서 {labels if labels != ROWS else ''}")
    ok(all(len(v) >= 2 for _, v in rows), f"{sid} 값 칸 비지 않음")
    ok(re.search(r"\| 최대 회차 \| [\d,]+", b) is not None, f"{sid} 최대 회차 숫자")

# E.3 · E.4
e3 = re.search(r"^### E\.3 .*?(?=^### E\.4 )", sec, re.M | re.S).group(0)
for kw in ("정지 10 · 후진 14 · 옆 7 + 7", "52", "60", "3/64", "0.03", "stop_training", "복원 13"):
    ok(kw in e3 or kw in sec, f"E.3 「{kw}」")
e4 = re.search(r"^### E\.4 .*?(?=^### E\.5 )", sec, re.M | re.S).group(0)
ok("| 칸 이름(YAML 경로) | 자료형 | 단위 | 기본값 |" in e4, "E.4 표 머리(칸 이름 · 자료형 · 단위 · 기본값)")
for key in ("`format`", "`env.num_envs`", "`stages[].boundary.kind`", "`stages[].boundary.changed_axis`", "`stages[].terrain.exposure.<family>.<kind>.share`",
            "`stages[].terrain.floors.continuous_share_min`", "`promotion.window_episodes`", "`maintenance.judge_cells`", "`maintenance.on_fail.hold_exposure`",
            "`forgetting_watch.compare_to`", "`eval.every_updates`", "`video.per_kind_success`", "`boundary_file`"):
    ok(key in e4, f"E.4 칸 {key}")
ym = re.search(r"```yaml\n(.*?)```", e4, re.S)
ok(ym is not None, "E.4 예시 YAML 블록")
if ym:
    try:
        import yaml
        y = yaml.safe_load(ym.group(1))
        st = y["stages"][0]
        sh = st["shares"]; tot = sum(sh.values())
        ok(abs(tot - 1.0) < 1e-9, f"예시 shares 합 1.0 ({tot:.3f})")
        ok(sh["stand"] >= 0.10 and sh["reverse"] >= 0.14 and sh["side_left"] >= 0.07 and sh["side_right"] >= 0.07, "예시 망각 방지 하한(정지 · 후진 · 옆)")
        ex = sum(k["share"] for fam in st["terrain"]["exposure"].values() for k in fam.values())
        ok(abs((1 - ex) - 0.95) < 1e-9, f"예시 연속 몫 1 − Σexposure = 0.95 ({1-ex:.2f})")
        ok(st["boundary"]["kind"] in ("S", "L+", "C", "K", "D", "M") and st["boundary"]["changed_axis"].startswith("terrain.exposure"), "예시 boundary 축 하나")
        ok(y["maintenance"]["judge_cells"] == 26 and y["maintenance"]["record_cells"] == 13 and y["maintenance"]["on_fail"]["stop_training"] is False, "예시 26 · 13 · stop_training false")
        ok(y["promotion"]["success_min"] == 52 and y["promotion"]["survival_min"] == 60 and y["env"]["num_envs"] == 3072, "예시 52 · 60 · 3072")
    except ImportError:
        ok(False, "pyyaml 없음(예시 YAML 미검사)")
    except Exception as e:
        ok(False, f"예시 YAML 파싱 · 값 오류 {type(e).__name__}: {e}")

ok(chr(0x2014) not in sec, "em dash 없음(정본 절)")
for n, line in enumerate(sec.splitlines(), 1):
    if re.search(r"26 ?칸", line) and not re.search(r"복원|39|13 칸", line):
        ok(False, f"정본 절 {n} 행 「26 칸」 에 복원 기록 없음: {line[:50]}")
print(("ok" if bad == 0 else "FAIL") + f" 어긋남 {bad}")
sys.exit(0 if bad == 0 else 1)
