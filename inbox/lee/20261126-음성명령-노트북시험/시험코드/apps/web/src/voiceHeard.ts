// L 시연 전용 · 「음성 시연 (합성 wav 인식)」 안내 줄 (표시만 · 기본 꺼짐).
// 개발 서버(import.meta.env.DEV) + VITE_FH_VOICE_SHOW=1 일 때만 켜진다. tools/voice_local/heard_feed.py 의 SSE 를 읽어
// 노트북 시연 프로그램이 합성 wav 를 인식한 문장 · 만든 요청 · 서버 접수 · 결과를 보여 준다.
// 가짜 Go2 가 직접 들은 것이 아니다. 이 화면은 이 내용으로 로봇에 아무것도 보내지 않는다 (rt 호출 없음).
// 결과는 요청 번호로만 문장에 짝짓는다 (짝 없는 결과는 따로 한 줄).
// 11-25: 알림은 쌓지 않고 가장 최근에 바뀐 한 줄만 보인다 · 앞에 알림 번호 (세션 · 문장마다 하나씩 늘어남).
import { useEffect, useState } from 'react';

export const VOICE_SHOW = !!import.meta.env.DEV && import.meta.env.VITE_FH_VOICE_SHOW === '1';
export const HEARD_EVENTS = '/voice-heard/events';

export type HeardEvent = {
  robot: string; at_ms: number; kind: 'heard' | 'request' | 'accepted' | 'rejected' | 'result' | 'session';
  heard_id?: string | null; request_id?: string | null; source?: 'wav' | 'direct';
  phrase?: string | null; match?: 'command' | 'known_unconnected' | 'call' | 'negation' | 'none';
  heard?: string | null; intent?: string | null; why?: string | null; result?: string | null; posture?: string | null;
  state?: string | null; holder_type?: string | null;
};

type Entry = { key: string; no: number; source: 'wav' | 'direct' | 'orphan'; heard?: string | null; intent?: string | null; phrase?: string | null; match?: HeardEvent['match'];
  stage: 'heard' | 'none' | 'rejected' | 'created' | 'accepted' | 'done'; why?: string | null; result?: string | null;
  posture?: string | null; request_id?: string | null; at: number };
export type HeardState = { entries: Record<string, Entry>; req: Record<string, string>; session: string | null;
  sessionNo: number; sessionAt: number; seq: number; no: number };
export const EMPTY: HeardState = { entries: {}, req: {}, session: null, sessionNo: 0, sessionAt: 0, seq: 0, no: 0 };

const ACT: Record<string, string> = { stand_down: '엎드리기', stand_up: '일어서기', sit_down: '앉기', sit_rise: '앉은 자세에서 일어서기' };
/** action 시험 프로필 (가짜 Go2) 의 접수 뒤 표시 · 접수는 물리 완료가 아니다 */
const AFTER: Record<string, string> = { sit_down: '앉음 확인 안 됨', sit_rise: '앉은 시작 자세 미검증 · 일어섬 확인 안 됨' };
/** 알아들었지만 아직 동작에 연결하지 않은 명령 (11-20 명령 6 개 중) */
const KNOWN: Record<string, string> = { 'foothold sit down': '앉기', 'foothold get up': '앉은 자세에서 일어서기', 'foothold stop': '멈춤' };
const POSTURE: Record<string, string> = { LYING: '엎드림', STANDING: '서 있음' };
const WHY: Record<string, string> = {
  before_grant: '조종권 받기 전에 들은 말', not_held: '음성 세션이 조종권을 쥐고 있지 않음', busy: '앞 요청 결과를 기다리는 중',
  action_once: '세션당 동작 한 건 · 이미 보냄', not_standing: '서 있음 측정이 아님', moving: '이동 입력이 남아 있음',
  expired: '기한 지남', duplicate: '같은 명령 두 번', wrong_intent: '명령 목록에 없음', stale: '로봇 상태가 오래됨', malformed: '형식 오류',
};

/** 사건 하나를 상태에 반영 (같은 의도 번호 · 요청 번호끼리만 합침) */
export function reduceHeard(s: HeardState, e: HeardEvent): HeardState {
  const entries = { ...s.entries }, req = { ...s.req }, at = s.seq + 1;
  let no = s.no;
  const put = (k: string, p: Partial<Entry>) => {
    const old = entries[k] ?? { key: k, no: ++no, source: 'orphan', stage: 'heard', at };
    entries[k] = { ...old, ...p, at };
  };
  switch (e.kind) {
    case 'heard':
      if (!e.heard_id) return s;
      put(e.heard_id, { source: e.source === 'direct' ? 'direct' : 'wav', heard: e.heard ?? null, intent: e.intent ?? null,
        phrase: e.phrase ?? null, match: e.match, stage: e.intent ? 'heard' : 'none' });
      break;
    case 'rejected':
      if (!e.heard_id || !entries[e.heard_id]) return s;
      put(e.heard_id, { stage: 'rejected', why: e.why ?? null });
      break;
    case 'request':
      if (!e.heard_id || !e.request_id || !entries[e.heard_id]) return s;
      req[e.request_id] = e.heard_id;
      put(e.heard_id, { stage: 'created', request_id: e.request_id });
      break;
    case 'accepted': case 'result': {
      if (!e.request_id) return s;
      const k = req[e.request_id] ?? `req:${e.request_id}`;
      if (!req[e.request_id]) req[e.request_id] = k;
      put(k, e.kind === 'accepted' ? { stage: 'accepted', request_id: e.request_id }
        : { stage: 'done', result: e.result ?? null, posture: e.posture ?? null, request_id: e.request_id });
      break;
    }
    case 'session': {
      const text = e.state === 'granted' ? '음성 시연 세션이 조종권을 받았습니다'
        : e.state === 'not_taking' ? '음성 시연 세션: 다른 조종 중이라 조종권을 받지 않았습니다'
        : e.state === 'closed' ? '음성 시연 세션 끝' : null;
      if (!text) return s;
      return { ...s, seq: at, no: s.no + 1, session: text, sessionNo: s.no + 1, sessionAt: at };
    }
  }
  return { ...s, entries, req, seq: at, no };
}

