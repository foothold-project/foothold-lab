# -*- coding: utf-8 -*-
"""배포본의 큰 PNG 를 WebP 로 바꾼다 (보이는 모습은 그대로 · #511 경량화).

> 분류: 운영
> 작성: 오흥재 · 2026-10-08 03:10
> 근거: 실측 (10/8 PNG 72장 80.5 MB · 샘플 3장 비교 · 투명 40장)
> 요지: 200 KB 넘는 PNG 를 배포본에서만 WebP 로 바꾸고 이름 참조를 고친다. 투명 배경은 무손실, 사진형은 품질 90. 원본 PNG(lab web/)는 그대로 둔다.
> 상태: 확정
> 판: v1.0

## 왜

영상을 NAS 로 넘긴 뒤 배포본 283 MB 중 PNG 가 84 MB 였다. 200 KB 넘는 것이
대부분(덱용 Blender 렌더 · Isaac 화면). 팀장 10/8 「그림은 똑같이 보이게 하고
용량은 줄일 수 없나」.

## 어떻게

- 투명 배경(RGBA) 은 **무손실** WebP. 보이는 픽셀(알파 > 0)의 RGB · 알파가 원본과
  같다. 완전 투명 픽셀의 숨은 색은 인코더가 바꾸지만 화면에 안 나온다.
- 사진형(RGB) 은 품질 90. 샘플에서 원본의 6~12 % · 100 % 확대 비교로 구분 안 됨.
  평균 차이가 2/255 를 넘으면 무손실로 바꾼다(10/8 최대 2.94 는 렌더 화질 비교 그림).
- 바꾼 뒤 다시 열어 대조한다: 무손실은 보이는 픽셀 완전 일치. 어긋나면 PNG 로 둔다.
- 참조는 파일 이름(`x.png` → `x.webp`)으로 고친다. 이름이 글자로 어디에도 안
  나오는 PNG 와, 같은 이름의 다른 PNG 가 200 KB 이하라 함께 못 바꾸는 것은 안 건드린다.
- 같은 PNG 를 다시 만나면 `_out/cache/webp/` 의 결과를 쓴다(sha256 열쇠).

## 관문

1. 배포본의 텍스트에 바꾼 PNG 이름이 남아 있지 않다.
2. 바꾼 WebP 가 전부 있다.

★ 이 관문이 «못 잡는 것»
- 스크립트가 경로를 조각으로 이어 붙이는 PNG(`'go2-' + n + '.png'`). 10/8 배포본에는
  0곳이었다(정규식 실측). 새로 생기면 이 관문은 모르고 그 그림이 깨진다.
- base64 로 HTML 안에 박힌 PNG. 손대지 않는다.
- 품질 90 의 «눈으로 같음» 은 평균 차이로만 잰다. 국소 결함은 사람이 본다.

## 판 이력

| 판 | 날짜 | 무엇 | 왜 |
|---|---|---|---|
| v1.0 | 2026-10-08 | 처음 씀 | 팀장 10/8 경량화 ①(PNG → WebP) 승인 |
"""
import hashlib
import io
import os
import shutil
import sys

MIN_BYTES = 200_000
TEXT = ('.html', '.js', '.css', '.json', '.svg', '.webmanifest', '.xml', '.txt')
HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(os.path.dirname(os.path.dirname(HERE)), '_out', 'cache', 'webp')


