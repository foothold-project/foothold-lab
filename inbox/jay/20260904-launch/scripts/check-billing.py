# -*- coding: utf-8 -*-
"""BILLING.md 안의 표들이 서로 맞는지 검산한다.

같은 돈을 네 가지로 나눠 적었다. 용도별 · 행선별 · 모델별 · 폐기내역이다.
넷이 다 원장 순 지출에 앉아야 한다. 한 곳을 고치고 다른 곳을 안 고치면 어긋난다.
실제로 두 번 어긋났다. 그래서 사람이 눈으로 보지 않고 이것으로 본다.

원장(`billing/transactions.json`)이 근거다. 문서가 아니라 원장이 기준이다.

쓰는 법
  python scripts/check-billing.py
"""
import json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, ".."))
DOC = os.path.join(ROOT, "BILLING.md")
LEDGER = os.path.join(ROOT, "billing", "transactions.json")
WASTE = 276.0                    # 성공했으나 안 쓴 것


def ledger_totals():
    d = json.load(open(LEDGER, encoding="utf-8"))
    spend = sum(-r["c"] for r in d if r["a"] == "spend")
    refund = sum(r["c"] for r in d if r["a"] == "refund")
    grant = sum(r["c"] for r in d if r["a"] == "grant")
    by = {}
    for r in d:
        if r["a"] in ("spend", "refund"):
            by[r["m"]] = by.get(r["m"], 0.0) - r["c"]
    return {"spend": spend, "refund": refund, "net": spend - refund,
            "grant": grant, "by_model": by}


def tables(text):
    """문서의 모든 표를 (머리글, 행들) 로 뽑는다."""
    out = []
    for block in re.findall(r"((?:^\|.*\|$\n)+)", text, re.M):
        lines = block.strip().splitlines()
        if len(lines) < 3:
            continue
        head = [c.strip().replace("*", "") for c in lines[0].strip("|").split("|")]
        rows = [[c.strip() for c in ln.strip("|").split("|")] for ln in lines[2:]]
        out.append((head, rows))
    return out


def pick(text, must_have, value_col, must_not_have=(), nth=0):
    """머리글에 `must_have` 가 다 들고 `must_not_have` 는 없는 표에서
    `value_col` 열을 (이름, 값) 으로 낸다. 같은 꼴이 여럿이면 `nth` 번째."""
    seen = 0
    for head, rows in tables(text):
        if not all(h in head for h in must_have) or value_col not in head:
            continue
        if any(h in head for h in must_not_have):
            continue
        i = head.index(value_col)
        out = []
        for r in rows:
            if len(r) <= i:
                continue
            cell = r[i].replace("*", "").replace(",", "").strip()
            if not re.fullmatch(r"-?\d+\.?\d*", cell):
                continue
            out.append((r[0].replace("*", "").strip(), float(cell)))
        if out:
            if seen == nth:
                return out
            seen += 1
    return []


def check(label, rows, want, tol=0.01):
    body = [(n, v) for n, v in rows if n != "합"]
    total = sum(v for _, v in body)
    stated = next((v for n, v in rows if n == "합"), None)
    ok = bool(body) and abs(total - want) < tol and (
        stated is None or abs(stated - want) < tol)
    print(f"  {label:<10} {len(body):2d}줄 합 {total:8.1f}"
          f"  적힌 합 {'-' if stated is None else format(stated, '.1f'):>7}"
          f"  기대 {want:8.1f}  {'통과' if ok else '**어긋난다**'}")
    return ok


def main():
    t = ledger_totals()
    doc = open(DOC, encoding="utf-8").read()
    print(f"원장  지급 {t['grant']:.1f} · 과금 {t['spend']:.1f} · 환불 {t['refund']:.1f}"
          f" · 순 지출 {t['net']:.1f} · 남은 것 {t['grant'] - t['net']:.1f}")
    print()
    ok = True
    ok &= check("용도별", pick(doc, ["무엇", "비중", "쓰였나"], "크레딧"), t["net"])
    ok &= check("행선별", pick(doc, ["크레딧", "비중"], "크레딧",
                              must_not_have=("무엇", "쓰였나")), t["net"])
    ok &= check("모델별", pick(doc, ["모델", "건수", "단가"], "순 지출"), t["net"])
    ok &= check("폐기내역", pick(doc, ["성격"], "크레딧"), WASTE)
    print()
    rows = pick(doc, ["모델", "건수", "단가"], "순 지출")
    for m, want in sorted(t["by_model"].items()):
        got = next((v for n, v in rows if n.split()[0] in m), None)
        good = got is not None and abs(got - want) < 0.01
        ok &= good
        print(f"  {m:<24} 문서 {'-' if got is None else format(got, '.1f'):>7}"
              f"  원장 {want:7.1f}  {'통과' if good else '**어긋난다**'}")
    print()
    for pat, want, what in [
            (r"지금 잔액\*{0,2} \| \*{0,2}([\d.]+)", t["grant"] - t["net"], "지금 잔액"),
            (r"순 지출\*{0,2} \| \*{0,2}-([\d.]+)", t["net"], "순 지출"),
            (r"작업 시작 잔액\*{0,2} \| \*{0,2}([\d.]+)", t["grant"], "시작 잔액")]:
        m = re.search(pat, doc)
        good = m is not None and abs(float(m.group(1)) - want) < 0.01
        ok &= good
        print(f"  {what:<10} 문서 {'못 찾음' if not m else m.group(1):>8}"
              f"  기대 {want:8.1f}  {'통과' if good else '**어긋난다**'}")
    print()
    print("모두 맞는다" if ok else "어긋나는 곳이 있다")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
