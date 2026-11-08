"""Check open R items and every closed item's local evidence. Exit 1 on either failure.

Usage: python _out/tools/worklist_check.py [plan_dir]
An R item is a markdown checkbox line that starts with "- [ ] R" (open) or "- [x] R" (done).
"""
import pathlib
import re
import sys
from evidence_check import check_evidence

root = pathlib.Path(__file__).resolve().parents[2]
plan = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else root / "inbox/jay/20261028-plan"
box = re.compile(r"^- \[( |x)\] (R\d+-\d+)\s*(.*)$")
total_open = 0
invalid = 0
cards = sorted(plan.glob("*.md")) if plan.is_dir() else []
if not cards:
    print(f"ERROR: 검사할 Markdown 없음: {plan}")
    sys.exit(2)
for card in cards:
    open_items, done = [], 0
    for lineno, line in enumerate(card.read_text(encoding="utf-8").splitlines(), 1):
        m = box.match(line.strip())
        if not m:
            continue
        if m.group(1) == "x":
            done += 1
            _, errors = check_evidence(m.group(3), card, root)
            if errors:
                invalid += 1
                print(f"INVALID {card.name}:{lineno} {m.group(2)}: {'; '.join(errors)}")
        else:
            open_items.append(f"{m.group(2)} {m.group(3)[:60]}")
    if open_items or done:
        print(f"{card.name}: open {len(open_items)} · done {done}")
        for item in open_items:
            print(f"  {item}")
    total_open += len(open_items)
print(f"TOTAL open {total_open} · invalid_done {invalid}")
sys.exit(1 if total_open or invalid else 0)
