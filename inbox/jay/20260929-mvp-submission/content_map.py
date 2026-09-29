"""최종 인쇄 DOM에서 절·그림·영상의 페이지 대응표를 만든다."""
from pathlib import Path
from bs4 import BeautifulSoup
import json
ROOT=Path(__file__).resolve().parent

def main():
    h=BeautifulSoup((ROOT/'output/FOOTHOLD-MVP.html').read_bytes(),'html.parser')
    source=BeautifulSoup((ROOT/'source/report.html').read_bytes(),'html.parser');sheets=h.select('#print-root .sheet')
    def pages(selector):return ', '.join(str(i+1) for i,s in enumerate(sheets) if s.select_one(selector))
    lines=['# 원문과 제출본 자료 대응표','','> 분류: 운영','> 작성: Codex · 2026-09-29 12:19','> 근거: 보존 원문과 최종 HTML의 인쇄 DOM 직접 집계','> 요지: 원문의 절·그림·영상이 제출 PDF의 어디에 있는지 연결한다.','> 상태: `확인됨`','> 판: v1.0','','원문: https://foothold-project.vercel.app/research-20260928-v2-mvp-report','','## 본문 16절','','| 원문 절 | 제출 PDF 쪽 | 표 | 그림 | 영상 |','|---|---|---:|---:|---:|']
    for s in source.select('section'):
        sid=s['id'];title=s.h2.get_text(' ',strip=True).replace('|','·')
        lines.append(f'| {title} | {pages("[data-source-id^="+sid+"-]")} | {len(s.select("table"))} | {len(s.select("img"))} | {len(s.select("video"))} |')
    lines+=['','## 본문 그림 8개','','| 원본 파일 | PDF 쪽 |','|---|---|']
    for im in h.select('#web-content .source-figure img[data-original-src]'):
        sid=im.find_parent(attrs={'data-source-id':True})['data-source-id'];name=im['data-original-src'].split('/')[-1]
        lines.append(f'| {name} | {pages("[data-source-id="+sid+"]")} |')
    lines+=['','## 영상 22편과 대표 장면','','PDF에는 각 영상의 실제 주요 장면 22장, 학습 진행 비교 2장, 원본 링크가 들어 있다.','', '| 영상 | 파일 | 대표 시각 | PDF 쪽 |','|---|---|---:|---|']
    for v in json.loads((ROOT/'video-scenes.json').read_text(encoding='utf-8')):
        lines.append(f'| {v["id"]} | {v["file"]} | {v["selected"]["seconds"]:g}초 | {pages("[data-video-id="+v["id"]+"]")} |')
    lines+=['','## 판 이력','','| 판 | 날짜 | 내용 |','|---|---|---|',f'| v1.0 | 2026-09-29 | 최종 {len(sheets)}쪽 PDF의 절·그림·영상 대응 집계 |','']
    (ROOT/'CONTENT-MAP.md').write_bytes('\n'.join(lines).encode())
    print('content map created')

if __name__=='__main__':main()
