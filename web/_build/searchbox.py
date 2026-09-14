# -*- coding: utf-8 -*-
"""사이트 전체 검색 (빌드 [1.89] 단계). 팀장 컨펌 2026-08-12.

  구조
    · 빌드가 모든 페이지의 «제목 · 절 제목 · 절 본문»을 훑어 assets/search-index.json 을 만든다
    · 각 페이지의 PDF 저장 버튼 **왼쪽에 같은 스타일의 검색 버튼**을 단다
    · 누르면 화면 위에 검색 오버레이가 뜬다 (입력 + 결과, ESC/바깥클릭으로 닫힘, Ctrl/Cmd+K)
    · 서버가 없다. 완전 정적이라 Vercel 그대로 동작한다

  v5 (팀장 피드백 2026-08-12): 인라인 입력창 전면 폐기.
    상단 바에 입력창을 끼우니 모바일에서 «← 표지로 · 검색 · PDF» 한 줄이 2행으로
    깨졌다(브리프·백과). 항상 보이는 입력창 대신 **버튼 + 오버레이**:
    기존 레이아웃을 전혀 건드리지 않고, 모든 페이지가 한 가지 방식으로 통일된다.
  이전 이력
    v4 절 단위 색인(백과 h3 id) · v3 iOS 줌(16px)과 잘림 · v2 이모지 제거 · v1 최초

  절 단위 색인
    · 문서형 페이지: <section id="sN"><h2>
    · 백과: <h2/3 id="..."> 로 쪼갠다 (절 29개, «ZMP» → #stability 점프)
    · 둘 다 없으면 페이지 전체가 한 항목

"""
import hashlib
import io
import json
import os
import re

MARK = '<!--search:v8-->'

