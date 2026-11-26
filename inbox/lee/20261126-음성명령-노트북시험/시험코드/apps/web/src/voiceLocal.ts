// 로컬 음성 → 엎드리기 · 일어서기 연동 시험 전용 (가짜 Go2 장치 시험 · 기본 꺼짐).
// 개발 서버(import.meta.env.DEV)이면서 VITE_FH_VOICE_LOCAL=1 일 때만 화면에 «음성 받기»가 보인다.
// 이 값은 빌드 표시일 뿐 인증 · 실기 격리 장치가 아니다 (격리는 로컬 서버 · 가짜 장치 · loopback 으로 한다).
// 음성 프로그램(같은 노트북 loopback 브리지)이 보낸 의도를 «이 화면이 지금 받아도 되는가»로 거르고,
// 받아들이면 화면은 «엎드리기» · «일어서기» 단추와 같은 처리 함수로 기존 자세 요청을 한 번 보낸다.
// 상태(동의 세대 · 처리 중 한 건 · 완료)는 React 렌더와 따로 이 객체가 즉시 갖는다 (같은 틀 안에서 두 의도가 와도 한 건만).
import type { ScreenState } from '../../contracts/ts';
import type { PostureSend } from './rt';

export const VOICE_LOCAL = !!import.meta.env.DEV && import.meta.env.VITE_FH_VOICE_LOCAL === '1';
export const VOICE_EVENTS = '/voice-local/events';
export const VOICE_LOG = '/voice-local/log';
/** 화면 상태가 이보다 오래되면 음성 의도를 받지 않고, 엎드림 완료로도 보지 않는다 */
export const VOICE_STATE_FRESH_MS = 1000;
/** 의도의 유효 기간 상한 (브리지가 더 길게 보내도 이 값으로 자른다) */
export const VOICE_TTL_MAX_MS = 3000;
/** 보낸 요청의 최종 결과를 기다리는 상한 (화면 자세 단추의 POSE_WAIT_MS 와 같은 20 초). 넘으면 «확인 불가» 로 끄고 다시 보내지 않는다 */
export const VOICE_RESULT_WAIT_MS = 20_000;
/** 한 번 본 의도 번호를 기억하는 개수 상한 (이 화면이 켜져 있는 동안만 · 재시작을 넘는 정확히 한 번 보증은 아님) */
export const VOICE_SEEN_MAX = 256;

export type VoiceIntent = { id: string; intent: string; robot: string; issued_at: number; ttl_ms: number };
/** 받는 음성 의도 두 개 (나): 기존 자세 요청 그대로 · 완료로 볼 측정 자세 */
export const VOICE_ACTIONS = {
  stand_down: { pose: 'down', target: 'LYING', label: '엎드림', ask: '엎드리기' },
  stand_up: { pose: 'up', target: 'STANDING', label: '일어섬', ask: '일어서기' },
} as const;
export type VoiceAction = keyof typeof VOICE_ACTIONS;
const isVoiceAction = (x: string): x is VoiceAction => Object.prototype.hasOwnProperty.call(VOICE_ACTIONS, x);

/** 받기 거부 이유 (요청 0 회). 화면 기록에 그대로 남긴다 */
export type VoiceWhy = 'off' | 'malformed' | 'wrong_intent' | 'wrong_robot' | 'expired' | 'duplicate'
  | 'not_mine' | 'link' | 'offline' | 'stale' | 'busy' | 'hidden';

export type VoiceGate = {
  on: boolean; robot: string; mine: boolean; linkOpen: boolean; online: boolean; fresh: boolean;
  busy: boolean; hidden: boolean; now: number; seen: { has(id: string): boolean };
};

export function parseIntent(raw: unknown): VoiceIntent | null {
  if (!raw || typeof raw !== 'object') return null;
  const x = raw as Record<string, unknown>;
  if (typeof x.id !== 'string' || !/^[0-9a-f-]{8,64}$/i.test(x.id) || typeof x.intent !== 'string' ||
      typeof x.robot !== 'string' || !x.robot ||
      typeof x.issued_at !== 'number' || !Number.isFinite(x.issued_at) ||
      typeof x.ttl_ms !== 'number' || !Number.isFinite(x.ttl_ms) || x.ttl_ms <= 0) return null;
  return { id: x.id, intent: x.intent, robot: x.robot, issued_at: x.issued_at, ttl_ms: x.ttl_ms };
}

