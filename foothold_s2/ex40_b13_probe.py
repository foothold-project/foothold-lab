"""One full EX-40 evaluation path on a short Kit checkpoint, never a gate score."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from foothold_s2.eval.map_mode_cells import EX40_B3_COMMANDS, commands
from foothold_s2.ex40_eval_once import DEFAULT_CONFIG, DEFAULT_TABLE, MODES, evaluate
from foothold_s2.ex40_score import judge, sha256
from foothold_s2.ex40_stage_publish import _document, _draw_charts
from foothold_s2.ex40_stage_report import build as build_report


PHASES = {"map64", "stand_eval_gt", "stand_probe_prop_only", "stand_eval_pred",
          "map64_b3", "axis_v2"}
STAGE = "T0"  # Selects the superset of phases, never claims the short model reached T0.


def check_smoke_receipt(path: Path) -> Path:
    """Take the checkpoint only from B12's completed Kit checker."""
    row = json.loads(path.read_text(encoding="utf-8-sig"))
    launch = json.loads((path.parent / "launch_receipt.json").read_text(encoding="utf-8-sig"))
    checkpoint = Path(row.get("checkpoint", "")).resolve()
    if (row.get("state") != "PASS" or row.get("run_dir") != str(checkpoint.parent)
            or launch.get("arm") != "B" or launch.get("start") != "scratch"
            or launch.get("stage_boundaries") != {"B0": 0, "B1": 2, "B2": 4,
                "B3a": 6, "B3b": 8, "B3c": 10, "D": 12, "T0": 14}
            or row.get("checkpoint_sha256") != check_checkpoint(checkpoint)
            or row.get("stages") != [["B0", 0], ["B1", 2], ["B2", 4], ["B3a", 6],
                ["B3b", 8], ["B3c", 10], ["D", 12], ["T0", 14]]):
        raise ValueError("B13 requires the passed B12 18-update Kit receipt")
    return checkpoint


def check_checkpoint(checkpoint: Path) -> str:
    if checkpoint.name != "model_17.pt" or not checkpoint.is_file():
        raise ValueError("B13 probe requires the completed B12 model_17.pt")
    manifest = json.loads((checkpoint.parent / "manifest.json").read_text(encoding="utf-8-sig"))
    digest = sha256(checkpoint)
    if (manifest.get("schema") != "foothold-manifest/1"
            or manifest.get("checkpoints", {}).get(checkpoint.name) != digest
            or manifest.get("progress", {}).get("completed_updates", 0) < 18):
        raise ValueError("B12 checkpoint is not an 18-update manifest-pinned save")
    return digest


def check_evidence(checkpoint: Path, out: Path, digest: str,
                   config: Path, table: Path) -> dict:
    receipt = json.loads((out / "eval_receipt.json").read_text(encoding="utf-8-sig"))
    if (receipt.get("state") != "done" or receipt.get("smoke") is not False
            or receipt.get("checkpoint_sha256") != digest
            or receipt.get("checkpoint") != str(checkpoint)
            or receipt.get("stage") != STAGE or receipt.get("arm") != "B"
            or receipt.get("device") != "cuda:1"
            or receipt.get("score_config_sha256") != sha256(config)
            or receipt.get("table_sha256") != sha256(table)
            or set(receipt.get("steps", {})) != PHASES
            or any(item.get("rc") != 0 or item.get("output_path") != str(out / name)
                   for name, item in receipt["steps"].items())):
        raise ValueError("B13 full Kit phase receipt incomplete or mismatched")
    map_row = json.loads((out / "map64/map_modes.json").read_text(encoding="utf-8-sig"))
    b3_row = json.loads((out / "map64_b3/map_modes.json").read_text(encoding="utf-8-sig"))
    expected_b3 = {"walk+0.5", "walk-0.5"} | set(EX40_B3_COMMANDS)
    if (map_row.get("checkpoint_sha256") != digest
            or map_row.get("envs") != 64
            or set(map_row.get("modes", {})) != set(MODES)
            or any(set(map_row["modes"][mode]) != set(commands("extended")) for mode in MODES)
            or b3_row.get("checkpoint_sha256") != digest
            or b3_row.get("envs") != 64
            or set(b3_row.get("modes", {})) != set(MODES)
            or any(set(b3_row["modes"][mode]) != expected_b3 for mode in MODES)):
        raise ValueError("B13 map modes or 13-command/B3 coverage incomplete")
    for mode in MODES:
        stand = json.loads((out / f"stand_{mode}/stand.json").read_text(encoding="utf-8-sig"))
        if (stand.get("checkpoint_sha256") != digest or stand.get("mode") != mode
                or stand.get("envs") != 64 or len(stand.get("per_env", [])) != 64):
            raise ValueError(f"B13 stand {mode} incomplete")
    axis = json.loads((out / "axis_v2/axis_v2.json").read_text(encoding="utf-8-sig"))
    if (axis.get("checkpoint_sha256") != digest or axis.get("envs") != 64
            or set(axis.get("modes", {})) != set(MODES)):
        raise ValueError("B13 axis coverage incomplete")
    return receipt


