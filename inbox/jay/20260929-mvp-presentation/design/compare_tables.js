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
 // 팀장 2026-10-02: 장으로 넘어가면 바로 재생. 18개를 한꺼번에 돌리면 노트북이 버거우니 첫 행부터 차례로(한 행이 끝나면 다음 행).
 function autoRow(page,i){
  const rows=[...page.querySelectorAll(ROW)];if(!rows.length||!page.classList.contains('active'))return;
  const row=rows[i%rows.length];stopAll(page,row);start(row);row.dataset.auto='1';
  const v=row.querySelector('video');if(!v)return;
  const next=()=>{v.removeEventListener('ended',next);if(page.classList.contains('active')&&row.dataset.auto==='1')autoRow(page,i+1);};
  v.addEventListener('ended',next);
  // loop 속성이 있으면 ended 가 안 온다 → 자동 행에서는 loop 를 끈다
  row.querySelectorAll('video').forEach(x=>{x.loop=false;});
 }
 // 사람이 행을 누르면 자동 진행은 멈춘다
 document.addEventListener('click',e=>{const row=e.target.closest(ROW);if(row)row.closest('.compare-page')?.querySelectorAll(ROW).forEach(r=>{delete r.dataset.auto;});},true);
 // 장을 떠나면 행을 쉬는 상태로 되돌린다 · 들어오면 첫 행부터 자동 재생
 const obs=new MutationObserver(ms=>ms.forEach(m=>{const s=m.target;if(!s.classList.contains('active'))stopAll(s);else setTimeout(()=>autoRow(s,0),250);}));
 document.querySelectorAll('.slide.compare-page').forEach(s=>obs.observe(s,{attributes:true,attributeFilter:['class']}));
})();
