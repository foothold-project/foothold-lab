"""Local USD-faithful v5 assembly and height-grid explanation. No policy simulation."""
import bpy, json, math, sys
from pathlib import Path
from mathutils import Vector, Quaternion
from bpy_extras.object_utils import world_to_camera_view

ROOT = Path(__file__).resolve().parent
bpy.ops.wm.open_mainfile(filepath=str(ROOT / 'go2-technical-v4.blend'))
s = bpy.context.scene
s.frame_set(1)
for o in list(bpy.data.objects):
    o.animation_data_clear()
    if o.type == 'CAMERA': o.data.animation_data_clear()
    if o.name.startswith(('AXIS_', 'BODY_', 'JOINT_MARKER')):
        bpy.data.objects.remove(o, do_unlink=True)
s.timeline_markers.clear()
s.name = 'GO2_U206_continuous_v5'
rig = bpy.data.objects['GO2_ROOT']
rig.rotation_euler = (0, 0, 0)
cam = s.camera
source = json.loads((ROOT/'geometry-manifest.json').read_text())
sensor_source=json.loads((ROOT/'v4-sensor-and-joint-anchors.json').read_text())['front']['sensors']
meshes = [bpy.data.objects[row['object']] for row in source['geometry']]
for o in meshes: o.hide_render = False
joints = source['joints']
for j in joints:
    bpy.data.objects[j['child']].rotation_quaternion = Quaternion(Vector(j['axis_parent']), j['initial_radians'])
hips = {leg: bpy.data.objects[leg+'_hip'] for leg in ['FL','FR','RL','RR']}
hip_locations = {leg:o.location.copy() for leg,o in hips.items()}
s.render.engine = 'BLENDER_EEVEE_NEXT'
s.render.film_transparent = True
s.render.image_settings.file_format='PNG'
s.render.image_settings.color_mode='RGBA'
s.render.resolution_percentage=100
s.render.fps=24
s.view_settings.view_transform='AgX'
s.view_settings.look='AgX - Medium Low Contrast'
s.view_settings.exposure=-.45
cam.data.type='ORTHO'

def mat(name,color,emission=.12):
    m=bpy.data.materials.new(name);m.diffuse_color=(*color,1);m.use_nodes=True
    bs=m.node_tree.nodes.get('Principled BSDF')
    bs.inputs['Base Color'].default_value=(*color,1)
    bs.inputs['Roughness'].default_value=.8
    bs.inputs['Emission Color'].default_value=(*color,1)
    bs.inputs['Emission Strength'].default_value=emission
    return m

gridmat=mat('V5_grid_teal',(.025,.35,.27),.3)
linemat=mat('V5_grid_lines',(.055,.22,.18),.15)
brightmat=mat('V5_active_samples',(.11,.57,.40),.4)
connectmat=mat('V5_attachment_guide',(.17,.30,.27),.15)

def line(name,points,material,radius=.001,cyclic=False):
    cu=bpy.data.curves.new(name,'CURVE');cu.dimensions='3D';cu.bevel_depth=radius;cu.bevel_resolution=1
    sp=cu.splines.new('POLY');sp.points.add(len(points)-1)
    for p,xyz in zip(sp.points,points):p.co=(*xyz,1)
    sp.use_cyclic_u=cyclic
    o=bpy.data.objects.new(name,cu);s.collection.objects.link(o);cu.materials.append(material)
    return o

guides={leg:line('V5_attachment_'+leg,[(0,0,0),(0,0,0)],connectmat,.0016) for leg in hips}
grid_objects=[];grid_points=[];point_objects=[]

def height(x,y):
    # Explicit teaching terrain, flat beneath feet; raised ground in front, lower rear.
    if x > .40: return .065 + .012*math.sin(y*7)
    if x < -.50: return -.035 + .006*math.sin(y*6)
    return 0.0

