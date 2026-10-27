"""Count open R items in the plan cards (lead, 10/28). Exit 1 if any R is open, 0 if all are ticked.

Usage: python _out/tools/worklist_check.py [plan_dir]
An R item is a markdown checkbox line that starts with "- [ ] R" (open) or "- [x] R" (done).
"""
import pathlib
import re
import sys

root = pathlib.Path(__file__).resolve().parents[2]
plan = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else root / "inbox/jay/20261028-plan"
box = re.compile(r"^- \[( |x)\] (R\d+-\d+)\s*(.*)$")
total_open = 0
for card in sorted(plan.glob("*.md")):
    open_items, done = [], 0
    for line in card.read_text(encoding="utf-8").splitlines():
        m = box.match(line.strip())
        if not m:
            continue
        if m.group(1) == "x":
            done += 1
        else:
            open_items.append(f"{m.group(2)} {m.group(3)[:60]}")
    if open_items or done:
        print(f"{card.name}: open {len(open_items)} · done {done}")
        for item in open_items:
            print(f"  {item}")
    total_open += len(open_items)
print(f"TOTAL open {total_open}")
sys.exit(1 if total_open else 0)
