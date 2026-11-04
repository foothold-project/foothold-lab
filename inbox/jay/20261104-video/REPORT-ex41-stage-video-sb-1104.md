# EX-41 단계 끝 영상 SB 기록기 연결

> 분류: A/평가
> 작성: scripter · 2026-11-04 12:44
> 근거: EX-41 m750 요청서 · gpu_jobs 원장 · Kit 자식 영수증 · CPU 시험
> 요지: A층 밀기와 W78 계단 영상을 SB 기록기로 연결하고 실제 첫 촬영을 확인했다.
> 상태: 확인됨 · W78 나머지 11편 대기열 진행 중

## 수정과 고정

| 항목 | 증거 |
|---|---|
| 원인 1 | `ex41_eval_once.py`가 A층 소비기가 받지 않는 `--headless`와 `--kit_args`를 붙여 argparse rc 2. |
| 원인 2 | A층과 W78이 SB 저장본을 B/TD 전용 `record_sol23f.py`에 넘겨 preflight 실패. |
| 고침 | A층 소비기에는 평가기 전용 Kit 인자를 붙이지 않고, 두 소비기 모두 SB를 받는 `record_c_layer.py`의 정확한 경로를 확인한 뒤 사용. 기록기 자체에는 `--headless --enable_cameras --livestream 0` 적용. |
| W78 자식 환경 | `recorder_child_env`의 실제 함수 계약에 맞춰 호출하고 고정 소스 루트를 `PYTHONPATH`에 넣음. |
| 구현 커밋 | `230cc44e2805021c3c73bd05e68547f9cdd72e03`, `54e393a575e268bf1afdbe21f9c1b8aca8266c9c` |
| 실행 고정본 | `D:/mai-wt/foothold-lab/ex41-video-sb-54e393a5`, HEAD `54e393a5` |

## 시험

- `isaac311` CPU: `test_w78_video_consumer_cpu.py`와 `test_ex41_score_watch_cpu.py` 39 passed, `test_a_push_video_cpu.py`와 `test_ex41_eval_once_cpu.py` 10 passed. 임시 폴더는 `D:/mai-tmp/scripter`.
- 실제 m750 저장본 SHA `575655db49e475e171c0a85a859ae4d261cac83814aee2a18be76d6711558e46`와 요청서 `request_m00750_71ff36997456.json`으로 두 소비기 `--plan-only` 및 실제 argparse preflight 통과. 영수증 `D:/mai-tmp/scripter/ex41_video_sb_54e393a5/preflight.json`.
- A층 gpu_jobs item 163: 정답 · 복원 · 끔 세 모드 rc 0. 각 150프레임 원영상 · 합성 영상 전 프레임 검사 PASS, issue 0, 영상 SHA 일치. 영수증 `D:/mai-tmp/scripter/ex41_video_sb_54e393a5/a_push_m750/{eval_gt,eval_pred,probe_prop_only}.json`. 세 모드 모두 밀기 t=2.0 s, 회복 중앙값 각각 1.29 · 1.08 · 1.17 s. 이는 같은 저장본의 기록값이며 독립 성능 판정이 아니다.
- W78 gpu_jobs item 162: `L5_a000_eval_gt_stairs_fwd` 첫 영상 rc 0, v3.4-D168, 원영상 150/150프레임 PASS, issue 0, 영상 SHA 일치. 영수증 `D:/mai-tmp/scripter/ex41_video_sb_54e393a5/w78_m750/receipts/71ff36997456f9eca830bc6cb3a7d15e1e21709601dd7e9b27083094191f7d1a/L5_a000_eval_gt_stairs_fwd.json`.
- W78 나머지 11조합은 gpu_jobs item 164~174, priority 2, kind render, cuda:1로 등록. 각 item은 조합별 영수증 파일을 완료 조건으로 삼는다. 등록 시점 첫 두 item 164는 완료, 165는 실행 중이고 166~174는 대기 중이다. 최종 12편 완료 여부는 현재 미확인.

## 실행 이력과 남은 확인

초기 item 158은 정답 지도 원영상에서 `render_still_dark`로 실패했고 item 159는 자식 환경 함수 인자 오류로 실패했다. 수정 뒤 item 160과 161은 잘못된 이전 출력 경로를 재사용한 등록 명령 때문에 실패했다. 새 출력 루트와 영수증 경로를 단언한 item 162와 163으로 다시 실행해 위 실제 통과를 확인했다. 이전 산출과 실패 영수증은 보존했다.

W78 item 164~174의 모든 영수증과 영상 SHA, 전 프레임 결과는 대기열이 끝난 뒤 다시 확인해야 한다. 학습 사본 `ex41-launch-2ee5dc00`과 운영 원장은 수정하지 않았다.

## 코드 SHA256

| 파일 | SHA256 |
|---|---|
| `foothold_s2/ex41_eval_once.py` | `8a6b2d10972dfa3ea3bffe8de7a351f62142c8f043e7267c6bb23806605be11e` |
| `foothold_s2/eval/a_push_video.py` | `356e96dc5d8001dfc3f6ad77faf2ff50b46e9a76545dcefd53a89b4eb23295e3` |
| `foothold_s2/eval/w78_video_consumer.py` | `8da2569036e62d41ad98cf4422ea3b117346b00bfd7d6c2c030cf32d8479ded4` |
| `foothold_s2/eval/video25/record_c_layer.py` | `62065369a64318a0f72318c3cf887cbf503ff088a26c324dea4ca0f0fd964c4c` |
