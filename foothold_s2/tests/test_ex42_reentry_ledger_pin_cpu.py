"""The ledger pin of `ex42_e2_reentry_draft --exit-judge`: the adapter is an exact named field of the approval line (not a substring of it) and the
pinned line number is the line's real place in the ledger at that commit. CPU only, a throwaway git repository stands in for the ledger."""
from __future__ import annotations

import hashlib
import subprocess

import pytest

from foothold_s2.ex42_e1_cap_handoff import LEDGER_PATH, LEDGER_REMOTE_REF
from foothold_s2.tools import ex42_e2_reentry_draft as rd

NEW, OLD, DECISION = "mapgain_two_boundary_e2", "kind_two_window_e2", "E2-EXIT-MAPGAIN-1120"
LINE = (f"2026-11-20 20:36\tlead\t{rd.EXIT_JUDGE_LINE_TAG} 결정 id {DECISION} · 어댑터 {NEW} · 근거: E2 → E3 진입 관문을 옛 {OLD} (성공 · 생존) 에서 이 어댑터로 바꿈")


@pytest.fixture()
def ledger(tmp_path):
    def git(*a):
        return subprocess.run(["git", "-C", str(tmp_path), *a], check=True, capture_output=True, text=True).stdout.strip()
    git("init", "-q")
    git("config", "user.email", "t@example.com")
    git("config", "user.name", "t")
    target = tmp_path / LEDGER_PATH
    target.parent.mkdir(parents=True)
    target.write_text("first\n" + LINE + "\nlast\n", encoding="utf-8")
    git("add", "-A")
    git("commit", "-q", "-m", "ledger")
    commit = git("rev-parse", "HEAD")
    git("update-ref", "refs/remotes/" + LEDGER_REMOTE_REF, commit)
    pin = {"commit": commit, "path": LEDGER_PATH, "line": 2, "line_text": LINE,
           "line_sha256": hashlib.sha256(LINE.encode("utf-8")).hexdigest(), "decision_id": DECISION}
    return tmp_path, pin


def test_the_real_shaped_line_approves_exactly_its_named_adapter(ledger):
    repo, pin = ledger
    assert rd.check_ledger_pin(pin, repo, NEW) == pin


def test_the_old_adapter_named_only_in_the_reason_cannot_be_approved_with_the_same_pin(ledger):
    repo, pin = ledger
    with pytest.raises(ValueError, match="exactly one adapter field"):
        rd.check_ledger_pin(pin, repo, OLD)


def test_a_line_that_names_two_adapter_fields_is_refused(ledger, tmp_path):
    repo, pin = ledger
    two = LINE + f" · 어댑터 {OLD}"
    pin2 = {**pin, "line_text": two, "line_sha256": hashlib.sha256(two.encode("utf-8")).hexdigest()}
    (repo / LEDGER_PATH).write_text("first\n" + two + "\nlast\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "commit", "-qam", "two"], check=True, capture_output=True)
    commit = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"], check=True, capture_output=True, text=True).stdout.strip()
    subprocess.run(["git", "-C", str(repo), "update-ref", "refs/remotes/" + LEDGER_REMOTE_REF, commit], check=True)
    with pytest.raises(ValueError, match="exactly one adapter field"):
        rd.check_ledger_pin({**pin2, "commit": commit}, repo, NEW)


@pytest.mark.parametrize("line", [1, 3, 5, 0, -1, "2"])
def test_a_wrong_line_number_is_refused(ledger, line):
    repo, pin = ledger
    with pytest.raises(ValueError, match="pinned line number"):
        rd.check_ledger_pin({**pin, "line": line}, repo, NEW)


def test_a_decision_id_that_is_only_a_prefix_of_the_field_is_refused(ledger):
    repo, pin = ledger
    with pytest.raises(ValueError, match="decision id"):
        rd.check_ledger_pin({**pin, "decision_id": "E2-EXIT-MAPGAIN"}, repo, NEW)
