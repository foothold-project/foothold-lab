"""EX-35 기동 줄 · 인자 영수증 (verifier 막음 1 의 2). CPU, Kit 없음."""

from pathlib import Path

import pytest

from foothold_s2 import ex35_launch as L

PKG = Path(__file__).resolve().parents[1]
REAL_PARENT = Path("C:/mai/wt/foothold-lab/impl-sb/logs/rsl_rl/foothold_s2_sb/2026-10-26_01-17-47_sb-main/model_1500.pt")
END = "2099-01-01T00:00:00+00:00"


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


def test_main_args_carry_every_treatment_the_run_sb_script_leaves_out():
    p = pairs(L.build_args("main", "cuda:0", "m1500.pt", END))

    assert p["--resume_from"] == "m1500.pt" and p["--max_iterations"] == "2001" and p["--command_mode"] == "s2a" and p["--clock_scatter"] == "on"
    assert p["--p_map_off"] == "0.1" and p["--judge_world_frame"] == "on" and p["--judge_mask_new_task"] == "off" and p["--num_envs"] == "3072" and p["--seed"] == "42"
    assert "--smoke-updates" not in p and p["--device"] == "cuda:0"


def test_receipt_counts_500_updates_from_1501_to_2000_and_smoke2_counts_2():
    r = L.receipt("main", L.build_args("main", "cuda:0", "m1500.pt", END), "m1500.pt", check_sha=False)

    assert (r["remaining_updates"], r["first_iter"], r["last_iter"], r["validate_launch"], r["contract"]) == (500, 1501, 2000, "ok", "walkturn_v1")
    s = L.receipt("smoke2", L.build_args("smoke2", "cuda:1", "m1500.pt", END), "m1500.pt", check_sha=False)

    assert s["remaining_updates"] == 2 and s["args"]["smoke-updates"] == "2"


def test_wrong_parent_sha_is_refused(tmp_path):
    f = tmp_path / "model_1500.pt"
    f.write_bytes(b"not the parent")

    with pytest.raises(ValueError, match="부모 SHA-256|허용표"):
        L.receipt("main", L.build_args("main", "cuda:0", str(f), END), str(f))


def test_the_real_parent_matches_the_card_sha():
    assert REAL_PARENT.exists(), REAL_PARENT
    r = L.receipt("main", L.build_args("main", "cuda:0", str(REAL_PARENT), END), str(REAL_PARENT))

    assert r["parent_sha256"] == L.PARENT_SHA256 == "4d987818c7e25b89e77b7541feca3ddabedd444c5b20651eb29f3681da040d9d"


def test_launch_without_the_extension_or_treatments_is_refused_by_the_contract():
    args = L.build_args("main", "cuda:0", "m1500.pt", END)
    i = args.index("--max_iterations")
    args[i + 1] = "1501"                                                                              # 2001 을 빠뜨린 기동 줄

    with pytest.raises(ValueError, match="0 updates"):
        L.receipt("main", args, "m1500.pt", check_sha=False)


def test_script_calls_the_generator_before_training_and_does_not_hard_code_1501():
    sh = (PKG / "run_ex35.sh").read_text(encoding="utf-8")

    assert sh.index("foothold_s2.ex35_launch") < sh.index("train_sb.py") and '"${ARGS[@]}"' in sh and "--max_iterations 1501" not in sh and "DRY" in sh
    assert "launch_receipt.json" in sh and "foothold_s2 더러움" in sh and "git_head.txt" in sh


# ---- verifier 막음 1 (570042cb): Windows python 출력의 CR 이 mapfile 로 argv 에 남던 것 ----
import shutil
import subprocess
import sys

BASH = shutil.which("bash")
RUN_SH = PKG / "run_ex35.sh"


def _py_print_args_bytes():
    r = subprocess.run([sys.executable, "-m", "foothold_s2.ex35_launch", "main", "cuda:0", "m1500.pt", "--end-by", END, "--print-args", "--no-sha"],
                       cwd=PKG.parent, env={**__import__("os").environ, "PYTHONPATH": str(PKG.parent)}, capture_output=True)
    assert r.returncode == 0, r.stderr.decode("utf-8", "replace")

    return r.stdout


def test_python_prints_args_and_receipt_with_lf_only():
    assert b"\r" not in _py_print_args_bytes()


def test_run_script_strips_cr_and_checks_argv_before_launch():
    s = RUN_SH.read_text(encoding="utf-8")
    assert "tr -d '" + chr(92) + "r'" in s and "launch_argv_repr.txt" in s
    assert s.index("launch_argv_repr") < s.index("train_sb.py")                # 검사가 기동보다 앞


@pytest.mark.skipif(BASH is None, reason="bash 없음")
def test_real_pipe_windows_python_into_git_bash_gives_clean_argv(tmp_path):
    """verifier 재현 그대로: Windows python 출력을 bash mapfile 로 받아 argv 를 repr 로 본다. CR 이 있으면 --command_mode\r 가 된다."""
    snippet = (
        f'cd "{PKG.parent.as_posix()}"; export PYTHONPATH="{PKG.parent.as_posix()}"; '
        f'mapfile -t ARGS < <("{Path(sys.executable).as_posix()}" -m foothold_s2.ex35_launch main cuda:0 m1500.pt --end-by {END} --print-args --no-sha | tr -d \'\r\'); '
        'for A in "${ARGS[@]}"; do printf "%q\n" "$A"; done'
    )
    r = subprocess.run([BASH, "-c", snippet], capture_output=True)
    assert r.returncode == 0, r.stderr.decode("utf-8", "replace")
    lines = r.stdout.decode("utf-8").splitlines()
    assert "--command_mode" in lines and "s2a" in lines and len(lines) >= 27
    assert all("\r" not in x and "\r" not in x and " " not in x for x in lines)


@pytest.mark.skipif(BASH is None, reason="bash 없음")
def test_script_guard_rejects_cr_space_or_empty_arg():
    """스크립트의 검사 case 문만 떼어 CR · 공백 · 빈 값 인자를 넣으면 exit 5."""
    s = RUN_SH.read_text(encoding="utf-8")
    start = s.index('for A in "${ARGS[@]}"')
    end = s.index("done", start) + 4
    loop = s[start:end].replace('>> "$OUT/launch_argv_repr.txt"', ">/dev/null")

    def run(arg):
        r = subprocess.run([BASH, "-c", f'ARGS=(--ok "$X"); {loop}; echo clean'], capture_output=True, env={**__import__("os").environ, "X": arg})

        return r.returncode, r.stdout.decode("utf-8", "replace")

    assert run("s2a")[1].strip().endswith("clean")
    for bad in ("s2a\r", "a b", ""):
        rc, out = run(bad)
        assert rc == 5 and "거절" in out
