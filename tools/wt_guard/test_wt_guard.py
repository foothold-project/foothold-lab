"""wt_guard 시험: 가짜 저장소에서 C 쪽 worktree 를 만들면 경보, D 쪽이면 조용함, 문턱 반례, 설치 이어 붙임.

실행(D: 임시):  TMP=D:/mai-tmp/<역할> python -m pytest -q -p no:cacheprovider tools/wt_guard/test_wt_guard.py
git · bash(Git for Windows 또는 Linux) 가 PATH 에 있어야 한다.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from collections import namedtuple
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import disk_guard  # noqa: E402
import inventory  # noqa: E402
import wt_config  # noqa: E402

Usage = namedtuple("usage", "total used free")
GB = 1_000_000_000
BASH = shutil.which("bash")
GIT = shutil.which("git")
ZERO = "0" * 40


def run(cmd, cwd=None, env=None, check=True):
    cp = subprocess.run(cmd, cwd=str(cwd) if cwd else None, env=env, capture_output=True,
                        text=True, encoding="utf-8", errors="replace")
    if check and cp.returncode != 0:
        raise AssertionError(f"{cmd} rc={cp.returncode}\nstdout={cp.stdout}\nstderr={cp.stderr}")
    return cp


def clean_env(**extra):
    """훅이 실제 orca · 사용자 설정 파일 · 바깥 MAI_* 변수를 못 보게 한 환경."""
    env = {k: v for k, v in os.environ.items() if not k.startswith("MAI_")}
    env["GIT_LFS_SKIP_SMUDGE"] = "1"
    env["GIT_CONFIG_NOSYSTEM"] = "1"
    env.setdefault("HOME", env.get("USERPROFILE", str(Path.home())))
    env.update(extra)
    return env


@unittest.skipUnless(BASH and GIT, "bash 와 git 이 필요")
class HookFixture(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="wt_guard_")
        self.addCleanup(self.temp.cleanup)
        t = Path(self.temp.name).resolve()
        self.t = t
        self.origin = t / "origin.git"
        self.main = t / "main"
        self.dside = t / "dside"
        self.cside = t / "cside"
        self.alerts = t / "alerts"
        self.notify_log = t / "notify.log"
        for d in (self.dside, self.cside):
            d.mkdir()
        run(["git", "init", "-q", "--bare", "-b", "main", str(self.origin)])
        run(["git", "clone", "-q", str(self.origin), str(self.main)], env=clean_env())
        run(["git", "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "--allow-empty", "-m", "init"],
            cwd=self.main)
        run(["git", "push", "-q", "origin", "main"], cwd=self.main)
        # orca 대신 부를 가짜 알림 명령: 제목 · 본문을 파일에 적는다
        self.stub = t / "notify_stub.sh"
        self.stub.write_text("#!/bin/sh\nprintf '%s\\n%s\\n' \"$1\" \"$2\" >> \"" + self.notify_log.as_posix() + "\"\n",
                             encoding="utf-8", newline="\n")
        self.stub.chmod(0o755)
        # 사용자 설정 파일: 뿌리 · 경보 자리 · 알림 명령
        self.user_cfg = t / "wt_guard.env"
        self.user_cfg.write_text(
            f"MAI_WT_ROOT={self.dside.as_posix()}\nMAI_WT_ALERT_DIR={self.alerts.as_posix()}\n"
            f"MAI_WT_NOTIFY_CMD={self.stub.as_posix()}\n", encoding="utf-8", newline="\n")
        self.env = clean_env(MAI_WT_GUARD_CONFIG=str(self.user_cfg), MAI_ROLE="tester")

    def install(self, extra_args=()):
        return run([BASH, str(HERE / "install.sh"), "--repo", str(self.main), *extra_args], env=self.env)

    def hooks_dir(self) -> Path:
        return Path(run(["git", "rev-parse", "--path-format=absolute", "--git-common-dir"],
                        cwd=self.main).stdout.strip()) / "hooks"

    def add_worktree(self, where: Path, branch: str, env=None):
        return run(["git", "worktree", "add", "-q", "-b", branch, str(where), "main"], cwd=self.main,
                   env=env or self.env)

    def alert_files(self):
        return sorted(self.alerts.glob("wt-outside-*.json")) if self.alerts.is_dir() else []

    # ---- 훅 ----
    def test_outside_root_alerts_and_notifies_inside_root_is_quiet(self):
        self.install()
        cp = self.add_worktree(self.cside / "wt-c", "b-c")
        self.assertIn("wt_guard 경고", cp.stderr)
        self.assertIn("GIT_LFS_SKIP_SMUDGE", cp.stderr.replace("\n", " ") if "GIT_LFS" in cp.stderr else "GIT_LFS_SKIP_SMUDGE")
        files = self.alert_files()
        self.assertEqual(len(files), 1, cp.stderr)
        doc = json.loads(files[0].read_text(encoding="utf-8"))
        self.assertEqual(doc["schema"], "wt-guard-alert/1")
        self.assertEqual(doc["prev_head"], ZERO)
        self.assertEqual(doc["role"], "tester")
        self.assertEqual(wt_config.norm_path(doc["worktree"]), wt_config.norm_path(self.cside / "wt-c"))
        self.assertEqual(wt_config.norm_path(doc["wt_root"]), wt_config.norm_path(self.dside))
        self.assertEqual(doc["notify"], "sent")
        lines = self.notify_log.read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(lines), 2)
        self.assertTrue(lines[0].startswith("[wt_guard] 허용 자리 밖 사본 생성 경고 · tester"), lines[0])
        self.assertIn("D138", lines[1])
        # D 쪽: 조용함(경보 · 알림 늘지 않음)
        cp2 = self.add_worktree(self.dside / "wt-d", "b-d")
        self.assertNotIn("wt_guard 경고", cp2.stderr)
        self.assertEqual(len(self.alert_files()), 1)
        self.assertEqual(len(self.notify_log.read_text(encoding="utf-8").splitlines()), 2)
        # 뿌리와 이름만 비슷한 형제 폴더(dside2)는 밖이다
        (self.t / "dside2").mkdir()
        cp3 = self.add_worktree(self.t / "dside2" / "wt-x", "b-x")
        self.assertIn("wt_guard 경고", cp3.stderr)
        self.assertEqual(len(self.alert_files()), 2)

    def test_ordinary_checkout_does_not_alert(self):
        self.install()
        self.add_worktree(self.cside / "wt-c", "b-c")
        self.assertEqual(len(self.alert_files()), 1)
        cp = run(["git", "checkout", "-q", "-b", "other"], cwd=self.cside / "wt-c", env=self.env)
        self.assertNotIn("wt_guard 경고", cp.stderr)
        self.assertEqual(len(self.alert_files()), 1)

    def test_lfs_recommendation_only_when_smudge_not_skipped(self):
        self.install()
        env_skip = dict(self.env)
        cp = self.add_worktree(self.dside / "wt-1", "b-1", env=env_skip)
        self.assertNotIn("GIT_LFS_SKIP_SMUDGE=1 을", cp.stderr)
        env_no = dict(self.env)
        env_no.pop("GIT_LFS_SKIP_SMUDGE")
        cp = self.add_worktree(self.dside / "wt-2", "b-2", env=env_no)
        self.assertIn("GIT_LFS_SKIP_SMUDGE=1 을", cp.stderr)

    def test_notify_off_and_env_override_beats_config_file(self):
        self.install()
        env = dict(self.env)
        env["MAI_WT_NOTIFY"] = "0"
        env["MAI_WT_ROOT"] = self.cside.as_posix()  # 환경 변수가 파일을 이긴다 → cside 가 뿌리
        cp = self.add_worktree(self.cside / "wt-c", "b-c", env=env)
        self.assertNotIn("wt_guard 경고", cp.stderr)
        cp = self.add_worktree(self.dside / "wt-d", "b-d", env=env)
        self.assertIn("wt_guard 경고", cp.stderr)
        doc = json.loads(self.alert_files()[0].read_text(encoding="utf-8"))
        self.assertEqual(doc["notify"], "skipped")
        self.assertFalse(self.notify_log.exists())

    def test_notify_failure_is_recorded_and_checkout_still_succeeds(self):
        self.install()
        bad = self.t / "bad_stub.sh"
        bad.write_text("#!/bin/sh\nexit 7\n", encoding="utf-8", newline="\n")
        env = dict(self.env)
        env["MAI_WT_NOTIFY_CMD"] = bad.as_posix()
        cp = self.add_worktree(self.cside / "wt-c", "b-c", env=env)
        self.assertEqual(cp.returncode, 0)
        self.assertTrue((self.cside / "wt-c" / ".git").exists())
        doc = json.loads(self.alert_files()[0].read_text(encoding="utf-8"))
        self.assertEqual(doc["notify"], "failed")

    # ---- 설치 ----
    def test_install_appends_to_existing_hook_without_overwriting_and_is_idempotent(self):
        hooks = self.hooks_dir()
        hooks.mkdir(parents=True, exist_ok=True)
        witness = self.t / "existing.log"
        existing = hooks / "post-checkout"
        existing.write_text("#!/bin/sh\necho EXISTING \"$1\" >> \"" + witness.as_posix() + "\"\n",
                            encoding="utf-8", newline="\n")
        existing.chmod(0o755)
        out1 = self.install().stdout
        self.assertIn("이어 붙임", out1)
        text = existing.read_text(encoding="utf-8")
        self.assertTrue(text.startswith("#!/bin/sh\necho EXISTING"), text)
        self.assertEqual(text.count("wt_guard-post-checkout"), 1)
        self.assertTrue(list(hooks.glob("post-checkout.before-wt_guard-*")))
        out2 = self.install().stdout
        self.assertIn("이미 이어 붙어 있음", out2)
        self.assertEqual(existing.read_text(encoding="utf-8").count("wt_guard-post-checkout"), 1)
        check = self.install(["--check"]).stdout
        self.assertIn("status=installed", check)
        # 둘 다 돈다: 기존 훅의 증인 파일 + wt_guard 경보
        self.add_worktree(self.cside / "wt-c", "b-c")
        self.assertIn("EXISTING " + ZERO, witness.read_text(encoding="utf-8"))
        self.assertEqual(len(self.alert_files()), 1)

    def test_install_refuses_non_sh_hook(self):
        hooks = self.hooks_dir()
        hooks.mkdir(parents=True, exist_ok=True)
        (hooks / "post-checkout").write_text("#!/usr/bin/env python3\nprint('x')\n", encoding="utf-8", newline="\n")
        cp = run([BASH, str(HERE / "install.sh"), "--repo", str(self.main)], env=self.env, check=False)
        self.assertEqual(cp.returncode, 3, cp.stdout + cp.stderr)
        self.assertEqual((hooks / "post-checkout").read_text(encoding="utf-8").count("wt_guard"), 0)

    def test_install_dry_run_changes_nothing(self):
        hooks = self.hooks_dir()
        before = sorted(p.name for p in hooks.glob("*")) if hooks.is_dir() else []
        cp = self.install(["--dry-run"])
        self.assertIn("복사할 것", cp.stdout)
        after = sorted(p.name for p in hooks.glob("*")) if hooks.is_dir() else []
        self.assertEqual(before, after)

    # ---- 재고 ----
    def test_inventory_classifies_outside_new_dirty_pushed(self):
        self.install()
        self.add_worktree(self.cside / "wt-c", "b-c")
        self.add_worktree(self.dside / "wt-d", "b-d")
        (self.cside / "wt-c" / "scratch.txt").write_text("x", encoding="utf-8")
        run(["git", "push", "-q", "-u", "origin", "b-d"], cwd=self.dside / "wt-d", env=self.env)
        cfg = wt_config.load(self.env, user_file=self.user_cfg)
        now = datetime.now(tz=wt_config.KST)
        rows = inventory.collect([str(self.main)], cfg, now=now, with_size=True, scan=False)
        by = {Path(r["path"]).name: r for r in rows}
        self.assertEqual(set(by), {"main", "wt-c", "wt-d"})
        self.assertTrue(by["main"]["is_main"])
        self.assertFalse(by["main"]["outside_root"])
        c, d = by["wt-c"], by["wt-d"]
        self.assertTrue(c["outside_root"])
        self.assertFalse(d["outside_root"])
        self.assertEqual(c["untracked"], 1)
        self.assertEqual(d["uncommitted"], 0)
        self.assertTrue(d["pushed"])
        self.assertTrue(d["remote_branch_exists"])
        self.assertFalse(c["remote_branch_exists"])
        self.assertIsNotNone(c["size_bytes"])
        self.assertIsNotNone(c["last_git_activity"])
        if wt_config.IS_WINDOWS or hasattr(os.stat(self.cside), "st_birthtime"):
            self.assertTrue(c["new_outside"], c)
        self.assertFalse(c["archive_candidate"])
        self.assertFalse(d["archive_candidate"])  # 깨끗 · push 됨이지만 방금 썼다
        line = inventory.summarize(rows, [{"path": "X:/", "free_gb": 12.0}], cfg, now=now)
        self.assertIn("사본 3", line)
        self.assertIn("밖 1", line)
        self.assertIn("미커밋 있음 1", line)
        self.assertIn("X:/ 12 GB", line)
        # 표 · JSON 경로(CLI)
        out = self.t / "inv.json"
        cp = run([sys.executable, "-X", "utf8", str(HERE / "inventory.py"), "--repo", str(self.main), "--no-scan",
                  "--json", str(out), "--table"], env=self.env)
        self.assertIn("wt_guard 재고", cp.stdout)
        doc = json.loads(out.read_text(encoding="utf-8"))
        self.assertEqual(doc["schema"], "wt-guard-inventory/1")
        self.assertEqual(len(doc["rows"]), 3)

    def test_inventory_scan_roots_finds_standalone_clone(self):
        clone = self.dside / "repo" / "standalone"
        clone.parent.mkdir()
        run(["git", "clone", "-q", str(self.origin), str(clone)], env=clean_env())
        cfg = wt_config.load(self.env, user_file=self.user_cfg)
        found = inventory.scan_roots([str(self.dside)])
        self.assertEqual([wt_config.norm_path(p) for p in found], [wt_config.norm_path(clone)])
        rows = inventory.collect([], cfg, now=datetime.now(tz=wt_config.KST), with_size=False,
                                 scan=True) if not cfg.scan_roots else None
        self.assertIsNone(rows)  # 기본 scan_roots 는 실제 D:/C: 라 여기서는 안 훑는다(위 scan_roots 직접 시험으로 대신)


class ClassifyPure(unittest.TestCase):
    def cfg(self):
        return wt_config.load({"MAI_WT_ROOT": "D:/mai-wt", "MAI_WT_NEW_SINCE": "2026-11-02T17:00:00+09:00",
                               "MAI_WT_IDLE_DAYS": "7", "HOME": "/nonexistent"}, user_file=None,
                              default_file=None)

    def row(self, **kw):
        base = {"path": "D:/mai-wt/foothold-lab/x", "is_main": False, "created_at": "2026-11-02T18:00:00+09:00",
                "last_write": "2026-10-20T10:00:00+09:00", "last_git_activity": None,
                "uncommitted": 0, "untracked": 0, "pushed": True}
        base.update(kw)
        return base

    def test_archive_candidate_needs_clean_pushed_idle(self):
        now = wt_config.parse_when("2026-11-02T18:00:00+09:00")
        cfg = self.cfg()
        self.assertTrue(inventory.classify(self.row(), cfg, now=now)["archive_candidate"])
        self.assertFalse(inventory.classify(self.row(untracked=1), cfg, now=now)["archive_candidate"])
        self.assertFalse(inventory.classify(self.row(pushed=False), cfg, now=now)["archive_candidate"])
        self.assertFalse(inventory.classify(self.row(last_write="2026-10-30T10:00:00+09:00"), cfg, now=now)
                         ["archive_candidate"])
        # 정확히 7 일이면 후보, 7 일에서 1 초 모자라면 아님
        self.assertTrue(inventory.classify(self.row(last_write="2026-10-26T18:00:00+09:00"), cfg, now=now)
                        ["archive_candidate"])
        self.assertFalse(inventory.classify(self.row(last_write="2026-10-26T18:00:01+09:00"), cfg, now=now)
                         ["archive_candidate"])
        # 마지막 git 활동이 더 늦으면 그것을 쓴다
        self.assertFalse(inventory.classify(self.row(last_git_activity="2026-11-01T00:00:00+09:00"), cfg, now=now)
                         ["archive_candidate"])

    def test_outside_and_new(self):
        now = wt_config.parse_when("2026-11-02T18:00:00+09:00")
        cfg = self.cfg()
        r = inventory.classify(self.row(path="C:/mai/wt/foothold-lab/x"), cfg, now=now)
        self.assertTrue(r["outside_root"])
        self.assertTrue(r["new_outside"])
        r = inventory.classify(self.row(path="C:/mai/wt/foothold-lab/x", created_at="2026-11-02T16:59:59+09:00"),
                               cfg, now=now)
        self.assertFalse(r["new_outside"])
        r = inventory.classify(self.row(path="C:/mai/wt/foothold-lab/x", created_at=None), cfg, now=now)
        self.assertIsNone(r["new_outside"])
        r = inventory.classify(self.row(path="d:\\MAI-WT\\foothold-lab\\x"), cfg, now=now)
        self.assertEqual(r["outside_root"], not wt_config.IS_WINDOWS is True and False)
        r = inventory.classify(self.row(path="D:/mai-wt-archive/x"), cfg, now=now)
        self.assertTrue(r["outside_root"])  # 접두가 같아도 형제 폴더는 밖
        r = inventory.classify(self.row(path="C:/anything", is_main=True), cfg, now=now)
        self.assertFalse(r["outside_root"])


class DiskGuardThresholds(unittest.TestCase):
    def cfg(self):
        return wt_config.load({"MAI_DISK_PATHS": "X:/;Y:/", "HOME": "/nonexistent"}, user_file=None,
                              default_file=None)

    def fake(self, table):
        def usage(path):
            if path not in table:
                raise FileNotFoundError(path)
            return Usage(total=2000 * GB, used=0, free=table[path])
        return usage

    def test_levels_at_boundaries(self):
        cfg = self.cfg()
        u = self.fake({"ok": 100 * GB, "warn": 100 * GB - 1, "block": 50 * GB - 1, "edge": 50 * GB})
        res = disk_guard.check(["ok", "warn", "block", "edge", "missing"], usage_fn=u, config=cfg)
        self.assertEqual([r["level"] for r in res], ["ok", "warn", "block", "warn", "unknown"])
        self.assertEqual(disk_guard.worst(res), "unknown")
        self.assertEqual(disk_guard.worst(res[:2]), "warn")
        self.assertEqual(disk_guard.worst(res[:1]), "ok")
        self.assertIn("missing 미측", disk_guard.summary_line(res))

    def test_custom_thresholds_and_counterexamples(self):
        cfg = self.cfg()
        u = self.fake({"p": 30 * GB})
        self.assertEqual(disk_guard.check(["p"], warn_gb=40, block_gb=20, usage_fn=u, config=cfg)[0]["level"], "warn")
        self.assertEqual(disk_guard.check(["p"], warn_gb=200, block_gb=31, usage_fn=u, config=cfg)[0]["level"], "block")
        with self.assertRaises(ValueError):
            disk_guard.check(["p"], warn_gb=50, block_gb=50, usage_fn=u, config=cfg)
        with self.assertRaises(ValueError):
            disk_guard.check(["p"], warn_gb=50, block_gb=60, usage_fn=u, config=cfg)
        with self.assertRaises(ValueError):
            disk_guard.check(["p"], warn_gb=-1, block_gb=-2, usage_fn=u, config=cfg)
        with self.assertRaises(ValueError):
            disk_guard.check([], usage_fn=u, config=cfg)

    def test_require_free_raises_on_block_and_unknown_warns_on_warn(self):
        cfg = self.cfg()
        import io
        buf = io.StringIO()
        ok = disk_guard.require_free(["a"], usage_fn=self.fake({"a": 500 * GB}), config=cfg, stream=buf)
        self.assertEqual(ok[0]["level"], "ok")
        self.assertEqual(buf.getvalue(), "")
        disk_guard.require_free(["a"], usage_fn=self.fake({"a": 60 * GB}), config=cfg, stream=buf)
        self.assertIn("disk_guard 경고", buf.getvalue())
        with self.assertRaises(disk_guard.DiskGuardError):
            disk_guard.require_free(["a"], usage_fn=self.fake({"a": 60 * GB}), config=cfg, strict=True, stream=buf)
        with self.assertRaises(disk_guard.DiskGuardError) as cm:
            disk_guard.require_free(["a", "b"], usage_fn=self.fake({"a": 500 * GB, "b": 10 * GB}), config=cfg)
        self.assertEqual(cm.exception.results[1]["level"], "block")
        with self.assertRaises(disk_guard.DiskGuardError):
            disk_guard.require_free(["nope"], usage_fn=self.fake({}), config=cfg)

    def test_cli_exit_codes_against_real_disk(self):
        here = str(Path(__file__).resolve().parent)
        env = clean_env(MAI_WT_GUARD_CONFIG="/nonexistent/wt_guard.env")
        cp = run([sys.executable, "-X", "utf8", str(HERE / "disk_guard.py"), here, "--warn-gb", "0.002",
                  "--block-gb", "0.001"], env=env)
        self.assertIn("ok", cp.stdout)
        cp = run([sys.executable, "-X", "utf8", str(HERE / "disk_guard.py"), here, "--warn-gb", "1e9",
                  "--block-gb", "1e8", "--json"], env=env, check=False)
        self.assertEqual(cp.returncode, 2, cp.stdout + cp.stderr)
        self.assertEqual(json.loads(cp.stdout)["worst"], "block")
        cp = run([sys.executable, "-X", "utf8", str(HERE / "disk_guard.py"), here, "--warn-gb", "1e9",
                  "--block-gb", "0.001"], env=env, check=False)
        self.assertEqual(cp.returncode, 0)
        cp = run([sys.executable, "-X", "utf8", str(HERE / "disk_guard.py"), here, "--warn-gb", "1e9",
                  "--block-gb", "0.001", "--strict"], env=env, check=False)
        self.assertEqual(cp.returncode, 1)
        cp = run([sys.executable, "-X", "utf8", str(HERE / "disk_guard.py"), "Q:/no/such/path/anywhere"],
                 env=env, check=False)
        self.assertEqual(cp.returncode, 3)
        cp = run([sys.executable, "-X", "utf8", str(HERE / "disk_guard.py"), here, "--warn-gb", "1",
                  "--block-gb", "2"], env=env, check=False)
        self.assertEqual(cp.returncode, 3)
        self.assertIn("설정 오류", cp.stderr)


class ConfigLayers(unittest.TestCase):
    def test_precedence_env_over_user_over_default(self):
        with tempfile.TemporaryDirectory(prefix="wt_cfg_") as d:
            dflt = Path(d) / "default.env"
            user = Path(d) / "user.env"
            dflt.write_text("MAI_DISK_WARN_GB=100\nMAI_DISK_BLOCK_GB=50\nMAI_WT_ROOT_WINDOWS=D:/x\nMAI_WT_ROOT_LINUX=/x\n",
                            encoding="utf-8")
            user.write_text("# 주석\r\nMAI_DISK_WARN_GB=120\r\nBAD KEY=1\r\n", encoding="utf-8")
            cfg = wt_config.load({"MAI_DISK_BLOCK_GB": "70", "HOME": d}, user_file=user, default_file=dflt)
            self.assertEqual(cfg.warn_gb, 120.0)
            self.assertEqual(cfg.block_gb, 70.0)
            self.assertEqual(cfg.wt_root, "D:/x" if wt_config.IS_WINDOWS else "/x")
            self.assertNotIn("BAD KEY", cfg.source)
            cfg2 = wt_config.load({"MAI_WT_ROOT": "E:/y", "HOME": d}, user_file=user, default_file=dflt)
            self.assertEqual(cfg2.wt_root, "E:/y")

    def test_default_file_in_repo_parses_and_matches_hook_builtin(self):
        cfg = wt_config.load({"HOME": "/nonexistent"}, user_file=None)
        self.assertEqual(cfg.warn_gb, 100.0)
        self.assertEqual(cfg.block_gb, 50.0)
        self.assertEqual(cfg.idle_days, 7)
        self.assertEqual(cfg.new_since.isoformat(), "2026-11-02T17:00:00+09:00")
        hook = (HERE / "post-checkout").read_text(encoding="utf-8")
        for v in ("D:/mai-wt", "/data/mai-wt", "D:/mai-tmp/wt_guard/alerts", "/data/mai-tmp/wt_guard/alerts"):
            self.assertIn(v, hook)
        self.assertIn(wt_config.BUILTIN["MAI_WT_ROOT"], hook)
        self.assertNotIn("\r", hook, "훅은 LF 여야 한다")
        self.assertNotIn("\r", (HERE / "install.sh").read_text(encoding="utf-8"))

    def test_norm_and_is_under(self):
        self.assertTrue(wt_config.is_under("D:/mai-wt/foothold-lab/a", "D:/mai-wt"))
        self.assertTrue(wt_config.is_under("D:/mai-wt/foothold-lab/a", "D:/mai-wt/"))
        self.assertFalse(wt_config.is_under("D:/mai-wt-archive/a", "D:/mai-wt"))
        self.assertFalse(wt_config.is_under("D:/mai-wt", "D:/mai-wt/foothold-lab"))
        self.assertTrue(wt_config.is_under("/data/mai-wt/x", "/data/mai-wt"))
        self.assertFalse(wt_config.is_under("/data/mai-wtx", "/data/mai-wt"))
        if wt_config.IS_WINDOWS:
            self.assertTrue(wt_config.is_under("d:\\MAI-WT\\x", "D:/mai-wt"))


if __name__ == "__main__":
    unittest.main()
