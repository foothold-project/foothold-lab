#!/usr/bin/env python3
"""L 시연 · C-1 음성 클라이언트를 순서대로 돌려 화면에서 보이게 한다 (127.0.0.1 시험 서버만 · 실기 아님).

순서 예: --steps "wait 3, say foothold_stand_down, wait 8, say foothold_stand_up, wait 8, close"
  wait N        N 초 기다림 (그동안 인식기 건강 신호는 계속 보냄)
  say <wav>     samples/<wav>.wav 를 Vosk + 11-23 판정 규칙으로 실제로 받아쓰고, 허용 명령이면 의도 한 건
  down / up     인식 없이 의도를 직접 넣음 (시험용)
  sit / rise    (--action-profile 때만) 인식 없이 sit_down / sit_rise 를 직접 넣음
  close         세션 닫기 (보낸 요청 결과 뒤 반납)
  drop          프로세스가 죽은 것처럼 연결만 끊음 (반납 없음 · 서버 만료를 기다림)
--action-profile : 음성 action 요청 · SDK 접수 경로 시험 (가짜 Go2 한정). 「foothold sit down」 → Sit ·
  「foothold get up」 → RiseSit. 세션당 action 한 건 · 접수 = 가짜 SDK 접수 (물리 완료 아님 · 앉음 측정 없음).
--heard-port 를 주면 들은 문장 · 요청 · 결과를 127.0.0.1 알림 통로 (heard_feed.py) 로 흘린다 — 화면 표시용.
로그인 정보 · 로봇은 logs/s5_login.txt · logs/s5_ids.json (s5_server.py 가 만든 시험 계정 · 화면에 출력 안 함)
"""
import argparse
import asyncio
import json
import os
import sys
import time
import types
import uuid

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import voice_client as V  # noqa: E402

