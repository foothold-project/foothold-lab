# -*- coding: utf-8 -*-
"""v6 · 카드가 말하는 동작을 로봇이 그 순간 수행하는 연속 구간.

팀장 지시 2026-10-02: 「바닥을 딛고 몸을 지탱」이면 발이 바닥에 닿는 동작,
「목표 각도를 따라」면 관절이 돌고 발이 옮겨지는 것, 「주변 영상을 봅니다」면
돌아서 측면을 보이며 전면 카메라에 RGB 가 들어오는 것, 「어느 방향으로」면 제자리
보행·횡이동·회전과 vx·vy·wz 가 차례로. 11쪽은 정면에서 그 자리에서 돌아 측면이
되고(점프 없음), 187 관측은 위에서 내려오는 레이저가 격자를 훑는다.

v5 (build_v5.py) 와 같은 뼈대다. 같은 blend(go2-technical-v4) 에서 같은 재질·격자를
다시 만들고, 같은 카메라 식(반지름 3 · 직교)으로 찍는다. 그래서 v5 상태에서 v6 구간으로
이어 붙여도 화각이 같다. 보행·관절 동작은 «설명용 기구학» 이지 정책 출력이 아니다.

쓰는 법 (Blender 4.5 · background):
  blender -b --python build_v6.py -- --test 320 400 470 ...   대표 프레임 PNG (v6-test/)
  blender -b --python build_v6.py -- --sequence               전 구간 PNG (v6-frames/)
  blender -b --python build_v6.py -- --stills                 상태 정지화 (go2-<state>-v6.png)
그 뒤 package_v6.py 가 WebP 와 v6-manifest 를 만든다.
"""
import bpy, json, math, sys
from pathlib import Path
from mathutils import Vector, Quaternion

ROOT = Path(__file__).resolve().parent
RGB_SAMPLE = (ROOT.parents[2] / '20260916-3dgs-test/_out/colmap/undistorted/images/0000.jpg')

bpy.ops.wm.open_mainfile(filepath=str(ROOT / 'go2-technical-v4.blend'))
s = bpy.context.scene
s.frame_set(1)
for o in list(bpy.data.objects):
    o.animation_data_clear()
    if o.type == 'CAMERA': o.data.animation_data_clear()
    if o.name.startswith(('AXIS_', 'BODY_', 'JOINT_MARKER')):
        bpy.data.objects.remove(o, do_unlink=True)
s.timeline_markers.clear()
s.name = 'GO2_v6_explanatory'
rig = bpy.data.objects['GO2_ROOT']
rig.rotation_euler = (0, 0, 0)
rig.rotation_mode = 'XYZ'
cam = s.camera
base = bpy.data.objects['base']
source = json.loads((ROOT/'geometry-manifest.json').read_text())
sensor_source = json.loads((ROOT/'v4-sensor-and-joint-anchors.json').read_text())['front']['sensors']
meshes = [bpy.data.objects[row['object']] for row in source['geometry']]
for o in meshes: o.hide_render = False
joints = source['joints']
JOINT = {j['name']: j for j in joints}
for j in joints:
    o = bpy.data.objects[j['child']]
    o.rotation_mode = 'QUATERNION'
    o.rotation_quaternion = Quaternion(Vector(j['axis_parent']), j['initial_radians'])
hips = {leg: bpy.data.objects[leg+'_hip'] for leg in ['FL','FR','RL','RR']}
hip_locations = {leg: o.location.copy() for leg, o in hips.items()}
s.render.engine = 'BLENDER_EEVEE_NEXT'
s.render.film_transparent = True
s.render.image_settings.file_format = 'PNG'
s.render.image_settings.color_mode = 'RGBA'
s.render.resolution_percentage = 100
s.render.fps = 24
s.view_settings.view_transform = 'AgX'
s.view_settings.look = 'AgX - Medium Low Contrast'
s.view_settings.exposure = -.45
cam.data.type = 'ORTHO'

def mat(name, color, emission=.12):
    m = bpy.data.materials.new(name); m.diffuse_color = (*color, 1); m.use_nodes = True
    bs = m.node_tree.nodes.get('Principled BSDF')
    bs.inputs['Base Color'].default_value = (*color, 1)
    bs.inputs['Roughness'].default_value = .8
    bs.inputs['Emission Color'].default_value = (*color, 1)
    bs.inputs['Emission Strength'].default_value = emission
    return m

