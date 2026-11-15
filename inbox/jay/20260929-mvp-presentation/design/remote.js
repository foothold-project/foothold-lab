/* FOOTHOLD 폰 리모트 · Supabase Realtime Broadcast.
   2026-10-02 팀장 지시: 「모바일에서 스크립트 띄우고 좌우 넘기면 PC 화면에서 슬라이드 넘어가게」.
   발표는 학원 노트북의 브라우저(이 덱 페이지)에서, 폰은 같은 사이트의 대본 페이지에서.
   둘 다 같은 «방 코드» 로 한 채널에 붙는다. 서버 코드 없음. 상태는 {index, step} 하나.

   설정은 window.FOOTHOLD_REMOTE = {url, key} (묶음 생성기가 넣는다. key 는 공개용 publishable key).
   역할은 window.FOOTHOLD_REMOTE_ROLE: 'deck' (노트북) | 'phone' (대본 페이지).
   방 코드: ?room=xxxx 또는 입력창. 마지막 방은 localStorage 에 남는다. */
(function(){
  const cfg=window.FOOTHOLD_REMOTE||null;
  const role=window.FOOTHOLD_REMOTE_ROLE||'deck';
  const me=Math.random().toString(36).slice(2,8);
  let room='',client=null,channel=null,status='꺼짐',applying=false;
  const listeners=[];
  function setStatus(s){status=s;listeners.forEach(f=>{try{f(s,room)}catch(e){}})}
  function lib(cb){
    if(window.supabase&&window.supabase.createClient)return cb();
    const s=document.createElement('script');
    s.src='https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2/dist/umd/supabase.min.js';
    s.onload=cb;s.onerror=()=>setStatus('라이브러리 못 받음');document.head.appendChild(s);
  }
  function clean(r){return String(r||'').trim().toLowerCase().replace(/[^a-z0-9-]/g,'').slice(0,24)}
  function connect(r){
    r=clean(r);if(!cfg||!cfg.url||!cfg.key){setStatus('설정 없음');return}
    if(!r){setStatus('방 코드 없음');return}
    room=r;try{localStorage.setItem('foothold-room',room)}catch(e){}
    setStatus('연결 중');
    lib(()=>{
      if(!client)client=window.supabase.createClient(cfg.url,cfg.key,{realtime:{params:{eventsPerSecond:20}}});
      if(channel){try{client.removeChannel(channel)}catch(e){}channel=null}
      channel=client.channel('deck-'+room,{config:{broadcast:{self:false}}});
      channel.on('broadcast',{event:'goto'},({payload})=>{
        if(!payload||payload.from===me)return;
        applying=true;
        try{if(typeof window.__remoteApply==='function')window.__remoteApply(payload)}finally{applying=false}
      });
      channel.on('broadcast',{event:'hello'},({payload})=>{
        // 상대가 들어오면 지금 상태를 한 번 보내 준다 (덱이 기준)
        if(role==='deck'&&payload&&payload.from!==me&&window.footholdDeck){const st=window.footholdDeck.state;send(st.current,st.step)}
      });
      channel.subscribe(st=>{
        if(st==='SUBSCRIBED'){setStatus('연결됨');channel.send({type:'broadcast',event:'hello',payload:{from:me,role}})}
        else if(st==='CHANNEL_ERROR')setStatus('채널 오류');
        else if(st==='TIMED_OUT')setStatus('시간 초과');
        else if(st==='CLOSED')setStatus('닫힘');
      });
    });
  }
  function send(index,step){
    if(!channel||applying)return;
    channel.send({type:'broadcast',event:'goto',payload:{index,step,from:me,role,t:Date.now()}});
  }
  function disconnect(){if(channel&&client){try{client.removeChannel(channel)}catch(e){}}channel=null;setStatus('꺼짐')}
  window.footholdRemote={connect,disconnect,send,onStatus:f=>listeners.push(f),
    get room(){return room},get status(){return status},get applying(){return applying},get enabled(){return !!(cfg&&cfg.url&&cfg.key)}};
  // 자동 연결: ?room= 이 있으면 바로, 없으면 마지막 방이 있어도 «자동으로는» 안 붙는다 (발표 중 엉뚱한 방에 붙지 않게)
  const q=new URLSearchParams(location.search);
  if(q.get('room'))connect(q.get('room'));
})();
