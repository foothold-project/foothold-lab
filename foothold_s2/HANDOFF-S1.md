> 분류: A/정책학습 · 구현 인계 (SC-3 START 시험지 · SC-4 S1-a 코드)
> 작성: sonnet-code 세션 (10/20 10:50, 컨텍스트 83 % 에서 단위를 끊음)
> 근거: 설계 커밋 28114f68 (14 · 15 · 16 · 17 · 52 · 13 · 18 · APPROVED-DIRECTION, 이 사본에 병합됨), lead 의뢰 SC-3 · SC-4
> 요지: SC-3 START 시험지는 Kit 연결 · 미리보기 · 측정 1 차 완료, 10 인스턴스 재측정이 GPU 에서 대기 중. SC-4 S1-a 는 순수 계산(명령 · 승급 · 열 배정 · 보상 · Go2 모델) L0 56 통과, Kit 쪽 모듈(명령 term · 승급 term · 지형 cfg · env cfg · 등록)은 아직 안 씀
> 상태: 진행 중 · 본 학습 안 함 · L1 은 lead 검수 뒤

# 인계

## SC-3 START 시험지 (GPU 측정 중)
- 미리보기: `evidence/baselines/start_preview/` (4 종 레벨 9 그림 + 전체 4 x 4 그림). Kit 메시에서 읽은 치수가 논문값과 맞음(징검돌 돌 0.2 · 구덩이 76.2 %, 평균대 폭 0.175, 디딤 빔 0.15 · 0.275 · 64.2 %, 틈 0.7).
- 1 차 측정(`eval_new/start/<판>/`, 칸 하나당 판 100, 칸 인스턴스 1 개): E1 R 0.074 (4 종 평균), v2 0.383, NVIDIA 는 끝났으나 표 미작성. **한계**: 같은 (종류, 레벨) 판들이 칸 하나(구덩이 깊이 · 돌 배치 하나)를 공유해 레벨별 값이 칸 하나의 운에 끌림(v2 틈 레벨 4~8 R 0 인데 레벨 9 R 0.99). Wilson 구간이 과소.
- 재측정: 종류 x 레벨마다 독립 칸 10 개(인스턴스), 칸당 10 판 = (종류, 레벨)당 100 판. 대기 스크립트 `eval_new/start10_all.sh` 가 smoke2(`eval_new/start_smoke2`) 통과를 보고 E1(GPU 0)→NVIDIA(GPU 0) · v2(GPU 1) 를 `eval_new/start10/<판>/` 에 돌림. 끝나면 `eval_new/start10/done.txt`. 표는 `python -m foothold_s2.eval.start_tables --root eval_new/start10 --out <폴더>` 로 만들고 evidence/baselines 에 복사 + README 갱신 + lead 보고.
- MEV 는 이 실행에서 안 재(발 디딤 위치 미수집). 주파율은 `crossing_ratio`.
- 코드: `foothold_s2/eval/` 의 `start_preview.py` `start_tables.py`, `run_eval.py start`, `terrain_sets.start_generator(instances)`, `assign_tiles`.

## SC-4 S1-a 코드: 한 것 (L0 56 통과, 전체 pytest 122 통과, pyflakes 0)
- `foothold_s2/commands/mixed_core.py` (torch): 자유 속도 표집 · 모드 비율(정지 > 회전 > heading > 자유 wz, 1,000 회 전후 플래그 0.333 / 0.417) · heading 식 · 깃발 상태기계(직선 4 깃발, 0.5 m 도달, 마지막 2 s 정지, 제자리 회전 v < 0.3, 물러나기) · 범위 커리큘럼 · 노출 로그. 시험 `tests/test_commands.py` 23.
- `foothold_s2/curriculum/rules.py`: 승급 · 강등(자유 속도 · 깃발). `terrains/columns.py`: Isaac 고정 배치 식으로 열 수 계산, `terrains/progression.py`: p_advance(S1-b 용). 시험 `tests/test_terrains_curriculum.py` 12.
- `foothold_s2/robots/go2_params.py`: 종아리 DCMotor(45.43 · 15.70) · PIE 범위 · `dc_motor_clip`. 시험 `tests/test_go2_model.py`: 설치 Isaac Lab `_clip_effort` 소스를 AST 로 꺼내 CPU 에서 실행해 ASTRA 표(+100: 45.43 · 22.715 · 0 · −12.443, −100: 전부 −45.43)와 대조, URDF 관절 12 개가 8 + 4 로 갈리는지, URDF 종아리 값 일치.
- `foothold_s2/rewards/core.py` (14 항 식 + 가중치 표, B 식, S1 발 가장자리 0) 시험 `tests/test_rewards.py` 11. `rewards/start_rewards.py`(Isaac 보상 cfg, **Kit 에서 import 시험 안 함**).

