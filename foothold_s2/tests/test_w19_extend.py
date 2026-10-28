"""W19: EX-35 extend kind (m2000 -> m3000 같은 조건 계속) + validate_launch 부모 sha 검사. CPU, Kit 없음. 학습은 띄우지 않는다."""

import shutil
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from foothold_s2 import ex35_launch as L
from foothold_s2.sol23f_contract import RESUME_PARENTS, TASKS, validate_launch

SB = Path("C:/mai/wt/foothold-lab/impl-sb/logs/rsl_rl/foothold_s2_sb")
M1500 = SB / "2026-10-26_01-17-47_sb-main/model_1500.pt"
M2000 = SB / "2026-10-26_01-17-47_sb-main_resume_20261026_232446_120476/model_2000.pt"
END = "2099-01-01T00:00:00+00:00"
PKG = Path(__file__).resolve().parents[1]


def pairs(args):
    out, i = {}, 0

    while i < len(args):
        if args[i].startswith("--") and i + 1 < len(args) and not args[i + 1].startswith("--"):
            out[args[i]] = args[i + 1]
            i += 2
        else:
            out[args[i]] = True
            i += 1

    return out


def ns(**kw):
    base = dict(variant="SB", task=TASKS["SB"], agent="rsl_rl_cfg_entry_point", distributed=False, map_input=None, force_gt=False, max_wall_s=86400.0, end_by=END,
                num_envs=3072, seed=42, max_iterations=3001, smoke_updates=None, resume_from=str(M2000), p_map_off=0.1, command_mode="s2a", clock_scatter="on")
    base.update(kw)

    return SimpleNamespace(**base)


def test_the_registry_holds_exactly_the_two_ex35_parents_and_the_kinds_point_into_it():
    assert RESUME_PARENTS == {L.PARENT_SHA256: 1500, L.EXTEND_PARENT_SHA256: 2000}
    assert L.PARENT_BY_KIND["extend"] == (L.EXTEND_PARENT_SHA256, 2000) and L.PARENT_BY_KIND["main"] == (L.PARENT_SHA256, 1500)
    assert L.EXTEND_PARENT_SHA256.startswith("eba0fbdd")


def test_extend_args_equal_main_args_except_parent_and_total():
    main, ext = pairs(L.build_args("main", "cuda:0", "m1500.pt", END)), pairs(L.build_args("extend", "cuda:0", "m2000.pt", END))
    diff = {k for k in set(main) | set(ext) if main.get(k) != ext.get(k)}

    assert diff == {"--resume_from", "--max_iterations"}, diff                       # env · 명령 구성(s2a · 흩기) · 시드 · p_map_off · 판정 인자는 같다
    assert ext["--max_iterations"] == "3001" and ext["--seed"] == "42" and ext["--num_envs"] == "3072" and ext["--command_mode"] == "s2a"


@pytest.mark.parametrize("to_iter,ok", [(2000, False), (2001, True), (2500, True), (3000, True), (3001, False), (0, False)])
def test_extend_to_iter_is_2001_through_3000(to_iter, ok):
    if ok:
        assert pairs(L.build_args("extend", "cuda:0", "m2000.pt", END, to_iter=to_iter))["--max_iterations"] == str(to_iter + 1)
    else:
        with pytest.raises(ValueError, match="to_iter"):
            L.build_args("extend", "cuda:0", "m2000.pt", END, to_iter=to_iter)


def test_extend_receipt_without_the_file_counts_1000_updates_2001_to_3000():
    r = L.receipt("extend", L.build_args("extend", "cuda:0", "m2000.pt", END), "m2000.pt", check_sha=False)

    assert (r["remaining_updates"], r["first_iter"], r["last_iter"], r["parent_iter"], r["expected_parent_sha256"]) == (1000, 2001, 3000, 2000, L.EXTEND_PARENT_SHA256)
    s = L.receipt("extend_smoke2", L.build_args("extend_smoke2", "cuda:1", "m2000.pt", END), "m2000.pt", check_sha=False)

    assert s["remaining_updates"] == 2 and s["first_iter"] == 2001 and s["args"]["smoke-updates"] == "2"


