# -*- coding: utf-8 -*-
"""입력이 같으면 기존 암호문을 재사용한다 (mai-os#22 · 묶음 6.6).

  왜
    빌드할 때마다 salt 를 새로 만들고 전부 다시 암호화했다. 원본이 하나도
    안 바뀐 날에도 `.enc` 아홉 개와 manifest 가 통째로 달라졌다.
    그래서 「이 빌드가 무엇을 바꿨는가」를 물을 수 없었다.

  ★ 난수성은 그대로 둔다
    salt = os.urandom(16) · nonce = os.urandom(12).
    바뀌는 것은 «언제 다시 암호화하는가» 뿐이다. 내용에서 nonce 를 유도하지
    않는다. 그것은 AES-GCM 의 IV 유일성 요구를 깬다 (NIST SP 800-38D).

  ★ 공개 manifest 에 비밀번호에서 나온 값을 적지 않는다
    `assets/` 는 통째로 공개 저장소로 복사된다 (build.py 의 DIRS).
    비밀번호 해시도, 그 앞자리도, 원문 해시도 거기 두지 않는다.
    원문 해시는 «비공개 캐시» 에만 둔다. 캐시는 `_build/` 에 있고,
    `_build` 는 배포 제외 목록(NEVER)에 있어 사이트로 나가지 않는다.

  비밀번호가 같은지 어떻게 아는가
    기존 manifest 의 salt 로 키를 유그림 기존 `check` 암호문을 **실제로 복호화**한다.
    풀리면 같은 키다. 해시를 견주지 않는다.

  다시 전부 암호화하는 경우 (셋 중 하나라도 걸리면)
    · 비밀번호가 다르다        · enc_version 이 올랐다      · PBKDF2 반복수가 다르다
    · 캐시가 없거나 salt 가 어긋난다
    이때는 새 salt 를 만들고 전부 새 nonce 로 다시 암호화한다.
    **한 manifest 안에 서로 다른 salt 기준의 암호문을 섞지 않는다.**

  원자적 교체
    새 폴더에 한 벌을 다 만든 뒤 한 번에 바꾼다. 도중에 죽으면 옛 벌이 그대로 남는다.
"""
import hashlib
import io
import json
import os
import shutil

ENC_VERSION = 1                       # 형식이 바뀌면 올린다. 올리면 전부 재암호화
CHECK_PLAIN = b'foothold-check'       # 비밀번호 확인용 알려진 평문


def digest(data):
    return hashlib.sha256(data).hexdigest()


def derive(password, salt, iters):
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    from cryptography.hazmat.primitives import hashes
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt,
                     iterations=iters)
    return kdf.derive(password.encode('utf-8'))


def encrypt(data, key):
    """항상 새 nonce 로 암호화한다. 여기에 결정론이 끼어들 자리는 없다."""
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    nonce = os.urandom(12)
    return nonce + AESGCM(key).encrypt(nonce, data, None)


def decrypt(blob, key):
    """풀리면 평문, 안 풀리면 None. 예외를 밖으로 흘리지 않는다."""
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    try:
        return AESGCM(key).decrypt(blob[:12], blob[12:], None)
    except Exception:
        return None


def _read_json(path):
    try:
        return json.load(io.open(path, encoding='utf-8'))
    except Exception:
        return None


def _write_atomic(path, text):
    """같은 폴더에 임시로 쓰고 · 디스크까지 밀어낸 뒤 · 한 번에 바꾼다.

    ★ 왜 «같은 폴더» 인가
      os.replace 는 같은 볼륨 안에서만 원자적이다. 임시 파일을 temp 폴더에
      만들면 볼륨이 달라져 복사가 되고, 그 사이에 죽으면 반쪽 파일이 남는다.

    ★ 왜 flush + fsync 인가
      close 만으로는 OS 버퍼에 남는다. 전원이 끊기면 이름은 바뀌었는데
      내용은 비어 있는 파일이 남는다. 캐시가 깨져도 «전체 재암호화» 로
      안전하게 물러서지만, 애초에 깨지지 않게 하는 편이 낫다.
    """
    tmp = path + '.tmp'
    f = io.open(tmp, 'w', encoding='utf-8')
    try:
        f.write(text)
        f.flush()
        os.fsync(f.fileno())
    finally:
        f.close()
    os.replace(tmp, path)


