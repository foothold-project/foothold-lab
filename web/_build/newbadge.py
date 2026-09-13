# -*- coding: utf-8 -*-
"""NEW 배지 자동화 (빌드 [1.88] 단계).

  요구 (팀장 2026-08-12): 새로 등록된 문서에 New 가 뜨고, 일정 시간이 지나면
  저절로 사라질 것. 하드코딩 금지.

  어떻게
    · 문서의 «등록일» = 공개 저장소(foothold-site) git 에 그 파일이 **처음 추가된 날**.
      사람이 적는 날짜가 아니라 배포 이력이 원본이다.
    · 판정은 **보는 사람의 브라우저가 현재 시각으로** 한다. 빌드 시점이 아니라
      열어 본 시점 기준이므로, 기한이 지나면 재배포 없이 저절로 사라진다.
    · 창: 14일. (바꾸려면 아래 WINDOW_DAYS 하나만)

  적용 대상: 카드형 링크(<a class="doc ..."> 와 <a class="rcard ...">)만.
  상단 «← 표지로» 같은 내비게이션에는 달지 않는다.
"""
import io
import os
import re
import subprocess
import buildtime

WINDOW_DAYS = 7          # 수요일 공유 주기에 맞춘다 (팀장 컨펌 2026-08-12)

# v2 (팀장 컨펌 2026-08-12)
#   · 배지는 절대 위치가 아니라 «제목 뒤 인라인 칩»: 제목·썸네일을 가리는 문제 해결
#   · 등록 7일 이내 **그리고 그 방문자가 아직 안 연 문서**만 NEW (localStorage)
#     문서를 한 번 열면 그 사람에게서는 사라진다. «뭘 봐야 하지»에 답하는 것이 목적.
# v3 (2026-08-12): 방문 기록 키를 정규화한다.
#   버그: Vercel 이 cleanUrls 로 /questions.html → /questions 리다이렉트하므로
#   방문 기록은 «questions»(확장자 없음)로 남는데, 카드 판정은 href 의
#   «questions.html»로 비교했다. 영원히 못 만나서 NEW 가 안 꺼졌다 (팀장 실측).
#   해법: 양쪽 다 .html 을 뗀 이름으로 통일하고, 과거 저장분도 읽을 때 정규화한다.
# v4 (2026-08-12): 뒤로가기에서도 꺼지게 한다.
#   버그: 문서를 열고 «뒤로가기»로 목록에 돌아오면 브라우저가 목록을 bfcache 로
#   복원해서 스크립트가 다시 돌지 않는다. 처음 계산된 NEW 가 그대로 남았다 (팀장 실측).
#   해법: 판정을 함수로 빼고 pageshow(persisted) 에서 재판정. toggle 이라 끄기도 된다.
# v5 (2026-08-12): «봤다» 기록이 아예 안 되고 있었다 (진짜 원인, 팀장 재실측).
#   버그: 이 스크립트를 **카드가 있는 페이지에만** 주입했다. 방문 기록은 문서
#   페이지에서 남겨야 하는데, 문서 페이지에는 스크립트 자체가 없어서
#   아무리 열어 봐도 seen 이 쌓이지 않았다. 목록만 열면 자기 자신만 기록됐다.
#   해법: 전 페이지 무조건 주입. 카드 없는 페이지에서는 기록만 하고 끝난다.
# v6 (2026-09-01): 배지가 «붙긴 하는데 안 보이던» 것을 고친다.
#   버그: is-new 는 붙었는데 CSS 가 .t · .rt · .bt 같은 «안쪽 제목 클래스» 를
#   열거해서 그렸다. 회의 허브의 tl3 카드는 제목이 .tlt3 라 아무것도 안 그려졌다.
#   판정 3건이 참인데 화면에는 0건이었다. 오류도 경고도 없다.
#   해법: 열거를 없앤다. 스크립트가 제목 요소를 찾아 진짜 <span> 을 꽂는다.
#   아는 클래스가 없으면 «텍스트가 있는 첫 자식» 으로, 그것도 없으면 <a> 자신에.
#   새 카드 종류가 생겨도 목록을 고칠 필요가 없다.
MARK = '<!--newbadge:v7-->'