def test_extend_receipt_with_the_real_m2000_passes_and_with_m1500_is_refused():
    assert M2000.exists() and M1500.exists()
    r = L.receipt("extend", L.build_args("extend", "cuda:0", str(M2000), END), str(M2000))

    assert r["parent_sha256"] == L.EXTEND_PARENT_SHA256 and r["validate_launch"] == "ok" and r["last_iter"] == 3000
    with pytest.raises(ValueError, match="부모 SHA-256"):                            # m1500 은 허용표에는 있지만 extend 의 부모는 아니다
        L.receipt("extend", L.build_args("extend", "cuda:0", str(M1500), END), str(M1500))
    with pytest.raises(ValueError, match="부모 SHA-256|남은 0 회"):                  # 반대로 main 에 m2000 을 줘도 거절
        L.receipt("main", L.build_args("main", "cuda:0", str(M2000), END), str(M2000))


def test_hand_launch_is_gated_by_the_registry(tmp_path):
    validate_launch(ns())                                                                       # m2000 -> 3001: 통과
    validate_launch(ns(max_iterations=2002))                                                    # 1 회만
    other = tmp_path / "model_2000.pt"
    other.write_bytes(b"some other checkpoint")

    with pytest.raises(ValueError, match="허용표"):
        validate_launch(ns(resume_from=str(other)))                                             # 손 명령으로 아무 저장본을 부모로 줄 수 없다
    with pytest.raises(ValueError, match="저장본 파일이 없다"):
        validate_launch(ns(resume_from=str(tmp_path / "nope.pt")))
    with pytest.raises(ValueError, match="허용표"):
        validate_launch(ns(resume_from=str(other), max_iterations=1501, smoke_updates=2))       # s2a smoke 2 도 같은 관문
    validate_launch(ns(max_iterations=1501, smoke_updates=2))                                   # m2000 의 smoke 2 는 통과


def test_zero_update_and_over_budget_extensions_are_refused():
    with pytest.raises(ValueError):
        validate_launch(ns(max_iterations=2001))                                                # m2000 에서 총 2001 = 0 회
    with pytest.raises(ValueError):
        validate_launch(ns(max_iterations=3002))                                                # 상한 3001 위
    with pytest.raises(ValueError, match="회"):
        validate_launch(ns(max_iterations=1800))                                                # 부모 회차보다 작다 (남은 회차 음수)


def test_verify_parent_false_is_cpu_test_only_and_the_default_is_on():
    import inspect

    assert inspect.signature(validate_launch).parameters["verify_parent"].default is True
    validate_launch(ns(resume_from="no_such_file.pt"), verify_parent=False)                     # 시험용 가짜 경로


def test_non_extended_sb_resume_without_the_treatment_is_unchanged():
    validate_launch(ns(command_mode=None, clock_scatter=None, max_iterations=1501, smoke_updates=2, resume_from="smoke10.pt"))


def test_run_ex35_script_is_valid_bash_with_the_extend_usage_and_lf_only():
    path = PKG / "run_ex35.sh"
    text = path.read_bytes()

    assert b"\r" not in text and b"extend" in text and b"TO_ITER" in text
    bash = shutil.which("bash")
    if bash is None:
        pytest.skip("bash 없음")
    try:
        rc = subprocess.run([bash, "-n", str(path)], capture_output=True, stdin=subprocess.DEVNULL, timeout=30)
    except subprocess.TimeoutExpired:
        pytest.skip("bash 가 30 초 안에 답하지 않음(WSL 래퍼 등)")

    assert rc.returncode == 0, rc.stderr


