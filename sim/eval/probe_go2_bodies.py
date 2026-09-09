"""Go2 USD 의 강체(rigid body) 이름과 충돌체를 전수로 읽는다.

**왜 만들었나.** 「라이다 링크에 뭐가 닿았나」를 세려면 그 링크의 **이름**을 알아야
하는데, 팀 문서가 `Head_upper` · `Head_lower` 라고 적어 온 것은 URDF 관행에서 온
추정이었다. `sim/eval/` 에는 그 이름을 확인한 코드가 없었다
(`docs/research/20260908-success-criteria-anatomy.md` 7절). 그래서 USD 를 직접 연다.

실행:

    export KMP_DUPLICATE_LIB_OK=TRUE
    export OMNI_KIT_ACCEPT_EULA=YES
    <isaac311 python> sim/eval/probe_go2_bodies.py out.json

`probe_go2_joint_limits.py` 와 같은 실행 조건이다. `conda activate isaac311` 만으로는
안 된다. KMP 를 빼면 libiomp5md.dll 중복 초기화로 죽고, EULA 를 빼면 프롬프트에서 멈춘다.

**조용한 실패를 막는 자리.** `ISAACLAB_NUCLEUS_DIR` 이 None 이면 경로가 `None/Isaac/...`
가 되는데 종료코드 0 에 결과 파일까지 생긴다. 빈 채로. 그래서 강체를 하나도 못 찾으면
종료코드 1 로 죽는다. `probe_go2_joint_limits.py` 가 같은 자리에 같은 관문을 둔다.
"""

import json
import sys

sys.stdout.reconfigure(encoding="utf-8")

from isaacsim import SimulationApp

app = SimulationApp({"headless": True})

from isaacsim.storage.native import get_assets_root_path
from pxr import Usd, UsdPhysics

# 「이 링크가 라이다·머리인가」를 물을 때 쓰는 낱말. 소문자로 비교한다.
# 이름을 못 찾으면 사람이 전체 목록을 보고 고르라는 뜻이지, 조용히 넘어가지 않는다.
INTEREST_WORDS = ("lidar", "radar", "head", "camera", "sensor", "imu")


def open_stage():
    """`probe_go2_joint_limits.py` 와 같은 두 후보를 같은 순서로 본다."""
    root = get_assets_root_path()

    if not root:
        raise SystemExit("asset root 를 못 잡았다. 네트워크나 카브 설정을 본다.")

    for tail in (
        "/Isaac/IsaacLab/Robots/Unitree/Go2/go2.usd",
        "/Isaac/Robots/Unitree/Go2/go2.usd",
    ):
        # **`LoadAll` 을 빼면 충돌체가 0 개로 보인다** `확인됨`. 2026-09-09 에 겪었다.
        # 페이로드가 안 열린 채로도 강체 19개는 그대로 나오므로 종료코드도 0 이고
        # 목록도 그럴듯하다. 「Head_upper 에 충돌체가 없으니 접촉이 안 잡힌다」는
        # 정반대의 결론이 조용히 나올 뻔했다.
        stage = Usd.Stage.Open(root + tail, Usd.Stage.LoadAll)

        if stage is not None:
            return stage, root + tail

    raise SystemExit("go2.usd 를 못 열었다.")


def read_bodies(stage):
    """`RigidBodyAPI` 가 붙은 프림 전부. 접촉 센서가 보는 후보와 같은 집합이다.

    `ContactSensorCfg(prim_path=".../Robot/.*")` 은 그 밑의 강체를 훑어 목록을
    만든다 (`contact_sensor.py:264-279`). 그래서 여기서 나오는 이름이
    센서의 `body_names` 후보다.
    """
    bodies = []

    for prim in stage.Traverse():
        if not prim.HasAPI(UsdPhysics.RigidBodyAPI):
            continue

        path = prim.GetPath().pathString
        name = prim.GetName()

        colliders = []

        # `AllPrims` 를 안 주면 인스턴스 프록시 밑으로 안 내려간다. 충돌체가
        # 인스턴스 안에 있으면 그대로 0 으로 보인다.
        for child in Usd.PrimRange(prim, Usd.TraverseInstanceProxies()):
            if child.HasAPI(UsdPhysics.CollisionAPI):
                colliders.append(child.GetPath().pathString)

        bodies.append({
            "name": name,
            "path": path,
            "collider_count": len(colliders),
            "colliders": colliders,
        })

    return bodies


def main():
    stage, usd_path = open_stage()

    bodies = read_bodies(stage)

    if not bodies:
        raise SystemExit("강체를 하나도 못 찾았다. 스테이지가 비었다는 뜻이다.")

    interesting = [
        b for b in bodies
        if any(word in b["name"].lower() for word in INTEREST_WORDS)
    ]

    report = {
        "usd_path": usd_path,
        "body_count": len(bodies),
        "body_names": [b["name"] for b in bodies],
        "bodies": bodies,
        "interest_words": list(INTEREST_WORDS),
        "interesting": interesting,
    }

    print(f"USD          : {usd_path}")
    print(f"강체 수       : {len(bodies)}")
    print("")
    print("이름 (충돌체 수)")

    for b in bodies:
        print(f"  {b['name']:<20} {b['collider_count']}")

    print("")
    print(f"관심 낱말 {INTEREST_WORDS} 에 걸린 강체 : {len(interesting)}")

    for b in interesting:
        print(f"  {b['name']}  <- {b['path']}")
        for c in b["colliders"]:
            print(f"      충돌체: {c}")

    if len(sys.argv) > 1:
        with open(sys.argv[1], "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

        print("")
        print(f"기록: {sys.argv[1]}")

    app.close()


main()
