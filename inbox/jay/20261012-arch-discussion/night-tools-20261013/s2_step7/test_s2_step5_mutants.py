"""Parity source mutants. Each mutant runs only after the normal audit passes."""
from __future__ import annotations
from pathlib import Path
import shutil
import tempfile
import s2_launch_parity as parity

MUTANTS=(
    ("missing_eula_env","s2_train_launch.py","\"OMNI_KIT_ACCEPT_EULA\":\"YES\"",
     "\"OMNI_KIT_ACCEPT_EULA\":\"NO\"","candidate_eula"),
    ("missing_unbuffered_env","s2_train_launch.py","\"PYTHONUNBUFFERED\":\"1\"",
     "\"PYTHONUNBUFFERED\":\"0\"","candidate_unbuffered"),
    ("wrong_visible_gpu","s2_train_launch.py","\"CUDA_VISIBLE_DEVICES\":\"0\"",
     "\"CUDA_VISIBLE_DEVICES\":\"1\"","candidate_visible_zero"),
    ("h5py_after_kit","s2_train_entry_17v.py","import h5py  # noqa: F401",
     "import h5py_late  # noqa: F401","candidate_preload_h5py"),
    ("tensordict_after_kit","s2_train_entry_17v.py","import tensordict  # noqa: F401",
     "import tensordict_late  # noqa: F401","candidate_preload_tensordict"),
    ("unapproved_argv","s2_train_contract.py","if entry_argv(m)!=m.get(\"entry_argv\")",
     "if False and entry_argv(m)!=m.get(\"entry_argv\")","candidate_argv"),
    ("no_job_assign","s2_job_owner.py","self.kernel.assign(self.job,process)",
     "self.kernel.no_assign(self.job,process)","candidate_owned_family"),
)


def test():
    normal=parity.audit()
    assert len(normal)==17 and all(normal.values()),normal
    print("PASS normal_first_launch_parity_17")
    original=parity.HERE
    names={x[1] for x in MUTANTS}|{"s2_train_entry_17v.py","s2_train_launch.py",
                                  "s2_job_owner.py","s2_train_contract.py"}
    try:
        for label,file,old,new,want in MUTANTS:
            with tempfile.TemporaryDirectory(prefix="s2_step5_mutant_") as td:
                folder=Path(td)
                for name in names:shutil.copyfile(original/name,folder/name)
                path=folder/file
                source=path.read_text(encoding="utf-8")
                assert source.count(old)==1,(label,source.count(old))
                path.write_text(source.replace(old,new,1),encoding="utf-8")
                parity.HERE=folder
                observed=parity.audit()
                first=next((name for name,passed in observed.items() if not passed),None)
                assert first==want,(label,first,want)
                print(f"CAUGHT {label} first_FAIL={first} want={want}")
    finally:parity.HERE=original


if __name__=="__main__":test()
