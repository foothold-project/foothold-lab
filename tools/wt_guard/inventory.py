"""작업 사본 재고 (D138): 모든 worktree · 사본의 자리 · 크기 · 마지막 쓰기 · 미커밋 · 원격 존재.

한 줄 요약(매시간 점검에 붙임)과 JSON · 표를 낸다. 대상 = 주어진 저장소의 `git worktree list` 전부
+ 설정 MAI_WT_SCAN_ROOTS(기본 D:/mai-wt;C:/mai/wt) 아래 깊이 2 까지의 .git 이 있는 폴더.

분류(설정값):
  outside_root      : MAI_WT_ROOT 밖에 있는 사본(주 체크아웃은 뺀다)
  new_outside       : outside_root 이고 만들어진 시각이 MAI_WT_NEW_SINCE(D138 시각) 뒤 → 「C 쪽 새 사본」
  archive_candidate : 미커밋 0 · HEAD 가 원격 가지에 들어 있음(push 됨) · MAI_WT_IDLE_DAYS 동안 안 씀

사용:
  python tools/wt_guard/inventory.py [--repo <경로>]... [--no-size] [--json <파일>] [--table] [--now <ISO>]
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parent))
import wt_config  # noqa: E402

GB = 1_000_000_000
GIT_TIMEOUT_S = 180


_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0) if wt_config.IS_WINDOWS else 0


def git(args: Sequence[str], cwd: str | Path, timeout: int = GIT_TIMEOUT_S) -> tuple[int, str]:
    """git 을 묻지 않게(stdin 닫음 · 터미널 프롬프트 끔 · Windows 는 창 없이) 부른다."""
    env = dict(os.environ, GIT_TERMINAL_PROMPT="0", GIT_OPTIONAL_LOCKS="0")
    try:
        cp = subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True,
                            encoding="utf-8", errors="replace", timeout=timeout,
                            stdin=subprocess.DEVNULL, env=env, creationflags=_NO_WINDOW)
        return cp.returncode, cp.stdout.strip()
    except (OSError, subprocess.TimeoutExpired) as exc:
        return 255, f"{type(exc).__name__}: {exc}"


def list_worktrees(repo: str | Path) -> list[dict]:
    rc, out = git(["worktree", "list", "--porcelain"], repo)
    if rc != 0:
        return []
    items: list[dict] = []
    cur: dict | None = None
    for line in out.splitlines() + [""]:
        if not line:
            if cur:
                items.append(cur)
            cur = None
            continue
        key, _, val = line.partition(" ")
        if key == "worktree":
            cur = {"path": val, "prunable": False, "detached": False, "branch": None}
        elif cur is None:
            continue
        elif key == "branch":
            cur["branch"] = val.replace("refs/heads/", "", 1)
        elif key == "detached":
            cur["detached"] = True
        elif key == "prunable":
            cur["prunable"] = True
    return items


def scan_roots(roots: Iterable[str], max_depth: int = 2) -> list[str]:
    found: list[str] = []

    def walk(d: Path, depth: int) -> None:
        try:
            entries = list(os.scandir(d))
        except OSError:
            return
        names = {e.name for e in entries}
        if ".git" in names:
            found.append(str(d).replace("\\", "/"))
            return
        if depth >= max_depth:
            return
        for e in entries:
            try:
                if e.is_dir(follow_symlinks=False):
                    walk(Path(e.path), depth + 1)
            except OSError:
                continue

    for r in roots:
        p = Path(r)
        if p.is_dir():
            walk(p, 0)
    return found


def walk_size(path: str | Path) -> tuple[int, int, float]:
    """(파일 수, 바이트, 가장 늦은 mtime). .git 폴더는 뺀다. scandir 의 stat 캐시를 써서 빠르다."""
    files = 0
    size = 0
    latest = 0.0
    stack = [str(path)]
    while stack:
        d = stack.pop()
        try:
            with os.scandir(d) as it:
                for e in it:
                    try:
                        if e.is_dir(follow_symlinks=False):
                            if e.name == ".git":
                                continue
                            stack.append(e.path)
                        else:
                            st = e.stat(follow_symlinks=False)
                            files += 1
                            size += st.st_size
                            if st.st_mtime > latest:
                                latest = st.st_mtime
                    except OSError:
                        continue
        except OSError:
            continue
    return files, size, latest


def iso(ts: float | None) -> str | None:
    if not ts:
        return None
    return datetime.fromtimestamp(ts, tz=timezone.utc).astimezone(wt_config.KST).isoformat(timespec="seconds")


def created_at(path: Path) -> tuple[float | None, str]:
    """사본이 생긴 시각과 출처. .git 항목의 생성 시각(Windows st_ctime · birthtime 있는 파일 시스템),
    없으면 HEAD reflog 의 첫 항목 시각(worktree add · clone 때 적힘)."""
    try:
        st = (path / ".git").stat()
    except OSError:
        st = None
    if st is not None:
        bt = getattr(st, "st_birthtime", None)
        if bt:
            return float(bt), "birthtime"
        if wt_config.IS_WINDOWS:
            return float(st.st_ctime), "ctime"
    rc, out = git(["log", "-g", "--format=%ct", "HEAD"], path)
    if rc == 0 and out.strip():
        try:
            return float(out.strip().splitlines()[-1]), "reflog"
        except ValueError:
            pass
    return None, "unknown"


def git_activity(path: Path) -> float | None:
    """마지막 git 활동: 사본의 git dir 에 있는 index · HEAD · logs/HEAD 의 mtime 최대."""
    rc, gd = git(["rev-parse", "--path-format=absolute", "--git-dir"], path)
    if rc != 0:
        return None
    latest = 0.0
    for name in ("index", "HEAD", "logs/HEAD"):
        try:
            latest = max(latest, (Path(gd) / name).stat().st_mtime)
        except OSError:
            continue
    return latest or None


def describe(path: str, cfg: wt_config.Config, *, now: datetime, with_size: bool = True,
             main_toplevel: str | None = None, wt: dict | None = None) -> dict:
    p = Path(path)
    row: dict = {
        "path": path.replace("\\", "/"), "real_path": None, "exists": p.is_dir(), "is_main": False,
        "branch": None, "head": None, "detached": None, "prunable": bool(wt and wt.get("prunable")),
        "upstream": None, "remote_branch_exists": None, "pushed": None,
        "uncommitted": None, "untracked": None, "ignored": None,
        "files": None, "size_bytes": None, "size_gb": None,
        "last_write": None, "last_git_activity": None, "created_at": None, "created_at_source": None,
        "outside_root": None, "new_outside": None, "archive_candidate": None, "notes": [],
    }
    if not row["exists"]:
        row["notes"].append("폴더 없음(prunable)")
        return row
    row["real_path"] = os.path.realpath(path).replace("\\", "/")
    row["is_main"] = bool(main_toplevel) and wt_config.norm_path(row["real_path"]) == wt_config.norm_path(
        os.path.realpath(main_toplevel))
    rc, head = git(["rev-parse", "--short", "HEAD"], p)
    row["head"] = head if rc == 0 else None
    rc, br = git(["symbolic-ref", "--short", "-q", "HEAD"], p)
    row["branch"] = br if rc == 0 and br else None
    row["detached"] = row["branch"] is None
    if row["branch"]:
        rc, up = git(["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"], p)
        row["upstream"] = up if rc == 0 else None
        rc, _ = git(["rev-parse", "--verify", "-q", f"refs/remotes/origin/{row['branch']}"], p)
        row["remote_branch_exists"] = rc == 0
    rc, contains = git(["branch", "-r", "--contains", "HEAD", "--format=%(refname:short)"], p)
    row["pushed"] = (rc == 0 and bool(contains.strip()))
    rc, st = git(["--no-optional-locks", "status", "--porcelain", "--untracked-files=normal", "--ignored=matching"], p)
    if rc == 0:
        lines = [ln for ln in st.splitlines() if ln.strip()]
        row["untracked"] = sum(1 for ln in lines if ln.startswith("??"))
        row["ignored"] = sum(1 for ln in lines if ln.startswith("!!"))  # 무시된 산출물도 센다(보관 후보 오판 방지)
        row["uncommitted"] = len(lines) - row["untracked"] - row["ignored"]
    else:
        row["notes"].append(f"git status 실패: {st[:80]}")
    if with_size:
        files, size, latest = walk_size(p)
        row["files"], row["size_bytes"], row["size_gb"] = files, size, round(size / GB, 2)
        row["last_write"] = iso(latest)
    act = git_activity(p)
    row["last_git_activity"] = iso(act)
    created, source = created_at(p)
    row["created_at"] = iso(created)
    row["created_at_source"] = source
    classify(row, cfg, now=now)
    return row


def classify(row: dict, cfg: wt_config.Config, *, now: datetime) -> dict:
    """순수 함수: outside_root · new_outside · archive_candidate 를 채운다(시험에서 직접 부른다)."""
    if row.get("is_main"):
        row["outside_root"] = False
        row["new_outside"] = False
        row["archive_candidate"] = False
        return row
    root_real = os.path.realpath(cfg.wt_root) if os.path.isdir(cfg.wt_root) else cfg.wt_root
    row["outside_root"] = not wt_config.is_under(row.get("real_path") or row["path"], root_real)
    created = row.get("created_at")
    if not row["outside_root"]:
        row["new_outside"] = False
    elif created is None:
        row["new_outside"] = None
    else:
        row["new_outside"] = wt_config.parse_when(created) >= cfg.new_since
    stamps = [s for s in (row.get("last_write"), row.get("last_git_activity")) if s]
    last = max(stamps) if stamps else None
    # 깨끗 = 변경 0 · 미추적 0 · 무시된 산출물 0 (무시 파일이 있으면 사람이 보고 보관)
    clean = row.get("uncommitted") == 0 and row.get("untracked") == 0 and (row.get("ignored") or 0) == 0
    pushed = row.get("pushed") is True
    idle = last is not None and (now - wt_config.parse_when(last)) >= timedelta(days=cfg.idle_days)
    row["archive_candidate"] = bool(clean and pushed and idle)
    return row


def disk_rows(cfg: wt_config.Config) -> list[dict]:
    rows = []
    for p in cfg.disk_paths:
        try:
            u = shutil.disk_usage(p)
            rows.append({"path": p, "free_gb": round(u.free / GB, 1), "total_gb": round(u.total / GB, 1)})
        except OSError as exc:
            rows.append({"path": p, "free_gb": None, "error": str(exc)})
    return rows


def summarize(rows: Sequence[dict], disks: Sequence[dict], cfg: wt_config.Config, *, now: datetime) -> str:
    present = [r for r in rows if r["exists"]]
    missing = [r for r in rows if not r["exists"]]
    inside = [r for r in present if r["outside_root"] is False and not r["is_main"]]
    outside = [r for r in present if r["outside_root"]]
    new_out = [r for r in outside if r["new_outside"]]
    new_unknown = [r for r in outside if r["new_outside"] is None]
    arch = [r for r in present if r["archive_candidate"]]
    dirty = [r for r in present if (r["uncommitted"] or 0) + (r["untracked"] or 0) + (r["ignored"] or 0) > 0]
    sized = [r for r in present if r["size_bytes"] is not None]
    size_txt = f"{sum(r['size_bytes'] for r in sized) / GB:.0f} GB" if sized else "크기 미측"
    names = ", ".join(Path(r["path"]).name for r in new_out[:5])
    if len(new_out) > 5:
        names += f" 외 {len(new_out) - 5}"
    disk_txt = " · ".join(
        f"{d['path']} {d['free_gb']:.0f} GB" if d.get("free_gb") is not None else f"{d['path']} 미측" for d in disks)
    unk = f"(생성 시각 미확인 {len(new_unknown)})" if new_unknown else ""
    return (f"wt_guard 재고 {now.astimezone(wt_config.KST):%m/%d %H:%M} · 사본 {len(present)}"
            f"(뿌리 안 {len(inside)} · 밖 {len(outside)} · 폴더 없음 {len(missing)}) · 합 {size_txt}"
            f" · 뿌리 밖 새 사본 {len(new_out)}{unk}{(' [' + names + ']') if names else ''}"
            f" · 보관 후보 {len(arch)} · 미커밋 있음 {len(dirty)} · 여유 {disk_txt}")


def table(rows: Sequence[dict]) -> str:
    hdr = "| 사본 | 브랜치 | 크기 GB | 마지막 쓰기 | 미커밋/미추적/무시 | push | 뿌리 밖 | 새 | 보관 후보 |"
    sep = "|---|---|---|---|---|---|---|---|---|"
    out = [hdr, sep]
    for r in rows:
        if not r["exists"]:
            out.append(f"| {r['path']} | (폴더 없음) | | | | | | | |")
            continue
        out.append("| {p} | {b} | {s} | {w} | {u}/{t}/{i} | {ps} | {o} | {n} | {a} |".format(
            p=r["path"], b=r["branch"] or f"(detached {r['head']})",
            s="" if r["size_gb"] is None else f"{r['size_gb']:.2f}",
            w=(r["last_write"] or r["last_git_activity"] or "")[:16],
            u=r["uncommitted"], t=r["untracked"], i=r["ignored"], ps={True: "예", False: "아니오", None: "?"}[r["pushed"]],
            o="예" if r["outside_root"] else "", n={True: "예", False: "", None: "?"}[r["new_outside"]],
            a="예" if r["archive_candidate"] else ""))
    return "\n".join(out)


def collect(repos: Sequence[str], cfg: wt_config.Config, *, now: datetime, with_size: bool = True,
            scan: bool = True) -> list[dict]:
    seen: dict[str, dict | None] = {}
    main_tops: dict[str, str] = {}
    for repo in repos:
        rc, top = git(["rev-parse", "--show-toplevel"], repo)
        if rc != 0:
            continue
        rc, common = git(["rev-parse", "--path-format=absolute", "--git-common-dir"], repo)
        main_top = str(Path(common).parent).replace("\\", "/") if rc == 0 and common.endswith(".git") else top
        for wt in list_worktrees(repo):
            key = wt_config.norm_path(wt["path"])
            if key not in seen:
                seen[key] = wt
                main_tops[key] = main_top
    if scan:
        for p in scan_roots(cfg.scan_roots):
            key = wt_config.norm_path(p)
            if key not in seen:
                seen[key] = {"path": p, "prunable": False}
                main_tops[key] = ""
    rows = []
    for key, wt in seen.items():
        rows.append(describe(wt["path"], cfg, now=now, with_size=with_size,
                             main_toplevel=main_tops.get(key) or None, wt=wt))
    rows.sort(key=lambda r: (not r["exists"], r["path"].lower()))
    return rows


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="작업 사본 재고 (D138)")
    ap.add_argument("--repo", action="append", default=None, help="worktree 를 셀 저장소(여러 번 가능, 기본 현재 폴더)")
    ap.add_argument("--no-size", action="store_true", help="크기 · 마지막 쓰기 걷기 생략")
    ap.add_argument("--no-scan", action="store_true", help="MAI_WT_SCAN_ROOTS 훑기 생략")
    ap.add_argument("--json", default=None, help="JSON 을 쓸 파일")
    ap.add_argument("--table", action="store_true", help="표도 출력")
    ap.add_argument("--now", default=None, help="기준 시각 ISO(시험용)")
    a = ap.parse_args(argv)
    cfg = wt_config.load()
    now = wt_config.parse_when(a.now) if a.now else datetime.now(tz=wt_config.KST)
    rows = collect(a.repo or ["."], cfg, now=now, with_size=not a.no_size, scan=not a.no_scan)
    disks = disk_rows(cfg)
    line = summarize(rows, disks, cfg, now=now)
    if a.json:
        Path(a.json).parent.mkdir(parents=True, exist_ok=True)
        Path(a.json).write_text(json.dumps({"schema": "wt-guard-inventory/1", "at": now.isoformat(timespec="seconds"),
                                            "wt_root": cfg.wt_root, "summary": line, "disks": disks, "rows": rows},
                                           ensure_ascii=False, indent=1), encoding="utf-8")
    print(line)
    if a.table:
        print(table(rows))
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
        sys.stderr.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    except Exception:
        pass
    raise SystemExit(main())
