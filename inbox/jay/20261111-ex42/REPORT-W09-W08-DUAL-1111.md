# W09/W08 두 장치 분할 실행

> 분류: 평가
> 작성: 오흥재 (scripter-lx 반영) · 2026-11-11
> 근거: lead-lx 17:06 지시 · #688 W09/W08 단일 장치 실행기
> 요지: W09와 W08 앞 두 번은 cuda:0, W08 뒤 세 번은 cuda:1에서 동시 실행하고 기존 순서로 한 영수증에 합친다.
> 상태: CPU 확인됨 · Kit 미실행

`--devices cuda:0,cuda:1`에서 두 작업군이 동시에 시작한다. 장치 안에서는 자식 두 칸을 순차 실행하고 각 회차도 원래 순서로 진행한다. `round_receipt.json` 여섯 개의 경로·SHA·시드·장치를 `chain_receipt.json`에 모으며 하나라도 실패하면 최종 상태 HOLD다. 기존 `--device` 단일 실행은 유지한다. 계획 모드에서는 GPU를 조회하거나 출력 폴더를 만들지 않는다.

runner 호출 한 줄 (E1 m1000 P1 PASS 뒤, 변수는 그 저장본과 영수증에서 고정):

```bash
cd "$FIXED_REPO" && "$ISAAC311_PYTHON" -m foothold_s2.scripts.ex42_flag_baseline_chain --checkpoint "$E1_RUN/model_1000.pt" --expected-checkpoint-sha256 "$E1_MODEL_SHA" --e1-gate "$E1_RUN/eval/scores/m1000/p1_score.json" --plan "$E1_EVAL_PLAN" --mesh-dir "$E1_EVAL_MESH_DIR" --expected-mesh-sha256 "$E1_EVAL_MESH_SHA" --devices cuda:0,cuda:1 --out "$E1_RUN/eval/w09-w08-$SOURCE_HEAD" --execute
```

isaac311 CPU `test_ex42_flag_baseline_chain_cpu.py`: 두 스레드 동시 시작, GPU0 0·1·2 및 GPU1 3·4·5 순서, 시드 42·42·42·43·44·45, 두 장치 이름 역순 거절, 기존 단일 실행과 실패 영수증을 확인했다. GPU/Kit은 실행하지 않았다.