# v6 (팀장 폰 실측 2026-08-12): 상단 바를 모바일에서도 무조건 한 줄로.
#   가운데 문서 이름표가 길면 줄바꿈되어 페이지마다 높이가 달랐다.
#   이름표를 말줄임(…)으로 줄이고 버튼·홈 링크는 줄바꿈을 금지한다.
# v7 (CDP 모바일 에뮬레이션 실측 2026-08-13 — 헤드리스 창 최소폭 500px 함정을 피해
#   Emulation.setDeviceMetricsOverride 390px 로 렌더·측정한 결과):
#   · 커리큘럼: 상단 바가 2줄 (검색·PDF 가 둘째 줄로) → 진행 칩(시작/기초…)을 모바일에서 숨김
#   · 백과: 자체 규칙 .pdfbtn{display:none} 이 모바일에서 검색 버튼(클래스 복제)까지 숨김
#     → .fh-sbtn 은 항상 보이게. PDF 가 숨겨진 페이지에서는 검색이 우상단 고정으로 선다
#   · 백과·브리프: 표 min-width:440px 가 화면(390px)을 넘음 → 모바일에서 표 자체 가로 스크롤
#   · 백과: 헤더 상단 여백 76px(9vh) → 모바일 28px
CSS_JS = MARK + '''<style>
@media (max-width:640px){
  .top .row{flex-wrap:nowrap}
  .top .row .doc{flex:0 1 auto;min-width:0;overflow:hidden;
    text-overflow:ellipsis;white-space:nowrap}
  .top .row a.home,.top .row .pdfbtn,.top .row .fh-sbtn{white-space:nowrap;flex:none}
  .topbar .stage-chip{display:none}
  .topbar .row{gap:.3rem}
  .topbar .tbtn{padding:.32rem .5rem}
  .topbar .counter{font-size:.62rem}
  .fh-sbtn{display:inline-flex!important}
  /* ★ 2026-08-28. 여기에 table{display:block} 이 있었다. 표를 블록으로 만들면
     안쪽 표 상자가 «내용 너비» 로 줄어든다. 내용이 넓은 표는 우연히 꽉 차 보이고
     좁은 표만 왼쪽으로 쏠린다. 팀장이 여러 번 지적한 «표가 틀어진다» 가 이것이다.
     실측(같은 페이지 · 같은 표 · 크롬): 컨테이너 700px 에서 display:block 은 51%,
     display:table 은 100%. 가로 스크롤은 표를 감싼 .tw 가 이미 맡고 있다.

     ★ 2026-09-14. **그때 `min-width:0` 이 여기 남아 있었다.** 그 한 줄이 위
     주석이 기대는 바로 그 장치를 깬다. 기본 CSS 가 `table{min-width:420px}` 라
     좁은 화면에서 표가 420 px 를 지키고 `.tw` 가 «스크롤» 하게 되어 있는데,
     `min-width:0` 이 그 바닥을 없애 표가 감싸개 폭까지 «짜부라진다».

     팀장이 폰에서 잡았다. 390 px 실측:

       11열 표   셀폭 30 px · 머리줄 76 px   「난이도」가 난/이/도 로 쪼개짐
                                             「100」이 1/0/0 으로 세로로 쌓임
        8열 표   셀폭 36 px

     반쪽만 고친 것을 마저 고쳤다. 이 줄을 지운다. */
  header.top{padding-top:28px}
}
.fh-sbtn-fix{position:fixed;top:7px;right:14px;z-index:70;background:var(--paper);
  border:1px solid var(--rule);color:var(--ink-2);padding:4px 9px;font-family:inherit;
  font-size:.55rem;font-weight:700;letter-spacing:.1em;cursor:pointer;border-radius:4px;
  display:inline-flex;align-items:center;gap:5px}
.fh-so{position:fixed;inset:0;background:rgba(10,14,16,.45);z-index:300;display:none}
.fh-so.on{display:flex;align-items:flex-start;justify-content:center;padding:9vh 14px 0}
.fh-sp{width:min(560px,100%);background:var(--paper);border:1px solid var(--rule);
  border-radius:8px;box-shadow:0 18px 50px rgba(0,0,0,.32);overflow:hidden}
.fh-sp input{width:100%;padding:.75rem .95rem;font-size:16px;border:0;
  border-bottom:1px solid var(--rule);background:var(--paper);color:var(--ink);
  font-family:inherit;outline:none}
.fh-sr{max-height:56vh;overflow-y:auto}
.fh-sr a{display:block;padding:.55rem .95rem;text-decoration:none;color:inherit;
  border-bottom:1px solid var(--rule)}
.fh-sr a:last-child{border-bottom:none}
.fh-sr a:hover,.fh-sr a.sel{background:var(--dim-soft)}
.fh-sr .sp1{font-size:.66rem;color:var(--dim);font-weight:800;letter-spacing:.03em}
.fh-sr .sp2{font-size:.8rem;font-weight:700;margin:.1rem 0}
.fh-sr .sp3{font-size:.7rem;color:var(--ink-3);line-height:1.45}
.fh-sr .none{padding:.7rem .95rem;font-size:.76rem;color:var(--ink-3)}
/* ★ 2026-09-08 감사 F-06. 검색 버튼 실측 58x30. 손가락 목표 44x44 에 못 미친다.
   그렇다고 버튼을 키우면 팀장이 맞춰 둔 상단바 높이(1.85rem)가 통째로 틀어진다.
   보이는 크기는 그대로 두고 «닿는 영역» 만 넓힌다. 가상 요소라 레이아웃을
   건드리지 않는다. 손가락으로 쓰는 화면에서만 건다. */
@media (hover:none),(pointer:coarse){
  .fh-sbtn{position:relative}
  .fh-sbtn::after{content:"";position:absolute;left:50%;top:50%;
    width:44px;height:44px;transform:translate(-50%,-50%)}
}
</style>
<script>
document.addEventListener('DOMContentLoaded',function(){
  /* «← …로» 버튼은 라벨이 가리키는 곳으로만 간다.
     예전의 «스마트 뒤로가기»(history.back)는 제거했다. 라벨은 «표지로»인데
     실제로는 직전 페이지로 돌아가 사용자를 속였다. (2026-08-24) */
  /* 검색 버튼: PDF 저장 버튼 왼쪽, 같은 스타일 (레이아웃을 새로 만들지 않는다) */
  var pb=document.getElementById('pdfBtn')||document.querySelector('.pdfbtn');
  var sb=document.createElement('button');sb.type='button';
  /* ★ 9/1 팀장 실측: 「돋보기 아이콘 크기가 달라지면서 위치가 변한다」.
     여기가 그 원인이다. 검색 버튼이 «그 페이지의 PDF 버튼 클래스를 복사» 해서
     페이지마다 패딩·글자·자간이 달랐고, 그만큼 오른쪽 묶음이 밀렸다.
     전역바가 바를 소유한 지금은 복사할 이유가 없다. 자기 클래스만 쓴다. */
  sb.className=(pb&&!pb.closest('.gnav')?'fh-sbtn-fix ':'')+'fh-sbtn';
  sb.setAttribute('aria-label','사이트 검색');
  sb.innerHTML='<svg viewBox="0 0 16 16" width="11" height="11" fill="none" '
    +'stroke="currentColor" stroke-width="1.6" aria-hidden="true">'
    +'<circle cx="7" cy="7" r="4.2"/><path d="M10.4 10.4L14 14"/></svg>검색';
  /* ★ 2026-08-28. 전에는 PDF 버튼 옆에 붙이려다, PDF 가 숨겨진 화면(모바일)에서
     position:fixed 로 튕겨나가 top:7px/right:14px 에 앉았다. 그 자리가 바로
     sticky 상단바 위였고 z-index 가 둘 다 70 이라 나중에 그려지는 검색이 이겨서
     「파이프라인」 글자를 덮었다 (팀장 모바일 실측).
     상단바에 자리(.navctl)를 마련했으니 **거기 앉는다.** 떠다니지 않는다. */
  var slot=document.querySelector('.gnav .navctl');
  if(slot){ slot.insertBefore(sb, slot.firstChild); }
  else if(pb){ pb.parentNode.insertBefore(sb,pb); }
  else { document.body.appendChild(sb); }
  function offset(){
    if(slot){ sb.style.position='';sb.style.top='';sb.style.right='';sb.style.zIndex='';return; }
    if(!pb)return;var cs=getComputedStyle(pb);
    var r=pb.getBoundingClientRect();
    if(cs.display==='none'||r.width===0){
      sb.style.position='fixed';sb.style.top='7px';sb.style.right='14px';sb.style.zIndex='71';
    }else if(cs.position==='fixed'){
      sb.style.position='fixed';sb.style.top=r.top+'px';
      sb.style.right=(window.innerWidth-r.left+8)+'px';sb.style.zIndex=cs.zIndex;
    }else{sb.style.position='';sb.style.top='';sb.style.right='';}}
  offset();window.addEventListener('resize',offset);
  /* 오버레이
     ★ 2026-09-08 감사 F-06. 화면에는 대화상자로 보이는데 «기계에게는» 그냥 div 였다.
       role·aria-modal 이 없어 보조 기술이 대화상자로 읽지 못하고, 결과가 바뀌어도
       aria-live 가 없어 알리지 않았다. 탭이 뒤 페이지로 새어 나갔고, 닫은 뒤에는
       포커스가 숨은 입력에 남아 키보드 사용자가 어디에 있는지 잃었다.
       보이는 것과 읽히는 것이 다르면 그것은 만들다 만 것이다. */
  var ov=document.createElement('div');ov.className='fh-so';
  ov.setAttribute('role','dialog');
  ov.setAttribute('aria-modal','true');
  ov.setAttribute('aria-label','사이트 검색');
  ov.innerHTML='<div class="fh-sp"><input type="search" placeholder="검색 (제목 · 절 · 본문)" '
    +'aria-label="사이트 검색"><div class="fh-sr" role="listbox" aria-live="polite" '
    +'aria-label="검색 결과"></div></div>';
  document.body.appendChild(ov);
  var inp=ov.querySelector('input'),res=ov.querySelector('.fh-sr'),IDX=null,sel=-1;
  sb.setAttribute('aria-haspopup','dialog');
  sb.setAttribute('aria-expanded','false');
  function open(){
    ov.classList.add('on');
    sb.setAttribute('aria-expanded','true');
    inp.focus();inp.select();
  }
  function close(){
    ov.classList.remove('on');
    sb.setAttribute('aria-expanded','false');
    /* 닫으면 «열었던 그 버튼» 으로 돌아간다. 안 그러면 키보드 사용자는
       숨은 입력에 포커스가 남아 화면 어디에 있는지 알 수 없다. */
    try{ sb.focus(); }catch(e){}
  }
  sb.addEventListener('click',open);
  ov.addEventListener('mousedown',function(e){if(e.target===ov)close();});
  /* 포커스 가두기. 열려 있는 동안 탭이 뒤 페이지로 새지 않게 한다.
     가둘 것은 입력과 결과 링크뿐이라 목록을 그때그때 다시 센다. */
  ov.addEventListener('keydown',function(e){
    if(e.key!=='Tab')return;
    var f=[inp].concat([].slice.call(res.querySelectorAll('a')));
    if(!f.length)return;
    var first=f[0],last=f[f.length-1],cur=document.activeElement;
    if(e.shiftKey&&(cur===first||!ov.contains(cur))){e.preventDefault();last.focus();}
    else if(!e.shiftKey&&cur===last){e.preventDefault();first.focus();}
  });
  document.addEventListener('keydown',function(e){
    if((e.ctrlKey||e.metaKey)&&e.key.toLowerCase()==='k'){e.preventDefault();open();}
    /* ★ 2026-09-08 감사 F-06. Ctrl/Cmd+K 는 브라우저가 주소창 검색으로 먼저
       가져갈 수 있다. 감사도 「실제 키로는 안 열렸다」고 적었고, 내 환경에서는
       키 자체가 페이지에 도달하지 않아 어느 쪽인지 «확인하지 못했다».
       확인 못 한 것을 고쳤다고 할 수 없으므로 Ctrl+K 는 그대로 두고,
       브라우저가 안 가져가는 «/» 를 함께 연다. 위키·깃허브가 쓰는 그 키다.
       글자를 치는 중일 때는 열지 않는다. 그러면 검색어에 / 를 못 넣는다. */
    else if(e.key==='/'&&!ov.classList.contains('on')){
      var a=document.activeElement, tag=(a&&a.tagName||'').toLowerCase();
      if(tag==='input'||tag==='textarea'||tag==='select'||(a&&a.isContentEditable))return;
      e.preventDefault();open();
    }
    else if(e.key==='Escape'&&ov.classList.contains('on'))close();
  });
  /* ★ 2026-09-08 감사 F-06. 셋을 한 덩어리로 삼켜 «결과 없음» 하나로 보여줬다.
     색인을 못 받은 것 · 받았는데 모양이 틀린 것 · 정말로 없는 것은 서로 다르다.
     앞의 둘은 우리 잘못이고 사용자는 다시 시도해야 한다는 것을 알아야 한다.
     경로도 루트 절대경로로 바꾼다. team-meang/ 처럼 한 단계 아래 페이지에서
     상대경로면 team-meang/assets/... 를 찾아 항상 실패한다. */
  var IDXERR=null;
  function load(cb){if(IDX)return cb();
    fetch('/assets/search-index.json').then(function(r){
        if(!r.ok)throw new Error('HTTP '+r.status);
        return r.json();})
      .then(function(j){
        if(!Array.isArray(j)||(j.length&&typeof j[0].x!=='string'))
          throw new Error('schema');
        IDX=j;IDXERR=null;cb();})
      .catch(function(err){
        IDX=[];IDXERR=(err&&err.message==='schema')?'schema':'fetch';cb();});}
  function esc(s){return s.replace(/[&<>"]/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]})}
  /* fh-rank:시작 · 순위 규칙은 여기 하나뿐이다. 빌드 관문 [1.8993] 이 이 함수를
     «그대로» 떼어 node 로 돌려 알려진 답과 맞춰 본다. 규칙을 두 번 적지 않는다. */
  function fhRank(IDX,q,cap,lim){
    var hits=[],i;
    for(i=0;i<IDX.length;i++){
      var e=IDX[i],H=e.h.toLowerCase(),X=e.x.toLowerCase(),T=e.t.toLowerCase(),
          hi=H.indexOf(q),ti=X.indexOf(q),pi=T.indexOf(q);
      if(hi<0&&ti<0&&pi<0)continue;
      var score=(hi>=0?3:0)+(pi>=0?2:0)+(ti>=0?1:0);
      /* ★ 2026-09-09 실측. 점수가 «어느 칸에 있나» 만 보니 본문에 한 번 스친 글과
         본문이 온통 그 얘기인 글이 동점이었고, 동점은 색인 순서로 풀려 결국
         파일이름 순이 됐다. 라이브에서 «rails» 를 치면 12칸이 전부 a~d 로
         시작하는 페이지로 찼고 정작 rails 진단 문서 셋은 하나도 없었다.
         그 낱말을 «몇 번» 쓴 글인가를 칸 다음 순위로 넣는다. 20에서 끊는다.
         (긴 글이 짧은 글을 무조건 이기면 그것대로 또 틀린 순위다.) */
      var n=0,at=-1;
      while(n<20&&(at=X.indexOf(q,at+1))>=0)n++;
      var bt=-1;
      while(n<20&&(bt=H.indexOf(q,bt+1))>=0)n++;
      var snip='';
      if(ti>=0){var s=Math.max(0,ti-34);snip=(s>0?'…':'')+e.x.substr(s,95)+'…';}
      hits.push({e:e,s:score,n:n,i:i,snip:snip});
    }
    /* 동점이면 색인 순서로 고정한다. 정렬이 흔들리면 같은 검색어가 매번 다른
       차례를 준다 (재현 빌드에서 A1 과 A2 가 갈리던 것과 같은 부류다). */
    hits.sort(function(a,b){return b.s-a.s||b.n-a.n||a.i-b.i});
    /* ★ 한 문서가 칸을 다 먹지 않게 한다. «pit» 을 치면 pit 진단 한 장의 절
       여섯이 화면을 채워 다른 문서를 전부 밀어냈다. 페이지당 cap 장까지만
       남기면 12칸이 적어도 네 문서를 담는다. */
    var seen={},keep=[];
    for(i=0;i<hits.length&&keep.length<lim;i++){
      var pg=hits[i].e.p,c=seen[pg]||0;
      if(c>=cap)continue;
      seen[pg]=c+1;keep.push(hits[i]);
    }
    return {hits:keep,total:hits.length};
  }
  /* fh-rank:끝 */
  function go(){
    var q=inp.value.trim().toLowerCase();sel=-1;
    if(q.length<2){res.innerHTML='';return;}
    load(function(){
      /* ★ 2026-09-08 감사 F-02. 전에는 hits.length<40 인 동안만 훑고 그 40개를
         정렬했다. 색인은 페이지 이름 순이라, 뒤쪽 페이지의 «제목 일치»(3점)가
         앞쪽 페이지의 «본문 일치»(1점)보다 높아도 후보에 못 들었다.
         실측: 프로젝트·보행·평가·문서·정책 다섯 낱말에서 화면 상위 12가
         전역 상위 12와 달랐다. 전부 점수 매기고 정렬한 «뒤에» 자른다. */
      var hits=fhRank(IDX,q,3,12).hits;
      if(!hits.length){
        var msg=IDXERR==='fetch'?'검색 색인을 불러오지 못했습니다. 새로고침해 주세요'
               :IDXERR==='schema'?'검색 색인 형식이 올바르지 않습니다. 관리자에게 알려 주세요'
               :'결과 없음: '+esc(q);
        res.innerHTML='<div class="none">'+msg+'</div>';}
      else{res.innerHTML=hits.map(function(h){
        return '<a href="'+h.e.p+(h.e.a?'#'+h.e.a:'')+'"><div class="sp1">'+esc(h.e.t)
          +'</div><div class="sp2">'+esc(h.e.h)+'</div>'
          +(h.snip?'<div class="sp3">'+esc(h.snip)+'</div>':'')+'</a>';}).join('');}
    });
  }
  inp.addEventListener('input',go);
  inp.addEventListener('keydown',function(e){
    e.stopPropagation(); /* 커리큘럼 등 자체 키보드 내비게이션 페이지로 새지 않게 */
    if(e.key==='Escape'){close();return;}
    var as=res.querySelectorAll('a');if(!as.length)return;
    if(e.key==='ArrowDown'){e.preventDefault();sel=Math.min(sel+1,as.length-1);}
    else if(e.key==='ArrowUp'){e.preventDefault();sel=Math.max(sel-1,0);}
    else if(e.key==='Enter'&&sel>=0){e.preventDefault();as[sel].click();return;}
    else return;
    as.forEach(function(a,i){a.classList.toggle('sel',i===sel)});
    if(as[sel])as[sel].scrollIntoView({block:'nearest'});
  });
});
</script>
'''


