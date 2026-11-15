> 분류: 리서치 · 결과 준비
> 작성: scripter · 2026-10-26 01:28 KST
> 근거: EX-32 판정 카드 · RULES-HUB 7·8절 · 64환경/16환경 원본 · TensorBoard · 생성 코드
> 요지: G0-B 학습과 평가를 원본에서 집계하고 결측은 평가 전으로 표시한다
> 상태: 중간판 · 영상과 m1500 확인 전 해석 미완

# SOL-26a · G0-B 결과 집계

## 1. 영상

영상 없음 · 미확인. 단일·비교 영상 및 대표 프레임이 없어 회전 수치만으로 보행 개선을 말하지 않는다.

## 2. 비교 조건

| 자료 | 환경 | 지형 SHA | 지도 모드 | 관측값 |
|---|---:|---|---|---|
| G0-B 64환경 | 64 | c3884d686592596ee6ac7b2cdfc94e0b1d3f6d84dbca66c52ad20a0400e2358f | none | 300 policy step |
| B1500 64환경 | 64 | c3884d686592596ee6ac7b2cdfc94e0b1d3f6d84dbca66c52ad20a0400e2358f | eval_gt·eval_pred·probe_prop_only | 300 policy step |
| G0-B 16환경 | 16 | 7f49a1e935ea1dd741b0db47fe6da965eaa772c03f30c94f9fa976125db33506 | none | alive 샘플 평균 |
| B1500 16환경 | 16 | 7f49a1e935ea1dd741b0db47fe6da965eaa772c03f30c94f9fa976125db33506 | eval_pred | alive 샘플 평균 |

같은 지형 배정이지만 B1500 16환경은 eval_pred이고 G0-B는 none이다. 지도 모드가 다른 비교는 정책 간 참조값이며 처치 효과를 고립하지 않는다.

## 3. 전진 · 높이 · 발 교대

B1500 eval_gt 전진1.0 거리는 5.653 m, 카드의 0.9배는 5.087 m이다. G0-B m1500 전진1.0은 5.740 m이다. 지도 없는 G0-B의 지도 켬 유지 판정은 해당 없다.
몸 높이 원자료는 이 평가 JSON에 없어서 미측정. m1500 발 위상은 `figs/ex32-g0b/checkpoint_table.md`의 위상 표와 `gait_phase.png`를 본다. 완전 주기가 없으면 각도 미측정이다.

## 4. 회전의 회차별 변화

64환경 최신 확인 저장본 m1500, 16환경 최신 확인 저장본 m1500이다. 모든 m550~m1500 칸의 값과 `평가 전`은 `figs/ex32-g0b/checkpoint_table.md`에 있다. `checkpoint_metrics.png`는 같은 표의 그림이다. 회전 `같음`은 m1500 같은 모드의 16환경 평균 요 속도 차가 0.12 rad/s 이하일 때만 판정하며 영상·위상 없는 개선 해석은 보류한다.

## 5. 관절 · 기울기

64환경 `map_modes.json`에는 `tilt_rad_mean_alive`가 저장되어 있고 원값은 `map64_by_checkpoint.csv`와 원본 JSON에 있다. 관절 ROM과 몸 높이는 이 묶음에서 뽑을 원자료가 없어 미측정이며 추가 결론을 내지 않는다.

## 6. 학습 곡선

학습 TensorBoard는 G0-B m1500까지 읽었다. `training_curves.png`에 보상 항, 길이, 지형 레벨, PPO·phi KL, action std, value loss와 종료 항을 B와 겹쳤다. `training_raw.csv`가 그 그림의 원값이며 훈련 평균은 독립 평가가 아니다.

## 7. 증거의 한계

현재 64환경 완료 80칸, 평가 전 0칸, 16환경 완료 114칸, 평가 전 6칸이다. 보행 위상 env 기록은 64개다. 진행 중 TensorBoard는 읽는 동안 바뀌지 않았다. `summary.json:training`의 앞뒤 SHA를 함께 남겼다. 동일 시드·지형만으로 지도의 인과 효과를 확정할 수 없다.

## 8. 다음 설계에서 바꿀 것

카드의 m1500 판정, 보행 위상, 영상 확인이 끝나기 전에는 출발선 선택을 보류한다. 이 문서는 새 학습 승인이나 설정 변경이 아니다.

## 9. 재현 경로

- 생성 코드: `figs/ex32-g0b/generate_result26a.py` · 답 아는 입력: `test_result26a.py`.
- 시험: B1500 여섯 경우 원본 NPZ 재계산 6/6 일치, 결측 평가 `평가 전`, S-B 두 모드·지도 켬/끔 분리, 지형 SHA 변이 거절, `ruff check --select F` 통과.
- 원본 절대 경로·SHA: `figs/ex32-g0b/summary.json`; 생성 표: `checkpoint_table.md`·CSV 4개.
- 코드와 표·그림 SHA: `figs/ex32-g0b/SHA256SUMS.txt`.
- S-B: 같은 생성기에 `--map-switch`와 `--expected-modes eval_gt,probe_prop_only`, `--turn-layout eval_gt:turn16_gt,probe_prop_only:turn16_prop`, `--g0-reference-map`을 주어 지도 켬·끔을 별도로 기록한다. 실제 평가 폴더명은 생성 전 확인해야 한다.
