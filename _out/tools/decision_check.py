"""Warn when a question or a "to decide" list touches a decision the lead already made (lead, 10/28).

Decisions live in inbox/jay/20261028-plan/WORKLIST.md under "## 확정" as lines
  - D01 <decision text> · 키워드: word1 | word2 | word3
Usage:
  python _out/tools/decision_check.py                 # list the decisions
  python _out/tools/decision_check.py --text "..."    # check a draft question before sending it
  python _out/tools/decision_check.py --file f.md     # check a document (e.g. a "정할 것" section)
Exit 1 when a draft hits a closed decision. It matches words, not meaning: a hit means "read D?? before asking",
and no hit does not prove the question is new.
Keywordless decisions use exact body tokens (at least two shared tokens,
including one word). This fallback is a warning, not semantic agreement.
"""
import argparse
import pathlib
import re
import sys

root = pathlib.Path(__file__).resolve().parents[2]
worklist = root / "inbox/jay/20261028-plan/WORKLIST.md"
line_re = re.compile(r"^- (D\d+) (.*?)(?: · 키워드: (.*))?$")
decisions = []
section = False
for line in worklist.read_text(encoding="utf-8").splitlines():
    if line.startswith("## "):
        section = line.strip() == "## 확정"
        continue
    m = line_re.match(line.strip()) if section else None
    if m:
        words = [w.strip() for w in (m.group(3) or "").split("|") if w.strip()]
        decisions.append((m.group(1), m.group(2), words))

ap = argparse.ArgumentParser()
ap.add_argument("--text")
ap.add_argument("--file", type=pathlib.Path)
a = ap.parse_args()
draft = a.text if a.text is not None else (a.file.read_text(encoding="utf-8") if a.file else None)
if draft is None:
    for did, text, words in decisions:
        print(f"{did} {text}  [키워드 {len(words)}]")
    sys.exit(0)
if not decisions:
    print("ERROR: 확정 결정 목록이 비었다")
    sys.exit(2)


def tokens(text):
    # Keep technical words, Korean words and compound numeric bounds.
    return set(re.findall(r"[가-힣a-z_]{2,}|\d+(?:[./]\d+)*", text.lower())) - {
        "한다", "것은", "있는", "확정", "팀장", "결정", "정정", "가정", "기준", "유지"}


hits = []
for did, text, words in decisions:
    found = [w for w in words if w.lower() in draft.lower()]
    if re.search(r"(?<!\w)" + re.escape(did) + r"(?!\w)", draft, re.I):
        found.append(did)
    if not words:
        shared = tokens(text) & tokens(draft)
        if len(shared) >= 2 and any(re.search(r"[가-힣a-z_]", w) for w in shared):
            found += ["본문:" + w for w in sorted(shared)]
    if found:
        hits.append((did, text, found))
for did, text, found in hits:
    print(f"HIT {did}: {text}\n    맞은 단어: {', '.join(found)}")
print(f"decisions {len(decisions)} · hits {len(hits)}")
sys.exit(1 if hits else 0)
