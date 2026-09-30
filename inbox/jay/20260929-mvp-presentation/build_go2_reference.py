"""공식 원본을 보존하고 출처가 있는 Go2 캐릭터 시트를 만든다."""
import hashlib
import html
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SOURCE = Path(sys.argv[1])
DEST = ROOT / 'assets/go2-reference'
DEST.mkdir(parents=True, exist_ok=True)
images = {r['i']: r for r in json.loads((SOURCE / 'manifest.json').read_text(encoding='utf-8-sig'))}
hero = 'https://oss-global-cdn.unitree.com/static/b666bad5b37742cb940f210eb097ac37.mp4'
follow = 'https://oss-global-cdn.unitree.com/static/1cededa1817a478381e62863e0a4bb3a.mp4'
detail = 'https://oss-global-cdn.unitree.com/static/b427f04cbbfd4b428b4e8dfe2a54436e.mp4'
rows = [
 ('3.jpg', 'front-render.jpg', images[3]['url'], None, '공식 제품 렌더', '정면 · 카메라와 하부 LiDAR'),
 ('hero-6.51.png', 'side-walk.png', hero, 6.51, '공식 영상 프레임', '측면 · 몸통 비율과 가느다란 다리'),
 ('follow-4.57.png', 'rear-walk.png', follow, 4.57, '공식 영상 프레임', '후면 · 보행 중 뒷몸통과 관절'),
 ('follow-3.68.png', 'rear-walk-wide.png', follow, 3.68, '공식 영상 프레임', '후면 보조 · 조금 더 먼 거리'),
 ('2.jpg', 'head-detail.jpg', images[2]['url'], None, '공식 제품 렌더', '머리 · 전면 세로 패널과 하부 하우징'),
 ('11.jpg', 'component-map.jpg', images[11]['url'], None, '공식 제품 도해', '전체 구성 · 관절과 센서 위치'),
 ('detail-0.1.png', 'body-three-quarter.png', detail, 0.1, '공식 제품 소개 영상 프레임', '기본 외형 · 상부 추가 모듈 없음'),
 ('detail-1.59.png', 'module-d435i.png', detail, 1.59, '공식 제품 소개 영상 프레임', '추가 모듈 · D435i 소개'),
 ('detail-3.83.png', 'module-hesai.png', detail, 3.83, '공식 제품 소개 영상 프레임', '추가 모듈 · HESAI 소개'),
]
manifest = []
for src, name, url, time, kind, label in rows:
    target = DEST / name
    shutil.copyfile(SOURCE / src, target)
    manifest.append(dict(file=name, title=label, kind=kind, source_page='https://www.unitree.com/go2/', source_url=url, capture_seconds=time, accessed='2026-09-30', sha256=hashlib.sha256(target.read_bytes()).hexdigest(), bytes=target.stat().st_size))
(DEST / 'sources.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')

def figure(i, cls=''):
    r = manifest[i]
    stamp = '' if r['capture_seconds'] is None else f" · {r['capture_seconds']:.2f}초"
    return f'''<figure class="{cls}"><a class="photo" href="../assets/go2-reference/{r['file']}" target="_blank"><img src="../assets/go2-reference/{r['file']}" alt="{html.escape(r['title'])}"></a><figcaption><b>{r['title']}</b><span>{r['kind']}{stamp} · <a href="{r['source_url']}" target="_blank" rel="noreferrer">원본</a></span></figcaption></figure>'''

