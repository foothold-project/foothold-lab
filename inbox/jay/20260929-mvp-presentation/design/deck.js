const slides=[...document.querySelectorAll('.slide')];
let current=0,step=0,presenterWindow=null,started=Date.now();
function fit(){document.documentElement.style.setProperty('--scale',Math.min(innerWidth/1600,innerHeight/900))}fit();addEventListener('resize',fit);
function show(index,atStep=0){
 const oldIndex=current;const oldShared=typeof captureShared==='function'?captureShared(slides[current]):[];
 current=Math.max(0,Math.min(slides.length-1,index));step=atStep;
 slides.forEach((s,i)=>{s.classList.toggle('active',i===current);if(i!==current)s.querySelectorAll('video').forEach(v=>v.pause())});
 slides[current].querySelectorAll('[data-step]').forEach(el=>el.classList.toggle('pending',Number(el.dataset.step)>step));
 if(typeof renderStoryState==='function')renderStoryState(slides[current],step);
 if(oldIndex!==current&&typeof animateShared==='function')animateShared(oldShared,slides[current]);
 if(oldIndex!==current)slides[current].querySelectorAll('video[data-autoplay],video[autoplay]').forEach(v=>{v.currentTime=0;v.play().catch(()=>{v.controls=true})});
 document.querySelector('#counter').textContent=`${current+1} / ${slides.length}`;
 document.querySelector('#notesContent').innerHTML=deckNotes[current];
 history.replaceState(null,'','#slide-'+(current+1));syncPresenter();
}
function next(){const max=Number(slides[current].dataset.steps||0);if(step<max)show(current,step+1);else show(current+1)}
function prev(){if(step>0)show(current,step-1);else {const j=Math.max(0,current-1);show(j,Number(slides[j].dataset.steps||0))}}
function toggleNotes(){document.querySelector('#notes').hidden=!document.querySelector('#notes').hidden}
function toggleTOC(){document.querySelector('#toc').hidden=!document.querySelector('#toc').hidden}
async function fullscreen(){try{if(document.fullscreenElement)await document.exitFullscreen();else await document.documentElement.requestFullscreen()}catch(e){}}
function playVideos(){const vs=[...slides[current].querySelectorAll('video')];const playing=vs.some(v=>!v.paused);vs.forEach(v=>{if(playing)v.pause();else {if(v.ended)v.currentTime=0;v.play().catch(()=>{})}})}
function restartVideos(){slides[current].querySelectorAll('video').forEach(v=>{v.currentTime=0;v.pause()})}
function syncPresenter(){if(presenterWindow&&!presenterWindow.closed){presenterWindow.document.querySelector('#presenterContent').innerHTML=deckNotes[current];presenterWindow.document.querySelector('#position').textContent=`${current+1} / ${slides.length} · ${deckMeta[current].section}`;presenterWindow.document.querySelector('#nextTitle').textContent=deckMeta[current+1]?'다음: '+deckMeta[current+1].title:'발표 끝'}}
function openPresenter(){
 if(presenterWindow&&!presenterWindow.closed){syncPresenter();presenterWindow.focus();return}
 presenterWindow=window.open('','footholdPresenter','popup=yes,width=720,height=850,resizable=yes,scrollbars=yes');
 if(!presenterWindow){document.querySelector('#notes').hidden=false;return}
 const d=presenterWindow.document;d.head.innerHTML='<meta charset="utf-8"><title>FOOTHOLD · 발표자 메모</title>';d.body.replaceChildren();
 const style=d.createElement('style');style.textContent='body{font-family:Pretendard,Malgun Gothic,sans-serif;background:#12161d;color:#e9e7e1;padding:28px;font-size:22px;line-height:1.75}h2{font-size:26px}h3,a{color:#70d3c3}button{padding:10px;background:#20353f;color:#e9e7e1;border:1px solid #62848d;cursor:pointer}header{position:sticky;top:0;background:#12161d;padding:12px 0;display:flex;gap:12px}#position,#nextTitle{font-size:17px;color:#bdc8cb}';d.head.append(style);
 d.body.innerHTML='<p id="position"></p><header><button id="prev">← 이전</button><button id="next">다음 →</button><button id="play">영상 재생·정지</button><button id="size">글자 크기</button></header><main id="presenterContent"></main><p id="nextTitle"></p>';
 d.querySelector('#prev').onclick=prev;d.querySelector('#next').onclick=next;d.querySelector('#play').onclick=playVideos;
 let size=22;d.querySelector('#size').onclick=()=>{size=size===28?18:size+2;d.body.style.fontSize=size+'px'};
 presenterWindow.addEventListener('keydown',e=>{if(['ArrowRight','PageDown',' '].includes(e.key)){e.preventDefault();next()}if(['ArrowLeft','PageUp'].includes(e.key)){e.preventDefault();prev()}});
 syncPresenter();document.querySelector('#notes').hidden=true;
}
slides.forEach(s=>s.querySelectorAll('video').forEach(v=>{if(v.poster){const img=document.createElement('img');img.src=v.poster;img.className='print-poster';img.alt=v.closest('figure')?.querySelector('figcaption')?.textContent||s.getAttribute('aria-label');v.after(img)}}));
deckMeta.forEach((m,i)=>{const b=document.createElement('button');const n=document.createElement('b');n.textContent=String(i+1).padStart(2,'0');b.append(n,document.createTextNode(m.title));b.onclick=()=>{show(i);document.querySelector('#toc').hidden=true};document.querySelector('#tocItems').append(b)});
addEventListener('keydown',e=>{if(e.ctrlKey||e.metaKey||e.altKey||/input|textarea|select/i.test(e.target.tagName))return;const k=e.key.toLowerCase();if(['arrowright','pagedown',' '].includes(k)){e.preventDefault();next()}else if(['arrowleft','pageup'].includes(k)){e.preventDefault();prev()}else if(k==='home')show(0);else if(k==='end')show(slides.length-1);else if(k==='f')fullscreen();else if(k==='n')toggleNotes();else if(k==='p')openPresenter();else if(k==='v')playVideos();else if(k==='r'){restartVideos();show(current,0)}else if(k==='t')toggleTOC();else if(k==='b')document.querySelector('#blank').hidden=!document.querySelector('#blank').hidden;else if(k==='escape'){document.querySelector('#blank').hidden=true;document.querySelector('#notes').hidden=true;document.querySelector('#toc').hidden=true}});
document.querySelector('#blank').onclick=()=>document.querySelector('#blank').hidden=true;
let controlTimer;addEventListener('pointermove',()=>{document.body.classList.add('controls');clearTimeout(controlTimer);controlTimer=setTimeout(()=>document.body.classList.remove('controls'),1800)});
const initial=Number(location.hash.replace('#slide-',''))-1;queueMicrotask(()=>show(Number.isFinite(initial)&&initial>=0?initial:0));
window.footholdDeck={show,next,prev,get state(){return {current,step,count:slides.length}}};
