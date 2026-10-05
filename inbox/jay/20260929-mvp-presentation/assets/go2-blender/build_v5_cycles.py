# -*- coding: utf-8 -*-
"""10쪽 0~2단계(v5: 턴테이블 1~97 · 네 다리 97~145 · 조립 145~193)를 Cycles 로 구운다 (2026-10-06 팀장).
build_v5.py 의 장면·apply 를 그대로 쓰고, 조명·재질·배경은 build_v6_cycles.py 와 같은 값.
  blender -b --python build_v5_cycles.py -- --test 1 97 145
  blender -b --python build_v5_cycles.py -- --sequence 1 193
결과: v5-cycles-frames/frame-NNNN.png (불투명 · 1280×960)"""
import bpy, sys, math, json, time
from pathlib import Path
from mathutils import Vector

ROOT = Path(__file__).resolve().parent
_src = (ROOT / 'build_v5.py').read_text(encoding='utf-8').split("if '--sequence' not in sys.argv:")[0]
exec(_src)

s = bpy.context.scene
s.render.engine = 'CYCLES'
prefs = bpy.context.preferences.addons['cycles'].preferences
prefs.compute_device_type = 'OPTIX'; prefs.get_devices()
for d in prefs.devices: d.use = d.type == 'OPTIX'
s.cycles.device = 'GPU'; s.cycles.samples = 128; s.cycles.use_adaptive_sampling = True; s.cycles.adaptive_threshold = 0.02
s.cycles.use_denoising = True; s.cycles.denoiser = 'OPTIX'; s.cycles.max_bounces = 6
s.render.film_transparent = False
s.view_settings.view_transform = 'AgX'; s.view_settings.look = 'AgX - Medium High Contrast'; s.view_settings.exposure = -0.35
s.render.image_settings.file_format = 'PNG'; s.render.image_settings.color_mode = 'RGB'

def _principled(m):
    if not m.use_nodes: m.use_nodes = True
    return m.node_tree.nodes.get('Principled BSDF')
for m in bpy.data.materials:
    n = m.name.lower(); bs = _principled(m)
    if not bs: continue
    if 'go2_description' in n:
        if 'logo' in n: bs.inputs['Roughness'].default_value = .45
        elif 'foot' in n:
            bs.inputs['Roughness'].default_value = .85; bs.inputs['Specular IOR Level'].default_value = .3
            bs.inputs['Base Color'].default_value = (.03, .03, .03, 1)
        else:
            bs.inputs['Roughness'].default_value = .28; bs.inputs['Specular IOR Level'].default_value = .55
            c = bs.inputs['Base Color'].default_value; bs.inputs['Base Color'].default_value = (c[0]*.86, c[1]*.86, c[2]*.87, 1)
            if 'Coat Weight' in bs.inputs: bs.inputs['Coat Weight'].default_value = .25; bs.inputs['Coat Roughness'].default_value = .08
    elif n.startswith('v5_') or n.startswith('teach_') or n.startswith('foothold_'):
        bs.inputs['Emission Strength'].default_value = max(.6, bs.inputs['Emission Strength'].default_value)

PAPER = (.62, .63, .62)
w = s.world or bpy.data.worlds.new('V5_world'); s.world = w; w.use_nodes = True
bg = w.node_tree.nodes.get('Background'); bg.inputs['Color'].default_value = (*PAPER, 1); bg.inputs['Strength'].default_value = .45
def area(name, loc, target, power, size):
    bpy.ops.object.light_add(type='AREA', location=loc); L = bpy.context.object; L.name = name
    L.data.energy = power; L.data.size = size; L.data.shape = 'SQUARE'
    L.rotation_mode = 'QUATERNION'; L.rotation_quaternion = (Vector(target) - Vector(loc)).to_track_quat('-Z', 'Y'); return L
area('V5_key', (-1.6, 2.2, 2.6), (0, 0, .3), 420, 1.6); area('V5_fill', (2.6, -1.4, 1.6), (0, 0, .3), 110, 3.0); area('V5_rim', (-2.4, -2.2, 1.9), (0, 0, .35), 360, 1.2)
bpy.ops.mesh.primitive_plane_add(size=40, location=(0, 0, 0)); floor = bpy.context.object; floor.name = 'V5_floor'
fm = bpy.data.materials.new('V5_floor_mat'); fm.use_nodes = True
fb = fm.node_tree.nodes.get('Principled BSDF'); fb.inputs['Base Color'].default_value = (*PAPER, 1); fb.inputs['Roughness'].default_value = .55; fb.inputs['Specular IOR Level'].default_value = .35
floor.data.materials.append(fm)

def render(frame, out):
    t0 = time.time(); apply(frame, (1280, 960)); floor.hide_render = False
    s.render.filepath = str(out / f'frame-{frame:04d}.png'); bpy.ops.render.render(write_still=True)
    return time.time() - t0

argv = sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else []
if argv and argv[0] == '--test':
    out = ROOT / 'v5-cycles-test'; out.mkdir(exist_ok=True); rep = {}
    for f in [int(x) for x in argv[1:]]: rep[f] = round(render(f, out), 1)
    print('V5_CYCLES_TEST_DONE', json.dumps(rep))
elif argv and argv[0] == '--sequence':
    out = ROOT / 'v5-cycles-frames'; out.mkdir(exist_ok=True)
    lo = int(argv[1]) if len(argv) > 1 else 1; hi = int(argv[2]) if len(argv) > 2 else 193
    t_all = time.time()
    for f in range(lo, hi + 1):
        if (out / f'frame-{f:04d}.png').exists(): continue
        render(f, out)
    print('V5_CYCLES_SEQUENCE_DONE', lo, hi, round((time.time()-t_all)/60, 1), 'min')
else:
    print('usage: --test f1 f2 ... | --sequence [lo hi]')
