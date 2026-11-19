#!/usr/bin/env python3
"""Back up Go2 X Jetson recordings to ai-lx01 and the NAS, then mark them (owner 11/19 16:35).

Runs on ai-lx01. For each finished folder in the Jetson records directory:
  1. make SHA256SUMS on the Jetson if the recorder did not (folder idle 10 min, no ros2 bag on it)
  2. rsync Jetson -> ai-lx01 D drive /mnt/win-d/mai/data/go2x_raw/jetson_go2_diag/records/<name>, sha256sum -c there
  3. rsync ai-lx01 -> NAS /volume1/foothold/go2x-raw/jetson_go2_diag/records/<name> over ssh, sha256sum -c there
  4. only when both pass, write .backup.json on the Jetson folder
Deleting on the Jetson is never automatic: `delete <name> --yes` re-checks all three copies first.
Every run writes ~/.mai/jetson-storage/status.json for the app status line.

  jetson_sync.py sync            # timer, every 10 min
  jetson_sync.py status
  jetson_sync.py candidates
  jetson_sync.py delete 20261119-0520-room-walk-full --yes
"""
import argparse
import datetime as dt
import hashlib
import json
import os
import re
import subprocess
import sys

JET = 'nvidia@100.107.113.1'   # go2x-jetson; only the tailnet IP is in known_hosts
JROOT = 'go2_diag/records'      # relative to the Jetson home
LOCAL = '/mnt/win-d/mai/data/go2x_raw/jetson_go2_diag/records'   # D drive (owner 11/19 17:12)
NAS = 'VFXPEDIA@100.80.160.84'
NAS_KEY = os.path.expanduser('~/.ssh/ai-nas01-backup-admin-20260912')
NROOT = '/volume1/foothold/go2x-raw/jetson_go2_diag/records'
STATE = os.path.expanduser('~/.mai/jetson-storage')
SUMS, MARK = 'SHA256SUMS', '.backup.json'
IDLE_S = 600
NAME = re.compile(r'^[A-Za-z0-9][A-Za-z0-9._-]*$')
SSH = ['ssh', '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes', '-o', 'ConnectTimeout=10']
SSH_J = SSH + [JET]
SSH_N = SSH + ['-i', NAS_KEY, NAS]

# Listed on the Jetson in one ssh call: name, size, idle seconds, SUMS hash, mark, whether a recorder holds it.
LIST = r'''
import hashlib, json, os, subprocess, time
root = os.path.expanduser('~/%s')
procs = subprocess.run(['pgrep', '-af', 'ros2 bag record|jrec.py|academy_1119'], capture_output=True, text=True).stdout
st = os.statvfs(root)
out = dict(free_gb=st.f_bavail * st.f_frsize / 1e9, folders=[])
for name in sorted(os.listdir(root)):
    d = os.path.join(root, name)
    if not os.path.isdir(d):
        continue
    size, newest = 0, os.stat(d).st_mtime
    for b, _, fs in os.walk(d):
        for f in fs:
            s = os.lstat(os.path.join(b, f))
            size += s.st_size
            newest = max(newest, s.st_mtime)
    sums = os.path.join(d, 'SHA256SUMS')
    mark = os.path.join(d, '.backup.json')
    out['folders'].append(dict(name=name, size=size, idle_s=time.time() - newest,
        sums=hashlib.sha256(open(sums, 'rb').read()).hexdigest() if os.path.exists(sums) else None,
        mark=json.load(open(mark)) if os.path.exists(mark) else None,
        recording=d in procs or name in procs))
print(json.dumps(out))
''' % JROOT

MAKE_SUMS = ('cd ~/%s/{n} && find . -type f ! -name SHA256SUMS ! -name .backup.json ! -name "*.tmp" -print0 '
             '| sort -z | xargs -0 -r nice -n 19 sha256sum > SHA256SUMS.tmp && mv SHA256SUMS.tmp SHA256SUMS') % JROOT


def run(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, **kw)