def _sha(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def _walk(site):
    for r, d, fs in os.walk(site):
        if '.git' in d:
            d.remove('.git')
        for f in fs:
            yield os.path.join(r, f)


LOSSY_MAX = 2.0   # 사진형 품질 90 의 평균 차이 상한(0~255). 넘으면 무손실로. 10/8 실측 36장 중앙 1.14 · 최대 2.94


def _encode(png, out):
    """돌려주는 것: (방식, 통과?, 사유).

    투명 배경 → 무손실. 사진형 → 품질 90, 평균 차이가 LOSSY_MAX 를 넘으면 무손실.
    (10/8 실측 최대 2.94 는 렌더 화질 «비교» 그림이었다. 비교 대상을 흐리면 안 된다.)
    """
    from PIL import Image
    import numpy as np
    im = Image.open(png)
    im.load()
    alpha = im.mode in ('RGBA', 'LA', 'PA') or 'transparency' in im.info
    src = im.convert('RGBA' if alpha else 'RGB')
    kind = '무손실'
    if not alpha:
        src.save(out, 'WEBP', quality=90, method=6)
        back = Image.open(out).convert('RGB')
        d = float(abs(np.asarray(src, dtype=np.int16) - np.asarray(back, dtype=np.int16)).mean())
        if d <= LOSSY_MAX:
            return '품질90', True, ''
    src.save(out, 'WEBP', lossless=True, method=6)
    back = Image.open(out)
    back.load()
    if back.size != src.size:
        return kind, False, '크기가 달라짐'
    a = np.asarray(src).astype(np.int16)
    b = np.asarray(back.convert(src.mode)).astype(np.int16)
    if alpha:
        if (a[..., 3] != b[..., 3]).any():
            return kind, False, '알파가 달라짐'
        vis = a[..., 3] > 0
        if (a[..., :3][vis] != b[..., :3][vis]).any():
            return kind, False, '보이는 픽셀 색이 달라짐'
    elif (a != b).any():
        return kind, False, '무손실인데 픽셀이 달라짐'
    return kind, True, ''


def slim(site, cache=CACHE):
    os.makedirs(cache, exist_ok=True)
    files = list(_walk(site))
    pngs = [p for p in files if p.lower().endswith('.png')]
    texts = {p: io.open(p, encoding='utf-8', errors='ignore').read()
             for p in files if p.lower().endswith(TEXT)}
    by_name = {}
    for p in pngs:
        by_name.setdefault(os.path.basename(p), []).append(p)
    st = dict(seen=0, converted=0, skipped_small=0, skipped_noref=0, skipped_bigger=0,
              failed=[], before=0, after=0)
    done_names = []
    for name, group in sorted(by_name.items()):
        if not all(os.path.getsize(p) > MIN_BYTES for p in group):
            st['skipped_small'] += len(group)
            continue
        st['seen'] += len(group)
        if not any(name in t for t in texts.values()):
            st['skipped_noref'] += len(group)
            continue
        made = []
        ok_group = True
        for p in group:
            h = _sha(p)
            hit = os.path.join(cache, h + '.webp')
            out = p[:-4] + '.webp'
            if not os.path.isfile(hit):
                tmp = hit + '.part'
                kind, ok, why = _encode(p, tmp)
                if not ok:
                    os.remove(tmp)
                    st['failed'].append('%s (%s)' % (os.path.relpath(p, site), why))
                    ok_group = False
                    break
                os.replace(tmp, hit)
            if os.path.getsize(hit) > 0.9 * os.path.getsize(p):
                st['skipped_bigger'] += 1
                ok_group = False
                break
            made.append((p, out, hit))
        if not ok_group:
            continue
        for p, out, hit in made:
            st['before'] += os.path.getsize(p)
            shutil.copyfile(hit, out)
            st['after'] += os.path.getsize(out)
            os.remove(p)
            st['converted'] += 1
        done_names.append(name)
    # 참조 고치기
    for p, t in texts.items():
        n = t
        for name in done_names:
            if name in n:
                n = n.replace(name, name[:-4] + '.webp')
        if n != t:
            io.open(p, 'w', encoding='utf-8', newline='').write(n)
    left, missing = gate(site, done_names)
    return st, left, missing


def gate(site, done_names):
    """바꾼 PNG 이름이 텍스트에 남았나 · 바꾼 WebP 가 다 있나."""
    files = list(_walk(site))
    webps = {os.path.basename(q) for q in files if q.lower().endswith('.webp')}
    left = [(os.path.relpath(p, site), name) for p in files if p.lower().endswith(TEXT)
            for name in done_names
            if name in io.open(p, encoding='utf-8', errors='ignore').read()]
    missing = [name for name in done_names if name[:-4] + '.webp' not in webps]
    return left, missing


def _meandiff(img, webp_path):
    import numpy as np
    from PIL import Image
    a = np.asarray(img.convert('RGB'), dtype=np.int16)
    b = np.asarray(Image.open(webp_path).convert('RGB'), dtype=np.int16)
    return float(abs(a - b).mean())


def _selftest():
    """알려진 답으로 먼저 돈다. 관문도 일부러 깨뜨려 본다."""
    global LOSSY_MAX
    import tempfile
    from PIL import Image, ImageFilter, ImageDraw
    with tempfile.TemporaryDirectory() as t:
        site, cache = os.path.join(t, 's'), os.path.join(t, 'c')
        a = os.path.join(site, 'a')
        os.makedirs(a)
        g = Image.effect_noise((1400, 1000), 60).filter(ImageFilter.GaussianBlur(4))   # L · 매끈
        photo = Image.merge('RGB', (g, g.rotate(180), g.transpose(Image.FLIP_LEFT_RIGHT)))
        photo.save(os.path.join(a, 'photo.png'))
        rough = Image.effect_noise((900, 700), 90).convert('RGB')                          # 거친 잡음
        rough.save(os.path.join(a, 'rough.png'))
        mask = Image.new('L', photo.size, 0)
        ImageDraw.Draw(mask).ellipse((200, 150, 1200, 850), fill=255)
        robot = photo.copy().convert('RGBA')
        robot.putalpha(mask.filter(ImageFilter.GaussianBlur(3)))
        robot.save(os.path.join(a, 'robot.png'))
        Image.new('RGB', (10, 10)).save(os.path.join(a, 'tiny.png'))
        photo.save(os.path.join(a, 'orphan.png'))
        io.open(os.path.join(site, 'p.html'), 'w', encoding='utf-8').write(
            '<img src="a/robot.png?v=1"><img src="/a/photo.png"><img src="a/tiny.png"><img src="a/rough.png">')
        sizes = {f: os.path.getsize(os.path.join(a, f)) for f in ('photo.png', 'robot.png', 'orphan.png')}
        if min(sizes.values()) <= MIN_BYTES:
            return False, '시험 그림이 너무 작다 %r' % sizes
        st, left, missing = slim(site, cache)
        h = io.open(os.path.join(site, 'p.html'), encoding='utf-8').read()
        exp = [('photo 바뀜', 'a/photo.webp' in h and not os.path.isfile(os.path.join(a, 'photo.png'))),
               ('robot 바뀜(무손실)', 'a/robot.webp?v=1' in h and not os.path.isfile(os.path.join(a, 'robot.png'))),
               ('tiny 그대로', 'a/tiny.png' in h and os.path.isfile(os.path.join(a, 'tiny.png'))),
               ('참조 없는 orphan 그대로', os.path.isfile(os.path.join(a, 'orphan.png'))),
               ('거친 잡음도 계약 안(평균 차이 ≤ 상한)', _meandiff(rough, os.path.join(a, 'rough.webp')) <= LOSSY_MAX),
               ('관문 통과', not left and not missing)]
        bad = [k for k, ok in exp if not ok]
        if bad:
            return False, '기대와 다름: %s · %r' % (' · '.join(bad), st)
        # 무손실 분기를 강제로 태운다: 상한 0 이면 사진형도 픽셀 그대로여야 한다
        keep, LOSSY_MAX = LOSSY_MAX, 0.0
        try:
            rough.save(os.path.join(t, 'r2.png'))
            kind, ok, why = _encode(os.path.join(t, 'r2.png'), os.path.join(t, 'r2.webp'))
        finally:
            LOSSY_MAX = keep
        if not (kind == '무손실' and ok and _meandiff(rough, os.path.join(t, 'r2.webp')) == 0):
            return False, '무손실 분기가 픽셀을 바꿨다 (%s %s %s)' % (kind, ok, why)
        # 관문을 일부러 깨뜨린다: 바꾼 이름이 다시 나타나면 잡아야 한다
        io.open(os.path.join(site, 'q.js'), 'w', encoding='utf-8').write('var s="a/photo.png";')
        left2, _ = gate(site, ['photo.png', 'robot.png'])
        if not left2:
            return False, '남은 참조를 관문이 못 잡았다'
        os.remove(os.path.join(a, 'robot.webp'))
        _, missing2 = gate(site, ['photo.png', 'robot.png'])
        if missing2 != ['robot.png']:
            return False, '빠진 WebP 를 관문이 못 잡았다'
    return True, '알려진 답 6칸 · 무손실 분기 1칸 · 깨뜨린 관문 2칸'


def main(site):
    ok, why = _selftest()
    if not ok:
        print('  [!] 자기시험 실패: %s' % why)
        return False
    print('  자기시험 통과 (%s)' % why)
    # ★ 빈 대상 관문(emptycheck [3.44]): 검사할 페이지가 0장이면 «통과» 가 아니라 실패다.
    #   큰 PNG 가 0장인 것은 정상일 수 있지만, 참조를 볼 텍스트가 0장이면 엉뚱한 폴더다.
    if not any(p.lower().endswith('.html') for p in _walk(site)):
        print('  [!] 배포본에 HTML 이 하나도 없습니다 (%s). 검사할 것이 없어 실패로 칩니다.' % site)
        return False
    st, left, missing = slim(site)
    print('  200 KB 넘는 PNG %d장 · 바꿈 %d장 %.1f MB → %.1f MB · 참조 없음 %d · 작아서 그대로 %d · 줄지 않아 그대로 %d'
          % (st['seen'], st['converted'], st['before'] / 1e6, st['after'] / 1e6,
             st['skipped_noref'], st['skipped_small'], st['skipped_bigger']))
    if st['failed']:
        print('  대조 실패로 PNG 유지 %d장: %s' % (len(st['failed']), ' · '.join(st['failed'][:3])))
    if left:
        print('  [!] 바꾼 PNG 이름이 텍스트에 남았습니다: %s' % ' · '.join('%s:%s' % x for x in left[:3]))
        return False
    if missing:
        print('  [!] WebP 가 없습니다: %s' % ' · '.join(missing[:3]))
        return False
    return True


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    print(_selftest())
