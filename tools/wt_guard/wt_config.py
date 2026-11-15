"""wt_guard 설정 읽기 (D138).

우선순위: 환경 변수 > 사용자 파일(~/.mai/wt_guard.env 또는 $MAI_WT_GUARD_CONFIG)
        > tools/wt_guard/wt_guard.default.env > 내장값.
파일 꼴은 KEY=VALUE 한 줄씩(bash 훅 post-checkout 과 같은 파일을 읽는다).
OS 별 값은 KEY_WINDOWS · KEY_LINUX 로 적고, 꼬리 없는 KEY 가 있으면 그것이 이긴다.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Mapping

HERE = Path(__file__).resolve().parent
DEFAULT_FILE = HERE / "wt_guard.default.env"
IS_WINDOWS = os.name == "nt"
OS_SUFFIX = "_WINDOWS" if IS_WINDOWS else "_LINUX"
KST = timezone(timedelta(hours=9))

BUILTIN = {
    "MAI_WT_ROOT": "D:/mai-wt" if IS_WINDOWS else "/data/mai-wt",
    "MAI_TMP_ROOT": "D:/mai-tmp" if IS_WINDOWS else "/data/mai-tmp",
    "MAI_WT_ALERT_DIR": "D:/mai-tmp/wt_guard/alerts" if IS_WINDOWS else "/data/mai-tmp/wt_guard/alerts",
    "MAI_WT_SCAN_ROOTS": "D:/mai-wt;C:/mai/wt" if IS_WINDOWS else "/data/mai-wt",
    "MAI_DISK_PATHS": "C:/;D:/" if IS_WINDOWS else "/;/data",
    "MAI_DISK_WARN_GB": "100",
    "MAI_DISK_BLOCK_GB": "50",
    "MAI_WT_IDLE_DAYS": "7",
    "MAI_WT_NEW_SINCE": "2026-11-02T17:00:00+09:00",
    "MAI_WT_NOTIFY": "1",
    "MAI_WT_NOTIFY_RUN": "",
    "MAI_WT_NOTIFY_TO": "",
}


def read_env_file(path: Path | str | None) -> dict[str, str]:
    """KEY=VALUE 파일을 읽는다. 없으면 빈 dict. 주석 · 빈 줄 · 이상한 키는 건너뛴다."""
    out: dict[str, str] = {}
    if not path:
        return out
    p = Path(path)
    if not p.is_file():
        return out
    for raw in p.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.rstrip("\r")
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        key = key.strip()
        if not key or not all(c.isalnum() or c == "_" for c in key):
            continue
        out[key] = val
    return out


def user_file_path(env: Mapping[str, str]) -> Path:
    explicit = env.get("MAI_WT_GUARD_CONFIG")
    if explicit:
        return Path(explicit)
    home = env.get("HOME") or env.get("USERPROFILE") or str(Path.home())
    return Path(home) / ".mai" / "wt_guard.env"


def resolve(env: Mapping[str, str] | None = None, *, user_file: Path | str | None = None,
            default_file: Path | str | None = DEFAULT_FILE) -> dict[str, str]:
    """세 층을 합친 평평한 dict. 뒤에 넣는 쪽이 이긴다: 기본 파일 → 사용자 파일 → 환경 변수."""
    env = dict(os.environ) if env is None else dict(env)
    merged: dict[str, str] = {}
    merged.update(read_env_file(default_file))
    merged.update(read_env_file(user_file if user_file is not None else user_file_path(env)))
    merged.update({k: v for k, v in env.items() if k.startswith("MAI_")})
    return merged


def pick(merged: Mapping[str, str], key: str) -> str:
    """KEY → KEY_<OS> → 내장값 순으로 첫 비어 있지 않은 값."""
    for k in (key, key + OS_SUFFIX):
        v = merged.get(k)
        if v is not None and v != "":
            return v
    return BUILTIN.get(key, "")


def norm_path(p: str | Path) -> str:
    """비교용 경로: 슬래시 통일 · 끝 슬래시 제거 · Windows 는 소문자."""
    s = str(p).replace("\\", "/")
    while len(s) > 1 and s.endswith("/") and not s.endswith(":/"):
        s = s[:-1]
    if s.endswith(":/"):
        s = s[:-1]
    if IS_WINDOWS:
        s = s.lower()
    return s


def is_under(path: str | Path, root: str | Path) -> bool:
    a = norm_path(path) + "/"
    r = norm_path(root) + "/"
    return a.startswith(r)


def split_list(value: str) -> list[str]:
    return [x.strip() for x in value.split(";") if x.strip()]


def parse_when(value: str) -> datetime:
    dt = datetime.fromisoformat(value.strip())
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=KST)
    return dt


@dataclass
class Config:
    wt_root: str
    tmp_root: str
    alert_dir: str
    scan_roots: list[str]
    disk_paths: list[str]
    warn_gb: float
    block_gb: float
    idle_days: int
    new_since: datetime
    notify: bool
    notify_run: str
    notify_to: str
    source: dict[str, str] = field(default_factory=dict, repr=False)


def load(env: Mapping[str, str] | None = None, *, user_file: Path | str | None = None,
         default_file: Path | str | None = DEFAULT_FILE) -> Config:
    m = resolve(env, user_file=user_file, default_file=default_file)
    return Config(
        wt_root=pick(m, "MAI_WT_ROOT"),
        tmp_root=pick(m, "MAI_TMP_ROOT"),
        alert_dir=pick(m, "MAI_WT_ALERT_DIR"),
        scan_roots=split_list(pick(m, "MAI_WT_SCAN_ROOTS")),
        disk_paths=split_list(pick(m, "MAI_DISK_PATHS")),
        warn_gb=float(pick(m, "MAI_DISK_WARN_GB")),
        block_gb=float(pick(m, "MAI_DISK_BLOCK_GB")),
        idle_days=int(pick(m, "MAI_WT_IDLE_DAYS")),
        new_since=parse_when(pick(m, "MAI_WT_NEW_SINCE")),
        notify=pick(m, "MAI_WT_NOTIFY") not in ("0", "false", "no"),
        notify_run=pick(m, "MAI_WT_NOTIFY_RUN"),
        notify_to=pick(m, "MAI_WT_NOTIFY_TO"),
        source=m,
    )
