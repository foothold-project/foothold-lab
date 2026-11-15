# -*- coding: utf-8 -*-
"""Go2 설명 «필름» · 유튜브용 한 흐름 (2026-10-06 팀장 지시 · 덱과 별개 · 덱은 건드리지 않는다).

레퍼런스(AMD EPYC 광고 · 애플 폴더블 해설)에서 가져온 문법:
  - 한 세트(어두운 스튜디오 · 같은 빛) 안에 주인공 하나. 컷은 있어도 세트·타이포가 같아 한 흐름.
  - 주장마다 «물리적 연출»: 분해(부품 띄우기) · 치수선/라벨(주황) · 투시(X-ray) · 측정 그래픽.
  - 원근 렌즈 · 얕은 심도 · 느린 푸시인/오빗. 자막은 인코딩 단계(package_film.py)에서 같은 자리에.

장면(초): S1 0~4 등장 · S2 4~10 네 다리 분해/결합 · S3 10~18 다리 투시 + 액추에이터 조립 + 관절 셋
  S4 18~24 접촉·토크·피드백 · S5 24~31 전면 카메라·LiDAR · S6 31~42 모듈 장착·분해도·라벨 · S7 42~52 명령 셋
  S8 52~59 187점 격자·레이저 · S9 59~70 틈 건너기 + 네 조건 치수 · S10 70~76 대군
프레임 = 초×24. 포즈·소품은 build_v6.py 의 것을 그대로 쓴다(exec).

  blender -b --python build_film.py -- --test 2 7 14 21 27 37 46 55 64 73      장면 대표 정지화(초)
  blender -b --python build_film.py -- --sequence [lo hi] [cycles]            전 구간 (기본 EEVEE 1280x720)
"""
import bpy, sys, math, json, time, random
from pathlib import Path
from mathutils import Vector, Quaternion

ROOT = Path(__file__).resolve().parent
_src = (ROOT / 'build_v6.py').read_text(encoding='utf-8').split('argv = sys.argv')[0]
exec(_src)
FPS = 24; W, H = 1280, 720; DUR = 76
argv = sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else []
USE_CYCLES = 'cycles' in argv      # Blender 가 '--' 뒤의 --cycles 도 자기 옵션으로 읽어 죽는다 → 맨말 cycles
RIG_Z = rig.location.z            # 0.341 · 발이 바닥에 닿는 높이 (0 으로 두면 몸이 바닥에 묻힌다)

# ── 엔진 ──────────────────────────────────────────────────────
s = bpy.context.scene
s.render.resolution_x, s.render.resolution_y = W, H; s.render.resolution_percentage = 100
s.render.film_transparent = False
s.render.image_settings.file_format = 'PNG'; s.render.image_settings.color_mode = 'RGB'
s.view_settings.view_transform = 'AgX'; s.view_settings.look = 'AgX - Medium High Contrast'; s.view_settings.exposure = -0.1
if USE_CYCLES:
    s.render.engine = 'CYCLES'; prefs = bpy.context.preferences.addons['cycles'].preferences
    prefs.compute_device_type = 'OPTIX'; prefs.get_devices()
    for d in prefs.devices: d.use = d.type == 'OPTIX'
    s.cycles.device = 'GPU'; s.cycles.samples = 128; s.cycles.use_adaptive_sampling = True; s.cycles.adaptive_threshold = .02
    s.cycles.use_denoising = True; s.cycles.denoiser = 'OPTIX'; s.cycles.max_bounces = 6
else:
    s.render.engine = 'BLENDER_EEVEE_NEXT'; s.eevee.taa_render_samples = 32
    s.eevee.use_raytracing = True; s.eevee.use_shadows = True

# ── 재질 ──────────────────────────────────────────────────────
body_mats = []
for m in bpy.data.materials:
    n = m.name.lower(); bs = m.node_tree.nodes.get('Principled BSDF') if m.use_nodes else None
    if not bs: continue
    if 'go2_description' in n:
        if 'logo' in n: bs.inputs['Roughness'].default_value = .45
        elif 'foot' in n:
            bs.inputs['Roughness'].default_value = .85; bs.inputs['Base Color'].default_value = (.03, .03, .03, 1)
        else:
            bs.inputs['Roughness'].default_value = .30; bs.inputs['Specular IOR Level'].default_value = .55
            c = bs.inputs['Base Color'].default_value; bs.inputs['Base Color'].default_value = (c[0]*.86, c[1]*.86, c[2]*.87, 1)
            if 'Coat Weight' in bs.inputs: bs.inputs['Coat Weight'].default_value = .25; bs.inputs['Coat Roughness'].default_value = .08
            m.surface_render_method = 'BLENDED'; m.use_backface_culling = True; body_mats.append(bs)
    elif n.startswith('v6_m_'):
        bs.inputs['Metallic'].default_value = .6; bs.inputs['Roughness'].default_value = .38
    elif n.startswith('v6_') and 'ground' not in n:
        bs.inputs['Emission Strength'].default_value = max(1.2, bs.inputs['Emission Strength'].default_value)