MODEL = os.path.expanduser('~/foothold-voice/model_dl/vosk-model-small-en-us-0.15')
# action 시험 프로필 전용 (11-25 · 기본 posture 전용 L 의 INTENT_PHRASES 는 그대로)
ACTION_PHRASES = {'foothold sit down': 'sit_down', 'foothold get up': 'sit_rise'}
RULES = os.path.expanduser('~/Desktop/foothold/1차 검토/26.11/26.11.23/2_음성인식_사람목소리시험_실기준비/시험코드')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--steps', required=True)
    ap.add_argument('--session-s', type=float, default=120)
    ap.add_argument('--server', default='http://127.0.0.1:8810')
    ap.add_argument('--heard-port', type=int, default=None)
    ap.add_argument('--action-profile', action='store_true')
    ap.add_argument('--log', default=os.path.join(HERE, 'logs', 'L_demo_voice.jsonl'))
    a = ap.parse_args()
    V.check_loopback(a.server)
    ws = 'ws://127.0.0.1:%d/api/v1/ws' % V.urlsplit(a.server).port
    user, pw = open(os.path.join(HERE, 'logs', 's5_login.txt')).read().split('\n')[:2]
    robot = json.load(open(os.path.join(HERE, 'logs', 's5_ids.json')))['robot']
    steps = [x.strip() for x in a.steps.split(',') if x.strip()]

    feed = None
    if a.heard_port:
        from heard_feed import HeardFeed
        feed = HeardFeed(a.heard_port).start()

    def publish(**ev):
        if feed:
            feed.publish(dict(ev, robot=robot, at_ms=int(time.time() * 1000)))

    listener = None
    if any(st.startswith('say ') for st in steps):
        import bridge as B
        listener = B.vosk_listener_factory(MODEL, RULES)
        reader = types.SimpleNamespace(samples=B.SAMPLES)

    def recognize(name):
        import bridge as B
        data = B.Bridge.read_sample(reader, name)         # 알려진 samples/ 이름만 · 형식 · 길이 검사
        lis, results = listener(), []
        for i in range(0, len(data), 4000):
            r = lis.feed(data[i:i + 4000])
            if r and r.get('kind') != 'empty':
                results.append(r)
        heard = ' / '.join(r.get('heard') or '' for r in results) or None
        phrases = dict(B.INTENT_PHRASES, **(ACTION_PHRASES if a.action_profile else {}))
        hit = next((r for r in results if r.get('kind') == 'trigger' and r.get('phrase') in phrases), None)
        trig = next((r for r in results if r.get('kind') == 'trigger'), None)
        # 표시용 분류 (요청 여부는 hit 로만 정함): 동작 연결 명령 · 알아들었지만 연결 안 한 명령 · 부르기 · 부정문 · 명령 아님
        words = set((heard or '').replace("'", "'").split())
        match = ('command' if hit else 'call' if trig and trig.get('phrase') == 'hey foothold'
                 else 'known_unconnected' if trig else 'negation' if words & {"don't", 'not', 'no'} else 'none')
        return heard, (phrases[hit['phrase']] if hit else None), (trig.get('phrase') if trig else None), match

    def log(row):
        with open(a.log, 'a', encoding='utf-8') as f:
            f.write(json.dumps(row, ensure_ascii=False) + '\n')
        k = row['kind']
        # 들은 문장 번호 (heard_id = 의도 번호) · 요청 번호를 그대로 실어 보낸다 — 화면은 같은 번호끼리만 잇는다
        if k == 'intent_accepted':
            publish(kind='request', heard_id=row.get('intent'), request_id=row['request_id'], intent=row['action'])
        elif k in ('posture_accepted_by_server', 'action_accepted_by_server'):
            publish(kind='accepted', request_id=row.get('request_id'))
        elif k == 'sdk_accepted':
            publish(kind='result', request_id=row.get('request_id'), result='SDK_ACCEPTED', intent=row.get('action'),
                    posture=row.get('posture'))
        elif k == 'action_unresolved_at_end':
            publish(kind='result', request_id=row.get('request_id'), result='UNRESOLVED_AT_END', why=row.get('why'))
        elif k == 'intent_rejected':
            publish(kind='rejected', heard_id=row.get('intent'), why=row.get('why'))
        elif k == 'confirmed':
            publish(kind='result', request_id=row.get('request_id'), result='CONFIRMED', intent=row.get('action'), posture=row.get('posture'))
        elif k == 'ended':
            publish(kind='result', request_id=row.get('request_id'), result=row.get('result'))
        elif k == 'unexpected_result':
            publish(kind='result', request_id=row.get('request_id'), result=f"예상 밖 결과 {row.get('code')}")
        elif k == 'pending_unknown':
            publish(kind='result', request_id=row.get('request_id'), result='UNKNOWN')
        elif k in ('granted', 'closed', 'not_taking'):
            publish(kind='session', state=k, why=row.get('why'), holder_type=row.get('holder_type'))
        if k in ('open', 'take', 'not_taking', 'granted', 'intent_accepted', 'action_accepted_by_server', 'posture_accepted_by_server',
                 'sdk_accepted', 'action_unresolved_at_end', 'late_result_ignored', 'unexpected_result', 'intent_rejected', 'confirmed',
                 'ended', 'reply_error', 'close_begin', 'closed', 'close_unconfirmed', 'pending_unknown', 'take_canceled',
                 'release_observed', 'release_reply_ok', 'release_reply_error'):
            extra = {x: v for x, v in row.items() if x in ('why', 'action', 'holder_type', 'result', 'code', 'posture', 'latched', 'basis', 'sdk_action', 'start_posture', 'physical', 'status', 'sdk_code')}
            print(time.strftime('%H:%M:%S'), '[음성]', k, extra, flush=True)

    s = V.VoiceSession(robot, a.session_s, log=log, action_profile=a.action_profile)
    if a.action_profile:
        print(time.strftime('%H:%M:%S'), '[음성] action 시험 프로필 · 가짜 Go2 한정 · 세션당 action 한 건', flush=True)
    q = asyncio.Queue()

    async def script():
        end = time.time() + 6
        while s.phase not in ('held', 'closed') and time.time() < end:
            await q.put(('health',)); await asyncio.sleep(.1)
        if s.phase != 'held':
            return
        for st in steps:
            if s.phase == 'closed':
                break
            if st.startswith('wait'):
                t_end = time.time() + float(st.split()[1])
                while time.time() < t_end and s.phase != 'closed':
                    await q.put(('health',)); await asyncio.sleep(.2)
            elif st.startswith('say '):
                name = st.split()[1]
                captured = int(time.time() * 1000)
                heard, intent, phrase, match = await asyncio.get_running_loop().run_in_executor(None, recognize, name)
                print(time.strftime('%H:%M:%S'), '[인식]', name, '→ 들은 것', repr(heard), '·', match, '· 의도', intent, flush=True)
                iid = str(uuid.uuid4())
                publish(kind='heard', heard_id=iid, source='wav', heard=heard, intent=intent, phrase=phrase, match=match)
                if intent is None:
                    continue
                await q.put(('health',))
                await q.put(('intent', dict(id=iid, intent=intent, robot=robot, issued_at=captured, ttl_ms=2000)))
            elif st in ('down', 'up', 'sit', 'rise'):
                name = {'down': 'stand_down', 'up': 'stand_up', 'sit': 'sit_down', 'rise': 'sit_rise'}[st]
                iid = str(uuid.uuid4())
                publish(kind='heard', heard_id=iid, source='direct', heard=None, intent=name)   # 인식 없이 직접 주입
                await q.put(('intent', dict(id=iid, intent=name, robot=robot,
                                            issued_at=int(time.time() * 1000), ttl_ms=2000)))
            elif st == 'close':
                await q.put(('close', 'demo_close'))
            elif st == 'drop':
                await q.put(('drop',))
                return

    async def both():
        runner = asyncio.create_task(V.run_session(s, ws, V.app_login(a.server, user, pw), q))
        await script()
        while s.phase != 'closed' and not runner.done():
            await q.put(('health',)); await asyncio.sleep(.2)
        await asyncio.wait_for(runner, 30)

    try:
        asyncio.run(both())
    finally:
        print(time.strftime('%H:%M:%S'), '[음성] 끝 ·', s.why, '· 보낸 프레임', s.counts, flush=True)
        if feed:
            time.sleep(1.0)
            feed.close()


if __name__ == '__main__':
    main()
