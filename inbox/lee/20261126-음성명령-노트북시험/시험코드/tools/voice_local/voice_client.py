#!/usr/bin/env python3
"""L 단계 · C-1 음성 클라이언트 (사본 전용 · 노트북 loopback 시험용 · 실기 · 운영 서버에 붙이지 않음).

무엇
  음성 의도 (stand_down / stand_up) 를 받아, 팀 서버의 화면 연결 (fh-rt/1) 로 **직접 조종권을 받고**
  기존 자세 요청 (posture) 을 보내는 작은 클라이언트. 버튼 없는 C-1 운용 모드의 노트북 모형이다.

지키는 순서 (11-25 Codex 판정)
  1. 세션은 명시적으로 열 때만 (open · 기간 session_s). 기간이 끝나면 닫는다.
  2. 조종권이 **비어 있을 때만** lease.take. 사람 (USER) · 자동 주행 (RUN) 이 쥐었거나 넘기는 중이면 받지 않고 끝 · 재시도 없음.
  3. 서버가 정지 확인 뒤 이 연결에 조종권 (lease_id) 을 줬을 때부터만 의도를 받는다. 그 전에 들은 말은 버린다.
  4. 쥐는 동안 0 속도 cmd 를 순번대로 (HEARTBEAT_S) 보내 갱신. 이동 · 잠금 해제는 보내지 않는다.
  5. 의도는 한 건씩 · 짧은 기한 · 새 요청 번호. 같은 번호의 결과 (CONFIRMED + 목표 측정 자세) 로만 완료.
  6. 결과 불명 · 연결 끊김 · 조종권 잃음 → 자동 재요청 · 재취득 없이 세션을 닫는다.
  7. 끝낼 때: 실행 자격을 먼저 닫고 → 안 보낸 의도 버리고 → (보낸 요청 결과를 기다린 뒤) lease.release → 해제 확인.
  8. 인식기 건강 신호가 끊기면 세션을 닫는다 (조종권만 붙잡고 남지 않게).

구조
  VoiceSession = 전송과 분리된 상태 기계 (on_message · on_tick · submit · close → 보낼 프레임 목록).
  run_session() = websockets 로 실제 서버에 붙이는 얇은 실행기 (127.0.0.1 만 허용).
"""
import asyncio
import json
import time
import uuid
from urllib.parse import urlsplit

PROTO = 'fh-rt/1'
ACTIONS = {'stand_down': 'LYING', 'stand_up': 'STANDING'}
# 11-25 · 음성 action 요청 · SDK 접수 경로 시험 (명시적 action_profile 일 때만 · 기본 posture 전용 L 은 그대로).
# 접수 (SUCCEEDED + SDK_ACCEPTED + sdk_code 0) 는 물리 완료가 아니다. 앉음 측정 판정 없음 (계약에 SITTING 없음).
SDK_ACTIONS = {'sit_down': 'Sit', 'sit_rise': 'RiseSit'}
HEARTBEAT_S = 1.0          # 서버 만료 15 s 보다 충분히 짧게 (현 코드 조건 · 새 권고 시간 아님)
PING_S = 1.0
TAKE_WAIT_S = 3.0          # 서버 정지 확인 기한 2 s + 여유
RESULT_WAIT_S = 20.0       # 웹 VOICE_RESULT_WAIT_MS 와 같음
INTENT_TTL_MAX_MS = 3000
HEALTH_WAIT_S = 5.0        # 인식기 건강 신호가 이만큼 없으면 닫음
SUB_WAIT_S = 5.0           # 구독 뒤 조종권 스냅숏 대기 상한
RELEASE_WAIT_S = 3.0       # 반납 확인 대기 상한 (넘으면 「반납 미확인」 으로 닫고 연결 종료)
CLOSE_WAIT_S = 5.0         # 받는 중 닫기 뒤 grant/취소 통지 대기 상한


