"""가짜 Go2 장치 모형 (로컬 음성 → 엎드리기 연동 시험 전용 · 실기 · SDK · DDS 없음).

이 파일은 물리 시뮬이 아니다. SDK 호출을 기록하고, 정해 둔 시험 규칙대로
측정 표본 (lowstate · sportmodestate 모양) 을 만들어 낼 뿐이다.

시험 장치 규칙 (방향 초안 4 절):
  1. 시작은 서 있음 (mode 0 · 몸 높이 0.30 m · 멈춤).
  2. StopMove · Move 는 자세를 바꾸지 않는다 (서 있음으로 되돌리지도 않음).
  3. StandDown 을 「수락」 (반환 0) 하면 그 다음 tick 에서만 엎드린 값으로 바뀐다.
  4. accept_without_change=True 면 수락만 하고 자세를 바꾸지 않는다 (부정 사례).
  5. 엎드린 값 (mode 5 · 몸 높이 0.10 m) 은 팀 Feedback 분류 기준 안의 **시험 가정**이며
     실기 Go2 X 에서 잰 값이 아니다.
"""
import threading
import time
from types import SimpleNamespace as NS

STANDING = dict(mode=0, body_height=.30)
LYING_ASSUMED = dict(mode=5, body_height=.10)   # 시험 가정 · 실측 아님
BALANCED = dict(mode=1, body_height=.30)        # 균형 서기 뒤 (팀 확인 조건 모드 1·3) · 시험 가정 · 실측 아님
# 11-25 · 앉음 가정 모형 (sit_model=True 일 때만). mode 10 은 Unitree 공식 열거값 (sit) · 높이 · 기울기는 임의 시험값.
SIT_ASSUMED = dict(mode=10, body_height=.24)    # .24 = PR478 팀 시험의 가정값 (실측 · 판정 문턱 아님)
SIT_PITCH_RAD = .52                              # 약 30° · 임의 시험값 (실제 앉음 대표값 아님)


class FakeGo2Device:
    def __init__(self, *, standdown_code=0, stopmove_code=0, accept_without_change=False, sit_model=False):
        self.pose = dict(STANDING)
        self.pending = None
        self.rpy = (0., 0., 0.)          # imu rpy (rad) · 앉음 모형에서만 pitch 가 바뀜
        self.pending_rpy = None
        self.sit_model = sit_model       # False (기본) = Sit/RiseSit 기록만 (11-25 A/B/C 와 같음)
        self.tick_count = 0
        self.standdown_code = standdown_code
        self.stopmove_code = stopmove_code
        self.accept_without_change = accept_without_change
        self.log = []          # (tick, 사건) — 시각 순서표용
        self.wall = []         # (벽시계 ms, tick, 사건) — S5 시각 순서표용
        self.lock = threading.Lock()

    def _event(self, what):
        self.log.append((self.tick_count, what))
        self.wall.append((int(time.time() * 1000), self.tick_count, what))

    def client(self, name):
        return _Client(self, name)

    def tick(self):
        """한 박자: 대기 중인 자세 변화를 적용하고 새 표본 두 개를 돌려준다."""
        with self.lock:
            self.tick_count += 1
            if self.pending is not None:
                self.pose = self.pending
                self.pending = None
                if self.pending_rpy is not None:
                    self.rpy, self.pending_rpy = self.pending_rpy, None
                self._event('pose_changed mode=%d height=%.2f pitch=%.2f' % (self.pose['mode'], self.pose['body_height'], self.rpy[1]))
            pose, tick, rpy = dict(self.pose), self.tick_count, list(self.rpy)
        low = NS(sn=(1234, 5678), tick=tick,
                 imu_state=NS(rpy=rpy, gyroscope=(0., 0., 0.)),
                 motor_state=[NS(dq=0.) for _ in range(20)], bms_state=NS(soc=75), power_v=28.)
        sport = NS(stamp=NS(sec=1 + tick // 1_000_000_000, nanosec=tick % 1_000_000_000), velocity=(0., 0., 0.), yaw_speed=0.,
                   error_code=0, progress=0., **pose)
        return low, sport


class _Client:
    """Go2Sink 가 부르는 SDK 자리 (normal · emergency 두 개)."""

    def __init__(self, device, name):
        self.device, self.name, self.calls, self.result = device, name, [], 0

    def _record(self, method, args=()):
        self.calls.append((method, args))
        with self.device.lock:
            self.device._event('%s.%s' % (self.name, method))

    def Move(self, *velocity):
        self._record('Move', velocity)
        return self.result

    def StopMove(self):
        self._record('StopMove')
        return self.device.stopmove_code

    def StandDown(self):
        self._record('StandDown')
        code = self.device.standdown_code
        if code == 0 and not self.device.accept_without_change:
            with self.device.lock:
                self.device.pending = dict(LYING_ASSUMED)   # 다음 tick 에서만 적용
        return code

    def StandUp(self):
        self._record('StandUp')
        if not self.device.accept_without_change:
            with self.device.lock:
                self.device.pending = dict(STANDING)        # 다음 tick 에서만 적용 (시험 가정 · 모드 0 · 0.30 m)
        return 0

    def Sit(self):
        """앉기: 받기만 기록 · 자세 숫자는 바꾸지 않음 (실기 앉음 값 모름 → 지어내지 않음 · 팀 판정에 「앉음」 없음)"""
        self._record('Sit')
        if self.device.sit_model and not self.device.accept_without_change:
            with self.device.lock:
                # 앉음 가정 모형: 메서드가 불린 뒤 다음 tick 에 mode·높이·기울기를 한꺼번에 (일관된 표본)
                self.device.pending = dict(SIT_ASSUMED)
                self.device.pending_rpy = (0., SIT_PITCH_RAD, 0.)
        return 0

    def RiseSit(self):
        """앉은 자세에서 일어서기: 받기만 기록 · 자세 숫자 그대로"""
        self._record('RiseSit')
        if self.device.sit_model and not self.device.accept_without_change:
            with self.device.lock:
                self.device.pending = dict(BALANCED)         # 모형의 서 있음 표본 (RiseSit 성공 증명 아님)
                self.device.pending_rpy = (0., 0., 0.)
        return 0

    def BalanceStand(self):
        self._record('BalanceStand')
        if not self.device.accept_without_change:
            with self.device.lock:
                if self.device.pose['mode'] == 0:
                    self.device.pending = dict(BALANCED)    # 다음 tick 에서만 적용
        return 0
