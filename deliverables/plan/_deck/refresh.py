# 영상이 바뀌었을 때 덱과 PDF 를 한 번에 갱신하고 결과를 검증한다.
#
#   python refresh.py
#
# 하는 일은 빌드 · PDF 렌더 · 검증 셋이다. 검증이 하나라도 어긋나면 0 이 아닌 값으로
# 끝난다. 「빌드가 돌았다」는 성공의 증거가 아니기 때문에 산출물을 다시 열어서 잰다.
import hashlib
import io
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding='utf-8')
HERE = os.path.dirname(os.path.abspath(__file__))
PLAN = os.path.abspath(os.path.join(HERE, os.pardir))
HTML = os.path.join(PLAN, 'proposal-deck.html')
PDF = os.path.join(PLAN, 'proposal-deck.pdf')
CHROME = [
    r'C:\Program Files\Google\Chrome\Application\chrome.exe',
    r'C:\Program Files (x86)\Google\Chrome\Application\chrome.exe',
    '/usr/bin/google-chrome',
]


def sha(b):
    return hashlib.sha256(b).hexdigest()[:12]


def build():
    r = subprocess.run([sys.executable, os.path.join(HERE, 'slides.py')],
                       cwd=HERE, capture_output=True, text=True, encoding='utf-8')
    sys.stdout.write(r.stdout or '')
    if r.returncode != 0:
        sys.stderr.write(r.stderr or '')
        raise SystemExit('빌드 실패')


def render():
    exe = next((p for p in CHROME if os.path.exists(p)), None)
    if exe is None:
        raise SystemExit('크롬을 찾지 못했다. CHROME 목록에 경로를 넣어라')
    if os.path.exists(PDF):
        os.remove(PDF)
    subprocess.run([exe, '--headless=new', '--disable-gpu', '--no-pdf-header-footer',
                    '--print-to-pdf=' + PDF, 'file:///' + HTML.replace(os.sep, '/')],
                   capture_output=True)
    if not os.path.exists(PDF):
        raise SystemExit('PDF 가 만들어지지 않았다')


def check():
    import pypdf
    h = io.open(HTML, encoding='utf-8').read()
    vis = re.sub(r'data:[a-z0-9/+.-]+;base64,[A-Za-z0-9+/=]+', '', h)
    embedded = base_of(h)
    src = io.open(os.path.join(PLAN, 'assets', 'foothold-launch-720.mp4'), 'rb').read()
    r = pypdf.PdfReader(PDF)
    boxes = {(round(float(p.mediabox.width)), round(float(p.mediabox.height))) for p in r.pages}
    thin = [i + 1 for i, p in enumerate(r.pages) if len(p.get_contents().get_data()) < 300]
    korean = sum(1 for p in r.pages
                 if any(k in p.extract_text() for k in ('험지', '학습', '실증', '정책', '보행')))
    rows = [
        ('심은 영상이 저장소 사본과 같다', sha(embedded) == sha(src), sha(embedded)),
        ('완전한 문서 (file:// 로 열어도 한글이 성한다)',
         h.lstrip().startswith('<!doctype html>') and '<meta charset="utf-8">' in h, ''),
        ('외부 참조 0건 (인터넷 없이 발표된다)',
         not re.search(r'(?:src|href)="(?:https?:)?//', h), ''),
        ('발표 모드가 기본으로 켜진다', "classList.add('present')" in h, ''),
        ('재생이 막히면 안내가 뜬다', 'needtap' in h, ''),
        ('em dash 없음', chr(8212) not in vis, ''),
        ('PDF 19쪽', len(r.pages) == 19, '%d쪽' % len(r.pages)),
        ('PDF 960x540', boxes == {(960, 540)}, str(boxes)),
        ('PDF 빈 쪽 없음', not thin, str(thin)),
        ('PDF 한글 정상', korean >= 15, '%d쪽' % korean),
    ]
    bad = 0
    for name, ok, note in rows:
        print('  %s %-42s %s' % ('OK  ' if ok else '실패', name, note))
        bad += 0 if ok else 1
    print('  HTML %d B · PDF %d B' % (os.path.getsize(HTML), os.path.getsize(PDF)))
    return bad


def base_of(h):
    import base64
    m = re.search(r'src="data:video/mp4;base64,([A-Za-z0-9+/=]+)"', h)
    if m is None:
        raise SystemExit('덱에서 영상을 찾지 못했다')
    return base64.b64decode(m.group(1))


if __name__ == '__main__':
    build()
    render()
    bad = check()
    print('  ' + ('전부 통과' if bad == 0 else '%d건 어긋남' % bad))
    raise SystemExit(1 if bad else 0)