def xray(alpha):
    for bs in body_mats: bs.inputs['Alpha'].default_value = alpha
def metal(name, color, metallic=.9, rough=.3):
    m = bpy.data.materials.new(name); m.use_nodes = True; bs = m.node_tree.nodes['Principled BSDF']
    bs.inputs['Base Color'].default_value = (*color, 1); bs.inputs['Metallic'].default_value = metallic; bs.inputs['Roughness'].default_value = rough; return m
orange = mat('FILM_orange', (.95, .42, .16), 2.2)
steel = metal('FILM_steel', (.60, .61, .63), .95, .25); copper = metal('FILM_copper', (.70, .36, .18), .85, .35)
dark_alu = metal('FILM_alu', (.32, .33, .35), .8, .4); black_plastic = metal('FILM_black', (.05, .05, .055), .0, .5)

# ── 세트 · 조명 (어두운 콘크리트 스튜디오 · 로봇 주변만 밝다) ─────────
FLOOR = (.14, .145, .14)
w = s.world or bpy.data.worlds.new('FILM_world'); s.world = w; w.use_nodes = True
# 카메라에는 어두운 배경, 반사·간접광에는 위가 밝은 회색 그라데이션 (금속·흰 외장이 살아난다)
nt = w.node_tree; nt.nodes.clear()
out_n = nt.nodes.new('ShaderNodeOutputWorld'); bg_cam = nt.nodes.new('ShaderNodeBackground'); bg_ref = nt.nodes.new('ShaderNodeBackground')
mixn = nt.nodes.new('ShaderNodeMixShader'); lp = nt.nodes.new('ShaderNodeLightPath'); grad = nt.nodes.new('ShaderNodeTexGradient'); ramp = nt.nodes.new('ShaderNodeValToRGB')
tc = nt.nodes.new('ShaderNodeTexCoord'); mp = nt.nodes.new('ShaderNodeMapping'); mp.inputs['Rotation'].default_value = (0, math.radians(-90), 0)
bg_cam.inputs['Color'].default_value = (.085, .09, .09, 1); bg_cam.inputs['Strength'].default_value = 1.0
ramp.color_ramp.elements[0].position = .45; ramp.color_ramp.elements[0].color = (.05, .052, .052, 1)
ramp.color_ramp.elements[1].position = 1.0; ramp.color_ramp.elements[1].color = (.18, .185, .19, 1)
nt.links.new(tc.outputs['Generated'], mp.inputs['Vector']); nt.links.new(mp.outputs['Vector'], grad.inputs['Vector'])
nt.links.new(grad.outputs['Fac'], ramp.inputs['Fac']); nt.links.new(ramp.outputs['Color'], bg_ref.inputs['Color']); bg_ref.inputs['Strength'].default_value = .9
nt.links.new(lp.outputs['Is Camera Ray'], mixn.inputs['Fac']); nt.links.new(bg_ref.outputs['Background'], mixn.inputs[1]); nt.links.new(bg_cam.outputs['Background'], mixn.inputs[2])
nt.links.new(mixn.outputs['Shader'], out_n.inputs['Surface'])
def area(name, power, size):
    bpy.ops.object.light_add(type='AREA', location=(0, 0, 3)); L = bpy.context.object; L.name = name
    L.data.energy = power; L.data.size = size; L.data.shape = 'SQUARE'; L.rotation_mode = 'QUATERNION'; return L
key = area('FILM_key', 110, 1.8); fill = area('FILM_fill', 32, 3.0); rim = area('FILM_rim', 100, 1.2)
CAM_AZ = [0.]
def rig_lights(target):
    """3점 조명을 카메라 방위각에 걸어 둔다 → 어느 컷이든 노출이 같다 (키 = 카메라 왼쪽 앞 위 · 림 = 뒤)."""
    tg = Vector(target)
    for L, daz, el, dist in ((key, 52, 48, 3.2), (fill, -62, 28, 3.2), (rim, 178, 36, 3.0)):
        a, e = math.radians(CAM_AZ[0] + daz), math.radians(el)
        L.location = tg + Vector((dist*math.cos(e)*math.cos(a), dist*math.cos(e)*math.sin(a), dist*math.sin(e)))
        L.rotation_quaternion = (tg - L.location).to_track_quat('-Z', 'Y')