def svg_text(chunk):
    """SVG 도식 «안의 글자» 만 뽑는다. 좌표와 경로는 버린다.

    ★ 2026-09-09 실측. 색인이 <svg> 를 통째로 버리고 있었다. 그런데 우리는
      「웹에 ASCII 아트 금지」(DESIGN-GUIDE §3) 때문에 도식을 전부 SVG 로 옮겼다.
      **규칙을 지킬수록 그 글자가 검색에서 사라졌다.**
      실측: 도식 안 글자 6,275자 중 5,010자(80%)가 색인 밖이었다.
      백과 3,181자 · 커리큘럼 1,744자. 낱말을 찾으러 오는 바로 그 두 페이지다.

      PDF 5종에 「웹에 없는 내용」이 있는지 세다가 나왔다. 처음에는 PDF 에만
      있는 문장으로 보였는데, 웹 페이지에는 있고 «색인에만» 없었다.
      화면에 보이는 글자는 색인에 있어야 한다.
    """
    out = []
    for m in re.finditer(r'<(?:text|title|tspan|desc)[^>]*>(.*?)</(?:text|title|tspan|desc)>',
                         chunk, re.S):
        out.append(re.sub(r'<[^>]+>', ' ', m.group(1)))
    # ★ 2026-09-09. 도식 상당수는 <text> 가 아예 없다. 도형만 있거나, 빈 <svg> 를
    #   두고 JS 가 런타임에 그린다 (백과의 보행 도해가 그렇다).
    #   그런 도식의 «이름» 은 aria-label 에 있고 그것이 유일한 정적 글자다.
    #   실측: 도식 184개 중 150개가 <text> 없이 왔고 aria-label 은 32개 있었다.
    #   런타임에 그려지는 글자는 정적 파일에 없으므로 색인할 방법이 없다.
    #   그것까지 담으려면 페이지를 실제로 띄워 읽어야 한다. 지금은 안 한다.
    #   대신 «못 담는다» 를 알고 있는 것과 모르는 것은 다르다.
    out += re.findall(r'aria-label="([^"]{2,})"', chunk)
    return ' '.join(out)


