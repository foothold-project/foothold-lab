"""W 하나를 시작하기 전에 앞 일과 뒤 일을 WORKLIST 표에서 읽어 보인다 (팀장 10/29 23:4x: 메모리가 아니라 표로).

쓰는 법: python _out/tools/worklist_gate.py W58
- 앞 일: 그 W 의 「앞 일」 칸에 적힌 W 번호들과 그 상태.
- 뒤 일: 「앞 일」 칸에 그 W 를 적은 다른 W 들(이 일이 끝나면 걸어야 할 것).
- 종료 코드: 앞 일 중 상태에 「끝」 · 「닫힘」 · 「대체」 가 없는 것이 있으면 3, 아니면 0. 상태 칸은 사람이 쓰는 글이라
  「끝」 이라는 낱말이 있어도 실제로 끝났다는 보장은 아니다. 근거(커밋 · 경로)는 그 행을 직접 읽는다.
"""
import re
import sys
from pathlib import Path

WL = Path(__file__).resolve().parents[2] / "inbox/jay/20261028-plan/WORKLIST.md"
DONE = ("끝", "닫힘", "대체")


def rows():
    out = {}
    for line in WL.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^\| (W\d+) \|(.*)\|\s*$", line)
        if not m:
            continue
        cells = [c.strip() for c in m.group(2).split("|")]
        if len(cells) < 4:
            continue
        out[m.group(1)] = {"work": cells[0], "owner": cells[1], "before": cells[2], "state": cells[3]}
    return out


def main(argv):
    if len(argv) != 2 or not re.fullmatch(r"W\d+", argv[1]):
        print("usage: worklist_gate.py W<n>")
        return 2
    table = rows()
    w = argv[1]
    if w not in table:
        print(f"{w} 가 WORKLIST 표에 없다: {WL}")
        return 2
    me = table[w]
    print(f"{w} · {me['work'][:160]}")
    print(f"  상태: {me['state'][:200]}")
    before = re.findall(r"W\d+", me["before"])
    open_before = []
    print(f"  앞 일 칸: {me['before'] or '-'}")
    for b in before:
        st = table.get(b, {}).get("state", "(표에 없음)")
        ok = any(k in st for k in DONE)
        open_before.append(b) if not ok else None
        print(f"    {b} [{'끝' if ok else '열림'}] {st[:160]}")
    after = [k for k, r in table.items() if k != w and w in re.findall(r"W\d+", r["before"])]
    print("  뒤 일(이 일을 앞 일로 적은 것): " + (", ".join(after) if after else "없음"))
    for a in after:
        print(f"    {a} · {table[a]['work'][:120]} · {table[a]['state'][:80]}")
    if open_before:
        print(f"  막음: 앞 일 {', '.join(open_before)} 가 끝나지 않았다")
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