gridmat = mat('V6_grid_teal', (.025, .35, .27), .3)
linemat = mat('V6_grid_lines', (.055, .22, .18), .15)
brightmat = mat('V6_active', (.11, .57, .40), .5)
groundmat = mat('V6_ground', (.80, .82, .78), .02)
accentmat = mat('V6_accent', (.05, .48, .43), .55)
rgbmat = None

def line(name, points, material, radius=.001, cyclic=False):
    cu = bpy.data.curves.new(name, 'CURVE'); cu.dimensions = '3D'; cu.bevel_depth = radius; cu.bevel_resolution = 2
    sp = cu.splines.new('POLY'); sp.points.add(len(points)-1)
    for p, xyz in zip(sp.points, points): p.co = (*xyz, 1)
    sp.use_cyclic_u = cyclic
    o = bpy.data.objects.new(name, cu); s.collection.objects.link(o); cu.materials.append(material)
    return o

def set_points(o, points):
    sp = o.data.splines[0]
    for p, xyz in zip(sp.points, points): p.co = (*xyz, 1)

def circle_pts(center, radius, axis='z', n=48, start=0., end=2*math.pi):
    out = []
    for i in range(n):
        a = start + (end-start)*i/(n-1)
        c, si = radius*math.cos(a), radius*math.sin(a)
        if axis == 'z': out.append((center[0]+c, center[1]+si, center[2]))
        elif axis == 'y': out.append((center[0]+c, center[1], center[2]+si))
        else: out.append((center[0], center[1]+c, center[2]+si))
    return out

# ── v5 와 같은 격자 ─────────────────────────────────────────────
def height(x, y):
    if x > .40: return .065 + .012*math.sin(y*7)
    if x < -.50: return -.035 + .006*math.sin(y*6)
    return 0.0
xs = [round(-.8+i*.1, 4) for i in range(17)]
ys = [round(-.5+i*.1, 4) for i in range(11)]
grid_objects = []; grid_points = []; point_objects = []
for i, x in enumerate(xs):
    for j, y in enumerate(ys):
        p = (x, y, height(x, y)+.003); grid_points.append(p)
        bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=1, radius=.0065, location=p)
        o = bpy.context.object; o.name = f'V6_height_{i:02d}_{j:02d}'; o.data.materials.append(gridmat)
        point_objects.append(o); grid_objects.append(o)
for i, x in enumerate(xs):
    grid_objects.append(line('V6_grid_x_'+str(i), [(x, y, height(x, y)+.002) for y in ys], linemat, .0007))
for j, y in enumerate(ys):
    grid_objects.append(line('V6_grid_y_'+str(j), [(x, y, height(x, y)+.002) for x in xs], linemat, .0007))
# 레이저: 격자 열마다 11개, 위(z=RAY_TOP)에서 바닥으로 내려온다
RAY_TOP = .42
ray_objects = []
for i, x in enumerate(xs):
    col = []
    for j, y in enumerate(ys):
        col.append(line(f'V6_ray_{i:02d}_{j:02d}', [(x, y, RAY_TOP), (x, y, RAY_TOP)], brightmat, .0009))
    ray_objects.append(col)

