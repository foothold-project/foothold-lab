"""Known-input checks for the local status refresher."""

import importlib.util
from datetime import datetime, timedelta, timezone
from pathlib import Path


SCRIPT = Path(__file__).with_name("refresh_lab_status.py")
SPEC = importlib.util.spec_from_file_location("refresh_lab_status", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def test_gpu_rows_reject_incomplete_sample():
    rows = MODULE.gpu_rows("0, GPU-a, 123, 456, 0\n1, GPU-b, 789, 101, 5\n")
    assert rows[0]["free"] == "456"
    try:
        MODULE.gpu_rows("0, GPU-a, 123, 456, 0\n")
    except ValueError:
        pass
    else:
        raise AssertionError("missing GPU1 accepted")


def test_render_updates_only_current_snapshot():
    source = (
        "마지막 원자료 대조 <b>OLD</b>\n"
        "팀장이 정할 것 · OLD</h2>\n"
        "<div class=\"row\"><div class=\"k\">GPU0</div><div>old0</div></div>\n"
        "<div class=\"row\"><div class=\"k\">GPU1</div><div>old1</div></div>\n"
        "<p>과거 결과 기록은 보존</p>"
    )
    now = datetime(2026, 10, 27, 6, 32, tzinfo=timezone(timedelta(hours=9)))
    gpus = MODULE.gpu_rows("0, GPU-a, 0, 15979, 0\n1, GPU-b, 3964, 12016, 0\n")
    source += "<p>긴 대시\u2014두 개\u2014제거</p>"
    output = MODULE.render(source, now, gpus, [], 8)
    assert "2026-10-27 06:32 KST" in output
    assert "06:32 KST" in output
    assert "여유 12016 MiB" in output
    assert "실행 중인 학습·평가 후보 없음" in output
    assert "STOP 6행" in output and "RESULT v1.5" in output
    assert output.count("팀장 결정 대기 여덟 건") == 2
    assert "팀장 결정 대기 3건" not in output
    assert "과거 결과 기록은 보존" in output
    assert "old0" not in output and "old1" not in output
    assert "\u2014" not in output and "긴 대시 · 두 개 · 제거" in output
    assert "PID 123" in MODULE.render(source, now, gpus, [123], 8)


def test_atomic_write_replaces_page(tmp_path):
    page = tmp_path / "index.html"
    page.write_text("old", encoding="utf-8")
    MODULE.write_atomic(page, "new")
    assert page.read_text(encoding="utf-8") == "new"
    assert not page.with_name(page.name + ".refresh.tmp").exists()
