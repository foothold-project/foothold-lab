"""동일 HTML에서 A4 PDF와 전 페이지 검수 이미지를 생성한다."""
from pathlib import Path
import sys,os,json,threading,http.server,functools
sys.path.insert(0,str(Path(os.environ['TEMP'])/'foothold-mvp-render-deps'))
from playwright.sync_api import sync_playwright
import fitz
from PIL import Image,ImageDraw,ImageFont

ROOT=Path(__file__).resolve().parent

class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self,*args):pass

def main():
    output=ROOT/'output';qa=ROOT/'qa';qa.mkdir(exist_ok=True)
    server=http.server.ThreadingHTTPServer(('127.0.0.1',0),functools.partial(QuietHandler,directory=str(output)))
    threading.Thread(target=server.serve_forever,daemon=True).start()
    with sync_playwright() as p:
        browser=p.chromium.launch(executable_path='C:/Program Files/Google/Chrome/Application/chrome.exe',headless=True)
        page=browser.new_page(viewport={'width':1440,'height':1050},device_scale_factor=1)
        errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
        page.goto(f'http://127.0.0.1:{server.server_port}/FOOTHOLD-MVP.html',wait_until='networkidle')
        page.evaluate('document.fonts.ready')
        page.screenshot(path=str(qa/'web-cover.png'))
        web=page.evaluate('''() => ({tables:document.querySelectorAll('.report-body table').length,videos:document.querySelectorAll('video').length,images:[...document.images].filter(x=>!x.complete||!x.naturalWidth).map(x=>x.alt),width:document.documentElement.scrollWidth,viewport:innerWidth})''')
        page.locator('#s7').scroll_into_view_if_needed();page.screenshot(path=str(qa/'web-experiments.png'))
        audit=page.evaluate('window.preparePrint()')
        page.pdf(path=str(output/'FOOTHOLD-MVP.pdf'),print_background=True,prefer_css_page_size=True)
        # 준비된 인쇄 DOM을 함께 저장해 브라우저 기본 인쇄도 비동기 조판 없이 동작한다.
        print_html=page.evaluate('''() => {const c=document.querySelector('#print-root').cloneNode(true);c.querySelectorAll('video,.media-tools,.original-figure-image').forEach(x=>x.remove());return c.outerHTML}''')
        html=(output/'FOOTHOLD-MVP.html').read_text(encoding='utf-8')
        html=html.replace('<div id="print-root"></div>',print_html)
        (output/'FOOTHOLD-MVP.html').write_bytes(html.encode('utf-8'))
        pdf_errors=page.evaluate('''() => [...document.querySelectorAll('.sheet-body *')].filter(e=>{let r=e.getBoundingClientRect(),b=e.closest('.sheet-body').getBoundingClientRect();return r.width>0&&(r.right>b.right+2||r.left<b.left-2)}).map(e=>({tag:e.tagName,text:e.textContent.slice(0,60)}))''')
        browser.close()
    server.shutdown()
    audit.update({'web':web,'runtime_errors':errors,'horizontal_overflow':pdf_errors})
    (ROOT/'pagination-audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding='utf-8')
    doc=fitz.open(output/'FOOTHOLD-MVP.pdf')
    font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',15)
    for i,page in enumerate(doc):
        pix=page.get_pixmap(matrix=fitz.Matrix(1.35,1.35),alpha=False);pix.save(qa/f'page-{i+1:02d}.png')
    for start in range(0,len(doc),8):
        sheet=Image.new('RGB',(4*300,2*448),'#ddd');draw=ImageDraw.Draw(sheet)
        for j,i in enumerate(range(start,min(start+8,len(doc)))):
            im=Image.open(qa/f'page-{i+1:02d}.png');im.thumbnail((292,415));x=(j%4)*300+4;y=(j//4)*448+24
            sheet.paste(im,(x,y));draw.text((x,y-21),f'PAGE {i+1}',font=font,fill='#161c26')
        sheet.save(qa/f'pages-{start+1:02d}-{min(start+8,len(doc)):02d}.jpg',quality=95)
    (qa/'pdf-text.txt').write_text('\n'.join(p.get_text() for p in doc),encoding='utf-8')
    print(json.dumps({'pages':len(doc),'web':web,'errors':errors,'horizontal_overflow_count':len(pdf_errors),'page_overflow':[x for x in audit['overflow'] if x['overflow']>1],'lowest_fill':sorted(audit['overflow'],key=lambda x:x['used']/x['available'])[:5]},ensure_ascii=False))

if __name__=='__main__':main()