xs=[round(-.8+i*.1,4) for i in range(17)]
ys=[round(-.5+i*.1,4) for i in range(11)]
for i,x in enumerate(xs):
    for j,y in enumerate(ys):
        p=(x,y,height(x,y)+.003)
        grid_points.append(p)
        bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=1,radius=.0065,location=p)
        o=bpy.context.object;o.name=f'V5_height_{i:02d}_{j:02d}';o.data.materials.append(gridmat)
        point_objects.append(o);grid_objects.append(o)
for i,x in enumerate(xs):
    grid_objects.append(line('V5_grid_x_'+str(i),[(x,y,height(x,y)+.002) for y in ys],linemat,.0007))
for j,y in enumerate(ys):
    grid_objects.append(line('V5_grid_y_'+str(j),[(x,y,height(x,y)+.002) for x in xs],linemat,.0007))
# Four short selected rays are illustrative and omit the virtual 20m sensor origin.
ray_objects=[]
for x,y in [(-.6,-.4),(-.2,-.4),(.2,-.4),(.6,-.4)]:
    o=line('V5_sample_ray_'+str(x),[(x,y,height(x,y)+.003),(x,y,.22)],linemat,.00075)
    ray_objects.append(o)

def ease(t): return .5-.5*math.cos(math.pi*max(0,min(1,t)))
def mix(a,b,t): return a+(b-a)*t

def apply(frame,res=(960,720)):
    s.frame_set(frame)
    for leg,o in hips.items():o.location=hip_locations[leg]
    angle=0.;scale=.76;z=.53;targetz=.22;spread=0.;grid=False
    if frame <= 97:
        t=ease((frame-1)/96);angle=math.radians(405)*t
        scale=mix(.76,1.13,min(1,(frame-1)/16));z=mix(.53,1.02,t)
    elif frame <= 145:
        t=ease((frame-97)/48);angle=math.radians(45);scale=mix(1.13,1.65,t);z=mix(1.02,2.4,t);spread=t
    elif frame <= 193:
        t=ease((frame-145)/48);angle=math.radians(45);scale=mix(1.65,1.13,t);z=mix(2.4,1.02,t);spread=1-t
    elif frame <= 241:
        t=ease((frame-193)/48);angle=math.radians(mix(45,90,t));scale=mix(1.13,1.93,t);z=mix(1.02,1.80,t);targetz=mix(.22,.12,t)
        grid=frame>=226
    else:
        angle=math.radians(90);scale=1.93;z=1.8;targetz=.12;grid=True
    for leg,o in hips.items():
        offset=Vector((.20 if leg[0]=='F' else -.20,.30 if leg[1]=='L' else -.30,0))*spread
        o.location=hip_locations[leg]+offset
        guide=guides[leg];guide.hide_render=spread<.01
        p0=o.parent.matrix_world@hip_locations[leg];p1=o.parent.matrix_world@o.location
        guide.data.splines[0].points[0].co=(*p0,1);guide.data.splines[0].points[1].co=(*p1,1)
    cam.location=(3*math.cos(angle),3*math.sin(angle),z)
    cam.rotation_euler=(Vector((0,0,targetz))-cam.location).to_track_quat('-Z','Y').to_euler()
    cam.data.ortho_scale=scale
    for o in grid_objects:o.hide_render=not grid
    reveal=ease((frame-225)/16)
    selected=int((frame-242)/3)%17 if frame>241 else -1
    for idx,o in enumerate(point_objects):
        k=idx//11;size=reveal*(1.65 if k==selected else 1)
        o.scale=(size,size,size)
        o.data.materials[0]=gridmat
    for o in grid_objects:
        if o.type=='CURVE':o.data.bevel_factor_end=reveal
    for o in ray_objects:o.hide_render=not grid or frame<=241
    s.render.resolution_x,s.render.resolution_y=res
    bpy.context.view_layer.update()

def project(p):
    q=world_to_camera_view(s,cam,p)
    return [round(q.x,6),round(1-q.y,6),round(q.z,6)]