def finalize(checkpoint: Path, out: Path, config: Path, table: Path,
             kit_check: Path | None = None) -> dict:
    digest = check_checkpoint(checkpoint)
    receipt = check_evidence(checkpoint, out, digest, config, table)
    score, _ = judge(checkpoint, STAGE, out, config, table, "B")
    if score["verdict"] == "HOLD":
        raise ValueError("B13 functional score HOLD: " + json.dumps(score["problems"], ensure_ascii=False))
    report = build_report(score, None, checkpoint.parent)
    report["functional_only"] = True
    report["gate_eligible"] = False
    report["actual_training_stage"] = "T0 short Kit schedule at smoke update 14"
    report["evaluation_stage_selector"] = STAGE
    report_root = out / "stage_reports"
    report_root.mkdir(exist_ok=True)
    report_json = report_root / "functional_T0_selector_m17.json"
    report_json.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
                           encoding="utf-8")
    charts = _draw_charts([report], report_root, "FUNCTIONAL-EX40-B13-m17")
    doc = report_root / "FUNCTIONAL-EX40-B13-m17.md"
    generated = _document(report, charts)
    generated = generated.replace("# EX-40 T0 m17 단계 끝 비교",
                                  "# EX-40 B13 짧은 저장본 전체 경로 기능시험", 1)
    generated = generated.replace("\n> 상태: 자동 생성 · 반복 폭 제한",
                                  "\n> 상태: 기능시험 · 본학습 T0 판정 아님 · 외부 발행 없음", 1)
    generated = generated.replace("\n앞 단계:",
                                  "\n이 저장본은 18회 Kit 확인의 m17이다. T0 인자는 전체 평가 단계를 선택하는 데만 썼다. "
                                  "실제 T0 단계 완료, m8000 판정, 승급, 성능 결론으로 쓰지 않는다.\n"
                                  "\n앞 단계:", 1)
    doc.write_text(generated, encoding="utf-8")
    result = {"format": "foothold-ex40-b13-functional/1", "state": "PASS",
              "functional_only": True, "gate_eligible": False, "published": False,
              "checkpoint": str(checkpoint), "checkpoint_sha256": digest,
              "b12_kit_check": str(kit_check) if kit_check else None,
              "source_git_head": receipt["source_git_head"], "eval_receipt": str(out / "eval_receipt.json"),
              "score_verdict_diagnostic_only": score["verdict"],
              "score": str(out / "score.functional.json"), "report": str(doc),
              "report_json": str(report_json),
              "charts": [{"path": str(path), "sha256": sha256(path)} for path in charts],
              "eval_seconds": receipt["elapsed_seconds"],
              "caution": "m17 is not a D74 stage-end checkpoint; no score ledger, Git push or Telegram"}
    (out / "score.functional.json").write_text(
        json.dumps(score, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    (out / "functional_receipt.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kit-check", type=Path, required=True,
                        help="B12 ex40_kit_smoke PASS JSON containing model_17 path")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--table", type=Path, default=DEFAULT_TABLE)
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args(argv)
    kit_check, out = args.kit_check.resolve(), args.out.resolve()
    checkpoint = check_smoke_receipt(kit_check)
    if not args.verify_only:
        if out.exists():
            parser.error("Kit output directory already exists")
        receipt = evaluate(checkpoint, out, stage=STAGE, arm="B",
                           config_path=args.config.resolve(), table_path=args.table.resolve(),
                           device="cuda:1", smoke=False)
        if receipt["state"] != "done":
            print(json.dumps(receipt, ensure_ascii=False))
            return 5
    result = finalize(checkpoint, out, args.config.resolve(), args.table.resolve(), kit_check)
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
