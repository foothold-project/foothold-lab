"""Real Windows Job Object CPU natural-exit smoke. No process is killed."""
import os
from pathlib import Path
import sys
import time
import tempfile
from s2_job_owner import JobOwner,WinKernel


def main():
    assert os.environ.get("CUDA_VISIBLE_DEVICES")=="-1"
    owner=JobOwner(WinKernel())
    log=Path(tempfile.mkdtemp(prefix="s2_a2_job_"))/"child.log"
    pid=owner.launch([sys.executable,"-B","-c","print('fixture exit')"],Path(__file__).parent,
                     {**os.environ,"CUDA_VISIBLE_DEVICES":"-1"},log_path=log)
    end=time.monotonic()+20
    while owner.active_count() and time.monotonic()<end:time.sleep(.02)
    assert owner.active_count()==0 and owner.exit_code()==0,(pid,owner.active_count(),owner.exit_code())
    owner.close()
    print("PASS job_object_suspended_assign_natural_exit",pid)
    assert "fixture exit" in log.read_text(encoding="utf-8")
    print("PASS child_stdout_log_redirect")

if __name__=="__main__":main()
