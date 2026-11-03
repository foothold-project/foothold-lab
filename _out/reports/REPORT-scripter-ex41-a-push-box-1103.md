# EX-41 A층 밀기 상자 경계 정렬
> 분류: A/평가
> 작성: 오흥재 · scripter 반영 · 2026-11-03 14:10
> 근거: EX-41 model_10 세 지도 모드 촬영 원자료, 합성기 픽셀 시험, 전 프레임 검사
> 요지: 밀기 상자의 좌우 경계를 아래 지형·속도 패널과 같은 값으로 연결했다.
> 상태: CPU 합성 세 편 확인됨 · 본 저장본 적용 전

## 변경과 시험

- 합성기 `GAUGE_X0`, `GAUGE_X1`을 지형·속도 패널과 밀기 상자가 함께 쓴다. 상자 x 범위는 `[1084, 1272)`이며, 밀기 표시 중에는 원래의 더 넓은 범례 배경을 그리지 않아 왼쪽 돌출을 막는다.
- 답을 아는 픽셀 시험에서 아래 속도 패널과 밀기 상자의 첫 번째·마지막 픽셀이 같다. 밀기 상자를 왼쪽으로 5픽셀 옮긴 반례는 의도한 단언으로 검출한다. 변경 전 시험 2 FAIL, 변경 뒤 관련 시험 14 PASS.
- `eval_gt`, `eval_pred`, `probe_prop_only`를 기존 촬영 원자료에서 CPU 재합성했다. 각 영상은 1920×1080, 150프레임이며 전 프레임 검사 PASS, 문제 0건이다. 디코드한 62번 프레임의 상자 배경 x 범위도 세 편 모두 `[1084, 1272)`다.
- 밀기 크기와 회복 수치는 원자료를 그대로 사용한다. 밀기 강도의 표현 방식은 이번 범위에서 바꾸지 않았다.

| 지도 모드 | 새 영상 | SHA256 | 프레임 검사 |
|---|---|---|---|
| `eval_gt` | `D:\mai-tmp\scripter\ex41_a_push_model10_box_aligned\eval_gt\styled.mp4` | `5c83431273a673946b44862c503bcc0f4c041a7def6237e06be8db2abec9df67` | 150/150 PASS |
| `eval_pred` | `D:\mai-tmp\scripter\ex41_a_push_model10_box_aligned\eval_pred\styled.mp4` | `ff9ba4b9223e3686c2be9feab7752e9ac9decd97a103236f69278e2607f9f9ab` | 150/150 PASS |
| `probe_prop_only` | `D:\mai-tmp\scripter\ex41_a_push_model10_box_aligned\probe_prop_only\styled.mp4` | `d7122e0de40c6c2ad446ac1cd2d2e3ead3ffe92ef21124c4cf2522116f8c14fe` | 150/150 PASS |

CPU 집계 정본: `D:\mai-tmp\scripter\ex41_a_push_model10_box_aligned\summary.json`. 각 모드 폴더의 `styled.json`, `styled_frame_audit.json`, `frame_062.png`가 각각 영상 영수증·전 프레임 결과·픽셀 확인 그림이다. 합성기 SHA256은 `3f06d3d2220c2faff01ff028089055b65dc8d9d794faaa9dbc76d2fce6716e94`다. 이번 결과는 model_10 기능 시험이다. 본 저장본과 A층 촬영 주기는 별도 결정 대상이다.
