"""경로별 디스크 여유 관문 (D138).

문턱은 설정(기본 경고 100 GB · 막음 50 GB, GB = 10^9 바이트) 또는 인자. 시작 스크립트 · 촬영 대기열이
함수로 부르거나(check · require_free) CLI 로 부른다.

    from tools.wt_guard.disk_guard import require_free, DiskGuardError
    require_free(["D:/mai-tmp/runner"])            # 막음이면 DiskGuardError, 경고면 stderr 한 줄

CLI 종료 코드: 0 = 전부 ok 또는 warn(경고는 stderr) · 2 = block 하나라도 · 3 = 경로를 잴 수 없음(unknown).
--strict 를 주면 warn 도 1 로 끝낸다.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path
from typing import Callable, Iterable, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parent))
import wt_config  # noqa: E402

GB = 1_000_000_000
LEVEL_ORDER = {"ok": 0, "warn": 1, "block": 2, "unknown": 3}


class DiskGuardError(RuntimeError):
    """막음 문턱 아래(또는 잴 수 없음)일 때."""

    def __init__(self, results: list[dict]) -> None:
        self.results = results
        super().__init__(summary_line(results))


def validate_thresholds(warn_gb: float, block_gb: float) -> None:
    if warn_gb < 0 or block_gb < 0:
        raise ValueError(f"문턱은 0 이상이어야 합니다: warn {warn_gb} · block {block_gb}")
    if block_gb >= warn_gb:
        raise ValueError(f"막음 문턱은 경고 문턱보다 작아야 합니다: warn {warn_gb} · block {block_gb}")


def check(paths: Iterable[str] | None = None, warn_gb: float | None = None, block_gb: float | None = None,
          *, usage_fn: Callable = shutil.disk_usage, config: wt_config.Config | None = None) -> list[dict]:
    """경로마다 {path, free_gb, total_gb, level, warn_gb, block_gb, error}. level: ok · warn · block · unknown."""
    cfg = config or wt_config.load()
    warn = cfg.warn_gb if warn_gb is None else float(warn_gb)
    block = cfg.block_gb if block_gb is None else float(block_gb)
    validate_thresholds(warn, block)
    paths = list(paths) if paths is not None else list(cfg.disk_paths)
    if not paths:
        raise ValueError("볼 경로가 없습니다")
    out: list[dict] = []
    for p in paths:
        row = {"path": p, "free_gb": None, "total_gb": None, "level": "unknown",
               "warn_gb": warn, "block_gb": block, "error": None}
        try:
            u = usage_fn(p)
            free_gb = u.free / GB
            row["free_gb"] = round(free_gb, 1)
            row["total_gb"] = round(u.total / GB, 1)
            if free_gb < block:
                row["level"] = "block"
            elif free_gb < warn:
                row["level"] = "warn"
            else:
                row["level"] = "ok"
        except (OSError, ValueError, AttributeError) as exc:
            row["error"] = f"{type(exc).__name__}: {exc}"
        out.append(row)
    return out


def worst(results: Sequence[dict]) -> str:
    return max((r["level"] for r in results), key=lambda lv: LEVEL_ORDER[lv], default="unknown")


def summary_line(results: Sequence[dict]) -> str:
    if not results:
        return "여유: 잰 경로 없음"
    parts = []
    for r in results:
        if r["free_gb"] is None:
            parts.append(f"{r['path']} 미측({r['error']})")
        else:
            parts.append(f"{r['path']} {r['free_gb']:.0f} GB {r['level']}")
    w, b = results[0]["warn_gb"], results[0]["block_gb"]
    return "여유 " + " · ".join(parts) + f" (경고 {w:g} · 막음 {b:g} GB)"


def require_free(paths: Iterable[str] | None = None, warn_gb: float | None = None, block_gb: float | None = None,
                 *, strict: bool = False, usage_fn: Callable = shutil.disk_usage,
                 config: wt_config.Config | None = None, stream=None) -> list[dict]:
    """block · unknown 이면 DiskGuardError. warn 은 stderr 한 줄(strict 면 예외). 결과 목록을 돌려준다."""
    results = check(paths, warn_gb, block_gb, usage_fn=usage_fn, config=config)
    lv = worst(results)
    if lv in ("block", "unknown") or (strict and lv == "warn"):
        raise DiskGuardError(results)
    if lv == "warn":
        print("disk_guard 경고: " + summary_line(results), file=stream or sys.stderr)
    return results


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="경로별 디스크 여유 관문 (D138)")
    ap.add_argument("paths", nargs="*", help="볼 경로(없으면 설정 MAI_DISK_PATHS)")
    ap.add_argument("--warn-gb", type=float, default=None)
    ap.add_argument("--block-gb", type=float, default=None)
    ap.add_argument("--strict", action="store_true", help="warn 도 종료 1")
    ap.add_argument("--json", action="store_true", help="JSON 출력")
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args(argv)
    try:
        results = check(a.paths or None, a.warn_gb, a.block_gb)
    except ValueError as exc:
        print(f"disk_guard 설정 오류: {exc}", file=sys.stderr)
        return 3
    lv = worst(results)
    if a.json:
        print(json.dumps({"worst": lv, "results": results}, ensure_ascii=False))
    elif not a.quiet:
        print(summary_line(results))
    if lv == "block":
        return 2
    if lv == "unknown":
        return 3
    if lv == "warn" and a.strict:
        return 1
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
        sys.stderr.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    except Exception:
        pass
    raise SystemExit(main())
