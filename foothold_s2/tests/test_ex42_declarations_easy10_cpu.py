"""1118 쉬운 사다리 선언: 낮은 열 하나만 1111 선언과 다르고, 선언 검사를 통과한다."""
import json
from pathlib import Path

from foothold_s2.tools.ex42_execution_manifest import declaration_errors

EV = Path(__file__).resolve().parents[2] / 'inbox/jay/20261111-analysis/evidence'


def _load(name):
    return json.loads((EV / name).read_text())


def test_only_low_stones_training_row_changed():
    old, new = _load('ex42-declarations-1111.json'), _load('ex42-declarations-1118-easy10.json')
    assert old.keys() == new.keys()
    diff = [(f, k) for f in old for k in old[f] if old[f][k] != new[f][k]]
    assert diff == [('A', 'stepping_stones_low')]
    o, n = old['A']['stepping_stones_low'], new['A']['stepping_stones_low']
    for key in ('original_dimensions_m', 'evaluation_dimensions_m', 'preset_id', 'physical_flag'):
        assert o[key] == n[key]
    assert n['training_dimensions_m'] == {'stone_x_m': 0.4063, 'stone_y_m': 0.3245,
                                          'gap_x_m': 0.2308, 'gap_y_m': 0.118, 'stone_height_m': 0.05}


def test_new_declaration_passes_checks_and_old_one_would_not_with_new_values():
    new = _load('ex42-declarations-1118-easy10.json')['A']['stepping_stones_low']
    assert declaration_errors(new) == []
    stale = json.loads(json.dumps(new))
    stale['evaluation_axis_directions'] = _load('ex42-declarations-1111.json')['A']['stepping_stones_low']['evaluation_axis_directions']
    assert declaration_errors(stale)
