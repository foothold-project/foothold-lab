"""Actual E1 CPU PPO plumbing iterations on known-answer synthetic sensor input."""
from __future__ import annotations
import json
import hashlib
from pathlib import Path
import sys
import tempfile
import torch

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE/"s2_step3"))
from test_s2_step3_entry import args
from s2_train_entry_17v import execute_plumbing
from s2_plumbing import WARNING,verify_result
from s2_train_contract import PARENT_SHA,canonical


def test():
    torch.set_num_threads(2)
    with tempfile.TemporaryDirectory(prefix="s2_step6_ppo_") as td:
        root=Path(td)
        for arm,updates,mode,want_frozen in (("A",1,"full_freeze",[True]),
                                              ("B",2,"schedule",[True,False])):
            a=args(root/arm,updates=updates,mode=mode,
                   W=1 if mode=="schedule" else None,
                   r=.5 if mode=="schedule" else None)
            a.arm=arm;a.stage="plumbing";a.input_path="synthetic_known_answer"
            a.checkpoint_interval=updates
            m={"chain_id":"cpu_structural_fixture","input_path":a.input_path,
               "plan":{"arm":arm,"updates":updates,"rollout_steps":a.rollout_steps,
                       "num_envs":a.num_envs,"epochs":a.epochs,"minibatches":a.minibatches,
                       "encoder_mode":mode,"freeze_updates":a.freeze_updates,
                       "parent_sha256":PARENT_SHA,"out_root":str(root/arm)}}
            digest=hashlib.sha256(canonical(m)).hexdigest()
            result=execute_plumbing(a,input_path=a.input_path,
                                    manifest_sha256=digest,cpu_dry=True)
            assert result["status"]=="RUN_COMPLETE_UNVERIFIED",result
            assert result["executed_updates"]==updates
            assert result["rollout_steps"]==2 and result["environment_steps"]==updates*2*2
            assert result["optimizer_steps_actual"]==updates
            assert result["parameter_changed"] is True
            assert result["gradient_norm_min"]>0
            assert result["nonfinite_count"]==0
            assert result["roundtrip"]["same_output"] is True
            assert [x["encoder_frozen"] for x in result["records"]]==want_frozen
            assert all(x["learning_rate"]>0 and x["nonfinite_count"]==0 for x in result["records"])
            assert WARNING in (root/arm/"PLUMBING_ONLY.txt").read_text(encoding="utf-8")
            for n in (0,updates):assert (root/arm/f"PLUMBING_ONLY_checkpoint_{n:06d}.pt").is_file()
            assert not list((root/arm).glob("checkpoint_*.pt"))
            assert json.loads((root/arm/"result.json").read_text(encoding="utf-8"))==result
            assert verify_result(m,result,root/arm)
            print(f"PASS actual_E1_CPU_{arm}_{updates}_PPO_iterations_roundtrip")


if __name__=="__main__":test()