# ── 소품 ───────────────────────────────────────────────────────
bpy.ops.mesh.primitive_circle_add(vertices=96, radius=1.9, fill_type='NGON', location=(0, 0, -.002))
ground = bpy.context.object; ground.name = 'V6_ground'
# 가장자리가 종이 배경으로 녹아드는 원판 (구형 그라데이션 -> 알파)
gm = bpy.data.materials.new('V6_ground_soft'); gm.use_nodes = True
gm.surface_render_method = 'BLENDED'
gn = gm.node_tree.nodes; gl = gm.node_tree.links; gb = gn.get('Principled BSDF')
gb.inputs['Base Color'].default_value = (.78, .80, .76, 1); gb.inputs['Roughness'].default_value = .9
gb.inputs['Emission Color'].default_value = (.78, .80, .76, 1); gb.inputs['Emission Strength'].default_value = .05
tc = gn.new('ShaderNodeTexCoord'); grad = gn.new('ShaderNodeTexGradient'); grad.gradient_type = 'SPHERICAL'
ramp = gn.new('ShaderNodeValToRGB'); ramp.color_ramp.elements[0].position = .35; ramp.color_ramp.elements[0].color = (0, 0, 0, 1)
ramp.color_ramp.elements[1].position = .95; ramp.color_ramp.elements[1].color = (1, 1, 1, 1)
gl.new(tc.outputs['Object'], grad.inputs['Vector']); gl.new(grad.outputs['Fac'], ramp.inputs['Fac']); gl.new(ramp.outputs['Color'], gb.inputs['Alpha'])
ground.data.materials.append(gm)
contact_ring = line('V6_contact_ring', circle_pts((0, 0, .004), .055, 'z'), brightmat, .0025, cyclic=True)
torque_arc = line('V6_torque_arc', circle_pts((0, 0, 0), .075, 'y', 40, math.radians(200), math.radians(-40)), accentmat, .003)
torque_tip = None
bpy.ops.mesh.primitive_cone_add(radius1=.016, radius2=0, depth=.04, location=(0, 0, 0))
torque_tip = bpy.context.object; torque_tip.name = 'V6_torque_tip'; torque_tip.data.materials.append(accentmat)
foot_trail = line('V6_foot_trail', [(0, 0, 0)]*40, brightmat, .002)
feedback_line = line('V6_feedback', [(0, 0, 0), (0, 0, 0), (0, 0, 0)], accentmat, .002)
joint_markers = {}
for j in joints:
    ring = line('V6_jm_'+j['name'], circle_pts((0, 0, 0), .04, 'z', 36), accentmat, .0022, cyclic=True)
    axis = line('V6_ja_'+j['name'], [(0, 0, -.11), (0, 0, .11)], accentmat, .0016)
    joint_markers[j['name']] = (ring, axis)
frustum = [line('V6_frustum_'+str(k), [(0, 0, 0), (0, 0, 0)], accentmat, .0014) for k in range(8)]
bpy.ops.mesh.primitive_plane_add(size=1, location=(0, 0, 0))
rgb_plane = bpy.context.object; rgb_plane.name = 'V6_rgb_plane'
rgbmat = bpy.data.materials.new('V6_rgb'); rgbmat.use_nodes = True
_nodes = rgbmat.node_tree.nodes; _bsdf = _nodes.get('Principled BSDF')
_tex = _nodes.new('ShaderNodeTexImage')
if RGB_SAMPLE.exists():
    _tex.image = bpy.data.images.load(str(RGB_SAMPLE))
rgbmat.node_tree.links.new(_tex.outputs['Color'], _bsdf.inputs['Base Color'])
rgbmat.node_tree.links.new(_tex.outputs['Color'], _bsdf.inputs['Emission Color'])
_bsdf.inputs['Emission Strength'].default_value = .7
rgb_plane.data.materials.append(rgbmat)
lidar_ring = line('V6_lidar_ring', circle_pts((0, 0, 0), .46, 'z', 64), accentmat, .0018, cyclic=True)
lidar_rays = [line('V6_lidar_ray_'+str(k), [(0, 0, 0), (0, 0, 0)], accentmat, .0011) for k in range(12)]
arrow_fwd = line('V6_arrow_fwd', [(.16, 0, .36), (.16, 0, .36)], accentmat, .004)
arrow_lat = line('V6_arrow_lat', [(0, .16, .36), (0, .16, .36)], accentmat, .004)
arrow_yaw = line('V6_arrow_yaw', circle_pts((0, 0, .52), .30, 'z', 40, math.radians(-20), math.radians(200)), accentmat, .004)
cones = {}
for k in ('fwd', 'lat', 'yaw'):
    bpy.ops.mesh.primitive_cone_add(radius1=.028, radius2=0, depth=.07, location=(0, 0, 0))
    c = bpy.context.object; c.name = 'V6_cone_'+k; c.data.materials.append(accentmat); cones[k] = c

PROPS = ([ground, contact_ring, torque_arc, torque_tip, foot_trail, feedback_line, rgb_plane, lidar_ring,
          arrow_fwd, arrow_lat, arrow_yaw] + list(cones.values()) + frustum + lidar_rays
         + [o for pair in joint_markers.values() for o in pair])

