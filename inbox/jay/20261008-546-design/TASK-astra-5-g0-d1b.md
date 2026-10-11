> 분류: 검증 의뢰 (ASTRA 5)
> 작성: 오흥재 (lead 세션 · Claude 작성) · 2026-10-11
> 근거: 팀장 10/10 「ASTRA 와 Top-down 으로 로컬 실험」 · `VERIFY-astra-4.md` 4절 gap 단락 · `DESIGN-astra-rl-topdown.md` 4절 G0 · D1 · G1 · `eval-g0/G0.md`
> 요지: G0 에서 legacy 관측이 no-hit 칸을 1 m 벽과 같은 -2.5 로 읽는 반전을 확인했다. D1-B (gap) 를 하기 전에 고정할 조건 여섯을 ASTRA 가 정한다
> 상태: 의뢰

# ASTRA 의뢰 5 · G0 검증 + D1-B (gap) 실행 조건 고정

**읽기 전용.** 결과는 `inbox/jay/20261008-546-design/VERIFY-astra-5.md` 새 파일 하나. 커밋 · push 하지 않는다.

**읽을 것:** `eval-g0/G0.md` (전부) · `VERIFY-astra-4.md` 4절 · DESIGN 4절 G0 · D1 · G1 (150~168 행). 원자료는 `C:/isaac/ext/go2_rl_robotlab/_eval/out/g0_probe/` 와 `out/G0-fixture.json`.

## 사실 (lead 가 코드에서 다시 확인)

- 식: `pos_w.z - ray_hits_w.z - 0.5` → clip (-1, 1) → × 2.5. no-hit 은 inf 라 -2.5. 1 m 높이 면도 -2.5. 바닥 있는 깊은 구멍은 +2.5
- 대입안 (no-hit → 식 단계 +1 → 최종 +2.5): CPU fixture 15 건 · GPU 실제 레이 617 만 개에서 finite 차 0 · 비유한 0
- 학습 지형 8종 (난이도 0~1 · tile 경계 포함) 레이 약 488 만 개에서 no-hit 0. 평가 전용 mesh gap 열에서 51,936 · 25 m 테두리 밖 15,250 · NaN 0
- Isaac Lab `gap_terrain` 은 틈 아래 바닥이 없다. 이 설정의 `stepping_stones` 는 구멍을 만들지 않는다 (`hf_terrains.py:383` 정수 자르기)
- 평가 하네스는 발밑 레이가 모두 no-hit 이면 `ground_z` 가 NaN 이라 「지지면 아래」 낙상을 못 센다
- probe 자세에서 finite hit 가 ±2.5 로 포화된 레이도 0. 즉 -2.5 · +2.5 둘 다 E1 teacher 가 학습 중 거의 못 본 값일 수 있다 (추정)

## 물음

1. **G0 판정.** 위 결론과 시험이 G0 수치 판정(finite ≤ 1e-6 · no-hit 설계값 · 비유한 0)을 닫는가. 빠진 시험.
2. **D1-B 조건 여섯을 정해 달라.** 각 항목에 값 또는 정하는 규칙을 적는다.
   - (1) encoding: E1 teacher 평가를 legacy 로 할지 · 대입으로 할지 · 둘 다 별도 이름으로 할지. E1 원본과 이어 붙이지 않는 표기
   - (2) gap 기하 동결: 폭 · platform · 진입 방향 · 시작점 · 명령 · 지형 시드 · 바닥 유무
   - (3) 무접촉 추락 판정 정의 (발밑 전부 no-hit · base 높이 · 속도 기준) 와 답을 아는 궤적 시험
   - (4) 발 착지 계측기: 이번 D1-B 에 넣어야 하는 최소 항목, 없이 할 때 결론 범위
   - (5) 희소 발판 (stepping stones) 을 넣을지 · 넣으면 구멍이 생기는 평가 전용 설정 확인 절차
   - (6) validation / holdout 분리 (지형 시드 · 기하)
3. **순서.** E2 는 10/12 낮에 끝난다. D1-B 를 E1 로 먼저 할지, E2 와 같이 할지. 그리고 G1 (학습에 gap 노출) 의 encoding 결정이 D1-B 결과를 기다려야 하는지.

## 형식

머리 다섯 줄 · em dash 금지 · 확인됨 / 추정 / 미확인 구분 · 판정 한 줄 (진행 / 고친 뒤 진행 / 안 닫힘). 계약 변경은 제안으로 쓰고 팀장 확정 필요 항목을 따로 묶는다.
