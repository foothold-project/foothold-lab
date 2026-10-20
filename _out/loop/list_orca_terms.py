# -*- coding: utf-8 -*-
"""Orca 터미널 목록을 「어느 워크스페이스 · 무슨 에이전트」로 편다.

분류: 운영
작성: 오흥재 · 2026-09-28
근거: codex 업데이트가 EBUSY 로 막힌다. 어느 세션을 닫아도 되는지 팀장이
      고르려면 「pid」가 아니라 「어느 워크스페이스의 무엇인가」가 필요하다.
요지: `orca terminal list --json` 을 읽어 워크스페이스별로 묶어 보여 준다.

돌리는 법
    orca terminal list --json > f.json && python _out/loop/list_orca_terms.py f.json
"""

from __future__ import annotations

import io
import json
import sys


def walk(node, out):
    """어떤 모양으로 오더라도 터미널처럼 보이는 dict 를 모은다."""
    if isinstance(node, dict):
        keys = set(node)
        if ("handle" in keys or "id" in keys) and (
            "title" in keys or "worktreePath" in keys or "cwd" in keys
        ):
            out.append(node)
        for v in node.values():
            walk(v, out)
    elif isinstance(node, list):
        for v in node:
            walk(v, out)


def main() -> int:
    path = sys.argv[1] if len(sys.argv) > 1 else None
    raw = io.open(path, encoding="utf-8").read() if path else sys.stdin.read()
    d = json.loads(raw)

    terms = []
    walk(d, terms)
    # 중복 제거
    seen, uniq = set(), []
    for t in terms:
        k = t.get("handle") or t.get("id")
        if k in seen:
            continue
        seen.add(k)
        uniq.append(t)

    print("터미널 %d 개" % len(uniq))
    print()

    groups = {}
    for t in uniq:
        wt = t.get("worktreePath") or t.get("worktree") or t.get("cwd") or "?"
        if isinstance(wt, dict):
            wt = wt.get("path", "?")
        wt = str(wt)
        for pre in ("C:/Users/AI-WS01/orca/workspaces/",
                    "C:\\Users\\AI-WS01\\orca\\workspaces\\"):
            if wt.startswith(pre):
                wt = wt[len(pre):]
        groups.setdefault(wt, []).append(t)

    for wt in sorted(groups):
        print("=== %s ===" % wt[:74])
        for t in groups[wt]:
            print("   %-30s | %-12s | %s" % (
                str(t.get("title", ""))[:30],
                str(t.get("agent") or t.get("kind") or "")[:12],
                str(t.get("handle") or t.get("id") or "")[:34],
            ))
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