page = '''<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>FOOTHOLD · Go2 캐릭터 시트</title><link rel="stylesheet" href="../design/presentation.css"><style>
*{box-sizing:border-box}body{margin:0;background:#0c1015;color:#eeeae3;font-family:var(--p-font),sans-serif}main{max-width:1480px;margin:auto;padding:36px}header{display:flex;justify-content:space-between;gap:24px;align-items:start;border-bottom:1px solid #42525b;padding-bottom:24px}header img{width:180px}h1{font-size:30px;margin:20px 0 8px}h2{font-size:23px;margin:0 0 12px}p{font-size:16px;line-height:1.7;color:#bdc8ce;margin:8px 0}a{color:#8fdfc7}nav{display:flex;gap:18px;font-size:14px;flex-wrap:wrap}.eyebrow{color:#8fdfc7;font-size:13px;letter-spacing:.12em}section{padding-top:30px}.views{display:grid;grid-template-columns:1fr 1.45fr 1fr;gap:18px}figure{margin:0;min-width:0}.photo{display:block;overflow:hidden;background:#030607;height:270px}.photo img{width:100%;height:100%;object-fit:cover}.front img{height:170%;object-fit:cover;transform:translateY(-37%)}.rear img{object-position:60% center}figcaption{padding:12px 0;font-size:14px;line-height:1.55}figcaption b,figcaption span{display:block}figcaption span{font-size:12px;color:#bac6cc;margin-top:4px}.rules{display:grid;grid-template-columns:1.3fr 1fr;gap:32px;border-top:1px solid #42525b;margin-top:14px;padding-top:24px}.rules ul{padding-left:20px;margin:0;line-height:1.9;font-size:15px}.rules strong{color:#8fdfc7}.aside{background:#17232a;padding:20px}.aside p{font-size:14px}.details{display:grid;grid-template-columns:1fr 1fr;gap:22px}.details .photo{height:360px}.details img{object-fit:contain}.support{display:grid;grid-template-columns:repeat(3,1fr);gap:20px}.support .photo{height:auto;aspect-ratio:16/9}.notice{border-left:3px solid #8fdfc7;padding-left:16px;margin-bottom:20px}footer{padding:30px 0 0;border-top:1px solid #42525b;margin-top:28px;font-size:13px;color:#bac6cc;line-height:1.7}@media(max-width:800px){main{padding:20px}header{display:block}nav{margin-top:18px}.views,.rules,.details,.support{grid-template-columns:1fr}.photo{height:auto;aspect-ratio:16/9}.front img{height:170%}.details .photo{height:auto;aspect-ratio:16/9}h1{font-size:26px}}
</style></head><body><main><div id="reference-sheet"><header><div><img src="../assets/foothold-lockup-compact-dark.svg" alt="FOOTHOLD"><h1>같은 Go2가 모든 컷을 걷도록</h1><p>Unitree 공식 이미지와 영상으로 고정하는 외형 기준</p></div><nav><a href="FOOTHOLD-film-storyboard.html">스토리보드</a><a href="../GO2-CHARACTER-REFERENCE.md">출처와 적용 기준</a><a href="../NEXT-PRODUCTION-STEPS.md">다음 제작 순서</a></nav></header><section><p class="eyebrow">UNITREE GO2 / OFFICIAL VISUAL REFERENCES</p><div class="views">'''
page += figure(0,'front') + figure(1) + figure(2,'rear')
page += '''</div></section><div class="rules"><div><h2>컷마다 유지할 외형</h2><ul><li><strong>머리:</strong> 전면 세로 패널과 그 아래 검은 LiDAR 하우징.</li><li><strong>몸통:</strong> 낮고 긴 회색 몸체, 둥근 상부 관절과 일정한 비율.</li><li><strong>다리:</strong> 굽은 가느다란 링크와 작은 검은 발고무. 두꺼운 부츠로 바꾸지 않음.</li><li><strong>후면:</strong> 실제 보행 프레임의 중앙 구조와 양쪽 관절을 참조.</li><li><strong>재질:</strong> 회색 표면의 미세한 거칠기. 젖은 곳만 국소 반사.</li></ul></div><div class="aside"><h2>참조 범위</h2><p>정면은 공식 제품 렌더, 측면과 후면은 공식 영상에서 직접 캡처했습니다. 정투상 도면이 아니므로 원근이나 보행 자세 차이를 치수 차이로 해석하지 않습니다.</p><p>영상 속 잔디·인물·센서 그래픽은 외형 참조에서 제외합니다. 현재 공식 페이지의 자료가 팀 보유 개체와 모든 세부 사양까지 같다는 뜻은 아닙니다.</p><p>기존 생성 컷은 연출 시안입니다. 이 시트에 맞춘 외형 보정은 다음 이미지 비교 단계에서 진행합니다.</p></div></div></div><section><h2>머리와 전체 구성</h2><div class="details">'''
page += figure(4) + figure(5)
page += '''</div><p>제품 도해의 기능 표기는 모델·구성별 차이가 있을 수 있습니다. 이 시트에서는 외형과 위치를 참조하며, 영상에 표시된 기능을 현재 연구의 구현 성과로 설명하지 않습니다.</p></section><section><h2>후면 보조와 기본 몸체</h2><div class="details">'''+figure(3)+figure(6)+'''</div></section><section><h2>추가 보유 모듈은 별도로 관리</h2><p class="notice">사용자 확인: Orin NX 16GB · D435i · HESAI-360 보유. 현재 장착 위치와 동시 장착 모습은 미확인입니다. 아래는 공식 옵션 소개 화면이며, 팀 장비의 실물 장착 사진이 아닙니다.</p><div class="details">'''+figure(7)+figure(8)+'''</div></section><footer>출처: <a href="https://www.unitree.com/go2/">Unitree Go2 공식 페이지</a> · 확인일 2026-09-30 · 이미지 권리: Unitree 및 원권리자.<br>원본 파일과 캡처 시점, SHA-256은 <a href="../assets/go2-reference/sources.json">sources.json</a>에 보존합니다. 이미지를 누르면 저장된 원본을 엽니다.</footer></main></body></html>'''
candidate = ROOT / 'assets/go2-reference/go2-side-neutral-v2.png'
if candidate.exists():
    section = '''<section id="generated-reference"><h2>배경 정리 후보 · 원본과 비교</h2><p>공식 측면 보행 프레임을 참조해 Higgsfield에 배경 정리를 요청한 결과입니다. 생성 이미지이므로 공식 원본과 구분합니다. 최종 캐릭터 시트 승인은 아직 하지 않았습니다.</p><a href="../assets/go2-reference/go2-side-neutral-v2.png"><img style="width:100%;height:auto" src="../assets/go2-reference/go2-side-neutral-v2.png" alt="공식 측면 프레임 기반 배경 정리 후보"></a><p>첫 다면 생성 시트는 별도 머리·센서 중복·다리와 후면 변형 때문에 제외했습니다. 여러 방향을 한꺼번에 발명하는 대신 공식 각도별 원본의 외형을 보존하는 방식으로 수정합니다.</p></section>'''
    page = page.replace('</div></div></div><section>', '</div></div></div>'+section+'<section>',1)
