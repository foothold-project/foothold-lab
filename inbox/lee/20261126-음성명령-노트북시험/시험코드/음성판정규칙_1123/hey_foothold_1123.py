#!/usr/bin/env python3
"""시험 1 · 2 (11-20 판): 노트북 마이크 → 「hey foothold」 정확 일치일 때만 소리로 대답.
11-19 hey_foothold.py 와 같은 판정 (Vosk 제한 문법 · 최종 결과가 정확히 ['hey','foothold']).
바뀐 점: 한 번 말할 때마다 화면에 한 줄 — 「대답함」 또는 「대답 안 함 + 참고 받아쓰기」.
  참고 받아쓰기는 화면 표시용으로 따로 돌리는 자유 받아쓰기이며 판정에 쓰지 않는다.
  두 받아쓰기의 문장 경계가 정확히 같다는 보장은 없다 (참고용).
- 원음은 메모리에서만 처리 (저장 · 전송 없음).
- --log-text 를 주면 받아쓴 글자도 기록에 남긴다 (시험 1 · 2 용). 주지 않으면 글자는 화면에만 (시험 6 용).
- 대답 중 · 대답 뒤 REARM_S 동안 들어온 소리는 버린다.
11-23 사본 (원본 26.11.20/.../hey_foothold_1120.py 는 그대로): 사용자 결정으로 「foothold rise sit」 → 「foothold get up」 (대답 「Get up」 · 동작은 그대로 RiseSit).
--commands 를 주면 명령 6 개 (hey foothold · foothold stand up / stand down / sit down / get up / stop) 를 듣고
  명령 말 그대로 소리로 대답한다 (거부 보기로 판정된 문장은 대답 안 함 · 부정문을 명령으로 잘못 알아들을 수 있음 · 노트북 소리만 · 로봇에 아무것도 보내지 않음).
사용: python hey_foothold_1123.py --model <모델 폴더> --log <기록 파일> [--label 이름] [--log-text] [--commands]
      python hey_foothold_1123.py --model <모델 폴더> --selftest   (합성 목소리로 작동만 확인)
끝내기: Ctrl+C
"""
import argparse, array, json, math, os, queue, signal, subprocess, sys, threading, time

RATE = 16000
CHUNK = 4000            # 바이트 = 2000 표본 = 0.125 초
REARM_S = 0.6
REPLY = "Yes, I'm listening"
TARGET = ["hey", "foothold"]
# --commands 판: 사용자 결정 명령 6 개 · 대답은 명령 말 그대로 (11-20)
CMD_REPLY = {
    'hey foothold': "Yes, I'm listening",
    'foothold stand up': 'Stand up',
    'foothold stand down': 'Stand down',
    'foothold sit down': 'Sit down',
    'foothold get up': 'Get up',          # 11-23: rise sit → get up (앉은 자세에서 일어서기 · RiseSit)
    'foothold stop': 'Stop',
}
CMD_REJECT = ["foothold don't sit down", "foothold don't stand up", "foothold don't stand down", "foothold don't get up",
              "don't", 'not', 'no', 'now', 'and']   # commands_1120.REJECT 에서 rise sit → get up 만 바꿈 (대답 안 함)
OLD_CODE = '/home/minwoo/Desktop/foothold/1차 검토/26.11/26.11.19/4_음성인식_호출어시험/시험코드'   # --selftest 합성 소리만


def now():
    return time.monotonic()


def text_of(r):
    return ' '.join(r.get('text', '').lower().split())