STAMP = re.compile(r'<!--stamp:v1-->.*?<!--/stamp:v1-->', re.S)


def strip_tags(s):
    # ★ 2026-09-09. 빌드 도장은 모든 페이지에 똑같이 붙는다. 색인에 들어가면
    #   「갱신」 「팀 공지」 로 128장이 전부 걸려 검색이 못 쓰게 된다.
    #   전에는 도장을 «색인 뒤에» 찍는 순서 덕에 우연히 안 들어왔다. 순서에
    #   기대는 것은 규칙이 아니다. 여기서 명시적으로 뺀다.
    s = STAMP.sub(' ', s)
    s = re.sub(r'<style.*?</style>|<script.*?</script>', ' ', s, flags=re.S)
    s = re.sub(r'<svg.*?</svg>', lambda m: ' ' + svg_text(m.group(0)) + ' ',
               s, flags=re.S)
    s = re.sub(r'<[^>]+>', ' ', s)
    s = s.replace('&lt;', '<').replace('&gt;', '>').replace('&amp;', '&').replace('&quot;', '"')
    return re.sub(r'\s+', ' ', s).strip()


def svg_census(vault, pub):
    """도식이 검색에 «어디까지» 보이는가를 센다.

    ★ 2026-09-09. 이 셈이 없어서 내가 틀린 수를 두 번 말했다. 처음엔 「<text> 가
      없는 도식 150개가 런타임에 그려진다」고 했는데, 실제로 JS 가 그리는 것은
      둘뿐이고 나머지는 aria-hidden 을 단 장식 아이콘이었다.
      세지 않고 말하면 그렇게 된다. 그래서 매 빌드가 이 넷을 찍는다.

    갈래
      내용   정적 <text>·<title>·<desc> 가 있다. 글자가 그대로 색인에 든다
      이름   글자는 없고 aria-label 만 있다. 도식 «이름» 으로만 찾힌다
      장식   aria-hidden="true". 아이콘·괘선이라 담을 것이 없다
      맨것   셋 다 아니다. 검색에서 통째로 안 보인다. 늘어나면 봐야 한다
    """
    kinds = {'내용': 0, '이름': 0, '장식': 0, '맨것': 0}
    drawn = []
    for f in sorted(pub):
        fp = os.path.join(vault, f)
        if not os.path.isfile(fp):
            continue
        raw = io.open(fp, encoding='utf-8', errors='replace').read()
        js = ' '.join(x.group(0) for x in
                      re.finditer(r'<script.*?</script>', raw, re.S))
        for m in re.finditer(r'<svg.*?</svg>', raw, re.S):
            c = m.group(0)
            has = bool(re.search(r'<(?:text|tspan|title|desc)[\s>]', c))
            lab = re.search(r'aria-label="([^"]{2,})"', c)
            sid = re.search(r'\bid="([^"]+)"', c)
            if has:
                kinds['내용'] += 1
            elif lab:
                kinds['이름'] += 1
            elif 'aria-hidden' in c:
                kinds['장식'] += 1
            else:
                kinds['맨것'] += 1
            if sid and not has and sid.group(1) in js:
                drawn.append((f, sid.group(1), lab.group(1) if lab else ''))
    return kinds, drawn


