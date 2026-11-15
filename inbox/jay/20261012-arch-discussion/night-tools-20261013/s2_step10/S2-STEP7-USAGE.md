# S2 B step7 배관 사용 경계

> 분류: A/정책학습 · 실행 계약
> 작성: Codex Worker · 2026-10-15
> 근거: TASK-codex-worker-s2-B-fix17ad.md · VERIFY-astra-17ad.md · step7 CPU 시험
> 요지: 참석 GPU 0 단회를 봉인하기 전에 필요한 입력과 HOLD 경계를 기록한다.
> 상태: CPU 확인됨 · GPU·Isaac 실제 기동 미확인 · 팀장 단회 동의와 ASTRA 검토 전

`s2_train_manifest.py`가 명시 입력 request를 봉인한다. 승인 파일은 이 사본에 없다. `s2_train_launch.py`는 승인 digest, 기한, 단회 claim, GPU 0 UUID와 bus, 자원 한계, Job 소유, USD 잠금, 변환 격리, STOP, 가족 정리를 검사한다. 기존 slot과 guard의 설정은 바꾸지 않았다.

배관 plan은 `stage=plumbing`, `updates=1` 또는 `2`, `checkpoint_interval=updates`, `max_wall_s<=600`, `plumbing_only=true`, `stage0_passed=false`, arm A 또는 B, `input_path` 하나를 요구한다. N은 2에서 1,024 사이로 입력에서 고정한다. 예를 들어 N=32를 선택할 수 있지만 작은 N은 1,024 환경의 VRAM 수용, 처리량, 조우 범위, 장기 안정성 또는 학습 효과를 증명하지 않는다. rollout 표본 수는 minibatch로 나누어떨어져야 한다. barrier, resume, 증분, 200회, 2,000회, GPU 1 병렬은 배관 범위에서 거절한다.

부모는 SHA256 `c8951b797dbe41570009e9de35589d56b7ea1d10092728af17761d46a2df47e8`의 E1 내용만 허용한다. 파일 이름을 바꾼 배관 checkpoint는 허용되지 않는다. 배관 checkpoint 안에는 manifest SHA, 원본 부모 SHA, 재사용 금지 표지가 들어가며 환경 복원은 지원하지 않는다.

실행기는 번들 안의 `usd_isolate_run_v3.py`를 해시 `30dc2ea930f400948474b11c648aa389ff495d2a1bd764b4b9b984b931d11efb`로 고정한다. 실행별 `out_root/usd`에 `FOOTHOLD_USD_ROOT`를 설정하고 Go2 URDF 변환 기대 수를 1로 고정한다. 자식 결과에는 실제 USD 참조 경로가 있어야 한다. 감독기는 `isolate_state.json`, `assigned.jsonl`, 생성 파일, 참조 경로가 하나로 일치해야 완료를 인정한다. 현재 이 실기 경로는 미확인이다.

`live_raycaster_unverified`는 기존 packet과 map 유효성 검사를 유지한다. `synthetic_known_answer`는 Isaac 관측과 PPO는 실제로 거치고 S2 지도 어댑터의 RayCaster 데이터 소비 자리에서 알려진 광선으로 치환한다. 실제 PPO 지도 입력의 해시를 정답 tensor와 대조한다. 기본 Isaac 관측과 critic은 센서를 사용할 수 있으므로 합성 경로 전체가 실센서와 무관하다고 주장하지 않는다. CPU의 FakeS2Env 결과는 live 참석 영수증에서 HOLD된다. 두 입력 모두 `stage0_passed=false`, `performance_verified=false`다. 조우는 미계측이다.

두 번째 arm은 첫 영수증의 `RUN_COMPLETE_UNVERIFIED`, `plumbing_checks=PASS`, 가족 0, 정리 확인, 서로 다른 출력, 사람의 검토, 팀장이 해당 두 번째 단회에 직접 낸 별도 동의 파일을 요구한다. 동의 파일의 `by=오흥재`, `scope=s2_plumbing_second_arm_one_shot`, `chain_id`, `arm`과 파일 SHA를 봉인한다. 첫 arm의 HOLD 뒤에는 다음 arm 또는 같은 manifest 자동 재시도가 없다.

감독기 `RUN_COMPLETE_UNVERIFIED`는 자식 종료 0, 가족 0, 필요 파일의 존재·크기·해시와 별도 증거 관문 통과를 뜻한다. 일반 smoke 시험의 가짜 checkpoint도 이 기본 영수증을 만들 수 있으므로 저장물 load 증명으로 쓰지 않는다. 배관에서만 checkpoint 내용, 새 policy strict load, 동일 입력 action/value, optimizer/control, 그룹별 경로, live 입력·장치·cfg·USD를 추가 검사한다. 실제 첫 단회가 끝나도 stage0나 성능 통과로 승격하지 않는다.
