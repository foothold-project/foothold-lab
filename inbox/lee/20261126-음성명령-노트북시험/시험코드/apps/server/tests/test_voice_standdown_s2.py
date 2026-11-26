"""S2 · 로컬 음성 → 엎드리기 연동 시험 (서버 중계 단계).

임시 PostgreSQL · 가짜 에이전트 연결 · 화면 연결 (팀 test_posture.py 와 같은 장치).
화면이 자세 요청 stand_down 을 보내면 서버가 같은 요청 번호로 에이전트에 넘기고,
에이전트가 보고한 상태 (진행 중 → 엎드림 · CONFIRMED) 가 화면에 그대로 오는지 본다.

주의: 여기 에이전트는 정해 둔 상태를 보내는 가짜 연결이다. 실제 판정 (Feedback) 까지
지난 결과가 아니며 그것은 S1 (에이전트 단독) · S5 (전체 실행) 에서 본다.
"""
from .test_server_drive import trial
from .test_realtime import app_token, hello, receive, reply, screen, send, state, take


def test_s2_stand_down_request_relays_and_lying_state_reaches_screen(trial, seeded):
    rid = seeded['robots']['mine']
    owner = app_token(trial)
    with trial.websocket_connect('/api/v1/agent/ws', headers={
            'authorization': 'Bearer fake-test-' + str(rid)}) as ag:
        ag.send_json(hello())
        receive(ag, 'lease'); receive(ag, 'stop'); receive(ag, 'field_approval')
        with screen(trial, owner) as ws:
            lease = take(ws, ag, rid)
            assert reply(ws, send(ws, 'sub', robots=[str(rid)], streams=['state']))['ok']

            ident = send(ws, 'posture', rid, lease_id=lease, action='stand_down')
            accepted = reply(ws, ident)
            assert accepted['ok'], accepted               # 서버 접수 (자세 결과 아님)
            relayed = receive(ag, 'posture')
            assert relayed == dict(t='posture', request_id=ident, lease_id=lease, action='stand_down')

            # 에이전트 보고 1: 진행 중 (아직 서 있음)
            ag.send_json(state(3, posture=dict(state='STANDING', mode=0), posture_result=dict(
                request_id=ident, action='stand_down', status='RUNNING', code='STARTED', sdk_code=None)))
            running = receive(ws, 'state', predicate=lambda m: (m.get('posture_result') or {}).get('status') == 'RUNNING')
            assert running['posture'] == dict(state='STANDING', mode=0)
            assert running['posture_result']['request_id'] == ident

            # 에이전트 보고 2: 측정 엎드림 · 같은 요청 번호 · 같은 동작 이름
            ag.send_json(state(3, posture=dict(state='LYING', mode=5), posture_result=dict(
                request_id=ident, action='stand_down', status='SUCCEEDED', code='CONFIRMED', sdk_code=0)))
            done = receive(ws, 'state', predicate=lambda m: (m.get('posture_result') or {}).get('code') == 'CONFIRMED')
            print('\n[S2] 요청 번호 %s · 서버 접수 ok · 에이전트 전달 같은 번호 · 화면 상태 %s · 결과 %s/%s · latched %s'
                  % (ident[:8], done['posture'], done['posture_result']['status'],
                     done['posture_result']['code'], done.get('latched')))
            assert done['posture'] == dict(state='LYING', mode=5)
            assert done['latched'] is True     # 가짜 agent 가 넣은 값의 전달 (실제 잠금 발생은 S1 범위)
            assert done['posture_result'] == dict(request_id=ident, action='stand_down',
                                                  status='SUCCEEDED', code='CONFIRMED', sdk_code=0)


def test_s2_running_only_report_is_not_turned_into_lying(trial, seeded):
    """에이전트가 「진행 중 · 서 있음」 만 보고하면 서버가 스스로 엎드림 · CONFIRMED 로 바꾸지 않는다."""
    rid = seeded['robots']['mine']
    owner = app_token(trial)
    with trial.websocket_connect('/api/v1/agent/ws', headers={
            'authorization': 'Bearer fake-test-' + str(rid)}) as ag:
        ag.send_json(hello())
        receive(ag, 'lease'); receive(ag, 'stop'); receive(ag, 'field_approval')
        with screen(trial, owner) as ws:
            lease = take(ws, ag, rid)
            assert reply(ws, send(ws, 'sub', robots=[str(rid)], streams=['state']))['ok']
            ident = send(ws, 'posture', rid, lease_id=lease, action='stand_down')
            assert reply(ws, ident)['ok']
            assert receive(ag, 'posture')['request_id'] == ident
            for _ in range(3):
                ag.send_json(state(3, posture=dict(state='STANDING', mode=0), posture_result=dict(
                    request_id=ident, action='stand_down', status='RUNNING', code='STARTED', sdk_code=None)))
            # 표지 상태 하나를 더 보내고, 표지가 올 때까지 화면이 받은 상태를 모두 모은다
            marker = state(3, posture=dict(state='STANDING', mode=0), posture_result=dict(
                request_id=ident, action='stand_down', status='RUNNING', code='STARTED', sdk_code=None))
            marker['battery'] = {'soc': 42}   # 서버는 0.1 초마다 현재 상태 스냅숏만 보내므로 표지에도 같은 결과를 실음
            ag.send_json(marker)
            seen = []
            receive(ws, 'state', predicate=lambda m: seen.append(m) or (m.get('battery') or {}).get('soc') == 42)
            ours = [m for m in seen if (m.get('posture_result') or {}).get('request_id') == ident]
            print('\n[S2 부정] 화면이 받은 상태 %d 개 · 이 요청 결과가 붙은 것 %d 개 · 자세 %s'
                  % (len(seen), len(ours), sorted({(m.get('posture') or {}).get('state') for m in seen})))
            assert ours and all(m['posture_result']['status'] == 'RUNNING' for m in ours)
            assert not any((m.get('posture') or {}).get('state') == 'LYING' for m in seen)
            assert not any((m.get('posture_result') or {}).get('code') == 'CONFIRMED' for m in seen)
