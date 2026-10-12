"""Collect only packaged frontend assets from the offline APK's loopback server.
No credential fields, application preferences, account endpoints or keys read.
"""
import hashlib,json,pathlib,urllib.request,concurrent.futures
ROOT=pathlib.Path(__file__).resolve().parent
SRC=ROOT/'extracted/assets/dist'
OUT=ROOT/'runtime-web'
OUT.mkdir(exist_ok=True)
def one(p):
    rel=p.relative_to(SRC)
    if p.suffix not in {'.js','.css','.html','.json','.wasm'}: return None
    url='http://127.0.0.1:19979/'+rel.as_posix()
    try: data=urllib.request.urlopen(url,timeout=45).read()
    except Exception as ex: return {'path':rel.as_posix(),'error':type(ex).__name__}
    dest=OUT/rel; dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(data)
    return {'path':rel.as_posix(),'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest(),'apk_same':data==p.read_bytes(),'source':url}
with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
    rows=[x for x in pool.map(one,SRC.rglob('*')) if x]
(ROOT/'evidence/runtime-web-manifest.json').write_text(json.dumps(rows,indent=2),encoding='utf-8')
print(json.dumps({'assets':len(rows),'errors':[x for x in rows if 'error' in x],'changed_from_apk':sum(not x.get('apk_same',True) for x in rows),'total_bytes':sum(x.get('bytes',0) for x in rows)}))
