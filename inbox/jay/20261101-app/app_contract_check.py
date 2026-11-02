"""APP-POLICY-CONTRACT-m6000.md §9 기계 블록을 m6000 run 폴더의 env.yaml · agent.yaml · 기록 파일과 ex40.yaml 로 대조한다.

사용: python -X utf8 app_contract_check.py [문서 md] [run 폴더] [ex40.yaml] [--no-sha]
종료 0 = 전부 일치 · 1 = 어긋남(어느 칸인지 출력) · 2 = 입력 없음.
문서 숫자가 설정과 갈라지면(예: Kp 를 30 으로 적음) 여기서 걸린다. --no-sha 는 27 MB 해시를 건너뛴다.
"""
import hashlib
import json
import re
import sys
from pathlib import Path

import yaml

args = [a for a in sys.argv[1:] if not a.startswith("--")]
no_sha = "--no-sha" in sys.argv
here = Path(__file__).resolve().parent
doc = Path(args[0]) if len(args) > 0 else here / "APP-POLICY-CONTRACT-m6000.md"
run = Path(args[1]) if len(args) > 1 else Path("C:/Users/AI-WS01/s2_lab/ex40_main_20261031_041313/main/EX-40-B-main_20261031_041337_26240")
ex40 = Path(args[2]) if len(args) > 2 else Path("D:/mai-wt/foothold-lab/analyst-ex41-score-name-1102/foothold_s2/curriculum/ex40.yaml")
envy, agenty, meta, model = run / "params/env.yaml", run / "params/agent.yaml", run / "training_trace/coordinate_metadata.json", run / "model_6000.pt"
for p in (doc, envy, agenty, meta, ex40):
    if not p.is_file():
        print("없음:", p)
        sys.exit(2)

m = re.search(r"```json\s*(\{.*?\})\s*```", doc.read_text(encoding="utf-8"), re.S)
if not m:
    print("문서 기계 블록 없음"); sys.exit(1)
spec = json.loads(m.group(1))

class L(yaml.SafeLoader):
    pass
L.add_constructor("tag:yaml.org,2002:python/tuple", lambda ld, node: tuple(ld.construct_sequence(node)))
L.add_multi_constructor("tag:yaml.org,2002:python/", lambda ld, suffix, node: None)
L.add_multi_constructor("tag:yaml.org,2002:python/object/apply:", lambda ld, suffix, node: None)
e = yaml.load(envy.read_text(encoding="utf-8"), Loader=L)
a = yaml.safe_load(agenty.read_text(encoding="utf-8"))
md = json.load(open(meta, encoding="utf-8-sig"))
x40 = yaml.safe_load(ex40.read_text(encoding="utf-8"))

bad = 0
def ok(cond, label):
    global bad
    print(("ok  " if cond else "MISS") + " " + label)
    bad += 0 if cond else 1
def eq(got, want, label):
    ok(got == want, f"{label}: 문서 {want!r} / 실제 {got!r}")

eq(e["sim"]["dt"], spec["sim_dt"], "sim dt")
eq(e["decimation"], spec["decimation"], "decimation")
eq(e["scene"]["depth_cam"]["update_period"], spec["depth_update_period"], "depth update_period")
eq(md["joint_names"], spec["joint_names_isaac"], "관절 순서(training_trace)")
eq(md.get("source"), "training", "기록 출처 training")
eq(float(md.get("control_dt_s")), round(spec["sim_dt"] * spec["decimation"], 6), "기록 control_dt = dt x decimation")
rob = e["scene"]["robot"]
eq(rob["init_state"]["joint_pos"], spec["default_joint_pos"], "기본 관절각")
eq(float(rob["init_state"]["pos"][2]), spec["init_pos_z"], "시작 높이")
act = rob["actuators"]
ht = [v for v in act.values() if ".*_hip_joint" in v["joint_names_expr"]][0]
cf = [v for v in act.values() if ".*_calf_joint" in v["joint_names_expr"]][0]
for name, v in (("hip_thigh", ht), ("calf", cf)):
    eq(v["stiffness"], spec["stiffness"], f"{name} Kp")
    eq(v["damping"], spec["damping"], f"{name} Kd")
