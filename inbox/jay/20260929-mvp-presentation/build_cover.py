"""Build a self-contained single-slide cover for review, leaving the old deck intact."""
from pathlib import Path
import base64
import re

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
OUT = HERE / 'output'
OUT.mkdir(exist_ok=True)
font = re.search(r'@font-face\{[^}]+\}', (ROOT / 'deliverables/plan/proposal-deck-presented.html').read_text(encoding='utf-8')).group()
def data(path, mime):
    return 'data:' + mime + ';base64,' + base64.b64encode(path.read_bytes()).decode()
bg = data(HERE / 'assets/cover-go2-terrain-v1.png', 'image/png')
wordmark = data(ROOT / 'web/assets/brand/foothold-wordmark-reverse.svg', 'image/svg+xml')
symbol = data(ROOT / 'web/assets/brand/foothold-symbol-brand.svg', 'image/svg+xml')
lockup = data(HERE / 'assets/foothold-lockup-compact-dark.svg', 'image/svg+xml')
system = (HERE/'design/presentation.css').read_text(encoding='utf-8')
page = '''<!doctype html>
<html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>FOOTHOLD · MVP 발표 표지</title><style>
__FONT__
__SYSTEM__
:root{color-scheme:dark;--paper:var(--p-dark-ink);--teal:var(--p-dark-brand)}
*{box-sizing:border-box}body{margin:0;background:#050b10;color:var(--paper);font-family:var(--p-font);overflow:hidden}
[hidden]{display:none!important}#viewport{position:fixed;inset:0;display:grid;place-items:center}
#slide{position:relative;width:1600px;height:900px;flex-shrink:0;overflow:hidden;transform:scale(var(--scale,1));background:#0b1822}
.scene{position:absolute;inset:0;width:100%;height:100%;object-fit:cover}
.shade{position:absolute;inset:0;background:linear-gradient(90deg,rgba(5,15,22,.54) 0%,rgba(5,15,22,.26) 41%,transparent 65%),linear-gradient(0deg,rgba(4,12,18,.92),transparent 24%)}
.identity{position:absolute;left:64px;top:64px;display:flex;align-items:center;gap:18px}.symbol{width:39px;height:45px}.wordmark{width:232px;height:auto}
.edition{position:absolute;right:64px;top:70px;font-size:19px;letter-spacing:.02em;color:#e9e7e1}.edition span{margin-left:24px;color:var(--p-dark-muted)}
.heading{position:absolute;left:64px;top:244px}.platform{font-size:26px;font-weight:500;letter-spacing:.04em;color:var(--p-dark-brand);margin:0 0 24px}
h1{font-size:var(--p-cover);line-height:1.15;font-weight:750;letter-spacing:-.047em;margin:0;text-wrap:nowrap}
.project{font-size:22px;line-height:1.6;color:var(--p-dark-ink);margin:30px 0 0}
.people{position:absolute;left:64px;bottom:64px;font-size:20px;line-height:1.8;color:#e9e7e1}.people small{font-size:18px;color:var(--p-dark-muted);display:block}.affiliation{position:absolute;right:64px;bottom:64px;font-size:18px;line-height:1.8;color:var(--p-dark-muted)}
.enter .scene{animation:scene-in var(--p-motion-cover) ease-out both}.enter .identity,.enter .edition,.enter .people,.enter .affiliation{animation:appear .8s .1s both}.enter .heading{animation:rise 1s .15s both}
@keyframes scene-in{from{opacity:.3;transform:scale(1.025)}to{opacity:1;transform:scale(1)}}@keyframes appear{from{opacity:0}to{opacity:1}}@keyframes rise{from{opacity:0;transform:translateY(15px)}to{opacity:1;transform:translateY(0)}}
#controls{position:fixed;bottom:9px;left:50%;transform:translateX(-50%);display:flex;gap:6px;padding:5px;border-radius:7px;background:#07131cf0;opacity:0;transition:opacity .2s}body.controls #controls,#controls:focus-within{opacity:1}button{background:none;border:1px solid #52747b;color:#e9e7e1;padding:8px 12px;border-radius:4px;cursor:pointer;font:14px Pretendard,sans-serif}button:focus-visible{outline:2px solid #9cd7cb;outline-offset:3px}
#notes{position:fixed;right:22px;top:22px;bottom:22px;width:min(540px,calc(100vw - 44px));padding:32px;background:#0b202b;border:1px solid #52747b;overflow:auto;box-shadow:0 12px 48px #0009;line-height:1.7;font-size:18px}#notes[data-side="left"]{left:22px;right:auto}#notes h2{font-size:23px;margin-top:0}#notes h3{font-size:18px;color:var(--p-dark-brand);margin-top:26px}#notes p{margin:12px 0}.note-actions{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:24px}.note-help{font-size:14px;color:var(--p-dark-muted)}#blank{position:fixed;inset:0;background:black;z-index:10}
@media(prefers-reduced-motion:reduce){*,*::before,*::after{animation:none!important;transition:none!important}}
@media print{@page{size:1600px 900px;margin:0}body{width:1600px;height:900px}#viewport{position:static;display:block}#slide{transform:none!important}#controls,#notes,#blank{display:none!important}*{animation:none!important;-webkit-print-color-adjust:exact;print-color-adjust:exact}}
</style></head><body>
<main id="viewport"><section id="slide" class="enter" aria-label="FOOTHOLD MVP 발표 표지">
<img class="scene" src="__BG__" alt="어두운 산업 공간의 갈라진 바닥 앞에 서 있는 Go2. AI 생성 콘셉트 이미지."><div class="shade"></div>
<div class="identity"><img style="width:280px;height:auto" src="__LOCKUP__" alt="FOOTHOLD"></div>
<div class="edition">MVP 중간발표 · 인공지능사관학교 7기 AI Physical</div>
<div class="heading"><p class="platform">Unitree Go2</p><h1>미경험 험지<br>적응 정책</h1><p class="project">Unitree Go2 미경험 험지 적응 시뮬레이션 및<br>실기 자율주행 프로젝트</p></div>
<div class="people">실증2팀 · FOOTHOLD<span style="margin-left:24px">발표 오흥재</span><small>팀원 맹라현 · 오현민 · 이민우 · 임석헌</small></div>


</section></main>
<nav id="controls" aria-label="발표 조작"><button id="fullscreen">F 전체화면</button><button id="noteButton">N 발표자 메모</button><button id="presenterButton">P 메모 별도 창</button><button id="replay">R 다시 보기</button></nav>
<aside id="notes" hidden><div class="note-actions"><button id="noteSide">왼쪽으로</button><button id="detachNotes">별도 창으로</button><button id="closeNotes">닫기</button></div><div id="notesContent"><h2>표지 · 발표자 메모</h2><h3>인사 초안</h3><p>안녕하세요. Unitree Go2의 미경험 험지 적응 정책을 연구하는 FOOTHOLD 팀장 오흥재입니다.</p><p>저는 이번 프로젝트를 하면서, 사족보행 로봇이 익숙한 곳에서 한 걸음을 배워도 낯선 바닥에서는 다시 넘어진다는 게, 마치 아기가 걸음마를 배우는 모습과 비슷하게 느껴졌습니다.</p><p>세상에 나가 넘어지고, 다시 일어나면서 배우는 거죠. 그만큼 쉽지 않은 도전이라고 해야 할까요?</p><p>오늘은 저희가 그 실패를 보면서 어떻게 한 걸음을 내디뎠는지 말씀드리고자 합니다.</p><h3>다음 장면과의 연결</h3><p>인사가 끝나면 오프닝 영상으로 전환합니다. 어둠과 연기, 탐색광, 멀리 붉은 목표 점등, 임무 HUD, Go2의 등장으로 이어지고 첫 디딤에서 멈춥니다.</p><p>그때 “그럼 우리 FOOTHOLD 프로젝트의 첫걸음을 함께 시작하겠습니다.”라고 말한 뒤 미경험 험지 소개로 넘어갑니다.</p><h3>이번 파일의 범위</h3><p>표지 한 장입니다. 오프닝 영상과 다음 장면은 아직 연결하지 않았습니다. 멘트는 사용자가 제시한 의도를 바탕으로 다듬은 제안입니다. 배경은 실제 실험 결과가 아닌 생성 콘셉트 이미지입니다.</p></div><p class="note-help" id="noteStatus" role="status">별도 창은 제목 표시줄을 끌어 다른 모니터로 옮길 수 있습니다.</p></aside><div id="blank" hidden></div>
<script>
const slide=document.getElementById('slide'),notes=document.getElementById('notes'),blank=document.getElementById('blank');
function fit(){document.documentElement.style.setProperty('--scale',Math.min(innerWidth/1600,innerHeight/900))}fit();addEventListener('resize',fit);
function replay(){slide.classList.remove('enter');void slide.offsetWidth;slide.classList.add('enter')}
async function fullscreen(){try{if(document.fullscreenElement)await document.exitFullscreen();else await document.documentElement.requestFullscreen()}catch(e){document.body.classList.add('controls')}}
document.getElementById('fullscreen').onclick=fullscreen;document.getElementById('noteButton').onclick=()=>notes.hidden=!notes.hidden;document.getElementById('closeNotes').onclick=()=>notes.hidden=true;document.getElementById('replay').onclick=replay;
document.getElementById('noteSide').onclick=()=>{const left=notes.dataset.side!=='left';notes.dataset.side=left?'left':'right';document.getElementById('noteSide').textContent=left?'오른쪽으로':'왼쪽으로'};
let presenterWindow=null;
function syncPresenter(){if(presenterWindow&&!presenterWindow.closed){const target=presenterWindow.document.getElementById('presenterContent');if(target)target.innerHTML=document.getElementById('notesContent').innerHTML}}
function openPresenter(){
 if(presenterWindow&&!presenterWindow.closed){syncPresenter();presenterWindow.focus();notes.hidden=true;return}
 presenterWindow=window.open('','footholdPresenter','popup=yes,width=680,height=840,resizable=yes,scrollbars=yes');
 if(!presenterWindow){notes.hidden=false;document.getElementById('noteStatus').textContent='브라우저에서 팝업을 허용한 뒤 별도 창으로 버튼을 다시 눌러 주세요.';return}
 const doc=presenterWindow.document;doc.title='FOOTHOLD · 발표자 메모';doc.documentElement.lang='ko';doc.head.replaceChildren();doc.body.replaceChildren();
 const title=doc.createElement('title');title.textContent='FOOTHOLD · 발표자 메모';doc.head.append(title);
 const style=doc.createElement('style');style.textContent=document.querySelector('style').textContent+'body{overflow:auto;background:#12161d;padding:28px;color:#e9e7e1;font-family:var(--p-font);font-size:var(--note-font,22px);line-height:1.75}header{position:sticky;top:0;background:#12161d;padding:8px 0 20px;display:flex;gap:10px;align-items:center;flex-wrap:wrap}header span{font-size:14px;color:#adb5c1}h2{font-size:26px}h3{font-size:20px;color:#3ec7b4;margin-top:32px}p{margin:18px 0}';doc.head.append(style);
 const header=doc.createElement('header');const tip=doc.createElement('span');tip.textContent='이 창을 다른 모니터로 옮겨 두세요.';header.append(tip);
 let size=22;for(const [label,delta] of [['글자 작게',-2],['글자 크게',2]]){const button=doc.createElement('button');button.textContent=label;button.onclick=()=>{size=Math.max(16,Math.min(36,size+delta));doc.body.style.setProperty('--note-font',size+'px')};header.append(button)}
 const content=doc.createElement('main');content.id='presenterContent';doc.body.append(header,content);syncPresenter();notes.hidden=true;presenterWindow.focus();
 presenterWindow.addEventListener('keydown',e=>{if(e.key==='Escape')presenterWindow.close()});
}
document.getElementById('presenterButton').onclick=openPresenter;document.getElementById('detachNotes').onclick=openPresenter;
new MutationObserver(syncPresenter).observe(document.getElementById('notesContent'),{childList:true,subtree:true,characterData:true});
addEventListener('keydown',e=>{if(e.ctrlKey||e.metaKey||e.altKey)return;const k=e.key.toLowerCase();if(k==='f'){e.preventDefault();fullscreen()}if(k==='n')notes.hidden=!notes.hidden;if(k==='p'){e.preventDefault();openPresenter()}if(k==='r')replay();if(k==='b')blank.hidden=!blank.hidden;if(k==='escape'){notes.hidden=true;blank.hidden=true}});blank.onclick=()=>blank.hidden=true;
let timer;addEventListener('pointermove',()=>{document.body.classList.add('controls');clearTimeout(timer);timer=setTimeout(()=>document.body.classList.remove('controls'),1700)});
</script></body></html>'''
page = page.replace('__FONT__',font).replace('__SYSTEM__',system).replace('__LOCKUP__',lockup).replace('__BG__',bg).replace('__SYMBOL__',symbol).replace('__WORDMARK__',wordmark)
assert '\u2014' not in page
(OUT/'FOOTHOLD-MVP-cover.html').write_text(page,encoding='utf-8')
print(OUT/'FOOTHOLD-MVP-cover.html')
