"""17x: a realistic provider's rows, stacked by the real capture(), must be accepted by the real checker
(array-shape convention between collector and checker). CPU only."""
import numpy as np

from s2_connect_check_17v import Criteria,check_arrays
from s2_connect_diag_17v import capture
from test_s2_connect_a2 import fixture


class FixtureProvider:
    """Replays the analytic fixture row by row, exactly the way a live provider hands rows to capture()."""
    num_envs=8
    def __init__(self,data):self.data=data;self.i=-1
    def reset(self):pass
    def translate(self):pass
    def reset_new_height_position(self):pass
    def change_yaw(self):pass
    def step_zero(self):self.i+=1
    def sample(self,step):
        row={}
        for key,value in self.data.items():
            if key in ("intervention_code","mode"):continue
            row[key]=np.arange(187) if key=="ray_index" else value[step]
        return row


def check(name,good):
    print(("PASS" if good else "FAIL")+" "+name,flush=True)
    assert good,name


def main():
    meta,data=fixture()
    got=capture(FixtureProvider(data),steps=256)
    check("capture_keys_match_fixture",set(got)==set(data))
    check("capture_shapes_match_fixture",all(got[k].shape==data[k].shape for k in data))
    check("ray_index_is_187_vector",got["ray_index"].shape==(187,))
    result=check_arrays(meta,got,Criteria(.002,.002,.005,256,16))
    check("collected_arrays_pass_checker",result["verdict"]=="PASS")


if __name__=="__main__":main()
