import bpy,json
from pathlib import Path
from mathutils import Vector
from bpy_extras.object_utils import world_to_camera_view
ROOT=Path('C:/Users/AI-WS01/Desktop/jay/인공지능사관학교/foothold-lab/inbox/jay/20260929-mvp-presentation/assets/go2-blender')
bpy.ops.wm.open_mainfile(filepath=str(ROOT/'go2-presentation-v3.blend'))
s=bpy.context.scene;manifest=json.loads((ROOT/'geometry-manifest.json').read_text())
geometry_checks=[{'object':r['object'],'vertices_match':len(bpy.data.objects[r['object']].data.vertices)==r['vertices'],'faces_match':len(bpy.data.objects[r['object']].data.polygons)==r['faces']} for r in manifest['geometry']]
framing=[]
for f in range(1,265,3):
    s.frame_set(f)
    pts=[world_to_camera_view(s,s.camera,o.matrix_world@Vector(v)) for o in s.objects if o.type=='MESH' for v in o.bound_box]
    framing.append({'frame':f,'x':[min(p.x for p in pts),max(p.x for p in pts)],'y':[min(p.y for p in pts),max(p.y for p in pts)]})
v={'file_reopened':bpy.data.filepath,'geometry_checks':geometry_checks,'camera':s.camera.name,'frame_range':[s.frame_start,s.frame_end],'fps':s.render.fps,'framing':framing,'all_bounds_inside':all(0<=p['x'][0]<p['x'][1]<=1 and 0<=p['y'][0]<p['y'][1]<=1 for p in framing)}
(ROOT/'reopen-audit.json').write_text(json.dumps(v,indent=2))
result={'geometry_17_match':all(r['vertices_match'] and r['faces_match'] for r in geometry_checks),'all_bounds_inside':v['all_bounds_inside'],'camera':s.camera.name,'frame_range':v['frame_range']}
