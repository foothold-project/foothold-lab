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
 // 장을 떠나면 행을 쉬는 상태로 되돌린다 (deck.js 는 영상만 멈춘다)
 const obs=new MutationObserver(ms=>ms.forEach(m=>{const s=m.target;if(!s.classList.contains('active'))stopAll(s);}));
 document.querySelectorAll('.slide.compare-page').forEach(s=>obs.observe(s,{attributes:true,attributeFilter:['class']}));
})();
