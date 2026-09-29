document.querySelectorAll('.vcmp').forEach(group=>{
  const videos=[...group.querySelectorAll('video')];
  group.querySelector('[data-action="play"]')?.addEventListener('click',()=>{
    const pause=videos.some(v=>!v.paused);videos.forEach(v=>pause?v.pause():v.play().catch(()=>{}));
  });
  group.querySelector('[data-action="reset"]')?.addEventListener('click',()=>videos.forEach(v=>{v.pause();v.currentTime=0}));
  group.querySelector('select')?.addEventListener('change',e=>videos.forEach(v=>v.playbackRate=Number(e.target.value)));
});

window.preparePrint=async function(sync=false){
  if(document.querySelector('.sheet'))return window.printAudit;
  if(!sync)await document.fonts.ready;
  const root=document.querySelector('#print-root');
  const queue=[];
  function atom(node,inherited){
    if(node.nodeType!==1)return;
    if(['SCRIPT','STYLE','BUTTON'].includes(node.tagName))return;
    const id=node.dataset.sourceId||inherited;
    if(node.matches('section,.report-body')){[...node.children].forEach(x=>atom(x,id));return}
    if(node.matches('span')&&!node.textContent.trim())return;
    if(node.matches('.source-figure')&&node.querySelector('[data-parts]')){
      const parts=JSON.parse(node.querySelector('[data-parts]').dataset.parts);
      parts.forEach((part,i)=>{const c=node.cloneNode(true),img=c.querySelector('[data-parts]');img.src=part.src;img.width=Number(part.width);img.height=Number(part.height);if(i<parts.length-1)c.replaceChildren(img);c.dataset.sourceId=id;queue.push(c)});return;
    }
    if(node.matches('.source-figure')&&node.querySelector('[data-part-one]')){
      const first=node.cloneNode(true),second=node.cloneNode(true),img=first.querySelector('[data-part-one]');
      first.replaceChildren(img);img.src=img.dataset.partOne;img.width=800;img.height=689;
      const other=second.querySelector('[data-part-two]');other.src=other.dataset.partTwo;other.width=800;other.height=754;
      first.dataset.sourceId=id;second.dataset.sourceId=id;queue.push(first,second);return;
    }
    if(node.matches('.tw')){[...node.children].forEach(x=>atom(x,id));return}
    if(node.matches('.cb')){
      const pre=node.querySelector('pre');if(pre){const c=pre.cloneNode(true);c.dataset.sourceId=id||'';queue.push(c)}return;
    }
    if(node.matches('blockquote')&&node.children.length>1){
      [...node.children].forEach(x=>{const c=x.cloneNode(true);c.classList.add('note-block');c.dataset.sourceId=id||'';queue.push(c)});return;
    }
    const c=node.cloneNode(true);if(id)c.dataset.sourceId=id;
    if(node.matches('section>h2'))c.id=node.parentElement.id;
    queue.push(c);
  }
  [...document.querySelector('#web-content').children].forEach(x=>atom(x));
  if(!sync)await Promise.all(queue.flatMap(n=>[...n.querySelectorAll('img')]).map(img=>img.decode().catch(()=>{})));
  document.body.classList.add('paginating');
  let sheet,body,number=0;
  function newPage(){
    sheet=document.createElement('article');sheet.className='sheet';number++;
    sheet.innerHTML='<header class="sheet-head"><b>FOOTHOLD</b><span>MVP 종합보고서 · 2026.09</span></header><div class="sheet-body"></div><footer class="sheet-foot"><span>미경험 험지 적응 · 지형 통과와 명령 수행</span><span class="page-number">'+number+'</span></footer>';
    root.append(sheet);body=sheet.querySelector('.sheet-body');
  }
  function fits(){return body.scrollHeight<=body.clientHeight+1&&lastBottom()<=body.clientHeight+0.5}
  function lastBottom(){return body.lastElementChild?body.lastElementChild.getBoundingClientRect().bottom-body.getBoundingClientRect().top:0}
  function splitTable(table){
    const rows=[...table.querySelectorAll('tbody>tr')];
    if(!rows.length)return false;
    const part=table.cloneNode(true),partBody=part.querySelector('tbody');partBody.innerHTML='';
    body.append(part);let used=0;
    for(const row of rows){partBody.append(row.cloneNode(true));if(!fits()){partBody.lastElementChild.remove();break}used++}
    if(!used){part.remove();return false}
    if(used<rows.length){
      const rest=table.cloneNode(true);const rb=rest.querySelector('tbody');rb.innerHTML='';rows.slice(used).forEach(r=>rb.append(r.cloneNode(true)));
      rest.dataset.continuation='true';queue.unshift(rest);
    }
    return true;
  }
  newPage();
  let safety=0;
  while(queue.length){
    if(++safety>4000)throw Error('Pagination did not converge');
    const item=queue.shift();
    if(item.matches('.cover')){if(body.children.length)newPage();sheet.classList.add('cover-sheet');body.append(item);newPage();continue}
    if(item.matches('h2,h3,h4')&&body.children.length&&body.clientHeight-lastBottom()<95)newPage();
    if(item.matches('h2,h3,h4')&&body.children.length&&queue[0]){
      const probe=queue[0].cloneNode(true);
      if(probe.matches('table'))[...probe.querySelectorAll('tbody>tr')].slice(2).forEach(row=>row.remove());
      body.append(item,probe);const together=fits();probe.remove();item.remove();if(!together)newPage();
    }
    body.append(item);
    if(fits())continue;
    item.remove();
    if(item.matches('table')&&splitTable(item)){if(queue.length)newPage();continue}
    if(body.children.length){newPage();body.append(item);if(fits())continue;item.remove()}
    if(item.matches('table')&&splitTable(item)){if(queue.length)newPage();continue}
    // Long source notes/lists are split at existing semantic children, never clipped.
    if(item.children.length>1&&!item.matches('.vcmp,.hero,.source-figure,.contents')){
      const parts=[...item.children].map(x=>{const c=x.cloneNode(true);if(item.dataset.sourceId)c.dataset.sourceId=item.dataset.sourceId;return c});queue.unshift(...parts);continue;
    }
    body.append(item);
    if(!fits())throw Error('Oversize source block: '+(item.dataset.sourceId||item.className||item.tagName));
  }
  if(!body.children.length){sheet.remove();number--}
  // 마지막 두 페이지에 이어진 같은 표의 행을 나눠 마지막 장의 공백을 줄인다.
  const bodies=[...root.querySelectorAll('.sheet-body')];
  if(bodies.length>1){
    const a=bodies.at(-2),b=bodies.at(-1),ta=a.lastElementChild,tb=b.firstElementChild;
    const used=x=>x.lastElementChild.getBoundingClientRect().bottom-x.getBoundingClientRect().top;
    if(ta?.matches('table')&&tb?.matches('table')&&ta.dataset.sourceId===tb.dataset.sourceId){
      let limit=30;
      while(limit--&&used(b)<used(a)-70&&ta.querySelectorAll('tbody>tr').length>1){
        const row=ta.querySelector('tbody').lastElementChild;tb.querySelector('tbody').prepend(row);
        if(b.scrollHeight>b.clientHeight+1){ta.querySelector('tbody').append(row);break}
      }
    }
  }
  document.querySelectorAll('.page-number').forEach((n,i)=>n.textContent=String(i+1).padStart(2,'0')+' / '+String(number).padStart(2,'0'));
  root.querySelectorAll('[id]').forEach(n=>n.id='print-'+n.id);
  root.querySelectorAll('a[href^="#"]').forEach(a=>{const id=a.getAttribute('href').slice(1);if(root.querySelector('[id="print-'+id+'"]'))a.href='#print-'+id});
  document.body.classList.remove('paginating');
  document.body.classList.add('print-ready');
  if(!sync)await Promise.all([...root.querySelectorAll('img')].map(img=>img.decode().catch(()=>{})));
  window.printAudit={pages:number,blocks:[...root.querySelectorAll('[data-source-id]')].map(x=>x.dataset.sourceId),
    overflow:[...root.querySelectorAll('.sheet-body')].map((b,i)=>({page:i+1,overflow:b.scrollHeight-b.clientHeight,used:Math.round(b.lastElementChild?b.lastElementChild.getBoundingClientRect().bottom-b.getBoundingClientRect().top:0),available:b.clientHeight})),
    videos:[...root.querySelectorAll('[data-video-id]')].map(x=>x.dataset.videoId)};
  return window.printAudit;
};
document.querySelector('#print-button').addEventListener('click',async()=>{await window.preparePrint();window.print()});
window.addEventListener('beforeprint',()=>window.preparePrint(true));
window.addEventListener('afterprint',()=>document.body.classList.remove('print-ready'));
