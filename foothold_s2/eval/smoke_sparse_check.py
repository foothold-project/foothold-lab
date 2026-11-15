"""smoke_sparse_start.sh 의 끝 확인. map_modes.json 이 없으면 여기서 실패한다(Isaac 종료 코드는 예외 뒤에도 0 일 수 있다)."""

import glob
import json
import sys

import numpy as np

out = sys.argv[1]
mm = json.load(open(out + "/map_modes.json", encoding="utf-8"))
npz = glob.glob(out + "/arrays_*.npz")

assert len(npz) == 1, npz
a = np.load(npz[0])
assert a["start_support"].shape == (64,) and a["start_support"].dtype == bool, a["start_support"].shape
by_kind = next(iter(mm["modes"].values()))["fwd1.0"]["by_kind"]
assert sum(d["envs"] for d in by_kind.values()) == 64 and all(("start_offbeam" in d) == (k == "balance_beams") for k, d in by_kind.items())
print("SMOKE_OK start_support", int(a["start_support"].sum()), "of 64 on support; terrain_geometry_sha256.total", mm["terrain_geometry_sha256"]["total"][:12])