def now():
    return dt.datetime.now().astimezone().isoformat(timespec='seconds')


def classify(f):
    """What to do with one Jetson folder. Pure, so it is tested without the robot."""
    if f['recording']:
        return 'recording'
    if f['sums'] is None:
        return 'make_sums' if f['idle_s'] >= IDLE_S else 'young'
    m = f['mark']
    a, n = m.get('ailx01', {}) if m else {}, m.get('nas', {}) if m else {}
    if m and m.get('sums') == f['sums'] and a.get('ok') and a.get('path', '').startswith(LOCAL) \
            and n.get('ok') and n.get('path', '').startswith(NROOT):
        return 'backed_up'
    return 'copy'


def jetson_list():
    r = run(SSH_J + ['python3', '-'], input=LIST, timeout=300)
    if r.returncode:
        return None
    return json.loads(r.stdout)


def check_local(name):
    r = run(['sha256sum', '-c', '--quiet', SUMS], cwd=os.path.join(LOCAL, name), timeout=7200)
    return r.returncode == 0


def check_nas(name):
    r = run(SSH_N + ['cd %s/%s && sha256sum -c --quiet %s' % (NROOT, name, SUMS)], timeout=7200)
    return r.returncode == 0


def check_jetson(name):
    r = run(SSH_J + ['cd ~/%s/%s && nice -n 19 sha256sum -c --quiet %s' % (JROOT, name, SUMS)], timeout=7200)
    return r.returncode == 0


def sums_hash_local(name):
    with open(os.path.join(LOCAL, name, SUMS), 'rb') as f:
        return hashlib.sha256(f.read()).hexdigest()


def back_up(f, log):
    n = f['name']
    os.makedirs(os.path.join(LOCAL, n), exist_ok=True)
    r = run(['rsync', '-a', '--exclude', MARK, '-e', ' '.join(SSH), '%s:%s/%s/' % (JET, JROOT, n),
             os.path.join(LOCAL, n) + '/'], timeout=14400)
    if r.returncode:
        log.append((n, 'rsync_jetson_failed', r.returncode))
        return False
    if sums_hash_local(n) != f['sums']:
        log.append((n, 'sums_changed_during_copy', 0))
        return False
    ok_local = check_local(n)
    if not ok_local:
        log.append((n, 'ailx01_verify_failed', 0))
        return False
    # Skip sending when the NAS copy already verifies (e.g. only the ai-lx01 path moved to D on 11/19).
    # UGREEN wraps rsync over ssh and refuses plain paths ("invalid path"), so ssh + tar like the RL backup.
    if not check_nas(n):
        tar = subprocess.Popen(['tar', '-C', LOCAL, '--exclude', MARK, '-cf', '-', n], stdout=subprocess.PIPE)
        r = run(SSH_N + ['mkdir -p %s && tar -C %s -xf -' % (NROOT, NROOT)], stdin=tar.stdout, timeout=14400)
        tar.stdout.close()
        if tar.wait() or r.returncode:
            log.append((n, 'nas_copy_failed', r.returncode))
            return False
        if not check_nas(n):
            log.append((n, 'nas_verify_failed', 0))
            return False
    mark = dict(sums=f['sums'], ailx01=dict(ok=True, path=os.path.join(LOCAL, n), at=now()),
                nas=dict(ok=True, path='%s/%s' % (NROOT, n), at=now()))
    r = run(SSH_J + ["cat > ~/%s/%s/%s.tmp && mv ~/%s/%s/%s.tmp ~/%s/%s/%s" % ((JROOT, n, MARK) * 3)],
            input=json.dumps(mark, indent=1), timeout=60)
    log.append((n, 'backed_up' if r.returncode == 0 else 'mark_write_failed', r.returncode))
    return r.returncode == 0


