# -*- coding: utf-8 -*-
"""v6 설명 애니메이션을 Cycles 로 «사실적» 렌더한다 (2026-10-06 팀장: 밤에 한 번 돌려 보자 · 덱 반영은 아직).

같은 장면·같은 카메라·같은 프레임 번호(build_v6.py 의 apply)를 쓰고, 재질·조명·배경만 바꾼다.
  - 엔진 Cycles · GPU(OptiX, 장치 전부) · 적응 샘플 · OptiX 디노이즈
  - Go2 USD 재질: 외장 = 반광 플라스틱 + 얇은 코트, 발 = 고무, 로고 유지. 설명 선·격자는 그대로(발광)
  - 스튜디오 조명: 키(왼쪽 위) · 필(오른쪽) · 림(뒤) 면광원 + 밝은 월드
  - 바닥: 큰 무광 평면(종이색) · 월드도 종이색 → 무한 호리존 느낌. build_v6 의 원반 바닥은 끈다
  - 결과: v6-cycles-frames/frame-NNNN.png (불투명) → package 단계에서 mp4

  blender -b --python build_v6_cycles.py -- --test 359 540 700 1225        시험 4장 (시간 측정)
  blender -b --python build_v6_cycles.py -- --sequence 300 1319             전 구간
"""
import bpy, sys, math, json, time
from pathlib import Path
from mathutils import Vector

ROOT = Path(__file__).resolve().parent
_src = (ROOT / 'build_v6.py').read_text(encoding='utf-8').split('argv = sys.argv')[0]
exec(_src)   # apply · SEGMENTS · STATES · cam · meshes · ground · mat ... 를 그대로 가져온다

# ── 엔진 ──────────────────────────────────────────────────────
s = bpy.context.scene
s.render.engine = 'CYCLES'
prefs = bpy.context.preferences.addons['cycles'].preferences
prefs.compute_device_type = 'OPTIX'
prefs.get_devices()
used = []
for d in prefs.devices:
    d.use = d.type == 'OPTIX'
    if d.use: used.append(d.name)
s.cycles.device = 'GPU'
s.cycles.samples = 128
s.cycles.use_adaptive_sampling = True
s.cycles.adaptive_threshold = 0.02
s.cycles.use_denoising = True
s.cycles.denoiser = 'OPTIX'
s.cycles.max_bounces = 6
s.render.film_transparent = False
s.view_settings.view_transform = 'AgX'
s.view_settings.look = 'AgX - Medium High Contrast'
s.view_settings.exposure = -0.35   # 1차 시험: 흰 로봇이 날아갔다(2026-10-06) → 빛을 줄이고 배경을 중간 회색으로
s.render.image_settings.file_format = 'PNG'; s.render.image_settings.color_mode = 'RGB'

# ── 재질 ──────────────────────────────────────────────────────
def _principled(m):
    if not m.use_nodes: m.use_nodes = True
    return m.node_tree.nodes.get('Principled BSDF')
for m in bpy.data.materials:
    n = m.name.lower()
    bs = _principled(m)
    if not bs: continue
    if 'go2_description' in n:
        if 'logo' in n:
            bs.inputs['Roughness'].default_value = .45
        elif 'foot' in n:
            bs.inputs['Roughness'].default_value = .85; bs.inputs['Specular IOR Level'].default_value = .3
            bs.inputs['Base Color'].default_value = (.03, .03, .03, 1)
        else:
            bs.inputs['Roughness'].default_value = .28; bs.inputs['Specular IOR Level'].default_value = .55
            c = bs.inputs['Base Color'].default_value; bs.inputs['Base Color'].default_value = (c[0]*.86, c[1]*.86, c[2]*.87, 1)   # 순백을 살짝 눌러 음영이 보이게
            if 'Coat Weight' in bs.inputs: bs.inputs['Coat Weight'].default_value = .25; bs.inputs['Coat Roughness'].default_value = .08
    elif n.startswith('v6_m_'):   # 모듈 근사체: 알루미늄 주조 느낌
        bs.inputs['Metallic'].default_value = .6; bs.inputs['Roughness'].default_value = .38
    elif n.startswith('v6_') and 'ground' not in n:   # 설명 선·격자·화살표: 발광 유지하되 과하지 않게
        bs.inputs['Emission Strength'].default_value = max(.6, bs.inputs['Emission Strength'].default_value)

