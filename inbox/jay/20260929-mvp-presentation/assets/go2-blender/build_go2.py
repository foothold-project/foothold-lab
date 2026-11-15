"""Build presentation rig from original USD geometry and physics attachment transforms."""
import bpy, json, math
from pathlib import Path
from mathutils import Vector, Matrix, Quaternion
from pxr import Usd, UsdGeom, UsdShade
ROOT=Path('C:/Users/AI-WS01/Desktop/jay/인공지능사관학교/foothold-lab/inbox/jay/20260929-mvp-presentation/assets/go2-blender')
stage=Usd.Stage.Open(str(ROOT/'go2.usd'))
bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
scene=bpy.context.scene; scene.name='FOOTHOLD_Go2_spec';scene.unit_settings.system='METRIC'
def empty(name,loc=(0,0,0)):
    o=bpy.data.objects.new(name,None);scene.collection.objects.link(o);o.location=loc;return o
rig=empty('GO2_ROOT')
links={}
cache=UsdGeom.XformCache()
for p in stage.GetPrimAtPath('/go2_description').GetChildren():
    if 'PhysicsRigidBodyAPI' in p.GetAppliedSchemas():
        o=empty(p.GetName());o.parent=rig;o.location=tuple(cache.GetLocalToWorldTransform(p).ExtractTranslation());links[p.GetName()]=o
def mat_for(prim):
    bound=UsdShade.MaterialBindingAPI(prim).ComputeBoundMaterial()[0]
    name=str(bound.GetPath()) if bound else 'default'; key='USD_'+name.replace('/','_')
    if key in bpy.data.materials:return bpy.data.materials[key]
    m=bpy.data.materials.new(key);m.use_nodes=True
    c=(0.5,0.53,0.58)
    if bound:
        s=bound.GetPrim().GetChild('Shader');a=s.GetAttribute('inputs:diffuse_color_constant')
        if a and a.Get() is not None:c=tuple(a.Get())
    bs=m.node_tree.nodes.get('Principled BSDF');bs.inputs['Base Color'].default_value=(*c,1);bs.inputs['Roughness'].default_value=.48
    bs.inputs['Metallic'].default_value=.15 if sum(c)>.3 else 0
    m.diffuse_color=(*c,1);return m
geometry=[]
for p in Usd.PrimRange(stage.GetPseudoRoot(),Usd.TraverseInstanceProxies()):
    path=str(p.GetPath())
    if not p.IsA(UsdGeom.Mesh) or '/visuals/' not in path:continue
    linkname=path.split('/')[2]; link=links[linkname]
    usdm=UsdGeom.Mesh(p);pts=usdm.GetPointsAttr().Get();counts=usdm.GetFaceVertexCountsAttr().Get();ids=usdm.GetFaceVertexIndicesAttr().Get()
    world=cache.GetLocalToWorldTransform(p); origin=cache.GetLocalToWorldTransform(stage.GetPrimAtPath('/go2_description/'+linkname)).ExtractTranslation()
    verts=[tuple(world.Transform(x)-origin) for x in pts]; faces=[];i=0
    for n in counts:faces.append(tuple(ids[i:i+n]));i+=n
    mesh=bpy.data.meshes.new(linkname+'_source_mesh');mesh.from_pydata(verts,[],faces);mesh.update()
    obj=bpy.data.objects.new(linkname+'_visual',mesh);scene.collection.objects.link(obj);obj.parent=link;obj.data.materials.append(mat_for(p))
    for sub in UsdGeom.Subset.GetAllGeomSubsets(usdm):
        mat=mat_for(sub.GetPrim());obj.data.materials.append(mat);idx=len(obj.data.materials)-1
        for f in sub.GetIndicesAttr().Get():mesh.polygons[f].material_index=idx
    for poly in mesh.polygons:poly.use_smooth=True
    geometry.append({'source':path,'object':obj.name,'vertices':len(verts),'faces':len(faces)})
# Recreate physics links with actual local joint frames. Keep source meshes unchanged.
joints=json.loads((ROOT/'joints-source.json').read_text())
controllers={};source_joint_data=[]
for j in joints:
    prim=stage.GetPrimAtPath(j['path']);bn0=j['rels']['physics:body0'][0].split('/')[-1];bn1=j['rels']['physics:body1'][0].split('/')[-1]
    parent=links[bn0];child=links[bn1]
    bpy.context.view_layer.update();saved=child.matrix_world.copy()
    child.parent=parent;child.matrix_parent_inverse=Matrix.Identity(4);child.matrix_world=saved
    if j['type']=='PhysicsRevoluteJoint':
        q=prim.GetAttribute('physics:localRot0').Get();quat=Quaternion((q.GetReal(),*q.GetImaginary()))
        axis=quat @ Vector((1,0,0))
        controllers[prim.GetName()]=(child,axis)
        child.rotation_mode='QUATERNION'
        angle=.1 if '_hip_' in prim.GetName() and 'L_' in prim.GetName() else -.1 if '_hip_' in prim.GetName() else .8 if prim.GetName().startswith('F') and '_thigh_' in prim.GetName() else 1.0 if '_thigh_' in prim.GetName() else -1.5
        child.rotation_quaternion=Quaternion(axis,angle)
        source_joint_data.append({'name':prim.GetName(),'axis_parent':list(axis),'child':child.name,'initial_radians':angle})
