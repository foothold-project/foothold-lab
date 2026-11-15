from pathlib import Path
import sys,json,hashlib
sys.path.insert(0,str(Path.home()/'AppData/Local/Temp/foothold-mvp-render-deps'))
from playwright.sync_api import sync_playwright
from PIL import Image,ImageDraw
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'output'
errors=[];frames=[];checks={}
with sync_playwright() as pw:
    browser=pw.chromium.launch(executable_path='C:/Program Files/Google/Chrome/Application/chrome.exe',headless=True,args=['--allow-file-access-from-files'])
    page=browser.new_page(viewport={'width':1600,'height':900},reduced_motion='reduce')
    page.on('pageerror',lambda e:errors.append(str(e)))
    page.goto((OUT/'FOOTHOLD-MVP-cover.html').as_uri());page.wait_for_timeout(1000)
    page.keyboard.press('ArrowRight');page.wait_for_timeout(1100)
    checks['opening_autoplay']=page.locator('.slide.active video').evaluate('(v)=>!v.paused&&v.currentTime>0')
    count=page.locator('.slide').count();checks['slides']=count
    broken=[];video=[];headers=[];footers=[]
    for index in range(count):
        maxstep=page.locator('.slide').nth(index).get_attribute('data-steps') or 0
        page.evaluate('([i,s])=>footholdDeck.show(i,s)',[index,int(maxstep)])
        page.wait_for_timeout(600 if index not in [9,10,11] else 3000)
        video+=page.locator('.slide.active video').evaluate_all('(vs)=>vs.map(v=>({src:v.getAttribute("src"),muted:v.muted,loop:v.loop,autoplay:(v.hasAttribute("data-autoplay")||v.autoplay),paused:v.paused,error:v.error?.code||null}))')
        broken+=page.locator('.slide.active img').evaluate_all('(xs)=>xs.filter(x=>!x.complete||!x.naturalWidth).map(x=>x.src)')
        if page.locator('.slide.active header').count():headers.append(page.locator('.slide.active header').bounding_box())
        if page.locator('.slide.active footer').count():footers.append(page.locator('.slide.active footer').bounding_box())
        page.locator('.slide.active video').evaluate_all('(vs)=>vs.forEach(v=>v.pause())')
        f=OUT/f'u206-after-{index+1:02}.jpg';page.screenshot(path=str(f),quality=80);frames.append(f)
    for index,step in [(2,0),(5,0),(5,2),(9,0),(9,1),(9,2),(9,3),(9,4),(9,5),(9,6),(9,7),(10,0),(10,1),(10,2),(10,3),(10,4)]:
        page.evaluate('([i,s])=>footholdDeck.show(i,s)',[index,step]);page.wait_for_timeout(800)
        if index==9 and step in [1,2]:page.wait_for_timeout(3100)
        if index==9 and step==3:page.wait_for_timeout(11000)
        if index==10 and step==1:page.wait_for_timeout(8000)
        f=OUT/f'u206-detail-{index+1:02}-{step}.jpg';page.screenshot(path=str(f),quality=85)
    checks.update(errors=errors,broken_images=broken,video=video,headers=headers,footers=footers,sha256=hashlib.sha256((OUT/'FOOTHOLD-MVP-cover.html').read_bytes()).hexdigest())
    (OUT/'u206-verification.json').write_text(json.dumps(checks,ensure_ascii=False,indent=2),encoding='utf8')
    browser.close()
for batch in range((len(frames)+7)//8):
    sheet=Image.new('RGB',(1200,4*358),'#d8ddd9');d=ImageDraw.Draw(sheet)
    for j,f in enumerate(frames[batch*8:(batch+1)*8]):
        im=Image.open(f);im.thumbnail((600,338));x=(j%2)*600;y=(j//2)*358;d.text((x+5,y+3),str(batch*8+j+1),fill='black');sheet.paste(im,(x,y+20))
    sheet.save(OUT/f'u206-after-contact-{batch}.jpg')
print(json.dumps({'slides':count,'errors':errors,'broken':broken,'opening_autoplay':checks['opening_autoplay']}))
