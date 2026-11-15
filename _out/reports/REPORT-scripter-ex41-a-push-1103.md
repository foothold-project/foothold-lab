# EX-41 A층 밀기 영상 준비와 model_10 지도 모드 셋 확인
> 분류: A/평가 · 일반화 벤치마크 · 지표
> 작성: 오흥재 (scripter 반영) · 2026-11-03
> 근거: 팀장 11/03 13:0x 지시 · eval_dr_mode.py · model_10 실제 Kit 기록
> 요지: DR 켬 밀기와 회복 원자료를 A층 영상에 묶고 지도 모드 셋을 같은 조건에서 확인함
> 상태: 코드 완료 · eval_gt, eval_pred, probe_prop_only Kit 확인 · model_10 기능 시험

## 구현

- `foothold_s2/eval/video25/record_c_layer.py`: EX-41 평가 로더, W86 런타임, 학습 DR 설치와 같은 `interval_push`를 A층 촬영에 연결했다. 2.0초에 64 env를 한 번 밀고 실제 Δv, 시각, 회복 원자료를 JSON에 저장한다. 세 지도 모드와 카메라 추적, 위 HUD, 아래 띠는 기존 D51 · D48 경로를 쓴다.
- `foothold_s2/eval/a_push_video.py`: `eval_gt`, `eval_pred`, `probe_prop_only`를 동일 지형 · 시드 · 밀기 그룹으로 등록한다. 출처 HEAD, 저장본 SHA, 실제 밀기 벡터를 비교한다. 주기는 `250`, `500`, `stage_end` 중 입력받아 기록만 한다. P1 평가·학습 표식이 있으면 보류하고 A층 표식으로 C층이 칸 경계에서 양보하게 한다. 프로세스 종료는 없다.
- 합성기는 `v3.2-D140` 판을 고정해 월드 XY 밀기 화살표와 크기, 모집단 중앙값 기준 회복 창을 그린다. 회복 수치의 기준과 문턱은 `eval_dr_mode.recovery_metrics`의 기록 전용 가정이다.

## CPU와 Kit 증거

| 검사 | 결과 | 원자료 |
|---|---|---|
| CPU 계약 · 지도 셋 · DR 설정 · 정수 done · 밀기 불일치 반례 · 기존 합성기 회귀 | 22 passed | `isaac311 python -m pytest foothold_s2/tests/test_a_push_video_cpu.py foothold_s2/tests/test_push_event_overlay.py foothold_s2/eval/tests/test_w78_video_consumer_cpu.py -q -p no:cacheprovider --basetemp D:/mai-tmp/scripter/a_push_final_tests` |
| 실제 저장본 | SHA `d9d4411c500107391c7e01baab86fb3fdf365d4d8e89869b219c6f78dfb2afcf` | `D:/mai-tmp/runner/s2_lab/ex41_rehearsal_20261103_025200/model_10.pt` |
| Kit `eval_pred` | rc 0 · 300 물리 step · 150/150 프레임 · 6.0초 · GT 사용 0/300 | `D:/mai-tmp/scripter/ex41_a_push_model10_try04/eval_pred.json` |
| 실제 밀기 | 2.0초 · 64 env · 중앙값 0.8098 m/s · 최대 1.3603 m/s | 같은 폴더의 `attempts/.../eval_pred/child.log` 안 `MAPMODE_DR` |
| 회복 | 59/64 env · 중앙값 1.08초, 기록 전용 | `eval_pred.json`의 `dr_recovery` |
| 전체 프레임 검사 | 원본 PASS · 합성본 PASS, 합성본 1920×1080 150 프레임 | `attempts/.../eval_pred/raw_frame_audit.json` · `styled_frame_audit.json` · `ffprobe` 직접 재확인 |
| 영상 | SHA `9b325b4834bc9588dec525ca16a3951a7a6e5eaa348ec099b541f333e69701db` | `D:/mai-tmp/scripter/ex41_a_push_model10_try04/attempts/a76fc9efcb873ba962e43f875fd1b1256d95cf739015e93d7a0f6b4fcc96ccb7/eval_pred/styled.mp4` |
| 육안 한 프레임 | 2.5초에 로봇 · 지도 · 밀기 화살표 · 아래 시간 띠 확인 | `D:/mai-tmp/scripter/ex41_a_push_model10_try04/frame_2p5.png` |

첫 세 시도는 각각 자식의 `PYTHONPATH` 누락, EX-41 W86 런타임 누락, 정수형 `done` 마스크 오류로 실패했다. 각 원본 로그는 `try01` · `try02` · `try03`에 보존했고, 고친 뒤 `try04`에서 rc 0을 확인했다. 기존 회귀 묶음 25개 중 `test_all_c_layer_rows_pin_headless_camera_args` 1개는 이번 변경과 무관하게 구 `build_plan` 호출에서 새 필수 인자 `gpu_jobs_tool`, `gpu_jobs_config`가 없어 실패했다. 위 22개 지정 시험은 통과했다.

## 고정 코드와 한계

