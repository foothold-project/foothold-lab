# Thin wrapper around RoboGauge v1.1.9 robogauge/scripts/run.py.
# Only differences from run.py:
#   1) GPUs are hidden (CUDA_VISIBLE_DEVICES=-1); torch in the robogauge env is the CPU build anyway.
#   2) Logs go to $RG_LOGS_DIR instead of <RoboGauge>/logs, so results land under _eval/out/robogauge.
# The patch is applied at module top level so spawned worker processes (multiprocessing 'spawn'
# re-imports this file as __mp_main__) get the same log root.
import os
import sys

os.environ["CUDA_VISIBLE_DEVICES"] = "-1"
os.environ.setdefault("MUJOCO_GL", "glfw")
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"
os.environ["TORCH_CPP_LOG_LEVEL"] = "ERROR"
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import robogauge  # noqa: E402

_logs = os.environ.get("RG_LOGS_DIR")
if _logs:
    robogauge.ROBOGAUGE_LOGS_DIR = _logs

from robogauge.tasks import *  # noqa: E402,F401,F403
from robogauge.tasks.pipeline import *  # noqa: E402,F401,F403

# Optional: video size only (no effect on physics or scores). Default stays 640x480.
if os.environ.get("RG_RENDER_W") and os.environ.get("RG_RENDER_H"):
    from robogauge.tasks.simulator.mujoco_config import MujocoConfig as _MC
    _MC.render.width = int(os.environ["RG_RENDER_W"])
    _MC.render.height = int(os.environ["RG_RENDER_H"])
from robogauge.utils.task_register import task_register  # noqa: E402
from robogauge.utils.helpers import parse_args  # noqa: E402


if __name__ == "__main__":
    import robogauge.utils.logger as _lg
    assert _logs is None or _lg.ROBOGAUGE_LOGS_DIR == _logs, "log dir patch did not apply"
    args = parse_args()
    if args.stress_benchmark:
        StressPipeline(args).run()
    elif args.multi:
        MultiPipeline(args).run()
    elif args.search_max_level:
        LevelPipeline(args).run()
    else:
        pipeline = task_register.make_pipeline(args=args)
        pipeline.run()
