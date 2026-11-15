"""W 하나를 시작하기 전에 앞 일과 뒤 일을 WORKLIST 표에서 읽어 보인다 (팀장 10/29 23:4x: 메모리가 아니라 표로).

쓰는 법: python _out/tools/worklist_gate.py W58
- 앞 일: 그 W 의 「앞 일」 칸에 적힌 W 번호들과 그 상태.
- 뒤 일: 「앞 일」 칸에 그 W 를 적은 다른 W 들(이 일이 끝나면 걸어야 할 것).
- 종료 코드: 앞 일이 끝/닫힘/대체로 시작하지 않거나 증거 경로/커밋이 미확인일 때 3.
  증거 존재는 완료 내용의 진실성이나 실행 승인을 뜻하지 않는다. 증거는 상태 칸에 적는다.
"""
import re
import sys
from pathlib import Path
from evidence_check import check_evidence

WL = Path(__file__).resolve().parents[2] / "inbox/jay/20261028-plan/WORKLIST.md"
ROOT = Path(__file__).resolve().parents[2]
DONE = re.compile(r"^(?:끝|닫힘|대체)(?=$|[\s(·:])")


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
        ok = bool(DONE.match(st)) and not re.match(r'^(?:끝|닫힘|대체)\s*(?:아님|아니|안\s|못\s)', st)
        _, errors = check_evidence(st, WL, ROOT) if ok else (0, ['NOT_CLOSED'])
        ok = ok and not errors
        open_before.append(b) if not ok else None
        print(f"    {b} [{'증거 존재 확인' if ok else '미확인'}] {st[:160]}")
        for error in errors:
            print(f"      {error}")
    if not before and me['before'] not in ('', '-', '없음'):
        open_before.append(me['before'])
        print('    UNRESOLVED_PREREQUISITE: W 번호 없는 앞 일은 자동 확인 불가')
    after = [k for k, r in table.items() if k != w and w in re.findall(r"W\d+", r["before"])]
    print("  뒤 일(이 일을 앞 일로 적은 것): " + (", ".join(after) if after else "없음"))
    for a in after:
        print(f"    {a} · {table[a]['work'][:120]} · {table[a]['state'][:80]}")
    if open_before:
        print(f"  막음: 앞 일 {', '.join(open_before)} 완료 상태·증거 검증 미통과")
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
