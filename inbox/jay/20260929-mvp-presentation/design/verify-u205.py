from pathlib import Path
import sys,json,hashlib
sys.path.insert(0,str(Path.home()/'AppData/Local/Temp/foothold-mvp-render-deps'))
from playwright.sync_api import sync_playwright
from PIL import Image,ImageDraw
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'output'
states=[(2,0),(2,1),(2,2),(3,1),(4,3),(5,0),(5,2),(6,2),(7,1),(8,2),(9,0),(9,1),(9,2),(9,3),(9,4),(9,5),(10,1),(10,2),(10,3),(10,4),(11,0),(11,2)]
errors=[];frames=[];checks={}
with sync_playwright() as pw:
    browser=pw.chromium.launch(executable_path='C:/Program Files/Google/Chrome/Application/chrome.exe',headless=True,args=['--allow-file-access-from-files'])
    page=browser.new_page(viewport={'width':1600,'height':900})
    page.on('pageerror',lambda e:errors.append(str(e)))
    page.goto((OUT/'FOOTHOLD-MVP-cover.html').as_uri());page.wait_for_timeout(1000)
    page.keyboard.press('ArrowRight');page.wait_for_timeout(1000)
    assert page.locator('.slide.active video').evaluate('(v)=>!v.paused&&v.currentTime>0')
    checks['film_autoplay_on_next']=True
    for index,step in states:
        page.evaluate('([i,s])=>footholdDeck.show(i,s)',[index,step]);page.wait_for_timeout(1800)
        if index==9 and step==1:page.wait_for_function("document.querySelector('.technical-player').go2Technical.current.state==='twelve_axes'",timeout=20000)
        if index==11 and step==2:page.wait_for_timeout(1500)
        f=OUT/f'u205-{index+1:02}-{step}.png';page.screenshot(path=str(f));frames.append(f)
    page.evaluate('footholdDeck.show(3,1)');page.wait_for_timeout(1000)
    rect=page.locator('.slide.active .terrain-world').bounding_box()
    page.keyboard.press('ArrowRight');page.wait_for_timeout(100)
    assert page.locator('.scene-traveler').count()==0
    assert page.locator('.slide.active .terrain-world').bounding_box()==rect
    checks['terrain_background_fixed']=True
    headers=[]
    for i in range(2,12):
        page.evaluate('(i)=>footholdDeck.show(i,0)',i)
        headers.append(page.locator('.slide.active header').bounding_box())
    assert all(x==headers[0] for x in headers)
    checks['header_coordinates_identical']=headers[0]
    page.evaluate('footholdDeck.show(5,0)')
    assert page.locator('.slide.active .industry-connections [data-step]').evaluate_all('(xs)=>xs.every(x=>Number(getComputedStyle(x).opacity)===0)')
    checks['industry_initial_lines_hidden']=True
    page.evaluate('footholdDeck.show(10,3)');page.keyboard.press('ArrowLeft');assert page.evaluate('footholdDeck.state.step')==2
    assert page.locator('.slide.active .critic-block').evaluate('(x)=>getComputedStyle(x.parentElement).visibility')=='hidden'
    checks['technical_reverse']=True
    page.evaluate('footholdDeck.show(10,0)');page.wait_for_timeout(900);page.keyboard.press('ArrowLeft');page.wait_for_timeout(300)
    assert page.evaluate('footholdDeck.state.step')==5
    assert page.locator('.scene-traveler').count()==0
    checks['reverse_to_animated_model_no_duplicate']=True
    page.evaluate('footholdDeck.show(11,1)');page.wait_for_timeout(1000)
    assert page.locator('.army-caption h3').evaluate('(el)=>getComputedStyle(el).display')=='none'
    assert page.locator('.army-render-note').evaluate('(el)=>Number(getComputedStyle(el).opacity)')==1
    checks['parallel_preview_does_not_claim_one_environment']=True
    for w,h in [(1280,720),(1366,768),(1920,1080)]:
        page.set_viewport_size({'width':w,'height':h});page.wait_for_timeout(100)
        for i in range(2,12):
            page.evaluate('(i)=>footholdDeck.show(i,0)',i)
            r=page.locator('.slide.active').bounding_box()
            assert r['x']>=-1 and r['y']>=-1 and r['x']+r['width']<=w+1 and r['y']+r['height']<=h+1
    checks['viewport_bounds']=True
    page.set_viewport_size({'width':1600,'height':900});page.evaluate('footholdDeck.show(0)')
    with page.expect_popup() as pop:page.keyboard.press('p')
    note=pop.value;note.wait_for_load_state();assert '아직은 어린 아기' in note.inner_text('body');note.close()
    checks['user_script_presenter']=True
    page.emulate_media(media='print')
    assert page.locator('.scan-print circle').count()==187
    assert page.locator('.scan-print').evaluate('(el)=>getComputedStyle(el).display')=='block'
    assert page.locator('.policy-robot').evaluate('(el)=>getComputedStyle(el).transform')=='none'
    checks['print_grid_independent_of_canvas_history']=True
    page.pdf(path=str(OUT/'FOOTHOLD-MVP-review.pdf'),print_background=True,prefer_css_page_size=True)
    browser.close()
for group in range((len(frames)+8)//9):
    subset=frames[group*9:group*9+9];sheet=Image.new('RGB',(1600,((len(subset)+2)//3)*320),'#d1d5d6');draw=ImageDraw.Draw(sheet)
    for j,f in enumerate(subset):
        x=j%3*533;y=j//3*320;sheet.paste(Image.open(f).resize((533,300)),(x,y+20));draw.text((x+10,y+3),f.stem,fill='#142b26')
    sheet.save(OUT/f'u205-contact-{group}.jpg')
for file in ['go2-front-alpha-v1.png','go2-pixel-alpha-v2.png']:
    im=Image.open(ROOT/'assets'/file);assert im.mode=='RGBA' and im.getextrema()[-1]==(0,255)
checks['real_alpha']=True
result={'html_sha256':hashlib.sha256((OUT/'FOOTHOLD-MVP-cover.html').read_bytes()).hexdigest(),'errors':errors,'checks':checks,'screenshots':[str(f.name) for f in frames]}
(OUT/'u205-qa.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps(result,ensure_ascii=False));assert not errors
