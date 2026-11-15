import bpy
from pathlib import Path
from mathutils import Vector
ROOT=Path(__file__).resolve().parent
bpy.ops.wm.open_mainfile(filepath=str(ROOT/'go2-technical-v4.blend'))
s=bpy.context.scene;s.frame_set(1)
for o in bpy.data.objects:
    if o.type=='MESH':o.hide_render=not o.name.startswith('FL_')
    if o.name.startswith('AXIS_'):o.hide_render='FL_' not in o.name
    if o.name.startswith('BODY_'):o.hide_render=True
c=s.camera;c.location=(3,.8,.7);c.rotation_euler=(Vector((.11,.145,.205))-c.location).to_track_quat('-Z','Y').to_euler();c.data.ortho_scale=.64
s.render.resolution_x=1280;s.render.resolution_y=960;s.render.filepath=str(ROOT/'go2-fl-leg-angle-v4.png');bpy.ops.render.render(write_still=True)
