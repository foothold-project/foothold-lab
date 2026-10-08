# -*- coding: utf-8 -*-
"""배포본 mp4 를 화질 그대로 faststart 로 다시 싼다 (#511 M1).

> 분류: 운영
> 작성: 오흥재 · 2026-10-09
> 근거: 10/8~10/9 실측 (moov 가 끝인 mp4 98개 · 바깥 경로 재생 시작 8.6~12.6 → 7.1~8.1 초) · ASTRA 2차 검증 `inbox/jay/20261008-546-design/VERIFY-astra-2.md`
> 요지: 배포본(복사본)에서만 moov 상자를 파일 앞으로 옮기고 그 안의 청크 위치값(stco · co64)만 고친다. 원본 `web/` 은 안 건드린다. 옮긴 전후의 패킷 내용(payload sha256) · 시간 · 스트림 정보가 같을 때만 바꾼다
> 상태: 확정
> 판: v1.0

## 왜

mp4 의 목차(moov)가 파일 끝에 있으면 브라우저는 재생 전에 끝을 한 번 더 받으러 간다.
느린 경로에서는 그 왕복이 초 단위다. moov 를 앞으로 옮기는 것은 «싸개» 만 바꾸는 일이라
영상 데이터는 그대로다. 그래도 «그대로» 를 말로 하지 않고 재서 확인한다.

## 어떻게

1. 배포본의 `.mp4` 를 상자 머리만 읽어 넷으로 가른다:
   `front`(moov 가 mdat 앞) · `tail`(뒤) · `fragmented`(moof 있음) · `invalid`(상자가 파일 밖으로
   넘침 · ftyp 가 처음이 아님 · moov 가 0개나 2개 · mdat 없음 · 끝에 남는 바이트).
2. `tail` 만 moov 상자를 ftyp 바로 뒤로 옮기고, moov 안의 stco · co64 청크 위치에 moov 크기를
   더한다(qt-faststart 와 같은 방식). 다른 바이트는 하나도 바꾸지 않는다. moov 가 맨 끝 상자가
   아니면(지원하지 않는 배치) 바꾸지 않고 실패한다.
   ★ 처음에는 ffmpeg `-c copy -movflags +faststart` 로 했다. 10/9 실측에서 HEVC 휴대폰 영상 1개의
   hvcC(extradata)를 ffmpeg 가 다시 쓰고 음성 길이가 0.0003 초 바뀌어 지문 대조에 걸렸다.
   그래서 아무것도 다시 쓰지 않는 상자 옮기기로 바꿨다.
3. 다시 싼 것이 `front` 이고, **동일성 지문**이 원본과 같아야 바꾼다. 지문은 ffprobe 의
   스트림 정보(코덱 · 크기 · 화소 형식 · 색 · 시간 단위 · extradata 해시 · 처분 · side data) +
   **패킷마다 payload sha256 · pts · dts · duration · size · flags** 이다. 파일 위치(pos)는 뺀다.
4. 결과는 캐시에 둔다. 열쇠 = 입력 sha256 + 규칙 판. 캐시를 쓸 때도
   기록해 둔 출력 sha256 과 대조한다. 임시 파일에 쓰고 검증한 뒤 원자 교체한다.

## 관문

- 단계 뒤 배포본에 `tail` 0개 · `invalid` 0개 · `fragmented` 0개(허용 목록 없음).
- 배포본 mp4 가 0개면 실패(엉뚱한 폴더). ffmpeg · ffprobe 가 없으면 실패.
- 동일성 지문이 다르면 그 파일을 바꾸지 않고 실패.

★ 이 관문이 «못 잡는 것»
- `.webm` · `.mov` · `.m4v` (mp4 만 본다).
- 영상 «내용» 이 맞는지. 원본이 처음부터 틀린 영상이면 그대로 간다.
- 서버가 느린 것 · 브라우저가 실제로 빨리 트는지 (M3 몫).
- 이미 공개된 같은 주소의 옛 바이트가 방문자 캐시에 남는 것. 내용(패킷)은 같고 싸개만
  다르므로 화면은 같고 시작만 느리다.
- 영상이 어디서 나가는지(10/9 부터 다시 Vercel). 미디어 서버를 옮기면(M2) 그쪽의 실제 바이트 ·
  Range 응답은 따로 확인한다.

## 판 이력

| 판 | 날짜 | 무엇 | 왜 |
|---|---|---|---|
| v1.0 | 2026-10-09 | 처음 씀 | 팀장 10/9 「M1 진행」 · ASTRA 2차 검증 지적(크기 · pts 만 보는 대조는 같은 크기의 다른 payload 를 놓친다) 반영 |
| v1.1 | 2026-10-09 | ffmpeg 재포장 → 상자 옮기기 | HEVC 1개에서 ffmpeg 가 extradata 를 다시 썼다 (지문 대조가 잡음) |
"""
import glob
import hashlib
import io
import json
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import uuid

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(os.path.dirname(os.path.dirname(HERE)), '_out', 'cache', 'faststart')
RULE = 'relocate-moov-v1'
CONTAINERS = (b'moov', b'trak', b'mdia', b'minf', b'stbl')
TIMEOUT_S = 600