/** 받아도 되면 null, 아니면 거부 이유. 어느 하나라도 걸리면 거부다 */
export function voiceDecide(raw: unknown, g: VoiceGate): VoiceWhy | null {
  if (!g.on) return 'off';
  const v = parseIntent(raw);
  if (!v) return 'malformed';
  if (g.seen.has(v.id)) return 'duplicate';
  if (!isVoiceAction(v.intent)) return 'wrong_intent';
  if (v.robot !== g.robot) return 'wrong_robot';
  const age = g.now - v.issued_at;
  if (age < 0 || age >= Math.min(v.ttl_ms, VOICE_TTL_MAX_MS)) return 'expired';   // 브리지와 같은 경계 (>=)
  if (g.hidden) return 'hidden';
  if (!g.mine) return 'not_mine';
  if (!g.linkOpen) return 'link';
  if (!g.online) return 'offline';
  if (!g.fresh) return 'stale';
  if (g.busy) return 'busy';
  return null;
}

/** 이 음성 요청의 완료인가: 같은 로봇 · 같은 요청 번호 · 같은 동작 · SUCCEEDED · CONFIRMED + 지금 신선한 측정 자세가 목표
 *  (엎드리기 → LYING · 일어서기 → STANDING) */
export function voiceConfirmed(state: ScreenState | null | undefined, robot: string, requestId: string | null, fresh: boolean,
  action: VoiceAction = 'stand_down'): boolean {
  const res = state?.posture_result;
  return !!requestId && fresh && !!state && state.robot === robot && !!res && res.request_id === requestId
    && res.action === action && res.status === 'SUCCEEDED' && res.code === 'CONFIRMED'
    && state.posture?.state === VOICE_ACTIONS[action].target;
}
/** 같은 요청의 최종 거절 · 실패 (그 요청은 끝 · 뒤늦은 성공을 완료로 잇지 않음) */
function voiceEnded(state: ScreenState | null | undefined, robot: string, requestId: string | null, action: VoiceAction): string | null {
  const res = state?.posture_result;
  if (!requestId || !state || state.robot !== robot || !res || res.request_id !== requestId || res.action !== action) return null;
  return res.status === 'REJECTED' || res.status === 'FAILED' ? `${res.status}/${res.code}` : null;
}

export type VoiceRow = Record<string, unknown> & { kind: string };
/** 보낸 요청 한 건. 동의를 꺼도 이 기록은 남아 다음 요청을 막는다 (재켬만으로 풀리지 않음) */
type Pending = { intent: string; action: VoiceAction; requestId: string | null; at: number; stopN: number; lease: string | null;
  cancelled: boolean; consentLost: boolean; unknown: boolean };
export type VoiceDeps = {
  robot: string;
  gate: () => Omit<VoiceGate, 'on' | 'robot' | 'seen' | 'busy' | 'now'> & { busy: boolean };
  now: () => number;                 // 같은 노트북 벽시계 ms (의도 issued_at 과 같은 기준)
  /** 지금 이 로봇 · 이 화면의 상태 (판정 순간에 다시 읽는다) */
  current: () => { robot: string; lease: string | null; stopN: number; state: ScreenState | null; fresh: boolean };
  /** 화면 단추와 같은 자세 요청을 한 번 (엎드리기 · 일어서기) */
  ask: (action: VoiceAction, onSent: (bad: string | null, requestId: string | null, outcome: PostureSend) => void) => void;
  /** token = 이 연결 전용 기록 토큰 (session 제어 이벤트로 받음 · 없으면 화면 관찰만) */
  log: (row: VoiceRow, token: string | null) => void;
  note: (text: string) => void;
  setOn: (on: boolean) => void;      // 화면 단추 표시만 (진짜 상태는 이 객체)
  open: (url: string) => EventSource;
};

/** 화면 하나 · 로봇 하나의 음성 받기. 동의 세대가 바뀌면 옛 연결 · 옛 콜백은 무시된다.
 *  대상 로봇이 바뀌면 화면은 이 객체를 버리고 새로 만든다 (robot 은 만들 때 고정). */
export class VoiceController {
  private gen = 0;
  private on = false;
  private es: EventSource | null = null;
  private lease: string | null = null;
  private logToken: string | null = null;
  private pending: Pending | null = null;
  private seen = new Set<string>();   // 최근 VOICE_SEEN_MAX 개만 기억 (세션 전체 · 정확히 한 번 보증 아님)
  constructor(private d: VoiceDeps) {}

