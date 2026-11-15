"""USD-faithful articulated technical illustrations. These are not policy rollouts."""
import bpy,json,math
from pathlib import Path
from mathutils import Vector,Quaternion
from bpy_extras.object_utils import world_to_camera_view
from pxr import Usd,UsdGeom
ROOT=Path(__file__).resolve().parent if '__file__' in globals() else Path('C:/Users/AI-WS01/Desktop/jay/인공지능사관학교/foothold-lab/inbox/jay/20260929-mvp-presentation/assets/go2-blender')
if not (ROOT/'go2-presentation-v3.blend').exists():ROOT=Path('C:/Users/AI-WS01/Desktop/jay/인공지능사관학교/foothold-lab/inbox/jay/20260929-mvp-presentation/assets/go2-blender')
bpy.ops.wm.open_mainfile(filepath=str(ROOT/'go2-presentation-v3.blend'))
s=bpy.context.scene;s.name='GO2_U205_technical';s.frame_set(1)
for o in list(bpy.data.objects):
    o.animation_data_clear()
    if o.type=='CAMERA':o.data.animation_data_clear()
    if o.name.startswith('JOINT_MARKER'):bpy.data.objects.remove(o,do_unlink=True)
s.timeline_markers.clear()
rig=bpy.data.objects['GO2_ROOT'];rig.rotation_euler=(0,0,0)
base_location=rig.location.copy();s.render.resolution_percentage=100;s.render.film_transparent=True
s.render.resolution_x=1600;s.render.resolution_y=1600;s.render.image_settings.file_format='PNG';s.render.image_settings.color_mode='RGBA'
s.render.engine='BLENDER_EEVEE_NEXT';s.view_settings.exposure=-.45
cam=s.camera
def camera(loc,target,scale,res):
    cam.location=loc;cam.rotation_euler=(Vector(target)-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=scale
    s.render.resolution_x,s.render.resolution_y=res
def material(name,color):
    m=bpy.data.materials.new(name);m.use_nodes=True;m.diffuse_color=(*color,1)
    b=m.node_tree.nodes.get('Principled BSDF');b.inputs['Base Color'].default_value=(*color,1);b.inputs['Roughness'].default_value=.5
    b.inputs['Emission Color'].default_value=(*color,1);b.inputs['Emission Strength'].default_value=.4
    return m
teal=material('TEACH_axis_teal',(.015,.42,.31));amber=material('TEACH_selected_joint',(.86,.39,.035))
line_mat=material('TEACH_body_axis',(.015,.42,.31))
def curve_obj(name,points,mat,radius=.0018,cyclic=False,parent=None):
    cu=bpy.data.curves.new(name,'CURVE');cu.dimensions='3D';cu.bevel_depth=radius;cu.bevel_resolution=2
    sp=cu.splines.new('POLY');sp.points.add(len(points)-1)
    for p,xyz in zip(sp.points,points):p.co=(*xyz,1)
    sp.use_cyclic_u=cyclic;o=bpy.data.objects.new(name,cu);s.collection.objects.link(o);cu.materials.append(mat);o.parent=parent;return o
manifest=json.loads((ROOT/'geometry-manifest.json').read_text());joints={j['name']:j for j in manifest['joints']}
def pose(name,offset):
    j=joints[name];bpy.data.objects[j['child']].rotation_quaternion=Quaternion(Vector(j['axis_parent']),j['initial_radians']+offset)
def reset_pose():
    for name in joints:pose(name,0)
    rig.location=base_location;rig.rotation_euler=(0,0,0)
reset_pose()
axis_objects=[]
for name,j in joints.items():
    parent=bpy.data.objects[j['child']];axis=Vector(j['axis_parent']).normalized();u=axis.cross(Vector((0,0,1)))
    if u.length<.1:u=axis.cross(Vector((0,1,0)))
    u.normalize();v=axis.cross(u).normalized();r=.037 if '_calf_' in name else .045
    # A ring locates the pivot; a line indicates the physical rotation axis.
    pts=[tuple(r*(math.cos(a)*u+math.sin(a)*v)) for a in [i*2*math.pi/64 for i in range(64)]]
    ring=curve_obj('AXIS_RING_'+name,pts,teal,.0022,True,parent)
    line=curve_obj('AXIS_LINE_'+name,[tuple(-axis*.062),tuple(axis*.062)],teal,.0025,False,parent)
    axis_objects.extend([ring,line])
def axes_visible(legs=()):
    for o in axis_objects:o.hide_render=not any(o.name.startswith('AXIS_RING_'+leg) or o.name.startswith('AXIS_LINE_'+leg) for leg in legs)
axes_visible()
camera((3,0,.43),(0,0,.215),.535,(1600,1600))
s.frame_start=1;s.frame_end=1;s.frame_set(1)
s.render.filepath=str(ROOT/'go2-front-v4.png');bpy.ops.render.render(write_still=True)
# Camera callout is an illustrative surface anchor, not a calibrated USD Camera prim.
stage=Usd.Stage.Open(str(ROOT/'go2.usd'));xc=UsdGeom.XformCache()
radar=stage.GetPrimAtPath('/go2_description/base/radar');imu=stage.GetPrimAtPath('/go2_description/base/imu')
sensor_base={
 'front_camera':{'point':[.329,0,.040],'label':'전면 카메라','basis':'USD visual surface anchor; not an authored Camera prim','calibrated':False},
 'front_lidar':{'point':list(xc.GetLocalToWorldTransform(radar).ExtractTranslation()),'label':'전면 LiDAR','basis':'USD /go2_description/base/radar transform','calibrated':False,'usd_authored_transform':True},
 'imu':{'point':list(xc.GetLocalToWorldTransform(imu).ExtractTranslation()),'label':'IMU','basis':'USD /go2_description/base/imu transform; inside body, not visible exterior hardware','calibrated':False,'usd_authored_transform':True}}
def xy(world):
    q=world_to_camera_view(s,cam,world);return {'x':q.x,'y':1-q.y,'depth':q.z}
bpy.context.view_layer.update()
sensors={k:{**row,'screen':xy(bpy.data.objects['base'].matrix_world@Vector(row['point']))} for k,row in sensor_base.items()}
projection={'front':{'resolution':[1600,1600],'sensors':sensors}}
camera((1.7,2.4,.92),(0,.055,.235),1.03,(1280,960));axes_visible(('FL',))
s.render.filepath=str(ROOT/'go2-three-axes-v4.png');bpy.ops.render.render(write_still=True)
bpy.context.view_layer.update()
projection['three_axes']={'resolution':[1280,960],'joints':{name:{**xy(bpy.data.objects[j['child']].matrix_world.translation),'axis_parent':j['axis_parent']} for name,j in joints.items() if name.startswith('FL')}}
# One shared timeline: isolated rotations, four-leg response, commanded direction.
segments=[]
for i,(name,label,amplitude) in enumerate([('FL_hip_joint','외전·내전',.26),('FL_thigh_joint','고관절 굽힘·폄',.32),('FL_calf_joint','무릎 굽힘·폄',.36)]):
    start=1+i*48;end=start+47
    for f,off in [(start,0),(start+12,amplitude),(start+35,-amplitude),(end,0)]:
        pose(name,off);bpy.data.objects[joints[name]['child']].keyframe_insert('rotation_quaternion',frame=f)
    segments.append({'id':['hip','thigh','calf'][i],'label':label,'start':start,'end':end,'camera':'technical','axes':['FL'],'kind':'single-joint kinematic rotation'})
    s.timeline_markers.new(name,frame=start)
for name in joints:
    pose(name,0)
    bpy.data.objects[joints[name]['child']].keyframe_insert('rotation_quaternion',frame=144)
for i,leg in enumerate(['FL','FR','RL','RR']):
    start=145+i*36;end=start+35
    for part,amplitude in [('hip',.16),('thigh',-.25),('calf',.38)]:
        name=leg+'_'+part+'_joint'
        for f,off in [(start,0),(start+17,amplitude),(end,0)]:pose(name,off);bpy.data.objects[joints[name]['child']].keyframe_insert('rotation_quaternion',frame=f)
    segments.append({'id':leg.lower(),'label':leg+' 다리의 3관절','start':start,'end':end,'camera':'fourlegs','axes':[leg],'kind':'leg-joint demonstration, not walking'})
# Keep frame 289 onward in neutral stance. Translation is a command-direction illustration.
for name in joints:pose(name,0);bpy.data.objects[joints[name]['child']].keyframe_insert('rotation_quaternion',frame=289)
body_axes=[]
for axis,label in [(Vector((1,0,0)),'x'),(Vector((0,1,0)),'y')]:
    end=axis*.56;start=-axis*.48;z=.025
    points=[tuple(start+Vector((0,0,z))),tuple(end+Vector((0,0,z)))]
    body_axes.append(curve_obj('BODY_AXIS_'+label,points,line_mat,.003))
    across=Vector((-axis.y,axis.x,0))
    body_axes.append(curve_obj('BODY_ARROW_'+label,[tuple(end-axis*.055+across*.028+Vector((0,0,z))),tuple(end+Vector((0,0,z))),tuple(end-axis*.055-across*.028+Vector((0,0,z)))],line_mat,.003))
arc=[(.46*math.cos(a),.46*math.sin(a),.03) for a in [math.radians(t) for t in range(-35,216,3)]]
body_axes.append(curve_obj('BODY_YAW_ARC',arc,line_mat,.003))
for o in body_axes:o.hide_render=True
for i,(id,label,axis,amp) in enumerate([('forward','전후 명령',0,.16),('lateral','횡이동 명령',1,.16),('yaw','회전 명령',2,.38)]):
    start=289+i*48;end=start+47
    for f,mult in [(start,0),(start+12,1),(start+35,-1),(end,0)]:
        rig.location=base_location;rig.rotation_euler=(0,0,0)
        if id=='yaw':rig.rotation_euler.z=amp*mult
        else:rig.location[axis]+=amp*mult
        rig.keyframe_insert('location',frame=f);rig.keyframe_insert('rotation_euler',frame=f)
    segments.append({'id':id,'label':label,'start':start,'end':end,'camera':'commands','axes':[],'kind':'command direction only, not locomotion'})
s.frame_start=1;s.frame_end=432;s.render.fps=24
reset_pose();axes_visible(('FL',));camera((1.7,2.4,.92),(0,.055,.235),1.03,(1280,960));s.frame_set(1)
(ROOT/'v4-sensor-and-joint-anchors.json').write_text(json.dumps(projection,ensure_ascii=False,indent=2),encoding='utf-8')
(ROOT/'v4-segments.json').write_text(json.dumps(segments,ensure_ascii=False,indent=2),encoding='utf-8')
bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'go2-technical-v4.blend'),compress=True)
result={'scene':'go2-technical-v4.blend','front':'go2-front-v4.png','three_axes':'go2-three-axes-v4.png','segments':len(segments),'frame_range':[1,432],'sensor_anchors':sensors}
