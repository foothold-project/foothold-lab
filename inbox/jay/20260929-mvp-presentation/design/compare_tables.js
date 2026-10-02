/* 실험 영상 비교표 (compare-page) · 2026-10-02
   행(.cmp-row)을 누르면 그 행 세 영상이 포스터 자리에서 같이 재생되고 다른 행은 멈춘다.
   같은 행을 다시 누르면 멈추고 포스터로 돌아간다. 전역에는 아무것도 남기지 않는다. */
(function(){
 const ROW='.cmp-row';
 function stop(row){row.classList.remove('on');row.querySelectorAll('video').forEach(v=>{v.pause();v.classList.remove('live');});}
 function stopAll(page,except){page.querySelectorAll(ROW+'.on').forEach(r=>{if(r!==except)stop(r);});}
 function start(row){
  row.classList.add('on');
  row.querySelectorAll('video').forEach(v=>{v.muted=true;v.currentTime=0;v.play().catch(()=>{});});
 }
 document.addEventListener('click',e=>{
  const row=e.target.closest(ROW);if(!row)return;
  const page=row.closest('.compare-page');if(!page)return;
  if(row.classList.contains('on')){stop(row);return;}
  stopAll(page,row);start(row);
 });
 // 영상이 실제로 그려지기 시작한 뒤에 포스터 위로 올린다 (검은 첫 화면 없음)
 document.addEventListener('playing',e=>{const v=e.target;if(v.tagName==='VIDEO'&&v.closest(ROW+'.on'))v.classList.add('live');},true);
 // V 키(playVideos)가 18 개를 한꺼번에 틀면 켜진 행만 남긴다 (노트북 보호)
 document.addEventListener('play',e=>{const v=e.target;if(v.tagName!=='VIDEO')return;const row=v.closest(ROW);if(row&&!row.classList.contains('on'))v.pause();},true);
 // 팀장 2026-10-02 (진짜 마지막): 장에 들어오면 한 슬라이드의 모든 영상(행 전부)을 한꺼번에 재생한다.
 function autoRow(page){
  if(!page.classList.contains('active'))return;
  page.querySelectorAll(ROW).forEach(row=>{start(row);row.dataset.auto='1';});
 }
 // 사람이 행을 누르면 자동 진행은 멈춘다
 document.addEventListener('click',e=>{const row=e.target.closest(ROW);if(row)row.closest('.compare-page')?.querySelectorAll(ROW).forEach(r=>{delete r.dataset.auto;});},true);
 // 장을 떠나면 행을 쉬는 상태로 되돌린다 · 들어오면 첫 행부터 자동 재생
 const obs=new MutationObserver(ms=>ms.forEach(m=>{const s=m.target;if(!s.classList.contains('active'))stopAll(s);else setTimeout(()=>autoRow(s),250);}));
 // 스크립트가 <head> 에서 먼저 돌면 장이 아직 없다 → DOM 이 준비된 뒤 붙이고, 이미 활성인 장이면 바로 재생
 function attach(){document.querySelectorAll('.slide.compare-page').forEach(s=>{if(s.dataset.cmpObs)return;s.dataset.cmpObs='1';obs.observe(s,{attributes:true,attributeFilter:['class']});if(s.classList.contains('active'))setTimeout(()=>autoRow(s),250);});}
 if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',attach);else attach();
 window.addEventListener('load',attach);
})();

/* data-start="초": 영상을 그 시점부터 보여 준다(앞부분은 결과까지 기다리게 해서). loop 로 되감겨도 다시 그 시점으로. */
(function(){
 const seek=v=>{const st=parseFloat(v.dataset.start||'0');if(st>0&&v.currentTime<st-0.25){try{v.currentTime=st}catch(e){}}};
 document.addEventListener('play',e=>{const v=e.target;if(v.tagName==='VIDEO'&&v.dataset.start)seek(v);},true);
 document.addEventListener('loadedmetadata',e=>{const v=e.target;if(v.tagName==='VIDEO'&&v.dataset.start)seek(v);},true);
 document.addEventListener('timeupdate',e=>{const v=e.target;if(v.tagName==='VIDEO'&&v.dataset.start&&!v.paused)seek(v);},true);
})();
