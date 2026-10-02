"""Render all slides, verify media and navigation, export a static PDF review."""
from pathlib import Path
import sys,json,re
sys.path.insert(0,str(Path.home()/'AppData/Local/Temp/foothold-mvp-render-deps'))
from playwright.sync_api import sync_playwright
from PIL import Image,ImageDraw
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'output'
errors=[];issues=[];frames=[]
manifest=json.loads((ROOT/'PPT-BUILD-MANIFEST.json').read_text(encoding='utf-8'))
titles=[s['title'] for s in manifest['slides']]
story_chain=[
 '왜, 잘 걷는 로봇인가?',
 '이 길을 건너, 점검 지점까지 가려면?',
 '미경험 험지란 무엇일까요?',
 '위험한 곳에 먼저 가고, 반복 점검을 맡습니다',
 '로봇은 점검을, 사람은 수리와 예방정비를',
 '같은 임무라도, 길에 따라 이동 방식이 달라집니다',
 '발을 옮겨, 지지점을 바꾸는 이동에 주목했습니다',
 '오늘의 이야기를 함께할 Unitree Go2입니다',
 '이 로봇은 어떤 정보를 얻을 수 있을까요?',
 '시뮬레이션 속 Go2가 받는 정보입니다',
 '관측이 들어오면 12개 관절 목표가 나옵니다',
 '신경망의 출력은 다시 이 로봇의 한 걸음이 됩니다',
 '학습에서는 critic이 행동의 결과를 평가하도록 돕습니다',
 '한 대의 경험을, 4,096개 환경에서 함께 모읍니다',
 '무엇을 더 가르칠지, 실패에서 찾았습니다',
 '실패 지형을 나누고, 먼저 시도할 과제를 골랐습니다',
 '틈을 만나게 하고, 바닥이 없다는 입력도 바로잡았습니다',
]
start=titles.index(story_chain[0])
assert titles[start:start+len(story_chain)]==story_chain,'User narrative sequence was interrupted'
assert titles.index('세 작업은 프로젝트 끝까지 함께 이어집니다')>titles.index('디딤돌에서는 평가 시드에 따라 성공률이 흔들렸습니다')
with sync_playwright() as pw:
    browser=pw.chromium.launch(executable_path=r'C:\Program Files\Google\Chrome\Application\chrome.exe',headless=True,args=['--allow-file-access-from-files'])
    page=browser.new_page(viewport={'width':1600,'height':900},device_scale_factor=1)
    page.on('pageerror',lambda e:errors.append(str(e)))
    page.goto((OUT/'FOOTHOLD-MVP-cover.html').as_uri());page.wait_for_timeout(1800)
    count=page.locator('.slide').count()
    for i in range(count):
        page.evaluate('(i)=>footholdDeck.show(i,99)',i);page.wait_for_timeout(950)
        result=page.evaluate('''()=>{const s=document.querySelector('.slide.active'),c=s.querySelector('.content');return {title:s.getAttribute('aria-label'),missing:[...s.querySelectorAll('img')].filter(x=>!x.complete||x.naturalWidth===0).map(x=>x.getAttribute('src')),overflow:c?[...c.querySelectorAll('p,h3,table,figure,.flow,.network,.callout,.bars,.agenda,.timeline')].filter(x=>{const b=x.getBoundingClientRect(),a=c.getBoundingClientRect();return b.height>0&&(b.bottom>a.bottom+10||b.right>a.right+5)}).map(x=>({tag:x.tagName,text:x.textContent.slice(0,100)})):[]}}''')
        if result['missing'] or result['overflow']:issues.append({'slide':i+1,**result})
        f=OUT/f'deck-review-{i+1:02}.png';page.screenshot(path=str(f));frames.append(f)
    page.evaluate('footholdDeck.show(0)');page.keyboard.press('ArrowRight');assert page.evaluate('footholdDeck.state.current')==1
    page.keyboard.press('ArrowLeft');assert page.evaluate('footholdDeck.state.current')==0
    page.keyboard.press('n');assert page.locator('#notes').is_visible();page.keyboard.press('n')
    with page.expect_popup() as popup:page.keyboard.press('p')
    notes=popup.value;notes.wait_for_load_state();notes.locator('#next').click();assert page.evaluate('footholdDeck.state.current')==1;notes.close()
    page.keyboard.press('b');assert page.locator('#blank').is_visible();page.keyboard.press('b')
    media=page.evaluate('''async()=>{const vs=[...document.querySelectorAll('video')];const out=[];for(const v of vs){v.preload='metadata';const r=await Promise.race([new Promise(r=>{if(v.readyState>=1)r({ok:true,duration:v.duration});else{v.onloadedmetadata=()=>r({ok:true,duration:v.duration});v.onerror=()=>r({ok:false,error:v.error?.message});v.load()}}),new Promise(r=>setTimeout(()=>r({ok:false,error:'timeout'}),8000))]);out.push({src:v.getAttribute('src'),...r})}return out}''')
    page.emulate_media(media='print');page.pdf(path=str(OUT/'FOOTHOLD-MVP-review.pdf'),print_background=True,prefer_css_page_size=True)
    browser.close()
for start in range(0,len(frames),12):
    group=frames[start:start+12];sheet=Image.new('RGB',(1200,round((len(group)+2)//3*249)), '#d8dbdc');d=ImageDraw.Draw(sheet)
    for j,f in enumerate(group):
        x=j%3*400;y=j//3*249;sheet.paste(Image.open(f).resize((400,225)),(x,y+24));d.text((x+8,y+5),f'Slide {start+j+1}',fill='#18212b')
    sheet.save(OUT/f'deck-contact-{start//12+1}.jpg',quality=88)
result={'slides':count,'errors':errors,'issues':issues,'media':media,'navigation':'passed','notes_popup':'passed','blackout':'passed','narrative_order':'passed; U202 intro and retained research body'}
(OUT/'deck-qa.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(result,ensure_ascii=False,indent=2))
