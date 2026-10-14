"""CPU mesh construction: explicit 0.2 m asymmetric markers and no hidden gap plane."""
from types import SimpleNamespace
import sys

import numpy as np

from s2_known_scene_a2 import _terrain,answer,oracle


# The worker CPU Python lacks trimesh. This small geometric shim exercises the
# actual terrain construction call and its returned triangles without Isaac.
class Mesh:
    def __init__(self,vertices,faces,process=False):
        self.vertices=np.asarray(vertices,dtype=float)
        self.faces=np.asarray(faces,dtype=int)
    def apply_translation(self,delta):self.vertices+=np.asarray(delta)


def box(extents,transform):
    x,y,z=np.asarray(extents,dtype=float)/2
    vertices=np.array([(-x,-y,-z),(x,-y,-z),(x,y,-z),(-x,y,-z),
                       (-x,-y,z),(x,-y,z),(x,y,z),(-x,y,z)])
    faces=np.array([(0,1,2),(0,2,3),(4,5,6),(4,6,7),
                    (0,1,5),(0,5,4),(1,2,6),(1,6,5),
                    (2,3,7),(2,7,6),(3,0,4),(3,4,7)])
    return Mesh(vertices+np.asarray(transform)[:3,3],faces)


def translation_matrix(center):
    transform=np.eye(4);transform[:3,3]=center
    return transform


def check(name,good):
    print(("PASS" if good else "FAIL")+" "+name,flush=True)
    assert good,name


def main():
    sys.modules["trimesh"]=SimpleNamespace(Trimesh=Mesh,
        creation=SimpleNamespace(box=box),
        transformations=SimpleNamespace(translation_matrix=translation_matrix))
    cfg=SimpleNamespace(size=(8.,8.))
    meshes={kind:_terrain(kind,0.,cfg)[0] for kind in answer()["order"]}
    check("four_static_scene_meshes",list(meshes)==answer()["order"] and all(meshes.values()))
    top_step=max(float(x.vertices[:,2].max()) for x in meshes["obstacles"])
    top_stones=max(float(x.vertices[:,2].max()) for x in meshes["stepping_stones"])
    check("step_and_stones_0_2m",abs(top_step-.2)<1e-12 and abs(top_stones-.2)<1e-12)
    z,finite,_=oracle("gap",np.array([[.25,0.],[.45,0.],[-.5,0.]]))
    check("gap_deep_and_true_void",finite.tolist()==[True,False,True] and z[0]==-2)
    # Local void (.45,0) is not covered by any horizontal top triangle.
    point=np.array([4.45,4.,0.])
    hidden=False
    for mesh in meshes["gap"]:
        vertices=mesh.vertices
        for face in mesh.faces:
            tri=vertices[face]
            if np.allclose(tri[:,2],tri[0,2]):
                a,b,c=tri[:,:2]
                cross=lambda u,v:np.linalg.det(np.stack((u,v)))
                p=point[:2]
                vals=(cross(b-a,p-a),cross(c-b,p-b),cross(a-c,p-c))
                if min(vals)>=-1e-10 or max(vals)<=1e-10:hidden=True
    check("void_has_no_horizontal_plane",not hidden)

if __name__=="__main__":main()
