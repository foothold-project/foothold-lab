SOL-26a CPU 결과 문서 생성기를 준비했다. 작업 폴더는 `C:/mai/wt/foothold-lab/lead_tmp-20261023/inbox/jay/20261026-experiments/figs/ex32-g0b/`, 보고서는 같은 `20261026-experiments/REPORT-sol-26a.md`다.

G0-B와 B1500 TensorBoard의 보상 항·길이·지형 레벨·PPO/phi KL·action std·value loss를 같은 갱신 축에 겹쳤다. G0-B m550~m1500 각 저장본의 64환경 전진/회전/생존과 16환경 여섯 경우 평균 요 속도·네 발 동시 접촉을 원본 JSON/NPZ에서 표와 그림으로 계산한다. m1500 보행 위상 네 경우는 평가가 생기면 계산하고, 현재 없는 값은 `평가 전`으로 둔다. 영상이 없어 출발선 최종 판정은 보류한다.

답을 아는 입력인 B1500 여섯 경우는 기존 `six_table.py`의 6개 반올림 값과 모두 일치했다. 결측 평가 보류, S-B 두 평가 모드·지도 켬/끔 분리, 지형 SHA 변이 거절을 CPU에서 확인했고 `ruff check --select F`가 통과했다. 실제 S-B `map_switch.jsonl`도 같은 생성기로 읽어 on/off 곡선을 만들었으며, 평가 원본이 아직 없으므로 S-B 평가 칸은 보류했다. 학습·평가 원본은 읽기만 했고 GPU·Kit·학습·커밋·push를 실행하지 않았다.

G0-B 평가와 영상이 끝나면 `& C:/mai/wt/foothold-lab/lead_tmp-20261023/inbox/jay/20261026-experiments/figs/ex32-g0b/rerun_g0b26a.ps1`로 CPU 집계를 다시 만들 수 있다. 이 명령은 표·그림·보고서와 SHA 목록을 함께 갱신한다. S-B의 실제 평가 폴더 배치는 실행 후 확인하여 `--expected-modes`, `--turn-layout`, `--g0-reference-map` 인자로 연결해야 한다.
