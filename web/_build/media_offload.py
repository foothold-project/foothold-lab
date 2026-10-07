# -*- coding: utf-8 -*-
"""영상은 NAS 에서, 페이지는 Vercel 에서 (#511 3단계).

> 분류: 운영
> 작성: 오흥재 · 2026-10-08 00:18
> 근거: 실측 (10/7 Funnel 경로 속도 · Vercel 배포 저장소 10 GB)
> 요지: 배포본에서 영상 파일을 빼고 NAS 에 있는지 sha256 으로 확인한다. 페이지의 영상 주소는 그대로 두고 vercel.json 의 돌림 규칙 한 줄이 NAS 로 보낸다.
> 상태: 확정
> 판: v1.1

## 왜

Vercel 은 배포마다 사이트 한 벌을 통째로 보관한다. 10/7 한 벌 892 MB 중 영상이
609 MB(68 %) 였고 Hobby 배포 저장소 10 GB 가 찼다. 영상을 빼면 한 벌이 약 280 MB.

## 어떻게

- 페이지 HTML 은 안 고친다. `/assets/.../x.mp4` 요청이 오면 Vercel 이
  `vercel.json` 돌림 규칙으로 `MEDIA_BASE` 의 같은 경로로 보낸다(307).
  덱의 상대 경로 · 갤러리 스크립트 주소도 브라우저가 절대 경로로 풀어 같은 규칙을 탄다.
- 빌드는 복사가 끝난 배포본에서 영상을 찾아, NAS 에 같은 sha256 이 있으면 지우고
  없으면 NAS 로 복사해 대조한 뒤 지운다. NAS 에 못 닿으면 배포를 막는다.
- 영상 서버: NAS 의 Caddy 컨테이너(127.0.0.1:8090, 폴더 읽기 전용) 를 Tailscale
  Funnel 이 `https://ai-nas01.tail025053.ts.net` 으로 연다. 목록은 안 보인다.
- 뒤쪽을 바꿀 때(도메인 · R2 등)는 `MEDIA_BASE` 와 vercel.json 한 줄만 바꾼다.
  두 값이 다르면 이 관문이 막는다.

## 관문

1. 배포본에 영상 파일 0개.
2. 지운 영상마다 NAS 에 같은 sha256 이 있다.
3. vercel.json 에 영상 돌림 규칙이 있고 목적지가 `MEDIA_BASE` 다.
재현 모드(`write=False`)는 NAS 에 쓰지 않고 «없는 것» 만 센다.

★ 이 관문이 «못 잡는 것»
- 배포본에 «없는» 영상. foothold-site 에만 있던 갤러리 클립(10/7 192개)은 재현
  모드 산출 폴더에 안 들어와 여기서 안 보인다. 그 192개는 1단계 복사 때
  sha256 으로 대조했고 NAS `MANIFEST.sha256` 에 있다.
- 영상 서버가 지금 «응답하는지». NAS · Caddy · Funnel 이 꺼져 있어도 이 관문은
  통과한다(파일이 NAS 폴더에 있는지만 본다). 응답은 배포 뒤 실제 주소에서 잰다.
- 페이지가 가리키는 영상 주소가 NAS 에 «있는지». 원래 죽은 링크였던 영상은
  여기서도 죽은 채로 넘어간다.

## 판 이력

| 판 | 날짜 | 무엇 | 왜 |
|---|---|---|---|
| v1.0 | 2026-10-08 | 처음 씀 | 팀장 10/7 「원본은 foothold 공유 그대로」 · Funnel 실측 통과 |
| v1.1 | 2026-10-08 | PDF 도 넘긴다 (7개 19.6 MB) · vercel.json 규칙에 pdf | 팀장 10/8 경량화 ② 승인 |
"""
import hashlib
import io
import json
import os
import shutil
import sys
import tempfile

