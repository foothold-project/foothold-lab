# SOL-23c · EX11·23·25·811 기존 학습곡선과 촬영 증거

> 분류: A/평가 · 일반화 벤치마크 · 지표
> 작성: jay · 2026-10-23
> 근거: 네 실행의 TensorBoard 원본, 각 실행 `params/env.yaml`·`manifest.json`, 기존 `s2_lab/videos/mid500_1022` 로그·JSON·MP4
> 요지: 기존 학습곡선을 원값으로 겹쳐 보고, EX25 리셋과 결측 영상의 시도 일치를 구분한다.
> 상태: CPU 재계산 완료 · 종료 원인 미확인 · GPU·Kit 미실행
> 판: v1.0

## 원자료와 읽는 법

| 판 | 실행 폴더 | event SHA256 | 규모 |
|---|---|---|---|
| EX11 | `foothold_s2_x11/2026-10-22_01-33-36_ex11-est-zero` | `142897d7a37ed8d16f6037bafb79e53c99967ae13905adc88e7904d97a51fdca` | 3072 env × 24 step |
| EX23 | `foothold_s2_x23/2026-10-22_21-52-26_ex23-g1` | `9e052900e36e17fd0d118c5484ce4632e18f183f837cb19d6f841d9bf93e47d9` | 3072 env × 24 step |
| EX25 | `foothold_s2_x23/2026-10-22_23-00-45_ex25-g0` | `521bc26ca31673fe92123e7b2447d801008cc475baae8faa6621d720f53c4f41` | 3072 env × 24 step |
| 811 | `C:/isaac/IsaacLab/logs/rsl_rl/unitree_go2_rough/2026-08-11_20-32-58` | `0453f60798f695627263aff812a65d17e52d6407c098eaa2234dc9b8c0c0ee19` | 4096 env × 24 step |

앞의 세 실행 폴더는 `C:/Users/AI-WS01/orca/workspaces/foothold-lab/sonnet-code/logs/rsl_rl/` 아래다. 각 폴더의 단일 `events.out.tfevents*`를 TensorBoard `EventAccumulator`로 직접 읽었다. [원값 CSV](../20261021-experiments/figs/ex23-25-sol-23c/tb_scalar_raw.csv)는 확인된 52개 판·필드 곡선의 78,042개 scalar를 한 행씩 담는다. [출처 목록](../20261021-experiments/figs/ex23-25-sol-23c/tb_sources.json)에 event 경로·SHA·누락을 담았다. CSV의 `tb_step`은 파일 원값이다. `update_completed=tb_step+1`, `transitions_completed_est=(tb_step+1)×env 수×24`는 설정과 logger 순서에서 계산한 축이다. 811은 갱신당 98,304, 나머지는 73,728 transition이므로 같은 update는 같은 경험량이 아니다. transition 축은 실제 개별 env 종료 횟수를 세는 값이 아닌 수집 슬롯 수 추정이다.

[update 축 그림](../20261021-experiments/figs/ex23-25-sol-23c/tb_overlay_update.png) · [transition 축 그림](../20261021-experiments/figs/ex23-25-sol-23c/tb_overlay_transitions.png) · [종료·KL update 그림](../20261021-experiments/figs/ex23-25-sol-23c/tb_termination_update.png) · [종료·KL transition 그림](../20261021-experiments/figs/ex23-25-sol-23c/tb_termination_transitions.png)을 원값으로 그렸다. 그림을 직접 열어 범례·축·누락 표시를 확인했다. 새 합격선이나 평활화는 적용하지 않았다.

## 태그 범위와 수치 판독

네 판에서 선속도·회전 추종 오차(`Metrics/base_velocity/error_vel_xy`, `error_vel_yaw`), episode 길이, `time_out`, terrain level, value·surrogate loss를 찾았다. EX11·23·25에는 `bad_orientation`, `foot_below_ground`, `Loss/reward_split/frac_stalled`, `Loss/perception/kl`, `Loss/kl_probe/ppo_mean`도 있다. 811은 `base_contact`가 있고 `bad_orientation`·`foot_below_ground`·정체율·지각 KL·PPO KL probe 태그가 없다. 없는 항목은 **미측정**이다. `base_contact`와 `bad_orientation`은 서로 다른 종료 항목이므로 한 곡선의 서로 다른 색으로 표시한 값의 크기를 동일 원인으로 해석하지 않는다. `Episode_Termination` 값은 logger가 낸 원값이며, 개별 평가 영상의 리셋 횟수나 전체 rollout transition에 대한 비율로 바꾸지 않았다.

| TB 마지막 값 | EX11 (1501회) | EX23 (1501회) | EX25 (1501회) | 811 (1500회) |
|---|---:|---:|---:|---:|
| 선속도 추종 오차 | 1.6213 | 1.0920 | 1.3289 | 0.5205 |
| 회전 추종 오차 | 1.5925 | 1.0993 | 1.2085 | 0.4358 |
| 평균 episode 길이 | 945.29 | 943.28 | 915.60 | 979.15 |
| terrain level | 5.0284 | 6.1810 | 6.0995 | 5.6317 |
| 정체율 태그 | 0.2411 | 0.0956 | 0.1231 | 미측정 |
| `time_out` 태그 | 0.9007 | 0.9221 | 0.9000 | 0.9358 |
| `bad_orientation` 또는 811 `base_contact` | 0.0993 | 0.0779 | 0.1000 | 0.0642 |
| 지각 KL 태그 | 0.0000107 | 0.0000101 | 0.0000072 | 미측정 |