def hide_all_props():
    for o in PROPS: o.hide_render = True
    for o in grid_objects: o.hide_render = True
    for col in ray_objects:
        for o in col: o.hide_render = True

# ── 도우미 ─────────────────────────────────────────────────────
def ease(t): return .5-.5*math.cos(math.pi*max(0, min(1, t)))
def mix(a, b, t): return a+(b-a)*t
def clamp01(t): return max(0., min(1., t))

def set_joint(name, delta):
    j = JOINT[name]; o = bpy.data.objects[j['child']]
    o.rotation_quaternion = Quaternion(Vector(j['axis_parent']), j['initial_radians']+delta)

def reset_pose():
    for j in joints: set_joint(j['name'], 0.)
    for leg, o in hips.items(): o.location = hip_locations[leg]
    rig.rotation_euler = (0, 0, 0)

def world(o, local=(0, 0, 0)):
    return o.matrix_world @ Vector(local)

def joint_world(name):
    return world(bpy.data.objects[JOINT[name]['child']])

def joint_axis_world(name):
    j = JOINT[name]; parent = bpy.data.objects[j['child']].parent
    return (parent.matrix_world.to_3x3() @ Vector(j['axis_parent'])).normalized()

def place_marker(name, show, pulse=1.):
    ring, axis = joint_markers[name]
    ring.hide_render = axis.hide_render = not show
    if not show: return
    c = joint_world(name); ax = joint_axis_world(name)
    q = ax.to_track_quat('Z', 'Y')
    for o in (ring, axis):
        o.location = c; o.rotation_mode = 'QUATERNION'; o.rotation_quaternion = q
        o.scale = (pulse, pulse, pulse)

def camera(angle_deg, scale, z, target):
    a = math.radians(angle_deg)
    cam.location = (target[0]+3*math.cos(a), target[1]+3*math.sin(a), z)
    cam.rotation_euler = (Vector(target)-cam.location).to_track_quat('-Z', 'Y').to_euler()
    cam.data.ortho_scale = scale

def arrow(line_obj, cone, p0, p1, grow):
    line_obj.hide_render = cone.hide_render = grow <= 0
    if grow <= 0: return
    p0 = Vector(p0); p1 = Vector(p1); d = (p1-p0)
    tip = p0 + d*grow
    set_points(line_obj, [tuple(p0), tuple(tip)])
    cone.location = tip; cone.rotation_mode = 'QUATERNION'
    cone.rotation_quaternion = d.normalized().to_track_quat('Z', 'Y')

def gait_pose(t, mode='trot', amp=1.):
    """설명용 기구학. 정책 출력이 아니다. t 는 주기 단위(1.0 = 한 주기)."""
    phase = {'FL': 0., 'RR': 0., 'FR': math.pi, 'RL': math.pi}
    for leg in hips:
        p = 2*math.pi*t + phase[leg]
        lift = max(0., math.sin(p))
        if mode == 'trot':
            set_joint(leg+'_thigh_joint', amp*(.28*lift - .14*math.cos(p)))
            set_joint(leg+'_calf_joint', amp*(-.50*lift))
            set_joint(leg+'_hip_joint', 0.)
        elif mode == 'lateral':
            side = 1. if leg[1] == 'L' else -1.
            set_joint(leg+'_hip_joint', amp*side*(.22*math.sin(p)))
            set_joint(leg+'_thigh_joint', amp*(.16*lift))
            set_joint(leg+'_calf_joint', amp*(-.28*lift))
        elif mode == 'yaw':
            set_joint(leg+'_thigh_joint', amp*(.14*lift))
            set_joint(leg+'_calf_joint', amp*(-.26*lift))
            set_joint(leg+'_hip_joint', 0.)

