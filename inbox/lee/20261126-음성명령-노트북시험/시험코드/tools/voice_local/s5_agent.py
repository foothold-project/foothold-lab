#!/usr/bin/env python3
"""S5 · 가짜 Go2 를 꽂은 오프라인 에이전트 (팀 go2_direct.server.run 그대로 · loopback 서버에만).

팀 에이전트의 실제 주행 고리 run() 에 센서 통로 (channel_factory) 와 SDK 자리 (connect_factory) 만
가짜 Go2 (apps/agent/tests/voice_fake_go2.py) 로 바꿔 끼운다. 진짜 Unitree · CycloneDDS · ROS 모듈은
불러오지 못하게 막아 두고, 가짜가 빠지면 진짜 장비로 넘어가지 않고 즉시 실패한다.
물리 시뮬이 아니다. 가짜 장치가 시험 규칙대로 숫자를 바꿀 뿐이다.

실행: python3 s5_agent.py --url ws://127.0.0.1:8810/api/v1/agent/ws --token-file <파일> --log <jsonl>
"""
import argparse
import asyncio
import json
import os
import signal
import sys
import threading
import time

# 진짜 장비 · 미들웨어 모듈은 불러오면 바로 실패하게 막는다 (가짜 누락 시 진짜로 넘어가지 않음)
for name in ('unitree_sdk2py', 'cyclonedds', 'rclpy', 'unitree_webrtc_connect'):
    sys.modules[name] = None

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))


def _pre_arg(name):
    """팀 모듈 import 전에 고를 값 (argparse 보다 먼저 · 같은 프로세스에서 판을 바꾸지 않음)"""
    if name in sys.argv:
        i = sys.argv.index(name)
        if i + 1 < len(sys.argv):
            return sys.argv[i + 1]
    return None


# --agent-repo : 팀 에이전트 코드를 가져올 저장소 (기본 = 이 사본). 반드시 팀 import 전에 정한다.
AGENT_REPO = os.path.abspath(os.path.expanduser(_pre_arg('--agent-repo') or REPO))
if not os.path.isdir(os.path.join(AGENT_REPO, 'apps', 'agent', 'foothold_agent')):
    sys.exit('agent 저장소에 apps/agent/foothold_agent 가 없음: %s' % AGENT_REPO)
sys.path.insert(0, os.path.join(AGENT_REPO, 'apps', 'agent'))

from types import SimpleNamespace as NS                                   # noqa: E402
from foothold_agent.go2_direct import server as go2_server                # noqa: E402
from foothold_agent.go2_direct.approval import Approval                   # noqa: E402
from foothold_agent.link.client import Settings                           # noqa: E402
import importlib.util                                                     # noqa: E402

# 가짜 장치는 항상 이 사본의 정확한 파일에서 (agent 판과 무관)
FAKE_PATH = os.path.join(REPO, 'apps', 'agent', 'tests', 'voice_fake_go2.py')
_spec = importlib.util.spec_from_file_location('voice_fake_go2', FAKE_PATH)
_fake = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(_fake)
FakeGo2Device = _fake.FakeGo2Device


def code_origin():
    """실제로 불러온 팀 모듈 · 가짜 장치 파일 위치와 agent 판 SHA (비교 근거 기록용)"""
    import subprocess
    from foothold_agent.go2_direct import actions, feedback, sink, server
    try:
        sha = subprocess.run(['git', '-C', AGENT_REPO, 'rev-parse', 'HEAD'], capture_output=True, text=True, timeout=5).stdout.strip()
    except Exception as e:
        sha = 'unknown (%r)' % e
    return dict(agent_repo=AGENT_REPO, agent_sha=sha,
                files={m.__name__: m.__file__ for m in (server, actions, feedback, sink)},
                fake_device=_fake.__file__)

PUBLISH_S = 0.02          # 가짜 센서 표본 간격 (50 Hz · 시험 값)
SERIAL = '1234-5678'      # 가짜 장치 시리얼 (voice_fake_go2 의 sn 과 같음)


def find_sink():
    """관찰 전용: 이 프로세스 안의 Go2Sink 를 찾는다 (값을 바꾸지 않음 · 못 찾으면 None)."""
    import gc
    for o in gc.get_objects():
        if type(o).__name__ == 'Go2Sink':
            return o
    return None


def sink_view(sink):
    """관찰 전용 스냅숏: 세대 · action 실행 중 여부 · 자세 정지 전용 표식 (내부 값 · 읽기만)."""
    if sink is None:
        return dict(sink='not_found')
    a = getattr(sink, 'actions', None)
    ex = getattr(a, 'executing', None) if a is not None else None
    job = getattr(a, 'job', None) if a is not None else None
    return dict(generation=getattr(sink, 'generation', None),
                executing=(ex or {}).get('action') if ex else None,
                job=(job or {}).get('action') if job else None,
                posture_stop_only=getattr(sink, '_posture_stop_only', None))


TRACE_ERRORS = []   # 관찰 실패 (기록 · 스냅숏) — 이 판의 관찰은 불완전으로 본다


def trace_failed(where, exc):
    """관찰 실패는 숨기지 않되 (stderr · 목록) 가짜 SDK 호출의 반환 · 예외에는 섞지 않는다."""
    TRACE_ERRORS.append((where, repr(exc)))
    try:
        print('[s5-agent] trace_error %s %r (관찰 불완전)' % (where, exc), file=sys.stderr, flush=True)
    except Exception:
        pass


