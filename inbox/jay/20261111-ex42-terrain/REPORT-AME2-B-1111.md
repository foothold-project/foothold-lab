> 분류: A/지형씬제작 · 연구 기록
> 작성: 오흥재 (scripter-lx) · 2026-11-11
> 근거: AME-2 Appendix A · CURRICULUM-GATES v0.16 E3/E4 · SPEC-ame2-go2 §1.6
> 요지: EX-42용 AME-2 Go2 혼합 지형 12종을 독립적인 메시 생성기와 CPU 계약으로 준비했다
> 상태: CPU 검증 완료 · Kit 메시 실측 전

# AME-2 묶음 B · Go2 혼합 메시 준비

## 구현

`foothold_s2/terrains/ame2_preset.py`는 `ame2_go2_mix_v1`의 12종 `KINDS`, 종류별 L0~9 치수, 시드 고정 박스와 높이 메시, 물리 구멍, 12 × 12 m 타일을 만든다. `measurement_generator(kind, *, seed)`는 JEPLO와 같은 `(TerrainGeneratorCfg, subcfg)` 계약을 내며 한 종류 1열과 10난도 행을 쓴다. `build_generator`는 부록 A의 12종 비율로 60열을 낸다. 현재 학습 cfg에는 등록하지 않았다.

sonnet의 작업 사본에 있는 `ex42_kit_measure.py:_generator_for`는 지금 C 계열 JEPLO만 분기하며 B 분기는 아직 없다. 이 PR을 합친 뒤 sonnet이 `from foothold_s2.terrains.ame2_preset import measurement_generator`를 B 분기에 연결해야 Kit 측정 사슬에서 이 생성기를 호출한다.

| 종류 | Go2 L0 → L9 | 근거와 구분 |
|---|---|---|
| stair_up · stair_down | 단 0.05 → 0.27 m, 디딤 0.30 m | SPEC §1.6의 공개 G1 수치, 논문은 경사 5° → 45° |
| rough | 잡음 전체 폭 0 → 0.16 m, 즉 U[−0.08,+0.08] m · 국소 경사 0 → 20° | SPEC §1.6의 G1 수치, 논문 ANYmal ±0.2 m · TRON1 ±0.15 m |
| boxes | 높이 0.05 → 0.30 m | 논문 TRON1 및 SPEC |
| obstacles | 밀도 0 → 0.5/m², 높이 0.2~2.0 m | 논문 밀도, SPEC의 장애물 높이 |
| climb_up · climb_down | 0.10 → 0.53 m · 0.20 → 0.60 m | CURRICULUM-GATES E4의 Go2 결정, 논문 최대 1.0/1.0 또는 0.48/0.88 m |
| consecutive | 두 턱 각각 0.05 → 0.30 m | E4 Go2 값, 논문 TRON1 상한 0.30 m |
| gap | 너비 0.18 → 0.70 m | E4 Go2 값, 논문 ANYmal 1.10 m · TRON1 0.60 m |
| pallets | 폭 0.40 → 0.16 m, 틈 0.08 → 0.35 m, 높이차 0 → 0.30 m | E4 Go2 값, 논문 ANYmal 값과 같음 |
| stones | 돌 변 0.71 → 0.41 m, 틈 0.08 → 0.12 m | E4 Go2 값, 논문은 Stones-Everywhere 참조만 |
| beam | 폭 0.90 → 0.18 m, rpy ±0.10 rad, 플랫폼 차 ±0.20 m | 논문 부록 A · E4 |

논문 원문은 [AME-2 Appendix A](https://arxiv.org/html/2601.08485#A-Terrain-Parameters)다. GPL-3 `ame2_minimal`은 수치와 동작 설명만 읽었다. 그 코드는 이 파일에 복사하거나 import하지 않았다. Go2 상한과 기하 배치는 팀의 결정 및 우리 구현이며 저자 재현으로 부르지 않는다.

## 실제 기하와 한계

계단은 0.30 m 단 폭에서 6단 후 평탄부가 이어지고, rough는 3 m 주기 국소 경사와 격자 잡음이다. 장애물은 양의 상자와 음의 함몰을 섞고, climbing은 단차 플랫폼, sparse는 충돌 메시 사이에 실제 빈 공간을 둔다. sparse 바닥은 시드 홀짝으로 물리 바닥 50 %와 충돌 없는 가상 바닥 50 %를 나눈다. **가상 바닥의 지도 전용 시각 표시는 아직 별도 렌더·지도 경로에 연결되지 않았다.** 저자 코드의 절벽 모서리 변형, 벽과 자세 분포, 실제 지형 성공률도 아직 맞춰 보지 않았다. 치수 계약과 CPU 메시 생성을 확인한 단계이며 Kit의 충돌·화면·관측 측정은 미확인이다.

## 확인

- isaac311 CPU: `test_ame2_preset_cpu.py` **18 passed**. 12종 L0/L9 치수, 시드 결정성, spawn 지지면, 희소 구멍과 바닥, 메시 유한성, 잘못된 레벨·시드·타일 반례를 확인. 갭을 가짜 박스로 메우거나 물리 바닥을 삭제한 돌연변이는 `validate_tile`이 거절했다.
- 실제 Isaac cfg를 CPU에서 import하는 시도는 `pxr`가 없어 `ModuleNotFoundError`로 끝났다. `TerrainGeneratorCfg` 구성과 충돌 동작은 Kit 측정 전까지 미확인이다. 이 실패를 CPU 통과로 세지 않는다.
- 산출은 코드와 보고서뿐이다. GPU·Kit·학습 실행과 운영 사본 변경은 하지 않았다.

## 01:34 검토 지적 반영

처음 판은 3 m 사인파 진폭에 `1.5·tan(20°)`를 곱해 실제 최대 미분 기울기가 20°를 넘었고, SPEC의 0.16 m **전체 잡음 폭**을 ±0.16 m로 잘못 읽었다. 수정판은 잡음 앵커를 U[−0.08,+0.08] m로 뽑아 3 m 간격에서 선형 보간하고 사인파에 기울기 예산 82 %를 배분한다. 0.1 m 메시의 각 삼각형 두 방향 높이 차로 실제 최대 기울기를 계산하는 시험은 L9·seed42에서 **19.139°**, 선언 상한 **20°** 안이다. L0은 평면이고 L5도 선언한 레벨별 상한 안이다. 독립 잡음을 각 격자점에 바로 얹으면 국소 기울기를 제한할 수 없으므로 보간을 사용했다. 이 형태는 우리 Go2 기하 선택이며 저자 생성기의 정확한 파형이라는 뜻은 아니다.
