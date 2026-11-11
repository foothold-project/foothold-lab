import json
import numpy as np
import pytest
from foothold_s2.terrains.ex42_eval_terrains import write_mesh
from foothold_s2.eval.ex42_task_mesh import select_tile, build_replicas, preflight


def test_actual_saved_triangles_selected_not_regenerated(tmp_path):
    source=tmp_path/'source'
    write_mesh(source,kinds=['eval_stairs_025','eval_slope_35'],seed=42)
    tile=select_tile(source,family='V',kind='eval_slope_35',level=0)
    assert np.allclose(tile['origin'],[.5,4,0])
    assert tile['vertices'][:,1].min()>=0 and tile['vertices'][:,1].max()<=8
    out=tmp_path/'replica'
    doc=build_replicas(source,out,family='V',kind='eval_slope_35',level=0)
    loaded=preflight(out)
    assert loaded['origins'].shape==(8,8,3)
    assert np.unique(loaded['origins'].reshape(-1,3),axis=0).shape[0]==64
    assert doc['source_mesh_sha256']==tile['source_mesh_sha256']
    assert doc['tile_triangle_sha256']==tile['tile_triangle_sha256']
    with pytest.raises(FileExistsError): build_replicas(source,out,family='V',kind='eval_slope_35',level=0)
    record=json.loads((out/'replica_receipt.json').read_text())
    record['source_mesh_sha256']='0'*64
    (out/'replica_receipt.json').write_text(json.dumps(record))
    with pytest.raises(ValueError,match='source'):preflight(out)


def test_flat_reference_is_explicit_and_preserves_xy_start(tmp_path):
    source=tmp_path/'source';write_mesh(source,kinds=['high_ledge_075'],seed=42)
    doc=build_replicas(source,tmp_path/'flat',family='V',kind='high_ledge_075',level=0,flat=True)
    data=preflight(tmp_path/'flat')
    assert doc['flat_reference'] is True
    assert np.allclose(data['origins'][0,0],[.5,4,0])
    assert data['vertices'][:,2].max()==0


def test_unknown_kind_level_cannot_fall_back(tmp_path):
    source=tmp_path/'source';write_mesh(source,kinds=['eval_stairs_025'],seed=42)
    for kind,level in [('eval_stairs_020',0),('eval_stairs_025',9)]:
        with pytest.raises(ValueError):select_tile(source,family='V',kind=kind,level=level)


def test_family_e_evaluation_starts_at_measured_entry_not_summit(tmp_path):
    import hashlib
    import trimesh
    pieces=[];origins=np.zeros((10,4,3))
    for r in range(10):
        for c in range(4):
            offset=np.array([(r-5)*8,(c-2)*8,0])
            for size,pos in [([8,8,.2],[4,4,-.1]),([3,3,1],[4,4,.5])]:
                box=trimesh.creation.box(size);box.apply_translation(np.array(pos)+offset);pieces.append(box)
            origins[r,c]=np.array([4,4,1])+offset
    m=trimesh.util.concatenate(pieces);v=np.asarray(m.vertices,np.float32);f=np.asarray(m.faces,np.int32)
    np.savez_compressed(tmp_path/'terrain_mesh.npz',vertices=v,faces=f,origins=origins,column_family=np.array(['E']*4))
    (tmp_path/'mesh_manifest.json').write_text(json.dumps(dict(format='foothold-ex42-combined-mesh/1',
        mesh_sha256=hashlib.sha256(v.tobytes()+f.tobytes()).hexdigest(),offsets_m={'E':0})))
    before=(tmp_path/'terrain_mesh.npz').read_bytes()
    t=select_tile(tmp_path,family='E',kind='slope_steep',level=6)
    assert np.allclose(t['origin'],[.5,4,0])
    assert np.allclose(t['source_origin'],[4,4,1])
    assert before==(tmp_path/'terrain_mesh.npz').read_bytes()
