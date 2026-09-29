"""공개 보고서의 전체 자료를 보존하는 외부 제출용 HTML 생성."""
from pathlib import Path
from bs4 import BeautifulSoup, NavigableString
from urllib.parse import urljoin, urlparse
import json, base64, mimetypes, re, hashlib
import xml.etree.ElementTree as ET
from submission_edit import edit_section,cover,PROJECT

ROOT=Path(__file__).resolve().parent
URL='https://foothold-project.vercel.app/research-20260928-v2-mvp-report'

REPLACE={
    'NVIDIA 는 1.5 m/s 에서 무너진다.':'NVIDIA는 1.5 m/s에서 종합 성공률이 크게 낮아진다. 낙상 여부는 생존 지표와 구분해 해석한다.',
    '임석헌이 만든':'선행 실험에서 개발한',
    '팀장 피드백':'검토 의견 반영', '팀장 지적으로 펼친다.':'검토를 거쳐 본문에 공개했다.',
    '그리고 팀장이 잡은 것.':'추가 검토에서 확인한 한계는 다음과 같다.',
    '팀장이 여러 번 「터지는 게 뭔가 이상하다」고 말했다. 나는 그것을 「어느 설정이 터뜨리나」 로 옮겨 읽었다.':'반복적인 학습 중단을 검토하면서 원인 탐색이 「어느 설정이 중단을 유발하는가」에 한정돼 있었음을 확인했다.',
    '팀장 요청은 「v2 넘는 거」였다.':'영상의 목적은 v2의 통과 사례를 보여 주는 것이었다.',
    '팀장 물음: 「원래 이렇게 4096 마리가 각 iter 에서 겹쳐서 걷는 걸 학습하고 그래?」 재 보고 답한다.':'학습 환경에서도 4,096대가 겹쳐 보이는 배치를 사용하는지 확인했다.',
    '팀장이':'검토자가', '팀장 지적':'검토 의견', '팀장:':'검토:', '팀장':'검토자',
    '6.5 초에서 넘어져 끝난다':'대표 장면 3.5초에서 넘어지는 모습이 보인다. 낙상 판정은 3.70초이며, 전체 영상 길이는 6.48초다. 이후 환경이 초기화된다',
    '오흥재':'FOOTHOLD', '임석헌':'선행 실험',
    '자빠진다':'넘어진다', '학습이 터진 기록':'학습 중단 기록', '터진 판':'중단된 실험',
    '\u2014':' · ', '씨앗':'시드',
}
TITLES={
    's1':'0. 연구 개요와 핵심 결과', 's2':'1. 평가 범위 · 학습과 미경험 지형의 구분',
    's3':'2. 미경험 지형 일반화 성능', 's4':'3. 성공률을 구성하는 네 조건',
    's5':'4. 지형별 성능', 's6':'5. 난이도 변화에 따른 성능',
    's7':'6. 연구 과정 · 문제, 가설, 실험과 검증', 's8':'7. 학습 방법과 레시피',
    's9':'8. 탐색 중단의 기준과 한계', 's10':'9. 명령 수행 능력 평가',
    's11':'10. 배포 모델과 참고 비교군', 's12':'11. 관측과 정책의 다음 연구 과제',
    's13':'12. 재현 방법', 's14':'13. 영상으로 확인하는 결과와 한계',
    's15':'14. 근거 자료',
}

def uri(path):
    path=Path(path)
    mime=mimetypes.guess_type(path.name)[0] or 'application/octet-stream'
    return f'data:{mime};base64,'+base64.b64encode(path.read_bytes()).decode()