def is_release_workspace(build_dir):
    """이 작업 공간이 secure 생성을 «소유» 하는가 (팀장 결정 2026-09-02).

      왜 제한하는가
        재사용 캐시는 비공개 로컬 상태다. git 에 올리지 않으므로 새 워크트리·
        다른 장비·A/B 사본에는 따라가지 않는다. 그런 곳에서 secure 를 돌리면
        매번 새 salt 로 전부 재암호화하고, 그 결과가 릴리스본과 어긋난 채
        배포될 수 있다.

      그래서 «지정된 release 작업 공간» 에서만 돈다. 표식은 둘 중 하나다.
        · 환경변수 FOOTHOLD_SECURE_OWNER 가 비어 있지 않다
        · _build/.secure-owner 파일이 있다 (git 무시 대상이라 복제되지 않는다)

      A/B · 검수 · Orca 하위 워크트리는 표식이 없으므로 저절로 건너뛴다.
    """
    if str(os.environ.get('FOOTHOLD_SECURE_OWNER', '')).strip():
        return True
    return os.path.exists(os.path.join(build_dir, '.secure-owner'))


class Session(object):
    """한 번의 암호화 묶음. put 으로 담고 commit 으로 한 번에 바꾼다."""

    def __init__(self, out_dir, cache_path, password, iters,
                 enc_version=ENC_VERSION):
        self.out = os.path.abspath(out_dir)
        self.cache_path = os.path.abspath(cache_path)
        self.iters = iters
        self.enc_version = enc_version
        self.tmp = self.out + '.new'
        self.reused = 0
        self.fresh = 0
        self.entries = {}
        self.tags = {}
        self._decide(password)

    def _decide(self, password):
        """salt 를 이어쓸지 새로 만들지 정한다. 이유를 남긴다."""
        man = _read_json(os.path.join(self.out, 'manifest.json'))
        cache = _read_json(self.cache_path)
        self.old_check = None
        why = None
        if not man:
            why = '기존 manifest 가 없습니다'
        elif man.get('iters') != self.iters:
            why = 'PBKDF2 반복수가 달라졌습니다 (%s -> %s)' % (man.get('iters'), self.iters)
        elif not cache:
            why = '비공개 캐시가 없습니다'
        elif cache.get('enc_version') != self.enc_version:
            why = 'enc_version 이 올랐습니다 (%s -> %s)' % (
                cache.get('enc_version'), self.enc_version)
        elif cache.get('salt') != man.get('salt'):
            why = '캐시의 salt 가 manifest 와 어긋납니다'
        if why is None:
            salt = bytes.fromhex(man['salt'])
            key = derive(password, salt, self.iters)
            # ★ 해시를 견주지 않는다. 기존 check 암호문을 실제로 푼다
            if decrypt(bytes.fromhex(man['check']), key) != CHECK_PLAIN:
                why = '비밀번호가 다릅니다 (기존 check 가 안 풀립니다)'
        if why is None:
            self.salt, self.key = salt, key
            self.old_entries = dict(cache.get('entries') or {})
            self.old_check = man['check']
            self.reason = '기존 salt 유지'
            self.reuse = True
        else:
            self.salt = os.urandom(16)                 # ★ 난수 그대로
            self.key = derive(password, self.salt, self.iters)
            self.old_entries = {}
            self.reason = why + ' -> 새 salt 로 전부 재암호화'
            self.reuse = False
        shutil.rmtree(self.tmp, ignore_errors=True)
        os.makedirs(self.tmp)

    def put(self, name, data):
        """`name` 자리에 `data` 를 싣는다. 안 바뀌었으면 옛 암호문을 옮겨 쓴다."""
        d = digest(data)
        old = self.old_entries.get(name)
        src = os.path.join(self.out, name)
        dst = os.path.join(self.tmp, name)
        if self.reuse and old and old.get('sha256') == d and os.path.exists(src):
            shutil.copyfile(src, dst)
            self.reused += 1
        else:
            io.open(dst, 'wb').write(encrypt(data, self.key))
            self.fresh += 1
        # ★ 캐시 버스터용 태그. **암호문** 의 해시 앞자리다.
        #   전에는 salt 앞자리를 썼는데, salt 를 이어쓰면 바뀐 파일이 옛 주소를
        #   그대로 갖게 되어 브라우저가 옛 암호문을 붙잡는다. 암호문 해시는
        #   내려받으면 누구나 계산할 수 있으므로 원문에 대해 아무것도 말하지 않는다.
        self.tags[name] = digest(io.open(dst, 'rb').read())[:8]
        self.entries[name] = {'sha256': d, 'size': len(data)}
        return name

    def check_hex(self):
        """비밀번호 확인용 암호문. salt 를 이어쓰면 옛것을 그대로 둔다."""
        if self.reuse and self.old_check:
            return self.old_check
        return encrypt(CHECK_PLAIN, self.key).hex()

    def commit(self, manifest_obj):
        """새 벌을 한 번에 바꾼다. 도중에 죽으면 옛 벌이 그대로 남는다."""
        manifest_obj = dict(manifest_obj)
        manifest_obj['salt'] = self.salt.hex()
        manifest_obj['iters'] = self.iters
        manifest_obj['check'] = self.check_hex()
        # 파일별 캐시 버스터. 값은 «암호문» 해시라 원문을 말하지 않는다
        manifest_obj['tags'] = {('assets/secure/' + k): self.tags[k]
                                for k in sorted(self.tags)}
        # ★ 공개로 나가는 것에 원문 해시나 비밀번호 유도값을 넣지 않는다
        for banned in ('sha256', 'digest', 'password', 'password_id', 'entries'):
            manifest_obj.pop(banned, None)
        io.open(os.path.join(self.tmp, 'manifest.json'), 'w',
                encoding='utf-8').write(json.dumps(manifest_obj, ensure_ascii=False))
        old = self.out + '.old'
        shutil.rmtree(old, ignore_errors=True)
        if os.path.isdir(self.out):
            os.rename(self.out, old)
        os.rename(self.tmp, self.out)
        shutil.rmtree(old, ignore_errors=True)
        # 캐시도 같은 방식으로 바꾼다. 반쪽 캐시는 «없는 캐시» 보다 나쁘다
        _write_atomic(self.cache_path, json.dumps(
            {'enc_version': self.enc_version, 'salt': self.salt.hex(),
             'iters': self.iters,
             'entries': {k: self.entries[k] for k in sorted(self.entries)}},
            ensure_ascii=False, indent=1, sort_keys=True))
        return self.reused, self.fresh


