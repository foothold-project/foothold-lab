# 배포본의 모든 영상 · PDF 를 운영 주소에서 1바이트 구간 요청으로 확인한다 (상태 · 형식 · 전체 크기 대조).
import os, sys, json, subprocess, concurrent.futures as cf
SITE = r'C:/Users/AI-WS01/Desktop/jay/인공지능사관학교/foothold-site'
BASE = 'https://foothold-project.vercel.app'
EXT = ('.mp4', '.webm', '.mov', '.m4v', '.pdf')
files = []
for root, d, fs in os.walk(SITE):
    if '.git' in d: d.remove('.git')
    for n in fs:
        if n.lower().endswith(EXT):
            p = os.path.join(root, n); files.append((os.path.relpath(p, SITE).replace(os.sep, '/'), os.path.getsize(p)))
def check(item):
    rel, size = item
    from urllib.parse import quote
    url = BASE + '/' + quote(rel)
    r = subprocess.run(['curl', '-s', '-o', 'NUL', '-A', 'Mozilla/5.0', '-r', '0-0', '-D', '-', '-w', '%{http_code}|%{redirect_url}', url],
                       capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=60)
    out = r.stdout
    code, redir = out.rsplit('\n', 1)[-1].split('|', 1) if '|' in out.rsplit('\n', 1)[-1] else ('?', '')
    hdr = out.lower()
    total = None
    for ln in hdr.splitlines():
        if ln.startswith('content-range:') and '/' in ln:
            try: total = int(ln.rsplit('/', 1)[1].strip())
            except ValueError: pass
    ok = code == '206' and total == size and not redir
    return rel, code, total, size, redir, ok
with cf.ThreadPoolExecutor(8) as ex:
    res = list(ex.map(check, files))
bad = [r for r in res if not r[5]]
print('files', len(res), 'ok', len(res) - len(bad), 'bad', len(bad))
for r in bad[:20]: print('  BAD', r)
json.dump(res, open('live_media_audit.json', 'w'), ensure_ascii=False)