_STREAM_KEYS = ('index,codec_type,codec_name,codec_tag_string,profile,level,width,height,'
                'coded_width,coded_height,pix_fmt,sample_fmt,sample_rate,channels,channel_layout,'
                'bits_per_raw_sample,field_order,color_range,color_space,color_transfer,'
                'color_primaries,chroma_location,sample_aspect_ratio,display_aspect_ratio,'
                'time_base,start_pts,duration_ts,nb_frames,r_frame_rate,avg_frame_rate,'
                'extradata_hash')
_PACKET_KEYS = 'stream_index,pts,dts,duration,size,flags,data_hash'


# ── 도구 찾기 ─────────────────────────────────────────────

def _find(name):
    p = shutil.which(name)
    if p:
        return p
    pat = os.path.join(os.environ.get('LOCALAPPDATA', ''), 'Microsoft', 'WinGet', 'Packages',
                       'Gyan.FFmpeg*', '*', 'bin', name + '.exe')
    hits = sorted(glob.glob(pat))
    return hits[-1] if hits else None


def tools():
    ff, fp = _find('ffmpeg'), _find('ffprobe')
    if not ff or not fp:
        return None
    ver = subprocess.run([ff, '-version'], capture_output=True, text=True,
                         encoding='utf-8', errors='replace').stdout.split('\n')[0].strip()
    return {'ffmpeg': ff, 'ffprobe': fp, 'version': ver}


# ── 상자 머리로 가르기 ─────────────────────────────────────

def classify(path):
    """('front'|'tail'|'fragmented'|'invalid', 까닭)."""
    try:
        size = os.path.getsize(path)
    except OSError as e:
        return 'invalid', 'stat: %s' % e
    if size < 16:
        return 'invalid', '16 바이트보다 작다'
    types = []
    pos = 0
    with open(path, 'rb') as f:
        while pos < size:
            if size - pos < 8:
                return 'invalid', '끝에 %d 바이트가 남는다' % (size - pos)
            f.seek(pos)
            h = f.read(16)
            n, t = struct.unpack('>I4s', h[:8])
            hdr = 8
            if n == 1:
                if len(h) < 16:
                    return 'invalid', '64비트 크기 머리가 잘렸다 @%d' % pos
                n = struct.unpack('>Q', h[8:16])[0]
                hdr = 16
            elif n == 0:
                n = size - pos
            if n < hdr:
                return 'invalid', '상자 크기 %d < 머리 %d @%d' % (n, hdr, pos)
            if pos + n > size:
                return 'invalid', '상자 %r 가 파일 밖으로 넘친다 @%d' % (t, pos)
            if not all(32 <= c < 127 for c in t):
                return 'invalid', '상자 이름이 글자가 아니다 @%d' % pos
            types.append(t.decode('ascii'))
            pos += n
    if not types or types[0] != 'ftyp':
        return 'invalid', 'ftyp 가 처음이 아니다: %s' % types[:3]
    if types.count('moov') != 1:
        return 'invalid', 'moov 가 %d개' % types.count('moov')
    if 'mdat' not in types:
        return 'invalid', 'mdat 가 없다'
    if 'moof' in types:
        return 'fragmented', ''
    return ('front' if types.index('moov') < types.index('mdat') else 'tail'), ''


# ── 동일성 지문 ─────────────────────────────────────────────

