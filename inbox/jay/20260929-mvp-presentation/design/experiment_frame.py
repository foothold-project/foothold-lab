# -*- coding: utf-8 -*-
"""실험 장(13~21쪽) 공통 틀 · 팀장 지시 2026-10-02.

「실험을 어떻게 했고 결과가 뭐다」만 있으면 「그래서 이걸 왜 한 거야?」가 나온다.
매 장 같은 자리에 네 칸 띠를 둔다: 문제 파악 → 가설·설계 → 실험 → 검증(얻은 것·잃은 것).
그 장이 맡은 칸이 켜지고, 나머지 칸에는 앞뒤 장의 한 줄이 들어가 사슬이 보인다.
개선을 말하는 장은 같은 화면에 «이전» 과 «이후» 를 같은 크기로 나란히 둔다.
전문가가 볼 코드 조각은 실제 파일의 실제 줄을 그대로 옮긴다 (경로·행 번호 표기).

숫자는 손으로 적지 않는다. 원자료(CSV · probe_manifest · per_env)에서 읽고 개수를 확인한다.
"""
import csv
import html
import io
import json
import os
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent          # 20260929-mvp-presentation
ROOT = HERE.parents[2]                                  # foothold-lab
MEDIA = '../../20260929-mvp-submission/source/media/'
GALLERY = '../../../../sim/eval/results/20260911-gallery/web/'

# ── 원자료 ─────────────────────────────────────────────────────
def rate(path, terrain=None):
    rows = []
    for f in sorted((ROOT / path).glob('**/d0.5/**/generalization_raw.csv')):
        rows.extend(r for r in csv.DictReader(io.open(f, encoding='utf-8-sig'))
                    if terrain is None or r['terrain'] == terrain)
    need = 300 if terrain else 4800
    assert len(rows) == need, (path, terrain, len(rows), need)
    return sum(r['overall_success'].lower() == 'true' for r in rows) / len(rows) * 100

def fall(model, probe):
    base = ROOT / 'sim/eval/results/20260929-axis2-fall' / model
    su = json.loads((base / 'probe_manifest.json').read_text(encoding='utf-8'))['summary'][probe]
    rows = json.loads((base / probe / 'per_env.json').read_text(encoding='utf-8'))
    mine = sum(1 for r in rows if r.get('fell'))
    assert mine == su['fell_count'] and su['envs'] == 64, (model, probe, mine, su)
    return su['fell_count']

def code_lines(rel, start, end):
    """실제 파일의 start~end 행 (1부터). 없는 줄을 적지 않는다."""
    lines = io.open(ROOT / rel, encoding='utf-8').read().split('\n')
    assert end <= len(lines), (rel, end, len(lines))
    picked = lines[start - 1:end]
    # 공통 들여쓰기 제거
    indent = min((len(l) - len(l.lstrip()) for l in picked if l.strip()), default=0)
    return [l[indent:] for l in picked]

# ── 조각 ───────────────────────────────────────────────────────
STEPS = ['문제 파악', '가설 설계', '실험', '검증', '그 다음 설정']

def strip(cells, on):
    out = '<div class="exp-strip" aria-label="문제 파악 · 가설 설계 · 실험 · 검증 · 그 다음 설정">'
    for i, (label, text) in enumerate(zip(STEPS, cells)):
        cls = 'exp-cell on' if i == on else 'exp-cell'
        out += f'<div class="{cls}"><small>{label}</small><p>{text}</p></div>'
        if i < len(STEPS) - 1:
            out += '<i class="exp-arrow"></i>'
    return out + '</div>'

def code_card(rel, start, end, caption=''):
    body = html.escape('\n'.join(code_lines(rel, start, end)))
    return (f'<figure class="exp-code"><figcaption>{rel}:{start}–{end}'
            + (f' · {caption}' if caption else '') + f'</figcaption><pre>{body}</pre></figure>')

def clip(src, caption, poster=None, verdict=''):
    po = f' poster="{poster}"' if poster else ''
    v = f'<b class="exp-verdict {"ok" if verdict == "ok" else "bad"}">{"통과" if verdict == "ok" else "실패"}</b>' if verdict else ''
    return (f'<figure class="film exp-clip"><video controls playsinline preload="metadata"{po} src="{src}" '
            f'data-autoplay="muted" muted loop></video><figcaption>{v}{caption}</figcaption></figure>')

def pair(a, b):
    return f'<div class="exp-pair">{a}{b}</div>'

