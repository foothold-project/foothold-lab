"""Static launch parity with the executed 1043 path and A4 r2 owner pattern."""
from __future__ import annotations
import ast
from pathlib import Path

HERE=Path(__file__).resolve().parent
EVAL=Path("C:/isaac/ext/go2_rl_robotlab/_eval")
A4=Path("C:/Users/AI-WS01/Desktop/jay/인공지능사관학교/foothold-lab/inbox/jay/20261012-arch-discussion/night-tools-20261013/s2_step4a4_unattended")

def audit():
    shell=(EVAL/"branch/night_20261013_cmdr1043_v3.sh").read_text(encoding="utf-8")
    branch=(EVAL/"branch/branch_run.py").read_text(encoding="utf-8")
    slot=(EVAL/"isaac_slot_v3.py").read_text(encoding="utf-8")
    a4=(A4/"s2_unattended_launch.py").read_text(encoding="utf-8")
    entry=(HERE/"s2_train_entry_17v.py").read_text(encoding="utf-8")
    launch=(HERE/"s2_train_launch.py").read_text(encoding="utf-8")
    job=(HERE/"s2_job_owner.py").read_text(encoding="utf-8")
    contract=(HERE/"s2_train_contract.py").read_text(encoding="utf-8")
    tree=ast.parse(entry)
    imports={}
    for node in tree.body:
        if isinstance(node,ast.Import):
            for item in node.names:imports[item.name.split(".")[0]]=node.lineno
    kit_lines=[node.lineno for node in ast.walk(tree) if isinstance(node,ast.ImportFrom) and node.module=="isaaclab.app"]
    kit=min(kit_lines) if kit_lines else -1
    return {
      "baseline_1043_env":"OMNI_KIT_ACCEPT_EULA=YES PYTHONUNBUFFERED=1" in shell and
          "CUDA_DEVICE_ORDER=PCI_BUS_ID CUDA_VISIBLE_DEVICES=0" in shell,
      "baseline_1043_preload":"import h5py" in branch and "import tensordict" in branch and
          branch.index("import h5py")<branch.index("from isaaclab.app import AppLauncher") and
          branch.index("import tensordict")<branch.index("from isaaclab.app import AppLauncher"),
      "baseline_1043_slot_cwd":"cd \"$(dirname \"$0\")\"" in shell and
          "subprocess.Popen(cmd, env=env)" in slot,
      "baseline_a4_stdin":"stdin=subprocess.DEVNULL" in a4 and "env={**os.environ, **ISAAC_ENV}" in a4,
      "candidate_preload_h5py":imports.get("h5py",10**9)<kit,
      "candidate_preload_torch":imports.get("torch",10**9)<kit,
      "candidate_preload_tensordict":imports.get("tensordict",10**9)<kit,
      "candidate_app_launcher":"AppLauncher.add_app_launcher_args(ap)" in entry and
          "launcher=AppLauncher(a)" in entry,
      "candidate_eula":"\"OMNI_KIT_ACCEPT_EULA\":\"YES\"" in launch and
          "approval.get(\"eula_accepted\") is not True" in contract,
      "candidate_unbuffered":"\"PYTHONUNBUFFERED\":\"1\"" in launch,
      "candidate_cuda_order":"\"CUDA_DEVICE_ORDER\":\"PCI_BUS_ID\"" in launch,
      "candidate_visible_zero":"\"CUDA_VISIBLE_DEVICES\":\"0\"" in launch,
      "candidate_cwd":"owner.launch(argv,HERE,child_environment(os.environ),log_path=log)" in launch,
      "candidate_stdin_nul":"stdin_fd=os.open(os.devnull,os.O_RDONLY|os.O_BINARY)" in job and
          "si.hStdInput=stdin_handle" in job,
      "candidate_argv":"if entry_argv(m)!=m.get(\"entry_argv\")" in contract and
          "if argv!=manifest.get(\"entry_argv\",[])[3:]" in entry,
      "candidate_headless_cuda0":"--headless\",\"--device\",\"cuda:0" in contract and
          "a.device!=\"cuda:0\"" in entry,
      "candidate_owned_family":"self.kernel.assign(self.job,process)" in job and
          "self.kernel.resume(thread)" in job and "owner.stop_owned(wait_seconds=10.)" in launch,
    }
