/* Same-page source comparison. Original artwork is never overwritten. */
const sourceSingles={O2:'opening-o2-overhead-v1',O7:'opening-o7-user-selected-reference',E1:'opening-o7-user-selected-reference',E2a:'ending-e2-mood-start-v6',E2:'ending-e2-mood-end-v6',E5pre:'ending-e5-step-v1',E5:'ending-e5a-climb-centered-v2',E5b:'ending-e5b-seated-front-v3'};
function originalPhotoStyle(id){
 if(sourceSingles[id])return `background-image:url('../assets/${sourceSingles[id]}.png');background-size:cover;background-position:center`;
 if(id==='E3'||id==='E4')return `background-image:url('../assets/ending-storyboard-v2.png');background-size:200% ${1330/328*100}%;background-position:${id==='E3'?0:100}% ${333/(1330-328)*100}%`;
 const panels={O1:['opening-storyboard-v6',0,1,375,1152],O3:['opening-storyboard-v3',100,1,375,1152],O3b:['opening-storyboard-v6',100,1,375,1152],O5:['opening-storyboard-v3',100,381,351,1152],O6:['opening-storyboard-v6',0,757,393,1152]};
 if(panels[id]){const [file,x,t,h,full]=panels[id];return `background-image:url('../assets/${file}.png');background-size:200% ${full/h*100}%;background-position:${x}% ${t/(full-h)*100}%`;}
 const entry=all.find(x=>x.d[0]===id);return entry?.fig.dataset.currentPhoto||entry?.fig.querySelector('.photo').getAttribute('style')||'';
}
function reviewButtons(n){return `<button data-review-index="${n}" data-review-version="current">현재 시안</button><button data-review-index="${n}" data-review-version="original">원래 원화</button>`;}
function showReview(n,version){
 show(n);
 const original=version==='original';const {d}=all[current];
 if(original){
  document.querySelector('.modal-frame .photo').setAttribute('style',originalPhotoStyle(d[0]));
  document.querySelector('.modal-frame').querySelectorAll('.hud').forEach(x=>x.remove());
 }else document.querySelector('.modal-frame .photo').setAttribute('style',all[current].fig.dataset.currentPhoto);
 document.querySelector('#modalTitle').textContent=d[0]+' · '+(original?'원래 원화':'현재 시안');
 document.querySelector('#modalCopy').textContent=original?'구도·지형 비교용 보존 원화입니다. 원화의 광택·HDR 표현까지 유지하라는 의미는 아닙니다.':d[2];
 document.querySelector('#modalMediaActions').innerHTML=reviewButtons(current)+mediaButtons(d[0],current);
 document.querySelectorAll('#modalMediaActions [data-review-version]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.reviewVersion===version)));
}
for(let n=0;n<all.length;n++){
 const {fig,d}=all[n];if(['O4','Q1'].includes(d[0]))continue;
 fig.dataset.currentPhoto=fig.querySelector('.photo').getAttribute('style');
 fig.querySelector('.frame').insertAdjacentHTML('afterend',`<div class="extra image-review-actions" style="margin-top:8px">${reviewButtons(n)}</div>`);
}
document.addEventListener('click',e=>{
 const b=e.target.closest('[data-review-index]');if(!b)return;
 const n=Number(b.dataset.reviewIndex),version=b.dataset.reviewVersion;
 if(b.closest('#viewer')){showReview(n,version);return;}
 const {fig,d}=all[n];
 fig.querySelector('.photo').setAttribute('style',version==='original'?originalPhotoStyle(d[0]):fig.dataset.currentPhoto);
 fig.querySelectorAll('.hud').forEach(x=>x.style.visibility=version==='original'?'hidden':'');
 fig.querySelectorAll('[data-review-version]').forEach(x=>x.setAttribute('aria-pressed',String(x.dataset.reviewVersion===version)));
});
const sittingReview=all.find(x=>x.d[0]==='E5b');
if(sittingReview){
 sittingReview.fig.querySelector('.image-review-actions').insertAdjacentHTML('beforeend','<button data-e5b-standing>서 있는 시작 후보</button>');
 document.querySelector('[data-e5b-standing]').onclick=()=>{
  sittingReview.fig.querySelector('.photo').setAttribute('style',"background-image:url('../assets/ending-e5b-standing-sunburst-v1.png');background-size:cover;background-position:center");
  sittingReview.fig.querySelectorAll('[data-review-version]').forEach(x=>x.setAttribute('aria-pressed','false'));
 };
}
