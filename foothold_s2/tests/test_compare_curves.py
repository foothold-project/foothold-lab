"""bf16 비교 스크립트 시험: 답을 아는 곡선(같은 과정의 다른 시드 → 통과 · 편향이 있는 곡선 → 실패)과 tfevents 읽기."""

import hashlib

import numpy as np
import pytest

from foothold_s2.scripts.compare_curves import RULE_PATH, load_rule, read_scalars, verdict

RULE, SHA = load_rule()
TAGS = RULE["metrics"]
N = RULE["iterations"]


def curve(seed, level=1.0, noise=0.02, bias_after=None, bias=0.0):
    rng = np.random.default_rng(seed)
    i = np.arange(N)
    base = level * (1 - np.exp(-i / 80.0)) + 0.1
    if bias_after is not None:
        base = np.where(i >= bias_after, base * (1 - bias), base)
    return base * (1 + rng.normal(0, noise, N))


def run(seed, **kw):
    return {t: {int(i): float(v) for i, v in enumerate(curve(seed + k, **kw))} for k, t in enumerate(TAGS)}


def test_rule_file_is_pinned():
    raw = open(RULE_PATH, "rb").read().replace(b"\r\n", b"\n")
    assert SHA == hashlib.sha256(raw).hexdigest()
    # 줄끝이 CRLF 인 사본(윈도우 체크아웃)도 같은 해시여야 한다
    import os
    import tempfile

    import foothold_s2.scripts.compare_curves as cc

    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "r.json")
        with open(p, "wb") as f:
            f.write(raw.replace(b"\n", b"\r\n"))
        assert cc.load_rule(p)[1] == SHA
    assert (RULE["iterations"], RULE["block"], RULE["noise_factor"], RULE["floor"], RULE["floor_weak"]) == (300, 30, 1.5, 0.02, 0.05)


def test_same_process_other_seed_passes():
    v = verdict(run(1), run(2), run(3), RULE)
    assert v["verdict"] == "pass", v


def test_biased_candidate_fails():
    v = verdict(run(1), run(2, bias_after=100, bias=0.10), run(3), RULE)  # 100 이후 10 % 낮음
    assert v["verdict"] == "fail"


def test_rule_is_noise_relative():
    """시드 잡음이 크면(5 %) 같은 4 % 편향도 잡음 안이라 통과한다. 잡음이 작으면(0.5 %) 같은 편향이 실패한다."""
    big = verdict(run(1, noise=0.15), run(2, noise=0.15, bias_after=0, bias=0.04), run(3, noise=0.15), RULE)
    small = verdict(run(1, noise=0.005), run(2, noise=0.005, bias_after=0, bias=0.04), run(3, noise=0.005), RULE)
    assert big["verdict"] == "pass" and small["verdict"] == "fail"


def test_without_noise_reference_is_only_weak():
    v = verdict(run(1), run(2), None, RULE)
    assert v["verdict"].startswith("weak_pass")  # «통과» 와 구분된다
    v = verdict(run(1), run(2, bias_after=0, bias=0.10), None, RULE)
    assert v["verdict"].startswith("fail")


def test_missing_iterations_and_nan_rejected():
    a = run(1)
    short = {t: {i: x for i, x in d.items() if i != 150} for t, d in run(2).items()}
    with pytest.raises(ValueError):
        verdict(a, short, None, RULE)
    nan = run(2)
    nan[TAGS[0]][10] = float("nan")
    with pytest.raises(ValueError):
        verdict(a, nan, None, RULE)


def test_read_scalars_from_tfevents(tmp_path):
    from torch.utils.tensorboard import SummaryWriter

    w = SummaryWriter(str(tmp_path))
    for i in range(N):
        for k, t in enumerate(TAGS):
            w.add_scalar(t, 0.5 * (k + 1) + i * 1e-3, i)
    w.close()
    got = read_scalars(str(tmp_path), TAGS)
    assert got[TAGS[1]][7] == pytest.approx(1.0 + 7e-3)
    assert len(got[TAGS[0]]) == N
    with pytest.raises(KeyError):
        read_scalars(str(tmp_path), ["Nope/none"])


def test_statistic_is_scale_free():
    """지표의 단위가 달라도(보상 수백 · 손실 0.01) 같은 상대 차이는 같은 판정이다."""
    for lvl in (0.01, 1.0, 300.0):
        assert verdict(run(1, level=lvl), run(2, level=lvl), run(3, level=lvl), RULE)["verdict"] == "pass", lvl
        assert verdict(run(1, level=lvl), run(2, level=lvl, bias_after=100, bias=0.10), run(3, level=lvl), RULE)["verdict"] == "fail", lvl