class Listener:
    """소리 조각을 받아, 한 마디가 끝날 때마다 결과 하나를 돌려준다."""

    def __init__(self, model, replies=None, extra=()):
        from vosk import KaldiRecognizer
        self.replies = replies or {'hey foothold': REPLY}
        self.rec = KaldiRecognizer(model, RATE, json.dumps(list(self.replies) + list(extra) + ["[unk]"]))
        self.rec.SetWords(True)
        self.free = KaldiRecognizer(model, RATE)      # 화면 표시용 자유 받아쓰기
        self.pending = []
        self.peak = 0.0

    def feed(self, b):
        a = array.array('h', b)
        if a:
            self.peak = max(self.peak, math.sqrt(sum(x * x for x in a) / len(a)))
        if self.free.AcceptWaveform(b):
            t = text_of(json.loads(self.free.Result()))
            if t:
                self.pending.append(t)
        if not self.rec.AcceptWaveform(b):
            return None
        r = json.loads(self.rec.Result())
        t = text_of(json.loads(self.free.FinalResult()))
        heard = ' '.join(self.pending + ([t] if t else []))
        self.pending = []
        self.free.Reset()
        got = text_of(r)
        conf = [round(w.get('conf', float('nan')), 3) for w in r.get('result', [])]
        level = round(20 * math.log10(max(self.peak, 1.0) / 32768), 1)   # 이 마디에서 가장 큰 0.125 초 구간 (dBFS)
        self.peak = 0.0
        if got in self.replies:
            return dict(kind='trigger', phrase=got, reply=self.replies[got], conf=conf, heard=heard, level=level)
        if not got and not heard:
            return dict(kind='empty')
        return dict(kind='other', grammar=got, heard=heard, level=level)

    def reset(self):
        self.rec.Reset(); self.free.Reset(); self.pending = []; self.peak = 0.0


def line(res, c):
    tm = time.strftime('%H:%M:%S')
    score = f'(대답 {c["trigger"]} · 대답 안 함 {c["other_final"]})'
    if res['kind'] == 'trigger':
        return (f'[{tm}] ● 대답함 「{res["reply"]}」 — 「{res["phrase"]}」 로 들음 · 확신도 {res["conf"]} · 소리 {res["level"]} dB'
                f' · 참고 받아쓰기 「{res["heard"]}」  {score}')
    g = f' · 판정 「{res["grammar"]}」' if res.get('grammar') else ''
    return f'[{tm}] ○ 대답 안 함{g} — 소리 {res["level"]} dB · 참고 받아쓰기 「{res["heard"] or "(글자 없음)"}」  {score}'


