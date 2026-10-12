"""Download explicitly selected public research inputs. Never starts the APK."""
from pathlib import Path
import urllib.request, urllib.parse, hashlib, json, datetime, sys

ROOT = Path(__file__).resolve().parent
def fetch(url, name):
    dst = ROOT / 'downloads' / name
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists():
        print('exists', name, dst.stat().st_size, flush=True)
        return dst
    req = urllib.request.Request(url, headers={'User-Agent':'ASTRA-local-research/1.0'})
    with urllib.request.urlopen(req, timeout=90) as response, dst.open('xb') as out:
        headers = dict(response.headers)
        parsed = urllib.parse.urlsplit(response.url)
        final = urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, parsed.path, '', ''))
        while True:
            block = response.read(1024*1024)
            if not block: break
            out.write(block)
    meta = {'source':url,'resolved_url':final,'file':name,'bytes':dst.stat().st_size,
            'sha256':hashlib.file_digest(dst.open('rb'),'sha256').hexdigest(),
            'retrieved_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
            'headers':{k:v for k,v in headers.items() if k.lower() in ['content-type','last-modified','etag','content-length']}}
    (ROOT/'logs'/f'{name}.source.json').write_text(json.dumps(meta,indent=2),encoding='utf-8')
    print(json.dumps(meta,ensure_ascii=True),flush=True)
    return dst

if __name__=='__main__': fetch(sys.argv[1],sys.argv[2])