def _kat():
    """★ 답을 아는 입력. 여섯 가지를 못 박는다."""
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        out = os.path.join(d, 'secure')
        cache = os.path.join(d, 'enc_cache.json')
        pw = 'pass-one'
        A, B = b'aaa' * 100, b'bbb' * 100

        def run(password, a, b, ver=ENC_VERSION, iters=1000):
            s = Session(out, cache, password, iters, ver)
            s.put('a.enc', a)
            s.put('b.enc', b)
            s.commit({'items': []})
            return s

        # 1) 첫 실행은 전부 새로 만든다
        s1 = run(pw, A, B)
        if s1.reuse or s1.fresh != 2:
            return False, '첫 실행이 재사용이라고 했다'
        salt1 = s1.salt.hex()
        blob = {n: io.open(os.path.join(out, n), 'rb').read() for n in ('a.enc', 'b.enc')}

        # 2) 같은 비밀번호 · 같은 입력 -> 암호문 바이트가 그대로다
        s2 = run(pw, A, B)
        if not s2.reuse or s2.reused != 2 or s2.fresh:
            return False, '안 바뀐 입력을 다시 암호화했다 (%d재사용 %d신규)' % (s2.reused, s2.fresh)
        if s2.salt.hex() != salt1:
            return False, 'salt 를 이어쓰지 않았다'
        for n in ('a.enc', 'b.enc'):
            if io.open(os.path.join(out, n), 'rb').read() != blob[n]:
                return False, '재사용인데 암호문이 달라졌다: ' + n

        # 3) 한 쪽만 바꾸면 그 한 쪽만 새 nonce 로 다시 암호화된다
        s3 = run(pw, A, B + b'!')
        if s3.reused != 1 or s3.fresh != 1:
            return False, '바뀐 하나만 다시 암호화하지 않았다 (%d/%d)' % (s3.reused, s3.fresh)
        if io.open(os.path.join(out, 'a.enc'), 'rb').read() != blob['a.enc']:
            return False, '안 바뀐 쪽까지 다시 암호화했다'
        if io.open(os.path.join(out, 'b.enc'), 'rb').read() == blob['b.enc']:
            return False, '바뀐 쪽이 그대로다'

        # 4) 실제로 풀리는가. 지금 salt·비밀번호로 복호화해 원문이 나와야 한다
        man = _read_json(os.path.join(out, 'manifest.json'))
        key = derive(pw, bytes.fromhex(man['salt']), 1000)
        if decrypt(io.open(os.path.join(out, 'a.enc'), 'rb').read(), key) != A:
            return False, '재사용한 암호문이 안 풀린다'
        if decrypt(bytes.fromhex(man['check']), key) != CHECK_PLAIN:
            return False, 'check 가 안 풀린다'

        # 5) 비밀번호가 다르면 새 salt 로 전부 다시
        s5 = run('pass-two', A, B + b'!')
        if s5.reuse or s5.fresh != 2:
            return False, '다른 비밀번호인데 재사용했다'
        if s5.salt.hex() == salt1:
            return False, '다른 비밀번호인데 salt 를 이어썼다'

        # 6) enc_version 이 오르면 전부 다시
        s6a = run('pass-two', A, B + b'!')
        if not s6a.reuse:
            return False, '같은 조건인데 재사용을 안 했다'
        s6 = run('pass-two', A, B + b'!', ver=ENC_VERSION + 1)
        if s6.reuse or s6.fresh != 2:
            return False, 'enc_version 이 올랐는데 재사용했다'

        # 7) 공개 manifest 에 원문 해시나 비밀번호 유도값이 없어야 한다
        man = _read_json(os.path.join(out, 'manifest.json'))
        flat = json.dumps(man, ensure_ascii=False)
        for e in list(_read_json(cache)['entries'].values()):
            if e['sha256'] in flat:
                return False, '공개 manifest 에 원문 해시가 실렸다'
        if set(man) - {'salt', 'iters', 'check', 'items', 'notes', 'tags'}:
            return False, 'manifest 에 예상 밖 키가 있다: %s' % sorted(man)

        # 8) 캐시 버스터 태그. 바뀐 파일만 태그가 바뀌어야 한다
        #    salt 를 이어쓰면 salt 앞자리로는 «바뀜» 을 알릴 수 없다. 그래서 넣었다
        s8a = run('pass-two', A, B + b'!')
        t_a, t_b = s8a.tags['a.enc'], s8a.tags['b.enc']
        man8 = _read_json(os.path.join(out, 'manifest.json'))
        if man8.get('tags', {}).get('assets/secure/a.enc') != t_a:
            return False, 'manifest 에 파일별 태그가 안 실렸다'
        s8b = run('pass-two', A, B + b'!!')          # b 만 바꾼다
        if s8b.tags['a.enc'] != t_a:
            return False, '안 바뀐 파일의 태그가 흔들렸다'
        if s8b.tags['b.enc'] == t_b:
            return False, '바뀐 파일인데 태그가 그대로다 (브라우저가 옛것을 붙잡는다)'
        if len(set([t_a, t_b])) != 2:
            return False, '태그가 파일을 못 가른다'

        # 9) 캐시가 깨졌으면 «안전하게» 전부 다시. 반쪽 캐시를 믿지 않는다
        io.open(cache, 'w', encoding='utf-8').write('{ 깨진 json')
        s9 = Session(out, cache, 'pass-two', 1000)
        if s9.reuse:
            return False, '깨진 캐시를 믿었다'
        s9.put('a.enc', A); s9.put('b.enc', B)
        s9.commit({'items': []})
        if _read_json(cache) is None:
            return False, '깨진 캐시를 성한 것으로 못 바꿨다'

        # 10) 캐시를 지워도 죽지 않고 전부 다시 한다
        os.remove(cache)
        s10 = Session(out, cache, 'pass-two', 1000)
        if s10.reuse:
            return False, '캐시가 없는데 재사용이라고 했다'
        s10.put('a.enc', A); s10.put('b.enc', B)
        if s10.commit({'items': []})[1] != 2:
            return False, '캐시가 없는데 전부 다시 하지 않았다'

        # 11) 원자적 쓰기. 임시 파일이 «같은 폴더» 에 나고 뒤에 안 남는다
        tgt = os.path.join(d, 'atom.json')
        _write_atomic(tgt, '{"a": 1}')
        if _read_json(tgt) != {'a': 1}:
            return False, '원자적 쓰기가 내용을 안 남겼다'
        if os.path.exists(tgt + '.tmp'):
            return False, '임시 파일이 남았다'
        _write_atomic(tgt, '{"a": 2}')
        if _read_json(tgt) != {'a': 2}:
            return False, '원자적 덮어쓰기가 안 먹었다'

        # 12) 릴리스 소유 표식
        os.environ.pop('FOOTHOLD_SECURE_OWNER', None)
        if is_release_workspace(d):
            return False, '표식이 없는데 소유라고 했다'
        io.open(os.path.join(d, '.secure-owner'), 'w').write('')
        if not is_release_workspace(d):
            return False, '표식 파일이 있는데 소유가 아니라고 했다'
        os.remove(os.path.join(d, '.secure-owner'))
        os.environ['FOOTHOLD_SECURE_OWNER'] = '1'
        try:
            if not is_release_workspace(d):
                return False, '환경변수로 소유를 못 켰다'
        finally:
            os.environ.pop('FOOTHOLD_SECURE_OWNER', None)

        # 13) 원자성. 커밋 전에는 옛 벌이 그대로 보인다
        before = io.open(os.path.join(out, 'a.enc'), 'rb').read()
        s8 = Session(out, cache, 'pass-two', 1000)
        s8.put('a.enc', b'completely-different')
        if io.open(os.path.join(out, 'a.enc'), 'rb').read() != before:
            return False, 'commit 전에 옛 벌이 바뀌었다'
        shutil.rmtree(s8.tmp, ignore_errors=True)
    return True, ''


if __name__ == '__main__':
    import sys
    sys.stdout.reconfigure(encoding='utf-8')
    ok, why = _kat()
    print('자기시험 %s%s' % ('통과' if ok else '실패', '' if ok else ': ' + why))
    sys.exit(0 if ok else 1)
