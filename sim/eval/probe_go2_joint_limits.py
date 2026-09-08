"""Go2 USD 의 관절 한계를 읽고 최대 발 높이를 계산한다.

무조코 쪽 값(맹라현 `20260903-rails-diagnosis`, 33.5 cm)이 아이작에서도 서는지
대조하려고 만들었다. 결과는 `inbox/jay/20260907-go2-관절한계-실측.md`.

실행:

    export KMP_DUPLICATE_LIB_OK=TRUE
    export OMNI_KIT_ACCEPT_EULA=YES
    <isaac311 python> sim/eval/probe_go2_joint_limits.py out.json

`conda activate isaac311` 만으로는 안 된다. `isaaclab.bat` 은 base 파이썬을 써서
`tensordict` 가 없다고 죽는다. 환경변수 둘도 필요하다. KMP 를 빼면 libiomp5md.dll
중복 초기화로 죽고, EULA 를 빼면 동의 프롬프트에서 멈춘다.

**조용히 실패한 적이 있다.** `ISAACLAB_NUCLEUS_DIR` 이 None 이면 경로가
`None/Isaac/...` 가 되는데 종료코드 0 에 결과 파일까지 생긴다. 관절 0개가 담긴 채로.
그래서 이 스크립트는 관절 수를 세어 0 이면 종료코드 1 로 죽는다.
"""

import io
import json
import math
import sys

sys.stdout.reconfigure(encoding="utf-8")

from isaacsim import SimulationApp

app = SimulationApp({"headless": True})

from isaacsim.storage.native import get_assets_root_path
from pxr import Usd, UsdGeom, UsdPhysics

D2R = math.pi / 180.0

# unitree.py 의 UNITREE_GO2_CFG.init_state.joint_pos
BASE_POSE = {"front": (0.8, -1.5), "rear": (1.0, -1.5)}
SOFT_FACTOR = 0.9  # UNITREE_GO2_CFG.soft_joint_pos_limit_factor


def open_stage():
    root = get_assets_root_path()
    if not root:
        raise SystemExit("asset root 를 못 잡았다. 네트워크나 카브 설정을 본다.")
    for tail in (
        "/Isaac/IsaacLab/Robots/Unitree/Go2/go2.usd",
        "/Isaac/Robots/Unitree/Go2/go2.usd",
    ):
        stage = Usd.Stage.Open(root + tail)
        if stage is not None:
            return stage, root + tail
    raise SystemExit("go2.usd 를 못 열었다.")


def read_joints(stage):
    out = {}
    for prim in stage.Traverse():
        if prim.IsA(UsdPhysics.RevoluteJoint):
            j = UsdPhysics.RevoluteJoint(prim)
            out[prim.GetName()] = {
                "lower_deg": j.GetLowerLimitAttr().Get(),
                "upper_deg": j.GetUpperLimitAttr().Get(),
                "axis": str(j.GetAxisAttr().Get()),
            }
    return out


def read_link_lengths(stage):
    """thigh -> calf -> foot 원점 사이 거리로 마디 길이를 잰다."""
    pts = {}
    for prim in stage.Traverse():
        p = prim.GetPath().pathString
        if not prim.IsA(UsdGeom.Xformable):
            continue
        name = p.rsplit("/", 1)[-1]
        if name in ("FL_thigh", "FL_calf", "FL_foot"):
            m = UsdGeom.Xformable(prim).ComputeLocalToWorldTransform(Usd.TimeCode.Default())
            t = m.ExtractTranslation()
            pts[name] = (t[0], t[1], t[2])
    if len(pts) < 3:
        return None, None
    d = lambda a, b: math.dist(pts[a], pts[b])
    return d("FL_thigh", "FL_calf"), d("FL_calf", "FL_foot")


def foot_z(thigh, calf, l1, l2):
    """다리 평면에서 hip 기준 발의 수직 위치. 아래가 음수."""
    return -(l1 * math.cos(thigh) + l2 * math.cos(thigh + calf))


def max_lift(t_lo, t_hi, c_lo, c_hi, base_z, l1, l2, factor, steps=400):
    """발이 몸통 «아래» 인 자세로 한정해 기본자세보다 더 드는 최대 높이를 찾는다.

    발이 몸통 위로 넘어간 자세는 관절이 허용해도 보행에 못 쓴다. 맹라현의 무조코
    계산도 같은 조건이라 그래야 대조가 된다.
    """

    def soften(lo, hi):
        mid, half = (lo + hi) / 2.0, (hi - lo) / 2.0 * factor
        return mid - half, mid + half

    t_lo, t_hi = soften(t_lo * D2R, t_hi * D2R)
    c_lo, c_hi = soften(c_lo * D2R, c_hi * D2R)
    best, arg = None, None
    for i in range(steps + 1):
        t = t_lo + (t_hi - t_lo) * i / steps
        for k in range(steps + 1):
            c = c_lo + (c_hi - c_lo) * k / steps
            z = foot_z(t, c, l1, l2)
            if z > -0.001:  # 발이 몸통 위로 올라간 자세는 버린다
                continue
            lift = z - base_z
            if best is None or lift > best:
                best, arg = lift, (t / D2R, c / D2R)
    return best, arg


def main():
    out_path = sys.argv[1] if len(sys.argv) > 1 else "go2_joint_limits.json"
    stage, usd = open_stage()
    joints = read_joints(stage)

    # 조용한 실패를 막는다. 관절이 없으면 이 스크립트는 아무것도 안 한 것이다.
    if not joints:
        raise SystemExit("관절을 하나도 못 읽었다. USD 경로를 의심한다: " + usd)

    l1, l2 = read_link_lengths(stage)
    if l1 is None:
        raise SystemExit("링크 원점을 못 읽어 마디 길이를 모른다.")

    res = {"usd": usd, "joints": joints, "thigh_m": round(l1, 5), "calf_m": round(l2, 5)}
    for tag, prefix in (("front", "FL"), ("rear", "RL")):
        t = joints[prefix + "_thigh_joint"]
        c = joints[prefix + "_calf_joint"]
        bt, bc = BASE_POSE[tag]
        base_z = foot_z(bt, bc, l1, l2)
        lift, arg = max_lift(
            t["lower_deg"], t["upper_deg"], c["lower_deg"], c["upper_deg"], base_z, l1, l2, SOFT_FACTOR
        )
        hard, _ = max_lift(
            t["lower_deg"], t["upper_deg"], c["lower_deg"], c["upper_deg"], base_z, l1, l2, 1.0
        )
        res[tag] = {
            "base_foot_z_m": round(base_z, 5),
            "max_lift_cm_soft": round(lift * 100, 2),
            "max_lift_cm_hard": round(hard * 100, 2),
            "at_thigh_deg": round(arg[0], 1),
            "at_calf_deg": round(arg[1], 1),
        }
        print("%-6s 최대 발 높이 %.1f cm (하드 한계 %.1f cm)" % (tag, lift * 100, hard * 100))

    io.open(out_path, "w", encoding="utf-8").write(json.dumps(res, ensure_ascii=False, indent=1))
    print("관절 %d개 · thigh %.3f m · calf %.3f m -> %s" % (len(joints), l1, l2, out_path))


main()
app.close()
