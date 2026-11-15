import bpy,json,math
from pathlib import Path
from mathutils import Vector
ROOT=Path('C:/Users/AI-WS01/Desktop/jay/인공지능사관학교/foothold-lab/inbox/jay/20260929-mvp-presentation/assets/go2-blender')
bpy.ops.wm.open_mainfile(filepath=str(ROOT/'go2-presentation-v1.blend'))
s=bpy.context.scene;c=s.camera;c.location=(2.4,0,.82);c.rotation_euler=(Vector((0,0,.26))-c.location).to_track_quat('-Z','Y').to_euler()
s.view_settings.exposure=-.75
for f,v in [(1,1.3),(96,1.3),(120,1.3),(156,1.8),(180,1.8),(216,1.3),(264,1.3)]:c.data.ortho_scale=v;c.data.keyframe_insert('ortho_scale',frame=f)
for o in bpy.data.objects:
    if o.name.startswith('JOINT_MARKER_'):
        for f,scale in [(1,.001),(216,.001),(240,1.5),(264,1.5)]:o.scale=(scale,)*3;o.keyframe_insert('scale',frame=f)
s.frame_set(1);s.render.resolution_x=960;s.render.resolution_y=720
bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'go2-presentation-v2.blend'))
for name,f in [('front',1),('three-quarter',96),('exploded',156),('joints',240)]:
    s.frame_set(f);s.render.filepath=str(ROOT/('go2-'+name+'-v2.png'));bpy.ops.render.render(write_still=True)
result={'saved':'go2-presentation-v2.blend'}
