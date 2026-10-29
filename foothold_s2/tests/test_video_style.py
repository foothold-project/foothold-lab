"""W49: 촬영 화풍(조명 L4 · 채도 1.25 · 이름)이 한 곳(video_style.py)이고, 모든 기록기의 argparse 기본값이 그것이며, 승인 아닌 영수증은 합성 · 검증이 거절한다 (CPU 시험, Kit 없음)."""
import ast
import importlib.util
import json
from pathlib import Path

import pytest

EVAL = Path(__file__).resolve().parents[1] / "eval"
REPO_ROOT = Path(__file__).resolve().parents[2]
VS_PATH = EVAL / "video_style.py"
RUNNER_STYLE = Path("C:/mai/wt/foothold-lab/runner-26a/inbox/jay/20261023-experiments/runner-26a/record_25e_l4sat125_26m.py")


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


vs = _load(VS_PATH, "video_style_under_test")
RECORDERS = sorted(list(EVAL.glob("record_*.py")) + list((EVAL / "video25").glob("record_25e_x*.py")))    # 예외 없음: x28 · x30 도 같은 관문


def test_approved_values_are_the_confirmed_ones():
    A = vs.APPROVED_STYLE
    assert A == {"lighting_profile": "dome_plus_three_point", "dome_intensity": 0.05, "three_point_intensity": 100.0,
                 "three_point_angle_deg": 12.0, "three_point_elevation_deg": 45.0, "three_point_shadows": True, "overlay_saturation": 1.25}
    assert vs.STYLE_ID in vs.APPROVED_STYLE_IDS and vs.STYLE_ID.startswith("L4_sat125_")


@pytest.mark.skipif(not RUNNER_STYLE.is_file(), reason="runner-26a copy not on this machine")
def test_style_args_match_the_runner_source():
    ns = {}
    src = RUNNER_STYLE.read_text(encoding="utf-8")
    start = src.index("STYLE_ARGS = (")
    exec(src[start:src.index(")\n", start) + 2], ns)
    assert tuple(ns["STYLE_ARGS"]) == tuple(vs.STYLE_ARGS)


def test_naming_function_follows_the_rule_and_rejects_result_words():
    assert vs.video_name("EX28-B", "hard_boxes", 3, 57, 1500) == "EX28-B-hard_boxes_L3_env57-m1500-seq-1x"
    for bad in ("hard_boxes_fail", "map_success", "x_fell"):
        with pytest.raises(ValueError):
            vs.video_name("EX35-SB10", bad, 3, 5, 3000)


def _argparse_style():
    import argparse
    p = argparse.ArgumentParser()
    vs.add_style_args(p)
    return p


def test_unapproved_values_need_the_allow_flag_and_get_a_marked_id():
    p = _argparse_style()
    ok = vs.resolve_style(p.parse_args([]), p)
    assert ok["approved"] and ok["style_id"] == vs.STYLE_ID
    with pytest.raises(SystemExit):
        vs.resolve_style(p.parse_args(["--lighting-profile", "inherit"]), p)
    with pytest.raises(SystemExit):
        vs.resolve_style(p.parse_args(["--overlay-saturation", "1.0"]), p)
    allowed = vs.resolve_style(p.parse_args(["--lighting-profile", "inherit", "--allow-unapproved-style"]), p)
    assert not allowed["approved"] and allowed["style_id"].startswith("UNAPPROVED_")
    with pytest.raises(ValueError):
        vs.require_approved({"style": allowed})
    for missing in ({}, {"style": {}}, {"style": {"style_id": "L4_sat125_00000000"}}):
        with pytest.raises(ValueError):
            vs.require_approved(missing)
    assert vs.require_approved({"style": ok})["style_id"] == vs.STYLE_ID


