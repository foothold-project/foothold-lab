# EX-41 밀기 영상 v3.4와 C층 GPU0 한 칸 확인
> 분류: A/평가
> 작성: 오흥재 · 2026-11-03
> 근거: 팀장 11/03 14:5x 지시 · 세 모드 재합성 영수증 · GPU0 C층 한 칸 원자료
> 요지: 회복 창 뒤 범례가 돌아오고 3D 밀기 화살표가 보이는 v3.4를 검증했다. GPU0에서 선택 로봇 분할이 한 칸 완주했지만 이전 실패의 하위 원인은 분리되지 않았다.
> 상태: 코드 및 CPU 영상 확인 완료 · C층 GPU0 원인 미확정

## 1. 변경과 계약

- `foothold_s2/eval/video25/push_event_overlay.py`: PUSH 상자는 이벤트부터 평가군 회복 시간 중앙값까지, 값이 없으면 1.5초까지만 보인다. 상자는 범례와 같은 사각형을 쓰며 붉은 바탕, 빨간 테두리, 흰 글을 가진다. 상자 화살표 선분의 중점은 상자 중심이다.
- `foothold_s2/eval/video25/compose_25e_v2style10.py`: 창 밖에서 범례가 돌아온다. 몸 위치와 저장된 카메라 자세에서 월드 XY 밀기 방향을 투영해 빨간 3D 화살표를 장면에 그린다. 화살표 길이는 밀기 속도 변화량에 비례하고 첫 0.16초에 원형 번쩍임을 그린다. 시작점은 몸 중심 위 0.20 m로 둬 몸통을 가리지 않는다. 원자료 `review_feet.npz/root_pos_w`와 `review.json/camera_screen_projection`가 있어 재촬영은 필요 없었다.
- `foothold_s2/eval/video_rule.py`: `VIDEO_RULE_VERSION=v3.4-D168`로 올렸다. 옛 판 영수증은 거절한다.
- 범례가 밀기 뒤 돌아오는 시각과 사각형 경계, 글과 화살표 비겹침, 3D 화살표의 창 안팎을 답 아는 입력 및 돌연변이로 확인했다.

## 2. 확인 자료

| 지도 모드 | 재합성 영상 | 전 프레임 검사 |
|---|---|---|
| 정답 `eval_gt` | `D:/mai-tmp/scripter/ex41_a_push_model10_v34/eval_gt/styled.mp4` | 150/150, 오류 0 |
| 복원 `eval_pred` | `D:/mai-tmp/scripter/ex41_a_push_model10_v34/eval_pred/styled.mp4` | 150/150, 오류 0 |
| 끔 `probe_prop_only` | `D:/mai-tmp/scripter/ex41_a_push_model10_v34/probe_prop_only/styled.mp4` | 150/150, 오류 0 |

각 폴더의 `styled.json`과 `styled_frame_audit.json`에 합성기 SHA와 판을 기록했다. 정지 화면 넷은 `eval_gt/legend_frame.png`, `scene_arrow_frame.png`, `push_box_frame.png`, `recovered_legend_frame.png`다. 화면을 직접 확인해 밀기 중 상자와 몸 위 화살표, 창 뒤 범례 복귀를 봤다. `isaac311` CPU 시험은 관련 묶음 55 PASS, 1건 제외(기존 plan fixture 실패), 최종 밀기 묶음 20 PASS다.

## 3. GPU0 기존 실패와 새 한 칸

- 기존 실패 원문: `D:/mai-tmp/c_layer_visibility_fix_v1/smoke_gpu0_out/attempts/pyramid_stairs_L0_eval_gt/01/child.log:279-285`의 `C76 robot instance mask missing subject or shows another robot`. 이는 첫 프레임 선택 로봇의 분할 마스크 관문 실패다. 기존 시도는 실패 packet을 저장하지 않아 실제 라벨 누락인지 픽셀 부족인지 분리할 수 없다.
- 새 코드에서는 같은 오류가 나면 분할 packet의 라벨 수와 선택 로봇 경로 수, RGB 화면을 `segmentation_failure.json`과 `segmentation_failure_rgb.png`에 남기고 그대로 실패하도록 했다. 임계치를 낮추거나 영수증을 수동 생성하지 않았다. 진단용 답 아는 CPU 시험 포함 13 PASS다.
- 새 계획 `D:/mai-tmp/scripter/c76_gpu0_v34_diag/plan_v2.json` SHA256 `6147d449ff5dc2cbd13c058e77db2631a545544f0e5b7688502c31afc3f4dd12`. 첫 호출은 더 높은 우선순위 학습 표식 때문에 `yielded_to_higher_priority`였고 Kit을 띄우지 않았다. 표식이 사라진 뒤 별도 출력 `D:/mai-tmp/scripter/c76_gpu0_v34_diag/out`에 GPU0 한 칸만 실행했다.
- 새 한 칸 결과: `pyramid_stairs_L0_eval_gt`, 시드 42, m6000, `state=complete`, 기술 실패 0. 원자료 450/450 프레임 오류 0, 합성본 450/450 프레임 오류 0. `review.json/robot_instance_evidence` 450행에서 선택 로봇 픽셀 최소 38,498, 다른 로봇 픽셀 최대 0이다. `out/receipts/pyramid_stairs_L0_eval_gt_success.json`과 `out/attempts/.../01`에서 되읽었다.
- 결론 범위: GPU0가 본질적으로 C층 분할을 못 한다는 가설은 이 한 칸에서 반박됐다. 이전 실패의 렌더 시점, 코드 판, 장치 동시 점유 가운데 어느 요소가 원인이었는지는 미확인이다. 이 한 번의 성공을 216칸 전체의 안정성으로 확대하지 않는다. 이 시험이 새로 만든 `C:/Users/AI-WS01/s2_lab/_playlists/EX40-C-m06000-all.m3u8`는 기존 파일 덮어쓰기가 아닌 새 파일이다.

## 4. 고정 코드와 해시

| 파일 | SHA256 |
|---|---|
| `compose_25e_v2style10.py` | `7407f7b68b8968847b9392817cb835fe9f5cf032b85aeeb7c1addfd4910a6c43` |
| `push_event_overlay.py` | `260d5ed6041b9efa1adae3ecf85cfbbade9783818240757aaadfb72ba9c1c2df` |
| `record_c_layer.py` | `62065369a64318a0f72318c3cf887cbf503ff088a26c324dea4ca0f0fd964c4c` |
| `c_layer_segmentation.py` | `c06479d19c6f3631992381e8d157b7a6b9357315d28dbf07be9bc29d4af8b957` |
| `video_rule.py` | `228d4826eb306c81ba3ecdf56e70eb449940c48712a92d3d901d429d7e549f25` |

코드 커밋은 `2a5886a1`, `cf05989c`, `e74402b5`다. 실행 중인 학습과 고정 촬영 사본은 고치지 않았다.