class VoiceSession:
    def __init__(self, robot, session_s, now=time.monotonic, wall_ms=lambda: int(time.time() * 1000), log=None,
                 ids=lambda: str(uuid.uuid4()), action_profile=False):
        import math
        if not isinstance(session_s, (int, float)) or isinstance(session_s, bool) or not math.isfinite(session_s) or session_s <= 0:
            raise ValueError('session_s 는 유한한 양수')
        self.robot, self.session_s, self.now, self.wall_ms, self.ids = robot, session_s, now, wall_ms, ids
        self.rows = []
        self._log = log
        self.phase = 'idle'          # idle → subscribing → taking → held → closing → closed
        self.why = None              # 닫힌 이유
        self.until = None
        self.first = True
        self.holder = 'unknown'      # 'unknown' | None | dict
        self.lease = None
        self.grant_wall = None       # 조종권을 받은 벽시계 ms (이 전에 들은 말은 버림)
        self.gate = False            # 음성 실행 자격 (조종권과 별개)
        self.seq = 0
        self.next_beat = 0.0
        self.next_ping = 0.0
        self.take_deadline = None
        self.pending = None          # 보낸 요청 한 건
        self.seen = set()
        self.replies = {}            # 프레임 id → 종류
        self.health_at = None
        self.state = None            # 마지막 화면 상태 (이 로봇)
        self.release_sent = False
        self.deadline = None         # 구독 · 받는 중 닫기 · 반납 확인의 상한 (monotonic)
        self.must_disconnect = False # 실행기가 연결을 끊어야 함 (반납 미확인 등)
        self.release_unconfirmed = False  # 반납을 보냈지만 서버 확인을 못 받음 (닫는 이유와 별개)
        self.release_seen = False         # 반납 뒤 「조종권 없음」 알림을 봄 (근거 1)
        self.release_reply = None         # 반납 접수 답 (True/False · 근거 2)
        self.counts = dict(take=0, release=0, cmd=0, posture=0, unlock=0, action=0)
        self.action_profile = bool(action_profile)
        self.action_used = False          # 세션당 action 한 건: 한 번 보내면 이 세션에서 동작 의도를 더 받지 않음
        self.action_unresolved = False    # SDK 접수 뒤 물리 실행 미확인 (접수 ≠ 완료 · 이 세션에서 풀리지 않음)

    # ── 기록 ──
    def log(self, kind, **kw):
        row = dict(kind=kind, phase=self.phase, wall_ms=self.wall_ms(), **kw)
        self.rows.append(row)
        if self._log:
            self._log(row)

    def frame(self, t, **body):
        fid = self.ids()
        msg = dict(id=fid, t=t, **body)
        if self.first:
            msg['proto'] = PROTO
            self.first = False
        self.replies[fid] = t
        if t == 'lease.take': self.counts['take'] += 1
        elif t == 'lease.release': self.counts['release'] += 1
        elif t == 'cmd': self.counts['cmd'] += 1
        elif t == 'posture': self.counts['posture'] += 1
        elif t == 'unlock': self.counts['unlock'] += 1
        elif t == 'action': self.counts['action'] += 1
        return msg

    # ── 세션 열기 · 닫기 ──
    def open(self):
        if self.phase != 'idle':
            return []
        self.until = self.now() + self.session_s
        self.health_at = self.now()
        self.phase = 'subscribing'
        self.deadline = self.now() + SUB_WAIT_S
        self.log('open', session_s=self.session_s)
        return [self.frame('sub', robots=[self.robot], streams=['state'])]

    def close(self, why):
        """실행 자격을 먼저 닫고, 안 보낸 의도는 없다 (한 건씩이라 큐 없음). 보낸 요청은 결과를 기다린 뒤 반납."""
        if self.phase in ('closing', 'closed'):
            return []
        self.gate = False
        self.why = self.why or why
        self.log('close_begin', why=why, pending=bool(self.pending))
        self._note_unresolved(why)
        if self.phase in ('idle', 'subscribing') or (self.phase == 'taking' and not self.lease):
            # 아직 조종권이 없다: 반납할 것 없음 (taking 중이면 서버 정지 확인 결과는 그대로 둔다)
            self.phase = 'closed' if self.phase != 'taking' else 'closing'
            if self.phase == 'closed':
                self.log('closed', why=self.why)
            else:
                self.deadline = self.now() + CLOSE_WAIT_S
            return []
        self.phase = 'closing'
        self.deadline = None                            # 이전 단계 (구독) 기한을 공유하지 않음
        return self._maybe_release()

    def _maybe_release(self):
        if self.phase != 'closing' or self.release_sent:
            return []
        if self.pending and not self.pending.get('done'):
            return []                                   # 보낸 요청은 결과 · 기한까지 추적
        if not self.lease:
            self.phase = 'closed'
            self.log('closed', why=self.why)
            return []
        self.release_sent = True
        self.deadline = self.now() + RELEASE_WAIT_S
        return [self.frame('lease.release', robot=self.robot)]

    def _lost(self, why):
        """조종권을 잃음 · 연결 끊김: 다시 잡지 않고 닫는다."""
        self.gate = False
        self._note_unresolved(why)
        self.lease = None
        if self.pending and not self.pending.get('done'):
            self.pending.update(done=True, unknown=True)
            self.log('pending_unknown', request_id=self.pending['id'], why=why)
        if self.release_sent and not self.release_unconfirmed:
            self.release_unconfirmed = True
            self.log('close_unconfirmed', why='release_unconfirmed')   # 반납 확인 못 함 — 닫는 이유 (handover 등) 와 별도
        self.why = self.why or why
        self.phase = 'closed'
        self.deadline = None
        self.log('closed', why=self.why)

    def _note_unresolved(self, why):
        """SDK 접수 뒤 세션이 끝남: 진행 상태 모름으로만 기록 (완료 · 취소로 적지 않음). 한 번만."""
        if self.action_unresolved and not getattr(self, '_unresolved_logged', False):
            self._unresolved_logged = True
            p = self.pending or {}
            self.log('action_unresolved_at_end', request_id=p.get('id'), action=p.get('action'), why=why)

    # ── 인식기 쪽 ──
    def health(self):
        """건강 신호. 먼저 지금까지의 무응답 기한을 적용하고 (끝난 세션을 되살리지 않음), 살아 있을 때만 갱신."""
        out = self._enforce()
        if self.phase in ('subscribing', 'taking', 'held'):
            self.health_at = self.now()
        return out

    def _enforce(self):
        """입력 · 결과 · 건강 신호를 처리하는 순간에 먼저 기한을 적용한다 (주기 점검을 기다리지 않음)."""
        out, at = [], self.now()
        if self.phase == 'closed':
            return out
        if self.pending and not self.pending.get('done') and at - self.pending['sent'] >= RESULT_WAIT_S:
            self.pending.update(done=True, unknown=True)
            self.log('pending_unknown', request_id=self.pending['id'], why='result_timeout')
            out += self.close('result_unknown') if self.phase == 'held' else self._maybe_release()
        if self.phase in ('subscribing', 'taking', 'held'):
            if self.until is not None and at >= self.until:
                out += self.close('session_expired')
            elif self.health_at is not None and at - self.health_at >= HEALTH_WAIT_S:
                out += self.close('recognizer_silent')
        if self.phase == 'taking' and not self.lease and self.take_deadline is not None and at >= self.take_deadline:
            # 받기 기한 넘음: 닫는 중으로 (늦게 온 grant 는 실행 자격 없이 바로 반납)
            out += self.close('take_timeout')
        if self.phase in ('subscribing', 'closing') and self.deadline is not None and at >= self.deadline:
            why = 'subscribe_timeout' if self.phase == 'subscribing' else ('release_unconfirmed' if self.release_sent else 'close_wait_timeout')
            self.gate = False
            self.why = self.why or why
            if self.pending and not self.pending.get('done'):
                self.pending.update(done=True, unknown=True)
                self.log('pending_unknown', request_id=self.pending['id'], why=why)
            if self.phase == 'closing':
                if self.release_sent:
                    self.release_unconfirmed = True
                self.log('close_unconfirmed', why=why)   # 서버 회수 여부는 모름 — 반납 확인으로 적지 않음
            self.phase = 'closed'
            self.deadline = None
            self.must_disconnect = True
            self.log('closed', why=self.why)
        return out

    def submit(self, intent):
        """의도 한 건. 받으면 posture 프레임 하나, 아니면 [] (거부 사유는 기록). 기한 · 닫기 프레임이 먼저 올 수 있다."""
        pre = self._enforce()
        why = self._reject_reason(intent)
        iid = intent.get('id') if isinstance(intent, dict) else None
        if isinstance(iid, str):
            self.seen.add(iid)
        if why:
            self.log('intent_rejected', intent=iid, why=why)
            return pre
        action = intent['intent']
        rid = self.ids()
        kind = 'action' if action in SDK_ACTIONS else 'posture'
        self.pending = dict(id=rid, intent=iid, action=action, kind=kind, sent=self.now(), acked=False, done=False)
        if kind == 'action':
            self.action_used = True
            self.pending['sdk'] = SDK_ACTIONS[action]
            self.log('intent_accepted', intent=iid, action=action, request_id=rid, sdk_action=SDK_ACTIONS[action],
                     start_posture=('STANDING_observed' if action == 'sit_down' else 'unverified'))
            msg = self.frame('action', robot=self.robot, lease_id=self.lease, action=SDK_ACTIONS[action],
                             params={}, confirmed=False)
        else:
            self.log('intent_accepted', intent=iid, action=action, request_id=rid)
            msg = self.frame('posture', robot=self.robot, lease_id=self.lease, action=action)
        msg['id'] = rid
        self.replies[rid] = kind
        return pre + [msg]

    def _reject_reason(self, x):
        if not isinstance(x, dict) or not isinstance(x.get('id'), str) or not isinstance(x.get('issued_at'), int) \
                or not isinstance(x.get('ttl_ms'), int) or x.get('robot') != self.robot:
            return 'malformed'
        if x['id'] in self.seen:
            return 'duplicate'
        if x.get('intent') not in ACTIONS and not (self.action_profile and x.get('intent') in SDK_ACTIONS):
            return 'wrong_intent'
        if self.phase != 'held' or not self.gate or not self.lease:
            return 'not_held'
        if self.grant_wall is None or x['issued_at'] < self.grant_wall:
            return 'before_grant'                      # 조종권 받기 전에 들은 말은 재생하지 않음
        age = self.wall_ms() - x['issued_at']
        if age < 0 or age >= min(x['ttl_ms'], INTENT_TTL_MAX_MS):
            return 'expired'
        if self.pending and not self.pending.get('done'):
            return 'busy'
        if self.action_used:
            return 'action_once'                       # 세션당 action 한 건 (접수 뒤 실행 미확인 · 거절 · 실패 모두)
        if not self._fresh():
            return 'stale'
        if x['intent'] == 'sit_down':
            # 관측 가능한 사전 검사만 (화면 상태의 자세 · 적용 입력). 에이전트의 최종 정지 검사와는 별개.
            if (self.state.get('posture') or {}).get('state') != 'STANDING':
                return 'not_standing'
            if self.state.get('applied') != [0, 0, 0]:
                return 'moving'
        return None

    def _fresh(self):
        return (self.state is not None and self.state.get('connection') == 'ONLINE'
                and self.now() - self.state['_at'] < 1.0)

    # ── 서버 메시지 ──
    def on_message(self, m):
        if self.phase == 'closed':
            if m.get('t') == 'reply' and self.replies.get(m.get('id')) == 'lease.release':
                self.replies.pop(m.get('id'))
                self._release_reply(m)                    # 근거 기록만 (상태는 이미 닫힘)
                return []
            if (m.get('t') == 'lease' and m.get('robot') == self.robot and self.release_sent
                    and 'holder' in m and m['holder'] is None):
                self._release_observed()                  # 근거 기록만
                return []
            res_key = 'action_result' if (self.pending or {}).get('kind') == 'action' else 'posture_result'
            if (m.get('t') == 'state' and self.pending and m.get('robot') == self.robot
                    and (m.get(res_key) or {}).get('request_id') == self.pending['id']):
                r = m.get(res_key) or {}
                key = (r.get('status'), r.get('code'))
                if key != getattr(self, '_late_seen', None):    # 같은 늦은 결과는 한 번만 기록
                    self._late_seen = key
                    self.log('late_result_ignored', request_id=self.pending['id'], status=r.get('status'),
                             code=r.get('code'))                 # 추적 기록만 · 완료로 바꾸지 않음
            return []
        out = self._enforce()
        if self.phase == 'closed':
            return out
        t = m.get('t')
        if t == 'subscription.revoked' and m.get('robot') == self.robot:
            return out + self.close('subscription_revoked')
        if t == 'state' and m.get('robot') == self.robot and m.get('connection') != 'ONLINE':
            self.state = dict(m, _at=self.now())          # 끊긴 상태의 과거 결과는 완료로 읽지 않음
            if self.phase in ('held', 'taking'):
                out += self.close('robot_offline')
            return out
        if t == 'reply':
            kind = self.replies.pop(m.get('id'), None)
            out += self._on_reply(kind, m)
        elif t == 'lease' and m.get('robot') == self.robot:
            out += self._on_lease(m)
        elif t == 'lease.result' and m.get('robot') == self.robot and m.get('request_id') is None:
            if self.phase in ('taking', 'closing') and not self.lease:
                self.log('take_canceled', result=m.get('result'), error=m.get('error'))
                self.why = self.why or ('take_' + str(m.get('error') or m.get('result')).lower())
                self.phase = 'closed'
                self.log('closed', why=self.why)
        elif t == 'state' and m.get('robot') == self.robot:
            self.state = dict(m, _at=self.now())
            out += self._check_result()
        return out

    def _on_reply(self, kind, m):
        if m.get('ok'):
            if kind in ('posture', 'action') and self.pending and self.pending['id'] == m.get('id'):
                self.pending['acked'] = True
                self.log(kind + '_accepted_by_server', request_id=m.get('id'))
                return self._check_result()
            if kind == 'lease.release':
                self._release_reply(m)
                self.lease = None
                self.phase = 'closed'
                self.deadline = None
                self.log('closed', why=self.why, basis='release_reply_ok')
            return []
        code = (m.get('error') or {}).get('code')
        if kind == 'lease.release':
            self._release_reply(m)
        self.log('reply_error', frame=kind, code=code)
        if kind == 'lease.take':
            self.why = self.why or ('take_refused_' + str(code).lower())
            self.phase = 'closed'
            self.log('closed', why=self.why)
            return []
        if kind in ('posture', 'action') and self.pending and self.pending['id'] == m.get('id'):
            self.pending.update(done=True, refused=code)
            return self._maybe_release()
        if kind == 'cmd' and code in ('LEASE_MISMATCH', 'CMD_SEQ'):
            self._lost('heartbeat_' + code.lower())
        return []

    def _on_lease(self, m):
        holder, lease = m.get('holder'), m.get('lease_id')
        self.holder = holder
        if self.phase == 'subscribing':
            if holder is None:
                self.phase = 'taking'
                self.deadline = None
                self.take_deadline = self.now() + TAKE_WAIT_S
                self.log('take', reason='free')
                return [self.frame('lease.take', robot=self.robot)]
            kind = (holder or {}).get('holder_type')
            self.log('not_taking', holder_type=kind)
            self.why = 'held_by_' + str(kind).lower()
            self.phase = 'closed'
            self.log('closed', why=self.why)
            return []
        if self.phase == 'closing' and not self.lease and lease:
            # 받는 중에 닫기로 했는데 서버가 조종권을 줌: 실행 자격 없이 바로 반납 (의도 받지 않음)
            self.lease = lease
            self.log('granted_while_closing', lease_id=lease)
            return self._maybe_release()
        if self.phase == 'taking' and lease:
            self.lease, self.phase, self.gate = lease, 'held', True
            self.deadline = self.take_deadline = None
            self.grant_wall = self.wall_ms()
            self.next_beat = self.now()
            self.log('granted', lease_id=lease)
            return []
        if self.phase == 'closing' and self.release_sent and 'holder' in m and m['holder'] is None:
            # 반납을 보낸 뒤 서버가 「이 로봇 조종권 없음」 을 알림 → 반납 관측으로 닫는다.
            # 반납 접수 답 (reply) 을 받은 것으로 적지 않는다 (답은 따로 기록) · 회수 원인까지 확정하지 않음.
            self._release_observed()
            self.gate = False
            self.lease = None
            self.phase = 'closed'
            self.deadline = None
            self.log('closed', why=self.why, basis='holder_null_broadcast')
            return []
        if self.phase in ('held', 'closing') and self.lease and lease != self.lease:
            self._lost('lease_lost')
        return []

    def _release_observed(self):
        if not self.release_seen:
            self.release_seen = True
            self.log('release_observed', basis='holder_null_broadcast')

    def _release_reply(self, m):
        if self.release_reply is None:
            self.release_reply = bool(m.get('ok'))
            self.log('release_reply_ok' if m.get('ok') else 'release_reply_error',
                     code=None if m.get('ok') else (m.get('error') or {}).get('code'))

    def _check_result(self):
        p, s = self.pending, self.state
        if self.phase == 'closed' or not p or p.get('done') or not p['acked'] or not s:
            return []
        if self.now() - p['sent'] >= RESULT_WAIT_S:
            return self._enforce()
        if p.get('kind') == 'action':
            return self._check_action(p, s)
        res = s.get('posture_result') or {}
        if res.get('request_id') != p['id'] or res.get('action') != p['action']:
            return []
        if res.get('status') in ('REJECTED', 'FAILED'):
            p.update(done=True, result=f"{res['status']}/{res.get('code')}")
            self.log('ended', request_id=p['id'], result=p['result'])
            return self._maybe_release()
        if res.get('status') == 'SUCCEEDED' and res.get('code') == 'CONFIRMED' and self._fresh() \
                and (s.get('posture') or {}).get('state') == ACTIONS[p['action']]:
            p.update(done=True, result='CONFIRMED')
            self.log('confirmed', request_id=p['id'], action=p['action'], posture=s['posture']['state'], latched=s.get('latched'))
            return self._maybe_release()
        return []

    def _check_action(self, p, s):
        """action 결과는 action_result 로만 · robot · request_id · SDK 이름이 모두 맞을 때. RUNNING 은 접수 아님."""
        res = s.get('action_result') or {}
        if s.get('robot') != self.robot or res.get('request_id') != p['id'] or res.get('action') != p['sdk']:
            return []
        st = res.get('status')
        if st in ('REJECTED', 'FAILED'):
            p.update(done=True, result=f"{st}/{res.get('code')}")
            self.log('ended', request_id=p['id'], action=p['action'], result=p['result'], sdk_code=res.get('sdk_code'))
            return self._maybe_release()
        if st == 'SUCCEEDED':
            if res.get('code') == 'SDK_ACCEPTED' and res.get('sdk_code') == 0 and type(res.get('sdk_code')) is int:
                p.update(done=True, result='SDK_ACCEPTED')
                self.action_unresolved = True               # 물리 실행 미확인 · 다음 의도는 action_once 로 계속 거부
                self.log('sdk_accepted', request_id=p['id'], action=p['action'], sdk_action=p['sdk'],
                         posture=(s.get('posture') or {}).get('state'), physical='unverified')
                if self.phase == 'closing':
                    self._note_unresolved(self.why)     # 닫는 중 접수: 기존 닫는 이유로 미확인 종료 한 번 (Codex 보완 1)
            else:
                # SUCCEEDED 지만 접수 조건 (SDK_ACCEPTED · sdk_code 0) 이 아님 — 거절 · 실패와 구분되는 예상 밖 결과 형식
                p.update(done=True, result=f"SUCCEEDED/{res.get('code')}/{res.get('sdk_code')}")
                self.log('unexpected_result', request_id=p['id'], action=p['action'], status=st,
                         code=res.get('code'), sdk_code=res.get('sdk_code'))
            return self._maybe_release()
        return []

    # ── 시간 ──
    def on_tick(self):
        out, at = [], self.now()
        if self.phase in ('closed', 'idle'):
            return out
        if at >= self.next_ping:
            self.next_ping = at + PING_S
            out.append(self.frame('ping'))
        out += self._enforce()
        if self.phase == 'closed':
            return out
        if self.lease and self.phase in ('held', 'closing') and not self.release_sent and at >= self.next_beat:
            self.next_beat = at + HEARTBEAT_S
            self.seq += 1
            out.append(self.frame('cmd', robot=self.robot, lease_id=self.lease, seq=self.seq, axes=[0, 0, 0]))
        return out

    def on_disconnect(self, why='connection_lost'):
        if self.phase != 'closed':
            self._lost(why)                               # 반납을 보냈었다면 _lost 가 release_unconfirmed 를 따로 남김


