# D137 영상 지도판 반영
> 분류: A/평가 · 일반화 벤치마크 · 지표
> 작성: 오흥재 · 2026-11-02
> 근거: 팀장 D137 · `D:/mai-tmp/mockups/mockups.py` · EX-40 m6000 원자료
> 요지: C층 합성 지도판의 최소 색 범위를 ±5 cm로 하고 attention 128칸을 고정 눈금으로 표시한다.
> 상태: CPU 확인 · EX-41 영상 결선 미확인

## 변경

| 자리 | 내용 |
|---|---|
| `foothold_s2/eval/video25/compose_25e_v2style10.py` | 정답 지도의 중앙값을 중심으로 한 공통 색 범위의 반폭을 최소 5 cm로 고정. 세 지도에 같은 범위를 쓰고 실제 양 끝 수치를 m 단위로 표시. attention 16×8 토큰 모두를 32×16 지도에 표시. 눈금은 매 프레임 0.00~0.30 고정, 초과값은 끝색. 발 표시는 기존 코드 그대로. 출력 영수증에 범위 기록. |
| `foothold_s2/eval/video25/record_c_layer.py` | 캡처 metadata에 합성 계약을 기록. 기존 캡처의 `gt_map`, `refined_map`, `attention_rows_per_step`만으로 재합성 가능. |

EX-41 단계 끝 영상 전용 촬영 및 합성 기동 코드는 조사한 `runner-ex41-b7-fixed/foothold_s2`에서 발견하지 못했다. EX-41 원자료가 동일한 `review.mp4`, `review.json`, `review_feet.npz`, `review.done` 형식이고 attention 128칸을 포함한다면 이 합성기를 그대로 쓸 수 있다. EX-41 영상 원자료 및 실제 결선은 미확인이다. 새 학습 또는 Kit 실행은 하지 않았다.

## 확인

- 알려진 입력 CPU 시험: 관련 40 passed. 지도 ±5 cm 끝색, 128칸 방향, 0.30 초과 포화, NaN 거절을 포함.
- `ruff check --select F`: 통과. `git diff --check`: 통과.
- EX-40 m6000 기존 원자료 `EX40-B-pyramid_stairs_L1_env23-m6000-fwd_back_eval_pred-1x`의 150프레임을 D:에 재합성. 해독 및 영수증 통과, 프레임 그림을 직접 판독. 출력 `D:/mai-tmp/scripter/d137-preview.mp4`, SHA256 `76233f10726dba2405c8f71ee0adc6f84ff0a572241707a0f3b9347f1cddc1e1`.
- 기존 C층 계획 `C:/Users/AI-WS01/s2_lab/c_layer_m6000/plan.json`은 이전 합성기 SHA를 고정한다. 적용 시 lead가 새 SHA로 계획을 다시 고정해야 한다. 이 실행 계획과 진행 중 작업은 수정하지 않았다.

## 파일 SHA256

| 파일 | SHA256 |
|---|---|
| `foothold_s2/eval/video25/compose_25e_v2style10.py` | `569acdaa69a30bfdbbcf5b37c63c302b1966693cdfb72a89d4641493653088ed` |
| `foothold_s2/eval/video25/record_c_layer.py` | `96014f8d5f3bd30a35099b83e0f637fed3b983a7ca2d517d0930595d2217306b` |
| `foothold_s2/tests/test_d137_map_panel.py` | `d986317b7dd48ed99ca8ec53a1ba585aa1a4665002c8393154d74351beb0179b` |