# ★ 2026-09-02. 옛 주입분 제거가 본문 18,000자를 먹은 적이 있다.
#   `<!--newbadge:vN-->[\s\S]*?</script>` 였는데, 표식만 남고 블록이 없는
#   페이지에서 «다음 </script>» 까지 지웠다. 그것이 본문 한참 아래의
#   남의 스크립트였다. 오류 없이 조용히 지운다 (원칙 2).
#
#   그래서 «지우려는 것이 정말 내 블록인가» 를 먼저 확인한다.
#   내 블록은 표식 바로 뒤에 <style> 로 시작하고 곧 </script> 로 끝난다.
#   확인이 안 되면 표식만 떼고 본문은 그대로 둔다.
_OLD = re.compile(r'<!--newbadge:v\d+-->([\s\S]*?)</script>\s*')
_SPAN_MAX = 6000        # 내 블록은 실측 1.4KB 안팎. 이 이상이면 남의 것이다


def strip_old(t):
    """옛 주입분만 지운다. 짝 없는 표식은 표식만 뗀다."""
    out, i = [], 0
    for m in _OLD.finditer(t):
        body = m.group(1)
        mine = len(body) <= _SPAN_MAX and ('span.fh-new' in body or 'fh_seen' in body)
        out.append(t[i:m.start()])
        if not mine:
            out.append(m.group(0)[len('<!--newbadge:v7-->'):])   # 표식만 뗀다
        i = m.end()
    out.append(t[i:])
    return ''.join(out)


def _kat_strip():
    """★ 답을 아는 입력. 남의 본문을 먹지 않는지 본다."""
    mine = MARK + '<style>span.fh-new{a:b}</style><script>x</script>'
    body = '<p>본문</p><script>남의것</script><p>더</p>'
    if strip_old(mine + body) != body:
        return False, '내 블록을 못 지웠다'
    if strip_old(MARK + body) != body:
        return False, '짝 없는 표식이 본문을 먹었다: %r' % strip_old(MARK + body)
    if strip_old(body) != body:
        return False, '표식이 없는데 건드렸다'
    big = MARK + '<style>span.fh-new{a:b}</style>' + 'x' * 9000 + '<script>y</script>'
    if 'x' * 9000 not in strip_old(big):
        return False, '너무 큰 범위를 지웠다'
    return True, ''

CSS_JS = MARK + '''<style>
span.fh-new{display:inline-block!important;margin-left:.45rem;vertical-align:.14em;
  background:var(--note)!important;color:#fff!important;font-size:.55rem!important;
  font-weight:800!important;letter-spacing:.1em!important;line-height:1.5!important;
  padding:.13rem .4rem!important;border-radius:3px!important;white-space:nowrap;
  text-transform:none!important;font-family:inherit}
</style>
<script>
(function(){
  var W=%d*86400000,KEY='fh_seen';
  var TITLE='.t,.rt,.bt,.tlt3,.ex3,.pk3,.k,.hb3,b,strong,h2,h3';
  function norm(s){s=(s||'').split('/').pop().split('#')[0].split('?')[0]
    .replace(/\\.html$/,'');return s||'index'}
  function host(a){
    var h=a.querySelector(TITLE);
    if(h)return h;
    for(var i=0;i<a.children.length;i++)
      if(a.children[i].textContent.trim())return a.children[i];
    return a;
  }
  function mark(a,on){
    var b=a.querySelector('.fh-new');
    if(!on){if(b)b.parentNode.removeChild(b);return}
    if(b)return;
    b=document.createElement('span');b.className='fh-new';b.textContent='NEW';
    host(a).appendChild(b);
  }
  function apply(){
    var seen={},raw={};
    try{raw=JSON.parse(localStorage.getItem(KEY)||'{}')}catch(e){}
    for(var k in raw)seen[norm(k)]=raw[k];
    seen[norm(location.pathname)]=Date.now();
    try{localStorage.setItem(KEY,JSON.stringify(seen))}catch(e){}
    document.querySelectorAll('a[data-added]').forEach(function(a){
      var t=Date.parse(a.getAttribute('data-added')+'T00:00:00');
      var tgt=norm(a.getAttribute('href'));
      var on=!isNaN(t)&&Date.now()-t>=0&&Date.now()-t<=W&&!seen[tgt];
      a.classList.toggle('is-new',on);
      mark(a,on);
    });
  }
  document.addEventListener('DOMContentLoaded',apply);
  window.addEventListener('pageshow',function(e){if(e.persisted)apply()});
})();
</script>
''' % WINDOW_DAYS


