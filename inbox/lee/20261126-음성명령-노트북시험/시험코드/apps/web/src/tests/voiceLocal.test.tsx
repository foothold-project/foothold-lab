// S3 · 로컬 음성 → 엎드리기 · 일어서기 연동 시험 (웹 단계 · 가짜 서버 소켓 · 가짜 음성 연결 EventSource).
// 실제 Vosk · 브리지 · 서버 · 에이전트는 없다 (S4 · S5). 화면이 음성 의도를 받아도 되는지 거르고,
// 받으면 «엎드리기» · «일어서기» 단추와 같은 처리로 stand_down · stand_up 을 한 번 보내며, 같은 요청 번호 · 같은 동작의 성공 + 목표 측정 자세만 완료로 기록하는지 본다.
// 팀 serverdrive.test.tsx 의 장치(mount · serve · push)를 최소로 옮겨 썼다.
import { act } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { ScreenState } from '../../../contracts/ts';
import { App } from '../App';
import { ROBOTS, USERS, type Robot } from './fixtures';
import { fleetRow } from './fleetRow';
import { FakeWS, lease, state } from './fakeWs';
import { api } from '../api';
import { ServerDrive } from '../serverdrive';
import { rt } from '../rt';
import { VOICE_RESULT_WAIT_MS, VoiceController, voiceConfirmed, voiceDecide, type VoiceGate, type VoiceRow } from '../voiceLocal';

vi.mock('../voiceLocal', async (orig) => ({ ...(await orig<typeof import('../voiceLocal')>()), VOICE_LOCAL: true }));