# ── 구간 ───────────────────────────────────────────────────────
SEGMENTS = [
    {'id': 'front_to_side', 'start': 300, 'end': 359, 'endState': 'side_grid6'},
    {'id': 'scan_rays',     'start': 360, 'end': 431, 'endState': 'scan_done'},
    {'id': 'joints',        'start': 432, 'end': 503, 'endState': 'joints_close'},
    {'id': 'contact',       'start': 504, 'end': 563, 'endState': 'stance'},
    {'id': 'feedback',      'start': 564, 'end': 623, 'endState': 'feedback_end'},
    {'id': 'sensors',       'start': 624, 'end': 719, 'endState': 'sensors_end'},
    {'id': 'commands',      'start': 720, 'end': 863, 'endState': 'commands_end'},
    # 2026-10-02 축 설명 장 · 21쪽 feet_air_time: 옆모습 제자리 트롯 3주기(24프레임 = 1주기). 864~871 은 서 있다가 들어간다.
    {'id': 'walk_side',     'start': 864, 'end': 935, 'endState': 'side_walk'},
    # 옆모습에서 명령 장면(720 의 카메라 -28°)으로 «그 자리에서» 돈다. 다리는 걷기에서 서기로 가라앉는다.
    {'id': 'to_commands',   'start': 936, 'end': 959, 'endState': 'commands_start'},
]
STATES = {'front6': 300, 'side_grid6': 359, 'scan_done': 431, 'assembled6': 432, 'joints_close': 503,
          'stance': 563, 'feedback_end': 623, 'sensors_end': 719, 'commands_end': 863, 'side_walk': 864, 'commands_start': 959}
ASSEMBLED = dict(angle=45, scale=1.13, z=1.02, target=(0, 0, .22))   # v5 frame 193 과 같다

