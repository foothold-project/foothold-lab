"""Isaac Lab rails_terrain 근사 씬을 MJCF로 만든다.

안쪽·바깥 사각 프레임 턱 두 겹. 침목·자갈 없음.
기하 상수 rail_2_ratio=0.6 은 Isaac Lab v2.3.2 rails_terrain 소스와 같다.
"""

from __future__ import annotations

from pathlib import Path

GO2_XML = Path(__file__).with_name("go2_collision.xml")
GO2_MOTOR_XML = Path(__file__).resolve().parent / "vendor" / "unitree_go2" / "go2.xml"


def _bar(name: str, cx: float, cy: float, hx: float, hy: float, hz: float) -> str:
    # geom size 는 반길이
    return (
        f'    <geom name="{name}" type="box" pos="{cx:.5f} {cy:.5f} {hz:.5f}" '
        f'size="{hx:.5f} {hy:.5f} {hz:.5f}" rgba="0.45 0.35 0.22 1" '
        f'friction="0.9 0.02 0.01"/>\n'
    )


def frame_geoms(prefix: str, inner: float, thickness: float, height: float) -> str:
    """한 변 inner 인 정사각 구멍을 thickness 폭으로 감싼 프레임."""
    t = thickness
    h = height
    hz = h / 2.0
    hole = inner / 2.0
    outer = hole + t
    # 앞뒤(+-x) 막대는 y 방향으로 바깥 전체, 좌우(+-y) 막대는 구멍 구간만 (모서리 중복 방지)
    xml = ""
    xml += _bar(f"{prefix}_px", hole + t / 2.0, 0.0, t / 2.0, outer, hz)
    xml += _bar(f"{prefix}_nx", -(hole + t / 2.0), 0.0, t / 2.0, outer, hz)
    xml += _bar(f"{prefix}_py", 0.0, hole + t / 2.0, hole, t / 2.0, hz)
    xml += _bar(f"{prefix}_ny", 0.0, -(hole + t / 2.0), hole, t / 2.0, hz)
    return xml


def rails_xml(
    height: float,
    thickness_inner: float,
    thickness_outer: float,
    tile: float = 8.0,
    platform_width: float = 1.5,
    rail_2_ratio: float = 0.6,
    robot_xml: Path | None = None,
) -> str:
    outer_inner = platform_width + (tile - platform_width) * rail_2_ratio
    go2 = (robot_xml or GO2_XML).resolve()
    assets = go2.parent / "assets"
    meshdir = assets if assets.is_dir() else go2.parent
    body = []
    body.append(frame_geoms("inner", platform_width, thickness_inner, height))
    body.append(frame_geoms("outer", outer_inner, thickness_outer, height))
    rails = "".join(body)
    return f"""<mujoco model="go2_rails">
  <compiler meshdir="{meshdir}"/>
  <include file="{go2}"/>
  <statistic center="0 0 0.2" extent="3"/>
  <visual>
    <headlight diffuse="0.6 0.6 0.6" ambient="0.3 0.3 0.3"/>
    <global azimuth="-120" elevation="-20"/>
  </visual>
  <asset>
    <texture type="skybox" builtin="gradient" rgb1="0.4 0.5 0.6" rgb2="0 0 0" width="256" height="256"/>
    <texture type="2d" name="groundplane" builtin="checker" mark="edge"
      rgb1="0.2 0.3 0.4" rgb2="0.1 0.2 0.3" markrgb="0.8 0.8 0.8" width="200" height="200"/>
    <material name="groundplane" texture="groundplane" texuniform="true" texrepeat="5 5"/>
  </asset>
  <worldbody>
    <light pos="0 0 2" dir="0 0 -1" directional="true"/>
    <geom name="floor" type="plane" size="{tile} {tile} 0.05" material="groundplane" friction="0.9 0.02 0.01"/>
{rails}  </worldbody>
</mujoco>
"""


def write_scene(
    path: Path,
    height: float,
    thickness_inner: float,
    thickness_outer: float | None = None,
    robot_xml: Path | None = None,
) -> Path:
    if thickness_outer is None:
        thickness_outer = thickness_inner
    path.write_text(
        rails_xml(height, thickness_inner, thickness_outer, robot_xml=robot_xml),
        encoding="utf-8",
    )
    return path
