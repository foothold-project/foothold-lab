# -*- coding: utf-8 -*-
"""Isaac Sim 학습 지형 장 · 「한 대의 경험을, 4,096개 환경에서 함께 모읍니다」 뒤,
「무엇을 더 가르칠지, 실패에서 찾았습니다」 앞.

팀장 지시 2026-10-02: 「12쪽(4,096 환경)과 13쪽(실패 지형) 사이에 Isaac Sim 학습 지형들을
퍼스펙 뷰로 보여 주는 장을 넣어라. 청자가 '아, 이런 곳을 학습하는구나' 하고 뒤 실험을 이해하게.」

덱에 거는 법 (공용 파일은 안 건드린다):
  FOOTHOLD_DECK_EXTRA=design.terrain_catalog FOOTHOLD_DECK_EXTRA_CSS=terrain_catalog.css \
  FOOTHOLD_DECK_OUT=output/preview-terrain.html python build_presentation.py
그림 만들기 (av · numpy · PIL 필요 · 빌드에는 필요 없다):
  python -m design.terrain_catalog --assets

왼쪽 여덟 종 = v2 가 학습한 지형 (보고서 §7 「학습 지형 여덟 종」 · models/foothold-v2.env.yaml sub_terrains).
오른쪽 여덟 종 = 어느 판도 학습 안 한 지형 (보고서 §1 「네 묶음」).
숫자(비중 · 난이도 · 속도 · 판 수 · 시드)는 손으로 적지 않고 yaml · run_manifest · 원CSV 에서 읽어 assert 한다.

그림: sim/eval/results/20260928-v2-gallery 의 <지형>-v1 컷(v2 · 1.0 m/s · d0.5).
  ★ posters/<지형>-v1.jpg 는 첫 프레임이라 pyramid_stairs · hf_pyramid_slope(_inv) 에서 지형이 안 보인다
    (출발판 위에 서 있다 · gallery_build.py poster_from 이 count_frames 실패로 0번을 집었다).
    sim/eval/make_posters.py 가 적어 둔 규칙 그대로 「HUD 아래 질감(밝기 표준편차)이 가장 큰 프레임」을
    같은 컷의 18~82 % 구간에서 고른다. HUD 패널(y<310 · 실측 305)은 잘라 낸다. 폭은 그대로.
  gap 은 평가용 MeshGap 컷이다. v2 학습은 omni_gap(ring) 이라 캡션에 그렇게 적는다 (보고서 §1 「친척」).
"""
import csv
import html
import importlib.util
import json
import re
import sys
from pathlib import Path

from .intro_story import make, src
from .research_revision import NAMES, ROUGH, UNSEEN, ROOTS, _read

HERE = Path(__file__).resolve().parent.parent          # 덱 폴더
ROOT = HERE.parents[2]                                   # 저장소
ASSETS = HERE / 'assets/terrain-persp'
GALLERY = ROOT / 'sim/eval/results/20260928-v2-gallery'
REPORT = '../../../../docs/research/20260928-v2-mvp-report.md'

TITLE = 'Isaac Sim 에는 이런 지형들이 있습니다'
AFTER = '한 대의 경험을, 4,096개 환경에서 함께 모읍니다'
BEFORE = '무엇을 더 가르칠지, 실패에서 찾았습니다'

HUD_BOTTOM = 310      # 포스터 실측: HUD 패널 어두운 띠 y 28~305
LONG = 960            # 긴 변
QUALITY = 88
TRAINED = ROUGH + ['gap', 'rails']           # 왼쪽 여덟 종 (그림 이름 · 학습 이름은 _train_name)
TRAIN_NAME = {'gap': 'omni_gap'}             # 학습 yaml 의 이름이 그림 이름과 다른 것
FROM_TAG = {'gap': 'v1 부터', 'rails': 'v2 부터'}


# ── 원자료 읽기 ───────────────────────────────────────────────
def _sub_terrains(tag):
    """models/foothold-<tag>.env.yaml 의 sub_terrains → {이름: {'proportion', 'line'}}, 블록 (시작행, 끝행)."""
    y = (ROOT / f'models/foothold-{tag}.env.yaml').read_text(encoding='utf-8').splitlines()
    i = next(k for k, l in enumerate(y) if l.strip() == 'sub_terrains:')
    out, name, end = {}, None, i
    for k in range(i + 1, len(y)):
        l = y[k]
        if l.strip() and (len(l) - len(l.lstrip())) <= 6:
            break
        end = k
        indent = len(l) - len(l.lstrip())
        if indent == 8 and l.strip().endswith(':'):
            name = l.strip()[:-1]
            out[name] = {'line': k + 1}
        elif name and l.strip().startswith('proportion:'):
            out[name]['proportion'] = float(l.split(':')[1])
    return out, i + 1, end + 1