  private log(row: VoiceRow) { this.d.log(row, this.logToken); }
  get robot() { return this.d.robot; }
  get active() { return this.on; }
  get waiting() { return this.pending; }

  start() {
    this.close('restart');
    const cur = this.d.current();
    if (cur.robot !== this.d.robot) return;
    const gen = ++this.gen, es = this.d.open(VOICE_EVENTS);
    this.on = true; this.es = es; this.lease = cur.lease; this.d.setOn(true);
    es.onmessage = (e) => { if (gen === this.gen && this.on) this.message(e.data); };
    // 의도와 구분되는 제어 이벤트: 기록 전용 토큰 (의도 처리 길로 넣지 않음)
    es.addEventListener('session', (e) => {
      if (gen !== this.gen) return;
      try { const x = JSON.parse((e as MessageEvent).data); if (x?.robot === this.d.robot && typeof x.log_token === 'string') this.logToken = x.log_token; } catch { /* 무시 */ }
    });
    es.onerror = () => { if (gen === this.gen) this.off('음성 연결이 끊겨 음성 받기를 껐습니다. 다시 켜야 받습니다.', 'link_error'); };
    this.log({ kind: 'on', gen });
    if (this.pending) this.d.note('앞 음성 요청의 결과가 아직 없어 새 의도는 받지 않습니다.');
  }

  /** 끄기 (사람 · 숨김 · 연결 · 조종권 · 대상 변경 · 오류 · 확인 불가). 다시 켜야 받는다 · 자동 재동의 없음 */
  off(note: string, why: string) {
    if (!this.on && !this.es) return;
    this.close(why);
    this.d.setOn(false);
    if (note) this.d.note(note);
  }

  private close(why: string) {
    this.gen++;
    if (this.es) { this.es.onmessage = null; this.es.onerror = null; this.es.close(); this.es = null; }
    if (this.on) this.log({ kind: 'off', why });
    this.on = false; this.lease = null; this.logToken = null;
    // 이미 보낸 (또는 보내는 중인) 요청은 잊지 않는다: 긍정 완료 자격만 잃고, 결과가 올 때까지 다음 요청을 막는다
    if (this.pending && !this.pending.consentLost) {
      this.pending.consentLost = true;
      this.log({ kind: 'consent_lost_pending_kept', intent: this.pending.intent, request_id: this.pending.requestId, why });
    }
  }

  /** 사용자 STOP 이 이 요청 뒤에 있었나 (판정 순간에 동기로 비교 · 렌더를 기다리지 않음) */
  private stopped(p: Pending) {
    if (!p.cancelled && this.d.current().stopN !== p.stopN) {
      p.cancelled = true;
      this.log({ kind: 'cancelled_by_stop', intent: p.intent, request_id: p.requestId });
      this.d.note('STOP 으로 음성 요청 결과를 완료로 기록하지 않습니다.');
    }
    return p.cancelled;
  }
  /** 화면의 STOP effect 에서도 부른다 (기록용 · 판정은 stopped() 가 동기로 함) */
  userStop() { if (this.pending) this.stopped(this.pending); }