def identity(path, tl):
    """스트림 정보 + 패킷마다 payload sha256 · 시간. 파일 위치는 뺀다."""
    cmd = [tl['ffprobe'], '-v', 'error', '-show_data_hash', 'sha256',
           '-show_entries', 'stream=%s:stream_disposition:stream_side_data:packet=%s'
           % (_STREAM_KEYS, _PACKET_KEYS),
           '-show_streams', '-show_packets', '-of', 'json', path]
    r = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8',
                       errors='replace', timeout=TIMEOUT_S)
    if r.returncode != 0:
        raise RuntimeError('ffprobe 실패 %s: %s' % (os.path.basename(path), r.stderr.strip()[:200]))
    d = json.loads(r.stdout or '{}')
    streams = d.get('streams') or []
    packets = d.get('packets') or []
    for s in streams:
        s.pop('tags', None)          # handler_name 같은 이름표는 다시 싸면 바뀔 수 있다
    for p in packets:
        p.pop('pos', None)           # -show_entries 에 안 적어도 ffprobe 9.0.2 가 붙인다(10/9 실측). 싸개 위치라 뺀다
    if not streams or not packets:
        raise RuntimeError('스트림 %d · 패킷 %d: 지문을 만들 수 없다' % (len(streams), len(packets)))
    if any('data_hash' not in p for p in packets):
        raise RuntimeError('payload 해시가 빠진 패킷이 있다')
    canon = json.dumps({'streams': streams, 'packets': packets}, sort_keys=True,
                       ensure_ascii=True, separators=(',', ':'))
    return hashlib.sha256(canon.encode('ascii')).hexdigest(), len(streams), len(packets)


# ── 다시 싸기 ─────────────────────────────────────────────

