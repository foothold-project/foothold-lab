"""Six targeted source mutations, each caught at its named first invariant."""
from __future__ import annotations

import inspect
from pathlib import Path
import sys
import tempfile
import textwrap
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent))
import s2_launch_common as C
import s2_eval0_checkpoint as K


def mutant(module, function, before, after):
    source = textwrap.dedent(inspect.getsource(function))
    if source.count(before) != 1:
        raise AssertionError("mutation_anchor_missing:" + function.__name__)
    code = source.replace(before, after)
    ns = dict(module.__dict__)
    exec(compile(code, "<mutant>", "exec"), ns)
    return ns[function.__name__]


def escaped(name, fn):
    try:
        fn()
    except C.LaunchHold:
        raise AssertionError(name + ": mutant still rejected the target")
    except Exception as ex:
        raise AssertionError(name + ": wrong first failure " + repr(ex)) from ex
    print(f"CAUGHT {name} first_FAIL={name} want={name}", flush=True)


def main():
    with tempfile.TemporaryDirectory() as td:
        path = Path(td) / "consent.json"
        C.write_json(path, {"scope": "wrong", "by": "lead", "quote": "yes",
            "eula_accepted": "yes", "attending_until_end": "yes",
            "go_for_this_one_run": "yes"})
        bad = mutant(C, C.consent_from, 'value.get("scope") != scope', "False")
        escaped("consent_scope_mismatch_accepted", lambda: bad(path, "s2_eval_kit_smoke_once"))
        old = mutant(C, C.go_fresh, "age < 0 or age > 45", "age < 0")
        escaped("stale_go_accepted", lambda: old({"status": "GO", "checked_epoch": 100.}, clock=lambda: 146.))
        ignore = mutant(C, C.observer_call, "if proc.returncode != 0:", "if False:")
        escaped("observer_failure_ignored", lambda: ignore(Path(td), "record",
            call=lambda *a, **k: SimpleNamespace(returncode=3, stdout="failure", stderr="")))
        retry = mutant(C, C.single_launch_guard, "prior_launches != 0", "False")
        escaped("automatic_retry_added", lambda: retry(1))
        checkpoint = Path(td) / "checkpoint_A_update000000.pt"
        checkpoint.write_text("old")
        reuse = mutant(K, K.fresh_checkpoint_target, "Path(path).exists()", "False")
        escaped("checkpoint_reuse_accepted", lambda: reuse(checkpoint))
        overlap = mutant(K, K.check_eval_seeds, "set(eval_seeds) & set(learning)", "False")
        escaped("eval_seed_overlap_accepted", lambda: overlap((11, 3109, 3119, 3121), (11, 7, 42, 1043)))
    print("MUTANTS 6/6 CAUGHT", flush=True)


if __name__ == "__main__":
    main()