선속도 보상은 네 env 설정 모두 `track_lin_vel_xy_exp`, std 0.5, weight 1.5이지만 811의 기록 이름은 `track_lin_vel_xy_exp`, 나머지는 `track_lin_vel`이다. 회전 보상은 같은 `track_ang_vel_z_exp`, std 0.5이나 811 weight 0.75, 나머지 0.5다. 따라서 회전 보상 원값의 높이를 성능 차이로 바로 읽을 수 없다. 명령·지형·종료 구성도 다르며, 학습곡선은 특정 사례의 통과율이 아니다. 811의 추종 오차가 낮다는 관측은 이 설정 차이를 제거한 비교가 아니다. EX11·23·25의 지각 KL이 작은 것은 기록된 마지막 scalar의 값이며 지도 사용의 효과 판정이 아니다.

## EX25 영상의 시도 일치와 종료 증거

| 기존 폴더와 사례 | 파일·로그에서 확인한 것 | 사용할 수 있는 범위 |
|---|---|---|
| `ex25_300/run_flat` | `run_flat_try1.log`의 `CLIP`은 300프레임·밝기 0·리셋 64. JSON·NPZ는 이 시도 시각이며 JSON도 64. 현재 MP4는 약 5분 뒤 try2 시각으로 덮였고 `ffprobe`는 `moov atom not found`. `run_flat.done` 없음 | 64는 첫 시도에서 기록한 reset 수. 현재 MP4와 JSON은 한 성공 시도가 아님. 종료 항목 미기록 |
| `ex23r_1000/run_rough` | EX23 checkpoint `model_1000.pt`의 try1 로그·JSON에 밝기 0·리셋 56. try2 로그에는 `CLIP` 완료 줄 없음. `run_rough.done` 없음, `ALL.done`만 있음 | 56은 EX23의 험지 시도 수치이며 EX25 수치가 아님. 종료 항목 미기록 |
| `ex25_1000/run_rough` | EX25 checkpoint `model_1000.pt`의 try1 로그·JSON에 밝기 0·리셋 71. try2 로그에는 `CLIP` 완료 줄 없음. 현재 MP4는 JSON보다 늦게 쓰였고 `ffprobe` 실패. `run_rough.done` 없음, `ALL.done`만 있음 | 71은 EX25의 험지 첫 시도 기록. 현재 MP4와 JSON은 한 성공 시도가 아님. 종료 항목 미기록 |
| `ex25_500/run_flat` | MP4만 있고 JSON·NPZ·`run_flat.done` 없음. MP4는 `ffprobe`에서 `moov atom not found`. `ALL.done`은 있음 | 평지 촬영 결과 결측. 리셋 수 미측정 |
| `scratch0811/s300_flat` 대조 | JSON·NPZ·MP4 시각이 맞고 MP4는 `ffprobe` 300프레임, JSON 밝기 183.47·리셋 0. 기존 `.done`은 단순 텍스트 | 이 대조는 EX25 결측을 채우지 않음. 영상의 보행 판정도 아님 |

기존 `seq_video.sh`의 `ALL.done` 및 5바이트 `done`은 자식 성공과 세 파일의 동일 시도성을 증명하지 않는다. 위 수치는 로그·JSON에 기록된 **반복 reset 관측**이다. `record_seq.py`는 `dones` 합계만 남기고 `time_out`·`bad_orientation`·`foot_below_ground` 등 개별 termination을 저장하지 않았다. 그래서 reset 64·56·71을 낙하나 특정 종료 원인으로 확정할 수 없다. `REPORT-sol-23a.md`와 `REPORT-sol-23b.md`의 force_gt·영수증 수정은 보존했다. `mid_ck2` 소비 연결은 미완료이며 이번 범위에서 도구·사슬·촬영을 실행하거나 수정하지 않았다.

## 확인 명령과 한계

CPU에서 TensorBoard 이벤트를 직접 파싱하고 파일 SHA를 계산했다. CSV는 78,042행·52곡선으로 되읽고 네 event 파일 SHA 및 각 파일의 update 300 원값을 다시 대조했다. PNG 네 장은 이미지 해독과 크기를 확인했고 update 축 그림을 직접 열어 읽었다. `ffprobe`는 위 네 MP4 중 손상 3건을 거절하고 811 대조 1건의 300프레임을 읽었다. 기존 로그의 `CLIP` 줄, JSON checkpoint·resets·brightness, 파일 시각을 대조했다. CUDA·Kit·학습·재촬영은 실행하지 않았다. 영상을 새로 해석하지 않았으며 종료 항목의 원자료가 없어 실제 reset 원인은 미확인이다.