sunburst = ROOT / 'assets/go2-reference/go2-character-sunburst-v1.png'
if sunburst.exists():
    section = '''<section id="sunburst-sheet"><h2>Go2 캐릭터 시트 · Sunburst 시안</h2><p>공식 측면·정면·후면 자료 3장으로 생성한 4방향 전신 시트입니다. GPT Image 2.5 Sunburst · 2K · high · 1회 요청. 제작 참조 후보이며 공식 제품 사진이나 도면은 아닙니다.</p><a href="../assets/go2-reference/go2-character-sunburst-v1.png"><img style="width:100%;height:auto" src="../assets/go2-reference/go2-character-sunburst-v1.png" alt="Go2 정면 측면 후면 사선 캐릭터 시트"></a><p>검토: 첫 결과의 별도 머리와 중복 센서 오류는 보이지 않습니다. 발끝 마모와 후면 그릴 세부는 원본 그대로라고 확인할 수 없으며, 실제 제품의 세부 치수를 검증한 결과는 아닙니다. <a href="../GO2-SUNBURST-PROMPT.md">프롬프트·입력 자료</a></p></section>'''
    page = page.replace('</header>', '</header>'+section,1)
(ROOT / 'output/FOOTHOLD-Go2-character-sheet.html').write_text(page,encoding='utf-8')
