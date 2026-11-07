# -*- coding: utf-8 -*-
"""영상은 Vercel 에서, 원본 백업은 NAS 에 (#511).

> 분류: 운영
> 작성: 오흥재 · 2026-10-08 00:18 (v1) · super2 · 2026-11-02 05:08 (v2)
> 근거: 실측 (10/7 Funnel 경로 속도 · Vercel 배포 저장소 10 GB · 11/02 라이브 HEAD 200 Server Vercel)
> 요지: 배포본의 영상 · PDF 를 NAS 에 sha256 대조로 백업한다. 배포본에서는 빼지 않는다. vercel.json 에 영상을 바깥으로 돌리는 규칙이 다시 생기면 배포를 막는다.
> 상태: 확정
> 판: v2.0

## 왜

v1 (10/8) 은 영상을 배포본에서 빼고 vercel.json 돌림 규칙으로 NAS (Tailscale Funnel)
에서 내보냈다. 바깥 망에서 갤러리가 8 ~ 17 초 걸려 10/9 팀장 결정 「가」 로 되돌렸고,
foothold-site 625587a2 가 영상 345 개 · PDF 7 개를 배포본에 되가져오고 돌림 줄을 지웠다.
lab 의 이 파일과 vercel.json 은 그 뒤로 v1 그대로라, lab 에서 다시 배포하면 10/9 결정이
조용히 되돌아갈 자리였다 (11/02 발견). 원본 백업은 그대로 NAS 에 한다.

## 어떻게

- 페이지도 영상도 Vercel 이 낸다. 이 단계는 배포본을 바꾸지 않는다.
- 배포본의 영상 · PDF 마다 NAS 에 같은 sha256 이 있는지 보고, 없거나 다르면 복사해
  대조한 뒤 `MANIFEST.sha256` 에 적는다. 배포본에서 지우지 않는다.
- NAS 에 못 닿거나 복사 대조가 틀리면 크게 알리되 배포는 막지 않는다. 웹 배포가 NAS 에
  기대지 않는 것이 10/9 결정이다. 백업이 안 된 개수는 숫자로 찍는다.

## 관문 (막는 것)

1. vercel.json 에 영상 · PDF 를 바깥 주소 (http · https) 로 돌리는 규칙이 없다.
2. 배포본 영상 · PDF 가 0 개가 아니다 (누가 다시 빼면 잡는다 · 빈 대상을 통과라 하지 않는다).
3. 자기시험이 알려진 답으로 통과한다.

★ 이 관문이 «못 잡는 것»
- NAS 백업이 «최신인지» 는 배포 때만 본다. 배포 없이 NAS 가 바뀌면 모른다.
- 영상 서버 (Vercel) 의 실제 응답 · 속도. 배포 뒤 실제 주소에서 잰다.

## 판 이력

| 판 | 날짜 | 무엇 | 왜 |
|---|---|---|---|
| v1.0 | 2026-10-08 | 처음 씀 (영상을 NAS 로 넘기고 배포본에서 뺌) | 팀장 10/7 「원본은 foothold 공유 그대로」 · Funnel 실측 통과 |
| v1.1 | 2026-10-08 | PDF 도 넘긴다 · vercel.json 규칙에 pdf | 팀장 10/8 경량화 ② 승인 |
| v2.0 | 2026-11-02 | 백업만 한다 (빼지 않음 · 바깥 돌림 규칙이 있으면 막음 · NAS 실패는 경고) | 10/9 팀장 결정 「가」 를 lab 빌드에 맞춤 |
"""
import hashlib
import io
import json
import os
import shutil
import sys
import tempfile

# 순서대로 찾는다. UNC 는 `net use` 로 자격이 이 로그인 세션에 들어 있어야 열린다.
NAS_ROOTS = (r'\\100.80.160.84\foothold\media\site', r'N:\media\site')
VID = ('.mp4', '.webm', '.mov', '.m4v', '.pdf')   # 10/8 경량화 ②: 산출물 PDF 도 백업
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


def media_redirects(site):
    """vercel.json 에서 영상 · PDF 를 바깥 주소로 돌리는 규칙의 목적지들. 없으면 []."""
    p = os.path.join(site, 'vercel.json')
    try:
        cfg = json.load(io.open(p, encoding='utf-8'))
    except (OSError, ValueError):
        return []
    out = []
    for r in cfg.get('redirects') or []:
        src, dst = str(r.get('source', '')), str(r.get('destination', ''))
        if any(e.lstrip('.') in src for e in VID) and dst.startswith(('http://', 'https://')):
            out.append(dst)
    return out


def _media(site):
    vids = []
    for root, dirs, files in os.walk(site):
        if '.git' in dirs:
            dirs.remove('.git')
        for n in files:
            if n.lower().endswith(VID):
                vids.append(os.path.join(root, n))
    return vids


