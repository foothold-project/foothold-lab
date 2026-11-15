"""Independent CPU result oracle for weight, finite and iteration accounting claims."""
from __future__ import annotations
import copy
import json
import math
from pathlib import Path
import tempfile
import torch

from s2_plumbing import PlumbingHold,verify_result
from s2_train_contract import canonical
from test_s2_step6_contract import make,PlumbingOwner


def check_bad(label,m,result,root,want):
    try:verify_result(m,result,root)
    except PlumbingHold as ex:assert str(ex)==want,(label,str(ex),want)
    else:raise AssertionError(label)
    print("PASS reject_"+label)


def test():
    with tempfile.TemporaryDirectory(prefix="s2_step6_proof_") as td:
        root=Path(td);m,_=make(root)
        Path(m["manifest_path"]).write_bytes(canonical(m))
        owner=PlumbingOwner()
        owner.launch(m["entry_argv"],root,{"OMNI_KIT_ACCEPT_EULA":"YES",
                "CUDA_VISIBLE_DEVICES":"0"},root/"fixture.log")
        output=Path(m["plan"]["out_root"])
        result=json.loads((output/"result.json").read_text(encoding="utf-8"))
        assert verify_result(m,result,output)
        print("PASS plumbing_result_known_answer")
        checkpoint=output/f"PLUMBING_ONLY_checkpoint_{m['plan']['updates']:06d}.pt"
        original=checkpoint.read_bytes()
        state=torch.load(checkpoint,map_location="cpu",weights_only=False)
        state["plumbing_meta"]["plumbing_only"]=False
        torch.save(state,checkpoint)
        check_bad("checkpoint_content_unmarked",m,result,output,"plumbing_checkpoint_content")
        checkpoint.write_bytes(original)
        for label,change,want in (
            ("weights_unchanged",lambda x:x.update(parameter_changed=False),"weights_unchanged"),
            ("parameter_hash_equal",lambda x:x.update(parameter_sha256_after=x["parameter_sha256_before"]),"weights_unchanged"),
            ("nan_count",lambda x:x.update(nonfinite_count=1),"nonfinite_record"),
            ("nan_loss",lambda x:x["records"][0].update(loss=math.nan),"nonfinite_loss"),
            ("inf_loss",lambda x:x["records"][0].update(loss=math.inf),"nonfinite_loss"),
            ("zero_gradient",lambda x:x["records"][0].update(gradient_norm_min=0.),"zero_gradient_or_lr"),
            ("roundtrip_false",lambda x:x["roundtrip"].update(same_output=False),"checkpoint_output_mismatch"),
            ("roundtrip_action_diff",lambda x:x["roundtrip"].update(action_max_abs_diff=1.),"checkpoint_output_mismatch"),
            ("environment_steps_mixed",lambda x:x.update(environment_steps=x["executed_updates"]),"iteration_step_accounting"),
            ("rollout_steps_missing",lambda x:x.pop("rollout_steps"),"iteration_step_accounting"),
            ("wrong_freeze",lambda x:x["records"][0].update(encoder_frozen=False),"encoder_freeze_schedule"),
            ("discarded",lambda x:x.update(discarded_transitions=1),"discarded_transitions"),
            ("sensor_read_short",lambda x:x.update(sensor_reads_total=0),"sensor_read_accounting"),
            ("critic_only",lambda x:x["records"][0]["group_changes"]["actor"].update(changed_tensors=0),"group_path_disconnected"),
        ):
            altered=copy.deepcopy(result);change(altered)
            check_bad(label,m,altered,output,want)


if __name__=="__main__":test()
