"""ex42_eval_once refuses --next-stage-launcher on an EMA export folder (lead 2026-11-22 09:36, planner): the folder is scored, never
handed off. Same argv on an ordinary run folder does not hit this refusal. CPU only, no Kit."""
from __future__ import annotations

import json

import pytest

from foothold_s2 import ex42_eval_once as eo


def _argv(tmp_path, folder):
    launcher = tmp_path / "launcher.sh"; launcher.write_text("#!/bin/sh\n")
    for name in ("plan.yaml", "approvals.json"):
        (tmp_path / name).write_text("{}")
    return ["--checkpoint", str(folder / "model_250.pt"), "--sha-from-manifest", "--out", str(tmp_path / "out"),
            "--p1-plan", str(tmp_path / "plan.yaml"), "--p1-approvals", str(tmp_path / "approvals.json"), "--p1-stage-id", "E2",
            "--mesh-dir", str(tmp_path), "--expected-mesh-sha256", "0" * 64, "--eval-seed", "42",
            "--next-stage-launcher", str(launcher), "--device", "cuda:0", "--execute"]


def _folder(tmp_path, name, manifest):
    d = tmp_path / name; d.mkdir()
    (d / "model_250.pt").write_bytes(b"x")
    if manifest is not None:
        (d / "manifest.json").write_text(manifest if isinstance(manifest, str) else json.dumps(manifest))
    return d


def test_export_folder_refuses_the_launcher(tmp_path, capsys):
    d = _folder(tmp_path, "ema", {"checkpoints": {}, "ema_export": {"format": "foothold-ema-export/1"}})
    with pytest.raises(SystemExit) as exc:
        eo.main(_argv(tmp_path, d))
    assert exc.value.code == 2 and "EMA export" in capsys.readouterr().err


def test_unreadable_manifest_refuses_too(tmp_path, capsys):
    d = _folder(tmp_path, "broken", "{not json")
    with pytest.raises(SystemExit):
        eo.main(_argv(tmp_path, d))
    assert "EMA export" in capsys.readouterr().err


@pytest.mark.parametrize("manifest", [{"checkpoints": {}}, None])
def test_ordinary_folder_does_not_hit_the_refusal(tmp_path, capsys, manifest):
    d = _folder(tmp_path, "run", manifest)
    try:
        eo.main(_argv(tmp_path, d))
    except (SystemExit, Exception):
        pass                                                                           # later checks fail on the fake files; only the refusal matters
    err = capsys.readouterr().err
    assert "EMA export" not in err and "arguments are required" not in err                # the argv is complete: it got past the parser
    assert not eo.exported_ema_folder(d / "model_250.pt")