# ── 실제 서버에 붙이는 실행기 (L 시험 · 127.0.0.1 만) ──
def check_loopback(base):
    u = urlsplit(base)
    try:
        port = u.port
    except ValueError:
        port = None
    if u.scheme != 'http' or u.hostname != '127.0.0.1' or port is None or u.username or u.password or u.path not in ('', '/'):
        raise SystemExit('L 시험은 http://127.0.0.1:<포트> 서버만 허용')
    return f'ws://127.0.0.1:{port}/api/v1/ws'


def check_ws(url):
    """실행 주소: ws · 정확히 127.0.0.1 · 유효한 명시 포트 · /api/v1/ws · userinfo/query/fragment 없음."""
    u = urlsplit(url)
    try:
        port = u.port
    except ValueError:
        port = None
    if (u.scheme != 'ws' or u.hostname != '127.0.0.1' or '@' in u.netloc or port is None or not 1 <= port <= 65535
            or u.path != '/api/v1/ws' or u.query or u.fragment):
        raise ValueError('loopback 시험 서버 WS 주소만 허용')
    return url


def app_login(base, username, password):
    """앱 세션 (client=app) 하나를 만든다. 토큰은 메모리에만 (기록 · 출력 안 함). 주소는 I/O 전에 검사."""
    check_loopback(base)
    import urllib.request
    req = urllib.request.Request(base.rstrip('/') + '/api/v1/auth/login', method='POST',
                                 data=json.dumps(dict(username=username, password=password, client='app',
                                                      device_label='voice-L')).encode(),
                                 headers={'content-type': 'application/json'})
    with urllib.request.urlopen(req, timeout=5) as r:
        return json.loads(r.read())['access_token']


