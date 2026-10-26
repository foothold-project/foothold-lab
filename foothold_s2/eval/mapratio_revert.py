"""M-T4: 지도 끔 비율 되돌림 자동화 (DESIGN-MAPRATIO v0.2 7 절 · JUDGE-SPEC 4.1 `consume` 의 소비자).

평가 사슬이 저장본마다 판정 상태(judge_gate.Verdict.state)를 하나씩 넣으면, 다음 동작과 «다음 저장 경계에서 걸 M-T1 인자»(`p_map_off_change`)를 돌려준다.
- MAINTAIN_FAIL 두 번 연속 -> 비율 단계를 한 칸 되돌리는 인자(직전 값). 이미 한 번 되돌렸으면(두 번째 되돌림) 인자 없이 멈춤 · 보고.
- 단일 MAINTAIN_FAIL -> 보류(인자 없음). PASS -> 확대(인자 없음, `expand_to` 에 다음 값; 단계표 끝이면 None). STOP -> 멈춤 · 보고.
- 직전 값이 없는 첫 단계에서의 되돌림은 되돌릴 곳이 없으므로 멈춤 · 보고.

숫자는 코드에 없다. 단계표(비율 사다리, 예: 높은 값에서 낮은 값으로)는 호출하는 쪽(cfg)이 준다. 이 모듈은 인자를 만들 뿐 학습을 띄우거나 멈추지 않는다.
인자의 키는 `StartRunner` 의 `p_map_off_change` 칸 {"from_iter", "to", "from"} 과 같다(feature/mapratio-jay). 두 브랜치는 아직 합쳐지지 않았다.
"""

from __future__ import annotations

import json
from typing import Sequence

from foothold_s2.eval import judge_gate as G

ARGUMENT_KEYS = ("from_iter", "to", "from")


class RatioController:
    """비율 단계표 위의 현재 위치 · 판정 소비자 · 기록. 순수 python."""

    def __init__(self, ladder: Sequence[float], start_index: int = 0):
        ladder = [float(v) for v in ladder]

        if not ladder or len(set(ladder)) != len(ladder) or any(not 0.0 <= v <= 1.0 for v in ladder):
            raise ValueError("ladder 는 [0, 1] 안의 서로 다른 값 하나 이상: %r" % (ladder,))
        if not 0 <= start_index < len(ladder):
            raise ValueError("start_index 가 단계표 밖: %r" % (start_index,))

        self.ladder = ladder
        self.index = int(start_index)
        self.consumer = G.Consumer()
        self.stopped = False
        self.records = []

    @property
    def current(self) -> float:
        return self.ladder[self.index]

    def _argument(self, to_index: int, ckpt_iter: int) -> dict:
        """다음 저장 경계(= 이 저장본의 다음 회차)부터 새 값을 쓰게 하는 M-T1 인자. «from» 은 체크포인트가 가진 값과의 대조용."""
        return {"from_iter": int(ckpt_iter) + 1, "to": self.ladder[to_index], "from": self.current}

    def step(self, state: str, ckpt_iter: int) -> dict:
        """저장본 하나의 판정 상태와 그 저장본 회차 -> {"action", "argument"(없으면 None), "stop", "reason", "index"}. 멈춘 뒤에는 부를 수 없다."""
        if self.stopped:
            raise RuntimeError("이미 멈춤 · 보고 상태다: 사람이 확인한 뒤 새 RatioController 로 이어 간다")
        if state not in G.STATES:
            raise ValueError("알 수 없는 판정 상태: %r" % (state,))

        action = self.consumer.step(state)
        argument, reason, expand_to = None, "", None
        before = self.index

        if action == G.REVERT:
            if self.index == 0:
                action, reason = G.STOP_REPORT, "되돌릴 직전 값이 없다(첫 단계)"
            else:
                argument = self._argument(self.index - 1, ckpt_iter)
                self.index -= 1
                reason = "MAINTAIN_FAIL 두 번 연속: 직전 값으로"
        elif action == G.EXPAND:
            if self.index + 1 < len(self.ladder):
                expand_to = self.ladder[self.index + 1]            # 확대는 M-T1 인자가 아니다(명세는 되돌림 인자만 정한다): 다음 값을 알려 줄 뿐, 걸지는 호출하는 쪽이 정한다
                self.index += 1
                reason = "PASS: 다음 단계로"
            else:
                reason = "PASS: 단계표 끝(더 확대할 값 없음)"
        elif action == G.STOP_REPORT:
            reason = reason or ("STOP" if state == G.STOP else "두 번째 되돌림: 멈춤 · 보고")

        stop = action == G.STOP_REPORT
        self.stopped = stop
        rec = {"ckpt_iter": int(ckpt_iter), "state": state, "action": action, "from_index": before, "to_index": self.index,
               "argument": argument, "expand_to": expand_to, "reverts": self.consumer.reverts, "reason": reason}
        self.records.append(rec)

        return {"action": action, "argument": argument, "expand_to": expand_to, "stop": stop, "reason": reason, "index": self.index, "record_line": record_line(rec)}


def record_line(rec: dict) -> str:
    """결정적 한 줄 JSON(키 정렬). 같은 입력이면 같은 줄이다."""
    return json.dumps(rec, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