def first_added(site, fname, cache={}):
    """공개 저장소에서 파일이 처음 추가된 날짜(YYYY-MM-DD). 없으면 None(=이번에 새로 나감).

    ★ 회의록만 예외: 파일명의 «회의 날짜» 를 쓴다 (2026-08-25).
      지난 회의를 뒤늦게 정리해 올리면 «오늘 등록» 이 되어 8/13 회의가 NEW 로
      떴다. 회의는 그날 일어난 일이므로 올린 날이 아니라 열린 날이 기준이다.
      연구 문서·길잡이는 그대로 «올라온 날» 을 쓴다.
    """
    if fname in cache:
        return cache[fname]
    m = re.match(r'meeting-(\d{4})(\d{2})(\d{2})-', fname)
    if m:
        cache[fname] = '%s-%s-%s' % m.groups()
        return cache[fname]
    try:
        r = subprocess.run(['git', '-C', site, 'log', '--diff-filter=A',
                            '--format=%ad', '--date=short', '--', fname],
                           capture_output=True, text=True, timeout=20)
        lines = [x for x in (r.stdout or '').strip().split('\n') if x]
        cache[fname] = lines[-1] if lines else None
    except Exception:
        cache[fname] = None
    return cache[fname]


def main(vault, pages, site):
    import datetime
    today = buildtime.today().isoformat()
    n_pages, n_links = 0, 0
    # ★ 9/1 실측 (#75 가 아직 열려 있던 이유): 표지에는 NEW 가 2개 뜨는데
    #   허브 6장은 «전부 0» 이었다. 여기 목록이 `doc`·`rcard` 둘뿐이라
    #   허브가 쓰는 카드 클래스(ev3·sb3·pc3·ir3·dp3·wr3·ht3·w3t·fk3·w3b)를
    #   통째로 비켜갔다. 관문이 아니라 «이름 나열» 이 문제였다 (철칙 4).
    #   -> 카드형 앵커를 한 자리에 모아 두고, 새 허브 부품이 생기면 여기 넣는다.
    #   ★ 9/1 팀장 확인 요청: 표지 9칸에도 배지가 붙는가 -> 실측 «안 붙는다»
    #   (등록일 0 · NEW 0). 표지가 띠(.band)와 허브(.hubs a) 로 재설계되면서
    #   옛 .doc 카드가 사라졌는데 목록을 안 고쳤다.
    #   band 는 «내용이 바뀌는 것»(공지 · 다이제스트 · 산출물)이라 배지가 맞다.
    #   ★ 허브 6칸도 넣는다 (팀장 9/1): 「새로운 연구가 업로드 되면 NEW 로 알려주는 게
    #   사용자 입장에서 '아, 이 허브에 새 정보가 들어왔구나' 하고 인지하지 않을까」.
    #   맞다. 허브 자체가 새로운 게 아니라 «그 안에 새 글이 있다» 는 신호로 쓴다.
    #   그래서 허브 카드의 등록일은 허브 파일이 아니라 «그 허브가 담은 글 중
    #   가장 최근 것» 을 따른다 (hub_latest).
    #   ★ 9/1 두 번째 실측: 회의 허브만 배지가 0개였다. 팀장이 「회의에 NEW 떠서
    #   클릭했는데 안에서 어떤 게 새 것인지 모르겠다」 고 한 그 증상이다.
    #   원인 둘. ① 회의 허브가 쓰는 tl3 이 목록에 없었다.
    #   ② 정규식이 class 바로 뒤에 href 가 오는 것만 봤는데, tl3 은 사이에
    #   data-seat= 가, w3t 은 style= 이 낀다. 클래스를 늘려도 안 잡혔을 것이다.
    CARD_CLASSES = ('doc', 'rcard', 'ev3', 'sb3', 'pc3', 'ir3', 'dp3', 'wr3',
                    'ht3', 'w3t', 'fk3', 'w3b', 'band', 'tl3', 'q3', 'mt3')
    card = re.compile(r'<a\s+class="(?:%s)(?![a-z0-9-])[^"]*"[^>]*?\shref="([a-z0-9._-]+\.html)"'
                      % '|'.join(CARD_CLASSES))

    # 허브 카드 (표지의 9칸 중 6개). 전역바 링크와 구분되는 표시는 안쪽 <div class="k">.
    # 등록일은 허브 파일이 아니라 «그 허브가 담은 글 중 가장 최근 것» 이다.
    hubcard = re.compile(r'<a[^>]*href="(hub-[a-z]+\.html)"><div class="k">')

    def hub_latest(hubfile):
        try:
            import ia
        except Exception:
            return None
        key = next((h[0] for h in ia.HUBS if h[3] == hubfile), None)
        if not key:
            return None
        ds = [first_added(site, fn) for fn, v in ia.VAULT_PAGE.items()
              if v and v[0] == key]
        ds = [d for d in ds if d]
        return max(ds) if ds else None


    for f in pages:
        p = os.path.join(vault, f)
        if not f.endswith('.html') or not os.path.exists(p):
            continue
        t = io.open(p, encoding='utf-8').read()

        # 이전 주입분(v1 포함) 제거 후 다시 (내용이 바뀌어도 한 벌만 남게)
        t = strip_old(t)
        t = re.sub(r'\s*data-added="[0-9-]{10}"', '', t)
        # 하드코딩된 New 배지는 걷어낸다. 이제 날짜가 정한다
        t = t.replace('<span class="badge">New</span>', '')

        def stamp(m):
            target = m.group(1)
            d = first_added(site, target) or today
            return m.group(0).replace('href="', 'data-added="%s" href="' % d, 1)

        t2, k = card.subn(stamp, t)
        def hstamp(mm):
            d = hub_latest(mm.group(1)) or today
            return mm.group(0).replace('href="',
                                       'data-added="%s" href="' % d, 1)
        t2, k2 = hubcard.subn(hstamp, t2)
        k += k2
        # ★ 옛 판이 남아 있으면 지운다. v5 CSS 는 «안쪽 제목 클래스» 를 열거해
        #   그렸고 새 카드 종류에서 아무것도 안 그렸다. 남겨 두면 새 판과 겹친다.
        t2 = strip_old(t2)
        # ★ 카드가 없어도 주입한다: 문서 페이지에서 «봤다»가 기록되어야 목록의 NEW 가 꺼진다
        if '</head>' in t2:
            t2 = t2.replace('</head>', CSS_JS + '</head>', 1)
            n_links += k
            n_pages += 1
        io.open(p, 'w', encoding='utf-8', newline='\n').write(t2)

    print('  카드 링크 %d개에 등록일 부여 · 방문 기록 스크립트 %d페이지(전부) · 창 %d일'
          % (n_links, n_pages, WINDOW_DAYS))
    return True