# After hierarchy configuration, source reference positions are local, not evaluated pose.
for j in joints:
    prim=stage.GetPrimAtPath(j['path']);child=links[j['rels']['physics:body1'][0].split('/')[-1]]
    p0=prim.GetAttribute('physics:localPos0').Get();child.location=tuple(p0)
bpy.context.view_layer.update()
low=min((o.matrix_world @ Vector(v)).z for o in scene.objects if o.type=='MESH' for v in o.bound_box)
rig.location.z=-low+.005
# Turntable is a physical root rotation. First pose faces camera exactly.
for f,ang in [(1,0),(24,0),(96,math.radians(315)),(120,math.radians(315)),(300,math.radians(315))]:
    rig.rotation_euler.z=ang;rig.keyframe_insert('rotation_euler',frame=f)
# Link separation is explanatory, never a claim about removable internal assemblies.
exploded=[]
for name,link in links.items():
    base=link.location.copy();off=Vector((0,0,0))
    if name.endswith('_hip'):off=Vector((.10 if name[0]=='F' else -.10,.16 if name[1]=='L' else -.16,0))
    elif name.endswith('_thigh'):off=Vector((0,.09 if name[1]=='L' else -.09,-.02))
    elif name.endswith('_calf'):off=Vector((0,0,-.07))
    elif name=='Head_upper':off=Vector((.12,0,.05))
    elif name=='Head_lower':off=Vector((.09,0,-.06))
    if off.length:
        for f,v in [(120,base),(156,base+off),(180,base+off),(216,base),(300,base)]:
            link.location=v;link.keyframe_insert('location',frame=f)
        exploded.append(name)
# Twelve markers located at the actual revolute attachment origins.
marker_mat=bpy.data.materials.new('FOOTHOLD_joint_teal');marker_mat.diffuse_color=(.03,.58,.45,1);marker_mat.use_nodes=True
bs=marker_mat.node_tree.nodes.get('Principled BSDF');bs.inputs['Base Color'].default_value=(.03,.58,.45,1);bs.inputs['Emission Color'].default_value=(.03,.58,.45,1);bs.inputs['Emission Strength'].default_value=.25
for name,(link,axis) in controllers.items():
    bpy.ops.mesh.primitive_uv_sphere_add(segments=16,ring_count=8,radius=.018)
    o=bpy.context.object;o.name='JOINT_MARKER_'+name;o.parent=link;o.location=(0,0,0);o.data.materials.append(marker_mat)
    for f,s in [(1,.001),(216,.001),(240,1),(300,1)]:o.scale=(s,s,s);o.keyframe_insert('scale',frame=f)
    # Axis is in the parent frame. Marker spheres intentionally do not assert rotation angle.
scene.frame_start=1;scene.frame_end=264;scene.render.fps=24
for label,f in [('FRONT',1),('TURN_START',24),('THREE_QUARTER',96),('EXPLODE_START',120),('EXPLODED',156),('ASSEMBLE_START',180),('ASSEMBLED',216),('TWELVE_JOINTS',240)]:scene.timeline_markers.new(label,frame=f)
def aim(obj,target):obj.rotation_euler=(Vector(target)-obj.location).to_track_quat('-Z','Y').to_euler()
bpy.ops.object.camera_add(location=(2.4,0,1.12));cam=bpy.context.object;cam.name='CAM_Go2_front';aim(cam,(0,0,.28));cam.data.type='ORTHO';cam.data.ortho_scale=1.72;scene.camera=cam
scene.world.color=(.2,.2,.2);scene.world.use_nodes=True;scene.world.node_tree.nodes['Background'].inputs[0].default_value=(.25,.28,.32,1);scene.world.node_tree.nodes['Background'].inputs[1].default_value=.35
for name,loc,power,size in [('LGT_key',(1,-2,3),220,3),('LGT_fill',(1,2,1.7),90,2),('LGT_rim',(-2,1,2),180,2)]:
    data=bpy.data.lights.new(name,'AREA');data.energy=power;data.shape='DISK';data.size=size;o=bpy.data.objects.new(name,data);scene.collection.objects.link(o);o.location=loc;aim(o,(0,0,.3))
scene.render.engine='BLENDER_EEVEE_NEXT';scene.render.resolution_x=960;scene.render.resolution_y=720;scene.render.resolution_percentage=100
scene.render.film_transparent=True;scene.render.image_settings.file_format='PNG';scene.render.image_settings.color_mode='RGBA'
scene.view_settings.view_transform='AgX';scene.view_settings.look='AgX - Medium Low Contrast'
scene.frame_set(1)
(ROOT/'geometry-manifest.json').write_text(json.dumps({'geometry':geometry,'joints':source_joint_data,'exploded_links':exploded,'materials':'USD diffuse constants preserved; roughness .48 studio adaptation','frames':{'front':1,'three_quarter':96,'exploded':156,'assembled':216,'joints':240}},indent=2),encoding='utf-8')
bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'go2-presentation-v1.blend'))
for name,frame in [('front',1),('three-quarter',96),('exploded',156),('joints',240)]:
    scene.frame_set(frame);scene.render.filepath=str(ROOT/('go2-'+name+'.png'));bpy.ops.render.render(write_still=True)
scene.frame_set(1)
result={'blend':str(ROOT/'go2-presentation-v1.blend'),'source_mesh_count':len(geometry),'actuated_joints':len(controllers),'rendered':['front','three-quarter','exploded','joints']}