# ── 장별 띠 ─────────────────────────────────────────────────────
def apply(slides):
    gap_nv = rate('sim/eval/results/20260921-nvidia-axis1', 'gap')
    gap_v1 = rate('sim/eval/results/maindata-v1/foothold-v1', 'gap')
    gap_d = rate('sim/eval/results/20260918-D-axis1', 'gap')
    gap_f = rate('sim/eval/results/20260920-F-axis1', 'gap')
    gap_v2 = rate('sim/eval/results/20260923-v2rs/v2g2-feetair01-iter3000', 'gap')
    w = {k: rate(f'sim/eval/results/20260923-v2rs/{k}-iter3000')
         for k in ('v2b-r', 'v2g2-feetair01', 'v2g-feetair1')}
    f = lambda m, p: fall(m, p)

    FRAMES = {
        '무엇을 더 가르칠지, 실패에서 찾았습니다': (0, [
            'NVIDIA 공식 정책이 10종 중 5지형에서 실패',
            '실패는 한 종류가 아닐 것이다',
            '성공률을 생존 · 전진 · 추종으로 쪼개 본다',
            '다섯 지형이 두 유형으로 갈린다',
            '유형마다 다른 처방 · 먼저 gap']),
        '실패 지형을 나누고, 먼저 시도할 과제를 골랐습니다': (1, [
            '생존부터 막히는 지형 / 살아도 못 가는 지형',
            '틈을 건너는 경험이 없다',
            'gap 을 첫 과제로 고른다',
            'gap · 디딤돌은 생존부터 · pit · rails · 고리는 전진 · 추종',
            'gap 을 첫 과제로 · 틈 경험 + 입력 정정']),
        '왜 첫 과제로 gap을 골랐을까요?': (2, [
            '기존 6종에는 끊긴 바닥이 없다',
            '틈 10 % 와 전진 명령으로 경험을 집중',
            'forward_gap 0.10 · vₓ 0.5~1.5 · vᵧ·ωz 0',
            '17쪽 · 틈 통과율과 명령 낙상으로 확인',
            '같은 설정으로 v1 학습']),
        '바닥을 못 찾았다는 정보도 올바르게 전달해야 했습니다': (0, [
            '바닥이 없으면 광선 값이 −1 로 들어간다',
            '「바닥 없음」을 +1 로 따로 알린다',
            'isfinite 검사 뒤 where 로 치환',
            '이후 모든 학습 · 평가에 같은 처리',
            '15쪽 설정 + 이 처리로 v1 학습']),
        '전진 보행은 개선됐습니다. 멈춤은 별도로 확인해야 했습니다': (3, [
            '15 · 16쪽 설정으로 v1 학습',
            '틈을 겪으면 틈을 건넌다',
            'v1 · 같은 평가 조건 · 모델당 4,800판',
            f'얻음 틈 {gap_nv:.1f}→{gap_v1:.1f} % · 잃음 정지 · 회전 낙상',
            '명령을 다시 열어 되찾자 (후보 D)']),
        '명령을 넓힌 후보에서는 gap 성능이 낮아졌습니다': (1, [
            f'v1 은 회전에서 {f("v1","turn")}/64 낙상',
            '명령을 다시 열면 되찾을 것이다',
            '후보 D · heading 과 정지 명령 개방',
            f'틈 {gap_v1:.1f}→{gap_d:.1f} % · 축 2 는 안 쟀다',
            '명령이 아니라 지형을 바꾼다 (omni_gap)']),
        '어느 방향으로 가도 틈을 만나도록 지형을 바꿨습니다': (2, [
            '명령을 열면 정면 틈을 안 만난다',
            '어느 방향이든 틈을 만나게 하자',
            'omni_gap + 최소 전진 0.4 (후보 F)',
            f'틈 {gap_f:.1f} % · 축 2 는 안 쟀다',
            '방향 · 정지 · 디딤을 함께 (v2)']),
        '방향·정지·디딤 경험을 함께 조정했습니다': (3, [
            '정지 · 회전 · 디딤을 함께 되찾아야 한다',
            '방향 · 정지 · 디딤 경험을 같이 넣는다',
            'omni_gap · heading · 정지 표집 0.1 · rails',
            f'정지 {f("v1","stop")}→{f("v2","stop")} · 유지 {f("v1","hold")}→{f("v2","hold")} · 회전 {f("v1","turn")}→{f("v2","turn")} /64',
            '디딤 보상 가중치 비교 → 21쪽']),
        '발을 들어 옮기는 경험을 보상 가중치로도 비교했습니다': (2, [
            'rails 에서 디딤이 약하다',
            '발 체공 보상 가중치가 디딤을 돕는다',
            'feet_air_time 0.01 / 0.1 / 1 · 같은 48칸',
            f'{w["v2b-r"]:.2f} / {w["v2g2-feetair01"]:.2f} / {w["v2g-feetair1"]:.2f} % · 0.1 채택',
            '두 잣대로 전체 재평가 → 결과']),
    }
    done = 0
    for s in slides:
        t = s['title']
        if t not in FRAMES:
            continue
        on, cells = FRAMES[t]
        s['body'] = strip(cells, on) + s['body']
        s['kind'] = (s.get('kind', '') + ' exp-page').strip()
        done += 1
    assert done == len(FRAMES), (done, len(FRAMES))

    # ── 17쪽 · 이전/이후를 같은 크기로 나란히, 아래 두 열과 같은 폭 ──
    s = next(x for x in slides if x['title'] == '전진 보행은 개선됐습니다. 멈춤은 별도로 확인해야 했습니다')
    nv_gap_poster = GALLERY + 'gap-v1-baseline.jpg' if (ROOT / 'sim/eval/results/20260911-gallery/web/gap-v1-baseline.jpg').exists() else None
    on17, cells17 = FRAMES[s['title']]
    head = strip(cells17, on17)   # 띠를 다시 만든다 (본문 자르기로 찾으면 첫 </div> 가 칸을 닫아 띠가 안 닫혔다 · 2026-10-02 실측)
    gained = ('<div class="exp-col"><h3 class="exp-h">얻은 것 · 틈을 건넌다</h3>'
              + pair(clip(GALLERY + 'gap-v1-baseline.mp4', '이전 · NVIDIA 공식 정책 · 1.0 m/s', nv_gap_poster, 'bad'),
                     clip(MEDIA + 'lineage-gap-v1.mp4', '이후 · v1 · 틈을 건넌다', MEDIA + 'lineage-gap-v1.jpg', 'ok'))
              + f'<p class="exp-num">틈 통과 <i>{gap_nv:.1f}%</i> → <b>{gap_v1:.1f}%</b>'
                f'<small>gap · 난이도 0.5 · 세 속도 300판 · 영상은 한 판의 예시</small></p></div>')
    rows = ''.join(f'<tr><td>{n}</td><td>{f("nvidia", p)} / 64</td><td><b>{f("v1", p)} / 64</b></td></tr>'
                   for n, p in [('정지 · 4초 전진 뒤 명령 0', 'stop'), ('유지 · 20초 내내 명령 0', 'hold'), ('회전 · 제자리 요레이트', 'turn')])
    lost = ('<div class="exp-col"><h3 class="exp-h">잃은 것 · 전진만 가르친 대가</h3>'
            + pair(clip('../assets/u206-axis2-stop-nvidia.mp4', '이전 · NVIDIA · 4초 뒤 정지 명령', '../assets/u206-axis2-stop-nvidia.jpg', 'ok'),
                   clip('../assets/u206-axis2-stop-v1.mp4', '이후 · v1 · 같은 정지 명령에 낙상', '../assets/u206-axis2-stop-v1.jpg', 'bad'))
            + '<table class="exp-table"><thead><tr><th>평지 명령 프로브 · 낙상 수</th><th>NVIDIA</th><th>v1</th></tr></thead>'
            + f'<tbody>{rows}</tbody></table></div>')
    s['body'] = (head + '<div class="exp-two">' + gained + lost + '</div>'
                 + '<div class="finding">학습에서 횡이동과 회전을 0으로 잠갔습니다. 틈은 건너게 됐지만, '
                   f'회전 명령에서는 {f("v1","turn")}판 모두 넘어집니다. 명령을 다시 열면 두 능력을 함께 가져갈 수 있을까?</div>'
                 + '<div class="condition">낙상 수는 64환경 · 평가 시드 42 의 평지 프로브 · 성공률이 아닙니다 · 영상은 각 한 판</div>')
    s['source'] = ('<a href="../../../../sim/eval/results/20260911-gallery/web/gap-v1-baseline.mp4" target="_blank" rel="noopener">'
                   'NVIDIA gap 1.0 m/s 갤러리 원본</a> · 축2 probe_manifest · per_env.json')

    # ── 15쪽 · 설정을 실제 코드로 (sim/policy/gap_env_cfg.py) ──
    s = next(x for x in slides if x['title'] == '왜 첫 과제로 gap을 골랐을까요?')
    old = '<p>기존 6종 90% + forward_gap 10%</p><p>첫 학습: 전진 0.5~1.5 m/s<br>횡이동 0 · 회전 0</p>'
    assert s['body'].count(old) == 1, '15쪽 설정 문단을 못 찾음'
    s['body'] = s['body'].replace(old, '<p>기존 6종 90% + forward_gap 10%</p>'
                                  + code_card('sim/policy/gap_env_cfg.py', 59, 60, '틈 지형 추가')
                                  + code_card('sim/policy/gap_env_cfg.py', 76, 79, '첫 학습의 명령 범위'))

    # ── 16쪽 · 미검출 처리를 실제 코드로 (sim/eval/gap_observations.py) ──
    s = next(x for x in slides if x['title'] == '바닥을 못 찾았다는 정보도 올바르게 전달해야 했습니다')
    old = '</div></div><p class="rr-bottom">'
    assert s['body'].count(old) == 1, '16쪽 비교 상자 끝을 못 찾음'
    s['body'] = s['body'].replace(old, '</div></div>' + code_card('sim/eval/gap_observations.py', 73, 80, '실제 구현 · miss_value = +1.0')
                                  + '<p class="rr-bottom">')
    return done