MEDIA_BASE = 'https://ai-nas01.tail025053.ts.net'
# 순서대로 찾는다. UNC 는 `net use` 로 자격이 이 로그인 세션에 들어 있어야 열린다.
NAS_ROOTS = (r'\\100.80.160.84\foothold\media\site', r'N:\media\site')
VID = ('.mp4', '.webm', '.mov', '.m4v', '.pdf')   # 10/8 경량화 ②: 산출물 PDF 도 NAS 로
MANIFEST = 'MANIFEST.sha256'
HOW_TO_MOUNT = ('NAS 를 붙이십시오 (별도 PowerShell 창):\n'
                '      net use N: \\\\100.80.160.84\\foothold /user:VFXPEDIA * /persistent:no')


def _sha(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def nas_root(roots=NAS_ROOTS):
    for r in roots:
        try:
            if os.path.isdir(r):
                return r
        except OSError:
            pass
    return None


def redirect_ok(site, base=MEDIA_BASE):
    """vercel.json 에 영상 돌림 규칙이 있고 목적지가 base 인가."""
    p = os.path.join(site, 'vercel.json')
    try:
        cfg = json.load(io.open(p, encoding='utf-8'))
    except (OSError, ValueError):
        return False
    for r in cfg.get('redirects') or []:
        if '.mp4' in r.get('source', '') or 'mp4' in r.get('source', ''):
            if str(r.get('destination', '')).startswith(base + '/'):
                return True
    return False


def offload(site, nas, write=True):
    """배포본(site) 의 영상을 NAS 로 넘기고 배포본에서 지운다.

    돌려주는 것: dict(found, already, copied, missing, mismatch, removed)
    write=False 면 NAS 에 쓰지도 배포본에서 지우지도 않는다(검사만).
    """
    st = dict(found=0, already=0, copied=0, missing=[], mismatch=[], removed=0)
    vids = []
    for root, dirs, files in os.walk(site):
        if '.git' in dirs:
            dirs.remove('.git')
        for n in files:
            if n.lower().endswith(VID):
                vids.append(os.path.join(root, n))
    st['found'] = len(vids)
    lines = {}
    mpath = os.path.join(nas, MANIFEST)
    if os.path.isfile(mpath):
        for ln in io.open(mpath, encoding='utf-8'):
            h, _, rel = ln.rstrip('\n').partition('  ')
            if rel:
                lines[rel] = h
    for src in vids:
        rel = os.path.relpath(src, site).replace(os.sep, '/')
        dst = os.path.join(nas, rel.replace('/', os.sep))
        want = _sha(src)
        if os.path.isfile(dst) and os.path.getsize(dst) == os.path.getsize(src) and _sha(dst) == want:
            st['already'] += 1
        elif not write:
            st['missing'].append(rel)
            continue
        else:
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            tmp = dst + '.part'
            shutil.copyfile(src, tmp)
            if _sha(tmp) != want:
                os.remove(tmp)
                st['mismatch'].append(rel)
                continue
            os.replace(tmp, dst)
            st['copied'] += 1
        lines[rel] = want
        if write:
            os.remove(src)
            st['removed'] += 1
    if write and (st['copied'] or not os.path.isfile(mpath)):
        with io.open(mpath, 'w', encoding='utf-8', newline='\n') as f:
            for rel in sorted(lines):
                f.write('%s  %s\n' % (lines[rel], rel))
    return st


def _selftest():
    """알려진 답으로 먼저 돈다. 관문이 조용히 통과하는 것을 막는다."""
    with tempfile.TemporaryDirectory() as t:
        site, nas = os.path.join(t, 'site'), os.path.join(t, 'nas')
        os.makedirs(os.path.join(site, 'a', 'b'))
        os.makedirs(nas)
        v = os.path.join(site, 'a', 'b', 'x.mp4')
        io.open(v, 'wb').write(b'clip-1')
        io.open(os.path.join(site, 'a', 'p.html'), 'w').write('<video src="b/x.mp4">')
        # 1) 검사만: NAS 에 없으면 missing 으로 센다 · 아무것도 안 지운다
        s = offload(site, nas, write=False)
        if s['missing'] != ['a/b/x.mp4'] or not os.path.isfile(v):
            return False, '검사 모드가 없는 영상을 못 셌거나 지웠다: %r' % s
        # 2) 쓰기: 복사 · 대조 · 배포본에서 지움 · 목록 기록
        s = offload(site, nas, write=True)
        if (s['copied'], s['removed']) != (1, 1) or os.path.isfile(v) \
                or not os.path.isfile(os.path.join(nas, 'a', 'b', 'x.mp4')):
            return False, '복사·삭제가 기대와 다르다: %r' % s
        if 'a/b/x.mp4' not in io.open(os.path.join(nas, MANIFEST), encoding='utf-8').read():
            return False, '목록에 안 적혔다'
        # 3) 같은 영상이 다시 오면 복사하지 않고 지우기만
        io.open(v, 'wb').write(b'clip-1')
        s = offload(site, nas, write=True)
        if (s['already'], s['copied'], s['removed']) != (1, 0, 1):
            return False, '이미 있는 영상을 다시 복사했다: %r' % s
        # 4) 내용이 바뀐 영상은 다시 복사
        io.open(v, 'wb').write(b'clip-2')
        s = offload(site, nas, write=True)
        if s['copied'] != 1 or io.open(os.path.join(nas, 'a', 'b', 'x.mp4'), 'rb').read() != b'clip-2':
            return False, '바뀐 영상을 안 바꿨다: %r' % s
        # 5) 돌림 규칙: 없으면 거짓 · 목적지가 다르면 거짓 · 맞으면 참
        if redirect_ok(site):
            return False, 'vercel.json 이 없는데 통과했다'
        cfg = {'redirects': [{'source': '/(.*)\\.(mp4|webm|mov|m4v)',
                              'destination': 'https://elsewhere.example/$1.$2'}]}
        json.dump(cfg, io.open(os.path.join(site, 'vercel.json'), 'w'))
        if redirect_ok(site):
            return False, '목적지가 다른데 통과했다'
        cfg['redirects'][0]['destination'] = MEDIA_BASE + '/$1.$2'
        json.dump(cfg, io.open(os.path.join(site, 'vercel.json'), 'w'))
        if not redirect_ok(site):
            return False, '맞는 규칙을 못 알아봤다'
    return True, '알려진 답 5단계 · 돌림 규칙 3칸'


def main(site, write=True):
    ok, why = _selftest()
    if not ok:
        print('  [!] 자기시험 실패: %s' % why)
        return False
    print('  자기시험 통과 (%s)' % why)
    if not redirect_ok(site):
        print('  [!] vercel.json 에 영상 돌림 규칙이 없거나 목적지가 %s 가 아닙니다' % MEDIA_BASE)
        return False
    nas = nas_root()
    if not nas:
        print('  [!] NAS 영상 폴더에 닿지 않습니다 (%s).\n      %s'
              % (' 또는 '.join(NAS_ROOTS), HOW_TO_MOUNT))
        return False
    s = offload(site, nas, write=write)
    print('  NAS %s · 배포본 영상 %d개 · 이미 있음 %d · 새로 올림 %d · 배포본에서 뺌 %d'
          % (nas, s['found'], s['already'], s['copied'], s['removed']))
    if s['mismatch']:
        print('  [!] 복사 대조 실패 %d개: %s' % (len(s['mismatch']), ' · '.join(s['mismatch'][:3])))
        return False
    if s['missing']:
        print('  [!] NAS 에 없는 영상 %d개 (검사 모드라 올리지 않음): %s'
              % (len(s['missing']), ' · '.join(s['missing'][:3])))
        return False
    left = [n for r, d, fs in os.walk(site) if '.git' not in r for n in fs if n.lower().endswith(VID)]
    if write and left:
        print('  [!] 배포본에 영상이 %d개 남았습니다' % len(left))
        return False
    return True


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    ok, why = _selftest()
    print('selftest', ok, why)
