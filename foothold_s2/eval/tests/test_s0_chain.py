"""S0 연쇄 드라이버의 일 풀어쓰기 시험 (Kit 없음)."""

import os

from foothold_s2.eval import cells, s0_chain


def test_jobs_per_policy_count_and_rows():
    jobs = s0_chain.expand_jobs("e1", "R")
    kinds = {}
    for j in jobs:
        kinds.setdefault(j["name"].split("/")[1], []).append(j)
    assert len(kinds["axis1"]) == 6 and len(kinds["axis2"]) == 1 and len(kinds["axis3"]) == 23
    assert sorted(j["rows"] for j in kinds["axis1"]) == [600, 600, 600, 1000, 1000, 1000]
    assert kinds["axis2"][0]["rows"] == 9
    assert sorted({j["rows"] for j in kinds["axis3"]}) == [300, 600]


def test_axis3_jobs_skip_out_of_range_and_label_assumed_vy():
    jobs = [j for j in s0_chain.expand_jobs("v2", "R", ("axis3",))]
    names = [j["name"] for j in jobs]
    assert not any("sparse_diag" in n for n in names)
    left = [j for j in jobs if "sparse_left" in j["name"]]
    assert len(left) == 1 and cells.VY_ASSUMED_LABEL in left[0]["args"]
    assert "0,0.2,0" in left[0]["args"]
    cont_left = [j for j in jobs if "continuous_left" in j["name"]][0]
    assert "--cmd_basis" not in cont_left["args"]


def test_job_names_and_out_dirs_are_unique():
    jobs = []
    for p in ("e1", "v2", "nvidia"):
        jobs += s0_chain.expand_jobs(p, "R")
    assert len({j["name"] for j in jobs}) == len(jobs) == 90
    assert len({os.path.normpath(j["out"]) for j in jobs}) == 90


def test_e1_axis1_override_dir_is_used():
    jobs = s0_chain.expand_jobs("e1", "R", ("axis1",), axis1_dir_override="X/axis1_e1")
    assert all(os.path.normpath(j["out"]).startswith(os.path.normpath("X/axis1_e1")) for j in jobs)


def test_job_done_false_without_outputs(tmp_path):
    job = dict(out=str(tmp_path / "nothing"), raw="axis1_raw.csv", rows=3)
    assert s0_chain.job_done(job) is False
