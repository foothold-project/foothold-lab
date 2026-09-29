"""기본 인쇄, 목차 목적지, 모바일 폭과 파일 묶음을 직접 검사한다."""
from pathlib import Path
import os,sys,json,hashlib
sys.path.insert(0,str(Path(os.environ['TEMP'])/'foothold-mvp-render-deps'))
from playwright.sync_api import sync_playwright
import fitz
ROOT=Path(__file__).resolve().parent

def main():
    result={}
    with sync_playwright() as p:
        browser=p.chromium.launch(executable_path='C:/Program Files/Google/Chrome/Application/chrome.exe',headless=True)
        page=browser.new_page(viewport={'width':390,'height':844})
        page.goto((ROOT/'output/FOOTHOLD-MVP.html').as_uri(),wait_until='load')
        result['mobile']=page.evaluate('({width:innerWidth,scrollWidth:document.documentElement.scrollWidth,broken:[...document.images].filter(x=>!x.complete||!x.naturalWidth).length})')
        page.screenshot(path=str(ROOT/'qa/mobile-cover.png'))
        page.pdf(path=str(ROOT/'qa/native-print.pdf'),print_background=True,prefer_css_page_size=True)
        result['native_print']=page.evaluate('({pages:document.querySelectorAll(".sheet").length,blocks:new Set([...document.querySelectorAll("#print-root [data-source-id]")].map(x=>x.dataset.sourceId)).size})')
        result['native_pdf_pages']=len(fitz.open(ROOT/'qa/native-print.pdf'))
        page.evaluate('window.dispatchEvent(new Event("afterprint"))')
        result['afterprint_web_visible']=page.locator('#web-content').is_visible()
        page.evaluate('window.print=()=>{window.printWasCalled=true}')
        page.locator('#print-button').click()
        page.wait_for_function('window.printWasCalled===true')
        result['print_button']=True
        browser.close()
    doc=fitz.open(ROOT/'output/FOOTHOLD-MVP.pdf')
    links=[l for pg in doc for l in pg.get_links()]
    toc=[l for pg in doc for l in pg.get_links() if l.get('page',-1)>=0]
    result['pdf']={'pages':len(doc),'toc_destinations':len(toc),'valid_destinations':all(0<=l['page']<len(doc) for l in toc),'video_links':len([l for l in links if '.mp4' in l.get('uri','')]),'sha256':hashlib.sha256((ROOT/'output/FOOTHOLD-MVP.pdf').read_bytes()).hexdigest()}
    assert result['mobile']['width']==result['mobile']['scrollWidth'] and result['mobile']['broken']==0,result
    assert result['native_print']['pages']==result['pdf']['pages']==result['native_pdf_pages'],result
    coverage=json.loads((ROOT/'coverage.json').read_text(encoding='utf-8'))
    assert result['native_print']['blocks']==len(coverage['source_blocks']) and len(toc)==coverage['sections'] and result['pdf']['video_links']==coverage['videos'],result
    assert result['afterprint_web_visible'],result
    (ROOT/'delivery-check.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False))

if __name__=='__main__':main()