- 구현 고정 커밋: `4c5134f25e26c4c02b73e34c0f021824e1da5c33`. 촬영 당시 HEAD는 `e835e32872a3cf2c85ff7af71befc501d4f8ad8f`였다. 이후 변경은 소비기의 세 모드 출처 HEAD 일치와 실제 밀기 벡터 허용차 `1e-5` 비교뿐이며 촬영기 SHA는 동일하다.
- 촬영기 SHA256 `32f01c060631b640e3297747f725840459cac4d3d941aec6e2783498097b9471`, 최종 소비기 SHA256 `54433dc7b1f386c81fbf735abb10dbe164ebb54b868a0220676799818dad1e1d`, 합성기 SHA256 `e0af53c859b037e423960f5ccedb32c4f669aef3713bc648a118d546ae6c2b99`.
- 위 표는 첫 Kit 확인 이력이다. 아래 지도 모드 셋 대조가 후속 완료 결과다. model_10은 기능 시험 저장본이며 본학습 성능 판정에 쓰지 않는다.

## 후속: 같은 밀기 세 지도 모드

GPU1의 runner P1 평가가 끝난 뒤 정답 지도와 지도 끔을 각각 Kit에서 촬영했다. 복원 지도의 원본 150프레임은 앞선 Kit 촬영에서 그대로 가져오고, 상태 표시줄이 파란 화살표를 가리지 않도록 바꾼 합성기만 CPU에서 다시 적용했다. 따라서 추가 Kit 촬영은 요청한 두 편이며 세 최종 영상은 같은 합성기 SHA를 가진다. 상태 표시줄 위치 수정은 커밋 `5fe372c37d8ce3a81a91a6f8e7d7d348c5c7138f`이다.

세 편 모두 model_10 SHA `d9d4411c500107391c7e01baab86fb3fdf365d4d8e89869b219c6f78dfb2afcf`, `pyramid_stairs` L0 · env0, 평가 시드 42, 밀기 시드 42, 밀기 그룹 `a76fc9efcb873ba962e43f875fd1b1256d95cf739015e93d7a0f6b4fcc96ccb7`이다. 촬영기 SHA `32f01c060631b640e3297747f725840459cac4d3d941aec6e2783498097b9471`가 세 편에서 같고, 실제 64 env 밀기 벡터도 절대 오차 `1e-5 m/s` 이내로 일치했다. 밀기는 물리 step 100, 영상 시각 2.0초였다.

| 정책 지도 | 최종 영상 | 회복 env/64 · 중앙값 | GT 지도 소비 | 150프레임 전수 검사 | 파란 화살표 상단 최소 y · 화면 위 잘림 |
|---|---|---:|---:|---|---|
| `eval_gt` | `D:/mai-tmp/scripter/ex41_a_push_model10_three_modes/attempts/a76fc9efcb873ba962e43f875fd1b1256d95cf739015e93d7a0f6b4fcc96ccb7/eval_gt/styled.mp4` | 63/64 · 1.16초 | 300/300 | 원본 PASS · 합성 PASS | 32 px · 0프레임 |
| `eval_pred` | `D:/mai-tmp/scripter/ex41_a_push_model10_three_modes/eval_pred_recomposed/styled.mp4` | 59/64 · 1.08초 | 0/300 | 원본 PASS · 재합성 PASS | 32 px · 0프레임 |
| `probe_prop_only` | `D:/mai-tmp/scripter/ex41_a_push_model10_three_modes/attempts/a76fc9efcb873ba962e43f875fd1b1256d95cf739015e93d7a0f6b4fcc96ccb7/probe_prop_only/styled.mp4` | 62/64 · 1.15초 | 0/300 | 원본 PASS · 합성 PASS | 32 px · 0프레임 |

화살표 검사는 합성 영상 150프레임의 좌상단에서 파란 표식의 최상단 픽셀을 세었고, y<30인 프레임은 없었다. 상태 표시줄은 A층 영상에서만 y=120 아래로 내려 파란 화살표와 겹치지 않는다. 각 모드의 2.48초 프레임도 직접 보아 로봇 · 밀기 HUD · 지도 선택 · 아래 시간 띠가 표시되는 것을 확인했다. 정답 지도와 지도 끔의 프레임은 `D:/mai-tmp/scripter/ex41_a_push_model10_three_modes/{eval_gt,probe_prop_only}_frame_062.png`, 복원 지도는 `eval_pred_recomposed/frame12.png`에 보존했다.

수치 정본은 `D:/mai-tmp/scripter/ex41_a_push_model10_three_modes/three_mode_summary.json`이다. 세 영상 SHA256은 차례로 `7c2b474332dc57e4efef4cb1caa7129c78cd701caf526e91936644c563aaab2d`, `ed02452d2925450546e36502771c7911b7b4b6bd13bef9c07d86b84a57b5e001`, `39646f5e50896cba16e5fc4309491a78852b66063e6cba7b77749f46b8063a71`이다. CPU 지정 회귀는 isaac311에서 23 passed였다. 본학습 저장본 성능과 A층 촬영 주기는 여전히 미확정이다.
