# S2 B plumbing CPU 구현 보고
> 분류: A/정책학습
> 작성: Codex Worker · 2026-10-15
> 근거: TASK-codex-worker-s2-B-plumbing.md · VERIFY-astra-17ac.md 6절 · step6 시험 로그
> 요지: 0단계 PASS 전 별도 참석 단회 plumbing 계약과 CPU 배관 시험을 구현했다.
> 상태: CPU 확인됨 · GPU/Isaac 미실행 · 승인 JSON 미발급

## 변경과 경계

새 사본 `codexE/s2_step6/`에만 작성했다. 기존 `s2_step5/`, A3.2 0단계 감독기, `_eval`, slot, guard, 부모 코드, 저장소 공유 체크아웃 쓰기 0이다. 기존 smoke 200회·short 2,000회 계약을 유지하고 별도 `plumbing` scope `s2_plumbing_attended_one_shot`을 추가했다. 한 프로세스 한 arm이며 DDP, 자동 재시도, 무인, 후속 학습·short 승격은 없다.

핵심 수정 파일은 `s2_train_contract.py`, `s2_train_manifest.py`, `s2_train_entry_17v.py`, `s2_train_launch.py`, `s2_ppo_17v.py`다. 새 파일은 `s2_plumbing.py`, `s2_step6_audit.py`, `run_all_s2_step6.py`, `test_s2_step6_contract.py`, `test_s2_step6_execution.py`, `test_s2_step6_proof.py`, `test_s2_step6_mutants.py`, `S2-STEP6-USAGE.md`다. 복사한 `test_s2_step5_clean_import.py`는 런타임 의존 수 표기만 20으로 고쳤다.

`plumbing`은 PPO iteration 1 또는 2, 같은 값의 checkpoint interval, `max_wall_s<=600`, `plumbing_only:true`, `stage0_passed:false`, 명시한 `input_path`를 요구한다. 결과의 iteration, rollout_steps, environment_steps를 분리한다. 새 격리 출력에 `PLUMBING_ONLY_checkpoint_*.pt`와 재사용 금지 문구 및 manifest SHA를 담은 `PLUMBING_ONLY.txt`를 쓴다. E1 부모 SHA를 기동 전후 재고 영수증에 보존하며 달라지면 HOLD다. 200회 smoke와 short의 부모 경로에 `PLUMBING_ONLY_`가 들어가면 거절한다.

CPU 정답 tensor에서 광선 187개의 축·순서, 높이·mask, 유한 값을 확인한다. 학습 cfg에서 `disable_gravity=True`와 `base_contact=None`을 거절한다. 실제 PPO 경로는 forward, loss, backward, optimizer, save, 의도적 parameter 교란 뒤 load와 동일 입력 출력 복원을 거친다. 유한 loss·KL·entropy·학습률, 양의 유한 gradient norm, 가중치 SHA 변화, NaN 0, manifest의 encoder freeze 일정을 영수증에 기록한다. `live_raycaster_unverified` 입력의 성공 문구는 배관 연결로 제한한다.

두 arm의 순차 계약은 첫 arm의 `RUN_COMPLETE_UNVERIFIED`, 증명 경계, 가족 0과 handle 정리, 부모 SHA 전후 일치, 영수증 SHA, 같은 GPU UUID, 다른 출력 폴더를 확인한 뒤 둘째 manifest를 받는다. 첫 arm 완료 전 둘째 기동은 HOLD다. Job Object는 기존 소유 경계를 그대로 사용했고 실제 Windows CPU 자식의 자연 종료·가족 0·handle 정리를 확인했다. 실제 프로세스를 죽이지 않았다.

## 시험과 첫 실패

최종 증거 `s2_step6/evidence_s2_step6/r20261015_step6_final2/summary.json`: 정상 시험 12개 프로세스 exit 0, 기존 B 정상 **53 PASS**, 새 plumbing 정상 **42 PASS**, 정상 뒤 기존 변이 **7/7 CAUGHT**, 새 변이 **11/11 CAUGHT**. 각 변이는 지정 첫 FAIL과 want가 같았다. `CUDA_VISIBLE_DEVICES=-1`, `C:/Users/AI-WS01/anaconda3/envs/isaac311-moects/python.exe -B`를 사용했다. 실제 E1 부모를 CPU strict load하고 arm A 1회, arm B 2회 PPO iteration과 저장 후 재적재를 돌렸다. N=1,024 실제 Isaac 학습 실측은 아니다.

첫 실제 CPU 실행은 `copy.deepcopy(policy)`가 비-leaf tensor 때문에 실패하여 arm A 결과가 HOLD였다. 원본 체크포인트 자체는 바꾸지 않았다. 정책을 의도적으로 교란하고 같은 정책에 저장된 state를 적재하는 확인으로 수정한 뒤 새 전체 묶음이 통과했다. 원문과 수정은 `s2_step6/evidence_s2_step6/FIRST-FAILURES.md`에 남겼다.

새 변이 11개: updates 3 허용, plumbing 표시 제거, stage0 통과 허용, 부모 재측정 제거, plumbing checkpoint 부모 허용, 입력 경로 선언 제거, 진단 cfg 유입 허용, arm 동시 기동 허용, 가중치 변화 검사 제거, NaN 검사 제거, 환경 step과 iteration 영수증 혼용이다. 정상 입력·반례는 함수 경계에서 실행했고 변이 사본은 원본 밖의 임시 폴더에서 정적 첫 FAIL 감사로 확인했다. 변이 CAUGHT는 실제 GPU 동작 증명이 아니다.

## 미확인과 인계

실제 GPU 0 자원·lease, Kit 기동, N=1,024에서의 메모리·시간, 실제 RayCaster 입력, root/sensor 좌표, 지형 조우, Isaac 자식의 가족 정리는 미확인이다. 0단계 A3.2·4차 수집·A4 무인은 이 작업 범위 밖이며 0단계 PASS나 학습 승인을 주장하지 않는다. ASTRA 17ac가 요청한 별도 새 동의와 승인 JSON은 아직 없다. 팀장 결정값을 채우지 않았다.

사용 입력과 순서는 `S2-STEP6-USAGE.md`에 적었다. #550 댓글은 초안만 작성했고 게시하지 않았다. 파일별 SHA256은 `S2-STEP6-SHA256SUMS.txt`에 있다.
