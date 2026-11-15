import bpy,json
from pxr import Sdf,Usd,UsdGeom
from pathlib import Path
root=Path('C:/Users/AI-WS01/Desktop/jay/인공지능사관학교/foothold-lab/inbox/jay/20260929-mvp-presentation/assets/go2-blender')
l=Sdf.Layer.FindOrOpen(str(root/'Props/instanceable_meshes.usd'))
# Keep binary source; a text dump is over 100 MB and is not needed for delivery.
stage=Usd.Stage.Open(str(root/'go2.usd'))
joints=[]
for p in stage.Traverse():
    if 'Joint' in p.GetTypeName():
        joints.append({'path':str(p.GetPath()),'type':p.GetTypeName(),'attrs':{a.GetName():str(a.Get()) for a in p.GetAttributes()},'rels':{r.GetName():[str(x) for x in r.GetTargets()] for r in p.GetRelationships()}})
(root/'joints-source.json').write_text(json.dumps(joints,indent=2),encoding='utf-8')
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
bpy.ops.wm.usd_import(filepath=str(root/'go2.usd'),import_usd_preview=True,support_scene_instancing=False)
(root/'import-objects.json').write_text(json.dumps([{'name':o.name,'type':o.type,'parent':o.parent.name if o.parent else None,'loc':list(o.location),'dim':list(o.dimensions)} for o in bpy.data.objects],indent=2),encoding='utf-8')
bpy.ops.wm.save_as_mainfile(filepath=str(root/'go2-imported-source.blend'))
result={'refs':l.GetExternalReferences(),'joint_count':len(joints),'objects':len(bpy.data.objects),'meshes':sum(o.type=='MESH' for o in bpy.data.objects)}
