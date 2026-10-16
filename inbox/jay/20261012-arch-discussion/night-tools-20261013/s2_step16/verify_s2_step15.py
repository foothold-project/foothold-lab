"""Normal-first CPU verification and separate mutant ledger."""
from __future__ import annotations

import os
import ast
from pathlib import Path
import re
import subprocess
import sys

HERE=Path(__file__).resolve().parent
OUT=HERE/'evidence_s2_step15'
OUT.mkdir(exist_ok=True)
env=dict(os.environ,CUDA_VISIBLE_DEVICES='-1')
for name in ('s2_foot_reward.py','s2_foot_query.py','s2_foot_config.py',
             's2_train_entry_17v.py','s2_train_manifest.py','s2_train_contract.py'):
    ast.parse((HERE/name).read_text(encoding='utf-8'),filename=name)

def run(filename):
    proc=subprocess.run([sys.executable,'-I','-B',str(HERE/filename)],
                        cwd=HERE,env=env,text=True,stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,encoding='utf-8',errors='replace')
    (OUT/(filename+'.log')).write_bytes(proc.stdout.replace('\r\n','\n').encode('utf-8'))
    if proc.returncode:raise SystemExit(filename+' FAIL\n'+proc.stdout)
    return proc.stdout

normal=run('test_s2_step15_foot.py')
normal_count=len(re.findall(r'^test_.*\.\.\. ok$',normal,re.MULTILINE))
if normal_count!=16 or 'Ran 16 tests' not in normal:
    raise SystemExit('normal count mismatch')
mutants=run('test_s2_step15_mutants.py')
mutant_count=len(re.findall(r'^CAUGHT .* first_FAIL=',mutants,re.MULTILINE))
if mutant_count!=10 or 'MUTANTS 10/10 CAUGHT' not in mutants:
    raise SystemExit('mutant count mismatch')
print(f'NORMAL {normal_count} PASS')
print(f'MUTANTS {mutant_count}/10 CAUGHT')
print('STATIC_AST 6 PASS')
print('CPU_ONLY CUDA_VISIBLE_DEVICES=-1; Kit and GPU not launched')
