"""현재 공개본과 그림·영상 원본을 보존하고 제출본 대조 목록을 만든다."""
from pathlib import Path
from urllib.parse import urljoin, urlparse
from urllib.request import urlopen
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import hashlib
import json
import argparse
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent
URL = 'https://foothold-project.vercel.app/research-20260928-v2-mvp-report'

def digest(data):
    return hashlib.sha256(data).hexdigest()

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--refresh', action='store_true')
    args = parser.parse_args()
    source = ROOT / 'source'
    source.mkdir(exist_ok=True)
    if args.refresh or not (source / 'report.html').exists():
        data = urlopen(URL, timeout=60).read()
        previous = source / 'report.html'
        if previous.exists() and previous.read_bytes() != data:
            (source / ('report-' + digest(previous.read_bytes())[:12] + '.html')).write_bytes(previous.read_bytes())
        previous.write_bytes(data)
        (source / 'snapshot.json').write_text(json.dumps({
            'url': URL, 'retrieved_at': datetime.now().astimezone().isoformat(),
            'sha256': digest(data)}, ensure_ascii=False, indent=2), encoding='utf-8')
    soup = BeautifulSoup((source / 'report.html').read_bytes(), 'html.parser')
    inventory = {'source': json.loads((source / 'snapshot.json').read_text(encoding='utf-8')),
                 'sections': [], 'assets': [], 'videos': []}
    requests = {}
    for si, section in enumerate(soup.select('section')):
        blocks = []
        for ni, node in enumerate(section.find_all(recursive=False)):
            if node.name in ['script', 'style', 'span']:
                continue
            text = node.get_text(' ', strip=True)
            blocks.append({'id': f'{section.get("id")}-b{ni:03d}', 'tag': node.name,
                           'classes': node.get('class', []), 'text': text,
                           'sha256': digest(str(node).encode()),
                           'tables': len(node.select('table')), 'images': len(node.select('img')),
                           'videos': len(node.select('video'))})
        inventory['sections'].append({'id': section.get('id'), 'title': section.h2.get_text(' ',strip=True),
                                      'blocks': blocks})
    for node in soup.select('img,video'):
        for attr in ['src', 'poster']:
            if not node.get(attr):
                continue
            url = urljoin(URL, node[attr])
            name = Path(urlparse(url).path).name
            local = 'source/media/' + name
            requests[url] = {'url': url, 'local': local, 'kind': 'video' if name.endswith('.mp4') else 'image'}
        if node.name == 'video':
            fig = node.find_parent('figure')
            inventory['videos'].append({'id': f'V{len(inventory["videos"])+1:02d}',
                'url': urljoin(URL,node['src']), 'file': Path(urlparse(node['src']).path).name,
                'title': fig.select_one('.vcmp-name').get_text(' ',strip=True) if fig else '',
                'caption': fig.figcaption.get_text(' ',strip=True) if fig and fig.figcaption else '',
                'section': node.find_parent('section').get('id')})
    def download(entry):
        path = ROOT / entry['local']
        path.parent.mkdir(exist_ok=True)
        # URL query fingerprint can change without a filename change.
        marker = path.with_suffix(path.suffix + '.url')
        if not path.exists() or not marker.exists() or marker.read_text() != entry['url']:
            data = urlopen(entry['url'],timeout=90).read()
            path.write_bytes(data)
            marker.write_text(entry['url'])
        data = path.read_bytes()
        return {**entry, 'bytes': len(data), 'sha256': digest(data)}
    with ThreadPoolExecutor(max_workers=6) as pool:
        inventory['assets'] = list(pool.map(download, requests.values()))
    inventory['counts'] = {k: len(soup.select(k)) for k in ['section','table','img','video']}
    (ROOT / 'inventory.json').write_text(json.dumps(inventory,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'counts': inventory['counts'], 'assets': len(inventory['assets']),
                      'download_MB':round(sum(x['bytes'] for x in inventory['assets'])/1e6,2)},ensure_ascii=False))

if __name__ == '__main__':
    main()
