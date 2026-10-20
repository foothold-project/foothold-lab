"""ZIP에서 푼 HTML의 모든 영상이 네트워크 없이 재생되는지 검사한다."""
from pathlib import Path
import os,sys,json
sys.path.insert(0,str(Path(os.environ['TEMP'])/'foothold-mvp-render-deps'))
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parent

def main():
    with sync_playwright() as p:
        browser=p.chromium.launch(executable_path='C:/Program Files/Google/Chrome/Application/chrome.exe',headless=True)
        context=browser.new_context(offline=True)
        page=context.new_page();page.goto((ROOT/'tmp/offline-check/FOOTHOLD-MVP.html').as_uri(),wait_until='load')
        results=[]
        for v in page.locator('#web-content video').all():
            result=v.evaluate('''async v=>{v.muted=true;await v.play();await new Promise(r=>setTimeout(r,150));v.pause();return {file:v.getAttribute('src'),time:v.currentTime,error:v.error?.code||null,local:v.currentSrc.startsWith('file:')}}''')
            assert result['time']>0 and result['error'] is None and result['local'],result
            results.append(result)
        expected=json.loads((ROOT/'coverage.json').read_text(encoding='utf-8'))['videos'];assert len(results)==expected
        links=page.locator('.topbar a').evaluate_all("els=>els.map(x=>x.getAttribute('href')).filter(x=>x.endsWith('.pdf'))")
        assert all((ROOT/'tmp/offline-check'/name).exists() for name in links)
        record={'network_disabled':True,'videos':results,'pdf_links':links}
        (ROOT/'offline-check.json').write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
        browser.close();print('offline videos verified:',len(results),'pdf links:',len(links))

if __name__=='__main__':main()
