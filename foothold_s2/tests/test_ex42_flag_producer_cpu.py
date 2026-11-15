"""Flags refer to the actual support mesh, with the consumer's world XY contract."""
import numpy as np
import pytest
import trimesh

from foothold_s2.terrains import ex42_flag_producer as fp
from foothold_s2.terrains.ex42_flags import load_flag_table, MeshFlagProvider


def boxes(rows):
    meshes=[]
    for x0,x1,y0,y1,z0,z1 in rows:
        tf=trimesh.transformations.translation_matrix(((x0+x1)/2,(y0+y1)/2,(z0+z1)/2))
        meshes.append(trimesh.creation.box((x1-x0,y1-y0,z1-z0),transform=tf))
    return trimesh.util.concatenate(meshes)


def test_gap_flags_never_select_pit_floor_or_leave_support():
    mesh=boxes([(0,12,0,12,-1.1,-1),(0,5.5,0,12,-.2,0),(6.5,12,0,12,-.2,0)])
    xy,meta=fp.tile_flags('B','gap',mesh.triangles,np.array([2,6,0]),(12,12))
    assert xy.shape==(4,2) and np.all(np.diff(xy[:,0])>0)
    assert not np.any((xy[:,0]>5.5)&(xy[:,0]<6.5))
    assert meta['support_z_m']==pytest.approx([0]*4)


def test_wall_route_goes_through_corridor_not_over_wall():
    from foothold_s2.terrains import hipan_posture as hp
    tile=hp.build_tile('wall',0,seed=42,wall_height_m=hp.WALL_HEIGHT_M,corridor_width_m=hp.CORRIDOR_WIDTH_M)
    mesh=trimesh.util.concatenate(hp.meshes_for(tile))
    xy,meta=fp.tile_flags('D','wall',mesh.triangles,tile.origin,tile.size)
    assert xy[0,0]<3.95 and xy[1,0]>4.05
    assert np.all(xy[:2,1]>7.2)
    assert meta['support_z_m']==pytest.approx([0]*4)


def test_crawl_flags_are_on_floor_below_roof():
    from foothold_s2.terrains import hipan_posture as hp
    tile=hp.build_tile('crawl',9,seed=42)
    mesh=trimesh.util.concatenate(hp.meshes_for(tile))
    xy,meta=fp.tile_flags('D','crawl',mesh.triangles,tile.origin,tile.size)
    assert meta['support_z_m']==pytest.approx([0]*4)
    assert np.any((xy[:,0]>2)&(xy[:,0]<6))


def test_missing_support_is_error_not_straight_fallback():
    mesh=boxes([(0,1,0,8,-.1,0)])
    with pytest.raises(ValueError,match='support|progress'):
        fp.tile_flags('C','gap',mesh.triangles,np.array([.5,4,0]),(9,9))
    with pytest.raises(ValueError,match='unknown'):
        fp.tile_flags('C','missing_kind',mesh.triangles,np.array([.5,4,0]),(9,9))


def test_continuous_A_keeps_straight_consumer_fallback():
    xy,meta=fp.tile_flags('A','pyramid_stairs',np.empty((0,3,3)),np.array([4,4,0]),(8,8))
    assert np.isnan(xy).all() and meta['rule']=='existing_continuous_straight'


def test_family_and_combined_offsets_are_applied_once(tmp_path):
    from types import SimpleNamespace
    import torch
    from foothold_s2.terrains.ex42_combined import combine_family_parts
    from foothold_s2.scripts.ex42_mesh_build import build_flags, write_mesh_arrays
    parts=[]
    for family,size in [('D',8.),('E',8.)]:
        tiles=[];origins=np.empty((2,1,3))
        for row in range(2):
            tile=boxes([(0,size,0,size,-.1,0)])
            shift=np.array([(row-1)*size,-size/2,0])
            tile.apply_translation(shift);tiles.append(tile)
            origins[row,0]=np.array([1,size/2,0])+shift
        mesh=trimesh.util.concatenate(tiles)
        kind='high_ledge' if family=='D' else 'stairs_high'
        parts.append(dict(name=family,mesh=mesh,origins=origins,kinds=[kind],size=(size,size)))
    combined=combine_family_parts(parts)
    vertices_before=combined['vertices'].copy();faces_before=combined['faces'].copy()
    flags,provenance=build_flags(parts,combined)
    assert flags.shape==(2,2,4,2)
    assert flags[:,1,:,1]==pytest.approx(flags[:,0,:,1]+combined['offsets']['E'])
    assert flags[1,:,:,0]==pytest.approx(flags[0,:,:,0]+8)
    p=tmp_path/'mesh.npz';write_mesh_arrays(p,combined,flags)
    with np.load(p) as stored:
        assert np.array_equal(stored['vertices'],vertices_before.astype(np.float32))
        assert np.array_equal(stored['faces'],faces_before.astype(np.int32))
        assert np.array_equal(stored['origins'],combined['origins'])
    loaded=load_flag_table(p,2,2)
    terrain=SimpleNamespace(terrain_levels=torch.tensor([0,1]),terrain_types=torch.tensor([1,0]),env_origins=torch.zeros((2,3)))
    out=MeshFlagProvider(loaded)(terrain,torch.tensor([0,1]),4)
    assert out.numpy()==pytest.approx(np.stack([flags[0,1],flags[1,0]]))
    assert provenance['coordinates']=='world_xy_m' and provenance['finite_cells']==4


