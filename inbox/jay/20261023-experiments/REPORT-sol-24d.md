# SOL-24d · TopDown GPU 1 본류 기동 전 읽기 검토

> 분류: A/정책학습 · 학습 · 보상 · 관측 · 파인튜닝
> 작성: sol · 2026-10-24
> 근거: `lead-tmp-start-b` d9517fb9의 실행 코드, 07:18 및 07:23 Kit 10회 원자료
> 요지: 3072 환경 10회는 완주와 저장을 확인했다. 09:55 경계 저장 뒤 재개는 코드상 가능하지만 동일 물리 궤적은 아니다.
> 상태: 원자료 읽기 확인 · GPU 1 본류 실행 결정은 root와 팀장 담당 · 장기 및 실제 재개 미확인

## 판단

현재 고정 코드에서 **3072 환경 TopDown 본류 기동을 막는 확인된 결함은 찾지 못했다.** 3072와 4096의 실제 Kit 10회가 각각 감독기 종료 코드 0, manifest `completed_updates=10`, `train_start_status.json`의 `state=done`, `model_9.pt`의 기록 SHA와 실제 SHA 일치로 끝났다. 이는 1001회 장기 안정성, 학습 성공, 재개 실기를 검증한 결과가 아니다. 팀장의 실행 결정이나 승인으로 해석하지 않는다.

| 항목 | 3072 환경 | 4096 환경 | 확인 범위 |
|---|---:|---:|---|
| 감독기 시작부터 종료 | 07:18:12~07:22:58, rc 0 | 07:22:58~07:29:35, rc 0 | `td_perf_compare/status.json` |
| 최종 갱신 | 10, `model_9.pt` | 10, `model_9.pt` | 두 manifest와 상태 파일 |
| 최종 체크포인트 SHA | `8402732d` | `34cac2b4` | 기록과 실제 파일 직접 대조 |
| 마지막 갱신 시간 | 24.61초 | 35.18초 | 두 `run.log`, update 9 |
| 마지막 AdaSmpl GT 선택 비율 | 0.8408 | 0.8306 | 로그의 `adasmpl/gt_fraction` |
| 마지막 지도 입력 | GT와 정제 지도의 혼합, `map_input=reconstruction` | 동일 | manifest와 `map_stats.jsonl` |
| 마지막 PPO / 지각 KL 평균 | 0.0079 / 0.0007 | 0.0157 / 0.0006 | `train_extra.jsonl` |
| 마지막 정체 구간 비율 | 0.8101 | 0.8222 | `train_extra.jsonl`, 성능 합격선 아님 |

두 manifest의 `est_mode=learned`, `force_gt=false`, `map_input=reconstruction`, `num_steps_per_env=24`, `seed=42`, `sim.device=cuda:1`을 확인했다. 두 로그는 update 0~9의 PPO · 지각 · KL · AdaSmpl 수치를 기록하고 `TRAIN_START_STATUS done`으로 끝나며, 비유한 손실이나 예외 줄은 확인되지 않았다. 지도 통계는 마지막 회차에서 GT와 refined 입력을 모두 기록한다. 초기 지도 GT 선택 비율이 아직 높으므로 10회 기록만으로 학습된 지도를 쓴 정책의 품질을 판정할 수 없다. floor material의 PhysX readback은 원자료 자체가 `API unverified`라고 표시한다.

## 09:55 경계 저장과 촬영 뒤 재개

`train_sol23f_common.py:39-48`의 `--end-by`는 시간대가 있는 마감이며 `max-wall-s`와 이른 쪽이 적용된다. `sol23f_runner.py:235-252`는 갱신 로그 직후 마감을 검사해 `model_<it>.pt`와 `latest.pt`를 저장하고 `stopped_saved` 상태로 돌아간다. `start_runner.py:369-386`의 통상 저장도 갱신 단위이고, `sol23f_runner.py:208-212`의 번호 붙은 저장은 임시 파일 후 교체다. 따라서 **09:55를 end-by로 둔 실행이 정상 마감하면** GPU 1을 B 500 촬영 전에 비울 수 있는 코드 경로가 있다. 마감 전에 이미 진행 중인 갱신은 끝나야 하므로 09:55 정각 즉시 해제는 보장되지 않는다. 10회 실측 마지막 갱신 24.61초를 경계 지연의 참고치로만 쓴다. 1001회 전체는 3072 환경 10회 속도만 단순 외삽하면 약 6.8시간이며 장기 처리량은 미측정이다.

재개는 완료된 `model_<it>.pt`를 `--resume_from`에 지정하고 `--max_iterations 1001`을 총 목표로 유지한다. `train_sol23f_common.py:107-122,183-220`는 부모 체크포인트와 SHA를 검증하고 별도 segment 폴더를 만든 뒤 `iter+1`부터 남은 회차를 센다. `start_runner.py:608-665`는 정책, PPO optimizer와 학습률, 지각 모듈, 지각 optimizer, AdaSmpl, terrain level/type와 명령 curriculum, RNG, 누적 갱신을 저장하고 로드한다. TopDown 환경의 `s2_23f_topdown_env.py:15-26`은 terrain sampler의 NumPy Generator 상태를 env hook으로 저장한다. `model_initial.pt`는 `sol23f_contract.py:64-78`에서 재개 부모로 거절한다.

반면 새 Kit 프로세스의 시뮬 물리 상태, 진행 중 episode, GRU의 환경별 활성 hidden과 관측 이력은 같은 시점으로 복원되지 않는다. `sol23f_runner.py:173-195`가 복원된 terrain 원점에서 새 물리 reset을 하고 `physical_resume_identical=false`로 기록한다. 따라서 **체크포인트의 학습 상태에서 새 segment를 이어 가는 것**이며 동일 궤적 재생은 아니다. 중간 마감과 그 부모를 사용한 실제 Kit 재개는 이번 두 10회 자료로 시험되지 않았다.

root가 실행을 결정할 때의 **인자 형태**는 다음과 같다. 기동 명령이 아니라 대조용이며, 체크포인트 경로와 재개 시각은 실제 저장 후 확정해야 한다.

```text
C:/Users/AI-WS01/anaconda3/envs/isaac311/python.exe foothold_s2/scripts/train_23f_topdown.py --headless --device cuda:1 --num_envs 3072 --seed 42 --max_iterations 1001 --map_input reconstruction --run_name ex29-td-main --end-by 2026-10-24T09:55:00+09:00
C:/Users/AI-WS01/anaconda3/envs/isaac311/python.exe foothold_s2/scripts/train_23f_topdown.py --headless --device cuda:1 --num_envs 3072 --seed 42 --max_iterations 1001 --map_input reconstruction --run_name ex29-td-main --end-by 2026-10-24T22:30:00+09:00 --resume_from <첫 segment의 완료 model_N.pt>
```

두 줄 모두 실제 감독기 환경, 작업 폴더, 승인과 GPU 자원 확인을 생략한 인자 대조다. 현재 B는 GPU 0에서 학습 중이며 GPU 1 동시 사용의 장기 VRAM과 USD/Kit 자원 경합은 이 읽기 검토로 확인되지 않았다. B 500 촬영의 시작 시각도 ETA이므로 TD 마감 상태 파일과 프로세스 종료를 root가 확인한 뒤 촬영해야 한다.