def main():
    source=BeautifulSoup((ROOT/'source/report.html').read_bytes(),'html.parser')
    scenes={v['file']:v for v in json.loads((ROOT/'video-scenes.json').read_text(encoding='utf-8'))}
    inventory=json.loads((ROOT/'inventory.json').read_text(encoding='utf-8'))
    output=ROOT/'output';output.mkdir(exist_ok=True)
    edits=[];sections=[];mapping=[];excluded=[]
    for sec in source.select('section'):
        sid=sec['id']
        for i,node in enumerate(sec.find_all(recursive=False)):
            if node.name not in ['script','style','span']:
                node['data-source-id']=f'{sid}-b{i:03d}'
                mapping.append({'source_id':node['data-source-id'],'section':sid,'kind':node.name})
        for node in list(sec.select('script,style,.cb .bar,.cb-h,.vcmp-toolbar,.vcmp-controls')):
            node.decompose()
        if not edit_section(sec,edits,excluded):continue
        if sid=='s7':
            paragraph=sec.select_one('[data-source-id="s7-b124"]')
            old=paragraph.get_text();new='반복적인 학습 중단을 검토하면서 원인 탐색이 「어느 설정이 중단을 유발하는가」에 한정돼 있었음을 확인했다. 변한 설정만 비교하는 방법으로는 모든 실험에서 변하지 않은 변수의 영향을 찾기 어렵다.'
            paragraph.clear();paragraph.append(new)
            edits.append({'section':sid,'before':old,'after':new,'reason':'외부 독자용으로 주체를 정리하고 통제되지 않은 실험의 한계를 보존'})
        for node in list(sec.find_all(string=True)):
            if not isinstance(node,NavigableString):continue
            old=str(node);new=old
            for a,b in REPLACE.items():new=new.replace(a,b)
            if old!=new:
                edits.append({'section':sid,'before':old,'after':new});node.replace_with(new)
        sec.h2.clear();sec.h2.append(TITLES[sid])
        for a in sec.select('a[href]'):
            if not a['href'].startswith('#'):a['href']=urljoin(URL,a['href'])
        for img in sec.select('img'):
            name=Path(urlparse(img['src']).path).name
            img['data-original-src']=urljoin(URL,img['src']);img['src']=uri(ROOT/'source/media'/name)
            img['loading']='eager';img.attrs.pop('data-themed',None)
            p=img.find_parent('p')
            if p and len(p.select('img'))==1:
                p.name='figure';p['class']=['source-figure']
            variant=ROOT/'print-figures'/name
            if variant.exists():
                img['class']=img.get('class',[])+['original-figure-image']
                replacement=source.new_tag('img',attrs={'class':'print-figure-image','src':uri(variant),'alt':img.get('alt','')+' · 인쇄용 재배치','data-print-figure':name})
                geometry=ET.parse(variant).getroot()
                replacement['width']=geometry.get('width');replacement['height']=geometry.get('height')
                if name=='v2-difficulty-curve.svg':
                    replacement['data-part-one']=uri(ROOT/'print-figures/v2-difficulty-curve-1.svg')
                    replacement['data-part-two']=uri(ROOT/'print-figures/v2-difficulty-curve-2.svg')
                if name in ['v2-next-step.svg','v2-blown-runs.svg','v2-terrain-bars.svg']:
                    parts=[]
                    for i in range(1,4 if name=='v2-next-step.svg' else 3):
                        path=ROOT/'print-figures'/name.replace('.svg',f'-{i}.svg');geometry=ET.parse(path).getroot()
                        parts.append({'src':uri(path),'width':geometry.get('width'),'height':geometry.get('height')})
                    replacement['data-parts']=json.dumps(parts)
                img.insert_after(replacement)
        for table in sec.select('table'):
            if len(table.select('tr')[0].select('th,td'))>=7:table['class']=table.get('class',[])+['wide-table']
        for group in sec.select('.vcmp'):
            # Only source UI is replaced; every video and original caption remains.
            figures=[f.extract() for f in group.select('figure.vcmp-cell')]
            group.clear()
            group['style']=f'--media-cols:{min(len(figures),3)}'
            toolbar=source.new_tag('div',attrs={'class':'media-tools'})
            toolbar.append(BeautifulSoup('<button type="button" data-action="play">함께 재생</button><button type="button" data-action="reset">처음으로</button><label>배속 <select aria-label="영상 재생 속도"><option value="0.25">0.25×</option><option value="0.5">0.5×</option><option selected value="1">1×</option><option value="2">2×</option></select></label>','html.parser'))
            group.insert(0,toolbar)
            for fig in figures:group.append(fig)
        for video in sec.select('video'):
            name=Path(urlparse(video['src']).path).name;scene=scenes[name];fig=video.find_parent('figure')
            video['src']=scene['url'];video['data-local']='media/'+name;video['poster']=uri(ROOT/scene['still'])
            video['preload']='none';video['controls']='';video['playsinline']=''
            fig['data-video-id']=scene['id'];fig['data-video-file']=name
            still=source.new_tag('img',attrs={'class':'video-still','src':uri(ROOT/scene['still']),
                'alt':scene['selected']['reason']})
            video.insert_after(still)
            meta=source.new_tag('div',attrs={'class':'scene-meta'})
            link=source.new_tag('a',href=scene['url']+f'#t={scene["selected"]["seconds"]:g}')
            link.string=f'{scene["id"]} · 영상 보기';meta.append(link)
            meta.append(f' · 대표 장면 {scene["selected"]["seconds"]:g}초 / {scene["duration"]:g}초')
            fig.append(meta)
            note=source.new_tag('div',attrs={'class':'scene-note'});note.string=scene['selected']['reason'];fig.append(note)
            if name in ['lineage-gap-v1.mp4','lineage-gap-D-fail.mp4','lineage-gap-v2.mp4','regress-stairsinv-d09-v1.mp4','regress-stairsinv-d09-v2.mp4']:
                note.append(' 캡션의 전진 거리는 영상 전체의 최종값이며, 대표 장면 시각의 HUD 값과 다를 수 있다.')
            for t in scene['selected'].get('extra_seconds',[]):
                extra=source.new_tag('figure',attrs={'class':'training-extra'})
                extra.append(source.new_tag('img',src=uri(ROOT/'stills'/name.replace('.mp4',f'-{t:g}s.jpg'))))
                caption=source.new_tag('figcaption');caption.string=f'학습 진행 비교 · {t:g}초';extra.append(caption)
                fig.append(extra)
        if sid=='s15':
            note=source.new_tag('p',attrs={'class':'evidence-note'})
            note.string='이 절의 sim/, _out/, params/ 등은 저장소 또는 로컬 원자료 경로다. 해당 원자료 전체는 이 제출 파일에 포함되지 않는다. 공개 링크와 재현에 필요한 내부 경로를 구분해 읽어야 한다.'
            sec.h2.insert_after(note)
        sections.append(str(sec))
    toc=''.join(f'<a href="#{k}"><span>{i:02}</span>{re.sub(r"^\d+\. ","",v)}</a>' for i,(k,v) in enumerate(TITLES.items()))
    logo=uri(ROOT/'source/media/foothold-wordmark-ink.svg')
    cover_html=cover(logo)
    css=(ROOT/'report.css').read_text(encoding='utf-8')
    js=(ROOT/'report.js').read_text(encoding='utf-8')
    html=f'''<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>FOOTHOLD MVP 종합보고서</title><meta name="description" content="Unitree Go2의 미경험 험지 적응과 명령 수행 능력에 관한 실험 보고서"><style>{css}</style></head><body>
<nav class="topbar"><a class="brand" href="#top"><img src="{logo}" alt="FOOTHOLD"></a><span>MVP RESEARCH REPORT</span><a href="#contents">목차</a><a href="FOOTHOLD-MVP-summary.pdf">요약본</a><a href="FOOTHOLD-MVP.pdf">PDF</a><button id="print-button">인쇄</button></nav>
<main id="web-content">{cover_html}<header class="hero"><div class="eyebrow">RESEARCH OVERVIEW</div><h2 class="overview-title">험지 통과와 명령 수행을 함께 평가한다</h2><div class="abstract"><p>Unitree Go2의 미경험 험지 적응을 평가하고, 전진 보행 성능의 개선이 기본 명령 수행 능력과 어떻게 연결되는지 살폈다. 지형 통과와 명령 응답을 두 평가 축으로 나누고, 학습 지형·명령·보상 변경의 결과를 비교했다.</p><p>학습 여부를 다시 분류한 미경험 8종의 성능을 중심으로 결과를 제시한다. 성공률의 개선과 함께 속도 추종 실패, 회전 낙상, 희소 발판의 한계를 기록하며, 배포 모델의 성능과 아직 충족하지 못한 기준을 구분한다.</p></div><div class="hero-findings"><div><span>미경험 8종 · 세 속도 평균</span><strong>43.9<span class="arrow">→</span>88.5<span class="unit">%</span></strong><small>NVIDIA 기준선 → foothold-v2 · 난이도 0.5</small></div><div><span>보고서가 집중한 두 축</span><strong class="axis-label">험지 통과<br>명령 수행</strong><small>성공률의 증가와 남은 실패를 함께 기록</small></div></div></header>
<div class="edition-note">MVP 공식 제출본 · 결과 기준 2026.09.29<br>HTML은 영상을 재생하며, PDF는 실제 영상의 주요 장면과 원본 링크를 제공한다.</div>
<nav id="contents" class="contents"><h2>보고서의 흐름</h2><div>{toc}</div></nav>
<div class="report-body">{''.join(sections)}</div>
<footer class="report-end"><b>FOOTHOLD</b><p>원보고서와 근거 자료: <a href="{URL}">FOOTHOLD v2 종합보고서</a></p><p>이 보고서는 전체 프로젝트 중 시뮬레이션 보행 정책의 학습과 평가를 중심으로 MVP 결과를 제시한다. 결과 기준일: 2026.09.29.</p></footer></main>
<div id="print-root"></div><script>{js}</script></body></html>'''
    (output/'FOOTHOLD-MVP.html').write_bytes(html.encode('utf-8'))
    (ROOT/'editorial-changes.json').write_text(json.dumps(edits,ensure_ascii=False,indent=2),encoding='utf-8')
    check=BeautifulSoup(html,'html.parser')
    retained={n['data-source-id'] for n in check.select('.report-body [data-source-id]')}
    coverage={'source_sha256':inventory['source']['sha256'],'sections':len(check.select('.report-body section')),
        'tables':len(check.select('.report-body table')),'source_figures':len(check.select('.source-figure')),
        'videos':len(check.select('video')),'video_ids':[x['data-video-id'] for x in check.select('[data-video-id]')],
        'source_blocks':[n for n in mapping if n['source_id'] in retained],'excluded_blocks':excluded,'original_blocks':len(mapping),'editorial_changes':len(edits),'forbidden_names':{x:check.select_one('.report-body').get_text().count(x) for x in ['팀장','오흥재','임석헌']}}
    assert coverage['sections']==15 and coverage['source_figures']==8 and coverage['videos']==len(inventory['videos']),coverage
    assert len(retained)+len(excluded)==len(mapping)
    assert all(v==0 for v in coverage['forbidden_names'].values()),coverage
    (ROOT/'coverage.json').write_text(json.dumps(coverage,ensure_ascii=False,indent=2),encoding='utf-8')
    (ROOT/'project-metadata.json').write_text(json.dumps(PROJECT,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in coverage.items() if k not in ['source_blocks','video_ids','excluded_blocks']},ensure_ascii=False))

if __name__=='__main__':main()
