> 분류: 실험 분석
> 작성: 오흥재 (luna 문서 반영) · 2026-10-23
> 근거: 94be0446 · raw gait_table.csv · mid500_1022 영상 · 기존 LUNA-23a 그림
> 요지: EX-23/25 1500회 자료의 회전표 출처 정정과 영상·그림 원자료 대응 기록
> 상태: 보강 자료 · 해석은 lead_tmp와 astra2 검토 대기

# LUNA-23b · EX-23/25 자료 보강

## 흐름과 범위

기존 EX-23/25 1500회 판의 낮은 자세 관찰, 811 회차별 기준 조사, 초기 DR와 지연 완화, 이후 EX-23/25 보행 개선이라는 시간 흐름을 유지한다. 이 문서는 분석 보강 자료만 담는다. `RESULT-EX23-25.md`는 편집하지 않았다.

수치의 근거 등급은 [실측] 원자료 표의 계산값, [기록] 파일·실행 기록, [가정] 해석 없이 보류로 구분했다. 결론은 lead_tmp와 astra2 검토에 남긴다.

## 회전표 기준선 행 출처 정정

[실측] [`rotation-corrected.csv`](figs/ex23-25-luna-23b/rotation-corrected.csv)는 EX-23/25의 1000·1500회 flat·rough 각각에서 회전 ±1.2 행을 원 `gait_table.csv`의 실험 라벨과 구간으로 필터해 재구성했다. 표에는 16개 실제 실험 행과 원본 경로, 라벨, 구간이 있다.

[실측] 기존 결과의 EX-23/25 회전표에 반복 삽입된 `0.207/-0.00`, `0.241/0.00`, `0.327/-0.42`, `0.132/0.01` 값 묶음은 각 raw `gait_table.csv`의 EX-11 500 평지 및 v2 3000 평지 참고 행과 일치한다. raw 표에서 참고행과 실험행은 별도 `label` 값으로 구분된다. 확인된 원인은 참고행이 EX-23/25 행으로 함께 옮겨진 라벨·체크포인트 혼입이다. 값 자체는 참고 실험 자료로 남기며 EX-23/25 성능값으로 해석하지 않는다.

[기록] 새 영상의 2초 간격 접촉 시트에서 로봇은 화면 안에 있고 검정 프레임·가림은 보이지 않았다. 회색 바닥은 rough 지형 렌더이며 결함으로 분류하지 않는다. 이전 LUNA-23a의 회색 화면 제외 판정은 잘못된 시각 판독이었다. v2 회전 중 넘어짐은 실제 정책 결과이며 제외하지 않는다. 기존 lead 비교 영상 `C:/Users/AI-WS01/s2_lab/videos/mid500_1022/compare_mid_1022.mp4`와 `compare_mid_1022_half.mp4`는 수정하지 않았고 보존한다.

## EX-23/25 1500회 비교 영상

[기록] 입력 영상은 `C:/Users/AI-WS01/s2_lab/videos/mid500_1022/ex23r_1500/run_flat.mp4`, `ex25_1500/run_flat.mp4`, `ex23r_1500/run_rough.mp4`, `ex25_1500/run_rough.mp4`이다. 각 입력은 12초이며 원본은 수정하지 않았다. 출력은 화면을 자르지 않고 좌우 배치했으며 상단에 모델명만 별도 띠로 표시했다. 원본 명령/HUD는 유지된다. 인코딩은 CPU `libx264`로 수행했고 오디오는 원본에 없으며 출력에도 넣지 않았다.