def backup(site, nas, write=True):
    """배포본(site) 의 영상 · PDF 를 NAS 에 백업한다. 배포본은 건드리지 않는다.

    돌려주는 것: dict(found, already, copied, missing, mismatch)
    write=False 면 NAS 에 쓰지 않는다 (없는 것만 센다).
    """
    st = dict(found=0, already=0, copied=0, missing=[], mismatch=[])
    vids = _media(site)
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
        # 1) 검사만: NAS 에 없으면 missing 으로 센다 · NAS 에 안 쓴다
        s = backup(site, nas, write=False)
        if s['missing'] != ['a/b/x.mp4'] or os.listdir(nas):
            return False, '검사 모드가 없는 영상을 못 셌거나 NAS 에 썼다: %r' % s
        # 2) 쓰기: 복사 · 대조 · 목록 기록 · 배포본에는 그대로 남는다
        s = backup(site, nas, write=True)
        if s['copied'] != 1 or not os.path.isfile(v) \
                or not os.path.isfile(os.path.join(nas, 'a', 'b', 'x.mp4')):
            return False, '복사가 기대와 다르거나 배포본에서 지웠다: %r' % s
        if 'a/b/x.mp4' not in io.open(os.path.join(nas, MANIFEST), encoding='utf-8').read():
            return False, '목록에 안 적혔다'
        # 3) 같은 영상이면 다시 복사하지 않는다
        s = backup(site, nas, write=True)
        if (s['already'], s['copied']) != (1, 0):
            return False, '이미 있는 영상을 다시 복사했다: %r' % s
        # 4) 내용이 바뀐 영상은 다시 복사
        io.open(v, 'wb').write(b'clip-2')
        s = backup(site, nas, write=True)
        if s['copied'] != 1 or io.open(os.path.join(nas, 'a', 'b', 'x.mp4'), 'rb').read() != b'clip-2':
            return False, '바뀐 영상을 안 바꿨다: %r' % s
        # 5) 돌림 규칙: 없으면 [] · 안쪽 주소 돌림은 [] · 바깥으로 돌리면 잡는다 (pdf 만 있어도)
        if media_redirects(site):
            return False, 'vercel.json 이 없는데 돌림 규칙을 찾았다'
        cfg = {'redirects': [{'source': '/old', 'destination': '/new'},
                             {'source': '/(.*)\\.(mp4|webm)', 'destination': '/v/$1.$2'}]}
        json.dump(cfg, io.open(os.path.join(site, 'vercel.json'), 'w'))
        if media_redirects(site):
            return False, '사이트 안쪽 돌림을 바깥 돌림으로 셌다'
        cfg['redirects'].append({'source': '/(.*)\\.pdf', 'destination': 'https://nas.example/$1.pdf'})
        json.dump(cfg, io.open(os.path.join(site, 'vercel.json'), 'w'))
        if media_redirects(site) != ['https://nas.example/$1.pdf']:
            return False, '바깥으로 돌리는 규칙을 못 잡았다'
    return True, '알려진 답 4단계 · 돌림 규칙 3칸'


def main(site, write=True):
    ok, why = _selftest()
    if not ok:
        print('  [!] 자기시험 실패: %s' % why)
        return False
    print('  자기시험 통과 (%s)' % why)
    bad = media_redirects(site)
    if bad:
        print('  [!] vercel.json 이 영상 · PDF 를 바깥으로 돌립니다: %s\n'
              '      10/9 팀장 결정은 Vercel 에서 직접 내는 것입니다. 그 규칙을 지우십시오' % ' · '.join(bad))
        return False
    vids = _media(site)
    if not vids:   # 재현 모드에서도 lab 영상이 들어온다. 0 이면 검사할 것이 없었던 것이지 통과가 아니다
        print('  [!] 배포본에 영상 · PDF 가 0 개입니다. 누가 배포본에서 뺐는지 보십시오')
        return False
    nas = nas_root()
    if not nas:
        print('  [!!] NAS 백업 안 됨: %s 에 닿지 않습니다. 배포는 계속하지만 영상 · PDF %d 개가 '
              '이번에 백업되지 않았습니다.\n      %s'
              % (' 또는 '.join(NAS_ROOTS), len(vids), HOW_TO_MOUNT))
        return True
    s = backup(site, nas, write=write)
    print('  NAS %s · 배포본 영상 · PDF %d개 · 이미 있음 %d · 새로 백업 %d'
          % (nas, s['found'], s['already'], s['copied']))
    if s['mismatch']:
        print('  [!!] NAS 백업 대조 실패 %d개 (배포는 계속): %s'
              % (len(s['mismatch']), ' · '.join(s['mismatch'][:3])))
    if s['missing']:
        print('  NAS 에 없는 것 %d개 (검사 모드라 백업하지 않음): %s'
              % (len(s['missing']), ' · '.join(s['missing'][:3])))
    return True


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    ok, why = _selftest()
    print('selftest', ok, why)
