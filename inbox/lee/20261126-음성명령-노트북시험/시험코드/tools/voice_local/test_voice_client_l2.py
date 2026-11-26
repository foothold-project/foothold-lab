"""L ② · C-1 음성 클라이언트 × 실제 팀 서버 (임시 DB · 조종권 코드 그대로) × 가짜 Go2 에이전트 (팀 주행 고리 그대로).

127.0.0.1 만. 로봇 · Orin · 운영 서버 없음. s5_server.py · s5_agent.py 를 띄워 쓴다 (포트 8810 · 시험 계정 · 가짜 로봇).
음성 클라이언트와 「사람 화면」 은 같은 담당자 계정의 서로 다른 앱 세션 — 실제 운용에서 이 방식이 허용된다는 뜻이 아니라
「같은 계정일 때 어떻게 동작하는가」 를 재는 모형이다 (실기 로봇은 담당자 한 명만 조종 가능 · api.authorize).

실행: python -m pytest test_voice_client_l2.py -q -s   (약 1~2 분)
"""
import asyncio
import json
import os
import signal
import subprocess
import sys
import time
import uuid

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import voice_client as V  # noqa: E402

PY = sys.executable
BASE = 'http://127.0.0.1:8810'
WS = 'ws://127.0.0.1:8810/api/v1/ws'
LOGS = os.path.join(HERE, 'logs')
AGENT_LOG = os.path.join(LOGS, 'L2_agent.jsonl')
VOICE_LOG = os.path.join(LOGS, 'L2_voice.jsonl')


def wait_line(path, text, timeout):
    end = time.time() + timeout
    while time.time() < end:
        if os.path.exists(path) and text in open(path, encoding='utf-8', errors='replace').read():
            return True
        time.sleep(.3)
    return False


def stop_procs(procs):
    """이 시험이 만든 프로세스만 정리 (SIGINT → 기다림 → kill 뒤에도 wait 로 회수)."""
    for p in procs:
        if p.poll() is None:
            p.send_signal(signal.SIGINT)
    for p in procs:
        try:
            p.wait(timeout=20)
        except subprocess.TimeoutExpired:
            p.kill()
            p.wait(timeout=10)


def start_stack(popen=subprocess.Popen, wait=wait_line, logs=LOGS, agent_log=AGENT_LOG):
    """서버 · 에이전트를 띄운다. 준비 확인이 실패하면 띄운 것을 정리하고 예외를 낸다."""
    procs = []
    try:
        if os.path.exists(agent_log):
            os.remove(agent_log)
        srv_out = os.path.join(logs, 'L2_server.out')
        procs.append(popen([PY, 's5_server.py'], cwd=HERE, stdout=open(srv_out, 'w'), stderr=subprocess.STDOUT))
        if not wait(srv_out, 'Uvicorn running', 120):
            raise RuntimeError('서버가 뜨지 않음')
        ids = json.load(open(os.path.join(LOGS, 's5_ids.json')))
        procs.append(popen([PY, 's5_agent.py', '--url', 'ws://127.0.0.1:8810/api/v1/agent/ws', '--token-file',
                            os.path.join(LOGS, 's5_agent.token'), '--log', agent_log, '--minutes', '30'],
                           cwd=HERE, stdout=open(os.path.join(logs, 'L2_agent.out'), 'w'), stderr=subprocess.STDOUT))
        if not wait(agent_log, 'agent_posture', 30):
            raise RuntimeError('에이전트가 붙지 않음')
        user, pw = open(os.path.join(LOGS, 's5_login.txt')).read().split('\n')[:2]
        time.sleep(1.0)
        return dict(robot=ids['robot'], user=user, pw=pw, agent=procs[1]), procs
    except BaseException:
        stop_procs(procs)
        raise


@pytest.fixture(scope='module')
def stack():
    st, procs = start_stack()
    try:
        yield st
    finally:
        stop_procs(procs)