def test_revert_kind_same_seed_parent_m1500_and_gates():
    args = L.build_args("revert", "cuda:0", str(M1500), END, to_iter=2000)

    assert args[args.index("--seed") + 1] == "42" and args[args.index("--max_iterations") + 1] == "2001"
    main = L.build_args("main", "cuda:0", str(M1500), END)
    diff = {t for t in args if t not in main} | {t for t in main if t not in args}
    assert diff == set()                                                                # 명령 구성 · env · 판정 인자 · 시드 모두 main 과 같다
    r = L.receipt("revert", args, str(M1500))
    assert r["parent_sha256"] == L.PARENT_SHA256 and r["parent_iter"] == 1500 and r["first_iter"] == 1501 and r["last_iter"] == 2000 and r["args"]["seed"] == "42"
    assert "확정 D21" in r["decision_basis"] and "assumption" not in r
    with pytest.raises(ValueError, match="부모 SHA-256"):
        L.receipt("revert", args, str(M2000))                                        # 부모 파일이 카드 sha 와 다르면 거절
    for bad in (1500, 3001):
        with pytest.raises(ValueError, match="to_iter"):
            L.build_args("revert", "cuda:0", str(M1500), END, to_iter=bad)
    assert pairs(L.build_args("revert", "cuda:0", str(M1500), END, to_iter=2000, seed=42))["--seed"] == "42"
    with pytest.raises(ValueError, match="시드"):
        L.build_args("revert", "cuda:0", str(M1500), END, to_iter=2000, seed=43)
    with pytest.raises(ValueError, match="seed 42"):                                  # 시드 43 은 새 판과 이어 가기 모두 거절
        from types import SimpleNamespace as NS
        from foothold_s2.sol23f_contract import validate_launch
        validate_launch(NS(variant="SB", task=L.TASKS["SB"], agent="rsl_rl_cfg_entry_point", distributed=False, map_input=None, force_gt=False, max_wall_s=1.0, end_by=END,
                           num_envs=3072, seed=43, max_iterations=1501, smoke_updates=None, resume_from=None, p_map_off=None, command_mode=None, clock_scatter=None))
    with pytest.raises(ValueError, match="seed 42"):
        validate_launch(NS(variant="SB", task=L.TASKS["SB"], agent="rsl_rl_cfg_entry_point", distributed=False, map_input=None, force_gt=False,
                           max_wall_s=1.0, end_by=END, num_envs=3072, seed=43, max_iterations=2001, smoke_updates=None,
                           resume_from=str(M1500), p_map_off=0.1, command_mode="s2a", clock_scatter="on"), verify_parent=False)


def test_revert_cli_prints_args(capsys):
    assert L.main(["revert", "cuda:0", str(M1500), "--to-iter", "2000", "--print-args", "--end-by", END]) == 0
    out = capsys.readouterr().out.split()
    assert "42" in out and "2001" in out


def test_parent_sha_and_seed_options_are_revert_only_and_revert_parent_is_m1500_only():
    for kind, parent in (("extend", M2000), ("main", M1500)):
        for kw in ({"parent_sha": L.PARENT_SHA256}, {"parent_sha": L.EXTEND_PARENT_SHA256}, {"seed": 44}):
            with pytest.raises(ValueError, match="revert 전용"):
                L.build_args(kind, "cuda:0", str(parent), END, **kw)
    ok = L.build_args("extend", "cuda:0", str(M2000), END)
    with pytest.raises(ValueError, match="revert 전용"):
        L.receipt("extend", ok, str(M2000), parent_sha=L.PARENT_SHA256)            # 리뷰 반례: extend + m1500 sha
    with pytest.raises(ValueError, match="revert 의 부모 sha"):
        L.build_args("revert", "cuda:0", str(M2000), END, parent_sha=L.EXTEND_PARENT_SHA256, to_iter=3000)   # m2000 은 되돌림 부모가 아니다
    d = L.build_args("revert", "cuda:0", str(M1500), END)                          # 기본 to_iter 3000
    assert d[d.index("--max_iterations") + 1] == "3001"
    assert L.receipt("revert", d, str(M1500))["remaining_updates"] == 1500


def test_cli_rejects_parent_sha_for_extend():
    with pytest.raises(ValueError, match="revert 전용"):
        L.main(["extend", "cuda:0", str(M2000), "--parent-sha", L.PARENT_SHA256, "--print-args", "--end-by", END])
