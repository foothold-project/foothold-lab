> 분류: A/평가 · 일반화 벤치마크 · 지표
> 작성: analyst-lx · 2026-11-13 10:43
> 근거: lead 10:39 전체 axis-v2 재측정 지시 · m2000 seed 42 원영수증
> 요지: 같은 코드 · 메시에서 seed 7/13의 Y1 반복 폭 측정 명령. 실행은 lead.
> 상태: CPU 준비 · GPU 미실행

# m2000 Y1 시드 반복 측정 명령

G1/G1b가 두 GPU에서 끝난 뒤 lead가 한 번 실행한다.

```bash
bash /home/jay/mai/wt/foothold-lab/analyst-lx-jeplo-c/inbox/jay/20261113-analysis/run_m2000_axis_seed_repeats.sh
```

시드 7은 cuda:0, 시드 13은 cuda:1이다. 각 시드에서 GT · PRED, L2, 64 env, 300 step, 전체 axis-v2 10명령을 순차 실행한다. 합계 40개 명령·모드 칸이다. 출력은 운영 run 밖인 `/home/jay/data/foothold/s2_lab/e1_yaw_repeat_20261113/m2000_<실행 시각>/seed7`과 `seed13`이다. argv · stdout · stderr · 종료 코드를 함께 남긴다. 코드 · 학습 · 기존 평가 파일을 바꾸지 않는다.

| 고정 대상 | 원자료와 같은 값 |
|---|---|
| 평가 사본 | `ex42-launch-e1-v6`, HEAD `c7692789eb7ce1d61d6530b1aa83be4f3ba6ab67` |
| model_2000 | `3937df92866b79581f7b27e8b8c9fbde1f7733a85fe5179388fcfd78aa83c4bb` |
| 메시 배열 해시 | `seed42_E0_c333`, `88197b3adfdde327edc633c025c6ad9aa690ea59aa7df5d51d548f7f56c12a95` |
| NPZ 파일 해시 | `b3e6ab6f5093cc78ad2cbb8848d8caa2969ad44774ad7889d5e16d1d8ed7734d` |
| 평가 plan | `c23a2325b70cb97ecf3c7f819b66967d19d0b3e271221d38431580b4f0699e61` |
| 마찰 · 무작위화 | 정답 영수증 기준 정적 0.8 · 동적 0.6, DR off |
| 원자료 | `ex42_main_20261112_164150/main/EX-42-B-E1-cmd7seg_20261112_164150/eval/scores/m2000/axis_v2/axis_v2.json` |

**확인됨:** 원영수증의 평가 소스 5개 SHA와 위 고정 사본이 모두 같다. G1/G1b 사본을 그대로 쓰면 고정 메시 없이 다른 지형에서 Y1을 재게 되므로 이 명령은 원영수증의 메시와 `--ex42-maintenance`를 보존했다. CPU 확인은 같은 스크립트 뒤에 `--check-only`를 붙인다. 이 모드는 Kit를 시작하지 않는다.

Y1은 `yaw` NPZ의 env별 시작 방향 대비 끝 방향 변화로 다시 센다. `median(abs(net yaw))`, signed median, p90을 따로 적고, 정지 후 리셋 표본은 버린다. `map64.yaw_follow_median`의 단위 rad/s를 누적 방향 변화 rad로 바꾸어 부르지 않는다.

**미확인:** 새 GPU 실행 시간 · 결과. 기존 m2000의 cuda0 두 모드 axis-v2 자식은 287.676초였으나 GT+끔이었으므로 이번 GT+PRED 두 모드의 ETA로 확정하지 않는다. 근거는 `.../eval/scores/m2000/shards/cuda0/children/axis_v2/child.json`이다.

S2는 별도 주의가 필요하다. 현재 G1b 반복은 옆 ±0.4 m/s, L0/L5다. planner S2의 ±0.5 m/s, L2 반복 폭으로 대신 쓰지 않는다. 같은 칸의 반복 자료가 오기 전 그 수치는 미측정이다. 세 시드의 최솟값~최댓값은 관측된 반복 범위이며 95% 신뢰구간이나 독립 학습 시드 성능은 아니다.
