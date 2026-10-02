import bpy
from pathlib import Path
ROOT=Path('C:/Users/AI-WS01/Desktop/jay/인공지능사관학교/foothold-lab/inbox/jay/20260929-mvp-presentation/assets/go2-blender')
bpy.ops.wm.open_mainfile(filepath=str(ROOT/'go2-presentation-v3.blend'))
s=bpy.context.scene;s.render.resolution_x=640;s.render.resolution_y=480;s.render.resolution_percentage=100
(ROOT/'frames').mkdir(exist_ok=True)
s.render.filepath=str(ROOT/'frames/frame-');s.frame_start=1;s.frame_end=264;s.frame_step=1
bpy.ops.render.render(animation=True)
