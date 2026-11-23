# Y1 좌우 대칭 손실의 거울 지각 재계산안

> 분류: A/정책학습 · 학습 · 보상 · 관측 · 파인튜닝
> 작성: scripter-lx · 2026-11-24 00:27
> 근거: `feature/scripter-e2-actor-mirror-1123` 002bfc9d0 · `feature/opus-code-e2-actor-mirror-1123` 3fc360556 · lead 11/24 00:22 요청
> 요지: 고정한 지각 잠재값 대신 거울 원자료로 지각을 한 번 더 재생하여 actor 대칭 손실을 계산하는 설계
> 상태: 초안 · 코드와 학습에 미적용
> 판: v1.0

## 왜 바꾸나

현재 Y1은 98차원 actor 입력의 관측 45개와 속도 추정의 y, 자세 roll만 뒤집고, 학습 잠재값 `z·zf·zb` 48개는 그대로 둔다. 코드가 이를 조건부 규제라고 명시한다 (`foothold_s2/runners/ex42_actor_mirror.py:1-7,45-82`). lead 보고의 손실 4~11과 관절별 행동 RMS 0.6~0.95는 이 좌우 불일치의 징후일 수 있지만, 원인 확정값은 아니다. 가중치만 낮추면 입력 불일치는 남는다.

## 제안하는 계산

1. PPO 수집 때 저장한 같은 시점의 `o45`, 이력 `10×45`, 깊이 `2×60×60`, 정답 지도 `32×16`, 발 지도 `4×5×5`, 몸속도, 명령, `first·tick·use_gt·map_off`를 사용한다. 평지 마스크는 현재처럼 **원 정답 지도 높이 범위 < 0.02 m**만 선택한다 (`ex42_actor_mirror.py:37-42`, `start_runner.py:952-955`). 마스크 밖은 손실 분모에서도 뺀다.
2. `o45`와 이력의 각 45차원 행은 `mirror_policy45`로 뒤집는다. 명령 `(vx,vy,wz)`는 `(vx,-vy,-wz)`, 몸속도는 y 부호 반전, 자세 `(Δh,roll)`은 `(Δh,-roll)`이다. 깊이는 영상 너비축, 정답 지도는 y축, 발 지도는 FL↔FR·RL↔RR 교환 뒤 각 `5×5`의 y축을 뒤집는다. 행동 12개는 관절 종류별 `JOINT_IDS` 순열과 hip 부호를 적용한다 (`ex41_critic_mirror.py:19-61`). 지도 끔과 정답/복원 선택은 원 표본의 플래그를 보존한다.
3. 거울 원자료를 **같은 지각 가중치**로 `StartPerception.est_sequence`의 `_advance`에 넣어 GRU를 다시 굴리고 `z·v·zf·zb`를 얻는다 (`foothold_s2/models/start_perception.py:413-430,455-469`). 복원 지도는 거울 깊이에서 TR-Net이 새로 만든 값이다. 원 복원 지도를 단순히 뒤집어 지각 입력으로 대신하지 않는다. `_est_in`의 속도 보정까지 원 actor 입력과 같은 길을 지나 거울 `actor_in`을 만든다.
4. `L_sym = mean || μ(actor_in) - M_action μ(mirrored_actor_in) ||²`를 평지 마스크 행에만 더한다. 원 PPO 수집 행동은 바꾸지 않는다. 제안 첫 판은 거울 지각 재생을 `no_grad`로 실행하여 **actor에만** 대칭 손실의 기울기를 보낸다. 지각까지 기울기를 보내면 지각 손실과 PPO 최적화가 섞이므로 별도 처치로 둔다. 기대 비용은 PPO update마다 선택된 rollout에 대한 지각 순방향 재생 1회다. 실제 초/회와 메모리는 미측정이다.

## 재생 시작 상태와 잠재 표집의 관문

기존 대안 가지에는 `mirror_replay`와 `mirrored_actor_inputs`가 이미 있다 (`feature/opus-code-e2-actor-mirror-1123`의 `ex42_actor_mirror.py:85-114`, `start_runner.py:477-490`). 다만 그 구현은 원 rollout의 `h_prop0·h_terr0`를 그대로 쓰며, 거울 앞 이력은 재생하지 않는다. `first`가 참이면 GRU가 0으로 재시작하므로 (`start_perception.py:413-416`) **첫 판은 reset 이후의 거울 이력이 전부 있는 연속 구간만 손실에 포함**한다. rollout 시작 때 이미 진행 중인 에피소드의 초기 hidden은 거울이 아니므로 제외하고, 제외 비율을 영수증에 쓴다. 그 비율이 지나치게 크면 reset 이후 이력을 이월 저장하는 후속 설계가 필요하다.

또한 수집 때 `z`가 표집될 수 있다 (`start_perception.py:443-453`). 원 표집 `z`와 거울 쪽 평균 `z`를 비교하면 표집 잡음도 대칭 손실에 들어간다. 첫 판은 수집 때 쓴 `eps`를 함께 저장하고 거울 `est_sequence`에 **같은 `eps`**를 넘긴다. 그러면 저장된 원 actor 입력을 그대로 쓰며 추가 지각 순방향은 거울 쪽 1회다. `eps`를 영수증으로 재구성할 수 없는 표본은 손실에서 제외하고 제외 수를 남긴다. 양쪽 posterior 평균을 쓰는 방식은 원쪽 추가 재생이 필요하므로 비용을 따로 재는 후속안이다.

## 코드 접점과 통과 시험

| 접점 | 필요한 변경 |
|---|---|
| `foothold_s2/runners/ex42_actor_mirror.py:45-82` | 고정 잠재값 경로를 거울 원자료 재생 손실로 교체. `flat_map_mask`와 행동 순열은 유지 |
| `foothold_s2/models/start_perception.py:443-453` · `foothold_s2/runners/start_runner.py:938-959` | 수집 때 사용한 `eps`, reset부터의 연속 구간, 마스크 분모를 저장. 행동·보상 수집은 그대로 |
| `foothold_s2/runners/start_runner.py:1060-1090` · `foothold_s2/models/start_perception.py:455-469` | PPO update 직전 거울 지각 순방향 재생을 연결하고 원 수집과 동일한 `eps`를 넘김 |
| `foothold_s2/runners/ex41_critic_mirror.py:393-405` | 재계산한 두 actor 평균의 손실만 더하고 actor 기울기·clip·영수증을 따로 확인 |

답을 아는 CPU 시험: 원자료 거울을 두 번 적용하면 `o45·hist·depth·지도·발 지도·pose·action`이 원래와 비트 동일해야 한다. 거울 대칭인 가짜 actor의 손실은 0, 일부러 한쪽으로 휘는 actor의 손실은 양수여야 한다. reset 전 이력이 없는 행은 제외되며, 지도 범위가 2 cm 이상인 행은 제외된다. 지각 파라미터 기울기는 0, actor 기울기는 양수여야 한다. 실제 저장본으로 동일 관절 순서·잠재값 크기·마스크 몫·회당 시간과 학습 첫 10회 손실을 재야 한다. 이 실측 전에는 Y1 개선 판정이나 학습 적용을 주장하지 않는다.
