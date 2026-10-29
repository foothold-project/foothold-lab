"""D51: map64 배치 촬영은 selected_environment.level 이 자리표시(0)다. 계기판 지형 칸 레벨은 실제 칸(selected_tile)에서 읽어야 한다."""
import importlib.util
from pathlib import Path

COMPOSER = Path(__file__).resolve().parents[1] / "eval/video25/compose_25e_v2style10.py"


def _composer():
    spec = importlib.util.spec_from_file_location("compose_v10_under_test", COMPOSER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_map64_capture_shows_the_tile_level_not_the_placeholder():
    meta = {"selected_environment": {"env_id": 23, "kind": "pyramid_stairs", "level": 0, "col": 0},
            "task_selection": {"selected_tile": {"env": 23, "kind": "pyramid_stairs", "level": 1, "col": 0}}}
    assert _composer().terrain_text(meta) == ("pyramid_stairs", "L1")


def test_capture_without_selected_tile_keeps_the_receipt_level():
    meta = {"selected_environment": {"env_id": 5, "kind": "boxes", "level": 3, "col": 2}}
    assert _composer().terrain_text(meta) == ("boxes", "L3")