  private message(data: string) {
    let raw: unknown = null; try { raw = JSON.parse(data); } catch { raw = null; }
    const parsed = parseIntent(raw), g = this.d.gate(), cur = this.d.current();
    const sameTarget = cur.robot === this.d.robot && cur.lease !== null && cur.lease === this.lease;
    const why = voiceDecide(raw, { ...g, mine: g.mine && sameTarget, on: this.on, robot: this.d.robot, now: this.d.now(), seen: this.seen,
      busy: g.busy || this.pending !== null });
    if (parsed && !this.seen.has(parsed.id)) {
      this.seen.add(parsed.id);
      if (this.seen.size > VOICE_SEEN_MAX) this.seen.delete(this.seen.values().next().value!);
    }
    if (why) { this.d.note(`음성 의도 거부 — ${why}`); this.log({ kind: 'rejected', intent: parsed?.id ?? null, why }); return; }
    const gen = this.gen;
    const action = parsed!.intent as VoiceAction;
    const mine: Pending = { intent: parsed!.id, action, requestId: null, at: this.d.now(), stopN: cur.stopN, lease: cur.lease,
      cancelled: false, consentLost: false, unknown: false };
    this.pending = mine;                                  // 요청 전에 한 건을 먼저 잡는다
    this.d.note(`음성 의도 받음 — ${VOICE_ACTIONS[action].ask} 요청`);
    this.log({ kind: 'accepted', intent: mine.intent, action });
    this.d.ask(action, (bad, requestId, outcome) => {
      if (this.pending !== mine) { this.log({ kind: 'late_reply_ignored', intent: mine.intent, request_id: requestId, outcome }); return; }
      if (requestId) mine.requestId = requestId;          // 보낸 번호는 결과를 몰라도 잃지 않는다
      if (outcome === 'rejected' || outcome === 'unsent') {
        this.pending = null; this.log({ kind: 'server_rejected', intent: mine.intent, request_id: requestId, outcome, why: bad }); return;
      }
      if (outcome === 'unknown') {
        // 보낸 뒤 연결이 끊김: 서버가 받았는지 모른다 → 대기를 유지해 다음 요청을 막고, 긍정 기록은 하지 않는다 (자동 재전송 없음)
        mine.unknown = true;
        this.log({ kind: 'send_unknown', intent: mine.intent, request_id: requestId, why: bad });
        return;
      }
      this.checkTarget(mine);
      this.log({ kind: 'server_accepted', intent: mine.intent, request_id: requestId, same_consent: gen === this.gen });
      const now = this.d.current();
      this.evaluate(now.state, now.fresh);                // 결과가 접수 응답보다 먼저 와 있었을 수 있다 (신선도는 지금 다시)
    });
  }

  /** 지금 로봇 · 조종권이 이 요청을 낸 때와 같은가 (판정 순간에 동기로). 다르면 동의 상실로 표시 (추적은 유지 · 긍정 기록 없음) */
  private checkTarget(p: Pending) {
    const cur = this.d.current();
    if (!p.consentLost && (cur.robot !== this.d.robot || cur.lease === null || cur.lease !== p.lease)) {
      p.consentLost = true;
      this.log({ kind: 'consent_lost_pending_kept', intent: p.intent, request_id: p.requestId, why: 'target_or_lease_changed' });
    }
  }

  /** 화면 상태가 바뀔 때마다 (그리고 접수 번호를 받았을 때) 부른다 */
  evaluate(state: ScreenState | null | undefined, fresh: boolean) {
    const p = this.pending;
    if (!p) return;
    const late = this.d.now() - p.at > VOICE_RESULT_WAIT_MS;
    // 1) 기한을 먼저: 넘었으면 이번 판정부터는 긍정 완료를 기록하지 않는다 (확인 불가 · 동의 끔 · 요청은 계속 추적)
    if (late && !p.unknown) {
      p.unknown = true;
      this.log({ kind: 'unknown', intent: p.intent, request_id: p.requestId });
      this.off('음성 요청 결과를 확인하지 못해 음성 받기를 껐습니다. 현장에서 로봇을 확인하세요.', 'result_unknown');
    }
    const ended = voiceEnded(state, this.d.robot, p.requestId, p.action);
    if (ended) { this.pending = null; this.d.note(`음성 요청이 끝났습니다 — ${ended}`); this.log({ kind: 'ended', intent: p.intent, request_id: p.requestId, result: ended }); return; }
    if (!voiceConfirmed(state, this.d.robot, p.requestId, fresh, p.action)) return;
    this.checkTarget(p);
    const cancelled = this.stopped(p);
    this.pending = null;
    if (cancelled || p.consentLost || p.unknown) {
      // 검증된 종결 결과로 추적만 닫는다 (긍정 기록 · 대답 없음)
      this.log({ kind: 'closed_without_confirm', intent: p.intent, request_id: p.requestId,
        why: cancelled ? 'user_stop' : p.unknown ? 'late_or_send_unknown' : 'consent_lost', posture: state!.posture?.state ?? null });
      return;
    }
    const t = VOICE_ACTIONS[p.action];
    this.d.note(`음성 요청 완료 — 측정으로 ${t.label} 확인 (CONFIRMED · ${t.target})`);
    this.log({ kind: 'confirmed', intent: p.intent, action: p.action, request_id: p.requestId, posture: state!.posture?.state ?? null, latched: state!.latched ?? null });
  }
}
