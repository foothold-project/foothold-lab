import bpy,json,math
from pathlib import Path
from mathutils import Vector
from bpy_extras.object_utils import world_to_camera_view
ROOT=Path(__file__).resolve().parent
bpy.ops.wm.open_mainfile(filepath=str(ROOT/'go2-technical-v4.blend'))
s=bpy.context.scene;c=s.camera
segments=json.loads((ROOT/'v4-segments.json').read_text(encoding='utf-8'))
manifest=json.loads((ROOT/'geometry-manifest.json').read_text(encoding='utf-8'))
src=json.loads((ROOT/'joints-source.json').read_text(encoding='utf-8'))
limits={j['path'].split('/')[-1]:(float(j['attrs']['physics:lowerLimit']),float(j['attrs']['physics:upperLimit'])) for j in src if j['type']=='PhysicsRevoluteJoint'}
reports=[];bad_limits=[];bad_frames=[]
for seg in segments:
    if seg['camera']=='technical':loc=(2.7,1.4,.8);target=(.10,.145,.205);scale=.64
    elif seg['camera']=='commands':loc=(1.7,2.4,1.45);target=(0,0,.19);scale=1.42
    else:
        leg=seg['id'].upper();loc=(1.7 if leg.startswith('F') else -1.7,2.4 if leg.endswith('L') else -2.4,.92);target=(0,0,.22);scale=1.03
    c.location=loc;c.rotation_euler=(Vector(target)-c.location).to_track_quat('-Z','Y').to_euler();c.data.ortho_scale=scale
    s.render.resolution_x=960;s.render.resolution_y=720
    ranges=[]
    for f in range(seg['start'],seg['end']+1):
        s.frame_set(f)
        visible=[bpy.data.objects[r['object']] for r in manifest['geometry'] if seg['camera']!='technical' or r['object'].startswith('FL_')]
        pts=[world_to_camera_view(s,c,o.matrix_world@Vector(v)) for o in visible for v in o.bound_box]
        bound=[min(v.x for v in pts),max(v.x for v in pts),min(v.y for v in pts),max(v.y for v in pts)]
        if not (0<=bound[0]<bound[1]<=1 and 0<=bound[2]<bound[3]<=1):bad_frames.append({'segment':seg['id'],'frame':f,'bounds':bound})
        for j in manifest['joints']:
            q=bpy.data.objects[j['child']].rotation_quaternion;axis=Vector(j['axis_parent']);angle=2*math.atan2(Vector((q.x,q.y,q.z)).dot(axis),q.w);deg=math.degrees(angle)
            lo,hi=limits[j['name']]
            if not lo-0.001<=deg<=hi+0.001:bad_limits.append({'frame':f,'joint':j['name'],'angle_deg':deg,'limits':[lo,hi]})
        ranges.append(bound)
    reports.append({'segment':seg['id'],'frames':len(ranges),'bounds':[min(r[0] for r in ranges),max(r[1] for r in ranges),min(r[2] for r in ranges),max(r[3] for r in ranges)]})
result={'saved_scene_reopened':True,'all_432_frames_inside':not bad_frames,'all_joint_angles_inside_USD_limits':not bad_limits,'bounds':reports,'bad_frames':bad_frames,'bad_limits':bad_limits,'geometry_preserved':all(len(bpy.data.objects[r['object']].data.vertices)==r['vertices'] and len(bpy.data.objects[r['object']].data.polygons)==r['faces'] for r in manifest['geometry'])}
(ROOT/'v4-scene-audit.json').write_text(json.dumps(result,indent=2));print(json.dumps({k:v for k,v in result.items() if k not in ['bounds','bad_frames','bad_limits']}))
