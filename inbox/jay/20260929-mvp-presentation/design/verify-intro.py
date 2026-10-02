"""Verify the U202 narrative, click states, shared scene transitions and print output."""
from pathlib import Path
import sys,json,hashlib
sys.path.insert(0,str(Path.home()/'AppData/Local/Temp/foothold-mvp-render-deps'))
from playwright.sync_api import sync_playwright
from PIL import Image,ImageDraw
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'output'
errors=[];issues=[];frames=[]
with sync_playwright() as pw:
    browser=pw.chromium.launch(executable_path=r'C:\Program Files\Google\Chrome\Application\chrome.exe',headless=True,args=['--allow-file-access-from-files'])
    page=browser.new_page(viewport={'width':1600,'height':900},device_scale_factor=1)
    page.on('pageerror',lambda e:errors.append(str(e)))
    page.goto((OUT/'FOOTHOLD-MVP-cover.html').as_uri()+'#slide-5');page.wait_for_timeout(1500)
    assert page.evaluate('footholdDeck.state.current')==4
    titles=page.evaluate('deckMeta.map(x=>x.title)')
    assert titles[1:10]==['우리가 향하는 곳','왜, 잘 걷는 로봇인가?','이 길을 건너, 점검 지점까지 가려면?','미경험 험지란 무엇일까요?','위험한 곳에 먼저 가고, 반복 점검을 맡습니다','로봇은 점검을, 사람은 수리와 예방정비를','같은 임무라도, 길에 따라 이동 방식이 달라집니다','발을 옮겨, 지지점을 바꾸는 이동에 주목했습니다','오늘의 이야기를 함께할 Unitree Go2입니다']
    page.evaluate('footholdDeck.show(2,0)');page.keyboard.press('ArrowRight');assert page.evaluate('footholdDeck.state.step')==1
    page.keyboard.press('ArrowLeft');assert page.evaluate('footholdDeck.state.step')==0
    page.evaluate('footholdDeck.show(7,1)');page.evaluate('footholdDeck.show(8,0)');page.wait_for_timeout(100)
    assert page.locator('.scene-traveler').count()>0
    page.evaluate('footholdDeck.show(7,1)');page.wait_for_timeout(1000)
    assert page.locator('.scene-traveler').count()==0
    assert page.locator('.slide.active [data-shared="go2"]').evaluate('(x)=>getComputedStyle(x).visibility')=='visible'
    new_indices=list(range(10))+[titles.index('FOOTHOLD가 추구하는 가치'),titles.index('Find the next foothold.')]
    for i in new_indices:
        page.evaluate('(i)=>footholdDeck.show(i,Number(document.querySelectorAll(".slide")[i].dataset.steps||0))',i);page.wait_for_timeout(1000)
        if i==9:page.wait_for_function("document.querySelector('.slide.active .go2-model').go2Player.frame===240",timeout=20000)
        missing=page.locator('.slide.active img').evaluate_all('(xs)=>xs.filter(x=>!x.complete||!x.naturalWidth).map(x=>x.src)')
        if missing:issues.append({'slide':i+1,'missing':missing})
        frame=OUT/f'intro-review-{i+1:02}.png';page.screenshot(path=str(frame));frames.append(frame)
    viewport_checks=[]
    for width,height in [(1280,720),(1366,768),(1920,1080)]:
        page.set_viewport_size({'width':width,'height':height})
        for i in new_indices:
            page.evaluate('(i)=>footholdDeck.show(i,Number(document.querySelectorAll(".slide")[i].dataset.steps||0))',i)
            page.wait_for_timeout(70)
            rect=page.locator('.slide.active').bounding_box()
            assert rect['x']>=-1 and rect['y']>=-1 and rect['x']+rect['width']<=width+1 and rect['y']+rect['height']<=height+1,(width,height,i,rect)
            if i in [3,4]:assert page.locator('.slide.active .route').is_visible()
        viewport_checks.append({'width':width,'height':height,'slides':'passed'})
    page.set_viewport_size({'width':1600,'height':900})
    page.evaluate('footholdDeck.show(0)')
    with page.expect_popup() as pop:page.keyboard.press('p')
    notes=pop.value;notes.wait_for_load_state();assert 'Isaac Sim에서 학습한 내용' in notes.inner_text('body');notes.close()
    media=page.evaluate('''async()=>{const vs=[...document.querySelectorAll('video')].filter(v=>/film-master-v8|FULL_v6/.test(v.src));return Promise.all(vs.map(v=>new Promise(resolve=>{if(v.readyState)resolve({src:v.getAttribute('src'),duration:v.duration});else{v.onloadedmetadata=()=>resolve({src:v.getAttribute('src'),duration:v.duration});v.onerror=()=>resolve({src:v.src,error:true});v.load()}})))}''')
    page.emulate_media(media='print');page.pdf(path=str(OUT/'FOOTHOLD-MVP-review.pdf'),print_background=True,prefer_css_page_size=True)
    browser.close()
sheet=Image.new('RGB',(1600,((len(frames)+2)//3)*325),'#d8dbdc');draw=ImageDraw.Draw(sheet)
for j,f in enumerate(frames):
    x=j%3*533;y=j//3*325;sheet.paste(Image.open(f).resize((533,300)),(x,y+25));draw.text((x+10,y+6),f.stem,fill='#18212b')
sheet.save(OUT/'intro-review-contact.jpg',quality=90)
result={'html_sha256':hashlib.sha256((OUT/'FOOTHOLD-MVP-cover.html').read_bytes()).hexdigest(),'viewport_checks':viewport_checks,'errors':errors,'issues':issues,'media':media,'story_sequence':'passed','click_forward_backward':'passed','rapid_reverse_shared_transition':'passed','presenter_notes':'passed','reviewed_slides':[x+1 for x in new_indices]}
(OUT/'intro-qa.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8');print(json.dumps(result,ensure_ascii=False))
assert not errors and not issues
