"""HTML·PDF·영상 22편을 외부 전달용 ZIP으로 묶고 바이트를 검증한다."""
from pathlib import Path
from urllib.parse import urlsplit
import json,zipfile,hashlib
ROOT=Path(__file__).resolve().parent

def main():
    output=ROOT/'output';html=(output/'FOOTHOLD-MVP.html').read_text(encoding='utf-8')
    scenes=json.loads((ROOT/'video-scenes.json').read_text(encoding='utf-8'))
    for scene in scenes:html=html.replace(scene['url'],'media/'+scene['file'])
    archive=output/'FOOTHOLD-MVP-submission.zip'
    readme='''FOOTHOLD MVP 종합보고서

압축을 모두 푼 뒤 FOOTHOLD-MVP.html을 브라우저에서 여십시오.
HTML은 한 웹페이지이며 영상 22편을 인터넷 없이 재생합니다.
FOOTHOLD-MVP.pdf는 여러 장의 A4 문서입니다. 영상 대신 실제 주요 장면을 담았습니다.
PDF의 영상 링크와 원자료 공개 링크는 인터넷 연결이 필요합니다.
media 폴더를 HTML과 함께 유지하십시오. PDF는 HTML과 같은 폴더에 두십시오.

기준: https://foothold-project.vercel.app/research-20260928-v2-mvp-report
공개본 수집: 2026-09-29. 원문의 본문 16절, 표 45개, 그림 8개, 영상 22편 포함.
원문 V15의 6.5초 낙상 설명은 영상과 환경 기록을 대조해 정정했습니다.
대표 장면 3.5초, 낙상 판정 3.70초, 전체 영상 길이 6.48초를 구분합니다.
'''
    files={'FOOTHOLD-MVP.html':html.encode(),'FOOTHOLD-MVP.pdf':(output/'FOOTHOLD-MVP.pdf').read_bytes(),'읽어주세요.txt':readme.encode('utf-8-sig')}
    for scene in scenes:files['media/'+scene['file']]=(ROOT/'source/media'/scene['file']).read_bytes()
    manifest={name:{'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()} for name,data in files.items()}
    with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for name,data in files.items():z.writestr(name,data)
        z.writestr('manifest.json',json.dumps(manifest,ensure_ascii=False,indent=2))
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
        for name,record in manifest.items():assert hashlib.sha256(z.read(name)).hexdigest()==record['sha256']
        target=ROOT/'tmp/offline-check';target.mkdir(parents=True,exist_ok=True);z.extractall(target)
    record={'zip_bytes':archive.stat().st_size,'zip_sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),'files':manifest}
    (ROOT/'package-manifest.json').write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'zip':str(archive),'bytes':record['zip_bytes'],'videos':len(scenes),'files':len(files)},ensure_ascii=False))

if __name__=='__main__':main()