def apply(frame, res=(960, 720)):
    s.frame_set(frame); reset_pose(); hide_all_props()
    bpy.context.view_layer.update()
    grid = False; reveal = 0.
    if 300 <= frame <= 359:
        # 11쪽 0->1: v5 front(1) 에서 v5 side_grid(241) 로 «그 자리에서» 돈다
        t = ease((frame-300)/59.)
        camera(mix(0, 90, t), mix(.76, 1.93, t), mix(.53, 1.80, t), (0, 0, mix(.22, .12, t)))
        grid = frame >= 340; reveal = ease((frame-340)/19.)
    elif 360 <= frame <= 431:
        camera(90, 1.93, 1.80, (0, 0, .12)); grid = True; reveal = 1.
        # 레이저가 열(17)을 왼쪽부터 훑는다. 열 하나에 4프레임, 내려오는 데 6프레임.
        for i, col in enumerate(ray_objects):
            t0 = 360 + i*3.6
            for j, o in enumerate(col):
                g = clamp01((frame - t0)/6.)
                o.hide_render = g <= 0 or frame > t0 + 22
                if g > 0:
                    x, y = xs[i], ys[j]; zb = height(x, y)+.003
                    set_points(o, [(x, y, RAY_TOP), (x, y, mix(RAY_TOP, zb, g))])
            lit = clamp01((frame - t0 - 5)/3.)
            for j in range(11):
                po = point_objects[i*11+j]; sc = 1+1.1*lit*(1 if frame < t0+30 else .45)
                po.scale = (sc, sc, sc); po.data.materials[0] = brightmat if lit > 0 else gridmat
    elif 432 <= frame <= 503:
        # 관절: 조립 상태(v5 193)에서 FL 다리로 당겨 고관절 -> 허벅지 -> 무릎
        t = ease((frame-432)/14.)
        bpy.context.view_layer.update()
        hip_w = joint_world('FL_hip_joint')
        tgt = (mix(0, hip_w.x-.05, t), mix(0, hip_w.y, t), mix(.22, hip_w.z-.12, t))
        camera(mix(45, 35, t), mix(1.13, .66, t), mix(1.02, .62, t), tgt)
        for k, (jn, amp) in enumerate([('FL_hip_joint', .28), ('FL_thigh_joint', .34), ('FL_calf_joint', -.40)]):
            a, b = 448 + k*14, 448 + k*14 + 14
            if a <= frame < b + 4:
                u = (frame-a)/14.; d = amp*math.sin(math.pi*clamp01(u))
                set_joint(jn, d)
        bpy.context.view_layer.update()
        for k, jn in enumerate(['FL_hip_joint', 'FL_thigh_joint', 'FL_calf_joint']):
            on = frame >= 446 + k*14
            place_marker(jn, on, 1. + .25*math.sin(math.pi*clamp01((frame-446-k*14)/10.)))
        if frame >= 490:
            # 12 자유도: 모든 관절 마커, 순서대로 점멸
            for idx, j in enumerate(joints):
                on = frame >= 490 + (idx % 12)
                place_marker(j['name'], on, 1.+.2*math.sin((frame-490+idx)*.8))
    elif 504 <= frame <= 563:
        # 접촉: 낮은 3/4 로 물러나고, 바닥 등장, FL 발이 들렸다 내려와 닿는다
        t = ease((frame-504)/16.)
        bpy.context.view_layer.update(); hip_w = joint_world('FL_hip_joint')
        tgt = (mix(hip_w.x-.05, .05, t), mix(hip_w.y, 0, t), mix(hip_w.z-.12, .14, t))
        camera(mix(35, 60, t), mix(.66, 1.28, t), mix(.62, .55, t), tgt)
        ground.hide_render = False; gs = ease((frame-506)/8.); ground.scale = (gs, gs, 1)
        lift = 0.
        if 520 <= frame < 534: lift = ease((frame-520)/13.)
        elif 534 <= frame < 540: lift = 1.
        elif 540 <= frame < 554: lift = 1-ease((frame-540)/13.)
        set_joint('FL_thigh_joint', -.34*lift); set_joint('FL_calf_joint', -.38*lift)
        bpy.context.view_layer.update()
        if 552 <= frame <= 563:
            fw = world(bpy.data.objects['FL_foot'])
            contact_ring.hide_render = False; contact_ring.location = (fw.x, fw.y, .004)
            r = .5 + 1.3*ease((frame-552)/10.); contact_ring.scale = (r, r, 1)
    elif 564 <= frame <= 623:
        # 피드백: 무릎에 토크 호살표, 종아리 회전, 발 궤적, 몸으로 되돌아가는 선
        t = ease((frame-564)/14.)
        bpy.context.view_layer.update(); knee = joint_world('FL_calf_joint')
        tgt = (mix(.05, knee.x, t), mix(0, knee.y-.1, t), mix(.14, knee.z-.03, t))
        camera(mix(60, 70, t), mix(1.28, .72, t), mix(.55, .45, t), tgt)
        ground.hide_render = False; ground.scale = (1, 1, 1)
        u = clamp01((frame-580)/28.); d = -.42*math.sin(math.pi*u)
        set_joint('FL_calf_joint', d); set_joint('FL_thigh_joint', -.10*math.sin(math.pi*u))
        bpy.context.view_layer.update()
        knee = joint_world('FL_calf_joint'); ax = joint_axis_world('FL_calf_joint')
        g = ease((frame-566)/10.)
        torque_arc.hide_render = torque_tip.hide_render = g <= 0
        if g > 0:
            torque_arc.location = knee; torque_arc.rotation_mode = 'QUATERNION'
            torque_arc.rotation_quaternion = ax.to_track_quat('Y', 'Z')
            torque_arc.data.bevel_factor_end = g
            pts = torque_arc.data.splines[0].points; n = len(pts)
            tip_local = Vector(pts[int((n-1)*g)].co[:3]); prev_local = Vector(pts[max(0, int((n-1)*g)-1)].co[:3])
            tip_w = torque_arc.matrix_world @ tip_local; prev_w = torque_arc.matrix_world @ prev_local
            torque_tip.location = tip_w; torque_tip.rotation_mode = 'QUATERNION'
            torque_tip.rotation_quaternion = (tip_w-prev_w).normalized().to_track_quat('Z', 'Y')
        # 발 궤적: 580~608 의 발 위치를 미리 계산한 선
        if frame >= 582:
            pts = []
            saved = (bpy.data.objects['FL_calf'].rotation_quaternion.copy(), bpy.data.objects['FL_thigh'].rotation_quaternion.copy())
            for f in range(580, min(frame, 608)+1, 1):
                uu = clamp01((f-580)/28.)
                set_joint('FL_calf_joint', -.42*math.sin(math.pi*uu)); set_joint('FL_thigh_joint', -.10*math.sin(math.pi*uu))
                bpy.context.view_layer.update(); pts.append(tuple(world(bpy.data.objects['FL_foot'])))
            bpy.data.objects['FL_calf'].rotation_quaternion, bpy.data.objects['FL_thigh'].rotation_quaternion = saved
            bpy.context.view_layer.update()
            while len(pts) < 40: pts.append(pts[-1])
            set_points(foot_trail, pts[:40]); foot_trail.hide_render = False
        if frame >= 604:
            g2 = ease((frame-604)/14.)
            bw = world(base, (0, 0, .02)); kw = joint_world('FL_calf_joint'); hw = joint_world('FL_hip_joint')
            set_points(feedback_line, [tuple(kw), tuple(hw), tuple(kw + (bw-kw)*g2)])
            feedback_line.hide_render = False
    elif 624 <= frame <= 719:
        # 센서: 돌아서 앞·측면을 보이고, 머리에서 시야뿔 -> RGB 프레임 -> LiDAR 링
        t = ease((frame-624)/22.)
        bpy.context.view_layer.update(); knee = joint_world('FL_calf_joint')
        tgt = (mix(knee.x, .22, t), mix(knee.y-.1, .05, t), mix(knee.z-.03, .12, t))
        camera(mix(70, -28, t), mix(.72, 1.22, t), mix(.45, .72, t), tgt)
        bpy.context.view_layer.update()
        cam_pt = world(base, sensor_source['front_camera']['point'])
        fwd = (base.matrix_world.to_3x3() @ Vector((1, 0, 0))).normalized()
        left = (base.matrix_world.to_3x3() @ Vector((0, 1, 0))).normalized()
        up = (base.matrix_world.to_3x3() @ Vector((0, 0, 1))).normalized()
        far = cam_pt + fwd*.52; hw_, hh_ = .22, .165
        corners = [far + left*hw_ + up*hh_, far - left*hw_ + up*hh_, far - left*hw_ - up*hh_, far + left*hw_ - up*hh_]
        g = ease((frame-640)/18.)
        for k in range(4):
            o = frustum[k]; o.hide_render = g <= 0
            if g > 0: set_points(o, [tuple(cam_pt), tuple(cam_pt + (corners[k]-cam_pt)*g)])
        g_rect = ease((frame-654)/10.)
        for k in range(4):
            o = frustum[4+k]; o.hide_render = g_rect <= 0
            if g_rect > 0:
                a, b = corners[k], corners[(k+1) % 4]; set_points(o, [tuple(a), tuple(a + (b-a)*g_rect)])
        g_img = ease((frame-664)/14.)
        rgb_plane.hide_render = g_img <= 0
        if g_img > 0:
            rgb_plane.location = far; rgb_plane.rotation_mode = 'QUATERNION'
            rgb_plane.rotation_quaternion = fwd.to_track_quat('Z', 'Y')
            rgb_plane.scale = (2*hw_*g_img, 2*hh_*g_img, 1)
        lid = world(base, sensor_source['front_lidar']['point'])
        g_ring = ease((frame-688)/14.)
        lidar_ring.hide_render = g_ring <= 0
        if g_ring > 0:
            lidar_ring.location = (lid.x, lid.y, lid.z+.02); lidar_ring.data.bevel_factor_end = g_ring
        for k, o in enumerate(lidar_rays):
            g_r = ease((frame-696-k*1.2)/8.)
            o.hide_render = g_r <= 0
            if g_r > 0:
                a = 2*math.pi*k/12; end = Vector((lid.x+.46*math.cos(a), lid.y+.46*math.sin(a), lid.z+.02))
                set_points(o, [tuple(lid), tuple(lid + (end-lid)*g_r)])
    elif 720 <= frame <= 863:
        # 명령: vx 제자리 트롯 -> vy 횡이동 -> wz 회전. 화살표가 설명 순서대로.
        t = ease((frame-720)/16.)
        camera(mix(-28, 38, t), mix(1.22, 1.34, t), mix(.72, .95, t), (mix(.22, 0, t), mix(.05, 0, t), mix(.12, .20, t)))
        ground.hide_render = False; ground.scale = (1, 1, 1)
        phase = (frame-720)/24.
        if frame < 768:
            gait_pose(phase, 'trot', ease((frame-724)/8.))
            arrow(arrow_fwd, cones['fwd'], (.18, 0, .36), (.62, 0, .36), ease((frame-726)/10.))
        elif frame < 816:
            gait_pose(phase, 'lateral', 1.)
            arrow(arrow_lat, cones['lat'], (0, .18, .36), (0, .62, .36), ease((frame-770)/10.))
        else:
            u = (frame-816)/47.
            rig.rotation_euler = (0, 0, .28*math.sin(2*math.pi*u))
            gait_pose(phase, 'yaw', 1.)
            g = ease((frame-818)/12.)
            arrow_yaw.hide_render = g <= 0; cones['yaw'].hide_render = g <= 0
            if g > 0:
                arrow_yaw.data.bevel_factor_end = g
                pts = arrow_yaw.data.splines[0].points; n = len(pts); k = int((n-1)*g)
                tip = Vector(pts[k].co[:3]); prev = Vector(pts[max(0, k-1)].co[:3])
                cones['yaw'].location = tip; cones['yaw'].rotation_mode = 'QUATERNION'
                cones['yaw'].rotation_quaternion = (tip-prev).normalized().to_track_quat('Z', 'Y')
    elif 864 <= frame <= 935:
        # 옆모습(오른쪽에서 본다) · 바닥 원반 · 제자리 트롯. 발 공중 시간을 설명하는 데 쓴다.
        camera(-90, 1.30, .62, (0, 0, .26))   # 오른쪽에서 본다 → 머리가 오른쪽(읽는 방향)
        ground.hide_render = False; ground.scale = (1, 1, 1)
        gait_pose((frame-864)/24., 'trot', ease((frame-868)/8.))
    elif 936 <= frame <= 959:
        t = ease((frame-936)/23.)
        camera(mix(-90, -28, t), mix(1.30, 1.22, t), mix(.62, .72, t), (mix(0, .22, t), mix(0, .05, t), mix(.26, .12, t)))
        ground.hide_render = False; ground.scale = (1, 1, 1)
        gait_pose((frame-864)/24., 'trot', 1-ease((frame-936)/12.))
    for o in grid_objects: o.hide_render = not grid
    if grid:
        for idx, o in enumerate(point_objects):
            if not (360 <= frame <= 431):
                o.scale = (reveal, reveal, reveal); o.data.materials[0] = gridmat
        for o in grid_objects:
            if o.type == 'CURVE': o.data.bevel_factor_end = reveal
    s.render.resolution_x, s.render.resolution_y = res
    bpy.context.view_layer.update()