def is_page(path):
    """«페이지» 인가 «조각» 인가. 조각은 다른 페이지 안에 끼워지는 토막이다.

    ★ 2026-09-13. assets/ 밑 .html 이 전부 페이지는 아니다. 다른 생성기가
      전역바 조각을 둔다 (gnav.html · gnav-head.html). <head> 가 없다.
      페이지로 세면 파비콘 · 검색 · 완비 관문이 전부 걸리고, 색인에는 전역바
      글자가 페이지 하나로 들어가 검색을 흐린다.
      실측: 그 둘 때문에 파비콘 관문이 배포를 세웠다.
    """
    try:
        head = io.open(path, encoding='utf-8', errors='replace').read(600)
    except OSError:
        return False
    return '<head' in head.lower()


def public_pages(vault, pages):
    """배포되는 공개 HTML 전수. 단일 정본이다.

    ★ 2026-09-08 감사 F-03. 전에는 `pages` 를 그대로 돌았는데 그 목록은 «루트» 만
      담는다. 하위 폴더 HTML 둘이 통째로 검색 밖이었다 (실측: 공개 117 · 색인 115).
        team-meang/index.html                        공개 URL /team-meang 로 200
        assets/deliverables/proposal-deck-presented.html  발표본 실물
      루트만 보는 암묵 규칙을 없애고 여기서 한 번만 정한다.

    보호 문서는 구조적으로 들어올 수 없다. assets/secure/ 는 전부 `.enc` 암호문이라
    `.html` 필터에 걸리지 않는다. 그래도 이름으로 한 번 더 막는다 (관문은 두 겹).
    """
    out = set()
    for f in pages:
        p = os.path.join(vault, f)
        if os.path.isdir(p):                      # PAGES 에 폴더가 들어온다 (team-meang/)
            for r, _, xs in os.walk(p):
                for x in xs:
                    if x.endswith('.html') and is_page(os.path.join(r, x)):
                        out.add(os.path.relpath(os.path.join(r, x), vault)
                                .replace(os.sep, '/'))
        elif f.endswith('.html') and os.path.exists(p):
            out.add(f)
    adir = os.path.join(vault, 'assets')          # assets 는 통째로 배포된다
    for r, _, xs in os.walk(adir):
        rel_dir = os.path.relpath(r, vault).replace(os.sep, '/')
        if rel_dir.startswith('assets/secure'):   # 보호 문서. 절대 색인하지 않는다
            continue
        for x in xs:
            if not x.endswith('.html'):
                continue
            if not is_page(os.path.join(r, x)):
                continue
            out.add((rel_dir + '/' + x).replace('./', ''))
    return sorted(out)


# 오버레이를 «넣지 않는» 페이지. 전체화면 발표본은 자체 키보드 조작이 있어
# 오버레이가 슬라이드를 덮고 Ctrl+K 가 덱 조작과 부딪힌다. 색인에는 넣는다.
NO_UI = {'assets/deliverables/proposal-deck-presented.html'}


# ★ 2026-09-13. 이 빌드가 «안 만드는» 배포본 페이지. 볼트에 없고 배포본에만
#   있다. 갤러리와 종합 보고서가 그렇고, 지금 이 프로젝트의 주된 산출물이라
#   검색에 없으면 「우리 결과가 어디 있지」가 검색으로 안 풀린다.
#   그 페이지는 «배포본이 곧 원본» 이다. 거기서 읽는 것은 두 번째 진실을
#   만드는 것이 아니라 유일한 진실을 읽는 것이다.
#   영상 자체는 대상이 아니다. 그 페이지들의 «글자» 만 담는다.
FROM_SITE = ['gallery/index.html', 'gallery/view/index.html',
             'gallery/compare/index.html', 'report-v1.html']
SITE_DIR = None          # build.py 가 배포본 경로를 넣어 준다


