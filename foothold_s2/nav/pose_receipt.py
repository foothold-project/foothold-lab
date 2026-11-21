"""하위 자세 영수증 쓰기 (lead 11/21 21:35 (2)): 상위 5 차원 (HIPAN_POSE_ACTIONS=1) 이 받는 하위 저장본을 「자세 단계를 통과했다」 고 적는다.
lower_adapter.pose_active_from_receipt 가 읽는 꼴 {stage_id, checkpoint_sha256, passed} + 근거 (판정 파일 경로 · sha · 결정 줄). 판정은 이 도구가 하지 않는다:
lead 가 rx2pz 졸업 숫자 (중앙 오차 2 cm · 기울기 0.8 · roll 0.1 rad · 지킬 칸) 를 확인한 뒤 --passed 로 부른다. CPU only.
    python -m foothold_s2.nav.pose_receipt --checkpoint <model_N.pt> --evidence <판정 파일> --decision "<원장 줄 요지>" --passed --out <receipt.json>
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from foothold_s2.nav.lower_adapter import POSE_STAGES, file_sha256


def write(checkpoint, evidence, decision: str, out, stage: str = "E6a", passed: bool = False) -> dict:
    if stage not in POSE_STAGES:
        raise ValueError(f"stage must be one of {POSE_STAGES}")
    if not passed:
        raise ValueError("a receipt is written only for a passed posture stage (--passed)")
    ev = Path(evidence)
    if not ev.is_file() or not decision.strip():
        raise ValueError("a receipt needs an evidence file and a decision line")
    out = Path(out)
    if out.exists():
        raise FileExistsError(out)
    rec = {"format": "foothold-hipan-pose-receipt/1", "stage_id": stage, "checkpoint": str(Path(checkpoint).resolve()),
           "checkpoint_sha256": file_sha256(checkpoint), "passed": True, "evidence": str(ev.resolve()),
           "evidence_sha256": hashlib.sha256(ev.read_bytes()).hexdigest(), "decision": decision}
    out.write_text(json.dumps(rec, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return rec


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--checkpoint", required=True); p.add_argument("--evidence", required=True); p.add_argument("--decision", required=True)
    p.add_argument("--stage", default="E6a"); p.add_argument("--passed", action="store_true"); p.add_argument("--out", required=True)
    a = p.parse_args(argv)
    print(json.dumps(write(a.checkpoint, a.evidence, a.decision, a.out, a.stage, a.passed), ensure_ascii=False))


if __name__ == "__main__":
    main()