floormat = bpy.data.materials.new('FILM_floor'); floormat.use_nodes = True
fb = floormat.node_tree.nodes['Principled BSDF']; fb.inputs['Base Color'].default_value = (*FLOOR, 1); fb.inputs['Roughness'].default_value = .86; fb.inputs['Specular IOR Level'].default_value = .05
def slab(name, x0, x1, y0=-200, y1=200):
    bpy.ops.mesh.primitive_cube_add(size=1, location=((x0+x1)/2, (y0+y1)/2, -.15)); o = bpy.context.object; o.name = name
    o.scale = ((x1-x0), (y1-y0), .3); o.data.materials.append(floormat); return o
GX0, GX1, GY = 1.25, 1.55, 1.2          # 틈 0.30 m 폭 · 2.4 m 길이 (S9 에서만 열린다)
slab_a = slab('FILM_slab_a', -200, GX0); slab_b = slab('FILM_slab_b', GX1, 200)
slab_c = slab('FILM_slab_c', GX0, GX1, GY, 200); slab_d = slab('FILM_slab_d', GX0, GX1, -200, -GY)
pitmat = bpy.data.materials.new('FILM_pit'); pitmat.use_nodes = True; pitmat.node_tree.nodes['Principled BSDF'].inputs['Base Color'].default_value = (.02, .02, .02, 1)
bpy.ops.mesh.primitive_plane_add(size=1, location=((GX0+GX1)/2, 0, -.9)); pit = bpy.context.object; pit.name = 'FILM_pit'; pit.scale = (GX1-GX0, 2*GY, 1); pit.data.materials.append(pitmat)
ground.hide_render = True
def floor_gap(open_):
    for o in (slab_b, slab_c, slab_d, pit): o.hide_render = not open_
    if open_: slab_a.scale.x = GX0 + 200; slab_a.location.x = (GX0 - 200)/2
    else: slab_a.scale.x = 400; slab_a.location.x = 0

# ── 카메라 (원근 · 궤도 보간) ─────────────────────────────────
cam.data.type = 'PERSP'; cam.data.sensor_fit = 'HORIZONTAL'; cam.data.sensor_width = 36; cam.data.shift_x = cam.data.shift_y = 0
cam.data.dof.use_dof = True; cam.data.dof.aperture_fstop = 2.8; cam.data.clip_start = .02
def look(pos, target, lens):
    cam.location = Vector(pos); cam.rotation_euler = (Vector(target) - cam.location).to_track_quat('-Z', 'Y').to_euler()
    cam.data.lens = lens; cam.data.dof.focus_distance = (Vector(target) - cam.location).length
    d = Vector(target) - cam.location; CAM_AZ[0] = math.degrees(math.atan2(-d.y, -d.x)); rig_lights(target)
def cam_axes():
    R = cam.rotation_euler.to_matrix(); return R @ Vector((1, 0, 0)), R @ Vector((0, 1, 0))
def orbit(az, el, dist, target, lens):
    a, e = math.radians(az), math.radians(el)
    look((target[0] + dist*math.cos(e)*math.cos(a), target[1] + dist*math.cos(e)*math.sin(a), target[2] + dist*math.sin(e)), target, lens)
# (초, 방위각 deg [0 = 얼굴 정면 · 90 = 로봇 왼쪽], 고도 deg, 거리 m, 목표, 렌즈 mm) · 사이는 smoothstep
HIP = (.193, .047, .341); THIGH = (.193, .142, .351); KNEE = (.041, .156, .203)
KEYS = [
    (0,  -38, 14, 2.6, (.05, 0, .26), 50), (4, -22, 11, 1.55, (.05, 0, .28), 55),
    (4.01, -22, 16, 2.1, (0, 0, .28), 45), (10, 58, 16, 2.1, (0, 0, .28), 45),
    (10.01, 58, 14, 1.25, (.12, .10, .24), 50), (18, 78, 12, 1.1, (.10, .11, .23), 52),
    (18.01, 92, 5, 1.35, (.10, 0, .20), 55), (24, 88, 5, 1.25, (.10, 0, .20), 55),
    (24.01, -42, 14, 1.05, (.33, 0, .30), 55), (31, -24, 12, .98, (.33, 0, .30), 60),
    (31.01, 132, 34, 1.6, (.10, 0, .42), 45), (42, 112, 30, 1.55, (.10, 0, .44), 45),
    (42.01, -48, 18, 2.2, (.10, 0, .30), 45), (52, -62, 20, 2.2, (.10, 0, .30), 45),
    (52.01, 24, 46, 2.2, (0, 0, .10), 40), (59, 18, 44, 2.1, (0, 0, .10), 40),
]
def cam_at(t):
    for (t0, a0, e0, d0, g0, l0), (t1, a1, e1, d1, g1, l1) in zip(KEYS, KEYS[1:]):
        if t0 <= t <= t1:
            u = ease((t-t0)/max(1e-6, t1-t0))
            orbit(mix(a0, a1, u), mix(e0, e1, u), mix(d0, d1, u), Vector(g0).lerp(Vector(g1), u), mix(l0, l1, u)); return
    t0, a0, e0, d0, g0, l0 = KEYS[-1]; orbit(a0, e0, d0, g0, l0)