def test_0_start_failure_cleans_up_own_processes(tmp_path):
    """준비 확인 실패 경로: 가짜 Popen 으로 띄운 것만 정리되는지 (실제 서버 안 띄움)."""
    made = []

    class P:
        def __init__(self, *a, **k):
            self.signals, self.waited, self.killed, self.alive = [], 0, False, True
            made.append(self)

        def poll(self):
            return None if self.alive else 0

        def send_signal(self, sig):
            self.signals.append(sig)

        def wait(self, timeout=None):
            self.waited += 1
            if self.signals and not self.killed and timeout == 20:
                raise subprocess.TimeoutExpired('x', timeout)       # SIGINT 로 안 죽는 경우
            self.alive = False
            return 0

        def kill(self):
            self.killed = True
    keep = os.path.join(tmp_path, 'keep.jsonl')
    open(keep, 'w').write('기존 증거\n')
    before = {f: os.path.getmtime(os.path.join(LOGS, f)) for f in os.listdir(LOGS)}
    with pytest.raises(RuntimeError):
        start_stack(popen=P, wait=lambda *a: False, logs=str(tmp_path), agent_log=keep)
    assert {f: os.path.getmtime(os.path.join(LOGS, f)) for f in os.listdir(LOGS)} == before   # 보존 기록 그대로
    assert len(made) == 1 and made[0].signals == [signal.SIGINT] and made[0].killed and made[0].waited == 2


def device_events():
    """에이전트 종료 때 쓰인 가짜 장치 사건 (종료 뒤에만 읽을 수 있음)."""
    rows = [json.loads(l) for l in open(AGENT_LOG, encoding='utf-8')]
    return [r['event'] for r in rows if r['kind'] == 'device']


class Screen:
    """사람 화면 역할 (같은 계정의 다른 앱 세션). 받은 메시지를 모으고 요청에 답을 기다린다."""

    def __init__(self, robot, token):
        self.robot, self.token, self.msgs, self.waiters, self.first, self.seq = robot, token, [], {}, True, 0
        self.lease = None

    async def __aenter__(self):
        import websockets
        self.ws = await websockets.connect(WS, additional_headers={'authorization': f'Bearer {self.token}'})
        self.rd = asyncio.create_task(self._read())
        await self.call('sub', robots=[self.robot], streams=['state'])
        return self

    async def __aexit__(self, *a):
        self.rd.cancel()
        await self.ws.close()

    async def _read(self):
        async for raw in self.ws:
            m = json.loads(raw)
            self.msgs.append(m)
            if m.get('t') == 'lease' and m.get('robot') == self.robot:
                self.lease = m.get('lease_id')
            if m.get('t') == 'reply' and m.get('id') in self.waiters:
                self.waiters.pop(m['id']).set_result(m)

    async def call(self, t, **body):
        fid = str(uuid.uuid4())
        msg = dict(id=fid, t=t, **body)
        if self.first:
            msg['proto'], self.first = 'fh-rt/1', False
        fut = asyncio.get_running_loop().create_future()
        self.waiters[fid] = fut
        await self.ws.send(json.dumps(msg))
        return await asyncio.wait_for(fut, 5)

    async def beat(self):
        if self.lease:
            self.seq += 1
            return await self.call('cmd', robot=self.robot, lease_id=self.lease, seq=self.seq, axes=[0, 0, 0])

    def last_state(self):
        return next((m for m in reversed(self.msgs) if m.get('t') == 'state' and m.get('robot') == self.robot), None)


def login(st):
    return V.app_login(BASE, st['user'], st['pw'])


def logrow(row):
    with open(VOICE_LOG, 'a', encoding='utf-8') as f:
        f.write(json.dumps(row, ensure_ascii=False) + '\n')


async def voice(st, script, session_s=60):
    """script: async 함수 (q, s) — 의도 · 건강 · 닫기를 넣는다. 세션 끝까지 돈다."""
    s = V.VoiceSession(st['robot'], session_s, log=lambda r: logrow(dict(r, test=os.environ.get('PYTEST_CURRENT_TEST', '')[:80])))
    q = asyncio.Queue()
    runner = asyncio.create_task(V.run_session(s, WS, login(st), q))
    await script(q, s)
    await asyncio.wait_for(runner, 30)
    return s