async def run_session(session, ws_url, token, intents, *, tick_s=0.05, stop=None):
    """intents: asyncio.Queue — ('intent', dict) · ('health',) · ('close', why) 를 넣는다."""
    check_ws(ws_url)                              # 네트워크 함수 전에
    import websockets
    async with websockets.connect(ws_url, additional_headers={'authorization': f'Bearer {token}'},
                                  max_size=2 ** 20) as ws:
        async def send(frames):
            for f in frames:
                await ws.send(json.dumps(f))

        async def reader():
            try:
                async for raw in ws:
                    m = json.loads(raw)
                    await send(session.on_message(m))
                    if session.phase == 'closed':
                        return
            except websockets.ConnectionClosed:
                pass
            session.on_disconnect()

        rd = None
        try:
            await send(session.open())                # 첫 송신 오류도 아래 finally 로 정리
            rd = asyncio.create_task(reader())
            while session.phase != 'closed' and not rd.done():
                try:
                    item = await asyncio.wait_for(intents.get(), timeout=tick_s)
                    if item[0] == 'intent':
                        await send(session.submit(item[1]))
                    elif item[0] == 'health':
                        await send(session.health())
                    elif item[0] == 'close':
                        await send(session.close(item[1]))
                    elif item[0] == 'drop':       # 시험용: 프로세스가 죽은 것처럼 연결만 끊음
                        await ws.close()
                        break
                except asyncio.TimeoutError:
                    pass
                await send(session.on_tick())
                if stop is not None and stop.is_set():
                    await send(session.close('stopped'))
                if session.must_disconnect:
                    break
            if session.must_disconnect:
                await ws.close()
        finally:
            # 어떤 오류 · 취소에서도 실행 자격을 닫는다 (오류 전파와 별개)
            reader_error = None
            if rd is not None:
                rd.cancel()
                try:
                    await rd
                except asyncio.CancelledError:
                    pass
                except BaseException as e:        # 깨진 메시지 등 reader 오류
                    reader_error = e
            if session.phase != 'closed':
                session.on_disconnect('runner_error' if reader_error else 'connection_lost')
            if reader_error is not None:
                raise reader_error
    return session