# ── 액추에이터 근사 (FL 세 관절: 고정자 · 회전자 · 유성 기어 셋) ────────
def cyl(name, r, h, m):
    bpy.ops.mesh.primitive_cylinder_add(radius=r, depth=h, vertices=48); o = bpy.context.object; o.name = name; o.data.materials.append(m); return o
ACT = {}
for jn in ['FL_hip_joint', 'FL_thigh_joint', 'FL_calf_joint']:
    stator = cyl('ACT_stator_'+jn, .030, .040, copper); rotor = cyl('ACT_rotor_'+jn, .018, .048, steel)
    planets = [cyl(f'ACT_planet_{jn}_{k}', .0055, .030, steel) for k in range(3)]
    ACT[jn] = (stator, rotor, planets)
ACT_OBJS = [o for v in ACT.values() for o in (v[0], v[1], *v[2])]
def place_actuators(show, spin=0., explode=0.):
    """explode 0 = 조립 완료 · 1 = 축 방향으로 벌어진 상태(고정자 그대로 · 회전자 +0.09 · 유성 +0.16)."""
    for jn, (stator, rotor, planets) in ACT.items():
        for o in (stator, rotor, *planets): o.hide_render = not show
        if not show: continue
        c = joint_world(jn); ax = joint_axis_world(jn); q = ax.to_track_quat('Z', 'Y')
        stator.location = c; rotor.location = c + ax*(.09*explode)
        for o in (stator, rotor): o.rotation_mode = 'QUATERNION'; o.rotation_quaternion = q
        for k, p in enumerate(planets):
            a = spin + 2*math.pi*k/3; off = q @ Vector((.0235*math.cos(a), .0235*math.sin(a), 0))
            p.location = c + off + ax*(.16*explode); p.rotation_mode = 'QUATERNION'; p.rotation_quaternion = q

# ── 모듈 디테일 (단순 상자 금지 · 방열핀 · 플랜지 · 커넥터) ─────────────
def detail_box(name, size, loc, m):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc); o = bpy.context.object; o.name = name; o.scale = size; o.data.materials.append(m); return o
dock_fins = [detail_box(f'dockfin{k}', (.13, .004, .012), (MOD_HOME['dock'][0], -.040 + .010*k, MOD_HOME['dock'][2] + .018 + .006), dark_alu) for k in range(9)]
dock_port = detail_box('dockport', (.012, .024, .010), (MOD_HOME['dock'][0] - .086, .02, MOD_HOME['dock'][2]), black_plastic)
dock_lid.hide_render = True                                   # v6 의 청록 띠 대신 방열핀
hesai_flange = cyl('hesai_flange', .046, .008, dark_alu); hesai_flange.location = (MOD_HOME['hesai'][0], 0, MOD_HOME['hesai'][2] - .036 + .004)
hesai_cap = cyl('hesai_cap', .041, .006, dark_alu); hesai_cap.location = (MOD_HOME['hesai'][0], 0, MOD_HOME['hesai'][2] + .036 + .003)
hesai_cable = cyl('hesai_cable', .004, .05, black_plastic); hesai_cable.rotation_euler = (0, math.radians(90), 0); hesai_cable.location = (MOD_HOME['hesai'][0] - .055, .02, MOD_HOME['hesai'][2] - .030)
EXTRA = {'dock': dock_fins + [dock_port], 'hesai': [hesai_flange, hesai_cap, hesai_cable], 'd435': []}
for k, objs in EXTRA.items():
    MODULES[k] = MODULES[k] + objs
    for o in objs: _mod_base[o.name] = tuple(o.location)
MOD_LABEL = {'dock': 'Orin NX 16GB', 'hesai': 'HESAI-360 LiDAR', 'd435': 'RealSense D435i'}

# ── 3D 글자 (라벨 · 치수 · 큰 숫자) ──────────────────────────
FONT = bpy.data.fonts.load('C:/Windows/Fonts/malgunbd.ttf')
def text3d(name, body, size, m, align='CENTER'):
    c = bpy.data.curves.new(name, 'FONT'); c.body = body; c.font = FONT; c.size = size; c.align_x = align; c.align_y = 'CENTER'
    o = bpy.data.objects.new(name, c); bpy.context.scene.collection.objects.link(o); o.data.materials.append(m); o.hide_render = True; return o
def billboard(o, pos):
    o.location = Vector(pos); o.rotation_mode = 'QUATERNION'; o.rotation_quaternion = (cam.location - o.location).to_track_quat('Z', 'Y')
