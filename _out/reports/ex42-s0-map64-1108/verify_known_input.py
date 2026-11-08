"""CPU oracle: call the actual evaluator's summarize, then recover signed vy."""
import hashlib
import importlib.util
import json
from pathlib import Path

import numpy as np


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


root = Path(__file__).resolve().parent
producer_path = Path("D:/mai-wt/foothold-lab/runner-ex42-w65-7916a52/foothold_s2/eval/map_mode_cells.py")
producer = module("actual_map_mode_cells", producer_path)
consumer = module("comparison_consumer", root / "recompute.py")
vx = np.array([[.3, -.2, .6], [.1, .2, .2], [999., .4, -.2]], dtype=np.float32)
vy = np.array([[-.4, .5, -.1], [-.2, .3, -.3], [999., .1, -.5]], dtype=np.float32)
alive = np.array([[1,1,1], [1,1,1], [0,1,1]], dtype=bool)
tiles = [{"env":i, "kind":"flat", "level":0, "column":i} for i in range(3)]
results = []
for cx,cy in ((0.,.5),(0.,-.5),(.5,.5),(.5,-.5),(-.5,.5),(-.5,-.5)):
    row = producer.summarize([cx,cy,0.], tiles, vx, vy, np.zeros_like(vx), alive, alive[-1], .02)
    for i, env in enumerate(row["per_env"]):
        vx_int = float((vx[:,i]*alive[:,i]).sum()*.02)
        actual = consumer.reconstruct_vy([cx,cy,0.], env["command_xy_projection_integral_m"], vx_int, env["samples_alive"], .02)
        expected = [-.3,.3,-.3][i]
        assert abs(actual-expected)<1e-6, (cx,cy,i,actual,expected)
        results.append({"cx":cx,"cy":cy,"env":i,"expected":expected,"actual":actual})
assert len(results)==18
receipt = {"status":"PASS", "producer":str(producer_path),
           "producer_sha256":hashlib.sha256(producer_path.read_bytes()).hexdigest(),
           "cases":len(results), "max_error_mps":max(abs(r['actual']-r['expected']) for r in results),
           "scope":"six signed command pairs x three envs; actual summarize; post-fall extreme excluded",
           "results":results}
(root / "known_producer_test.json").write_text(json.dumps(receipt,indent=2)+"\n",encoding="utf-8",newline="\n")
print(json.dumps({k:v for k,v in receipt.items() if k!='results'}))
