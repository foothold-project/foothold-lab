"""Full CLI checks; pure-function mutation copies intentionally exclude CLIs."""
from pathlib import Path
import subprocess
import sys
import pytest


@pytest.mark.parametrize('name',['boundary_read.py','replay_de8.py'])
def test_cli_allows_new_run_250(name):
    proc=subprocess.run([sys.executable,'-B',str(Path(__file__).with_name(name)),
                         '--effective-from','250','--help'],capture_output=True,text=True)
    assert proc.returncode==0,proc.stderr
    assert '{250,750,1000}' in proc.stdout