TXT = {k: text3d('TXT_'+k, v, sz, orange) for k, (v, sz) in {
    'legs': ('다리 4 × 관절 3 = 모터 12', .055), 'hip': ('고관절 · 외전·내전', .026), 'thigh': ('허벅지 · 굽힘·폄', .026), 'calf': ('무릎 · 굽힘·폄', .026),
    'torque': ('모터 토크 → 관절 회전 → 발 이동', .028), 'cam': ('RGB 카메라', .024), 'lidar': ('LiDAR', .024),
    'vx': ('vx  0.4 ~ 1.5 m/s', .06), 'vy': ('vy  0 (이번 학습은 잠금)', .06), 'wz': ('ωz  -1.0 ~ 1.0 rad/s', .06),
    'grid': ('187 점 · 1.6 × 1.0 m', .045), 'm3': ('전진 3 m', .055), 'mae': ('속도 오차 ≤ 0.25 m/s', .05), 'lane': ('좌우 ± 0.75 m', .05),
    'alive': ('넘어지지 않기', .05), 'army': ('× 4,096', .55)}.items()}
MOD_ALIGN = {'dock': 'LEFT', 'hesai': 'LEFT', 'd435': 'RIGHT'}; MOD_OFF = {'dock': (.13, -.02), 'hesai': (.12, .03), 'd435': (-.05, .07)}
for k in MOD_LABEL: TXT['mod_'+k] = text3d('TXT_mod_'+k, MOD_LABEL[k], .028, orange, MOD_ALIGN[k])
dim_line = line('FILM_dim', [(0, 0, 0), (0, 0, 0)], orange, .003)
lane_l = line('FILM_lane_l', [(0, 0, 0), (0, 0, 0)], orange, .002); lane_r = line('FILM_lane_r', [(0, 0, 0), (0, 0, 0)], orange, .002)
leaders = {k: line('FILM_leader_'+k, [(0, 0, 0), (0, 0, 0)], orange, .0012) for k in list(MOD_LABEL) + ['hip', 'thigh', 'calf', 'cam', 'lidar']}
PROPS_FILM = [dim_line, lane_l, lane_r] + list(TXT.values()) + ACT_OBJS + list(leaders.values())
def hide_film():
    for o in PROPS_FILM: o.hide_render = True
    place_modules({})
def label(key, anchor, dx, dz):
    """anchor(월드 점)에서 화면 기준 오른쪽 dx · 위 dz 만큼 띄운 자리에 글자, 둘 사이 지시선."""
    right, up = cam_axes(); o = TXT[key]; o.hide_render = False; pos = Vector(anchor) + right*dx + up*dz; billboard(o, pos)
    ld = leaders[key.replace('mod_', '')]; ld.hide_render = False; set_points(ld, [tuple(anchor), tuple(pos)])

# ── 대군 (S10) · 연결 복제 ─────────────────────────────────────
def descendants(o):
    out = [o]
    for c in o.children: out += descendants(c)
    return out
robot_objs = descendants(rig)
ARMY = []          # (rig, {hero_name: dup_obj})
def make_army(n_x=8, n_y=6, dx=1.5, dy=1.35):
    for i in range(n_x):
        for j in range(n_y):
            bpy.ops.object.select_all(action='DESELECT')
            for o in robot_objs: o.select_set(True)
            bpy.context.view_layer.objects.active = rig
            bpy.ops.object.duplicate(linked=True)
            dup = {o.name.rsplit('.', 1)[0]: o for o in bpy.context.selected_objects}
            new_rig = dup[rig.name]; new_rig.location = (i*dx, (j-2.5)*dy, RIG_Z); new_rig.rotation_euler = (0, 0, 0)
            ARMY.append((new_rig, dup))
            for o in bpy.context.selected_objects: o.hide_render = True
    bpy.ops.object.select_all(action='DESELECT')
make_army()
def show_army(show, origin_x=0., t=0.):
    for k, (r, dup) in enumerate(ARMY):
        for o in dup.values(): o.hide_render = not show
        if not show: continue
        i, j = divmod(k, 6); r.location = (origin_x + .9 + i*1.5, (j-2.5)*1.35, RIG_Z)
        gait_pose(t*1.1 + k*.37, 'trot', 1.); bpy.context.view_layer.update()
        for ho in robot_objs:
            if ho is rig: continue
            ao = dup.get(ho.name)
            if ao is None: continue
            ao.rotation_mode = ho.rotation_mode; ao.rotation_quaternion = ho.rotation_quaternion; ao.rotation_euler = ho.rotation_euler; ao.location = ho.location

