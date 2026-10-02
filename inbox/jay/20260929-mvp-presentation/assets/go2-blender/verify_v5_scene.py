import bpy,json
from pathlib import Path
from mathutils import Vector
from bpy_extras.object_utils import world_to_camera_view
ROOT=Path(__file__).resolve().parent
bpy.ops.wm.open_mainfile(filepath=str(ROOT/'go2-continuous-v5.blend'))
s=bpy.context.scene;expected=json.loads((ROOT/'v5-static-anchors.json').read_text());source=json.loads((ROOT/'geometry-manifest.json').read_text())
checks=[]
for name,row in expected.items():
    s.frame_set(row['frame']);bpy.context.view_layer.update()
    errors=[]
    for j in source['joints']:
        q=world_to_camera_view(s,s.camera,bpy.data.objects[j['child']].matrix_world.translation)
        errors.extend([abs(q.x-row['joints'][j['name']][0]),abs((1-q.y)-row['joints'][j['name']][1])])
    checks.append({'state':name,'frame':row['frame'],'max_anchor_error':max(errors),'passes':max(errors)<.0001})
assert all(c['passes'] for c in checks),checks
(ROOT/'v5-reopen-audit.json').write_text(json.dumps({'editable_scene_keyframes_match_rendered_states':True,'checks':checks},indent=2),encoding='utf-8')
sensor_source=json.loads((ROOT/'v4-sensor-and-joint-anchors.json').read_text())['front']['sensors']
records=json.loads((ROOT/'v5-frame-anchors.json').read_text())
for row in records:
    s.frame_set(row['frame']);bpy.context.view_layer.update();row['sensors']={}
    for name,src in sensor_source.items():
        q=world_to_camera_view(s,s.camera,bpy.data.objects['base'].matrix_world@Vector(src['point']))
        row['sensors'][name]={'screen':[round(q.x,6),round(1-q.y,6),round(q.z,6)],'basis':src['basis'],'calibrated':False}
for row in expected.values():row['sensors']=records[row['frame']-1]['sensors']
(ROOT/'v5-static-anchors.json').write_text(json.dumps(expected,indent=2),encoding='utf-8')
(ROOT/'v5-frame-anchors.json').write_text(json.dumps(records,separators=(',',':')),encoding='utf-8')