def test_every_recorder_takes_its_style_defaults_from_video_style():
    """기록기마다: video_style 을 불러 add_style_args 와 resolve_style 을 부르고, 자기 argparse 에 조명 · 채도 인자를 따로(다른 기본값으로) 두지 않는다.
    새 기록기 사본(x32 등)이 생겨도 이 시험이 걸린다. 제외 목록 없음."""
    assert RECORDERS, "기록기를 못 찾았다"
    styled = []
    for path in RECORDERS:
        src = path.read_text(encoding="utf-8")
        if "--lighting-profile" in src or "video_style" in src or "AppLauncher" in src:
            tree = ast.parse(src)
            literals = {n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str)}
            assert "video_style" in src and "add_style_args" in src and "resolve_style" in src, f"{path.name}: video_style 을 쓰지 않는다"
            assert not ({"--lighting-profile", "--overlay-saturation", "--dome-intensity", "--three-point-intensity"} & literals), f"{path.name}: 조명 · 채도 인자를 따로 정의했다(기본값이 갈라진다)"
            styled.append(path.name)
    assert {"record_clip.py", "record_sol23f.py", "record_25e_x28.py", "record_25e_x30.py", "record_25e_x31.py"} <= set(styled)


@pytest.mark.parametrize("name", ["record_sol23f.py", "record_25e_x28.py", "record_25e_x30.py", "record_25e_x31.py"])
def test_real_argparse_defaults_are_the_approved_style(name):
    """parser 를 만드는 기록기는 실제 parser 로 기본값을 읽는다(Kit 은 main 안에서만 불러오는 구조)."""
    path = EVAL / name if name == "record_sol23f.py" else EVAL / "video25" / name
    mod = _load(path, "rec_" + name[:-3])
    parser = mod._argv_parser()
    args, _ = parser.parse_known_args(["--policy", "{}", "--checkpoint", "x.pt", "--label", "l", "--scene", "rough", "--mp4", "o.mp4"])
    style = vs.resolve_style(args, parser)
    assert style["approved"] and style["style_id"] == vs.STYLE_ID
    assert args.overlay_saturation == 1.25 and args.lighting_profile == "dome_plus_three_point" and args.three_point_shadows is True


def test_composer_and_seq_video_refuse_a_non_approved_receipt(tmp_path):
    comp = _load(EVAL / "video25" / "compose_25e_v2style9.py", "compose_v9_under_test")
    (tmp_path / "review.json").write_text(json.dumps({"label": "x", "style": {"style_id": "UNAPPROVED_deadbeef"}}), encoding="utf-8")
    with pytest.raises(ValueError, match="승인 화풍"):
        comp.render(tmp_path, "seq", "1x", tmp_path / "o.mp4")
    (tmp_path / "review.json").write_text(json.dumps({"label": "x"}), encoding="utf-8")    # 옛 영수증(style 없음)도 실패
    with pytest.raises(ValueError, match="승인 화풍"):
        comp.render(tmp_path, "seq", "1x", tmp_path / "o.mp4")
    seq = _load(EVAL / "seq_video.py", "seq_video_under_test")
    mp4 = tmp_path / "c.mp4"
    mp4.write_bytes(b"x")
    (tmp_path / "c_feet.npz").write_bytes(b"x")
    (tmp_path / "c.json").write_text(json.dumps({"label": "L", "scene": "rough", "checkpoint": str(tmp_path / "ck.pt"), "frames": 3}), encoding="utf-8")
    with pytest.raises(seq.CaptureError, match="style_not_approved"):
        seq.validate_attempt(mp4, checkpoint=tmp_path / "ck.pt", label="L", scene="rough", expected_frames=3, ffprobe="ffprobe", ffmpeg="ffmpeg")


def test_record_clip_real_parser_defaults_are_the_approved_style():
    """record_clip 은 import 만으로 Kit 을 띄우므로 모듈을 실행하지 않고 _argv_parser 함수 하나만 떼어 실제 parser 를 만든다."""
    import argparse
    src = (EVAL / "record_clip.py").read_text(encoding="utf-8")
    fn = next(n for n in ast.parse(src).body if isinstance(n, ast.FunctionDef) and n.name == "_argv_parser")
    ns = {"argparse": argparse, "video_style": vs}
    exec(compile(ast.Module(body=[fn], type_ignores=[]), "record_clip._argv_parser", "exec"), ns)
    parser = ns["_argv_parser"]()
    args = parser.parse_args(["--policy", "v2", "--checkpoint", "x.pt", "--label", "l", "--mp4", "o.mp4"])
    style = vs.resolve_style(args, parser)
    assert style["approved"] and style["style_id"] == vs.STYLE_ID
    with pytest.raises(SystemExit):
        vs.resolve_style(parser.parse_args(["--policy", "v2", "--checkpoint", "x.pt", "--label", "l", "--mp4", "o.mp4", "--overlay-saturation", "1.0"]), parser)


