"""CPU regression for the native v2 recorder's real RSL-RL checkpoint load path."""

import ast
import io
import os
from pathlib import Path
from types import MethodType, SimpleNamespace
from unittest.mock import patch

os.environ["CUDA_VISIBLE_DEVICES"] = "-1"
import torch  # noqa: E402
from rsl_rl.runners import OnPolicyRunner  # noqa: E402


def main():
    source = Path(os.environ.get("CE12_NATIVE_V2_SOURCE", Path(__file__).with_name("dump_native_v2.py")))
    tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
    loads = [n for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
             and isinstance(n.func.value, ast.Name) and n.func.value.id == "runner" and n.func.attr == "load"]
    assert len(loads) == 1, "v2_runner_load_call: expected exactly one recorder load"
    assert any(isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "dev" for t in n.targets)
               and isinstance(n.value, ast.Attribute) and n.value.attr == "device"
               and isinstance(n.value.value, ast.Name) and n.value.value.id == "raw_env" for n in ast.walk(tree)), \
        "v2_recorder_device: dev must be raw_env.device"

    # Tag a CPU storage as CUDA:1 when saving. Loading still uses PyTorch's real
    # restore_location and _validate_device code, with device_count mocked to one.
    def tag_cuda1(storage):
        return "cuda:1" if storage.device.type == "cpu" else None

    torch.serialization.register_package(0, tag_cuda1, lambda storage, location: None)
    ckpt = io.BytesIO()
    torch.save({"model_state_dict": {"w": torch.tensor([3.0])}, "optimizer_state_dict": {},
                "iter": 7, "infos": {"test": True}}, ckpt)

    class Policy:
        def load_state_dict(self, state):
            self.w = state["w"]
            return True

    policy = Policy()
    runner = SimpleNamespace(alg=SimpleNamespace(policy=policy, optimizer=SimpleNamespace(load_state_dict=lambda _d: None)),
                             current_learning_iteration=0)
    runner.load = MethodType(OnPolicyRunner.load, runner)

    with patch.object(torch.cuda, "is_available", return_value=True), patch.object(torch.cuda, "device_count", return_value=1):
        ckpt.seek(0)
        try:
            runner.load(ckpt)
        except RuntimeError as exc:
            assert "Attempting to deserialize object on CUDA device 1 but torch.cuda.device_count() is 1" in str(exc), \
                f"cuda1_control_wrong_failure: {exc}"
            print("CONTROL real OnPolicyRunner.load without map_location rejects CUDA:1 storage at restore_location")
        else:
            raise AssertionError("cuda1_control_missing_failure: unmapped CUDA:1 storage loaded")

        ckpt.seek(0)
        call = ast.Expression(body=loads[0])
        ast.fix_missing_locations(call)
        try:
            eval(compile(call, str(source), "eval"), {"runner": runner, "ckpt": ckpt, "dev": "cpu"})
        except RuntimeError as exc:
            if "Attempting to deserialize object on CUDA device 1 but torch.cuda.device_count() is 1" in str(exc):
                raise AssertionError("v2_runner_load_map_location: recorder call reached CUDA:1 restore_location") from exc
            raise

    assert policy.w.device.type == "cpu" and policy.w.item() == 3.0, "v2_runner_load_result: CPU tensor mismatch"
    assert runner.current_learning_iteration == 7, "v2_runner_load_iteration: wrong checkpoint"
    print("PASS v2_runner_load_map_location: real runner loaded CUDA:1 tagged storage onto recorder CPU device")


if __name__ == "__main__":
    main()