def selftest(model_dir, commands=False):
    sys.path.insert(0, OLD_CODE)
    from vosk import Model, SetLogLevel
    SetLogLevel(-1)
    import synth_feed_test as S
    phrases = (['hey foothold', 'foothold stand up', 'foothold sit down', "foothold don't sit down", 'foothold stop', 'hey photo',
                'foothold get up', "foothold don't get up"]   # 11-23: get up 작동 사례 (합성 한 조건 · 사람 성능 아님)
               if commands else ['hey foothold', 'hey football', 'foothold', 'hey photo', 'hey foothold'])
    data = b''
    for p in phrases:
        data += S.pcm([0] * 8000 + S.resample(S.synth(p, 'en-us', 150, 50), S.SR) + [0] * 16000)
    L = Listener(Model(model_dir), CMD_REPLY, CMD_REJECT) if commands else Listener(Model(model_dir))
    c = dict(trigger=0, other_final=0)
    lines = []
    for i in range(0, len(data), CHUNK):
        res = L.feed(data[i:i + CHUNK])
        if res and res['kind'] != 'empty':
            c['trigger' if res['kind'] == 'trigger' else 'other_final'] += 1
            lines.append(line(res, c)); print(lines[-1])
            if res['kind'] == 'trigger':
                L.reset()
    print(f'\n[작동 확인 · 합성 목소리] 넣은 말 {len(phrases)} 개 · 나온 줄 {len(lines)} 개 · 대답 {c["trigger"]} · 대답 안 함 {c["other_final"]}')
    print('  (합성 목소리 작동 확인일 뿐 · 사람 목소리 성능 아님)')
    return 0 if len(lines) == len(phrases) else 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--model', required=True)
    ap.add_argument('--log')
    ap.add_argument('--label', default='시험')
    ap.add_argument('--device', default=None, help='pactl 입력 장치 이름 (기본: 시스템 기본 입력)')
    ap.add_argument('--log-text', action='store_true', help='받아쓴 글자도 기록에 남김 (시험 1 · 2)')
    ap.add_argument('--commands', action='store_true', help='명령 6 개를 모두 듣고 명령 말 그대로 대답 (거부 보기로 판정된 문장은 대답 안 함 · 부정문 오분류 가능)')
    ap.add_argument('--selftest', action='store_true')
    a = ap.parse_args()
    if a.selftest:
        sys.exit(selftest(a.model, a.commands))
    if not a.log:
        sys.exit('--log 가 필요합니다')

    from vosk import Model, SetLogLevel
    SetLogLevel(-1)
    dev = a.device or subprocess.run(['pactl', 'get-default-source'], capture_output=True, text=True).stdout.strip()
    if dev.endswith('.monitor'):
        sys.exit(f'입력 장치가 스피커 되받기(monitor) 입니다: {dev}')
    print('[준비] 모델 불러오는 중…', flush=True)
    L = Listener(Model(a.model), CMD_REPLY, CMD_REJECT) if a.commands else Listener(Model(a.model))

    cmd = ['parecord', '--raw', f'--rate={RATE}', '--channels=1', '--format=s16le', f'--device={dev}',
           '--latency-msec=50']
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    q = queue.Queue()
    stats = dict(bytes=0)

    def reader():
        while True:
            b = proc.stdout.read(CHUNK)
            if not b:
                q.put(None); return
            stats['bytes'] += len(b)
            q.put((now(), b))
    threading.Thread(target=reader, daemon=True).start()

    log = open(a.log, 'a', encoding='utf-8')
    t0 = now()

    def write(ev, **kw):
        kw.update(ev=ev, t=round(now() - t0, 3), wall=time.strftime('%H:%M:%S'), label=a.label)
        log.write(json.dumps(kw, ensure_ascii=False) + '\n'); log.flush()

    c = dict(trigger=0, other_final=0, empty_final=0, reply_fail=0, discarded_chunks=0)
    lat_end = []
    write('start', device=dev, rate=RATE, rearm_s=REARM_S, replies=L.replies, commands=a.commands, log_text=a.log_text, program='hey_foothold_1123')
    print(f'[시작] {time.strftime("%H:%M:%S")} · 입력 장치: {dev}\n'
          f'한 번 말할 때마다 한 줄이 나옵니다 (● 대답함 · ○ 대답 안 함). 말 끝나고 잠깐 쉬면 결과가 나옵니다. 끝내려면 Ctrl+C', flush=True)

    ignore_until = 0.0
    stop = dict(v=False)
    signal.signal(signal.SIGINT, lambda *_: stop.__setitem__('v', True))
    while not stop['v']:
        try:
            item = q.get(timeout=0.5)
        except queue.Empty:
            continue
        if item is None:
            write('error', msg='마이크 입력 끊김'); print('[오류] 마이크 입력 끊김'); break
        ts, b = item
        if ts < ignore_until:
            c['discarded_chunks'] += 1
            continue
        res = L.feed(b)
        if res is None:
            continue
        if res['kind'] == 'empty':
            c['empty_final'] += 1; continue
        txt = dict(heard=res['heard']) if a.log_text else {}
        if res['kind'] == 'other':
            c['other_final'] += 1
            print(line(res, c), flush=True)
            write('other', n=c['other_final'], level=res['level'], **(dict(txt, grammar=res['grammar']) if a.log_text else {}))
            continue
        t_final = now()
        c['trigger'] += 1
        print(line(res, c), flush=True)
        rc = subprocess.run(['spd-say', '-w', '-o', 'espeak-ng', '-l', 'en', res['reply']],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode
        t_done = now()
        if rc != 0:
            c['reply_fail'] += 1; print('   [대답 소리 실패]', flush=True)
        lat_end.append(t_done - t_final)
        write('trigger', n=c['trigger'], phrase=res['phrase'], level=res['level'], conf=res['conf'], final_to_reply_end_s=round(t_done - t_final, 3), reply_rc=rc, **txt)
        ignore_until = now() + REARM_S
        L.reset()

    proc.terminate()
    dur = now() - t0
    s = dict(c, duration_s=round(dur, 1), samples_expected=int(dur * RATE), samples_received=int(stats['bytes'] / 2),
             final_to_reply_end_s_median=round(sorted(lat_end)[len(lat_end) // 2], 3) if lat_end else None)
    write('end', **s)
    print(f'\n[종료] {time.strftime("%H:%M:%S")} · 대답 {c["trigger"]} · 대답 안 함 {c["other_final"]} · 대답 소리 실패 {c["reply_fail"]}')


if __name__ == '__main__':
    main()
