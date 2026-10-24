> 분류: 가이드
> 작성: sol · 2026-10-24
> 근거: 고정 `lead-tmp-start-b`의 `record_sol23f.py` SHA `662cd68906bd…`, `seq_video.py` SHA `270b7dbe…`, 이전 `s2_lab/record_seq.py`, B500 실제 `b_model500_flat_ready.json`
> 요지: 같은 촬영 계약을 유지한 별도 recorder에 몸통과 발의 원시 위치를 추가했다.
> 상태: CPU 검증 완료 · Kit 촬영 미실행
> 판: v1.0

# SOL-24g · B1000/EX23_1000 평지 촬영 계측 준비

`확인됨`: CPU 계측 시험과 원본 해시. `미확인`: 새 계측기의 실제 Kit 촬영. 준비 이유: [B500·EX29 200 기록](https://github.com/foothold-project/foothold-lab/issues/555#issuecomment-6378262843).

## 바뀐 것

고정 학습 코드와 고정 recorder는 읽기만 했다. 새 `foothold_s2/eval/record_sol24g.py`는 고정 `record_sol23f.py` 사본에 아래 필드만 더했다. `source_root`가 고정 코드 폴더의 절대 경로인지 확인하고, 원 recorder SHA가 다르면 시작 전에 거절한다. 정책과 환경 import는 그 고정 코드 폴더에서 해결한다. JSON의 `sources_sha256`은 고정 코드 목록이고, `measurement_recorder.path/sha256`은 이번 별도 사본이다. `seq_video.py`는 기존 고정본을 사용하며 세 파일의 단일 시도 검증과 SHA 영수증을 그대로 받는다.

| NPZ 필드 | tick 기준 · 뜻 |
|---|---|
| `root_pos_w` 600×3, `root_quat_w` 600×4 | 행동 직전 몸통 세계 위치, 쿼터니언 wxyz |
| `foot_pos_w` 600×4×3, `foot_contact` 600×4 | 같은 순간 발 중심 세계 위치와 1 N 접촉 판정. 발 순서는 `foot_names` |
| `body_height_foot_center_m` 600 | root z에서 접촉 발 중심 z 평균을 뺀 값. 무접촉이면 NaN. 지면 기준 실제 높이라고 부르지 않음 |
| `joint_pos`, `joint_names`, `policy_action` | 같은 순간 관절과 정책 출력. 실제 적용 관절 목표는 아님 |
| `joint_pos_target_last_substep`, `applied_torque_last_substep`, `joint_target_valid` | 비종료 tick의 마지막 물리 substep에서 읽은 목표와 토크. 종료 tick은 자동 reset 뒤 값과 섞이지 않도록 NaN/False |

두 편의 비교에는 `root_pos_w[:,2] * 100` cm와 `body_height_foot_center_m * 100` cm를 각각 제시한다. 전자는 평지 세계 좌표의 높이, 후자는 접촉 발 중심 상대치다. 초기 원점이 다르면 절대 높이 순위를 내지 않는다. 종료 tick의 자세·발 위치는 행동 직전 상태이며 `done`은 그 행동 뒤 판정이다. 따라서 종료 직전 높이를 찾으려면 `done`이 처음 True인 행을 보고, reset 뒤 첫 행을 같은 episode로 잇지 않는다. 기존 12초, 600 tick, 25 fps, 300 frame, 명령 4구간 각 3초, saved 지도, mean/mean, 고정 물리는 수정하지 않았다.

## CPU 확인

- `python -m pytest foothold_s2/eval/tests/test_record_sol24g.py foothold_s2/eval/tests/test_seq_video.py -q`: **15 passed**. 새 시험은 600행 NPZ 왕복, 알려진 높이 0.30 m, 종료 target 무효화, 무접촉 NaN, 한 행 결측·종료 마스크 변이 거절, saved force_gt=True 소비, 고정 원본 SHA, Kit 없는 plan-only를 확인했다. 기존 seq_video 시험도 포함한다.
- `ruff check --select F`와 `pyflakes` 두 새 파일 모두 0건. `py_compile` 통과. `CUDA_VISIBLE_DEVICES=-1`로 시험했다.
- Kit에서 실제 `ArticulationData` 필드와 MP4까지 통과하는지는 **미확인**. 첫 촬영의 JSON, NPZ와 `.done`을 반드시 되읽는다.

| 새 파일 | SHA-256 |
|---|---|
| `foothold_s2/eval/record_sol24g.py` | `12547e29e15e0c9b1c0eb05cf1d460218292249b0750ec00eb73cfc906147ca0` |
| `foothold_s2/eval/tests/test_record_sol24g.py` | `00ebd6bce8f79666ec5e27e03ba9c16e827013cae3c25d8e9a218a87c204ef2a` |

## 순차 실행 명령

두 명령은 **준비만 했다**. root가 기존 B500 기동의 conda `isaac311`, `PATH`, `OMNI_KIT_ACCEPT_EULA=YES`, `ISAACLAB_PATH`, `CUDA_DEVICE_ORDER=PCI_BUS_ID`, `CUDA_VISIBLE_DEVICES` unset 환경을 그대로 사용하고, cwd를 `C:/mai/wt/foothold-lab/lead-tmp-start-b`로 둔다. 출력 두 폴더는 새 빈 이름이다. B1000 체크포인트는 이 문서를 쓸 때 아직 없으므로 완료 SHA와 파일 존재를 먼저 확인한다. EX23_1000 파일은 읽기로 존재 확인했다. GPU 실행 승인이나 실행 결과를 이 문서가 대신하지 않는다.

```powershell
$py = 'C:/Users/AI-WS01/anaconda3/envs/isaac311/python.exe'
$fixed = 'C:/mai/wt/foothold-lab/lead-tmp-start-b'
$seq = "$fixed/foothold_s2/eval/seq_video.py"
$rec = 'C:/mai/wt/foothold-lab/sol-23a/foothold_s2/eval/record_sol24g.py'
$policy = '{"physics_mode":"fixed","seed":42,"z_mode":"mean","act_mode":"mean","map_mode":"saved","terrain":"flat","experiment":"B","source_root":"C:/mai/wt/foothold-lab/lead-tmp-start-b"}'
$b1000 = "$fixed/logs/rsl_rl/foothold_s2_23f_b/2026-10-24_06-52-56_ex28-b-main/model_1000.pt"
$ex23 = 'C:/Users/AI-WS01/orca/workspaces/foothold-lab/sonnet-code/logs/rsl_rl/foothold_s2_x23/2026-10-22_21-52-26_ex23-g1/model_1000.pt'
Set-Location -LiteralPath $fixed
& $py $seq 'C:/Users/AI-WS01/s2_lab/run_20261024/b_model1000_flat_height' review $policy $b1000 'B model_1000' flat cuda:1 --python $py --recorder $rec --max-attempts 1
& $py $seq 'C:/Users/AI-WS01/s2_lab/run_20261024/ex23_model1000_flat_height' review $policy $ex23 'EX-23 model_1000' flat cuda:1 --python $py --recorder $rec --max-attempts 1
```

각 명령은 앞 명령의 `.done` 검증 후 다음을 시작한다. 출력 `review.json`의 `measurement_recorder.sha256`, `sources_sha256`, `map_modes.effective_use_gt`, `map_modes.gt_use_count`, `step_contract.physics_steps`를 확인한다. `review_feet.npz`의 새 필드가 모두 600행인지와 `joint_target_valid == ~done`을 확인한다. `seq_video.py --verify-receipt <폴더>/review.done`으로 기존 영수증도 되읽는다. `saved` 지도는 checkpoint의 `force_gt`를 복원하므로 두 JSON에서 `saved_force_gt`와 실제 GT 소비를 각각 확인해야 비교가 성립한다.

## 이력

| 판 | 변경 |
|---|---|
| v1.0 | 고정 recorder를 별도 사본으로 둔 몸통·발·행동 계측과 CPU 계약 시험 |
