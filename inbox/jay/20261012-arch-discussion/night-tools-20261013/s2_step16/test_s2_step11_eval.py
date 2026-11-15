"""Real E1 parent on CPU, S2Runner.save, strict S2 load and fixed forward."""
from __future__ import annotations

import copy
from pathlib import Path
import tempfile
from types import SimpleNamespace

import torch

from s2_eval_cpu import (EvalContractError,known_maps,strict_load,
                         compare_training_forward,sha)
from s2_policy import build_s2,load_parent_cpu,E1_CKPT,make_optimizer
from s2_runner_17v import S2Runner,_hash_plan


def saved_runner(policy, mode):
    runner=S2Runner.__new__(S2Runner)
    runner.mode=mode
    runner.plan={"mode":mode,"ppo":{"num_envs":2,"rollout_steps":2},
                 "encoder_mode":"full_freeze","freeze_updates":None,
                 "encoder_lr_ratio":None,"geometry_tolerance_m":.002}
    runner.plan_sha256=_hash_plan(runner.plan)
    runner.env_config_sha256="a"*64
    runner.discarded_transitions=0
    runner.encounters=SimpleNamespace(states={})
    optimizer, control = make_optimizer(policy, .001, encoder_mode="full_freeze")
    runner.algo=SimpleNamespace(policy=policy,optimizer=optimizer,ctl=control)
    return runner


def expect_error(fn,want):
    try:fn()
    except EvalContractError as ex:assert str(ex).startswith(want),(str(ex),want)
    else:raise AssertionError(want+" accepted")


def run():
    torch.set_num_threads(2)
    maps=known_maps()
    assert maps["A"].shape==(2,374) and maps["B"].shape==(2,374)
    assert torch.all(maps["A"]==0) and maps["B"][0,0]==1 and torch.isclose(
        maps["B"][1,1],torch.tensor(-.2))
    print("PASS known_maps")
    parent,meta=load_parent_cpu(E1_CKPT)
    assert meta["dims"]=={"policy":450,"critic":275,"single_obs":45,"actions":12,"latent":32}
    print("PASS parent_dims")
    with tempfile.TemporaryDirectory(prefix="s2_eval_cpu_") as td:
        for mode in ("A","B"):
            policy,_,_=build_s2(mode,parent=parent,map_init_seed=0)
            # Learned map column must be exercised by the B policy, not only the zero initialization.
            if mode=="B":
                with torch.no_grad():policy.actor_in_map.weight.fill_(.0001)
            policy.eval()
            runner=saved_runner(policy,mode)
            path=Path(td)/(mode+".pt")
            runner.save(path)
            digest=sha(path)
            loaded,info=strict_load(path,expected_sha256=digest,parent=parent,mode=mode,
                                    expected_env_config_sha256="a"*64,map_init_seed=0)
            assert info["format"]=="s2-17v-checkpoint-only"
            assert set(info["top_level_keys"])=={"format","mode","plan","plan_sha256",
                "env_config_sha256","policy","s2_control","optimizer","rng",
                "resume_supported","discarded_transitions","encounter_states"}
            assert info["policy_tensor_count"]==len(policy.state_dict())
            assert info["policy_shapes_dtypes"]["actor_in.weight"]=={
                "shape":[512,77],"dtype":"torch.float32"}
            assert info["policy_shapes_dtypes"]["actor_in_map.weight"]=={
                "shape":[512,64],"dtype":"torch.float32"}
            out=compare_training_forward(policy,loaded,meta["dims"],mode)
            assert out["action_shape"]==[2,12] and out["value_shape"]==[2,1]
            assert out["action_equal"] and out["value_equal"]
            print("PASS strict_forward_"+mode)
            with torch.no_grad():loaded.actor_rest[-1].bias[0]+=.1
            expect_error(lambda:compare_training_forward(policy,loaded,meta["dims"],mode),
                         "action_forward_mismatch")
            print("PASS reject_action_drift_"+mode)
            expect_error(lambda:strict_load(path,expected_sha256="0"*64,parent=parent,mode=mode,
                         expected_env_config_sha256="a"*64,map_init_seed=0),"checkpoint_hash")
            print("PASS reject_hash_"+mode)
            state=torch.load(path,map_location="cpu",weights_only=False)
            state["policy"]["actor_in_map.weight"]=torch.zeros(512,63)
            bad=Path(td)/(mode+"_bad.pt");torch.save(state,bad)
            expect_error(lambda:strict_load(bad,expected_sha256=sha(bad),parent=parent,mode=mode,
                         expected_env_config_sha256="a"*64,map_init_seed=0),"policy_shape_dtype")
            print("PASS reject_shape_"+mode)


if __name__=="__main__":run()