def test_name_rule_accepts_single_word_terrain_and_label_is_enforced():
    assert vs.video_name("ex36a", "stairs", 3, 12, 2000) == "ex36a-stairs_L3_env12-m2000-seq-1x"
    for kind in ("boxes", "gaps", "flat", "rough", "pyramid_stairs_inv", "sparse_beam"):
        assert vs.NAME_RE.match(vs.video_name("EX28-B", kind, 1, 2, 1500))
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--label")
    vs.add_style_args(p)
    vs.check_label(p.parse_args(["--label", "EX28-B-hard_boxes_L3_env57-m1500-seq-1x"]), p)
    for bad in ("my clip", "EX28-B-boxes_L3_env57-m1500-seq-1x-success", "comparison_1x"):
        with pytest.raises(SystemExit):
            vs.check_label(p.parse_args(["--label", bad]), p)
    vs.check_label(p.parse_args(["--label", "free text", "--allow-unapproved-style"]), p)


def test_forged_receipt_with_approved_id_but_other_values_is_refused():
    ok = vs.resolve_style(_argparse_style().parse_args([]))
    forged = dict(ok, values=dict(ok["values"], overlay_saturation=1.0))
    with pytest.raises(ValueError, match="values"):
        vs.require_approved({"style": forged})
    with pytest.raises(ValueError):
        vs.require_approved({"style_id": "L4_sat125_00000000"})
    assert vs.require_approved({"style_id": vs.STYLE_ID})["style_id"] == vs.STYLE_ID


def test_recorders_have_no_undefined_names():
    """x31 이 지운 함수를 맨 이름으로 불러 NameError 가 난 일(리뷰 405d6aa0)을 정적으로 막는다: 기록기 파일마다 pyflakes 의 undefined name 0."""
    pyflakes = pytest.importorskip("pyflakes.api")
    import io
    from pyflakes.reporter import Reporter
    bad = {}
    for path in RECORDERS + [VS_PATH, EVAL / "seq_video.py", EVAL / "video_combine_check.py", EVAL / "video25" / "compose_25e_v2style9.py"]:
        out, err = io.StringIO(), io.StringIO()
        pyflakes.check(path.read_text(encoding="utf-8"), str(path), Reporter(out, err))
        lines = [l for l in out.getvalue().splitlines() if "undefined name" in l]
        if lines:
            bad[path.name] = lines
    assert not bad, bad


def test_v8_composer_copy_and_frame_check_refuse_non_approved(tmp_path):
    v8 = REPO_ROOT / "inbox" / "jay" / "20261028-plan" / "compose_25e_v2style8.py"
    comp = _load(v8, "compose_v8_under_test")
    (tmp_path / "review.json").write_text(json.dumps({"label": "x", "style": {"style_id": "UNAPPROVED_deadbeef"}}), encoding="utf-8")
    with pytest.raises(ValueError, match="승인 화풍"):
        comp.render(tmp_path, "seq", "1x", tmp_path / "o.mp4")
    (tmp_path / "review.json").write_text(json.dumps({"label": "x"}), encoding="utf-8")    # x28 기본(옛 영수증, style 없음)도 실패
    with pytest.raises(ValueError, match="승인 화풍"):
        comp.render(tmp_path, "seq", "1x", tmp_path / "o.mp4")
    chk = _load(EVAL / "video_combine_check.py", "combine_check_under_test")
    mp4 = tmp_path / "a.mp4"
    mp4.write_bytes(b"x")
    with pytest.raises(SystemExit):                        # 영수증 없음
        chk.style_gate(str(mp4))
    (tmp_path / "a.json").write_text(json.dumps({"style": {"style_id": "UNAPPROVED_deadbeef"}}), encoding="utf-8")
    with pytest.raises(ValueError, match="승인 화풍"):
        chk.style_gate(str(mp4))
    ok = vs.resolve_style(_argparse_style().parse_args([]))
    (tmp_path / "a.json").write_text(json.dumps({"style": ok}), encoding="utf-8")
    assert chk.style_gate(str(mp4)) == {"style_gate": "approved"}