def test_waypoint_selection_does_not_consume_rng():
    mesh=boxes([(0,8,0,8,-.1,0)])
    before=np.random.get_state()
    fp.tile_flags('D','high_ledge',mesh.triangles,np.array([1,4,0]),(8,8))
    after=np.random.get_state()
    assert before[0]==after[0] and np.array_equal(before[1],after[1]) and before[2:]==after[2:]


@pytest.mark.parametrize('level',[0,5,9])
def test_real_family_tiles_all_kinds_at_three_levels(level):
    from foothold_s2.terrains import ame2_preset as b, jeplo_preset as c, hipan_posture as d
    for kind in b.KINDS:
        tile=b.build_tile(kind,level,42)
        mesh=trimesh.util.concatenate(b.mesh_arrays(tile))
        xy,meta=fp.tile_flags('B',kind,mesh.triangles,b.spawn_origin(tile),(12,12))
        assert np.isfinite(xy).all() and len(meta['support_z_m'])==4, ('B',kind,level)
    for kind in c.KINDS:
        tile=c.build_heightfield(kind,level,42)
        v,f=c.mesh_arrays(tile)
        xy,meta=fp.tile_flags('C',kind,v[f],c.spawn_origin(tile,vertices=v,faces=f),(9,9))
        assert np.isfinite(xy).all() and len(meta['support_z_m'])==4, ('C',kind,level)
    for kind in d.KINDS:
        tile=d.build_tile(kind,min(level,d.LEVEL_COUNTS[kind]-1),seed=42,
                          wall_height_m=d.WALL_HEIGHT_M,corridor_width_m=d.CORRIDOR_WIDTH_M)
        mesh=trimesh.util.concatenate(d.meshes_for(tile))
        xy,meta=fp.tile_flags('D',kind,mesh.triangles,tile.origin,tile.size)
        assert np.isfinite(xy).all() and len(meta['support_z_m'])==4, ('D',kind,level)


def test_offline_annotation_preserves_geometry_and_source_receipts(tmp_path):
    import hashlib,json
    from foothold_s2.tools.ex42_mesh_flags import annotate
    from foothold_s2.terrains import hipan_posture as d
    from foothold_s2.terrains.ex42_combined import combine_family_parts
    tiles=[];origins=[]
    for col,kind in enumerate(d.KINDS):
        tile=d.build_tile(kind,0,seed=42,wall_height_m=d.WALL_HEIGHT_M,corridor_width_m=d.CORRIDOR_WIDTH_M)
        shift=np.array([-4,(col-1.5)*8,0.])
        mesh=trimesh.util.concatenate(d.meshes_for(tile));mesh.apply_translation(shift)
        tiles.append(mesh);origins.append(tile.origin+shift)
    combined=combine_family_parts([dict(name='D',mesh=trimesh.util.concatenate(tiles),origins=np.array([origins]))])
    source=tmp_path/'source';source.mkdir();p=source/'terrain_mesh.npz'
    np.savez_compressed(p,vertices=combined['vertices'].astype(np.float32),faces=combined['faces'].astype(np.int32),
                        origins=combined['origins'],column_family=np.array(combined['column_family']))
    original=p.read_bytes();agg=b'{"partial_generation_seconds": 1.0}\n'
    (source/'aggregate_partial_mesh.json').write_bytes(agg)
    doc={'format':'foothold-ex42-combined-mesh/1','join_axis':1,'families_present':['D'],
         'columns_by_family':{'D':3},'offsets_m':{'D':0.},'origins_shape':[1,3,3],
         'mesh_sha256':hashlib.sha256(combined['vertices'].astype(np.float32).tobytes()+combined['faces'].astype(np.int32).tobytes()).hexdigest(),
         'mesh_file_sha256':hashlib.sha256(original).hexdigest(),'aggregate_file':'aggregate_partial_mesh.json'}
    mp=source/'mesh_manifest.json';mp.write_text(json.dumps(doc))
    result=annotate(source,tmp_path/'new')
    assert p.read_bytes()==original and json.loads(mp.read_text())==doc
    assert (tmp_path/'new'/'aggregate_partial_mesh.json').read_bytes()==agg
    with np.load(p) as a,np.load(tmp_path/'new'/'terrain_mesh.npz') as b:
        for key in a.files:
            assert np.array_equal(a[key],b[key])
        assert np.isfinite(b['flags']).all() and b['flags'].shape==(1,3,4,2)
    assert result['mesh_sha256']==doc['mesh_sha256']
    assert result['flag_annotation_source']['new_kit_validation'] is False
    assert not (tmp_path/'new'/'terrain_manifest.json').exists()
    with pytest.raises(FileExistsError):
        annotate(source,tmp_path/'new')
    doc['mesh_file_sha256']='0'*64;mp.write_text(json.dumps(doc))
    with pytest.raises(ValueError,match='SHA mismatch'):
        annotate(source,tmp_path/'bad')
    assert not (tmp_path/'bad').exists()
