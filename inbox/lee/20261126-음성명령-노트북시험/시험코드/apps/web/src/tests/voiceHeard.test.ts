// L 시연 표시 · 결과를 요청 번호로만 짝짓는지 (Codex 재현: 앞 stand_down 결과가 새 「stand up」 문장에 붙음)
import { describe, expect, it } from 'vitest';
import { EMPTY, topic, heardLines, reduceHeard, type HeardEvent, type HeardState } from '../voiceHeard';

const R = 'r1', N = '가짜 Go2 (S5)';
const ev = (e: Partial<HeardEvent>): HeardEvent => ({ robot: R, at_ms: 0, kind: 'heard', ...e } as HeardEvent);
const run = (xs: Partial<HeardEvent>[]) => xs.reduce<HeardState>((s, e) => reduceHeard(s, ev(e)), EMPTY);

describe('음성 시연 안내 줄', () => {
  it('앞 요청 결과는 새 문장에 붙지 않고 자기 문장에만', () => {
    const s = run([
      { kind: 'heard', heard_id: 'h1', heard: 'foothold stand down', intent: 'stand_down', source: 'wav' },
      { kind: 'request', heard_id: 'h1', request_id: 'q1' },
      { kind: 'accepted', request_id: 'q1' },
      { kind: 'heard', heard_id: 'h2', heard: 'foothold stand up', intent: 'stand_up', source: 'wav' },
      { kind: 'result', request_id: 'q1', result: 'CONFIRMED', posture: 'LYING' },
    ]);
    const lines = heardLines(N, s);
    expect(lines).toHaveLength(1);                         // 쌓지 않고 최신 한 줄만
    expect(lines[0]).toMatch(/^1\. /);                     // 늦게 온 결과는 자기 번호 (1) 줄로
    expect(lines[0]).toContain('stand down');
    expect(lines[0]).toContain('행동: 엎드림 (측정 확인)');
    expect(lines[0]).not.toContain('stand up');
  });

  it('미등록 문장 뒤 앞 결과도 그 문장에 붙지 않음 · 짝 없는 결과는 따로', () => {
    const s0: Partial<HeardEvent> = { kind: 'heard', heard_id: 'h3', heard: 'foothold sit down', intent: null, source: 'wav', phrase: 'foothold sit down', match: 'known_unconnected' };
    const s = run([
      s0,
      { kind: 'result', request_id: 'q9', result: 'CONFIRMED', posture: 'STANDING' },
    ]);
    expect(heardLines(N, run([s0]))).toEqual([`1. ${N} 음성 시연(합성 wav) · 들은 명령어: foothold sit down / 행동: 없음 (앉기는 아직 동작 연결 안 함)`]);
    const lines = heardLines(N, s);
    expect(lines).toHaveLength(1);
    expect(lines[0]).toMatch(/^2\. /);
    expect(lines[0]).toContain('앞 요청');
    expect(lines[0]).toContain('행동: 서 있음 (측정 확인)');
  });

  it('요청은 만듦(전송 대기) → 서버 접수 → 완료 순 · 직접 주입은 따로 표시', () => {
    let s = run([{ kind: 'heard', heard_id: 'd1', intent: 'stand_down', source: 'direct' }, { kind: 'request', heard_id: 'd1', request_id: 'q2' }]);
    expect(heardLines(N, s)[0]).toBe(`1. ${N} 음성 시연(인식 없이 직접 주입) · 넣은 명령: 엎드리기 / 행동: 엎드리기 요청 준비 중…`);
    s = reduceHeard(s, ev({ kind: 'accepted', request_id: 'q2' }));
    expect(heardLines(N, s)[0]).toContain('행동: 엎드리기 요청 중… (서버 접수)');
    s = reduceHeard(s, ev({ kind: 'result', request_id: 'q2', result: 'UNKNOWN' }));
    expect(heardLines(N, s)[0]).toContain('행동: 확인 못 함 (결과 없음)');
  });

  it('거부 사유 · 다른 로봇 사건은 상태를 바꾸지 않음 (훅에서 거름)', () => {
    const s = run([{ kind: 'heard', heard_id: 'h4', heard: 'foothold stand down', intent: 'stand_down', source: 'wav' },
      { kind: 'rejected', heard_id: 'h4', why: 'before_grant' }]);
    expect(heardLines(N, s)[0]).toContain('행동: 없음 (받지 않음 · 조종권 받기 전에 들은 말)');
  });

  it('명령 아님 · 부정문 · 부르기는 서로 다르게 · 받아쓴 문장은 그대로', () => {
    const s = run([
      { kind: 'heard', heard_id: 'a', heard: 'the weather is nice too', intent: null, source: 'wav', match: 'none' },
      { kind: 'heard', heard_id: 'b', heard: "foothold don't stand up", intent: null, source: 'wav', match: 'negation' },
    ]);
    expect(heardLines(N, run([{ kind: 'heard', heard_id: 'a', heard: 'the weather is nice too', intent: null, source: 'wav', match: 'none' }])))
      .toEqual([`1. ${N} 음성 시연(합성 wav) · 들은 말: the weather is nice too / 행동: 없음 (명령 아님)`]);
    expect(heardLines(N, s)).toEqual([`2. ${N} 음성 시연(합성 wav) · 들은 말: foothold don't stand up / 행동: 없음 (부정문이라 무시)`]);
    const c = run([{ kind: 'heard', heard_id: 'c', heard: 'hey foothold', intent: null, source: 'wav', phrase: 'hey foothold', match: 'call' }]);
    expect(heardLines(N, c)[0]).toContain('들은 명령어: hey foothold / 행동: 없음 (부르기 인식 · 동작 요청 없음 · 대답 소리 미연결)');
  });

  it('foothold stop 은 «지원 안 함» 으로 표시 (나중 연결 예정처럼 읽히지 않게)', () => {
    const s = run([{ kind: 'heard', heard_id: 's', heard: 'foothold stop', intent: null, source: 'wav', phrase: 'foothold stop', match: 'known_unconnected' }]);
    expect(heardLines(N, s)[0]).toBe(`1. ${N} 음성 시연(합성 wav) · 들은 명령어: foothold stop / 행동: 없음 (음성 정지 미지원 · 이 명령으로 요청 안 함)`);
  });

  it('세션 알림도 번호를 받고, 새 알림이 오면 이전 알림은 안 보임', () => {
    let s = run([{ kind: 'session', state: 'granted' }]);
    expect(heardLines(N, s)).toEqual(['1. 음성 시연 세션이 조종권을 받았습니다']);
    s = reduceHeard(s, ev({ kind: 'heard', heard_id: 'h', heard: 'foothold stand down', intent: 'stand_down', source: 'wav' }));
    expect(heardLines(N, s)).toEqual([`2. ${N} 음성 시연(합성 wav) · 들은 명령어: foothold stand down / 행동: 엎드리기 요청 준비 중…`]);
    s = reduceHeard(s, ev({ kind: 'request', heard_id: 'h', request_id: 'q' }));
    s = reduceHeard(s, ev({ kind: 'result', request_id: 'q', result: 'CONFIRMED', posture: 'LYING' }));
    expect(heardLines(N, s)).toEqual([`2. ${N} 음성 시연(합성 wav) · 들은 명령어: foothold stand down / 행동: 엎드림 (측정 확인)`]);   // 같은 알림은 번호 유지
    s = reduceHeard(s, ev({ kind: 'session', state: 'closed' }));
    expect(heardLines(N, s)).toEqual(['3. 음성 시연 세션 끝']);
  });

  it('앉기 (action 시험 프로필): 서버 접수 → 가짜 Go2 SDK 접수 · 앉음 확인 안 됨 · 세션 끝나면 진행 상태 모름', () => {
    let s = run([
      { kind: 'heard', heard_id: 'h', heard: 'foothold sit down', intent: 'sit_down', source: 'wav', phrase: 'foothold sit down', match: 'command' },
      { kind: 'request', heard_id: 'h', request_id: 'q' }, { kind: 'accepted', request_id: 'q' },
    ]);
    expect(heardLines(N, s)[0]).toContain('행동: 앉기 요청 중… (서버 접수)');
    s = reduceHeard(s, ev({ kind: 'result', request_id: 'q', result: 'SDK_ACCEPTED', posture: 'STANDING' }));
    expect(heardLines(N, s)[0]).toBe(`1. ${N} 음성 시연(합성 wav) · 들은 명령어: foothold sit down / 행동: 앉기 · 가짜 Go2 SDK 접수 (앉음 확인 안 됨)`);
    expect(heardLines(N, s)[0]).not.toContain('측정 확인');
    s = reduceHeard(s, ev({ kind: 'result', request_id: 'q', result: 'UNRESOLVED_AT_END' }));
    expect(heardLines(N, s)[0]).toContain('행동: 앉기 진행 상태 모름 (세션 끝 · 완료·취소 아님)');
    const r = run([{ kind: 'heard', heard_id: 'g', heard: 'foothold get up', intent: 'sit_rise', source: 'wav', match: 'command' },
      { kind: 'request', heard_id: 'g', request_id: 'p' }, { kind: 'result', request_id: 'p', result: 'SDK_ACCEPTED' }]);
    expect(heardLines(N, r)[0]).toContain('행동: 앉은 자세에서 일어서기 · 가짜 Go2 SDK 접수 (앉은 시작 자세 미검증 · 일어섬 확인 안 됨)');
    const x = run([{ kind: 'heard', heard_id: 'k', heard: 'foothold get up', intent: 'sit_rise', source: 'wav' }, { kind: 'rejected', heard_id: 'k', why: 'action_once' }]);
    expect(heardLines(N, x)[0]).toContain('행동: 없음 (받지 않음 · 세션당 동작 한 건 · 이미 보냄)');
  });
});

describe('topic 조사', () => {
  it('받침 있으면 은 · 없으면 는', () => {
    expect(topic('멈춤')).toBe('멈춤은');
    expect(topic('앉기')).toBe('앉기는');
    expect(topic('앉은 자세에서 일어서기')).toBe('앉은 자세에서 일어서기는');
    expect(topic('stop')).toBe('stop는');
  });
});