def make_traced(client, log, view):
    """가짜 SDK 자리의 호출 기록에 관찰을 덧붙인다. 원래 기록 (orig) 의 결과 · 예외는 그대로 두고,
    관찰 (view · log) 실패는 trace_failed 로만 남긴다. trace 시각은 기록 위치의 관측 시각이지 호출 완료 · 물리 시작 시각이 아니다."""
    orig = client._record

    def rec(method, args=()):
        result = orig(method, args)
        try:
            row = dict(kind='sdk_call', lane=client.name, method=method, args=list(args), **view())
        except Exception as e:                    # 스냅숏 실패
            trace_failed('snapshot', e)
            row = dict(kind='sdk_call', lane=client.name, method=method, args=list(args), view='failed')
        try:
            log(row)
        except Exception as e:                    # 기록기 실패
            trace_failed('log', e)
        return result
    client._record = rec
    return client


class FakeChannel:
    """센서 통로 자리: subscribe 한 받는 쪽에 가짜 표본을 일정 간격으로 넣는다"""

    def __init__(self, device, log):
        self.device, self.log, self.stop = device, log, threading.Event()
        self.thread = None
        self.last_posture = None
        self.trace = False
        self.sink = None
        self.last_view = None

    def subscribe(self, inputs):
        def loop():
            while not self.stop.is_set():
                low, sport = self.device.tick()
                inputs.lowstate(low)
                inputs.sportmodestate(sport)
                snap = inputs.posture_snapshot()
                if snap['state'] != self.last_posture:
                    self.last_posture = snap['state']
                    self.log(dict(kind='agent_posture', state=snap['state'], mode=snap['mode'], tick=self.device.tick_count))
                if self.trace:
                    try:
                        if self.sink is None:
                            self.sink = find_sink()
                        v = sink_view(self.sink)
                        if v != self.last_view:
                            self.last_view = v
                            self.log(dict(kind='agent_exec', tick=self.device.tick_count, **v))
                    except Exception as e:
                        trace_failed('exec_view', e)
                time.sleep(PUBLISH_S)
        self.thread = threading.Thread(target=loop, name='fake-go2-telemetry', daemon=True)
        self.thread.start()

    def close(self):
        self.stop.set()
        if self.thread is not None:
            self.thread.join(timeout=1)


AGENT_PATH = '/api/v1/agent/ws'


def check_url(url):
    """ws · 정확히 127.0.0.1 · 명시 포트 · 사용자 정보 없음 · 고정 경로 · query/fragment 없음만 허용"""
    from urllib.parse import urlsplit
    u = urlsplit(url)
    try:
        port = u.port
    except ValueError:
        port = None
    if (u.scheme != 'ws' or u.hostname != '127.0.0.1' or u.username is not None or u.password is not None
            or '@' in u.netloc or port is None or not 1 <= port <= 65535 or u.path != AGENT_PATH or u.query or u.fragment):
        sys.exit('loopback 서버 고정 경로만 허용 (ws://127.0.0.1:<포트>%s)' % AGENT_PATH)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--url', required=True)
    ap.add_argument('--token-file', required=True)
    ap.add_argument('--log', required=True)
    ap.add_argument('--minutes', type=float, default=30)
    ap.add_argument('--agent-repo', default=None, help='팀 에이전트 코드 저장소 (팀 import 전에 적용 · 기본 이 사본)')
    ap.add_argument('--sit-model', action='store_true', help='가짜 장치 앉음 가정 모형 (mode 10 · 높이 · 기울기 임의값)')
    ap.add_argument('--trace', action='store_true', help='SDK 호출 (normal/emergency · 인자) 과 실행 상태를 바로바로 기록 (관찰 전용)')
    a = ap.parse_args()
    check_url(a.url)                       # 토큰을 읽거나 run 하기 전에
    token = open(a.token_file).read().strip()
    lock = threading.Lock()

    def log(row):
        line = json.dumps(dict(row, wall_ms=int(time.time() * 1000)), ensure_ascii=False)
        with lock, open(a.log, 'a', encoding='utf-8') as f:
            f.write(line + '\n')

    device = FakeGo2Device(sit_model=a.sit_model)
    origin = code_origin()
    bad = [f for f in origin['files'].values() if not os.path.abspath(f).startswith(AGENT_REPO + os.sep)]
    if bad:
        sys.exit('팀 모듈이 고른 판에서 오지 않음: %s' % bad)
    channel = FakeChannel(device, log)
    channel.trace = a.trace

    def traced(client):
        return make_traced(client, log, lambda: dict(tick=device.tick_count, **sink_view(channel.sink or find_sink())))
    config = NS(approval=Approval(nic='fake0', robot_serial=SERIAL, expires_at=time.time() + a.minutes * 60),
                link=Settings(a.url, token), robot=None)

    def connect_factory(env, *, observed_serial, channel):
        if observed_serial != SERIAL:
            raise PermissionError('fake serial mismatch')
        n, e = device.client('normal'), device.client('emergency')
        return (traced(n), traced(e)) if a.trace else (n, e)

    stop = asyncio.Event()

    async def runner():
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, stop.set)
        log(dict(kind='agent_start', url=a.url, serial=SERIAL, sit_model=a.sit_model, **origin))
        try:
            await go2_server.run(config, {}, stop=stop, channel_factory=lambda env: channel, connect_factory=connect_factory)
        finally:
            for when, tick, what in device.wall:
                log(dict(kind='device', event=what, tick=tick, device_ms=when))
            log(dict(kind='agent_stop', trace_errors=len(TRACE_ERRORS),
                     observation='incomplete' if TRACE_ERRORS else ('complete' if a.trace else 'off')))

    print('[s5-agent] 가짜 Go2 · 서버 %s · 기록 %s' % (a.url, a.log), flush=True)
    asyncio.run(runner())


if __name__ == '__main__':
    main()