def say(s, action):
    return ('intent', dict(id=str(uuid.uuid4()), intent=action, robot=s.robot, issued_at=int(time.time() * 1000), ttl_ms=2000))


async def until(cond, timeout, q=None):
    end = time.time() + timeout
    while time.time() < end:
        if cond():
            return True
        if q is not None:
            await q.put(('health',))
        await asyncio.sleep(.1)
    return cond()


# ── A. 정상: 받기 → 음성 엎드리기 → 음성 일어서기 → 반납 (잠금 해제 · 이동 없이) ──
def test_A_voice_session_down_then_up(stack):
    async def script(q, s):
        assert await until(lambda: s.phase == 'held', 5, q), s.why
        await asyncio.sleep(.5)
        await q.put(say(s, 'stand_down'))
        assert await until(lambda: s.pending and s.pending.get('done'), 10, q), s.rows[-5:]
        await asyncio.sleep(.3)
        await q.put(say(s, 'stand_up'))
        assert await until(lambda: s.pending and s.pending.get('done') and s.pending['action'] == 'stand_up', 10, q)
        await q.put(('close', 'test_done'))
    s = asyncio.run(voice(stack, script))
    done = [(r['kind'], r.get('action') or r.get('result')) for r in s.rows if r['kind'] in ('confirmed', 'ended', 'reply_error')]
    print('\n[A] 결과', done, '· 닫힘', s.why, '· 프레임', s.counts)
    assert done == [('confirmed', 'stand_down'), ('confirmed', 'stand_up')]
    assert s.why == 'test_done' and s.phase == 'closed'
    assert s.counts['take'] == 1 and s.counts['release'] == 1 and s.counts['posture'] == 2
    assert s.counts['unlock'] == 0 and s.counts['action'] == 0


# ── B. 사람이 쥐고 있으면 음성은 받지 않음 ──
def test_B_human_holds_voice_does_not_take(stack):
    async def main():
        async with Screen(stack['robot'], login(stack)) as h:
            r = await h.call('lease.take', robot=stack['robot'])
            assert r['ok'], r
            assert await until(lambda: h.lease, 5)
            async def script(q, s):
                for _ in range(20):
                    await h.beat()
                    await asyncio.sleep(.1)
            s = await voice(stack, script)
            await h.call('lease.release', robot=stack['robot'])
            return s
    s = asyncio.run(main())
    print('\n[B] 닫힘', s.why, '· 프레임', s.counts)
    assert s.why == 'held_by_user' and s.counts['take'] == 0 and s.counts['posture'] == 0 and s.counts['cmd'] == 0


