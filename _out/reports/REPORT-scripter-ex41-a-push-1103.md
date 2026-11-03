# EX-41 A층 밀기 영상 준비와 model_10 한 편 확인
> 분류: A/평가 · 일반화 벤치마크 · 지표
> 작성: 오흥재 (scripter 반영) · 2026-11-03
> 근거: 팀장 11/03 13:0x 지시 · eval_dr_mode.py · model_10 실제 Kit 기록
> 요지: DR 켬 밀기와 회복 원자료를 A층 영상에 묶고 복원 지도 모드 한 편을 확인함
> 상태: 코드 완료 · 지도 모드 셋 중 eval_pred Kit 확인, 나머지 두 모드 Kit 미확인

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
- 이번 실제 Kit 검증은 `eval_pred` 한 편이다. `eval_gt`와 `probe_prop_only`의 실제 촬영 및 세 모드 간 실측 밀기 동등성은 미확인이다. model_10은 기능 시험 저장본이며 본학습 성능 판정에 쓰지 않는다.
