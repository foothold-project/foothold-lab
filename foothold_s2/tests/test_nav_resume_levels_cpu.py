"""HiPAN (A) --resume-levels 손잡이 · (B) 수준별 judge (CPU · Kit 없음)."""
import dataclasses
import json
from types import SimpleNamespace

import numpy as np
import pytest
import torch

from foothold_s2.nav import hl_judge, hl_ppo_cfg as cfg, hl_train
from foothold_s2.tests.test_nav_train_cpu import FakeEnv, _ppo

N = 8


class LeveledEnv(FakeEnv):
    """FakeEnv + PGCL 수준을 가진 task (nav_task 의 pgcl 목록만 흉내: level · streak)."""

    def __init__(self, n):
        super().__init__(n)
        self.task = SimpleNamespace(pgcl=[SimpleNamespace(level=1, streak=0) for _ in range(n)])


def test_parse_distribution_quota_and_errors():
    lv = hl_train.parse_resume_levels("1:0.5,2:0.25,3:0.25", N, seed=1)
    assert sorted(lv) == [1] * 4 + [2] * 2 + [3] * 2
    assert lv == hl_train.parse_resume_levels("1:0.5,2:0.25,3:0.25", N, seed=1) and lv != hl_train.parse_resume_levels("1:0.5,2:0.25,3:0.25", N, seed=2)
    assert sorted(hl_train.parse_resume_levels("1:0.34,2:0.33,3:0.33", 10)) == [1] * 4 + [2] * 3 + [3] * 3
    assert hl_train.parse_resume_levels("checkpoint", N) == "checkpoint"
    for bad in ("1:0.5", "0:1.0", "1:0.5,1:0.5", "1:1.5,2:-0.5", "x", "1:0.5,2"):
        with pytest.raises(ValueError):
            hl_train.parse_resume_levels(bad, N)


def _first(tmp_path):
    env = LeveledEnv(N)
    for i, p in enumerate(env.task.pgcl):
        p.level, p.streak = 1 + i % 4, i % 3
    hl_train.train(env, _ppo(), out_dir=tmp_path, iterations=2, receipt={"receipt_sha256": "aa"}, log=lambda s: None)
    return str(tmp_path / "model_2.pt"), [p.level for p in env.task.pgcl], [p.streak for p in env.task.pgcl]


def test_checkpoint_keeps_pgcl_state_and_default_resume_starts_at_level_1_as_before(tmp_path):
    ck, levels, streaks = _first(tmp_path)
    saved = torch.load(ck, weights_only=False)
    assert saved["pgcl"] == {"level": levels, "streak": streaks}
    env = LeveledEnv(N)
    lines = []
    hl_train.train(env, _ppo(), out_dir=tmp_path / "off", iterations=1, receipt={"receipt_sha256": "aa"}, resume=ck, log=lines.append)
    assert all(p.level == 1 for p in env.task.pgcl) and not any("RESUME_LEVELS" in s for s in lines)      # 꺼짐 = 옛 동작
    assert "pgcl" not in torch.load(_plain(tmp_path), weights_only=False)                                   # task 없는 env 는 옛 저장본 모양 그대로


def _plain(tmp_path):
    hl_train.train(FakeEnv(N), _ppo(), out_dir=tmp_path / "plain", iterations=2, receipt={"receipt_sha256": "aa"}, log=lambda s: None)
    return str(tmp_path / "plain" / "model_2.pt")


def test_resume_levels_checkpoint_mode_restores_levels_and_streaks(tmp_path):
    ck, levels, streaks = _first(tmp_path)
    env, lines = LeveledEnv(N), []
    hl_train.train(env, _ppo(), out_dir=tmp_path / "on", iterations=1, receipt={"receipt_sha256": "aa"}, resume=ck, resume_levels="checkpoint", log=lines.append)
    assert [p.level for p in env.task.pgcl] == levels and [p.streak for p in env.task.pgcl] == streaks
    assert any(s.startswith("RESUME_LEVELS mode=checkpoint") for s in lines)


def test_resume_levels_distribution_mode_works_on_a_checkpoint_without_pgcl_but_checkpoint_mode_refuses(tmp_path):
    old = _plain(tmp_path)
    env, lines = LeveledEnv(N), []
    hl_train.train(env, _ppo(), out_dir=tmp_path / "d", iterations=1, receipt={"receipt_sha256": "aa"}, resume=old, resume_levels="3:0.5,4:0.5", log=lines.append)
    assert sorted(p.level for p in env.task.pgcl) == [3] * 4 + [4] * 4 and all(p.streak == 0 for p in env.task.pgcl)
    assert any('"3": 4' in s and "mode=distribution" in s for s in lines)
    with pytest.raises(ValueError, match="no pgcl state"):
        hl_train.train(LeveledEnv(N), _ppo(), out_dir=tmp_path / "e", iterations=1, receipt={"receipt_sha256": "aa"}, resume=old, resume_levels="checkpoint", log=lambda s: None)


