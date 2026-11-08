# SOL-25c · B1500, EX-30, EX-31 그림 세트

> 분류: A/평가 · 일반화 벤치마크 · 지표
> 작성: sol · 2026-10-25
> 근거: 여섯 촬영 영수증과 JSON/NPZ/MP4, 64환경 평가 JSON, TensorBoard 원자료
> 요지: 동일 촬영 조건의 보행과 회전, 학습 곡선, 64환경 회전 평가를 나란히 제시한다.
> 상태: CPU 재계산 확인 · 해석은 lead 검토 대기

## 입력과 검증

- `C:/Users/AI-WS01/s2_lab/run_20261025/`의 B1500, EX-30 m2000, EX-31 m2000 각각 flat/rough 촬영 여섯 편을 사용했다. 모두 12초, 제어 600행, 해독 영상 300프레임, reset 0이다. 각 `review.done`의 파일 해시와 영상을 다시 대조했다. 짝의 명령, 시드, 지형 선택, 물리 및 정책 모드도 대조했다.
- 촬영 시 B1500과 EX-31은 정답 지도 입력 600/600, EX-30은 복원 지도 입력 0/600이다. `matched_metrics.json`의 `map_choice`에 판별 기록이 있다. 지도 입력이 다른 판끼리 단독 정책 효과로 읽으면 안 된다.
- `turn_change_1500_1750_2000.png`는 고정 64환경, 300제어회 평가 원자료다. GT와 PRED를 별도 칸에 표시했다. B1500을 각 판의 1500 기준으로 그렸고 1750과 2000은 EX-30/31 각 판이다. 이 그림은 촬영 한 편의 연속 명령 궤적과 다른 측정이다.
- 출처 경로와 SHA는 `matched_metrics.json`, `turn_change_1500_1750_2000.json`, `video_evidence.json`, `training_last25_and_restart.json`에 있다. 답을 아는 네 발 접촉 판별 입력은 분석기 실행 중 통과했다.

## 연속 명령 촬영의 직접 측정

수치는 각 구간에서 제어 100행의 평균이다. 전진은 1~3초, 좌회전은 7~9초, 우회전은 10~12초다. 높이는 접촉 발 중심 기준이다. 회전 추종 비율은 해당 부호의 실제 요속도 평균을 1.2 rad/s 목표로 나눈 값이다.

| 촬영 | 전진 vx m/s | 전진 높이 m | 전진 대각 단독 접촉 비율 | 좌회전 wz rad/s | 좌 추종 | 우회전 wz rad/s | 우 추종 |
|---|---:|---:|---:|---:|---:|---:|---:|
| B flat | 0.541 | 0.321 | 0.52 | 1.309 | 1.091 | -0.449 | 0.374 |
| EX-30 flat | 0.499 | 0.313 | 0.28 | 1.034 | 0.861 | -0.676 | 0.564 |
| EX-31 flat | 0.501 | 0.309 | 0.50 | 0.372 | 0.310 | -0.359 | 0.299 |
| B rough | 0.509 | 0.319 | 0.35 | 1.320 | 1.100 | -0.133 | 0.111 |
| EX-30 rough | 0.373 | 0.309 | 0.15 | 0.718 | 0.599 | -0.688 | 0.573 |
| EX-31 rough | 0.441 | 0.300 | 0.35 | 0.647 | 0.539 | -0.526 | 0.438 |

촬영에서는 EX-30의 우회전 추종이 B보다 높지만 전진 속도와 대각 단독 접촉 비율은 낮다. EX-31은 flat 좌회전 추종이 낮다. 따라서 한 지표만으로 판을 고를 수 없다. `rough`는 시작 타일 이름이다. 모든 촬영은 그 타일의 추정 8 x 8 m 경계를 지난 뒤 회전 구간에 들어가므로 이 표의 회전을 순수 험지 회전으로 해석할 수 없다. 한 지형·정책당 연속 명령 1편이며 성공률을 추정하지 않는다.

64환경 회전 평가의 `yaw_follow_median`은 EX-30의 정답 지도 좌회전에서 B1500 0.873, EX-30 1750 0.480, EX-30 2000 0.331이었다. EX-31의 복원 지도 우회전에서는 B1500 0.151, EX-31 1750 0.663, EX-31 2000 0.321이었다. 나머지 좌·우, GT·PRED 값은 JSON과 그림에 모두 남겼다. 이 두 예만으로 2000의 일관된 개선을 주장할 수 없다.

## 학습 곡선과 위상

- `training_curves.png`는 SOL-25b의 CPU 원자료 그림을 복사했다. 마지막 25회 평균의 `Train/mean_reward`는 B 14.131, EX-30 15.555, EX-31 16.742다. 같은 창에서 `Episode_Reward/track_lin_vel`은 각각 1.138, 1.167, 1.240이고 `Loss/reward_split/frac_stalled`는 0.0626, 0.0673, 0.0313이다. 훈련 평균은 독립 평가가 아니며 EX-30의 보상 합이 더 높다는 사실이 촬영 회전·전진 우세를 뜻하지 않는다.
- 재시작 부근 value loss의 개별 값을 `training_last25_and_restart.json`에 보존했다. 예를 들어 EX-30은 1750에서 0.02439, 1751에서 0.01282, 2000에서 0.02822다. 시작점의 단일 값을 마지막 성능으로 쓰지 않는다.
- `contact_phase_summary.png`는 별도의 SOL-25b 고정 지형 16환경 probe의 발 접촉·발 풀림·실제 요를 시각화한다. 여섯 촬영의 1환경 위상과 실험 조건이 다르므로 별도 증거다. 접촉 발 링크 중심의 XY 속도는 접촉점의 지면 상대 미끄럼과 같지 않다.

## 그림과 파일

- 대표 영상 JPG: `comparison_frame_8s_flat.jpg`, `comparison_frame_8s_rough.jpg`.
- 촬영별 JPG: `B`, `EX30`, `EX31` 각각 flat/rough의 overview, stride, left_end, right_end, 총 24장. `inspection_jpg_sheet.jpg`로 전체 구도를 확인했다.
- PNG: `gait_height_commands.png`, `turn_change_1500_1750_2000.png`, `left_turn_joint_response.png`, `right_turn_joint_response.png`, `body_tilt.png`, `joint_angles_flat.png`, `joint_angles_rough.png`, `contact_phase_summary.png`, `training_curves.png`.
- CPU 재생성 코드: `analyze_ex3031_w2_1025.py`. 측정 JSON: `matched_metrics.json`, `turn_change_1500_1750_2000.json`, `contact_phase_source.json`, `training_last25_and_restart.json`, `video_evidence.json`. 별도 비교 영상 네 편은 기존 `run_20261025/compare/`에 있고 새 렌더는 필요하지 않다.

PNG와 JPG를 직접 열어 빈 축, 잘림, 범례 및 영상 속 로봇을 확인했다. 렌더는 추가로 실행하지 않았다. 추가 촬영과 새 학습은 이 작업 범위 밖이다.

## lead가 정할 것

정답 지도 B·EX-31과 복원 지도 EX-30의 차이, 한 편의 연속 명령 촬영과 64환경 평가를 함께 보고 결과 문서의 결론 강도를 정해야 한다. 현재 원자료에서 누락된 요청 파일은 없다.
