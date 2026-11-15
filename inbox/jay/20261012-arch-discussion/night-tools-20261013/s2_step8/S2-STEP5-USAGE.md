# S2 B 참석 기동 입력 계약
> 분류: A/정책학습
> 작성: Codex Worker · 2026-10-15
> 근거: TASK-codex-worker-s2-B-live.md · step5 코드 · CPU 시험
> 요지: 팀장이 결정한 요청과 승인 JSON을 분리하여 단회 참석 기동한다.
> 상태: CPU 확인됨 · GPU/Isaac 미확인

## 순서

1. 팀장이 `request.json`에 모든 선택값과 자원 한도를 채운다. `UNDECIDED`는 seal과 prelaunch에서 거절한다. 팀장 결정값을 이 묶음에 미리 넣지 않았다.
2. `python.exe -B s2_train_manifest.py --request request.json --manifest manifest.json`으로 코드, E1 부모, Python, agent YAML, 센서 hook 해시와 정확한 argv를 봉인한다. 출력 manifest 경로는 새 파일이어야 한다.
3. 팀장이 별도 `approval.json`을 만든다. 필수 필드: `status: APPROVED`, `scope: s2_one_arm_training_attended`, `chain_id`, `by`, `approval_id`, `eula_accepted: true`, `expires_epoch`, `manifest_sha256`. 마지막 해시는 `manifest.json` 파일의 SHA256이다. 승인 파일은 이 코드가 작성하지 않는다.
4. `python.exe -B s2_train_launch.py --manifest manifest.json --approval approval.json --prelaunch`로 GO 보고서를 만든다. 이는 CPU 정적 확인과 승인된 장치 자원 조회 및 lease 확인을 한다. CPU 시험에서는 meter와 lease를 가짜로 주입했고 실제 GPU 조회는 하지 않았다.
5. GO 뒤 60초 이내에 같은 인자로 `--prelaunch` 없이 참석 감독기를 실행한다. 원래 승인 argv를 자식에게 전달하며, Job Object 가족, EULA 환경 변수, NUL stdin, 로그, heartbeat, STOP, 마감, claim, 영수증을 묶는다. 두 번째 실행은 거절한다.

## 요청 JSON 필드

최상위 필수: `chain_id`, `gpu_index`, `gpu_uuid`, `gpu_bus_id`, `max_wall_s`, `min_free_vram_bytes`, `running_floor_vram_bytes`, `min_free_disk_bytes`, `max_disk_bytes`, `deadline_epoch`, `approval_path`, `prelaunch_report_path`, `status_path`, `log_path`, `claim_root`, `gpu_lease_root`, `usd_lock_path`, `plan`.

`plan` 필수: `stage`, `parent`, `agent_yaml`, `sensor_hook_path`, `out_root`, `stop_file`, `arm`, `encoder_mode`, `schedule`, `seed`, `num_envs`, `updates`, `rollout_steps`, `epochs`, `minibatches`, `checkpoint_interval`, `map_init_seed`, `gap_proportion`, `stones_proportion`, `step_height_m`, `step_width_m`, `geometry_tolerance_m`, `deadline_epoch`, `lr`, `clip_param`, `gamma`, `lam`, `value_loss_coef`, `entropy_coef`, `max_grad_norm`, `desired_kl`, `use_clipped_value_loss`.

`stage=short`에는 `barrier_contract`가 더 필요하다. 그 JSON은 같은 `chain_id`, `arm`, `approval_id`, `stop_file`, `deadline_epoch`, `initial_short_updates=2000`, `max_total_updates>=2500`, `allowed_increments=[500]`을 담는다. 두 arm의 grant와 pair commit은 기존 `s2_increment_barrier.py` 계약을 따라 별도로 제출한다. E1 부모 SHA는 `c8951b797dbe41570009e9de35589d56b7ea1d10092728af17761d46a2df47e8`로 고정된다. `gpu_index=0`, `num_envs=1024`, gap/stones `.15`씩, smoke 200회, short 2,000회와 +500 증분이 검사된다.

## 판정 범위

`RUN_COMPLETE_UNVERIFIED`는 자식 종료, 영수증, 지정 경계 체크포인트가 맞았다는 뜻이다. 센서 유효성, 실제 지형 조우, GPU 성능, 단계 합격은 별도 독립 증거가 필요하다. 무인 A4 r2 gate는 0단계 scope이므로 이 문서의 학습 기동에 연결하지 않는다.