# ── 장면 ──────────────────────────────────────────────────────
LIGHTS = [key, fill, rim]; LIGHTS_SIZE_BOOST = LIGHTS
for L in LIGHTS: L['home'] = L.data.size; L['e'] = L.data.energy
def apply_film(frame):
    t = frame / FPS
    for L in LIGHTS: L.data.size = L['home']; L.data.energy = L['e']
    s.frame_set(frame); reset_pose(); hide_all_props(); hide_film(); xray(1.); place_actuators(False); show_army(False)
    rig.location = (0, 0, RIG_Z); rig.rotation_euler = (0, 0, 0); floor_gap(False)
    for o in grid_objects: o.hide_render = True
    cam_at(t)
    if t < 4:            # S1 등장 · 푸시인
        pass
    elif t < 10:         # S2 네 다리 분해 → 결합
        e = ease((t-4.4)/2.0) if t < 7.2 else 1-ease((t-7.4)/2.0)
        for leg, o in hips.items():
            o.location = hip_locations[leg] + Vector((.20*e*(1 if leg[0] == 'F' else -1), .18*e*(1 if leg[1] == 'L' else -1), .08*e))
        bpy.context.view_layer.update()
        if e > .3:
            TXT['legs'].hide_render = False; billboard(TXT['legs'], (0, 0, .66))
    elif t < 18:         # S3 투시 + 액추에이터 조립 + 관절 셋
        a = 1 - .55*ease((t-10.3)/1.0) if t < 17.2 else 1 - .55*(1-ease((t-17.2)/.8))
        xray(a)
        for k, (jn, amp, key_) in enumerate([('FL_hip_joint', .26, 'hip'), ('FL_thigh_joint', .32, 'thigh'), ('FL_calf_joint', -.40, 'calf')]):
            t0 = 12.2 + k*1.7
            if t0 <= t < t0 + 1.7:
                u = (t-t0)/1.5; set_joint(jn, amp*math.sin(math.pi*clamp01(u)))
                place_marker(jn, True, .6+.1*math.sin(math.pi*clamp01(u)))
            elif t >= t0: place_marker(jn, True, .6)
        bpy.context.view_layer.update()
        for k, (jn, key_) in enumerate([('FL_hip_joint', 'hip'), ('FL_thigh_joint', 'thigh'), ('FL_calf_joint', 'calf')]):
            if t >= 12.2 + k*1.7: label(key_, joint_world(jn), *[(-.12, -.16), (.14, .03), (.12, -.05)][k])
        place_actuators(True, spin=t*5., explode=1-ease((t-10.6)/1.4))
    elif t < 24:         # S4 접촉 · 토크 · 피드백
        u = (t-18.4)
        lift = ease(u/.8) if u < .8 else (1. if u < 1.4 else 1-ease((u-1.4)/.9)) if u < 2.3 else 0.
        set_joint('FL_thigh_joint', -.34*lift); set_joint('FL_calf_joint', -.38*lift)
        bpy.context.view_layer.update()
        if 20.7 <= t:
            fw = world(bpy.data.objects['FL_foot']); contact_ring.hide_render = False; contact_ring.location = (fw.x, fw.y, .004)
            r = .5 + 1.3*ease((t-20.7)/.6); contact_ring.scale = (r, r, 1)
        if 21.3 <= t:
            uu = clamp01((t-21.3)/1.4); set_joint('FL_calf_joint', -.42*math.sin(math.pi*uu)); set_joint('FL_thigh_joint', -.10*math.sin(math.pi*uu))
            bpy.context.view_layer.update()
            knee = joint_world('FL_calf_joint'); ax = joint_axis_world('FL_calf_joint'); cd = (Vector(cam.location) - knee).normalized()
            g = ease((t-21.3)/.5); torque_arc.hide_render = torque_tip.hide_render = g <= 0
            torque_arc.location = knee + cd*.10; torque_arc.rotation_mode = 'QUATERNION'; torque_arc.rotation_quaternion = ax.to_track_quat('Y', 'Z'); torque_arc.data.bevel_factor_end = g
            pts = torque_arc.data.splines[0].points; n = len(pts); tip_w = torque_arc.matrix_world @ Vector(pts[int((n-1)*g)].co[:3]); prev_w = torque_arc.matrix_world @ Vector(pts[max(0, int((n-1)*g)-1)].co[:3])
            torque_tip.location = tip_w; torque_tip.rotation_mode = 'QUATERNION'; torque_tip.rotation_quaternion = (tip_w-prev_w).normalized().to_track_quat('Z', 'Y')
            TXT['torque'].hide_render = False; billboard(TXT['torque'], (.05, 0, .66))
        if 22.3 <= t:
            g2 = ease((t-22.3)/.8); bw = world(base, (0, 0, .02)); kw = joint_world('FL_calf_joint'); hw = joint_world('FL_hip_joint'); cd = (Vector(cam.location) - kw).normalized()
            set_points(feedback_line, [tuple(kw + cd*.06), tuple(hw + cd*.06), tuple(kw + (bw-kw)*g2 + cd*.06)]); feedback_line.hide_render = False
    elif t < 31:         # S5 전면 카메라 · LiDAR
        bpy.context.view_layer.update()
        cam_pt = world(base, sensor_source['front_camera']['point']); fwd = (base.matrix_world.to_3x3() @ Vector((1, 0, 0))).normalized()
        left = (base.matrix_world.to_3x3() @ Vector((0, 1, 0))).normalized(); up = (base.matrix_world.to_3x3() @ Vector((0, 0, 1))).normalized()
        far = cam_pt + fwd*.85; hw_, hh_ = .15, .11
        corners = [far + left*hw_ + up*hh_, far - left*hw_ + up*hh_, far - left*hw_ - up*hh_, far + left*hw_ - up*hh_]
        g = ease((t-24.6)/.8)
        for k in range(4):
            o = frustum[k]; o.hide_render = g <= 0
            if g > 0: set_points(o, [tuple(cam_pt), tuple(cam_pt + (corners[k]-cam_pt)*g)])
        gr = ease((t-25.2)/.5)
        for k in range(4):
            o = frustum[4+k]; o.hide_render = gr <= 0
            if gr > 0: a_, b_ = corners[k], corners[(k+1) % 4]; set_points(o, [tuple(a_), tuple(a_ + (b_-a_)*gr)])
        gi = ease((t-25.6)/.6); rgb_plane.hide_render = gi <= 0
        if gi > 0: rgb_plane.location = far; rgb_plane.rotation_mode = 'QUATERNION'; rgb_plane.rotation_quaternion = fwd.to_track_quat('Z', 'Y'); rgb_plane.scale = (2*hw_*gi, 2*hh_*gi, 1)
        if t >= 25.0: label('cam', cam_pt, -.15, .06)
        lid = world(base, sensor_source['front_lidar']['point']); gl = ease((t-27.2)/.6); lidar_ring.hide_render = gl <= 0
        if gl > 0: lidar_ring.location = (lid.x, lid.y, lid.z+.02); lidar_ring.data.bevel_factor_end = gl
        for k, o in enumerate(lidar_rays):
            g_r = ease((t-27.6-k*.05)/.35); o.hide_render = g_r <= 0
            if g_r > 0:
                a = 2*math.pi*k/12 + (t-27.6)*.8; end = Vector((lid.x+.30*math.cos(a), lid.y+.30*math.sin(a), lid.z+.02)); set_points(o, [tuple(lid), tuple(lid + (end-lid)*g_r)])
        if t >= 27.4: label('lidar', lid, -.14, -.12)
    elif t < 42:         # S6 모듈 장착 → 분해도 + 라벨 → 결합
        drop = {'dock': (31.6, .34), 'hesai': (32.8, .40), 'd435': (34.0, .30)}
        expl = {'dock': Vector((-.06, 0, .10)), 'hesai': Vector((.03, 0, .17)), 'd435': Vector((.08, 0, .10))}
        offs = {}; lines = set()
        for k, (t0, h) in drop.items():
            if t < t0: continue
            u = ease((t-t0)/1.1); off = Vector((0, 0, h*(1-u)))
            if t >= 36.2:
                e = ease((t-36.2)/1.2) if t < 39.6 else 1-ease((t-39.6)/1.2); off = expl[k]*e
                if e > .05: lines.add(k)
                if e > .5: label('mod_'+k, Vector(MOD_HOME[k]) + off, *MOD_OFF[k])
            offs[k] = off
        place_modules(offs, lines)
    elif t < 52:         # S7 명령 셋
        u = t-42
        if u < 3.4:
            gait_pose(u, 'trot', ease(u/.4)); arrow(arrow_fwd, cones['fwd'], (.34, 0, .36), (.74, 0, .36), ease((u-.3)/.5))
            TXT['vx'].hide_render = False; billboard(TXT['vx'], (.1, 0, .64))
        elif u < 6.8:
            gait_pose(u, 'lateral', 1.); arrow(arrow_lat, cones['lat'], (0, .17, .36), (0, .60, .36), ease((u-3.6)/.5))
            TXT['vy'].hide_render = False; billboard(TXT['vy'], (.1, 0, .64))
        else:
            rig.rotation_euler = (0, 0, .28*math.sin(2*math.pi*(u-6.8)/3.2)); gait_pose(u, 'yaw', 1.)
            g = ease((u-6.9)/.6); arrow_yaw.hide_render = g <= 0; cones['yaw'].hide_render = g <= 0
            if g > 0:
                arrow_yaw.data.bevel_factor_end = g; pts = arrow_yaw.data.splines[0].points; n = len(pts); k = int((n-1)*g)
                tip = Vector(pts[k].co[:3]); prev = Vector(pts[max(0, k-1)].co[:3]); cones['yaw'].location = tip; cones['yaw'].rotation_mode = 'QUATERNION'; cones['yaw'].rotation_quaternion = (tip-prev).normalized().to_track_quat('Z', 'Y')
            TXT['wz'].hide_render = False; billboard(TXT['wz'], (.1, 0, .64))
    elif t < 59:         # S8 격자 · 레이저 (2.6 초마다 한 번 훑는다)
        reveal = ease((t-52.3)/.8)
        for o in grid_objects: o.hide_render = False
        for o in grid_objects:
            if o.type == 'CURVE': o.data.bevel_factor_end = reveal
        for idx, o in enumerate(point_objects): o.scale = (reveal, reveal, reveal); o.data.materials[0] = gridmat
        if t >= 53.5:
            tt = ((t-53.5) % 2.6) / 2.6 * 72
            for i, col in enumerate(ray_objects):
                t0 = i*3.6
                for j, o in enumerate(col):
                    g = clamp01((tt - t0)/6.); o.hide_render = g <= 0 or tt > t0 + 22
                    if g > 0: x, y = xs[i], ys[j]; zb = height(x, y)+.003; set_points(o, [(x, y, RAY_TOP), (x, y, mix(RAY_TOP, zb, g))])
                lit = clamp01((tt - t0 - 5)/3.)
                for j in range(11):
                    po = point_objects[i*11+j]; sc = 1+1.1*lit*(1 if tt < t0+30 else .45); po.scale = (sc, sc, sc); po.data.materials[0] = brightmat if lit > 0 else gridmat
        TXT['grid'].hide_render = False; billboard(TXT['grid'], (-.55, .55, .12))
    elif t < 70:         # S9 틈 건너기 + 네 조건 (측면 추적)
        floor_gap(True); u = t-59; x = min(3.3, .45*u); rig.location = (x, 0, RIG_Z); gait_pose(u, 'trot', ease(u/.5))
        bpy.context.view_layer.update()
        orbit(96, 18, 2.7, (x+.1, 0, .22), 42)
        if u > 1.2: TXT['alive'].hide_render = False; billboard(TXT['alive'], (x+.05, 0, .72))
        if u > 3.0:
            g = ease((u-3.0)/.8); set_points(dim_line, [(0, -.62, .005), (3.0*g, -.62, .005)]); dim_line.hide_render = False
            TXT['m3'].hide_render = False; billboard(TXT['m3'], (2.5, -.74, .10))
        if u > 5.0: TXT['mae'].hide_render = False; billboard(TXT['mae'], (x+.05, 0, .86))
        if u > 7.0:
            g = ease((u-7.0)/.8); set_points(lane_l, [(-.3, .75, .005), (-.3+3.8*g, .75, .005)]); set_points(lane_r, [(-.3, -.75, .005), (-.3+3.8*g, -.75, .005)])
            lane_l.hide_render = lane_r.hide_render = False; TXT['lane'].hide_render = False; billboard(TXT['lane'], (x+.8, .85, .14))
    else:                # S10 대군 · 크레인 아웃
        u = t-70; x = 3.3 + .45*u; rig.location = (x, 0, RIG_Z); gait_pose(t-59, 'trot', 1.); floor_gap(True)
        e = ease(u/4.)
        orbit(mix(110, 140, e), mix(12, 32, e), mix(2.6, 11., e), (x + mix(.2, 5.5, e), 0, .3), 35)
        for L in LIGHTS_SIZE_BOOST: L.data.size = mix(L['home'], L['home']*3, e); L.data.energy = mix(L['e'], L['e']*4, e)
        show_army(u > .3, origin_x=x, t=t-59)
        TXT['army'].hide_render = u < 1.6
        if u >= 1.6: billboard(TXT['army'], (x + 4.6, 0, 2.3))
    bpy.context.view_layer.update()