(globalThis as { IS_REACT_ACT_ENVIRONMENT?: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

/** 가짜 음성 연결 (브라우저 EventSource 자리) */
class FakeES {
  static all: FakeES[] = [];
  onmessage: ((e: { data: string }) => void) | null = null;
  onerror: (() => void) | null = null;
  closed = false;
  listeners: Record<string, ((e: { data: string }) => void)[]> = {};
  constructor(public url: string) { FakeES.all.push(this); }
  addEventListener(t: string, f: (e: { data: string }) => void) { (this.listeners[t] ??= []).push(f); }
  session(token = 'logtok', robot = 'r7') { act(() => { this.listeners.session?.forEach((f) => f({ data: JSON.stringify({ log_token: token, robot }) })); }); }
  close() { this.closed = true; }
  emit(body: object) { act(() => { this.onmessage?.({ data: JSON.stringify(body) }); }); }
}
const es = () => FakeES.all.filter((x) => !x.closed).pop();

let root: Root | null = null, box: HTMLDivElement, w: FakeWS, st: Record<string, ScreenState> = {};
const PARK = { id: 'u-park', name: '박OO' };
const ON = ROBOTS.map((r) => (r.id === 'r7' ? { ...r, serverDrive: true, approvalUntil: new Date(Date.now() + 30 * 60_000).toISOString() } : r));
function mount(robots: Robot[] = ON) {
  window.matchMedia = ((q: string) => ({ matches: false, media: q, addEventListener() {}, removeEventListener() {} })) as unknown as typeof window.matchMedia;
  location.hash = '#/fleet';
  box = document.createElement('div'); document.body.append(box);
  const u = USERS.find((x) => x.id === 'u-park')!, side = robots.find((x) => x.serverDrive && x.owner === 'u-park')!;
  act(() => { root = createRoot(box); root.render(<><App user={u} robots={robots.map((x) => ({ ...x, serverDrive: false }))} /><ServerDrive c={{ user: u }} r={side} /></>); });
}
const ORG = { battery_low_pct: 20, run_min_battery_pct: 30, deviation_m: 1.5, lease_request_timeout_s: 10, link_loss_wait_s: 30 };
const spySettings = () => vi.spyOn(api, 'settings');
let settingsMock: ReturnType<typeof spySettings>, logs: Record<string, unknown>[] = [], fetchHeaders: Record<string, string>[] = [], fetched: Record<string, unknown>[] = [];
beforeEach(() => {
  vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout', 'setInterval', 'clearInterval', 'Date', 'performance'] });
  settingsMock = spySettings().mockImplementation(() => ({ then: (ok: (o: object) => void) => { ok(ORG); } }) as never);
  FakeES.all = []; logs = []; fetchHeaders = []; fetched = []; currentRobot = 'r7';
  vi.stubGlobal('EventSource', FakeES);
  vi.stubGlobal('fetch', vi.fn((u: string, o: { body: string; headers: Record<string, string> }) => { if (u === '/voice-local/log') { fetchHeaders.push(o.headers); fetched.push(JSON.parse(o.body)); } return Promise.resolve(new Response('{}')); }));
  vi.spyOn(console, 'info').mockImplementation((tag?: unknown, body?: unknown) => { if (tag === '[voice-local]') logs.push(JSON.parse(String(body))); });
});
afterEach(() => {
  act(() => root?.unmount()); settingsMock.mockRestore(); root = null; box?.remove(); vi.useRealTimers(); vi.unstubAllGlobals(); vi.restoreAllMocks();
  delete (document as { visibilityState?: string }).visibilityState;
});
const $ = (s: string) => box.querySelector<HTMLElement>(s);
const btn = (t: string) => [...box.querySelectorAll('button')].find((b) => b.textContent === t)!;
const click = (el: Element) => act(() => { (el as HTMLElement).click(); });
const tick = (ms: number) => act(() => { vi.advanceTimersByTime(ms); });
const push = (r: string, p: Partial<ScreenState> = {}) => { st[r] = { ...(st[r] ?? state(r)), ...p }; w.recv(st[r]); };
const rtSock = () => FakeWS.all.filter((x) => x.url.endsWith('/api/v1/ws')).pop()!;
function serve() {
  w = rtSock(); st = {};
  w.auto = (m) => {
    w.recv({ t: 'reply', id: m.id, ok: true });
    const r = m.robot as string;
    if (m.t === 'lease.take') { w.recv(lease(r, PARK, `L${m.id}`)); w.recv({ t: 'lease.result', robot: r, request_id: null, result: 'ACCEPTED' }); }
    if (m.t === 'unlock') push(r, { latched: false });
    if (m.t === 'lease.release' || m.t === 'hidden') w.recv(lease(r, null));
  };
  act(() => { w.open(); push('r7'); });
}
/** 조종 시작 · 잠금 해제 · 서 있음까지 (팀 시험 ready() 와 같은 순서) */
function ready() {
  mount(); serve();
  click(fleetRow(box, 'Go2-7'));
  click(btn('조종 시작'));
  click(btn('② 잠금 해제'));
  act(() => push('r7', { posture: { state: 'STANDING', mode: 0 } }));
  tick(100);
}
const voiceOn = () => { click($('[data-sd-voice-toggle]')!); FakeES.all.filter((x) => !x.closed).pop()?.session('logtok', currentRobot); };
let currentRobot = 'r7';
let idn = 0;
const uid = () => `00000000-0000-4000-8000-${String(++idn).padStart(12, '0')}`;
const intent = (p: Partial<{ id: string; intent: string; robot: string; issued_at: number; ttl_ms: number }> = {}) =>
  ({ id: uid(), intent: 'stand_down', robot: 'r7', issued_at: Date.now(), ttl_ms: 2000, ...p });
const sent = () => w.of('posture').map((m) => m.action);
const fresh = () => act(() => push('r7', {}));
const result = (request_id: string, action: 'stand_up' | 'stand_down', status: 'RUNNING' | 'SUCCEEDED' | 'REJECTED' | 'FAILED', code: string, posture?: 'LYING' | 'STANDING') =>
  act(() => push('r7', { posture_result: { request_id, action, status, code, sdk_code: status === 'SUCCEEDED' ? 0 : null },
    ...(posture ? { posture: { state: posture, mode: posture === 'LYING' ? 5 : 0 } } : {}) }));
const kinds = (k: string) => logs.filter((x) => x.kind === k);
const reqId = () => w.of('posture')[0].id as string;
/** 서버 접수 응답을 늦게 주는 모드: posture 요청의 reply 를 붙잡아 둔다 */
function holdPostureReply() {
  const held: string[] = [], base = w.auto!;
  w.auto = (m) => { if (m.t === 'posture') { held.push(m.id as string); return; } return base(m); };
  return () => act(() => { held.forEach((id) => w.recv({ t: 'reply', id, ok: true })); });
}

describe('S3 · 판단 함수 (화면 없이)', () => {
  const g = (p: Partial<VoiceGate> = {}): VoiceGate => ({ on: true, robot: 'r7', mine: true, linkOpen: true, online: true, fresh: true,
    busy: false, hidden: false, now: 10_000, seen: new Set<string>(), ...p });
  const A = '0000000a-0000-4000-8000-000000000001';
  const v = (p = {}) => ({ id: A, intent: 'stand_down', robot: 'r7', issued_at: 9_500, ttl_ms: 2000, ...p });
  it('모든 조건이 맞을 때만 받는다 (엎드리기 · 일어서기 두 의도)', () => {
    expect(voiceDecide(v(), g())).toBeNull();
    expect(voiceDecide(v({ intent: 'stand_up' }), g())).toBeNull();
  });
  it.each([
    ['off', v(), { on: false }], ['malformed', { id: 1 }, {}], ['malformed', v({ robot: undefined }), {}],   // 로봇 지정 필수
    ['malformed', v({ id: 'not an id!' }), {}], ['duplicate', v(), { seen: new Set([A]) }],
    ['wrong_intent', v({ intent: 'sit_down' }), {}], ['wrong_intent', v({ intent: 'Sit' }), {}], ['wrong_intent', v({ intent: 'toString' }), {}],
    ['wrong_robot', v({ robot: 'r3' }), {}], ['expired', v({ issued_at: 7_000 }), {}], ['expired', v({ issued_at: 10_500 }), {}],
    ['expired', v({ issued_at: 5_000, ttl_ms: 60_000 }), {}],
    ['hidden', v(), { hidden: true }], ['not_mine', v(), { mine: false }], ['link', v(), { linkOpen: false }],
    ['offline', v(), { online: false }], ['stale', v(), { fresh: false }], ['busy', v(), { busy: true }],
  ])('거부 %s', (why, raw, gate) => { expect(voiceDecide(raw, g(gate as Partial<VoiceGate>))).toBe(why); });
  it('완료 = 같은 로봇 · 같은 번호 · stand_down · SUCCEEDED · CONFIRMED · 신선한 LYING', () => {
    const ok = { request_id: 'q', action: 'stand_down', status: 'SUCCEEDED', code: 'CONFIRMED', sdk_code: 0 };
    const s = (r: object, posture = 'LYING', robot = 'r7') => ({ robot, posture: { state: posture, mode: 5 }, posture_result: r }) as unknown as ScreenState;
    expect(voiceConfirmed(s(ok), 'r7', 'q', true)).toBe(true);
    expect(voiceConfirmed(s(ok, 'STANDING'), 'r7', 'q', true)).toBe(false);     // 성공 결과만 있고 지금 서 있음
    expect(voiceConfirmed(s(ok), 'r7', 'q', false)).toBe(false);                // 상태 오래됨
    expect(voiceConfirmed(s(ok, 'LYING', 'r3'), 'r7', 'q', true)).toBe(false);
    expect(voiceConfirmed(s(ok), 'r7', 'other', true)).toBe(false);
    expect(voiceConfirmed(s(ok), 'r7', null, true)).toBe(false);
    expect(voiceConfirmed(s({ ...ok, action: 'stand_up' }), 'r7', 'q', true)).toBe(false);
    expect(voiceConfirmed(s({ ...ok, status: 'RUNNING', code: 'STARTED' }), 'r7', 'q', true)).toBe(false);
    expect(voiceConfirmed(null, 'r7', 'q', true)).toBe(false);
  });
  it('(나) 일어서기 완료 = 같은 번호 · stand_up · SUCCEEDED · CONFIRMED · 신선한 STANDING (엎드림 · 다른 동작 · 오래됨 아님)', () => {
    const up = { request_id: 'u', action: 'stand_up', status: 'SUCCEEDED', code: 'CONFIRMED', sdk_code: 0 };
    const s = (r: object, posture = 'STANDING') => ({ robot: 'r7', posture: { state: posture, mode: 1 }, posture_result: r }) as unknown as ScreenState;
    expect(voiceConfirmed(s(up), 'r7', 'u', true, 'stand_up')).toBe(true);
    expect(voiceConfirmed(s(up, 'LYING'), 'r7', 'u', true, 'stand_up')).toBe(false);
    expect(voiceConfirmed(s(up), 'r7', 'u', false, 'stand_up')).toBe(false);
    expect(voiceConfirmed(s(up), 'r7', 'u', true)).toBe(false);                          // 기본(엎드리기)으로 보면 아님
    expect(voiceConfirmed(s({ ...up, action: 'stand_down' }, 'STANDING'), 'r7', 'u', true, 'stand_up')).toBe(false);
    expect(voiceConfirmed(s({ ...up, status: 'RUNNING', code: 'STARTED' }), 'r7', 'u', true, 'stand_up')).toBe(false);
  });
});

describe('S3 · 화면에서 음성 의도 소비', () => {
  it('기본 꺼짐 · 조종권 없으면 단추 없음', () => {
    mount(); serve(); click(fleetRow(box, 'Go2-7'));
    expect($('[data-sd-voice-toggle]')).toBeNull();
    click(btn('조종 시작')); click(btn('② 잠금 해제'));
    expect(FakeES.all.length).toBe(0);
  });

  it('정상: 의도 1 → stand_down 1 · UUID 번호 · 성공 + 신선한 LYING 에서만 완료 1 (RUNNING 건너뜀 허용)', () => {
    ready(); voiceOn();
    expect(es()!.url).toBe('/voice-local/events');
    expect(fetchHeaders.every((h) => h['x-voice-log-token'] === 'logtok')).toBe(true);   // 기록에는 기록 토큰만
    const v = intent(); es()!.emit(v);
    expect(sent()).toEqual(['stand_down']);
    const id = reqId();
    expect(id).toMatch(/^[0-9a-f-]{36}$/);
    expect(kinds('server_accepted')[0].request_id).toBe(id);
    result('old', 'stand_down', 'SUCCEEDED', 'CONFIRMED', 'LYING');   // 다른 요청
    expect(kinds('confirmed').length).toBe(0);
    result(id, 'stand_down', 'SUCCEEDED', 'CONFIRMED', 'STANDING');   // 성공 결과지만 지금 서 있음
    expect(kinds('confirmed').length).toBe(0);
    act(() => push('r7', { posture: { state: 'LYING', mode: 5 } }));  // 측정 엎드림
    expect(kinds('confirmed').length).toBe(1);
    expect(kinds('confirmed')[0]).toMatchObject({ intent: v.id, request_id: id, posture: 'LYING' });
    result(id, 'stand_down', 'SUCCEEDED', 'CONFIRMED', 'LYING');
    expect(kinds('confirmed').length).toBe(1);
  });

  it('(나) 엎드린 뒤 「foothold stand up」 의도 → stand_up 1 · 같은 번호 성공 + 신선한 STANDING 에서만 완료 (엎드림 · stand_down 결과로는 아님)', () => {
    ready(); voiceOn();
    act(() => push('r7', { posture: { state: 'LYING', mode: 5 }, latched: true }));   // 엎드림 · 잠금 (팀 규칙: 잠금인 채 일어서기)
    const v = intent({ intent: 'stand_up' }); es()!.emit(v);
    expect(sent()).toEqual(['stand_up']);
    const id = reqId();
    expect(kinds('accepted')[0]).toMatchObject({ intent: v.id, action: 'stand_up' });
    result(id, 'stand_up', 'SUCCEEDED', 'CONFIRMED', 'LYING');       // 성공 결과지만 아직 엎드림
    expect(kinds('confirmed').length).toBe(0);
    result(id, 'stand_down', 'SUCCEEDED', 'CONFIRMED', 'STANDING');  // 같은 번호 · 다른 동작
    expect(kinds('confirmed').length).toBe(0);
    result(id, 'stand_up', 'SUCCEEDED', 'CONFIRMED', 'STANDING');
    expect(kinds('confirmed').length).toBe(1);
    expect(kinds('confirmed')[0]).toMatchObject({ intent: v.id, request_id: id, action: 'stand_up', posture: 'STANDING' });
    expect($('[data-sd-voice-note]')!.textContent).toContain('일어섬 확인 (CONFIRMED · STANDING)');
  });

  it('(나) 엎드리기 완료 뒤 일어서기 음성 → 요청 2 개 (stand_down · stand_up) · 완료 2', () => {
    ready(); voiceOn();
    es()!.emit(intent());
    const down = reqId();
    result(down, 'stand_down', 'SUCCEEDED', 'CONFIRMED', 'LYING');
    es()!.emit(intent({ intent: 'stand_up' }));
    expect(sent()).toEqual(['stand_down', 'stand_up']);
    const up = w.of('posture')[1].id as string;
    result(up, 'stand_up', 'SUCCEEDED', 'CONFIRMED', 'STANDING');
    expect(kinds('confirmed').map((x) => [x.action, x.posture])).toEqual([['stand_down', 'LYING'], ['stand_up', 'STANDING']]);
  });

  it('같은 번호에서 action 이 stand_up → stand_down 으로 바뀌어도 다시 따져서 완료를 놓치지 않음', () => {
    ready(); voiceOn(); es()!.emit(intent());
    const id = reqId();
    result(id, 'stand_up', 'SUCCEEDED', 'CONFIRMED', 'LYING');
    expect(kinds('confirmed').length).toBe(0);
    result(id, 'stand_down', 'SUCCEEDED', 'CONFIRMED', 'LYING');
    expect(kinds('confirmed').length).toBe(1);
  });

  it('최종 결과가 서버 접수 응답보다 먼저 와도 접수 뒤 완료 1', () => {
    ready(); voiceOn();
    const release = holdPostureReply();
    es()!.emit(intent());
    const id = reqId();
    result(id, 'stand_down', 'SUCCEEDED', 'CONFIRMED', 'LYING');
    expect(kinds('confirmed').length).toBe(0);                 // 아직 번호를 모름
    release();
    expect(kinds('server_accepted').length).toBe(1);
    expect(kinds('confirmed').length).toBe(1);
  });

  it('RUNNING · 서버 접수만으로는 완료 아님', () => {
    ready(); voiceOn(); es()!.emit(intent());
    result(reqId(), 'stand_down', 'RUNNING', 'STARTED', 'STANDING');
    expect(kinds('confirmed').length).toBe(0);
  });

  it('최종 거절 → 그 요청은 끝 · 뒤늦은 성공은 완료로 잇지 않음', () => {
    ready(); voiceOn(); es()!.emit(intent());
    const id = reqId();
    result(id, 'stand_down', 'REJECTED', 'MOVING', 'STANDING');
    expect(kinds('ended').length).toBe(1);
    result(id, 'stand_down', 'SUCCEEDED', 'CONFIRMED', 'LYING');
    expect(kinds('confirmed').length).toBe(0);
  });

  it('같은 번호 두 번 · 기한 지남 · 목록 밖 의도 · 다른 로봇 · 로봇 지정 없음 → 0 / 정상 하나만 1', () => {
    ready(); voiceOn();
    es()!.emit(intent({ issued_at: Date.now() - 5_000 }));
    es()!.emit(intent({ intent: 'sit_down' }));
    es()!.emit(intent({ robot: 'r3' }));
    const noRobot = intent(); delete (noRobot as { robot?: string }).robot; es()!.emit(noRobot);
    expect(sent()).toEqual([]);
    const v = intent(); es()!.emit(v); es()!.emit(v);
    expect(sent()).toEqual(['stand_down']);
  });

  it('한 틀 안에서 서로 다른 의도 두 개 → 요청 1 (요청 전에 한 건을 먼저 잡음)', () => {
    ready(); voiceOn();
    const e = es()!;
    act(() => { e.onmessage?.({ data: JSON.stringify(intent()) }); e.onmessage?.({ data: JSON.stringify(intent()) }); });
    expect(sent()).toEqual(['stand_down']);
    expect(kinds('rejected').map((x) => x.why)).toEqual(['busy']);
  });

  it('사람이 단추로 먼저 → 음성은 busy 거부', () => {
    ready(); voiceOn();
    click($('[data-sd-pose="down"]')!);
    es()!.emit(intent());
    expect(sent()).toEqual(['stand_down']);
    expect(kinds('rejected')[0].why).toBe('busy');
  });

  it('화면 상태가 오래되면 거부 · 새 상태 뒤 받음', () => {
    ready(); voiceOn();
    tick(1_500);
    es()!.emit(intent());
    expect(sent()).toEqual([]);
    fresh(); es()!.emit(intent());
    expect(sent()).toEqual(['stand_down']);
  });

  it('수동 끄기 (조종권 유지) 뒤 옛 핸들러가 불려도 요청 0', () => {
    ready(); voiceOn();
    const e = es()!, old = e.onmessage!;
    click($('[data-sd-voice-toggle]')!);
    expect(e.closed).toBe(true);
    act(() => { old({ data: JSON.stringify(intent()) }); });
    expect(sent()).toEqual([]);
  });

  it('한 틀 안에서 오류 다음 메시지 → 요청 0 · 자동 재연결 없음', () => {
    ready(); voiceOn();
    const e = es()!, err = e.onerror!, msg = e.onmessage!;
    act(() => { err(); msg({ data: JSON.stringify(intent()) }); });
    expect(sent()).toEqual([]);
    expect(FakeES.all.filter((x) => !x.closed).length).toBe(0);
    expect($('[data-sd-voice-toggle]')!.textContent).toBe('음성 받기 켜기');
  });

  it('숨김 → 즉시 끔 · 옛 핸들러 무시 · 다시 조종 시작해도 자동 재동의 없음', () => {
    ready(); voiceOn();
    const e = es()!, old = e.onmessage!;
    act(() => { Object.defineProperty(document, 'visibilityState', { value: 'hidden', configurable: true }); document.dispatchEvent(new Event('visibilitychange')); });
    expect(e.closed).toBe(true);
    delete (document as { visibilityState?: string }).visibilityState;
    act(() => { old({ data: JSON.stringify(intent()) }); });
    expect(sent()).toEqual([]);
    if (!$('[data-sd-voice-toggle]')) { click(btn('조종 시작')); tick(100); const u = btn('② 잠금 해제'); if (u) click(u); tick(100); }
    expect(FakeES.all.filter((x) => !x.closed).length).toBe(0);
  });

  it('조종 끝내기 → 끔 · 그 뒤 옛 핸들러 무시', () => {
    ready(); voiceOn();
    const e = es()!, old = e.onmessage!;
    click(btn('조종 끝내기'));
    expect(e.closed).toBe(true);
    act(() => { old({ data: JSON.stringify(intent()) }); });
    expect(sent()).toEqual([]);
  });

  it('STOP 뒤 같은 요청의 늦은 LYING · CONFIRMED → 완료 기록 0', () => {
    ready(); voiceOn(); es()!.emit(intent());
    const id = reqId();
    click($('[data-sd-stop="panel"]') ?? $('[data-sd-stop="full"]')!);
    expect(w.of('stop').length).toBe(1);
    expect(kinds('cancelled_by_stop').length).toBe(1);
    result(id, 'stand_down', 'SUCCEEDED', 'CONFIRMED', 'LYING');
    expect(kinds('confirmed').length).toBe(0);
    expect(kinds('closed_without_confirm').length).toBe(1);
  });

  it('결과 기한 넘김 → 확인 불가 기록 · 음성 받기 끔 · 다시 보내지 않음', () => {
    ready(); voiceOn(); es()!.emit(intent());
    tick(VOICE_RESULT_WAIT_MS + 500); fresh();
    expect(kinds('unknown').length).toBe(1);
    expect($('[data-sd-voice-toggle]')!.textContent).toBe('음성 받기 켜기');
    expect(sent()).toEqual(['stand_down']);
  });

  it('보낸 요청의 결과가 없는데 껐다 켜도 다음 의도는 막힘 (재켬만으로 풀리지 않음)', () => {
    ready(); voiceOn(); es()!.emit(intent());
    expect(sent()).toEqual(['stand_down']);
    click($('[data-sd-voice-toggle]')!);   // 끔
    voiceOn();                             // 다시 켬
    es()!.emit(intent());
    expect(sent()).toEqual(['stand_down']);
    expect(kinds('rejected').map((x) => x.why)).toEqual(['busy']);
    expect(kinds('consent_lost_pending_kept').length).toBe(1);
    result(reqId(), 'stand_down', 'SUCCEEDED', 'CONFIRMED', 'LYING');   // 끈 뒤 온 최종 → 추적만 닫음 (긍정 기록 없음)
    expect(kinds('confirmed').length).toBe(0);
    expect(kinds('closed_without_confirm')[0].why).toBe('consent_lost');
  });

  it('결과 먼저 관측 · 접수 응답 보류 → 한 틀 안에서 STOP 과 접수 해제 → 완료 0', () => {
    ready(); voiceOn();
    const release = holdPostureReply();
    es()!.emit(intent());
    const id = reqId();
    result(id, 'stand_down', 'SUCCEEDED', 'CONFIRMED', 'LYING');
    const stopBtn = ($('[data-sd-stop="panel"]') ?? $('[data-sd-stop="full"]'))!;
    act(() => { stopBtn.click(); w.recv({ t: 'reply', id, ok: true }); });
    release();
    expect(w.of('stop').length).toBe(1);
    expect(kinds('confirmed').length).toBe(0);
    expect(kinds('closed_without_confirm')[0].why).toBe('user_stop');
  });

  it('같은 화면에서 로봇이 r7 → r8 로 바뀌면 옛 대상 의도는 0 · 새 대상 의도만 받음', () => {
    ready();
    const u = USERS.find((x) => x.id === 'u-park')!, r8 = { ...ON.find((x) => x.id === 'r7')!, id: 'r8', name: 'Go2-8' };
    act(() => { root!.render(<><App user={u} robots={ON.map((x) => ({ ...x, serverDrive: false }))} /><ServerDrive c={{ user: u }} r={r8} /></>); });
    act(() => { push('r8', { posture: { state: 'STANDING', mode: 0 } }); });
    click(btn('조종 시작')); tick(100); const unlock = btn('② 잠금 해제'); if (unlock) click(unlock);
    act(() => push('r8', { posture: { state: 'STANDING', mode: 0 } })); tick(100);
    currentRobot = 'r8'; voiceOn();
    es()!.emit(intent({ robot: 'r7' }));
    expect(w.of('posture').filter((m) => m.robot === 'r8').length).toBe(0);
    expect(w.of('posture').length).toBe(0);
    es()!.emit(intent({ robot: 'r8' }));
    expect(w.of('posture').map((m) => [m.robot, m.action])).toEqual([['r8', 'stand_down']]);
  });
});

describe('S3 · 관리 객체 경계 (화면 없이)', () => {
  it('기한을 성공보다 먼저: 20 초 넘어 처음 본 성공은 완료 아님 (확인 불가 · 추적만 닫음)', () => {
    let now = 1_000, sentCb: ((bad: string | null, id: string | null, outcome: 'accepted' | 'rejected' | 'unsent' | 'unknown') => void) | null = null;
    const rows: VoiceRow[] = [], st = (p: object) => ({ robot: 'r7', posture: { state: 'LYING', mode: 5 }, posture_result: p }) as unknown as ScreenState;
    const fake = { onmessage: null as ((e: { data: string }) => void) | null, onerror: null as (() => void) | null, close() {}, addEventListener() {} };
    const c = new VoiceController({
      robot: 'r7', now: () => now, gate: () => ({ mine: true, linkOpen: true, online: true, fresh: true, busy: false, hidden: false }),
      current: () => ({ robot: 'r7', lease: 'L', stopN: 0, state: null, fresh: true }),
      ask: (_a, cb) => { sentCb = cb; }, log: (r) => rows.push(r), note: () => {}, setOn: () => {}, open: () => fake as unknown as EventSource,
    });
    c.start();
    fake.onmessage!({ data: JSON.stringify({ id: '0000000b-0000-4000-8000-000000000001', intent: 'stand_down', robot: 'r7', issued_at: now, ttl_ms: 2000 }) });
    sentCb!(null, 'Q', 'accepted');
    now = 21_500;
    c.evaluate(st({ request_id: 'Q', action: 'stand_down', status: 'SUCCEEDED', code: 'CONFIRMED', sdk_code: 0 }), true);
    expect(rows.filter((r) => r.kind === 'confirmed').length).toBe(0);
    expect(rows.filter((r) => r.kind === 'unknown').length).toBe(1);
    expect(rows.find((r) => r.kind === 'closed_without_confirm')!.why).toBe('late_or_send_unknown');
  });

  it('기록 토큰 전에는 브리지로 기록을 보내지 않음 · 다른 로봇용 토큰은 무시 · 끈 뒤 토큰 폐기', () => {
    ready(); click($('[data-sd-voice-toggle]')!);
    const e = es()!;
    expect(fetchHeaders.length).toBe(0);                 // on 기록은 화면 관찰만
    e.session('wrong', 'r3');
    e.emit(intent());
    expect(fetchHeaders.length).toBe(0);
    e.session('good', 'r7');
    e.emit(intent());                                     // busy 거부 기록 → 이번엔 토큰과 함께
    expect(fetchHeaders.map((h) => h['x-voice-log-token'])).toEqual(['good']);
    click($('[data-sd-voice-toggle]')!);                  // 끔 → 토큰 버림
    const n = fetchHeaders.length;
    result(reqId(), 'stand_down', 'SUCCEEDED', 'CONFIRMED', 'LYING');
    expect(fetchHeaders.length).toBe(n);
  });

  /** 관리 객체 단독 장치: current() 를 바꿀 수 있고 ask 호출 수를 센다 */
  function rig() {
    const rows: VoiceRow[] = [], cbs: ((bad: string | null, id: string | null, o: 'accepted' | 'rejected' | 'unsent' | 'unknown') => void)[] = [];
    const cur = { robot: 'r7', lease: 'L1' as string | null, stopN: 0, state: null as ScreenState | null, fresh: true };
    const fakes: { onmessage: ((e: { data: string }) => void) | null; onerror: (() => void) | null; close(): void; addEventListener(): void }[] = [];
    const c = new VoiceController({
      robot: 'r7', now: () => 5_000, gate: () => ({ mine: true, linkOpen: true, online: true, fresh: true, busy: false, hidden: false }),
      current: () => ({ ...cur }), ask: (_a, cb) => { cbs.push(cb); }, log: (r) => rows.push(r), note: () => {}, setOn: () => {},
      open: () => { const f = { onmessage: null, onerror: null, close() {}, addEventListener() {} }; fakes.push(f); return f as unknown as EventSource; },
    });
    let n = 0;
    const say = () => fakes[fakes.length - 1].onmessage!({ data: JSON.stringify({ id: `0000000c-0000-4000-8000-${String(++n).padStart(12, '0')}`, intent: 'stand_down', robot: 'r7', issued_at: 5_000, ttl_ms: 2000 }) });
    const lying = (id: string) => ({ robot: 'r7', posture: { state: 'LYING', mode: 5 }, posture_result: { request_id: id, action: 'stand_down', status: 'SUCCEEDED', code: 'CONFIRMED', sdk_code: 0 } }) as unknown as ScreenState;
    return { c, rows, cbs, cur, say, lying };
  }

  it('보낸 뒤 연결이 끊겨 접수 불명 → 대기 유지 · 껐다 켜도 새 요청 0 · 그 요청 결과는 긍정 기록 없이 닫음', () => {
    const { c, rows, cbs, say, lying } = rig();
    c.start(); say();
    expect(cbs.length).toBe(1);
    c.off('', 'link');
    cbs[0]('서버 연결이 끊겼습니다.', 'Q1', 'unknown');
    c.start(); say();
    expect(cbs.length).toBe(1);                                   // 새 요청 안 나감
    expect(rows.filter((r) => r.kind === 'rejected').map((r) => r.why)).toEqual(['busy']);
    expect(rows.find((r) => r.kind === 'send_unknown')!.request_id).toBe('Q1');
    c.evaluate(lying('Q1'), true);
    expect(rows.filter((r) => r.kind === 'confirmed').length).toBe(0);
    expect(rows.find((r) => r.kind === 'closed_without_confirm')).toBeTruthy();
  });

  it('보내기 전 실패 · 서버 거절은 대기를 풀어 다음 요청 가능', () => {
    const { c, cbs, say } = rig();
    c.start(); say(); cbs[0]('서버 연결이 끊겼습니다.', 'Q1', 'unsent');
    say(); expect(cbs.length).toBe(2);
    cbs[1]('MOVING', 'Q2', 'rejected');
    say(); expect(cbs.length).toBe(3);
  });

  it('의도 수락 (L1) 뒤 접수 응답 전에 조종권이 L2 로 바뀌면 같은 요청 성공이어도 완료 0', () => {
    const { c, rows, cbs, cur, say, lying } = rig();
    c.start(); say();
    cur.lease = 'L2'; cur.state = lying('Q1');
    cbs[0](null, 'Q1', 'accepted');                               // effect 보다 먼저 접수 응답
    expect(rows.filter((r) => r.kind === 'confirmed').length).toBe(0);
    expect(rows.find((r) => r.kind === 'closed_without_confirm')!.why).toBe('consent_lost');
  });
});

describe('S3 · rt.posture 보낸 결과 세 갈래', () => {
  it('보낸 뒤 끊김은 unknown (같은 요청 번호 유지) · 끊긴 뒤(조종권 없음) 요청은 unsent', () => {
    ready();
    const seen: [string | null, string | undefined, string | undefined][] = [];
    w.auto = (m) => { if (m.t === 'posture') return; w.recv({ t: 'reply', id: m.id, ok: true }); };   // posture 는 답 안 함
    act(() => { rt.posture('r7', 'stand_down', (why, id, o) => { seen.push([why, id, o]); }); });
    const sentId = w.of('posture')[0].id as string;
    act(() => { w.drop(1006); });                                 // 보낸 뒤 끊김
    expect(seen[0][1]).toBe(sentId); expect(seen[0][2]).toBe('unknown');
    act(() => { rt.posture('r7', 'stand_down', (why, id, o) => { seen.push([why, id, o]); }); });   // 끊긴 상태 = 보내기 전 실패
    expect(seen[1][2]).toBe('unsent');
  });
});
