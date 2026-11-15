import os
import runpy
import sys
from pathlib import Path
copy = Path(sys.argv[1]).resolve()
work = Path('C:/Users/AI-WS01/.claude/jobs/09bbf294/tmp/codexB')
real_eval = Path('C:/isaac/ext/go2_rl_robotlab/_eval')
assert os.environ.get('CUDA_VISIBLE_DEVICES') == '-1'
assert copy.is_relative_to(work.resolve())
sys.path.insert(0, str(copy))
import rand_lib as RL
RL.EVAL = str(real_eval)
RL.SLOT_SCRIPT = str(real_eval / 'isaac_slot_v3.py')
RL.ISOLATE_SCRIPT = str(real_eval / 'usd_isolate_run_v3.py')
RL.LEGACY_REGISTRY = str(real_eval / 'slot' / 'isaac_usd_registry.json')
RL.V3_REGISTRY = str(real_eval / 'slot' / 'isaac_usd_registry_v3.json')
RL.OUT_RAND = str(work / 'mutation_outputs' / copy.name)
Path(RL.OUT_RAND).mkdir(parents=True, exist_ok=True)
sys.argv = [str(copy / 'test_rand_scenes.py'), *sys.argv[2:]]
runpy.run_path(sys.argv[0], run_name='__main__')
