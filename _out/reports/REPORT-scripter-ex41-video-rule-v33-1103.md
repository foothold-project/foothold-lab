# EX-41 A층 범례와 밀기 상자 공통 배치
> 분류: A/평가
> 작성: 오흥재 · scripter 반영 · 2026-11-03 14:22
> 근거: lead 14:2x 배치 지시 · model_10 기존 촬영 세 모드 · 합성기 픽셀 시험 · 전 프레임 검사
> 요지: 범례와 밀기 상자를 같은 188×150 픽셀 영역에 놓고 영상 판을 v3.3-D167로 올렸다.
> 상태: CPU 재합성 세 편 확인됨 · 본 저장본 촬영 계획 재고정 전

## 배치와 깨뜨려 보기

`compose_25e_v2style10.py:404`의 `LEGEND_RECT`가 범례와 밀기 상자 둘의 유일한 사각형이다. 실제 값은 `(x=1084, y=34, w=188, h=150)`이며 아래 지형·속도 패널은 y=192에서 시작한다. 범례 아랫끝 184와 패널 시작 사이 간격은 8픽셀이다. 글꼴 크기는 12를 유지하고 긴 범례 표지만 줄임말로 바꿨다. 밀기 화살표를 제목과 회복 문구 사이의 빈 띠로 줄였다. 밀기 전에는 범례를, 밀기 뒤에는 같은 사각형의 PUSH를 그린다.

픽셀 시험은 범례·PUSH·아래 속도 패널의 좌우 경계를 비교한다. 밀기 사각형을 왼쪽으로 5픽셀 옮기는 반례와 화살표를 아래 문구까지 늘리는 반례를 각각 검출한다. 지도 모드 셋 모두에서 범례 글자가 사각형 바깥으로 나가지 않는다. 설치 `isaac311`에서 관련 시험 `63 passed, 1 deselected`다. 별도로 기존 C층 계획 시험 하나는 이번 변경 전부터 `build_plan()`의 `gpu_jobs_tool`, `gpu_jobs_config` 필수 인자가 빠져 실패하며, 이번 배치 변경의 통과 근거로 세지 않았다.

## 원자료 재합성

세 영상 모두 `pyramid_stairs` L0 · env0 · model_10 기능 시험이다. GPU·Kit 재촬영 없이 기존 `review.mp4`, `review_feet.npz`, `push_events.json`에서 CPU 합성했다. 각 영상은 1920×1080, 150프레임, 영상 판 `v3.3-D167`이며 전 프레임 검사 0건이다. 합성기 SHA256은 `286ef00be498afbdb0c3009a0a73375f61906720709b4d03b0faa67afe800f69`이다. 밀기 강도 표기와 DR 원자료는 바꾸지 않았다.

| 지도 모드 | 영상 | SHA256 | 범례 정지 화면 · 밀기 정지 화면 |
|---|---|---|---|
| 정답 `eval_gt` | `D:\mai-tmp\scripter\ex41_a_push_model10_v33_aligned\eval_gt\styled.mp4` | `939bdd004fcad8f1bec3815d819da849200e790b98d0ca6c65598822525f5634` | 같은 폴더 `legend_frame.png` · `push_frame.png` |
| 복원 `eval_pred` | `D:\mai-tmp\scripter\ex41_a_push_model10_v33_aligned\eval_pred\styled.mp4` | `060dfe154474b8f47ddc259ff3017124a4fbc1e3a2a3d4a48a75b0c44ce7daf5` | 같은 폴더 `legend_frame.png` · `push_frame.png` |
| 끔 `probe_prop_only` | `D:\mai-tmp\scripter\ex41_a_push_model10_v33_aligned\probe_prop_only\styled.mp4` | `d45f634893c823522fa2c44f0e7723cb371677dadf8f4aefebe1594c582ccdbf` | 같은 폴더 `legend_frame.png` · `push_frame.png` |

결과 원장 `D:\mai-tmp\scripter\ex41_a_push_model10_v33_aligned\summary.json`; 각 폴더 `styled.json`은 판·합성기 SHA 영수증, `styled_frame_audit.json`은 150프레임 검사 결과다. `eval_gt`의 두 정지 화면을 직접 열어 범례·PUSH가 아래 패널과 같은 끝선에 놓이고 화살표가 회복 글과 겹치지 않음을 확인했다.

## 같은 합성기 소비 경로

| 경로 | 코드 근거 | 판과 파일 고정 |
|---|---|---|
| C층 대기열 | `foothold_s2/eval/c_layer_queue.py:101-103,455-477` | 계획의 `composer` 파일과 SHA를 대조하고 판·영수증을 확인한다. |
| W78 단계 영상 | `foothold_s2/eval/w78_video_consumer.py:105,207-221` | 지정 `composer`의 판을 읽고 영상 영수증 SHA를 확인한다. |
| A층 밀기 | `foothold_s2/eval/a_push_video.py:55-57,161-181` | 지정 `composer`의 판을 읽고 영상 영수증 SHA 및 전 프레임 결과를 확인한다. |
| 단계 끝 재합성 도구 | `foothold_s2/eval/ex40_v3_recompose.py:105-126` | 호출자가 넘긴 `composer`를 실행하고 영수증 판·SHA를 확인한다. |

네 소비 경로는 합성기 경로를 인자로 받는다. 현재 코드의 판 관문은 이전 `v3.2-D140`을 거절한다. 따라서 실제 C층·W78·A층·단계 끝 실행은 새 고정 사본의 `compose_25e_v2style10.py` 경로와 SHA로 계획 또는 요청을 다시 고정해야 한다. 현재 실행 중인 고정 사본과 계획은 수정하지 않았다. 단계 끝 운영 루프의 실제 argv가 새 파일을 가리키는지는 이 CPU 작업에서 미확인이다.
