> 분류: A/평가 · W56의 W15 근거 칸
> 작성: analyst · 2026-11-07
> 근거: 대기열1079 · W15 반복 원자료 · scripter 비교기
> 요지: 같은 코드의 전체 평가가 끝나기 전에는 분할 동등성을 확정하지 않는다.
> 상태: 1079 실행 중 · 후속 완료 영수증 대기

# W15 · 전체 평가와 분할 평가 대조

현재 결과는 **대기**다. 1079는 `D:/mai-tmp/gpu/queue.json`에서 GPU1·실행 상태이고, 완료 결과 `D:/mai-tmp/gpu/results/item_1079.json`은 아직 없다. 결과 파일이 만들어져도 완료 상태·회차·저장본 SHA·코드·지형 배치·시드·장치가 맞는지 확인한 뒤 비교한다.

지금 확인된 것은 선택한 두 칸(`eval_gt/stairs_side_left`, `probe_prop_only/flat_fwd1.0`)의 같은 코드 세 번 반복에서 숫자 변동이 없었다는 결과다. 각 칸은 L2/L5와 시작 방향 0/30/60/90을 포함한다. 이것을 모든 W78 칸의 반복 폭0으로 확대하지 않는다. 옛 전체412는 코드가 달라 조각 효과만 비교하는 자료로 쓸 수 없다.

완료 뒤 들어갈 것: 1079 rc·실제 소요시간·완료 JSON SHA, 같은 코드 전체/조각의 공통 숫자·키 차이·반복 폭 밖 수·생존 차이, 최종 G11 연결을 별도로 확인해야 하는 범위. 보고자의 판정만 옮기지 않고 원자료를 CPU로 다시 센다.

- 전체 출력: `D:/mai-tmp/scripter/w15_noise_1107/full_same_code/terrain_skill_v2.json`
- 기존 조각: `D:/mai-tmp/scripter/w78units/m750/units/`
- 반복: `D:/mai-tmp/scripter/w15_noise_1107/repeat2/`, `repeat3/`
- 이전 집계: `D:/mai-tmp/scripter/W15-repeat-comparison-1107.json`
- 비교기: `D:/mai-tmp/scripter/w15_compare.py` (`--self-test`, 이어 `--full`로 새 전체 파일 지정)

이번 문서는 GPU 작업을 등록하거나 기존 프로세스를 바꾸지 않는다.
