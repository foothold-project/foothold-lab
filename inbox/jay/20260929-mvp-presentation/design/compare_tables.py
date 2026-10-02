# -*- coding: utf-8 -*-
"""실험 영상 비교표 세 장 · 팀장 지시 2026-10-02.

「발표 뒤쪽에서 실험했던 영상 자료들을 비교 테이블로 많이 보여 주자.
 영상·이미지에 양쪽·위아래 블랙 바 없게.」

한 장 = 6행(지형 · 속도) × 3열(NVIDIA 공식 정책 · foothold-v1 · foothold-v2).
칸마다 16:9 포스터(object-fit:cover · 검은 띠 없음) + 그 칸 100판의 성공률.
행을 누르면 그 행 세 영상이 포스터 자리에서 함께 재생된다(다른 행은 멈춤).

자료
  v1 갤러리  sim/eval/results/20260911-gallery/web/<지형>-v<속도>.mp4 (foothold-v1)
             같은 폴더 <지형>-v<속도>-baseline.mp4 (= NVIDIA 공식 사전학습 정책 · 아래 «라벨 근거»)
  v2 갤러리  sim/eval/results/20260928-v2-gallery/web/<지형>-v<속도>.mp4 + posters/<같은 이름>.jpg
  성공률     세 모델의 **/d0.5/v<속도>/generalization_raw.csv · overall_success · 지형·속도당 100판
세 모델 컷이 모두 있는 칸만 쓴다. v1 갤러리의 baseline 컷은 18 칸뿐이라 18 칸 = 3 장.

«baseline» 라벨 근거 (손으로 단정하지 않고 파일에서 읽은 것)
  - 20260911-gallery/manifest.json: clips[].model 이 'baseline' 18 · 'foothold-v1' 48 · 'A' 18.
  - 20260911-gallery/gallery.html: 「기준선 · A · foothold-v1」.
  - 20260911-gallery/cuts/<칸>-baseline/*.json: policy_checkpoint 가
    .pretrained_checkpoints/rsl_rl/Isaac-Velocity-Rough-Unitree-Go2-v0/checkpoint.pt (sha f2aa77bf…).
  - 성공률 CSV 의 NVIDIA 는 nvidia_pretrained_source/nvidia_pretrained.pt (sha 1891ab2b…) 인데
    20260921-nvidia-axis1/README.md 가 두 파일의 텐서 17 개를 대조해 최대 차이 0.0 (iter 만 0 대 1499)
    이라고 적었고, 이 모듈을 만들며 같은 대조를 다시 돌려 확인했다.
  - manifest 의 baseline 18 컷 success_rate 가 NVIDIA CSV 의 같은 칸 성공 수와 18/18 일치한다.
  - docs/research/20260928-v2-mvp-report.md §13: 「foothold-v1 판의 기준선 둘(NVIDIA · v1)과 같은
    자리를 같은 카메라로 찍었으므로 세 열을 나란히 견줄 수 있다」 · §14: 「NVIDIA 는 …-baseline.mp4」.

포스터
  v2 는 갤러리 posters/ 를 그대로 쓴다(1920×1080 jpg). v1 갤러리와 baseline 은 포스터가 없어
  PyAV 로 첫 프레임을 assets/compare-posters/<파일>.jpg (640×360) 로 만든다. 이미 있으면 안 만든다.
"""
import csv
import html
import io
import json
from pathlib import Path

from .intro_story import make, src
from .research_revision import NAMES

HERE = Path(__file__).resolve().parent.parent          # 20260929-mvp-presentation
ROOT = HERE.parents[2]                                  # foothold-lab
RESULTS = ROOT / 'sim/eval/results'
GALLERY1 = RESULTS / '20260911-gallery'
GALLERY2 = RESULTS / '20260928-v2-gallery'
POSTERS = HERE / 'assets/compare-posters'
WEB1 = '../../../../sim/eval/results/20260911-gallery/web/'    # output/ 기준
WEB2 = '../../../../sim/eval/results/20260928-v2-gallery/web/'
POST2 = '../../../../sim/eval/results/20260928-v2-gallery/posters/'
MINE = '../assets/compare-posters/'
REPORT = '../../../../docs/research/20260928-v2-mvp-report.md'

ROOTS = {
    'nv': RESULTS / '20260921-nvidia-axis1',
    'v1': RESULTS / 'maindata-v1/foothold-v1',
    'v2': RESULTS / '20260923-v2rs/v2g2-feetair01-iter3000',
}
LABEL = {'nv': 'NVIDIA 공식 정책', 'v1': 'foothold-v1', 'v2': 'foothold-v2'}
SEED = 42
DIFF = 0.5
SECTION = '남은 과제'                      # 30쪽(디딤돌 시드)과 같은 장
ANCHOR = '디딤돌에서는 평가 시드에 따라 성공률이 흔들렸습니다'

# 학습에 넣은 지형: gap 은 v1(forward_gap) · v2(omni_gap), rails 는 v2 (보고서 §7 · sim/policy/gap_env_cfg.py)
TRAINED = {'gap': ('v1', 'v2'), 'rails': ('v2',)}

