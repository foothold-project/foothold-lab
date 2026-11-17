"""기록기 본체 (ex42_mapfit_record_child 가 쓴다 · Kit 없이 시험하려고 분리). StartPerception._advance 를 감싸 TRNet 입력 · 정답을 적고 값은 그대로 돌려준다."""
from __future__ import annotations

import numpy as np

from foothold_s2.models import start_perception as sp


class Recorder:
    def __init__(self) -> None:
        self.rec = {"env": [], "call": [], "first": [], "depth2": [], "z_prop": [], "gt": [], "grav": []}
        self.calls = 0
        self._orig = None

    def install(self) -> None:
        orig = self._orig = sp.StartPerception._advance
        me = self

        def advance(self_, h_prop, h_terr, hist, depth2, tick, first, use_gt, gt_map, *rest):
            result = orig(self_, h_prop, h_terr, hist, depth2, tick, first, use_gt, gt_map, *rest)
            me.add(result[0], depth2, tick, first, gt_map, hist)
            return result
        sp.StartPerception._advance = advance

    def uninstall(self) -> None:
        if self._orig is not None:
            sp.StartPerception._advance = self._orig
            self._orig = None

    def add(self, z_prop, depth2, tick, first, gt_map, hist=None) -> None:
        """h_terr 가 바뀌는 스텝 (깊이 틱 또는 리셋 직후) 의 env 만 적는다. z_prop = _advance 가 돌려준 새 h_prop (TRNet.step 이 받는 값). grav = 이 스텝 몸 틀 중력 방향 (관측 45 칸의 3:6 열 · hist[:, 0] = 최신 · B2a 기하 채널의 몸 기울기 보정용)."""
        self.calls += 1
        sel = (tick | first).detach().bool()
        if not bool(sel.any()):
            return
        idx = sel.nonzero().flatten()
        r = self.rec
        r["env"].append(idx.cpu().numpy().astype(np.int16))
        r["call"].append(np.full(len(idx), self.calls, dtype=np.int32))
        r["first"].append(first[idx].detach().cpu().numpy().astype(bool))
        r["depth2"].append(depth2[idx].detach().float().cpu().numpy().astype(np.float16))
        r["z_prop"].append(z_prop[idx].detach().float().cpu().numpy())
        if hist is not None:
            r["grav"].append(hist[idx, 0, 3:6].detach().float().cpu().numpy())
        r["gt"].append(gt_map[idx].detach().float().cpu().numpy().reshape(len(idx), sp.MAP_X, sp.MAP_Y))

    def save(self, path) -> bool:
        if not self.rec["env"]:
            return False
        np.savez(path, **{k: np.concatenate(v) for k, v in self.rec.items() if v})
        return True
