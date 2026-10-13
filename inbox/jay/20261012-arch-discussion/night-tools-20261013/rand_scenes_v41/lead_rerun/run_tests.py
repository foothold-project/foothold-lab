import os
import runpy
import sys
from pathlib import Path
src = Path('C:/isaac/ext/go2_rl_robotlab/_eval/rand_scenes')
work = Path('C:/Users/AI-WS01/.claude/jobs/09bbf294/tmp/codexB2')
assert os.environ.get('CUDA_VISIBLE_DEVICES') == '-1'
sys.path.insert(0, str(src))
import rand_lib as RL
RL.OUT_RAND = str(work / 'out_cpu')
Path(RL.OUT_RAND).mkdir(parents=True, exist_ok=True)
sys.argv = [str(src / 'test_rand_scenes.py'), *sys.argv[1:]]
runpy.run_path(sys.argv[0], run_name='__main__')