PAGES = [
    ('학습에 넣은 틈과 턱에서, 세 모델을 같은 자리에서 봅니다',
     [('gap', .5), ('gap', 1.), ('gap', 1.5), ('rails', .5), ('rails', 1.), ('rails', 1.5)],
     '뒤쪽 실험 영상을 표로 모았습니다. 왼쪽부터 NVIDIA 공식 정책, v1, v2 이고, 세 판을 같은 자리에서 같은 카메라로 찍었습니다. '
     '틈은 v1 과 v2 가, 턱은 v2 가 학습에 넣은 지형이라 일반화가 아니라 학습 결과입니다. '
     '행을 누르면 그 행 세 영상이 같이 재생됩니다. 숫자는 그 칸 100판의 성공률입니다.'),
    ('미경험 고리와 함몰에서, 세 속도를 나란히 봅니다',
     [('floating_ring', .5), ('floating_ring', 1.), ('floating_ring', 1.5), ('pit', .5), ('pit', 1.), ('pit', 1.5)],
     '고리와 함몰은 세 모델 모두 학습에 넣지 않은 지형입니다. 속도를 올릴수록 어떻게 갈리는지 행마다 보시면 됩니다. '
     '1.5 미터 매 초는 NVIDIA 학습 명령 범위 밖입니다.'),
    ('나머지 미경험 지형 여섯 칸도 같은 자리에서 봅니다',
     [('discrete_obstacles', 1.5), ('repeated_boxes', 1.5), ('repeated_cylinders', 1.5),
      ('star', 1.5), ('wave', 1.5), ('stepping_stones', 1.)],
     '세 모델 컷이 다 있는 나머지 미경험 칸입니다. 대부분 1.5 미터 매 초이고 디딤돌만 1.0 입니다. '
     '디딤돌은 앞 장에서 본 대로 시드에 따라 흔들리는 칸이라 영상 한 판으로 안정성을 말하지 않습니다.'),
]


# ── 원자료 · 지형·속도당 100판 ───────────────────────────────────
def _cells(root):
    out = {}
    for f in sorted(root.glob('*/d0.5/*/generalization_raw.csv')):
        m = json.loads((f.parent / 'run_manifest.json').read_text(encoding='utf-8'))
        sp = float(m['command_vx_mps'])
        assert float(f.parent.name[1:]) == sp, (f, sp)
        assert m['eval_spec_version'] == 2 and m['seed'] == SEED, (f, m['eval_spec_version'], m['seed'])
        assert [float(x) for x in m['terrain_difficulty_range']] == [DIFF, DIFF], (f, m['terrain_difficulty_range'])
        with io.open(f, encoding='utf-8-sig', newline='') as h:
            for r in csv.DictReader(h):
                out.setdefault((r['terrain'], sp), []).append(r['overall_success'].lower() == 'true')
    assert len(out) == 48, (root, len(out))
    for k, v in out.items():
        assert len(v) == 100, (root, k, len(v))
    return {k: sum(v) for k, v in out.items()}       # 100판 중 성공 수 = 성공률 %


def _rates():
    r = {m: _cells(p) for m, p in ROOTS.items()}
    # 답을 아는 칸에 먼저 걸어 본다: 보고서 §13 「rails 1.0 · 세 판이 8 · 48 · 100」
    assert (r['nv'][('rails', 1.)], r['v1'][('rails', 1.)], r['v2'][('rails', 1.)]) == (8, 48, 100), \
        [r[m][('rails', 1.)] for m in ROOTS]
    man = json.loads((GALLERY1 / 'manifest.json').read_text(encoding='utf-8'))
    base = [c for c in man['clips'] if c['model'] == 'baseline']
    assert len(base) == 18, len(base)
    for c in base:                                   # 갤러리가 적어 둔 baseline 성적 = NVIDIA CSV
        assert abs(c['success_rate'] - r['nv'][(c['terrain'], float(c['speed_mps']))]) < 1e-9, c['file']
    return r


# ── 포스터 · 첫 프레임 640×360 (없을 때만 만든다) ───────────────────
def _poster(src_path, name):
    dst = POSTERS / f'{name}.jpg'
    if not dst.exists():
        import av
        from PIL import Image
        POSTERS.mkdir(parents=True, exist_ok=True)
        with av.open(str(src_path)) as c:
            frame = next(c.decode(video=0))
        im = frame.to_image()
        assert abs(im.size[0] / im.size[1] - 16 / 9) < 1e-3, (src_path, im.size)
        im.resize((640, 360), Image.LANCZOS).save(dst, quality=86, optimize=True)
    return MINE + dst.name


