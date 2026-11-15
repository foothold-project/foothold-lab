"""S0 연쇄 드라이버의 일 풀어쓰기 시험 (Kit 없음)."""

import os

from foothold_s2.eval import cells, s0_chain


def test_jobs_per_policy_count_and_rows():
    jobs = s0_chain.expand_jobs("e1", "R")
    kinds = {}
    for j in jobs:
        kinds.setdefault(j["name"].split("/")[1].split("_")[0], []).append(j)
    assert len(kinds["axis1"]) == 6 and len(kinds["axis2"]) == 3 and len(kinds["axis3"]) == 23
    assert sorted(j["rows"] for j in kinds["axis1"]) == [600, 600, 600, 1000, 1000, 1000]
    assert all(j["rows"] == 9 for j in kinds["axis2"])
    assert sorted({j["rows"] for j in kinds["axis3"]}) == [300, 600, 700]


def test_axis3_jobs_skip_out_of_range_and_label_assumed_vy():
    jobs = [j for j in s0_chain.expand_jobs("v2", "R", ("axis3",))]
    names = [j["name"] for j in jobs]
    assert not any("sparse_diag" in n for n in names)
    left = [j for j in jobs if "sparse_left" in j["name"]]
    assert len(left) == 1 and cells.VY_ASSUMED_LABEL in left[0]["args"]
    assert "--cmd=0,0.2,0" in left[0]["args"]
    cont_left = [j for j in jobs if "continuous_left" in j["name"]][0]
    assert "--cmd_basis" not in cont_left["args"]


def test_job_names_and_out_dirs_are_unique():
    jobs = []
    for p in ("e1", "v2", "nvidia"):
        jobs += s0_chain.expand_jobs(p, "R")
    assert len({j["name"] for j in jobs}) == len(jobs) == 96
    assert len({os.path.normpath(j["out"]) for j in jobs}) == 96


def test_e1_axis1_override_dir_is_used():
    jobs = s0_chain.expand_jobs("e1", "R", ("axis1",), axis1_dir_override="X/axis1_e1")
    assert all(os.path.normpath(j["out"]).startswith(os.path.normpath("X/axis1_e1")) for j in jobs)


def test_job_done_false_without_outputs(tmp_path):
    job = dict(out=str(tmp_path / "nothing"), raw="axis1_raw.csv", rows=3)
    assert s0_chain.job_done(job) is False


def test_axis2_seed_jobs_have_distinct_seeds_and_dirs():
    jobs = [j for j in s0_chain.expand_jobs("v2", "R", ("axis2",))]
    seeds = [j["args"][j["args"].index("--seed") + 1] for j in jobs]
    assert seeds == ["42", "43", "44"]
    assert [os.path.basename(j["out"]) for j in jobs] == ["axis2", "axis2_s43", "axis2_s44"]


def test_find_bash_returns_an_existing_absolute_path_not_bare_bash():
    path = s0_chain.find_bash()
    assert os.path.isabs(path) and os.path.isfile(path) and os.path.basename(path).lower() == "bash.exe"
    assert "system32" not in path.lower()


def test_negative_commands_are_attached_to_the_flag_and_parse():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--cmd", default="0.5,0,0")
    jobs = [j for j in s0_chain.expand_jobs("e1", "R", ("axis3",))]
    negative = [j for j in jobs if any(a.startswith("--cmd=-") or a.startswith("--cmd=0,-") or a.startswith("--cmd=0,0,-")
                                       for a in j["args"])]
    assert len(negative) >= 4
    for job in jobs:
        flags = [a for a in job["args"] if a == "--cmd" or a.startswith("--cmd=")]
        assert len(flags) == 1 and flags[0].startswith("--cmd=")
        got = parser.parse_known_args([flags[0]])[0].cmd
        assert len(got.split(",")) == 3
