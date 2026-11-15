"""STOP 파일 · 마감을 저장 경계(save_interval 의 배수)에서만 받는 runner 래퍼 (SONNET-X25, REVIEW-35fd1478 막음 1).

Sol23FRunner.log 는 STOP 파일이나 마감이 있으면 그 회차 번호로 model_{it}.pt 를 저장하고 멈춘다. 그대로 쓰면 두 판이 서로 다른 임의 회차에서 멈춘다.
여기서는 it 가 interval 의 배수가 아닌 회차에는 stop_file · deadline_epoch 를 잠시 가려, 다음 배수 경계에서 저장하고 멈추게 한다.
runners/sol23f_runner.py 는 고치지 않는다.
"""

from __future__ import annotations


def boundary_stop(base: type, interval: int) -> type:
    """base(Sol23FRunner 하위) 의 log 가 interval 배수 회차에서만 STOP · 마감을 보게 하는 하위 클래스."""
    if interval <= 0:
        raise ValueError("interval 은 양수")

    class BoundaryStop(base):
        def log(self, locs, width: int = 80, pad: int = 35) -> None:
            it = int(locs["it"])

            if it % interval == 0:
                return super().log(locs, width, pad)
            held = (self.stop_file, self.deadline_epoch)
            self.stop_file, self.deadline_epoch = None, None

            try:
                return super().log(locs, width, pad)
            finally:
                self.stop_file, self.deadline_epoch = held

    BoundaryStop.__name__ = f"{base.__name__}BoundaryStop"
    BoundaryStop.__qualname__ = BoundaryStop.__name__

    return BoundaryStop