# ── 조명 · 배경 ───────────────────────────────────────────────
PAPER = (.62, .63, .62)   # 월드·바닥: 중간 회색이어야 흰 로봇의 윤곽이 산다
w = s.world or bpy.data.worlds.new('V6_world'); s.world = w; w.use_nodes = True
bg = w.node_tree.nodes.get('Background'); bg.inputs['Color'].default_value = (*PAPER, 1); bg.inputs['Strength'].default_value = .45
def area(name, loc, target, power, size):
    bpy.ops.object.light_add(type='AREA', location=loc); L = bpy.context.object; L.name = name
    L.data.energy = power; L.data.size = size; L.data.shape = 'SQUARE'
    L.rotation_mode = 'QUATERNION'; L.rotation_quaternion = (Vector(target) - Vector(loc)).to_track_quat('-Z', 'Y')
    return L
key = area('V6_key', (-1.6, 2.2, 2.6), (0, 0, .3), 420, 1.6)
fill = area('V6_fill', (2.6, -1.4, 1.6), (0, 0, .3), 110, 3.0)
rim = area('V6_rim', (-2.4, -2.2, 1.9), (0, 0, .35), 360, 1.2)
bpy.ops.mesh.primitive_plane_add(size=40, location=(0, 0, 0)); floor = bpy.context.object; floor.name = 'V6_floor'
fm = bpy.data.materials.new('V6_floor_mat'); fm.use_nodes = True
fb = fm.node_tree.nodes.get('Principled BSDF'); fb.inputs['Base Color'].default_value = (*PAPER, 1); fb.inputs['Roughness'].default_value = .55; fb.inputs['Specular IOR Level'].default_value = .35   # 바닥에 희미한 반사
floor.data.materials.append(fm)

def apply_real(frame, res=(1280, 960)):
    apply(frame, res)
    ground.hide_render = True          # 원반 대신 무한 바닥
    floor.hide_render = False
    # 구간에 따라 로봇이 공중(분해·회전)에 있어도 바닥은 z=0 에 둔다

def render(frame, out):
    t0 = time.time(); apply_real(frame)
    s.render.filepath = str(out / f'frame-{frame:04d}.png'); bpy.ops.render.render(write_still=True)
    return time.time() - t0

argv = sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else []
print('CYCLES_DEVICES', used)
if argv and argv[0] == '--test':
    out = ROOT / 'v6-cycles-test'; out.mkdir(exist_ok=True); rep = {}
    for f in [int(x) for x in argv[1:]]: rep[f] = round(render(f, out), 1)
    print('CYCLES_TEST_DONE', json.dumps(rep))
elif argv and argv[0] == '--sequence':
    out = ROOT / 'v6-cycles-frames'; out.mkdir(exist_ok=True)
    lo = int(argv[1]) if len(argv) > 1 else 300; hi = int(argv[2]) if len(argv) > 2 else 1319
    t_all = time.time(); n = 0
    for f in range(lo, hi + 1):
        if (out / f'frame-{f:04d}.png').exists(): continue      # 이어서 돌릴 수 있게
        dt = render(f, out); n += 1
        if n % 20 == 0: print('CYCLES_PROGRESS', f, round(dt, 1), 's/frame', round((time.time()-t_all)/60, 1), 'min', flush=True)
    print('CYCLES_SEQUENCE_DONE', lo, hi, round((time.time()-t_all)/60, 1), 'min')
else:
    print('usage: --test f1 f2 ... | --sequence [lo hi]')
