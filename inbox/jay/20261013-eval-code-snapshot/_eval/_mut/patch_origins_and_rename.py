# Applied after the E2 evaluation chain has ended (q_eval.py and full_record.py are not in use then).
# 1. q_eval.py: save the per-env terrain origins (after the seeded reset, before the fingerprint exit), read only.
# 2. full_record.py: the world base height column is named base_z_w_m (the lab name); base_z_m means height
#    above the floor in the lab timeseries, so our world z must not use that name.
import os, shutil
H = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
p = os.path.join(H, "q_eval.py")
s = open(p, encoding="utf-8").read()
a = 'meta["terrain_origins_sha256"] = sha256_arr(np.round(ter.terrain_origins.cpu().numpy(), 5))\n'
b = a + ('np.save(os.path.join(OUT, "env_origins.npy"), ter.env_origins.cpu().numpy().astype(np.float32))  # floor_z of the lab timeseries\n'
         'meta["env_origins_file"] = "env_origins.npy"\n')
if "env_origins.npy" not in s:
    assert s.count(a) == 1
    shutil.copy(p, os.path.join(H, "_mut", "q_eval_before_env_origins.py"))
    s = s.replace(a, b)
    open(p, "w", encoding="utf-8").write(s)
p = os.path.join(H, "full_record.py")
s = open(p, encoding="utf-8").read()
if '"base_x_m", "base_y_m", "base_z_m",' in s:
    shutil.copy(p, os.path.join(H, "_mut", "full_record_before_base_z_w.py"))
    s = s.replace('"base_x_m", "base_y_m", "base_z_m",', '"base_x_m", "base_y_m", "base_z_w_m",')
    s = s.replace("- base: `base_{x,y,z}_m` world position of the base link;",
                  "- base: `base_x_m`, `base_y_m`, `base_z_w_m` world position of the base link (lab names; `base_z_m` in the lab\n  timeseries means height above the floor, so the world height is `base_z_w_m`);")
    open(p, "w", encoding="utf-8").write(s)
print("patched")