/** 받침이 있으면 「은」, 없으면 「는」 (한글이 아니면 「는」) */
export function topic(word: string): string {
  const c = word.charCodeAt(word.length - 1);
  return word + (c >= 0xac00 && c <= 0xd7a3 && (c - 0xac00) % 28 !== 0 ? '은' : '는');
}

/** 「들은 명령어 / 행동」 한 줄. 행동은 측정으로 확인된 자세만 적는다 (요청만 보낸 동안은 「요청 중」 · 보내지 않았으면 「없음」) */
function entryLine(name: string, x: Entry): string {
  const act = ACT[x.intent ?? ''] ?? x.intent ?? '';
  const isCmd = x.stage !== 'none' || x.match === 'call' || x.match === 'known_unconnected';
  const said = x.heard ? x.heard : '(알아듣지 못함)';
  const head = x.source === 'direct' ? `${name} 음성 시연(인식 없이 직접 주입) · 넣은 명령: ${act}`
    : x.source === 'orphan' ? `${name} 음성 시연 · 앞 요청 (${(x.request_id ?? '').slice(0, 8)}…)`
    : `${name} 음성 시연(합성 wav) · ${isCmd ? '들은 명령어' : '들은 말'}: ${said}`;
  const doing = x.stage === 'none' ? (
      x.match === 'call' ? '없음 (부르기 인식 · 동작 요청 없음 · 대답 소리 미연결)'
      : x.match === 'known_unconnected' && x.phrase === 'foothold stop' ? '없음 (음성 정지 미지원 · 이 명령으로 요청 안 함)'
      : x.match === 'known_unconnected' ? `없음 (${topic(KNOWN[x.phrase ?? ''] ?? x.phrase ?? '')} 아직 동작 연결 안 함)`
      : x.match === 'negation' ? '없음 (부정문이라 무시)'
      : '없음 (명령 아님)')
    : x.stage === 'rejected' ? `없음 (받지 않음 · ${WHY[x.why ?? ''] ?? x.why})`
    : x.stage === 'heard' || x.stage === 'created' ? `${act} 요청 준비 중…`
    : x.stage === 'accepted' ? `${act} 요청 중… (서버 접수)`
    : x.result === 'CONFIRMED' ? `${POSTURE[x.posture ?? ''] ?? x.posture} (측정 확인)`
    : x.result === 'SDK_ACCEPTED' ? `${act} · 가짜 Go2 SDK 접수 (${AFTER[x.intent ?? ''] ?? '동작 확인 안 됨'})`
    : x.result === 'UNRESOLVED_AT_END' ? `${act} 진행 상태 모름 (세션 끝 · 완료·취소 아님)`
    : `확인 못 함 (${x.result === 'UNKNOWN' ? '결과 없음' : x.result})`;
  return `${head} / 행동: ${doing}`;
}

/** 가장 최근에 바뀐 알림 한 줄만 (앞에 알림 번호). 이전 알림은 보이지 않는다 · 각 줄은 자기 번호의 결과만 가짐 */
export function heardLines(name: string, s: HeardState): string[] {
  const x = Object.values(s.entries).sort((a, b) => b.at - a.at)[0];
  if (s.session && (!x || s.sessionAt > x.at)) return [`${s.sessionNo}. ${s.session}`];
  return x ? [`${x.no}. ${entryLine(name, x)}`] : [];
}

export function useVoiceHeard(robot: string, name: string): string[] {
  const [st, setSt] = useState<HeardState>(EMPTY);
  useEffect(() => {
    if (!VOICE_SHOW) return;
    // 알림 통로는 시연이 돌 때만 열린다 → 끊기거나 아직 없으면 2 s 뒤 다시 붙는다 (표시만이라 재연결이 안전)
    let es: EventSource | null = null, timer: ReturnType<typeof setTimeout> | undefined, alive = true;
    const open = () => {
      if (!alive) return;
      es = new EventSource(HEARD_EVENTS);
      es.onmessage = (m) => {
        let e: HeardEvent | null = null;
        try { e = JSON.parse(m.data); } catch { return; }
        if (!e || e.robot !== robot) return;
        setSt((prev) => reduceHeard(prev, e!));
      };
      es.onerror = () => { es?.close(); es = null; timer = setTimeout(open, 2000); };
    };
    open();
    return () => { alive = false; clearTimeout(timer); es?.close(); };
  }, [robot]);
  return VOICE_SHOW ? heardLines(name, st) : [];
}