def audit(frame):
    corners=[project(o.matrix_world@Vector(v)) for o in meshes for v in o.bound_box]
    bounds=[min(p[0] for p in corners),min(p[1] for p in corners),max(p[0] for p in corners),max(p[1] for p in corners)]
    return {'frame':frame,'robot_bounds':bounds,'joints':{j['name']:project(bpy.data.objects[j['child']].matrix_world.translation) for j in joints},'sensors':{name:{'screen':project(bpy.data.objects['base'].matrix_world@Vector(row['point'])),'basis':row['basis'],'calibrated':False} for name,row in sensor_source.items()},'grid':[project(Vector(p)) for p in grid_points] if frame>=226 else [],'camera_position':list(cam.location),'ortho_scale':cam.data.ortho_scale}

STATES={'front':1,'three_quarter':97,'four_legs':145,'assembled':193,'side_grid':241,'scan':265}
SEGMENTS=[{'id':'turntable','start':1,'end':97},{'id':'four_legs','start':97,'end':145},{'id':'assemble','start':145,'end':193},{'id':'to_side','start':193,'end':241},{'id':'scan','start':241,'end':289}]
s.frame_start=1;s.frame_end=289
for name,frame in STATES.items():s.timeline_markers.new(name,frame=frame)
if '--sequence' not in sys.argv:
    anchors={}
    for name,frame in STATES.items():
        apply(frame,(1600,1200));s.render.filepath=str(ROOT/('go2-'+name+'-v5.png'))
        bpy.ops.render.render(write_still=True);anchors[name]=audit(frame)
    (ROOT/'v5-static-anchors.json').write_text(json.dumps(anchors,indent=2),encoding='utf-8')
    # Bake editable transforms and visibility into the scene, not just poster snapshots.
    for f in range(1,290):
        apply(f,(1600,1200))
        cam.keyframe_insert('location',frame=f);cam.keyframe_insert('rotation_euler',frame=f)
        cam.data.keyframe_insert('ortho_scale',frame=f)
        for o in hips.values():o.keyframe_insert('location',frame=f)
        for o in list(guides.values())+grid_objects+ray_objects:
            o.keyframe_insert('hide_render',frame=f)
            if o in point_objects:o.keyframe_insert('scale',frame=f)
            if o.type=='CURVE' and o in grid_objects:o.data.keyframe_insert('bevel_factor_end',frame=f)
        for guide in guides.values():
            for p in guide.data.splines[0].points:p.keyframe_insert('co',frame=f)
    s.frame_set(1);bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'go2-continuous-v5.blend'),compress=True)
    (ROOT/'v5-segments.json').write_text(json.dumps(SEGMENTS,indent=2),encoding='utf-8')
else:
    frames=ROOT/'v5-frames';frames.mkdir(exist_ok=True);records=[]
    for f in range(1,290):
        apply(f);s.render.filepath=str(frames/f'frame-{f:04d}.png');bpy.ops.render.render(write_still=True)
        records.append(audit(f))
    geometry_ok=all(len(bpy.data.objects[row['object']].data.vertices)==row['vertices'] and len(bpy.data.objects[row['object']].data.polygons)==row['faces'] for row in source['geometry'])
    (ROOT/'v5-frame-anchors.json').write_text(json.dumps(records,separators=(',',':')),encoding='utf-8')
    pose_ok=all(bpy.data.objects[j['child']].rotation_quaternion.rotation_difference(Quaternion(Vector(j['axis_parent']),j['initial_radians'])).angle<1e-5 for j in joints)
    assembled_ok=all((o.location-hip_locations[leg]).length<1e-6 for leg,o in hips.items())
    (ROOT/'v5-audit.json').write_text(json.dumps({'original_mesh_counts_preserved':geometry_ok,'frames':len(records),'grid_points':len(grid_points),'robot_fits_all_frames':all(0<=r['robot_bounds'][0]<r['robot_bounds'][2]<=1 and 0<=r['robot_bounds'][1]<r['robot_bounds'][3]<=1 for r in records),'leg_internal_joint_rotations_unchanged':pose_ok,'reassembled_original_hip_locations':assembled_ok,'grid_data':'Geometric teaching terrain, not recorded Isaac observations','source':'go2-technical-v4.blend','states':STATES},indent=2),encoding='utf-8')