def test_resume_levels_refuses_without_resume_or_without_a_pgcl_task(tmp_path):
    with pytest.raises(ValueError, match="needs a resume"):
        hl_train.train(LeveledEnv(N), _ppo(), out_dir=tmp_path / "a", iterations=1, receipt={"receipt_sha256": "aa"}, resume_levels="1:1.0", log=lambda s: None)
    old = _plain(tmp_path)
    with pytest.raises(ValueError, match="PGCL"):
        hl_train.train(FakeEnv(N), _ppo(), out_dir=tmp_path / "b", iterations=1, receipt={"receipt_sha256": "aa"}, resume=old, resume_levels="1:1.0", log=lambda s: None)


def test_receipt_gets_a_levels_cell_only_when_on_and_identity_is_unchanged(tmp_path, monkeypatch):
    from foothold_s2.scripts import train_nav_teacher as t

    off = {"path": "x", "sha256": "y"}
    row = lambda lv: {"path": "x", "sha256": "y", **({"levels": str(lv)} if lv else {})}
    assert row(None) == off and row("checkpoint")["levels"] == "checkpoint"
    rec = {"format": "f", "a": 1, "resume": row("checkpoint")}
    assert t.identity_text(rec) == t.identity_text({"format": "f", "a": 1, "resume": off})           # resume 칸은 신원 글에서 빠진다
    with pytest.raises(SystemExit, match="needs --resume"):
        t.main(["--print", "--lower-checkpoint", "a", "--lower-sha256", "b", "--room-manifest", "c", "--plan", "d", "--vx-corr-b", "1", "--resume-levels", "1:1.0"])


# ---- (B) judge ----

def _row(it, lv, noise=0.2):
    r = {"iteration": it, "noise_std": noise}
    for k in ("l2", "l3p", "l3", "l4", "l5", "l6p"):
        e, s, p, c = lv.get(k, (0, -1.0, -1.0, -1.0))
        r.update({f"nv_eps_{k}": e, f"nv_succ_{k}": s, f"nv_prog_{k}": p, f"nv_cos_{k}": c, f"nv_cos_n_{k}": e})
    return r


def _log(tmp_path, prev, last):
    path = tmp_path / "train.log"
    path.write_text("\n".join("junk line\n" + json.dumps(_row(i, prev if i <= 50 else last)) for i in range(1, 101)), encoding="utf-8")
    return str(path)


GOOD = {"l3": (10, 0.9, 0.9, 0.5), "l4": (10, 0.8, 0.8, 0.4), "l5": (4, 0.7, 0.7, 0.4)}


def test_judge_passes_when_every_populated_level_holds_and_marks_empty_levels_na(tmp_path):
    rows = hl_judge.read_rows(_log(tmp_path, GOOD, GOOD))
    res = hl_judge.judge(rows, (51, 100), (1, 50))
    assert res["ok"] and res["cells"]["l6p"]["na"] and res["cells"]["l3"]["pass"]
    assert "n/a (에피소드 없음)" in hl_judge.render(res, (51, 100), (1, 50))


def test_judge_catches_a_drop_at_one_level_that_a_pooled_block_would_hide(tmp_path):
    """수준 3 은 크게 떨어지고 수준 5 가 늘어 합친 값 (l3p) 은 안 떨어진 판: 옛 블록 판정은 통과, 새 판정은 l3 실패."""
    last = {"l3": (4, 0.3, 0.9, 0.5), "l4": (10, 0.8, 0.8, 0.4), "l5": (30, 0.95, 0.95, 0.5)}
    rows = hl_judge.read_rows(_log(tmp_path, GOOD, last))
    pooled = lambda d: sum(d[k][0] * d[k][1] for k in d) / sum(d[k][0] for k in d)
    assert pooled(last) > 0.55 and pooled(last) - pooled(GOOD) > -0.05
    res = hl_judge.judge(rows, (51, 100), (1, 50))
    assert not res["ok"] and not res["cells"]["l3"]["pass"] and res["cells"]["l3"]["checks"]["succ"] is False and res["cells"]["l3"]["checks"]["dsucc"] is False
    assert res["cells"]["l5"]["pass"]


def test_judge_noise_threshold_and_old_logs_without_fine_columns(tmp_path, capsys):
    p = tmp_path / "train.log"
    p.write_text("\n".join(json.dumps(_row(i, GOOD, noise=0.1)) for i in range(1, 101)), encoding="utf-8")
    assert not hl_judge.judge(hl_judge.read_rows(str(p)), (51, 100), (1, 50))["ok"]
    old = tmp_path / "old.log"
    old.write_text("\n".join(json.dumps({"iteration": i, "noise_std": 0.2, "nv_eps_l3p": 5, "nv_succ_l3p": 0.9}) for i in range(1, 101)), encoding="utf-8")
    assert hl_judge.main([str(old), "--last", "51", "100", "--prev", "1", "50"]) == 2 and "세분" in capsys.readouterr().err
    assert hl_judge.main([_log(tmp_path, GOOD, GOOD), "--last", "51", "100", "--prev", "1", "50"]) == 0