def _eval_terrains():
    """sim/eval/terrains.py 를 isaaclab 없이 임포트해 rough6 · unseen10 이름과 행 번호를 읽는다."""
    path = ROOT / 'sim/eval/terrains.py'
    spec = importlib.util.spec_from_file_location('foothold_eval_terrains', path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    lines = path.read_text(encoding='utf-8').splitlines()
    line = {k: next(n + 1 for n, l in enumerate(lines) if l.startswith(k + ' = '))
            for k in ('ROUGH6_TERRAIN_NAMES', 'TERRAIN_SETS')}
    ev = (ROOT / 'sim/eval/eval_generalization.py').read_text(encoding='utf-8').splitlines()
    line['terrain_set_arg'] = next(n + 1 for n, l in enumerate(ev) if '"--terrain_set"' in l)
    return list(mod.ROUGH6_TERRAIN_NAMES), list(mod.TERRAIN_NAMES), line


def _eval_conditions():
    """v2 배포본 평가 원자료(d0.5 · 세 속도)에서 난이도 · 속도 · 판 수 · 시드를 읽는다."""
    root = ROOTS['v2']
    rows = _read(root)
    assert len(rows) == 4800, len(rows)
    terrains = sorted({r['terrain'] for r in rows})
    assert set(terrains) == set(TRAINED) | set(UNSEEN), terrains
    seeds, eps, sets, diffs, speeds, cells = set(), set(), set(), set(), set(), {}
    for m, raw in _manifests(root):
        seeds.add(m['seed']); eps.add(m['episodes_per_terrain']); sets.add(m['terrain_set'])
        diffs.add(tuple(m['terrain_difficulty_range'])); speeds.add(float(m['command_vx_mps']))
        with raw.open(encoding='utf-8-sig', newline='') as h:        # 판 수는 매니페스트가 아니라 원CSV 를 센다
            for r in csv.DictReader(h):
                cells[(r['terrain'], float(m['command_vx_mps']))] = cells.get((r['terrain'], float(m['command_vx_mps'])), 0) + 1
    assert seeds == {42} and eps == {100} and sets == {'rough6', 'unseen10'}, (seeds, eps, sets)
    assert diffs == {(0.5, 0.5)}, diffs
    assert sorted(speeds) == [0.5, 1.0, 1.5], speeds
    assert len(cells) == 48 and set(cells.values()) == {100}, (len(cells), set(cells.values()))
    assert {t for t, _ in cells} == set(terrains)
    return dict(difficulty=0.5, speeds=sorted(speeds), episodes=100, seed=42)


def _manifests(root):
    for f in sorted(root.glob('*/*/*/run_manifest.json')):
        m = json.loads(f.read_text(encoding='utf-8'))
        if float(m['terrain_difficulty_range'][0]) == 0.5 and float(m['command_vx_mps']) in (.5, 1., 1.5):
            yield m, f.parent / 'generalization_raw.csv'


def _frames_index():
    idx = json.loads((ASSETS / 'index.json').read_text(encoding='utf-8'))
    for t in TRAINED + UNSEEN:
        assert t in idx and (ASSETS / f'{t}.jpg').exists(), f'그림 없음: {t} (python -m design.terrain_catalog --assets)'
        assert idx[t]['command_vx_mps'] == 1.0 and idx[t]['difficulty'] == 0.5 and idx[t]['crop_top'] == HUD_BOTTOM, idx[t]
    sizes = {tuple(v['size']) for v in idx.values()}
    assert len(sizes) == 1, sizes
    return idx, sizes.pop()


# ── 그림 굽기 (av · numpy · PIL) ───────────────────────────────
def build_assets():
    import av
    import numpy as np
    from PIL import Image
    ASSETS.mkdir(parents=True, exist_ok=True)
    index = {}
    for t in TRAINED + UNSEEN:
        cut = GALLERY / f'cuts/{t}-v1'
        clip = cut / f'{t}-v1.trim.mp4'
        head = '\n'.join((cut / f'{t}-v1.trace.csv').read_text(encoding='utf-8').splitlines()[:6])
        speed = float(re.search(r'command_vx_mps = ([0-9.]+)', head).group(1))
        diff = float(re.search(r'difficulty = ([0-9.]+)', head).group(1))
        with av.open(str(clip)) as box:
            stream = box.streams.video[0]
            total = stream.frames
            assert total > 0, clip
            lo, hi = int(total * .18), int(total * .82)
            best = (-1.0, None, -1)
            for n, frame in enumerate(box.decode(stream)):
                if lo <= n <= hi and (n - lo) % 6 == 0:
                    im = frame.to_image()
                    tex = float(np.asarray(im.convert('L'), dtype=np.float32)[HUD_BOTTOM:].std())
                    if tex > best[0]:
                        best = (tex, im, n)
        tex, im, n = best
        assert im is not None and im.size == (1920, 1080), (t, im and im.size)
        crop = im.crop((0, HUD_BOTTOM, 1920, 1080))
        w, h = LONG, round(crop.height * LONG / crop.width)
        crop.resize((w, h), Image.LANCZOS).save(ASSETS / f'{t}.jpg', quality=QUALITY)
        index[t] = dict(clip=str(clip.relative_to(ROOT)).replace('\\', '/'), frame=n, frames=total,
                        texture=round(tex, 1), command_vx_mps=speed, difficulty=diff,
                        crop_top=HUD_BOTTOM, size=[w, h])
        print(f'{t:22s} frame {n:3d}/{total}  texture {tex:5.1f}  -> {w}x{h}')
    (ASSETS / 'index.json').write_text(json.dumps(index, ensure_ascii=False, indent=1), encoding='utf-8')
    print('->', ASSETS / 'index.json')


# ── 장 ───────────────────────────────────────────────────────
def _label(t):
    """NAMES 의 한글 이름 · 영문 id. NAMES 에 영문이 이미 붙은 것(틈 · gap)은 한글만 떼어 쓴다."""
    ko = NAMES[t]
    if ' · ' in ko and ko.rsplit(' · ', 1)[1] == t:
        ko = ko.rsplit(' · ', 1)[0]
    return ko


def _tile(t, share=None, train=None):
    ko = _label(t)
    en = train if train and train != t else t
    if train and train != t:
        en = f'{train} · 그림은 평가 {t}'
    badges = ''
    if share is not None:
        badges += f'<i class="tc-share">{share * 100:g} %</i>'
    if t in FROM_TAG and train is not None:
        badges += f'<em class="tc-from">{FROM_TAG[t]}</em>'
    return (f'<figure class="tc-tile"><div class="tc-pic"><img src="../assets/terrain-persp/{t}.jpg" '
            f'alt="{html.escape(ko)} 지형 · v2 1.0 m/s 컷">{badges}</div>'
            f'<figcaption><span>{html.escape(ko)}</span><small>{html.escape(en)}</small></figcaption></figure>')


def slide():
    v2, y_start, y_end = _sub_terrains('v2')
    v1, _, _ = _sub_terrains('v1')
    rough6, unseen10, line = _eval_terrains()
    assert rough6 == ROUGH, rough6
    assert set(unseen10) - {'gap', 'rails'} == set(UNSEEN) and len(unseen10) == 10, unseen10
    assert list(v2) == ROUGH + ['omni_gap', 'rails'], list(v2)
    assert list(v1) == ROUGH + ['forward_gap'], list(v1)
    assert abs(sum(v['proportion'] for v in v2.values()) - 1.0) < 1e-9
    ev = _eval_conditions()
    idx, (iw, ih) = _frames_index()

    left = ''.join(_tile(t, v2[TRAIN_NAME.get(t, t)]['proportion'], TRAIN_NAME.get(t, t)) for t in TRAINED)
    right = ''.join(_tile(t) for t in UNSEEN)
    speeds = ' / '.join(f'{s:g}' for s in ev['speeds'])
    body = (
        '<div class="technical-world tc-world">'
        '<section class="tc-group tc-trained"><h3><b>학습 8종</b><span>v2 가 배운 지형 · NVIDIA 6종 + v1 gap + v2 rails</span></h3>'
        f'<div class="tc-grid">{left}</div></section>'
        '<section class="tc-group tc-unseen"><h3><b>미경험 8종</b><span>어느 판도 학습에 넣지 않음 · 시험만</span></h3>'
        f'<div class="tc-grid">{right}</div></section>'
        '<aside class="tc-panel"><small>Isaac Sim · 학습 지형과 시험 지형</small>'
        '<p class="tc-easy">로봇은 이런 바닥들 위에서<br>넘어지며 배웁니다.</p>'
        '<p class="tc-easy tc-step1">오른쪽 여덟 종은 학습에<br>한 번도 넣지 않고, 시험만 봅니다.</p>'
        '<dl class="tc-hard">'
        f'<div><dt>학습</dt><dd>출발 정책 NVIDIA 의 rough6 → v1 + forward_gap → v2 + omni_gap · rails · 그림 안 숫자가 학습 비중 · models/foothold-v2.env.yaml:{y_start}–{y_end}</dd></div>'
        '<div class="tc-step1"><dt>미경험</dt><dd>NVIDIA · v1 · v2 어느 판도 학습에 넣지 않은 8종 · 보고서 §1 「네 묶음」</dd></div>'
        f'<div><dt>평가</dt><dd>terrain_set rough6 · unseen10 (sim/eval/terrains.py:{line["ROUGH6_TERRAIN_NAMES"]} · :{line["TERRAIN_SETS"]} · eval_generalization.py:{line["terrain_set_arg"]}) · '
        f'난이도 d{ev["difficulty"]:g} · {speeds} m/s · 지형·속도당 {ev["episodes"]}판 · 시드 {ev["seed"]}</dd></div>'
        '<div><dt>명령</dt><dd>범위는 「두 잣대」 장의 설정 그대로</dd></div>'
        '</dl>'
        f'<p class="tc-prov">그림: 20260928-v2-gallery 의 v2 · 1.0 m/s · d0.5 컷 16편에서 지형이 가장 잘 보이는 프레임 · HUD 제외 · {iw}×{ih} · 컷마다 카메라 거리가 달라 축척은 같지 않습니다</p>'
        '</aside></div>')
    spoken = ('학습에 들어가기 전에, Isaac Sim 안의 바닥들부터 보겠습니다. 왼쪽 여덟 종이 v2 가 학습한 지형입니다. '
              '출발 정책인 NVIDIA 가 배운 여섯 종에, v1 이 틈을, v2 가 턱을 더했습니다. 그림 안 숫자는 학습에서 그 지형이 차지한 비중입니다. '
              '로봇은 이런 바닥들 위에서 넘어지며 배웁니다. '
              '(클릭) 오른쪽 여덟 종은 학습에 한 번도 넣지 않고 시험만 봅니다. '
              f'뒤에 나오는 성공률은 이 열여섯 종을 난이도 {ev["difficulty"]:g}, 세 속도, 지형과 속도마다 {ev["episodes"]}판씩 같은 조건으로 잰 것입니다. '
              '명령 범위는 두 잣대 장의 설정 그대로입니다.')
    note = ('그림은 20260928-v2-gallery 의 v2 · 1.0 m/s · d0.5 컷에서 HUD 아래 질감이 가장 큰 프레임을 골라 HUD 를 잘라 낸 것이다(assets/terrain-persp/index.json 에 프레임 번호). '
            '포스터(첫 프레임)는 pyramid_stairs · hf_pyramid_slope(_inv) 에서 출발판만 보여 쓰지 않았다. '
            'gap 그림은 평가용 MeshGap 이고 v2 학습 지형은 omni_gap(ring) 이라 캡션에 적었다. 비중은 foothold-v2.env.yaml sub_terrains 의 proportion 이다. '
            '난이도·속도·판 수·시드는 v2 배포본 평가의 run_manifest.json 에서 읽었다.')
    return make('학습과 평가', TITLE, body, spoken,
                src('학습 지형 여덟 종 §7 · 네 묶음 §1 · MVP 보고서', REPORT),
                kind='intro authored technical-page terrain-page', steps=1, note=note)


def apply(slides):
    titles = [s['title'] for s in slides]
    assert TITLE not in titles
    i = titles.index(AFTER)
    assert titles.index(BEFORE) > i, (AFTER, BEFORE)
    slides.insert(i + 1, slide())
    return slides


if __name__ == '__main__':
    if '--assets' in sys.argv:
        build_assets()
    else:
        s = slide()
        print(s['title'], '· steps', s['steps'], '· (클릭)', s['spoken'].count('(클릭)'))