def build_index(vault, pages):
    idx = []
    # ★ 2026-09-03 (foothold-lab#137). 색인 순서를 이름으로 못박는다.
    #   pages 는 빌드 도중 늘어나는 목록이라, 뒤늦게 생기는 페이지가 언제
    #   들어오느냐에 따라 첫 빌드와 두 번째 빌드의 «레코드 자리» 가 달라졌다.
    #   내용과 개수는 같은데 순서만 달라 A1 과 A2 가 바이트로 갈렸다
    #   (실측: 731 레코드 집합 동일 · 자리만 다름 136).
    #   정렬만 한다. 담기는 내용도 개수도 검색 동작도 그대로다.
    for f in public_pages(vault, pages):
        p = os.path.join(vault, f)
        if not os.path.exists(p):
            continue
        t = io.open(p, encoding='utf-8').read()
        mt = re.search(r'<title>([^<]+)</title>', t)
        ptitle = (mt.group(1).split('·')[0].strip() if mt else f)
        # 절 단위 ①: <section id="..."> … (문서형 페이지의 표준 구조)
        # ★ 2026-09-09. 여기는 원래 <section id><h2> 가 «곧바로» 붙은 것만 찾는
        #   정규식이었다. 그런데 docs_pages 가 나중에 그 사이에 눈썹 줄을 끼운다
        #   (<section id="sN"><div class="rpt-eyebrow">…</div><h2>).
        #   그래서 13개 절 중 1개만 맞았고, 22,011자 페이지에서 338자만 색인됐다.
        #   나머지 21,673자가 통째로 검색 밖이었다. 1500 절단보다 큰 누수다.
        #   「Acquisition 을 못 찾는다」의 진짜 원인이 이것이었다.
        #   정규식으로 «구조를 맞히려» 하지 않는다. 경계로 자르고 그 안에서 찾는다.
        #   마크업이 또 바뀌어도 경계는 그대로다.
        secs = []
        marks = [(m.start(), m.group(1)) for m in
                 re.finditer(r'<section id="([\w.-]+)"[^>]*>', t)]
        if marks:
            # ★ 첫 절 «앞» 도 본문이다. 제목·리드·머리 띠가 거기 있다.
            #   절만 담으면 그 부분이 통째로 빠진다 (실측: 48장이 56~81%).
            wrap = re.search(r'<div class="wrap">(.*)', t[:marks[0][0]], re.S)
            head0 = strip_tags(wrap.group(1) if wrap else t[:marks[0][0]])
            if len(head0) >= 40:
                secs.append(('', ptitle, t[:marks[0][0]]))
        for k, (pos, sid) in enumerate(marks):
            end = marks[k + 1][0] if k + 1 < len(marks) else len(t)
            chunk = t[pos:end]
            hm = re.search(r'<h([23])[^>]*>(.*?)</h\1>', chunk, re.S)
            secs.append((sid, hm.group(2) if hm else sid, chunk))
        # 절 단위 ②: id 달린 제목으로 쪼갠다 (백과: h3 id 29개. 팀장 요청 2026-08-12)
        heads = [(m.start(), m.group(2), m.group(3)) for m in
                 re.finditer(r'<h([23])\s+id="([\w.-]+)"[^>]*>(.*?)</h\1>', t, re.S)]
        # ★ 2026-09-08 감사 F-01. 여기 세 곳이 본문을 [:1500] 으로 잘랐다.
        #   실측: 848 레코드 중 100개가 정확히 1500자에서 끊겼고 공개 본문의 30.2% 가
        #   색인에 없었다. deliverable-proposal 화면에 있는 «Acquisition» 을 검색하면
        #   0건이 나왔다. 있는 글자를 못 찾는 것은 검색이 아니다. 절단을 없앤다.
        #   대가는 실측했다. gzip 353KB -> 478KB (+35%). 첫 검색에만 한 번 받고
        #   그 뒤로는 캐시다. 「빠짐없이 찾힌다」가 그 값보다 무겁다.
        if secs:
            for a, h, body in secs:
                idx.append({'p': f, 't': ptitle, 'h': strip_tags(h)[:90],
                            'a': a, 'x': strip_tags(body)})
        elif heads:
            # 첫 제목 앞도 같은 이유로 담는다
            wrap = re.search(r'<div class="wrap">(.*)', t[:heads[0][0]], re.S)
            head0 = strip_tags(wrap.group(1) if wrap else t[:heads[0][0]])
            if len(head0) >= 40:
                idx.append({'p': f, 't': ptitle, 'h': ptitle, 'a': '', 'x': head0})
            for j, (pos, hid, htxt) in enumerate(heads):
                end = heads[j + 1][0] if j + 1 < len(heads) else len(t)
                idx.append({'p': f, 't': ptitle, 'h': strip_tags(htxt)[:90],
                            'a': hid, 'x': strip_tags(t[pos:end])})
        else:
            body = re.search(r'<div class="wrap">(.*)', t, re.S)
            idx.append({'p': f, 't': ptitle, 'h': ptitle, 'a': '',
                        'x': strip_tags(body.group(1) if body else t)})
    # ── 배포본에만 있는 페이지 ────────────────────────────────────
    #   ★ 0건이면 실패한다. 경로가 바뀌거나 파일이 사라지면 «조용히» 빠지고,
    #     그러면 검색에서 없어지는데 아무도 모른다.
    if SITE_DIR:
        got = 0
        for rel in FROM_SITE:
            fp = os.path.join(SITE_DIR, rel.replace('/', os.sep))
            if not os.path.isfile(fp):
                continue
            t = io.open(fp, encoding='utf-8', errors='replace').read()
            mt = re.search(r'<title>([^<]+)</title>', t)
            ttl = (mt.group(1).split('·')[0].strip() if mt else rel)
            body = re.search(r'<body[^>]*>(.*)', t, re.S)
            txt = strip_tags(body.group(1) if body else t)
            if not txt:
                continue
            idx.append({'p': rel, 't': ttl, 'h': ttl, 'a': '', 'x': txt})
            got += 1
        if got != len(FROM_SITE):
            print('  [!] 배포본에서 읽을 페이지 %d개 중 %d개만 찾았습니다'
                  % (len(FROM_SITE), got))
            print('      경로가 바뀌었거나 그 생성기가 안 돌았습니다.')
            print('      조용히 빠지면 검색에서 사라지는데 아무도 모릅니다.')
            return -1, 0
        print('  배포본 전용 페이지 %d장도 색인에 넣었습니다: %s'
              % (got, ' · '.join(FROM_SITE)))
    out = os.path.join(vault, 'assets', 'search-index.json')
    io.open(out, 'w', encoding='utf-8').write(json.dumps(idx, ensure_ascii=False))
    return len(idx), os.path.getsize(out)