def render(frame, out):
    apply_film(frame); s.render.filepath = str(out / f'frame-{frame:04d}.png'); bpy.ops.render.render(write_still=True)

if argv and argv[0] == '--test':
    out = ROOT / 'film-test'; out.mkdir(exist_ok=True)
    for sec in [float(x) for x in argv[1:] if x.replace('.', '', 1).isdigit()]:
        render(int(round(sec*FPS)), out)
    print('FILM_TEST_DONE')
elif argv and argv[0] == '--sequence':
    nums = [int(x) for x in argv[1:] if x.isdigit()]
    lo = nums[0] if nums else 0; hi = nums[1] if len(nums) > 1 else DUR*FPS
    out = ROOT / ('film-cycles-frames' if USE_CYCLES else 'film-frames'); out.mkdir(exist_ok=True); t0 = time.time()
    for f in range(lo, hi + 1):
        if (out / f'frame-{f:04d}.png').exists(): continue
        render(f, out)
        if f % 48 == 0: print('FILM_PROGRESS', f, round((time.time()-t0)/60, 1), 'min', flush=True)
    print('FILM_SEQUENCE_DONE', lo, hi, round((time.time()-t0)/60, 1), 'min')
else:
    print('usage: --test sec... | --sequence [lo hi] [cycles]')