def _sha(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def cache_key(in_sha, tl=None):
    return hashlib.sha256(('%s|%s' % (RULE, in_sha)).encode('utf-8')).hexdigest()[:40]


def _boxes(buf, start, end):
    """buf[start:end] 안의 상자들: (이름, 시작, 머리 길이, 전체 길이)."""
    out = []
    pos = start
    while pos < end:
        if end - pos < 8:
            raise RuntimeError('상자 머리가 잘렸다 @%d' % pos)
        n, t = struct.unpack('>I4s', buf[pos:pos + 8])
        hdr = 8
        if n == 1:
            n = struct.unpack('>Q', buf[pos + 8:pos + 16])[0]
            hdr = 16
        elif n == 0:
            n = end - pos
        if n < hdr or pos + n > end:
            raise RuntimeError('상자 %r 크기가 맞지 않다 @%d' % (t, pos))
        out.append((t, pos, hdr, n))
        pos += n
    return out


def _shift_offsets(moov, delta):
    """moov 사본 안의 stco · co64 청크 위치에 delta 를 더한다. 바꾼 칸 수를 돌려준다."""
    count = 0

    def walk(start, end):
        nonlocal count
        for t, pos, hdr, n in _boxes(moov, start, end):
            body = pos + hdr
            if t in CONTAINERS:
                walk(body, pos + n)
            elif t in (b'stco', b'co64'):
                k = struct.unpack('>I', moov[body + 4:body + 8])[0]
                w, fmt, lim = (4, '>I', 0xFFFFFFFF) if t == b'stco' else (8, '>Q', 0xFFFFFFFFFFFFFFFF)
                if body + 8 + k * w > pos + n:
                    raise RuntimeError('%s 칸 수 %d 가 상자보다 크다' % (t, k))
                for i in range(k):
                    at = body + 8 + i * w
                    v = struct.unpack(fmt, moov[at:at + w])[0] + delta
                    if v > lim:
                        raise RuntimeError('stco 위치가 32비트를 넘는다 (co64 로 바꿔야 한다)')
                    moov[at:at + w] = struct.pack(fmt, v)
                    count += 1
    walk(8 if struct.unpack('>I', moov[:4])[0] != 1 else 16, len(moov))
    return count


def relocate(src, dst):
    """ftyp · … · moov(끝) → ftyp · moov(위치 고침) · … . 다른 바이트는 그대로."""
    with open(src, 'rb') as f:
        buf = bytearray(f.read())
    top = _boxes(buf, 0, len(buf))
    names = [t for t, _, _, _ in top]
    if not names or names[0] != b'ftyp' or names.count(b'moov') != 1 or names[-1] != b'moov':
        raise RuntimeError('지원하지 않는 배치 (moov 가 맨 끝이 아니다): %s' % [x.decode('latin1') for x in names])
    _, fpos, _, fn = top[0]
    _, mpos, _, mn = top[-1]
    moov = bytearray(buf[mpos:mpos + mn])
    k = _shift_offsets(moov, mn)
    if k == 0:
        raise RuntimeError('stco · co64 칸이 하나도 없다')
    with open(dst, 'wb') as f:
        f.write(buf[fpos:fpos + fn])
        f.write(moov)
        f.write(buf[fpos + fn:mpos])
    return k


def _verified_from_cache(cache, key):
    out, meta = os.path.join(cache, key + '.mp4'), os.path.join(cache, key + '.json')
    if not (os.path.isfile(out) and os.path.isfile(meta)):
        return None
    try:
        m = json.load(io.open(meta, encoding='utf-8'))
    except (OSError, ValueError):
        return None
    if _sha(out) != m.get('out_sha') or classify(out)[0] != 'front':
        return None                  # 손상된 캐시는 쓰지 않고 다시 만든다
    return out


def remux(src, cache, tl, mutate=None):
    """src(tail) → 캐시의 검증된 front 경로. 지문이 다르면 RuntimeError."""
    os.makedirs(cache, exist_ok=True)
    in_sha = _sha(src)
    key = cache_key(in_sha, tl)
    hit = _verified_from_cache(cache, key)
    if hit:
        return hit, True
    tmp = os.path.join(cache, '%s.%s.part.mp4' % (key, uuid.uuid4().hex[:8]))
    try:
        relocate(src, tmp)
        if mutate:
            mutate(tmp)              # 자기시험 전용: 출력을 일부러 망가뜨린다
        kind, why = classify(tmp)
        if kind != 'front':
            raise RuntimeError('다시 싼 것이 front 가 아니다: %s %s' % (kind, why))
        a, b = identity(src, tl), identity(tmp, tl)
        if a != b:
            raise RuntimeError('동일성 지문이 다르다 (스트림 %d→%d · 패킷 %d→%d)'
                               % (a[1], b[1], a[2], b[2]))
        out = os.path.join(cache, key + '.mp4')
        os.replace(tmp, out)
        with io.open(os.path.join(cache, key + '.json'), 'w', encoding='utf-8') as f:
            json.dump({'rule': RULE, 'ffprobe': tl['version'], 'in_sha': in_sha,
                       'out_sha': _sha(out), 'identity': a[0], 'streams': a[1], 'packets': a[2]},
                      f, ensure_ascii=False, indent=1)
        return out, False
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


# ── 배포본 전체 ─────────────────────────────────────────────

def _mp4s(site):
    for root, dirs, files in os.walk(site):
        if '.git' in dirs:
            dirs.remove('.git')
        for n in files:
            if n.lower().endswith('.mp4'):
                yield os.path.join(root, n)


def run(site, cache=CACHE, tl=None, mutate=None):
    """배포본 mp4 를 가르고 tail 을 다시 싼다. 돌려주는 것: 집계 dict."""
    st = dict(total=0, front=0, tail=0, fragmented=[], invalid=[], converted=0, cache_hit=0,
              failed=[], bytes_before=0, bytes_after=0)
    for p in sorted(_mp4s(site)):
        st['total'] += 1
        kind, why = classify(p)
        rel = os.path.relpath(p, site).replace(os.sep, '/')
        if kind == 'front':
            st['front'] += 1
        elif kind == 'fragmented':
            st['fragmented'].append(rel)
        elif kind == 'invalid':
            st['invalid'].append('%s (%s)' % (rel, why))
        else:
            st['tail'] += 1
            try:
                out, hit = remux(p, cache, tl, mutate)
            except Exception as e:   # noqa: BLE001 · 파일마다 까닭을 남긴다
                st['failed'].append('%s (%s)' % (rel, e))
                continue
            st['bytes_before'] += os.path.getsize(p)
            tmp = p + '.fs-' + uuid.uuid4().hex[:8]
            shutil.copyfile(out, tmp)
            os.replace(tmp, p)
            st['bytes_after'] += os.path.getsize(p)
            st['converted'] += 1
            st['cache_hit'] += int(hit)
    return st


def gate(site):
    """단계 뒤: tail · invalid · fragmented 가 하나라도 있으면 그 목록."""
    bad = []
    n = 0
    for p in _mp4s(site):
        n += 1
        kind, why = classify(p)
        if kind != 'front':
            bad.append('%s:%s %s' % (os.path.relpath(p, site).replace(os.sep, '/'), kind, why))
    return n, bad


# ── 자기시험 ─────────────────────────────────────────────

def _make(tl, path, faststart=False, frag=False, audio=True):
    cmd = [tl['ffmpeg'], '-v', 'error', '-nostdin', '-y',
           '-f', 'lavfi', '-i', 'testsrc=duration=1:size=64x48:rate=10']
    if audio:
        cmd += ['-f', 'lavfi', '-i', 'sine=frequency=440:duration=1']
    cmd += ['-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-g', '5']
    if audio:
        cmd += ['-c:a', 'aac', '-shortest']
    if faststart:
        cmd += ['-movflags', '+faststart']
    if frag:
        cmd += ['-movflags', 'frag_keyframe+empty_moov']
    cmd += [path]
    r = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace')
    if r.returncode != 0:
        raise RuntimeError('표본 생성 실패: %s' % r.stderr[:200])


def _flip_in_mdat(path):
    """mdat 안 마지막 쪽 바이트 하나를 바꾼다. 크기 · 시간은 그대로다."""
    size = os.path.getsize(path)
    pos = 0
    with open(path, 'r+b') as f:
        while pos < size:
            f.seek(pos)
            n, t = struct.unpack('>I4s', f.read(8))
            if n == 0:
                n = size - pos
            if t == b'mdat':
                at = pos + n - 3
                f.seek(at)
                b = f.read(1)
                f.seek(at)
                f.write(bytes([b[0] ^ 0x01]))
                return
            pos += n
    raise RuntimeError('mdat 를 못 찾았다')


def _selftest(tl):
    with tempfile.TemporaryDirectory() as t:
        site, cache = os.path.join(t, 'site'), os.path.join(t, 'cache')
        os.makedirs(os.path.join(site, 'a'))
        tail, front = os.path.join(site, 'a', 'tail.mp4'), os.path.join(site, 'a', 'front.mp4')
        _make(tl, tail)
        _make(tl, front, faststart=True)
        if classify(tail)[0] != 'tail' or classify(front)[0] != 'front':
            return False, '표본 판별이 틀렸다: %s · %s' % (classify(tail), classify(front))
        front_sha, tail_id = _sha(front), identity(tail, tl)
        # 1) 다시 싸기: tail → front, 지문 같음, front 표본은 그대로
        st = run(site, cache, tl)
        if (st['converted'], st['front'], st['failed']) != (1, 1, []):
            return False, '첫 실행 집계가 다르다: %r' % st
        if classify(tail)[0] != 'front' or identity(tail, tl) != tail_id:
            return False, '다시 싼 결과가 front 가 아니거나 지문이 다르다'
        if _sha(front) != front_sha:
            return False, '이미 front 인 파일을 건드렸다'
        if gate(site)[1]:
            return False, '정상 배포본에서 관문이 실패했다'
        # 2) 관문 깨기: 다시 싸지 않은 tail 이 남으면 관문이 잡는다
        _make(tl, os.path.join(site, 'a', 'left.mp4'))
        n, bad = gate(site)
        if not any('left.mp4:tail' in b for b in bad):
            return False, '남은 tail 을 관문이 못 잡았다: %r' % bad
        os.remove(os.path.join(site, 'a', 'left.mp4'))
        # 3) 지문 깨기: 같은 크기 · 같은 시간에서 payload 한 바이트만 바꾸면 실패해야 한다
        src = os.path.join(t, 'src.mp4')
        _make(tl, src)
        try:
            remux(src, os.path.join(t, 'c2'), tl, mutate=_flip_in_mdat)
            return False, 'payload 한 바이트가 바뀌었는데 지문이 같다고 했다'
        except RuntimeError as e:
            if '지문' not in str(e):
                return False, 'payload 변형이 다른 까닭으로 실패했다: %s' % e
        # 4) 지문 깨기: 음성을 뺀 출력은 다르다
        noa = os.path.join(t, 'noa.mp4')
        _make(tl, noa, audio=False)
        if identity(src, tl) == identity(noa, tl):
            return False, '음성 스트림이 없는데 지문이 같다'
        # 5) 구조 깨기: 잘린 파일 · moov 없음 · fragmented
        cut = os.path.join(t, 'cut.mp4')
        with open(src, 'rb') as f:
            data = f.read()
        with open(cut, 'wb') as f:
            f.write(data[:len(data) // 2])
        if classify(cut)[0] != 'invalid':
            return False, '반쯤 잘린 파일을 %s 로 봤다' % classify(cut)[0]
        nomoov = os.path.join(t, 'nomoov.mp4')
        with open(nomoov, 'wb') as f:
            f.write(struct.pack('>I4s', 16, b'ftyp') + b'isom\x00\x00\x02\x00'
                    + struct.pack('>I4s', 12, b'mdat') + b'\x00\x00\x00\x00')
        if classify(nomoov)[0] != 'invalid':
            return False, 'moov 없는 파일을 %s 로 봤다' % classify(nomoov)[0]
        frag = os.path.join(t, 'frag.mp4')
        _make(tl, frag, frag=True)
        if classify(frag)[0] != 'fragmented':
            return False, 'fragmented 를 %s 로 봤다' % classify(frag)[0]
        # 6) 손상된 캐시: 캐시 출력을 망가뜨리면 다시 만든다
        src2 = os.path.join(t, 'src2.mp4')
        _make(tl, src2)
        c3 = os.path.join(t, 'c3')
        out, hit = remux(src2, c3, tl)
        good = _sha(out)
        with open(out, 'r+b') as f:
            f.seek(os.path.getsize(out) - 2)
            f.write(b'\xff\xff')
        out2, hit2 = remux(src2, c3, tl)
        if hit2 or _sha(out2) != good:
            return False, '손상된 캐시를 그대로 썼다 (hit=%s)' % hit2
        if remux(src2, c3, tl)[1] is not True:
            return False, '정상 캐시를 다시 쓰지 않았다'
        # 7) 지원하지 않는 배치: moov 뒤에 상자가 더 있으면 옮기지 않고 실패한다
        odd = os.path.join(t, 'odd.mp4')
        _make(tl, odd)
        with open(odd, 'ab') as f:
            f.write(struct.pack('>I4s', 8, b'free'))
        try:
            remux(odd, os.path.join(t, 'c4'), tl)
            return False, 'moov 뒤에 상자가 있는데 옮겼다'
        except RuntimeError as e:
            if '지원하지 않는 배치' not in str(e):
                return False, '배치 검사가 다른 까닭으로 실패했다: %s' % e
        # 8) 빈 배포본은 main 이 실패로 친다 (main 에서 확인)
    return True, '알려진 답 8갈래 (옮기기 · 관문 깨기 · payload 깨기 · 음성 깨기 · 구조 셋 · 손상 캐시 · 배치 · front 보존)'


def main(site, cache=CACHE):
    tl = tools()
    if not tl:
        print('  [!] ffmpeg · ffprobe 가 없습니다. winget install Gyan.FFmpeg 뒤 다시 빌드하십시오.')
        return False
    ok, why = _selftest(tl)
    if not ok:
        print('  [!] 자기시험 실패: %s' % why)
        return False
    print('  자기시험 통과 (%s) · %s' % (why, tl['version']))
    n_before = sum(1 for _ in _mp4s(site))
    if n_before == 0:
        print('  [!] 배포본에 mp4 가 하나도 없습니다 (%s). 엉뚱한 폴더로 보고 실패로 칩니다.' % site)
        return False
    st = run(site, cache, tl)
    print('  mp4 %d개 · 이미 앞 %d · 끝 %d → 다시 쌈 %d (캐시 %d) · %.1f MB → %.1f MB'
          % (st['total'], st['front'], st['tail'], st['converted'], st['cache_hit'],
             st['bytes_before'] / 1e6, st['bytes_after'] / 1e6))
    for k, label in (('failed', '다시 싸기 실패'), ('invalid', '구조가 깨진 파일'),
                     ('fragmented', 'fragmented (허용 목록 없음)')):
        if st[k]:
            print('  [!] %s %d개: %s' % (label, len(st[k]), ' · '.join(st[k][:3])))
    n, bad = gate(site)
    if bad:
        print('  [!] 관문: front 가 아닌 mp4 %d개: %s' % (len(bad), ' · '.join(bad[:3])))
        return False
    if st['failed'] or st['invalid'] or st['fragmented']:
        return False
    print('  관문 통과: mp4 %d개 전부 moov 가 앞' % n)
    return True


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    tl = tools()
    if not tl:
        print('ffmpeg 없음')
        sys.exit(1)
    ok, why = _selftest(tl)
    print('selftest', ok, why)
    sys.exit(0 if ok else 1)
