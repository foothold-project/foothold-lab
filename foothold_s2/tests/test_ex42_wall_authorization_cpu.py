"""12:02 wall decision: expose through the existing K ladder, not all at entry."""
from pathlib import Path
import yaml
from foothold_s2.terrains import hipan_posture as posture


def test_wall_enters_existing_e6b_ladder_with_confirmed_geometry():
    root = Path(__file__).resolve().parents[1]
    doc = yaml.safe_load((root / 'curriculum/ex42-prep.yaml').read_text())
    terrain = next(r for r in doc['stages'] if r['id'] == 'E6b')['terrain']
    assert terrain['k_ladder']['order'] == [
        {'family': 'D', 'kind': 'crawl', 'level_cap': 0},
        {'family': 'D', 'kind': 'wall', 'level_cap': 0},
    ]
    # decisions 7121e018:420 confirms these project estimates; not HiPAN numbers.
    tile = posture.build_tile('wall', 0, seed=42, wall_height_m=posture.WALL_HEIGHT_M,
                              corridor_width_m=posture.CORRIDOR_WIDTH_M)
    assert tile.dimensions['wall_height_m'] == 1.20
    assert tile.dimensions['corridor_width_m'] == 0.80
    assert not any(r.get('kind') == 'wall' for r in terrain['exposure_at_E6b']['positive'])


def test_wall_needs_preceding_performance_and_then_gets_five_percent():
    from foothold_s2.terrains.ex42_k_ladder import ladder_terrain
    root = Path(__file__).resolve().parents[1]
    doc = yaml.safe_load((root / 'curriculum/ex42-prep.yaml').read_text())
    terrain = next(r for r in doc['stages'] if r['id'] == 'E6b')['terrain']
    unchanged, moves = ladder_terrain(terrain, 'E6b', 8, outcomes=[])
    assert not moves
    assert not any(r.get('kind') == 'wall' for r in unchanged['exposure_at_E6b']['positive'])
    outcomes = [{'D/high_ledge': {'first_window_pass': True}},
                {'D/high_ledge': {'target_level_reached': True}}, {},
                {'D/crawl': {'first_window_pass': True}},
                {'D/crawl': {'target_level_reached': True}}, {}]
    applied, moves = ladder_terrain(terrain, 'E6b', 6, outcomes=outcomes)
    wall = next(r for r in applied['exposure_at_E6b']['positive'] if r.get('kind') == 'wall')
    assert wall == {'family': 'D', 'kind': 'wall', 'share': .05, 'level_cap': 0}
    assert moves[-1]['kind'] == 'D/wall'
    assert moves[-1]['because'] == 'previous_kind_passed'