def _kat():
    """알려진 답으로 먼저 시험한다. 절단이 되살아나면 여기서 걸린다.

    긴 본문의 «끝» 에 고유 토큰을 심고 그것이 색인에 들어오는지 본다.
    1500자 절단이 있으면 토큰이 사라지므로 이 시험이 실패한다.
    """
    import tempfile
    tok = 'ZZKATTOKEN9137'
    body = ('가나다라마바사 ' * 900) + tok          # 6,300자 남짓
    html = ('<html><head><title>KAT · 시험</title></head><body>'
            '<div class="wrap"><p>%s</p></div></body></html>' % body)
    d = tempfile.mkdtemp()
    os.makedirs(os.path.join(d, 'assets'), exist_ok=True)
    io.open(os.path.join(d, 'kat.html'), 'w', encoding='utf-8').write(html)
    idx = []
    try:
        n, _ = build_index(d, ['kat.html'])
        idx = json.load(io.open(os.path.join(d, 'assets', 'search-index.json'),
                                encoding='utf-8'))
    except Exception as e:
        return False, '색인을 못 만듦: %s' % e
    if not idx:
        return False, '레코드가 0개'
    if not any(tok in r.get('x', '') for r in idx):
        return False, '긴 본문 끝의 토큰이 색인에 없다 (절단이 살아 있다)'
    if not any(len(r.get('x', '')) > 1500 for r in idx):
        return False, '1500자를 넘는 레코드가 하나도 없다 (상한이 걸려 있다)'

    # ★ 2026-09-09. 도식 «안의 글자» 는 색인에 들고 좌표·경로는 안 든다.
    #   우리는 ASCII 도식을 전부 SVG 로 옮겼다. 그 규칙을 지킬수록 검색에서
    #   사라지면 안 된다. 반대로 경로 데이터가 새면 검색이 쓰레기로 찬다.
    g = strip_tags('<p>본문</p><svg viewBox="0 0 9 9"><rect x="3" y="4"/>'
                   '<path d="M1 2L3 4"/><text x="5" y="9">ZZSVGKAT</text>'
                   '<title>도해</title></svg><p>끝</p>')
    for want in ('본문', 'ZZSVGKAT', '도해', '끝'):
        if want not in g:
            return False, '도식 안 글자가 색인에서 빠진다: %s' % want
    for junk in ('viewBox', 'M1 2L3 4', 'rect'):
        if junk in g:
            return False, '도식의 좌표·경로가 색인으로 샌다: %s' % junk
    # <text> 가 없는 도식은 aria-label 이 유일한 정적 글자다. 그것마저 버리면
    # 그 도식은 검색에서 통째로 사라진다.
    g2 = strip_tags('<svg aria-label="ZZARIAKAT" viewBox="0 0 4 4">'
                    '<circle cx="2" cy="2" r="1"/></svg>')
    if 'ZZARIAKAT' not in g2:
        return False, '글자 없는 도식의 이름(aria-label)이 색인에서 빠진다'
    # 빌드 도장은 128장에 똑같이 붙는다. 들어가면 검색이 못 쓰게 된다.
    g3 = strip_tags('<p>본문</p><!--stamp:v1--><div>이 페이지 갱신 ZZSTAMPKAT</div>'
                    '<!--/stamp:v1--><p>끝</p>')
    if 'ZZSTAMPKAT' in g3:
        return False, '빌드 도장이 색인에 들어간다 (모든 페이지가 같은 말로 걸린다)'
    if '본문' not in g3 or '끝' not in g3:
        return False, '도장을 걷다가 앞뒤 본문까지 지웠다'
    return True, ''


