"""Separate CPU mutation prepass. A mutation counts only when first FAIL matches want."""
from __future__ import annotations

import copy
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))

from s2_eval_scope import validate
from s2_eval_pre_reset import PreResetStep
from s2_eval_case_fingerprint import tile_mesh_sha
from test_s2_step14_scope import TestScope
from test_s2_step14_hooks import FakeRaw
from test_s2_step14_usd import TestUsdEvidence
from s2_eval_usd_provenance import evidence as usd_evidence


def main():
    fixture = TestScope("test_known_answer_scope")
    fixture.setUp()
    caught = []
    def check(name, want, operation):
        try:
            operation()
        except Exception as ex:
            got = str(ex)
            if want not in got:
                raise AssertionError(f"{name}: first_FAIL={got!r}, want={want!r}") from ex
            caught.append({"name": name, "first_FAIL": got, "want": want})
        else:
            raise AssertionError(name + ": mutation survived")
    try:
        base = fixture.m
        check("argv_device", "exact_argv", lambda: (lambda m: validate(m, fixture.approve(m), now=100., fixture=True))(
            {**base, "argv": [*base["argv"][:-1], "cpu"]}))
        check("training_update", "evaluation_only_scope", lambda: (lambda m: validate(m, fixture.approve(m), now=100., fixture=True))(
            {**base, "training_updates": 1}))
        check("single_conversion_limit", "evaluation_conversion_scope", lambda: (lambda m: validate(
            m, fixture.approve(m), now=100., fixture=True))({**base, "expect_conversions": "1"}))
        check("approval_digest", "approval_digest_or_expiry", lambda: validate(base,
            {**fixture.approve(base), "manifest_sha256": "0"*64}, now=100., fixture=True))
        changed = copy.deepcopy(base)
        changed["code_hashes"]["s2_eval_kit_adapter.py"] = "0"*64
        check("code_closure", "code_closure_sha256", lambda: validate(
            changed, fixture.approve(changed), now=100., fixture=True))
        raw = FakeRaw()
        class WrongDone:
            def step(self, action):
                raw._reset_idx([0])
                return None, None, [False, True], {}
        check("reset_env_identity", "reset_ids_vs_done", lambda: PreResetStep(
            WrongDone(), raw, lambda: copy.deepcopy(raw.state), num_envs=2).step_recorded(None, env_index=0))
        check("empty_tile", "tile_mesh_empty", lambda: tile_mesh_sha([], center_xy=(0, 0), size_xy=(8, 8)))
        usd = TestUsdEvidence("test_two_conversions_within_cap")
        usd.setUp()
        try:
            usd.state["conversions"] = 9
            usd.rows = usd.rows * 4 + usd.rows[:1]
            usd.save()
            check("ninth_converter", "usd_isolation_state_or_count", lambda: usd_evidence(
                usd.root, usd.asset, usd.refs, max_entries=8))
        finally:
            usd.doCleanups()
        print(json.dumps({"mutants_CAUGHT": caught}, ensure_ascii=False, sort_keys=True))
    finally:
        fixture.doCleanups()


if __name__ == "__main__":
    main()