def bounds():
    from bpy_extras.object_utils import world_to_camera_view
    pts = [world_to_camera_view(s, cam, o.matrix_world @ Vector(v)) for o in meshes for v in o.bound_box]
    return [round(min(p.x for p in pts), 3), round(1-max(p.y for p in pts), 3),
            round(max(p.x for p in pts), 3), round(1-min(p.y for p in pts), 3)]

argv = sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else []
if argv and argv[0] == '--test':
    out = ROOT/'v6-test'; out.mkdir(exist_ok=True); rep = {}
    for f in [int(x) for x in argv[1:]]:
        apply(f); s.render.filepath = str(out/f'frame-{f:04d}.png'); bpy.ops.render.render(write_still=True)
        rep[f] = bounds()
    (out/'bounds.json').write_text(json.dumps(rep, indent=1)); print('TEST_DONE', json.dumps(rep))
elif argv and argv[0] == '--stills':
    for name, f in STATES.items():
        if len(argv) > 1 and name not in argv[1:]: continue
        apply(f, (1600, 1200)); s.render.filepath = str(ROOT/f'go2-{name}-v6.png'); bpy.ops.render.render(write_still=True)
    print('STILLS_DONE')
elif argv and argv[0] == '--sequence':
    frames = ROOT/'v6-frames'; frames.mkdir(exist_ok=True); rep = {}
    lo = int(argv[1]) if len(argv) > 1 else 300; hi = int(argv[2]) if len(argv) > 2 else 863
    for f in range(lo, hi+1):
        apply(f); s.render.filepath = str(frames/f'frame-{f:04d}.png'); bpy.ops.render.render(write_still=True)
        rep[f] = bounds()
    (ROOT/f'v6-bounds-{lo}-{hi}.json').write_text(json.dumps(rep, separators=(',', ':')))
    (ROOT/'v6-segments.json').write_text(json.dumps({'segments': SEGMENTS, 'states': STATES}, indent=1))
    print('SEQUENCE_DONE', lo, hi)
else:
    print('usage: --test f1 f2 ... | --stills | --sequence [lo hi]')