def _files(terrain, sp):
    tag = f'{terrain}-v{sp:g}'
    nv = GALLERY1 / 'web' / f'{tag}-baseline.mp4'
    v1 = GALLERY1 / 'web' / f'{tag}.mp4'
    v2 = GALLERY2 / 'web' / f'{tag}.mp4'
    p2 = GALLERY2 / 'posters' / f'{tag}.jpg'
    for p in (nv, v1, v2, p2):
        assert p.exists(), p
    return {
        'nv': (WEB1 + nv.name, _poster(nv, f'{tag}-baseline')),
        'v1': (WEB1 + v1.name, _poster(v1, f'{tag}-v1')),
        'v2': (WEB2 + v2.name, POST2 + p2.name),
    }


# ── 조각 ───────────────────────────────────────────────────────
def _tag(terrain):
    if terrain in TRAINED:
        return '<i class="cmp-tag learn">학습 지형 · ' + ' · '.join(TRAINED[terrain]) + '</i>'
    return '<i class="cmp-tag">미경험 · 셋 다</i>'


def _row(terrain, sp, rates):
    files = _files(terrain, sp)
    vals = {m: rates[m][(terrain, sp)] for m in ROOTS}
    best = max(vals.values())
    speed = f'{sp:.1f} m/s' + (' *' if sp == 1.5 else '')
    name = html.escape(NAMES[terrain])
    h = (f'<div class="cmp-row" data-cell="{terrain}-v{sp:g}" aria-label="{name} {speed} · 행을 누르면 세 영상 재생">'
         f'<div class="cmp-key"><b>{name}</b><span>{speed}</span>{_tag(terrain)}</div>')
    for m in ROOTS:
        mp4, poster = files[m]
        v = vals[m]
        cls = 'cmp-cell best' if v == best and best > 0 else 'cmp-cell'
        alt = html.escape(f'{LABEL[m]} · {NAMES[terrain]} · {speed} 첫 프레임')
        h += (f'<figure class="{cls}" data-model="{m}"><div class="cmp-frame">'
              f'<img src="{poster}" alt="{alt}" loading="lazy">'
              f'<video preload="none" muted playsinline loop src="{mp4}" aria-label="{html.escape(LABEL[m])} 영상"></video>'
              f'<i class="cmp-play" aria-hidden="true"></i></div>'
              f'<figcaption><b>{v}%</b><small>{v} / 100판</small><i class="cmp-bar"><em style="width:{v}%"></em></i></figcaption></figure>')
    return h + '</div>'


def _page(title, rows, spoken, rates, page_no, total):
    head = ('<div class="cmp-head"><span>지형 · 속도</span>'
            + ''.join(f'<span data-model="{m}">{LABEL[m]}</span>' for m in ROOTS) + '</div>')
    table = '<div class="cmp-table">' + ''.join(_row(t, sp, rates) for t, sp in rows) + '</div>'
    cond = ('<p class="cmp-cond"><b>행을 누르면 세 영상이 같이 재생됩니다</b> · 난이도 0.5 · 지형·속도당 100판 · 평가 시드 42 · '
            '세 판을 같은 자리 같은 카메라로 · 영상은 각 한 판의 예시 · * NVIDIA 학습 명령 범위 밖'
            f' · 비교표 {page_no}/{total}</p>')
    source = (src('v1 갤러리 (NVIDIA · v1)', WEB1 + '../gallery.html') + ' · '
              + src('v2 갤러리', WEB2 + '../gallery.html') + ' · '
              + src('성공률 원자료 · 보고서 §13', REPORT))
    note = ('칸마다 성공 수는 세 모델의 **/d0.5/v<속도>/generalization_raw.csv 에서 overall_success 를 세어 100판을 확인했다. '
            'NVIDIA 열의 영상은 v1 갤러리의 -baseline 컷이다: cuts/*.json 의 policy_checkpoint 는 '
            '.pretrained_checkpoints/…/Isaac-Velocity-Rough-Unitree-Go2-v0/checkpoint.pt (sha f2aa77bf) 이고, '
            '성공률 CSV 의 nvidia_pretrained.pt (sha 1891ab2b) 와 텐서 17 개 최대 차이 0.0 (20260921-nvidia-axis1/README.md · 이 모듈 제작 때 재확인). '
            'manifest.json 의 baseline 성적 18 칸이 NVIDIA CSV 와 전부 일치한다. '
            'v2 열은 20260928-v2-gallery (v2g2-feetair01 iter3000, sha e5c21321). '
            '세 판을 같은 자리 같은 카메라로 찍은 것은 보고서 §13. 포스터는 첫 프레임이고 HUD 는 같은 시뮬레이션의 계측이다.')
    return make(SECTION, title, head + table + cond, spoken, source,
                kind='compare-page', steps=0, note=note)


def apply(slides):
    titles = [s['title'] for s in slides]
    for t, _, _ in PAGES:
        assert t not in titles, t
    rates = _rates()
    i = titles.index(ANCHOR) + 1
    pages = [_page(t, rows, spoken, rates, k, len(PAGES)) for k, (t, rows, spoken) in enumerate(PAGES, 1)]
    cells = {c for _, rows, _ in PAGES for c in rows}
    assert len(cells) == 18, len(cells)
    slides[i:i] = pages
    return slides