# ── C. 음성이 쥐는 동안 사람: 받기 · 요청 모두 거부 → 음성 넘기기 → 사람이 받아 단추 일어서기 · 음성은 다시 안 잡음 ──
def test_C_handover_then_human_stand_up(stack):
    out = {}

    async def main():
        async with Screen(stack['robot'], login(stack)) as h:
            async def script(q, s):
                assert await until(lambda: s.phase == 'held', 5, q)
                await asyncio.sleep(.5)
                await q.put(say(s, 'stand_down'))
                assert await until(lambda: s.pending and s.pending.get('done'), 10, q)
                out['take_while_voice'] = (await h.call('lease.take', robot=stack['robot'])).get('error', {}).get('code')
                out['request_while_voice'] = (await h.call('lease.request', robot=stack['robot'])).get('error', {}).get('code')
                await q.put(('close', 'handover'))
            s = await voice(stack, script)
            out['voice'] = s
            await asyncio.sleep(.5)
            r = await h.call('lease.take', robot=stack['robot'])
            out['take_after'] = r.get('ok'), (r.get('error') or {}).get('code')
            assert await until(lambda: h.lease, 5), '사람이 조종권을 못 받음'
            for _ in range(5):
                await h.beat(); await asyncio.sleep(.1)
            st = h.last_state()
            out['before_up'] = (st.get('posture') or {}).get('state'), st.get('latched')
            rid = str(uuid.uuid4())
            h.first = False
            fut = asyncio.get_running_loop().create_future(); h.waiters[rid] = fut
            await h.ws.send(json.dumps(dict(id=rid, t='posture', robot=stack['robot'], lease_id=h.lease, action='stand_up')))
            out['up_reply'] = (await asyncio.wait_for(fut, 5)).get('ok')
            ok = False
            for _ in range(60):
                await h.beat(); await asyncio.sleep(.1)
                st = h.last_state() or {}
                res = st.get('posture_result') or {}
                if res.get('request_id') == rid and res.get('status') in ('SUCCEEDED', 'FAILED', 'REJECTED'):
                    ok = (res['status'], res.get('code'), (st.get('posture') or {}).get('state'))
                    break
            out['human_up'] = ok
            await h.call('lease.release', robot=stack['robot'])
    asyncio.run(main())
    s = out.pop('voice')
    print('\n[C]', out, '· 음성 닫힘', s.why, '· 프레임', s.counts)
    assert out['take_while_voice'] == 'LEASE_HELD'
    assert out['request_while_voice'] == 'LEASE_REQUEST_PENDING'          # 같은 계정: 넘겨 달라는 요청도 못 함
    assert s.why == 'handover' and s.counts['take'] == 1 and s.counts['release'] == 1
    assert out['take_after'] == (True, None)
    assert out['human_up'] == ('SUCCEEDED', 'CONFIRMED', 'STANDING')


# ── D. 음성 프로세스가 죽음 (연결만 끊김) → 조종권은 남았다가 15 s 뒤 만료 · 그 사이 사람은 못 받음 ──
def test_D_voice_dies_lease_expires(stack):
    out = {}

    async def main():
        async def script(q, s):
            assert await until(lambda: s.phase == 'held', 5, q)
            await q.put(('drop',))
        s = await voice(stack, script)
        out['voice'] = s
        died = time.time()
        async with Screen(stack['robot'], login(stack)) as h:
            r = await h.call('lease.take', robot=stack['robot'])
            out['take_right_after'] = (r.get('error') or {}).get('code')
            got = None
            while time.time() - died < 25:
                await asyncio.sleep(.5)
                r = await h.call('lease.take', robot=stack['robot'])
                if r.get('ok'):
                    got = round(time.time() - died, 1)
                    break
            out['human_took_after_s'] = got
            if got:
                assert await until(lambda: h.lease, 5)
                await h.call('lease.release', robot=stack['robot'])
    asyncio.run(main())
    s = out.pop('voice')
    print('\n[D]', out, '· 음성 닫힘', s.why)
    assert s.why == 'connection_lost'
    assert out['take_right_after'] == 'LEASE_HELD'
    assert out['human_took_after_s'] is not None and 13 <= out['human_took_after_s'] <= 20


# ── 마지막: 에이전트를 끄고 가짜 장치 명령 수를 센다 ──
def test_Z_device_counts(stack):
    a = stack['agent']
    a.send_signal(signal.SIGINT)
    a.wait(timeout=20)
    ev = device_events()
    names = [e.split(' ')[0].split('.')[-1] for e in ev]
    # Move 는 호출 횟수만 센다 (장치 기록에 인자가 없어 「0 속도였음」 을 여기서 확인하지 않음)
    print('\n[Z] 가짜 장치 명령 (횟수):', {k: names.count(k) for k in ('StandDown', 'StandUp', 'BalanceStand', 'Move')})
    # A: down 1 · up 1 / C: down 1 · (사람) up 1 → StandDown 2 · StandUp 2 · BalanceStand 2
    assert names.count('StandDown') == 2 and names.count('StandUp') == 2 and names.count('BalanceStand') == 2