| 조합 | 작업 사본 경로 | 길이 | SHA-256 |
|---|---|---:|---|
| flat 1배 | `C:/mai/wt/foothold-lab/luna-23b/inbox/jay/20261021-experiments/figs/ex23-25-luna-23b/ex23-ex25-flat-1500-1x.mp4` | 12초 | `70FC8BCECE9E59157A2C5D0989DD7E42CA8A10461E96A5480A24274201252638` |
| flat 0.5배 | `C:/mai/wt/foothold-lab/luna-23b/inbox/jay/20261021-experiments/figs/ex23-25-luna-23b/ex23-ex25-flat-1500-0.5x.mp4` | 24초 | `55F051A57E5F7FB92B6F383D02F8C920ED90307A60F9AD29028883DBC3F3F418` |
| rough 1배 | `C:/mai/wt/foothold-lab/luna-23b/inbox/jay/20261021-experiments/figs/ex23-25-luna-23b/ex23-ex25-rough-1500-1x.mp4` | 12초 | `C61E2D616E75D0FAF0FFFF931B0B7718A50A5E5E5C8E956DFB49FD7C4F65A6B3` |
| rough 0.5배 | `C:/mai/wt/foothold-lab/luna-23b/inbox/jay/20261021-experiments/figs/ex23-25-luna-23b/ex23-ex25-rough-1500-0.5x.mp4` | 24초 | `1B978AFCF5C3C006D5BEAF4695B2E2FE7EDE80679414A451650C93252E4692F1` |

각 영상의 0·2·4·6·8·10초 프레임을 담은 contact sheet는 같은 폴더의 `*-contact.png` 파일이다. 전 구간 접촉 시트에서 화면 잘림, HUD 덮임, 로봇 가림, 검정 프레임은 확인되지 않았다. 0.5배 영상은 같은 12초 장면 전체를 24초로 늘렸다. 0~12초 자료 전체를 보존했다.

큰 mp4는 git에 추가하지 않았다. 로컬 작업 사본 경로와 SHA-256만 기록한다.

## 재사용한 그림과 원자료 대응

아래는 기존 LUNA-23a 자료 재사용 목록이다. 이번 작업에서 원 그림 파일은 수정하지 않았다.

| 그림 | 기존 파일 | 사용 자료 |
|---|---|---|
| 보행 위상 | `figs/ex23-25-luna-23a/gait-phase.png` | `C:/Users/AI-WS01/s2_lab/videos/mid500_1022/{ex23r_300,ex23r_1000,ex23r_1500,ex25_300,ex25_1000,ex25_1500}/run_flat_feet.npz`, `scratch0811/s1000_flat_feet.npz`, `v2_flat_feet.npz` |
| 자세·관절 | `figs/ex23-25-luna-23a/pose-joints.png` | 위와 같은 feet NPZ. v2에는 관절각·pitch·roll이 없어 몸 높이만 표시 |
| 학습 곡선 | `figs/ex23-25-luna-23a/learning-curves.png` | 811: `C:/isaac/IsaacLab/logs/rsl_rl/unitree_go2_rough/2026-08-11_20-32-58/events.out.tfevents.1786447995.AI-WS01.71864.0`; EX-11: `C:/Users/AI-WS01/orca/workspaces/foothold-lab/sonnet-code/logs/rsl_rl/foothold_s2_x11/2026-10-22_01-33-36_ex11-est-zero/events.out.tfevents.1792600433.AI-WS01.84612.0`; EX-23: `.../foothold_s2_x23/2026-10-22_21-52-26_ex23-g1/events.out.tfevents.1792673564.AI-WS01.29056.0`; EX-25: `.../foothold_s2_x23/2026-10-22_23-00-45_ex25-g0/events.out.tfevents.1792677663.AI-WS01.46760.0` |
| 0.08초 프레임 띠와 접촉 시트 | `figs/ex23-25-luna-23a/{ex23r_1000,ex23r_1500,ex25_1000,ex25_1500,scratch0811_s1000,v2_flat}-{strip,contact}.png` | 각각 `C:/Users/AI-WS01/s2_lab/videos/mid500_1022/{ex23r_1000,ex23r_1500,ex25_1000,ex25_1500}/run_flat.mp4`, `scratch0811/s1000_flat.mp4`, `v2_flat.mp4` |

[기록] TensorBoard 그림은 10 update 이동평균 표시이며 재학습하지 않았다. 파일 목록은 `figs/ex23-25-luna-23a/tensorboard-tags.txt`에 기록되어 있다. EX-25 500회 feet NPZ는 없어 위상·자세 그림에서 제외되어 있다.

## 검토 대기

수치·위상·프레임이 같은 해석을 지지하는지와 보행 개선 여부의 결론은 lead_tmp와 astra2가 판정한다. 이 보강물은 EX-23/25 회전 실측과 baseline 참고행을 구분하고, v2 넘어짐 및 회색 rough 장면을 보존한다.
