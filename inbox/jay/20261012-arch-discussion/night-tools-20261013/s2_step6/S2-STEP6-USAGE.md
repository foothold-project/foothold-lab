# S2 B plumbing 참석 단회 입력 계약
> 분류: A/정책학습
> 작성: Codex Worker · 2026-10-15
> 근거: TASK-codex-worker-s2-B-plumbing.md · VERIFY-astra-17ac.md 6절 · step6 CPU 시험
> 요지: 0단계 미통과 상태에서 PPO iteration 1~2회 배관 확인을 격리해 수행한다.
> 상태: CPU 확인됨 · 실제 GPU/Isaac 미확인 · 승인 미발급

## manifest 요청

기존 `S2-STEP5-USAGE.md`의 최상위 및 `plan` 필드를 모두 명시한다. 추가 필수 최상위 필드:

- `plumbing_only: true`, `stage0_passed: false`
- `input_path: live_raycaster_unverified` 또는 `synthetic_known_answer`
- `plumbing_pair: {"pair_id": "<chain_id>", "ordinal": 1}`. 둘째 arm은 `ordinal: 2`, `previous_receipt_path`, `previous_receipt_sha256`를 함께 넣는다.

`plan.stage`는 `plumbing`, `plan.updates`는 PPO iteration 수 1 또는 2, `plan.checkpoint_interval`은 그와 같은 값이어야 한다. `plan.rollout_steps`는 환경 step 수로 따로 둔다. `max_wall_s`는 600 이하, GPU index는 0, 환경 수는 1,024, gap/stones는 각각 0.15, 부모는 원본 E1 `model_20000.pt` SHA `c8951b797dbe41570009e9de35589d56b7ea1d10092728af17761d46a2df47e8`다. `PLUMBING_ONLY_` 경로의 체크포인트를 부모로 지정하면 거절한다. 매 arm은 새 manifest, 승인, claim, 출력 폴더를 쓴다.

봉인 명령은 `python.exe -B s2_train_manifest.py --request request.json --manifest manifest.json`이다. 승인 JSON은 코드가 만들지 않는다. 승인 scope는 `s2_plumbing_attended_one_shot`이며 manifest SHA, EULA 동의, 담당자, 만료 시각을 별도로 담아야 한다. `UNDECIDED`는 거절한다. 승인과 참석 감독이 마련된 뒤에만 `s2_train_launch.py --manifest manifest.json --approval approval.json --prelaunch`, 이어 60초 내 같은 명령에서 `--prelaunch`를 뺀 단회 기동을 검토한다. 이 문서는 GPU 실행 동의가 아니다.

## 결과 해석과 순서

성공 영수증은 `executed_updates`와 `rollout_steps`, `environment_steps`를 별도로 적고 부모 SHA 전후, Job 가족 정리, 입력 경로, 손실·KL·entropy·gradient norm·NaN·가중치 변화·encoder freeze·학습률·checkpoint 재적재 출력을 담는다. 출력은 `PLUMBING_ONLY_checkpoint_*.pt`와 경고문 `PLUMBING_ONLY.txt`로 표시한다. 이 가중치를 A/B 성능, 지도 효과 또는 후속 학습 시작점에 쓰지 않는다.

둘째 arm은 첫 arm의 `RUN_COMPLETE_UNVERIFIED`, 가족 0과 handle 정리 확인, 원본 부모 SHA 불변, 고정된 영수증 해시, 같은 GPU UUID와 다른 출력 폴더를 확인한 뒤에만 시작한다. 동시 기동, 자동 재시도, 무인 기동, 200회 smoke와 short로의 자동 승격은 없다. `live_raycaster_unverified`의 성공은 배관 연결에만 한정된다. 실제 RayCaster와 Isaac 지형 신뢰성은 0단계 자료로 따로 판단한다.