def main(vault, pages):
    ok, why = _kat()
    if not ok:
        print('  [!] 자기시험 실패: %s' % why)
        return False

    n, size = build_index(vault, pages)
    # ★ 배포본 전용 페이지를 하나라도 못 찾으면 build_index 가 -1 을 준다.
    #   여기서 안 보면 «옛 색인 파일» 을 그대로 읽고 통과한다. 조용한 실패다.
    if n < 0:
        return False
    pub = public_pages(vault, pages)

    # ── 관문 ① 색인 대상 집합 == 공개 HTML 집합 ────────────────────────
    idx = json.load(io.open(os.path.join(vault, 'assets', 'search-index.json'),
                            encoding='utf-8'))
    indexed = set(r['p'] for r in idx)
    missing = sorted(set(pub) - indexed)
    if missing:
        print('  [!] 공개 HTML 인데 색인에 없습니다 %d개' % len(missing))
        for x in missing[:10]:
            print('     %s' % x)
        return False

    # ── 관문 ② 공개 본문 유실 0 (절단 흔적이 없어야 한다) ────────────────
    # ★ 2026-09-09. 전에는 «정확히 1500자» 하나만 봤다. 그런데 그것은 절단의
    #   증거가 아니라 정황이다. 실측: notice-20260809 는 페이지 전체가 마침
    #   1500자라 멀쩡한데도 배포가 섰다. 우는 관문은 곧 무시된다.
    #   절단이면 «그 페이지에 더 남은 글이 있어야» 한다. 그것을 같이 본다.
    seen_len = {}
    for r in idx:
        seen_len[r['p']] = seen_len.get(r['p'], 0) + len(r['x'])
    capped = []
    for r in idx:
        if len(r['x']) != 1500:
            continue
        fp = os.path.join(vault, r['p'])
        if not os.path.exists(fp):
            continue
        b = re.search(r'<div class="wrap">(.*)',
                      io.open(fp, encoding='utf-8').read(), re.S)
        full = len(strip_tags(b.group(1))) if b else 0
        if full > seen_len.get(r['p'], 0):
            capped.append(r['p'])
    if capped:
        print('  [!] 1500자에서 끊긴 레코드 %d개 · 그 페이지에 더 남은 글이 있습니다.'
              ' 절단이 되살아났습니다: %s'
              % (len(capped), ' · '.join(sorted(set(capped))[:6])))
        return False

    # ── 관문 ②-b 페이지마다 «본문을 얼마나 담았는가» ──────────────────────
    #   ★ 2026-09-09. 절단만 보면 부족했다. 절을 못 찾아 «담지 못한» 경우는
    #     레코드 길이가 멀쩡해서 ①을 통과한다. 실측: deliverable-proposal 이
    #     22,011자 중 338자(1.5%)만 담고도 관문을 통과하고 있었다.
    #     담은 양을 페이지 본문과 견준다. 이것이 「유실 0」의 진짜 관문이다.
    have = {}
    for r in idx:
        have[r['p']] = have.get(r['p'], 0) + len(r['x'])
    thin = []
    for f in pub:
        p = os.path.join(vault, f)
        if not os.path.exists(p):
            continue
        body = re.search(r'<div class="wrap">(.*)', io.open(p, encoding='utf-8').read(), re.S)
        full = len(strip_tags(body.group(1))) if body else 0
        if full >= 400 and have.get(f, 0) < full * 0.9:
            thin.append((f, have.get(f, 0), full))
    if thin:
        print('  [!] 본문을 다 못 담은 페이지 %d개 (담은 양 / 전체)' % len(thin))
        for f, got, full in sorted(thin, key=lambda x: x[1] / max(1, x[2]))[:10]:
            print('     %-46s %6d / %6d  (%.0f%%)' % (f, got, full, 100.0 * got / full))
        return False

    # ── 관문 ③ 보호 문서는 한 줄도 들어오면 안 된다 ──────────────────────
    leaked = [r['p'] for r in idx if 'assets/secure' in r['p']]
    if leaked:
        print('  [!] 보호 문서가 색인에 있습니다: %s' % ' · '.join(sorted(set(leaked))))
        return False

    # ── 관문 ④ 도식 안 글자가 색인에 들어왔는가 ──────────────────────────
    #   ★ 2026-09-09 실측에서 나왔다. 색인이 <svg> 를 통째로 버려 도식 글자
    #     6,275자 중 5,010자(80%)가 검색 밖이었다. 백과 3,181 · 커리큘럼 1,744.
    #     낱말을 찾으러 오는 바로 그 두 페이지다.
    #     「웹에 ASCII 아트 금지」 규칙을 지킬수록 검색이 나빠지는 구조였다.
    per = {}
    for r in idx:
        per.setdefault(r['p'], []).append(r['x'])
    thin_svg = []
    for f in sorted(pub):
        fp = os.path.join(vault, f)
        if not os.path.isfile(fp):
            continue
        raw = io.open(fp, encoding='utf-8', errors='replace').read()
        frags = []
        for m in re.finditer(r'<svg.*?</svg>', raw, re.S):
            frags += [x.strip() for x in svg_text(m.group(0)).split('  ')]
        frags = [x for x in frags if len(x.strip()) >= 2]
        if not frags:
            continue
        got = ' '.join(per.get(f, []))
        lost = [x for x in frags if x not in got]
        if lost:
            thin_svg.append((f, len(lost), len(frags), lost[:3]))
    if thin_svg:
        print('  [!] 도식 안 글자가 색인에 없습니다:')
        for f, a_, b_, sample in thin_svg[:6]:
            print('      %s · %d/%d 조각 · 예: %s'
                  % (f, a_, b_, ' | '.join(s[:24] for s in sample)))
        return False

    chars = sum(len(r['x']) for r in idx)
    longest = max(len(r['x']) for r in idx) if idx else 0

    # ── 색인 주소에 내용 해시 ────────────────────────────────────────────
    #   ★ 2026-09-09. vercel.json 이 /assets/* 를 1년 immutable 로 준다.
    #     그런데 색인만 assetver 의 해시 대상에서 빠져 있었다 (고정 이름으로
    #     부르니까). 그래서 «고친 색인이 재방문자에게 영원히 안 닿는다».
    #     실측: 내 브라우저가 147 레코드짜리 옛 판을 계속 읽었다. 957 로
    #     늘려 놓고도 사용자는 옛것을 본다면 고친 것이 아니다.
    #     파일을 캐시 밖으로 옮기면 1.6MB 를 매번 다시 받는다. 그건 손해다.
    #     immutable 을 살리고 «주소» 에 내용 해시를 붙인다. 내용이 바뀌면
    #     주소가 바뀌므로 캐시가 저절로 비켜난다. 표준적인 방법이다.
    ver = hashlib.sha256(
        io.open(os.path.join(vault, 'assets', 'search-index.json'), 'rb')
        .read()).hexdigest()[:8]
    css_js = CSS_JS.replace("'/assets/search-index.json'",
                            "'/assets/search-index.json?v=%s'" % ver)
    if css_js == CSS_JS:
        print('  [!] 색인 주소에 해시를 못 붙였습니다. 부르는 자리가 바뀌었습니다')
        return False
    m = 0
    for f in pub:
        if f in NO_UI:
            continue
        p = os.path.join(vault, f)
        if not os.path.exists(p):
            continue
        t = io.open(p, encoding='utf-8').read()
        t = re.sub(r'<!--search:v\d+-->.*?</script>\s*', '', t, flags=re.S)
        # v3~v4 의 인라인 슬롯 잔재 제거 (index.html 은 재생성되지 않고 누적된다)
        t = re.sub(r'<!--searchslot:v\d+--><div id="fh-search-slot"[^>]*></div>\n?', '', t)
        if '</head>' in t:
            t = t.replace('</head>', css_js + '</head>', 1)
            m += 1
        io.open(p, 'w', encoding='utf-8', newline='\n').write(t)
    # 관문이 «몇 장을 봤는지» 찍는다. 숫자가 없으면 통과가 사각지대인지 알 수 없다.
    # ★ 2026-09-09. 「대상에 닿지 못한 것」과 「위반이 없는 것」은 다른 사실인데
    #   같은 «통과» 를 내고 있었다. 빈 볼트로 돌려 보고 알았다.
    #   관문이 0개를 검사하고 통과하면, 목록이 비는 순간 조용히 무력해진다.
    if not pub:
        print('  [!] 공개 페이지를 한 장도 못 찾았습니다. 검사가 헛돌았습니다')
        return False
    print('  자기시험 통과 · 공개 %d장 = 색인 %d장 · 절단 0 · 보호 문서 0'
          % (len(pub), len(indexed)))
    print('  색인 %d개 절 · 본문 %d자 · 최장 레코드 %d자 · %dKB · 오버레이 %d페이지 (Ctrl/Cmd+K)'
          % (n, chars, longest, size // 1024, m))
    if NO_UI:
        print('  오버레이 제외 %d장 (전체화면 발표본. 색인에는 들어감): %s'
              % (len(NO_UI), ' · '.join(sorted(NO_UI))))
    kinds, drawn = svg_census(vault, pub)
    print('  도식 %d개 · 내용까지 %d · 이름만 %d · 장식(담을 것 없음) %d · 맨것 %d'
          % (sum(kinds.values()), kinds['내용'], kinds['이름'],
             kinds['장식'], kinds['맨것']))
    if drawn:
        print('  화면에서 JS 가 그리는 도식 %d개 · 이름으로만 찾힙니다 (정적 파일에 글자가 없음):'
              % len(drawn))
        for f, i, lab in drawn:
            print('      %s #%s%s' % (f, i, ('  «%s»' % lab) if lab else '  (이름 없음)'))
    return True
