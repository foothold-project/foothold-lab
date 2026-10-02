import bpy,json,math,sys
from pathlib import Path
from mathutils import Vector
from bpy_extras.object_utils import world_to_camera_view
ROOT=Path(__file__).resolve().parent
bpy.ops.wm.open_mainfile(filepath=str(ROOT/'go2-technical-v4.blend'))
s=bpy.context.scene;cam=s.camera
if 'TEACH_selected_joint' not in bpy.data.materials:
    m=bpy.data.materials['TEACH_axis_teal'].copy();m.name='TEACH_selected_joint'
    b=m.node_tree.nodes.get('Principled BSDF')
    b.inputs['Base Color'].default_value=(.86,.39,.035,1);b.inputs['Emission Color'].default_value=(.86,.39,.035,1)
segments=json.loads((ROOT/'v4-segments.json').read_text())
manifest=json.loads((ROOT/'geometry-manifest.json').read_text());joints={j['name']:j for j in manifest['joints']}
renderdir=ROOT/'v4-frames';renderdir.mkdir(exist_ok=True)
def camera(loc,target,scale,res):
    cam.location=loc;cam.rotation_euler=(Vector(target)-cam.location).to_track_quat('-Z','Y').to_euler();cam.data.ortho_scale=scale
    s.render.resolution_x,s.render.resolution_y=res
def config(seg,res=(960,720)):
    single=seg['camera']=='technical';commands=seg['camera']=='commands'
    for row in manifest['geometry']:
        o=bpy.data.objects[row['object']];o.hide_render=single and not o.name.startswith('FL_')
    for o in bpy.data.objects:
        if o.name.startswith('AXIS_'):
            o.hide_render=not any(o.name.startswith('AXIS_RING_'+leg) or o.name.startswith('AXIS_LINE_'+leg) for leg in seg['axes'])
            active=single and ('_'+seg['id']+'_joint') in o.name
            o.data.materials[0]=bpy.data.materials['TEACH_selected_joint' if active else 'TEACH_axis_teal']
        if o.name.startswith('BODY_'):o.hide_render=not commands or (seg['id']=='forward' and not o.name.endswith('_x')) or (seg['id']=='lateral' and not o.name.endswith('_y')) or (seg['id']=='yaw' and o.name!='BODY_YAW_ARC')
    if single:camera((2.7,1.4,.8),(.10,.145,.205),.64,res)
    elif commands:camera((1.7,2.4,1.45),(0,0,.19),1.42,res)
    else:
        # Opposite-side legs need their own meaningful view, not hidden pivots.
        leg=seg['id'].upper();loc=(1.7 if leg.startswith('F') else -1.7,2.4 if leg.endswith('L') else -2.4,.92)
        camera(loc,(0,0,.22),1.03,res)
# Canonical static assets.
config(segments[0],(1280,960));s.frame_set(1);s.render.filepath=str(ROOT/'go2-fl-leg-v4.png');bpy.ops.render.render(write_still=True)
bpy.context.view_layer.update()
anchors=json.loads((ROOT/'v4-sensor-and-joint-anchors.json').read_text())
anchors['single_leg']={'resolution':[1280,960],'joints':{}}
for name,j in joints.items():
    if name.startswith('FL'):
        q=world_to_camera_view(s,cam,bpy.data.objects[j['child']].matrix_world.translation)
        anchors['single_leg']['joints'][name]={'x':q.x,'y':1-q.y,'depth':q.z,'axis_parent':j['axis_parent']}
config({'camera':'fourlegs','id':'fl','axes':['FL','FR','RL','RR']},(1280,960));s.frame_set(144)
s.render.filepath=str(ROOT/'go2-twelve-axes-v4.png');bpy.ops.render.render(write_still=True)
for seg in segments:
    if '--single-only' in sys.argv and seg['camera']!='technical':continue
    config(seg);s.frame_start=seg['start'];s.frame_end=seg['end'];s.render.filepath=str(renderdir/(seg['id']+'-'))
    bpy.ops.render.render(animation=True)
    s.frame_set((seg['start']+seg['end'])//2);s.render.resolution_x=1280;s.render.resolution_y=960
    s.render.filepath=str(ROOT/('go2-'+seg['id']+'-v4.png'));bpy.ops.render.render(write_still=True)
(ROOT/'v4-sensor-and-joint-anchors.json').write_text(json.dumps(anchors,ensure_ascii=False,indent=2),encoding='utf-8')
