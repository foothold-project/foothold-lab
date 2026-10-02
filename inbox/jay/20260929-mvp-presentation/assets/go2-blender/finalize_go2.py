import bpy,json,math
from pathlib import Path
from mathutils import Vector
from pxr import Usd,UsdGeom
from bpy_extras.object_utils import world_to_camera_view
ROOT=Path('C:/Users/AI-WS01/Desktop/jay/인공지능사관학교/foothold-lab/inbox/jay/20260929-mvp-presentation/assets/go2-blender')
bpy.ops.wm.open_mainfile(filepath=str(ROOT/'go2-presentation-v2.blend'))
s=bpy.context.scene;stage=Usd.Stage.Open(str(ROOT/'go2.usd'));cache=UsdGeom.XformCache();fixed=[]
manifest=json.loads((ROOT/'geometry-manifest.json').read_text())
for row in manifest['geometry']:
    p=stage.GetPrimAtPath(row['source']);u=UsdGeom.Mesh(p);o=bpy.data.objects[row['object']];ns=u.GetNormalsAttr().Get()
    if ns:
        mat=cache.GetLocalToWorldTransform(p)
        normals=[tuple(mat.TransformDir(n).GetNormalized()) for n in ns]
        if len(normals)==len(o.data.vertices):o.data.normals_split_custom_set_from_vertices(normals);fixed.append(o.name)
        elif len(normals)==len(o.data.loops):o.data.normals_split_custom_set(normals);fixed.append(o.name)
s.frame_set(1)
bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'go2-presentation-v3.blend'))
for name,f in [('front',1),('three-quarter',96),('exploded',156),('joints',240)]:
    s.frame_set(f);s.render.filepath=str(ROOT/('go2-'+name+'-v3.png'));bpy.ops.render.render(write_still=True)
# Check recovered assembled matrices against the pre-explosion pose.
s.frame_set(120);before={o.name:o.matrix_world.copy() for o in s.objects if o.type=='MESH' and not o.name.startswith('JOINT_MARKER')}
s.frame_set(216);delta=max(abs(before[n][r][c]-bpy.data.objects[n].matrix_world[r][c]) for n in before for r in range(4) for c in range(4))
track={}
for f in [1,96,156,216,240]:
    s.frame_set(f);track[str(f)]={}
    for j in manifest['joints']:
        o=bpy.data.objects[j['child']];v=world_to_camera_view(s,s.camera,o.matrix_world.translation)
        track[str(f)][j['name']]={'x':v.x,'y':1-v.y,'depth':v.z}
(ROOT/'joint-screen-positions.json').write_text(json.dumps(track,indent=2))
(ROOT/'verification.json').write_text(json.dumps({'source_meshes':len(manifest['geometry']),'revolute_joints':len(manifest['joints']),'source_normals_restored':fixed,'assembly_max_transform_error':delta,'preview_resolution':[960,720],'frame_range':[1,264],'fps':24,'notes':'Kinematic explanatory animation, not policy rollout. Geometry originates in IsaacLab Go2 USD. No external Orin/D435i/HESAI module added.'},indent=2))
s.frame_set(1)
result={'saved':'go2-presentation-v3.blend','normals':len(fixed),'assembly_max_transform_error':delta}
