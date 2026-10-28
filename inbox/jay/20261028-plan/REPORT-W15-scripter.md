> 분류: A/평가 · 일반화 벤치마크 · 지표
> 작성: 오흥재 (scripter 반영) · 2026-10-28
> 근거: WORKLIST W15 · 팀장 추가 지시 · RESEARCH-basic-gait-list.md §2 · 기존 eval_map_modes.py
> 요지: eval_pred와 64환경 지형별 기록에 후진·횡이동·대각·정지·회전 반전·재출발 칸을 연결
> 상태: CPU 시험 통과 · Kit/GPU 미실행 · 실측값·판정 없음

# W15 평가 사슬 CPU 구현

`run_sb_eval.sh`의 기본 모드를 `eval_gt,probe_prop_only,eval_pred`로 바꾸고 64환경 `map64` 호출에 `--command-suite extended`를 연결했다. 지도 없는 G0 호출은 기존처럼 `MODES=none`을 명시해야 한다. `eval_map_modes.py` 기본 `core` 인자는 기존 네 독립 칸을 보존한다. 사슬의 `extended` 인자는 기존 전진 두 칸·제자리 회전 두 칸에 후진 두 칸, 옆걸음 양방향, 전방·후방 대각 네 칸, 정지 한 칸을 더한다. 대각은 vx=±0.5, vy=±0.5, wz=0의 네 조합으로 고정했다. 이는 이번 평가 입력 선택이며 새 학습 범위나 합격선이 아니다.

64환경 각각에 지형 종류, 레벨, 열, 생존 표본 수와 최종 생존, 몸 좌표 vx·vy·wz 분해 오차, 명령 방향 이동 적분, 세계 좌표 경로 길이와 시작~끝 이동량을 기록한다. 종류별 및 종류×레벨별로 환경 수와 최종 생존 수, 이동 중앙값을 묶는다. **64환경은 평가 한 칸의 합계이며 종류마다 64환경이 아니다.** `terrain_tiles`와 배치 SHA를 모드·명령 사이에 대조해 배치가 바뀌면 중단한다. 종료된 환경에서 `env.step` 뒤 reset된 값이 섞이지 않게 그 step의 계측 마스크를 제외한다.

연속 sequence 세 개는 독립 reset 결과와 별도 `sequences` 필드에 기록한다. `spin_left_to_right`, `spin_right_to_left`는 각각 두 phase, `stop_and_restart`는 0→전진→0→전진 네 phase다. 전체 300 step을 phase에 나누고 phase 사이에는 reset하지 않는다. 각 phase의 세계 좌표 경로 길이와 순이동량, vx/vy/wz 오차, 최종 생존을 따로 남긴다. 첫 절반 명령 속도 도달 시각과 회전 부호 반응 시각은 **기술적인 응답 측정 정의**이며 통과 문턱이 아니다. 좌우를 합친 평균으로 대체하지 않는다. 시퀀스 뒤에는 지도 입력 GT 사용 횟수를 모드와 다시 대조한다.

결과 JSON은 임시 파일 쓰기·flush·fsync·replace 뒤에만 `MAPMODE_DONE`을 출력한다. 기존의 `json.dump(open(...))` 다음 즉시 `os._exit(0)`은 파일 flush가 보장되지 않아 이 경로에서 바로잡았다. 비유한 결과는 `allow_nan=False`로 실패한다.

CPU 검증: `C:/Users/AI-WS01/anaconda3/envs/isaac311-moects/python.exe -m pytest foothold_s2/tests/test_w15_map_mode_cells.py foothold_s2/tests/test_sb_eval_chain2.py::test_run_sb_eval_uses_task_and_modes_from_the_environment -q` 결과 6 PASS. `ruff check --select F`, `python -m py_compile`, Git Bash `bash -n`, `git diff --check`도 통과했다. 답을 아는 입력은 64환경 중 한 환경의 마지막 step 종료, 지형 영수증 누락, 역방향 속도 부호, 측방 속도 분해, 제자리 회전 이동량과 재출발 응답을 포함한다. Kit와 GPU를 실행하지 않았으므로 실제 지형 이름 매핑과 전체 실행 시간은 미확인이다. 기존 사슬 전체 시험 중 자식 shell을 강제로 종료하는 시험은 이번 작업에서 실행하지 않았다.

검토용 명령만 기록한다. 승인된 실행자는 GPU 여유와 기존 사슬 중복 여부를 확인한 뒤 사용한다.

```powershell
$env:TASK='FootholdS2-Go2-S2-SB-v0'
$env:MODES='eval_gt probe_prop_only eval_pred'
$env:COMMAND_SUITE='extended'
& 'C:/Program Files/Git/bin/bash.exe' 'C:/mai/wt/foothold-lab/scripter-w15/foothold_s2/eval/run_sb_eval.sh' cuda:1 '<checkpoint.pt>' '<new-output-dir>'
```

이 작업은 학습, 평가 Kit 실행, 성능 판정, 새 지형 난도 설정을 수행하지 않았다.