eq(ht["effort_limit"], spec["effort_limit_hip_thigh"], "hip·thigh 토크 한계")
eq(ht["velocity_limit"], spec["velocity_limit_hip_thigh"], "hip·thigh 속도 한계")
eq(cf["effort_limit"], spec["effort_limit_calf"], "calf 토크 한계")
eq(cf["velocity_limit"], spec["velocity_limit_calf"], "calf 속도 한계")
jp = e["actions"]["joint_pos"]
eq(jp["scale"], spec["action_scale"], "행동 배율")
eq(jp["offset"], spec["action_offset"], "행동 offset")
eq(jp["use_default_offset"], spec["use_default_offset"], "use_default_offset")
eq(jp["max_delay_s"], spec["max_delay_s"], "행동 지연 상한")
eq(a["clip_actions"], spec["clip_actions"], "clip_actions")
eq(a["policy"]["actor_hidden_dims"], spec["actor_hidden_dims"], "actor 은닉")
eq(a["policy"]["activation"], spec["activation"], "활성화")
eq(a["policy"]["actor_obs_normalization"], spec["actor_obs_normalization"], "관측 정규화")
for k in ("force_gt", "p_map_off", "map_input", "est_mode", "critic_mode"):
    eq(a["perception"][k], spec[k], f"perception.{k}")
pol = e["observations"]["policy"]
terms = [k for k, v in pol.items() if isinstance(v, dict) and "func" in v]
eq(terms, spec["policy_terms"], "policy 항 순서")
ok(all(pol[t]["scale"] is None and pol[t]["clip"] is None for t in terms), "policy 항 scale · clip 전부 null")
ok(pol["history_length"] is None, "policy history_length null")
dc = e["scene"]["depth_cam"]
eq(dc["pattern_cfg"]["width"], spec["depth_cam"]["width"], "깊이 폭")
eq(dc["pattern_cfg"]["height"], spec["depth_cam"]["height"], "깊이 높이")
eq([float(v) for v in dc["offset"]["pos"]], spec["depth_cam"]["offset_pos"], "깊이 카메라 위치")
eq(dc["pattern_cfg"]["focal_length"], spec["depth_cam"]["focal_length"], "초점")
gm = e["scene"]["gt_map_scan"]
eq(gm["pattern_cfg"]["resolution"], spec["gt_map_scan"]["resolution"], "지도 해상도")
eq([float(v) for v in gm["pattern_cfg"]["size"]], spec["gt_map_scan"]["size"], "지도 크기")
eq(float(gm["offset"]["pos"][0]), spec["gt_map_scan"]["offset_x"], "지도 중심 x")
eq(gm["pattern_cfg"]["ordering"], spec["gt_map_scan"]["ordering"], "지도 ordering")
b3c = [s for s in x40["stages"] if s.get("id") == "B3c"][0]
rng = b3c.get("ranges") or b3c.get("range") or {}
if not rng:
    for k, v in b3c.items():
        if isinstance(v, dict) and "forward_vx" in v:
            rng = v
eq({k: [float(x) for x in rng[k]] for k in spec["b3c_ranges"]}, spec["b3c_ranges"], "B3c 명령 범위")
if not no_sha and model.is_file():
    h = hashlib.sha256(model.read_bytes()).hexdigest()
    eq(h, spec["model_sha256"], "model_6000 sha256")
elif no_sha:
    print("skip model sha256 (--no-sha)")
else:
    ok(False, f"model 없음 {model}")
print(("ok" if bad == 0 else "FAIL") + f" 어긋남 {bad}")
sys.exit(0 if bad == 0 else 1)
