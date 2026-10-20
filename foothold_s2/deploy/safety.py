"""정책 노드의 안전 상태기계 (23 §4 · 42 §1). 순수 파이썬, 시계는 호출 쪽이 시각 `now` 로 준다.

상태: PASSIVE -> FIXSTAND -> POLICY -> HOLD(STOP 래치) -> SPORT(실기만) / DAMP(평지만).
- deadman: 명령이 0.3 s 끊기면 정리기 출력 0 (상태는 그대로, 경고).
- heartbeat: 1.0 s 끊기면 STOP 래치(HOLD).
- STOP: 명령 0 + 잠금. 자동 재개 없음: `release()` 가 호출되어야만 POLICY 로 돌아간다(사람이 해제).
- DAMP 는 평지일 때만. 평지가 아니면 HOLD 를 유지한다.
"""

from dataclasses import dataclass, field

PASSIVE, FIXSTAND, POLICY, HOLD, SPORT, DAMP = "PASSIVE", "FIXSTAND", "POLICY", "HOLD", "SPORT", "DAMP"

DEADMAN_S = 0.3
HEARTBEAT_S = 1.0
HOLD_UNSTABLE_S = 30.0
FIXSTAND_S = 2.0


@dataclass
class SafetyMachine:
    state: str = PASSIVE
    t_state: float = 0.0
    last_cmd: float = 0.0
    last_hb: float = 0.0
    latched: bool = False
    unstable_since: float = None
    events: list = field(default_factory=list)

    def command_received(self, now):
        self.last_cmd = now

    def heartbeat(self, now):
        self.last_hb = now

    def _go(self, state, now, why):
        self.events.append((now, self.state, state, why))
        self.state = state
        self.t_state = now

    def request_stand(self, now):
        if self.state == PASSIVE:
            self.last_cmd = self.last_hb = now
            self._go(FIXSTAND, now, "stand")

    def stop(self, now, why="STOP"):
        self.latched = True

        if self.state in (FIXSTAND, POLICY):
            self._go(HOLD, now, why)

    def release(self, now):
        """사람이 STOP 을 해제한다. HOLD 에서만 POLICY 로 돌아간다."""
        if self.state == HOLD and self.latched:
            self.latched = False
            self.last_cmd = self.last_hb = now
            self._go(POLICY, now, "release")

    def tick(self, now, posture_ok=True, flat_terrain=False, sport_available=False, hold_stable=True):
        if self.state == FIXSTAND and now - self.t_state >= FIXSTAND_S:
            self._go(POLICY if posture_ok else PASSIVE, now, "stand done" if posture_ok else "stand failed")

        if self.state == POLICY:
            if now - self.last_hb > HEARTBEAT_S:
                self.stop(now, "heartbeat")
            elif not posture_ok:
                self.stop(now, "posture")

        if self.state == HOLD:
            if hold_stable:
                self.unstable_since = None
            elif self.unstable_since is None:
                self.unstable_since = now

            if self.unstable_since is not None and now - self.unstable_since >= HOLD_UNSTABLE_S:
                if sport_available:
                    self._go(SPORT, now, "hold unstable")
                elif flat_terrain:
                    self._go(DAMP, now, "hold unstable, flat")

    def deadman_tripped(self, now):
        return self.state == POLICY and now - self.last_cmd > DEADMAN_S

    def filter_command(self, cmd, now):
        """정책에 줄 명령. POLICY 가 아니거나 STOP 래치거나 deadman 이면 0."""
        if self.state != POLICY or self.latched or self.deadman_tripped(now):
            return (0.0, 0.0, 0.0)

        return tuple(float(c) for c in cmd)