## SC-4 Kit 쪽 모듈 (10/20 오후 작성, L0: pytest 133 통과 · AST 이름 대조 11 · pyflakes 미사용 import 외 0)
- `commands/mixed_command.py` (MixedVelocityCommand): env 번호 % 5 == 0 이 깃발 env, reset 때 기록 · 깃발 갱신, `max_dist` `cmd_sum_xy` `goals` `iteration`. S2 는 `flag_provider` 로 깃발 목록을 갈아 끼움.
- `curriculum/terrain_levels_mixed.py`: `terrain_levels_mixed`(rules.judge 호출, cmd 합을 재추출 단위로 환산), `command_range_curriculum`(반복당 한 번 vmax 올림).
- `robots/go2_cfg.py`, `terrains/rough_go2_cfg.py`(23 열, `build_generator` 는 S1-b/S2 가 비율만 바꿔 씀), `tasks/mdp_extra.py`(발 접촉 관측 · 발 지면 아래 종료), `tasks/s1_env_cfg.py`(Scan/Blind, S2 는 상속), `tasks/agents/s1_ppo_cfg.py`, `tasks/__init__.py`(등록 `FootholdS2-Go2-S1a-scan-v0` · `-blind-v0`), `train_s1.py`(설치 train.py 를 읽어 우리 task 등록 줄만 끼워 실행).
- `tests/test_kit_names.py`: 설치 Isaac Lab 소스와 `mdp.X` · import · `params` 키 대조(없는 이름을 넣으면 걸림을 확인).
- **Kit 에서 처음 도는 것(미확인, L1 에서 드러날 것)**: 충돌 링크 이름 `Head_.*`, 정확한 `history_length` 관측 크기(495), `sky_light=None`, 발 지면 아래 종료의 스캔 점 조회, 명령 term reset 순서.
- 다음: lead L0 검수 → L1(GPU 0 scan · GPU 1 blind 첫 10 update, Traceback 0, steps/s, 메모리, env별 명령 방식 로그).

## 해석 · 문서와 다르게 한 곳 (lead 확인 필요)
- **S1-a 열 수 23**: 이어진 지형만 학습하면 Isaac 이 비율을 합 1 로 정규화해, 15 §2 의 50 열이면 비율이 정수 열로 안 떨어짐(50 열에 이어진 7 종만 배정 시 10.87 열 등). 23 열은 정수(5 5 4 4 2 2 1). 50 열 전체 혼합(S1-b · S2)은 `columns.FULL` 로 시험함.
- 14 §9 의 「1,000 표본 ±0.03」 은 비율 0.5 에서 1.9 시그마(우연히 약 6 % 실패)라 시험은 1,000 표본 ±0.05, 20 만 표본 ±0.005 로 이중화.
- 17 §9 의 「+21.67」 은 식으로 21.655 (문서 반올림).
- 시스템 지연 0~15 ms · 모터 세기 배율은 DCMotor 로는 구현 안 함(DelayedPD 가 필요) → 열린 항목. 초기 관절 0.5~1.5 단위 열린 채 Isaac 기본 유지.
- critic 관측(S1)은 문서에 없음: o_t + 몸 선속도 3 + 발 접촉 4 (가정).
- START 4 종은 8 x 4 m 칸이라 축 3 옆 · 뒤 명령을 못 잼(앞서 보고).