def write_status(listing, log):
    os.makedirs(STATE, exist_ok=True)
    s = dict(time=now(), jetson_reachable=listing is not None)
    if listing:
        kinds = [classify(f) for f in listing['folders']]
        s.update(free_gb=round(listing['free_gb'], 1),
                 records_gb=round(sum(f['size'] for f in listing['folders']) / 1e9, 1),
                 folders=len(kinds), not_backed_up=sum(k != 'backed_up' for k in kinds),
                 recording=kinds.count('recording'), delete_candidates=kinds.count('backed_up'))
    s['failed'] = [dict(name=n, why=w) for n, w, _ in log if w != 'backed_up']
    s['line'] = ('Jetson 연결 안 됨' if listing is None else
                 'Jetson 남은 %(free_gb)s GB · 백업 안 된 녹화 %(not_backed_up)d 개 · 지울 수 있는 것 %(delete_candidates)d 개' % s)
    tmp = os.path.join(STATE, 'status.json.tmp')
    with open(tmp, 'w') as fh:
        json.dump(s, fh, ensure_ascii=False, indent=1)
    os.replace(tmp, os.path.join(STATE, 'status.json'))
    with open(os.path.join(STATE, 'log.tsv'), 'a') as fh:
        for n, w, rc in log:
            fh.write('%s\t%s\t%s\t%s\n' % (now(), n, w, rc))
    return s


def sync():
    import fcntl
    os.makedirs(STATE, exist_ok=True)
    lock = open(os.path.join(STATE, 'sync.lock'), 'w')
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)   # the timer and a manual run never copy at once
    except OSError:
        print('another sync is running')
        return 0
    listing, log = jetson_list(), []
    if listing:
        for f in listing['folders']:
            kind = classify(f)
            if kind == 'make_sums':
                r = run(SSH_J + [MAKE_SUMS.format(n=f['name'])], timeout=7200)
                log.append((f['name'], 'sums_made' if r.returncode == 0 else 'sums_failed', r.returncode))
        listing = jetson_list() or listing   # folders that just got SHA256SUMS are copied in the same run
        for f in listing['folders']:
            if classify(f) == 'copy':
                back_up(f, log)
        listing = jetson_list() or listing
    s = write_status(listing, [x for x in log if x[1] != 'sums_made'])
    print(s['line'])
    return 0 if not s['failed'] else 1


def delete(name, yes):
    if not NAME.match(name):
        print('bad name')
        return 2
    listing = jetson_list()
    f = next((x for x in (listing or {}).get('folders', []) if x['name'] == name), None)
    if f is None or classify(f) != 'backed_up':
        print('refused: not a delete candidate (%s)' % (classify(f) if f else 'missing'))
        return 2
    checks = dict(jetson=check_jetson(name), ailx01=check_local(name) and sums_hash_local(name) == f['sums'],
                  nas=check_nas(name))
    if not all(checks.values()):
        print('refused: verify failed %s' % checks)
        return 2
    if not yes:
        print('ok to delete %s (%.1f GB). Run again with --yes after the owner confirms.' % (name, f['size'] / 1e9))
        return 0
    r = run(SSH_J + ['rm -rf -- ~/%s/%s' % (JROOT, name)], timeout=600)
    write_status(jetson_list(), [(name, 'deleted_on_jetson' if r.returncode == 0 else 'delete_failed', r.returncode)])
    print('deleted' if r.returncode == 0 else 'delete failed')
    return r.returncode


def main(argv=None):
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest='cmd', required=True)
    sub.add_parser('sync')
    sub.add_parser('status')
    sub.add_parser('candidates')
    d = sub.add_parser('delete')
    d.add_argument('name')
    d.add_argument('--yes', action='store_true')
    a = ap.parse_args(argv)
    if a.cmd == 'sync':
        return sync()
    if a.cmd == 'delete':
        return delete(a.name, a.yes)
    listing = jetson_list()
    if a.cmd == 'status':
        print(write_status(listing, [])['line'])
        return 0
    for f in (listing or {}).get('folders', []):
        if classify(f) == 'backed_up':
            print('%6.2f GB  %s' % (f['size'] / 1e9, f['name']))
    return 0


if __name__ == '__main__':
    sys.exit(main())
