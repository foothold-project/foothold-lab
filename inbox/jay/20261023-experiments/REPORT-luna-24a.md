> 분류: C/기록
> 작성: 오흥재 (luna 반영) · 2026-10-24
> 근거: lead 고정본 ea664f1e · recorder 5651b5f6 · foothold_s2/runners/start_runner.py · foothold_s2/runners/sol23f_runner.py
> 요지: 평가자료 시각화와 실제 학습 step 표본 기록을 분리한 CPU 도구
> 상태: CPU 예시 확인 · observer 학습 연결 및 simulator 출력 미확인

# LUNA-24a depth 및 height-map 시각화

## 결과물

- foothold_s2/eval/render_depth_compare.py는 기존 recorder의 RGB MP4, JSON, *_feet.npz를 읽어 새 동기화 MP4를 만든다. 입력 파일은 수정하지 않으며 출력 경로가 이미 있으면 중단한다. 이 도구 자체는 seq_video의 .done receipt를 검증하지 않으므로, 실행 전 원본 capture receipt를 별도로 검증해야 한다.
- 한 화면에 원본 RGB 보행 영상, depth 입력, GT 기준 지도, TR-Net rough, TR-Net refined를 배치한다. 각 지도에는 높이 단위 m와 공통 높이 범위를 표시한다. 정책 실제 입력은 NPZ의 map_use_gt로 정해 GT 또는 PRED로 표시하고 JSON의 요청 모드도 함께 적는다. 셀 단위 validity mask는 원자료에 없어 화면에도 미기록 상태라고 표시한다.
- 높이 지도는 512개 값을 32x16으로 reshape하고 X-depth/Y-lateral 축과 셀당 0.05 m를 표시한다. GT 센서 설정의 ordering은 yx이며 runner/TR-Net의 지형 배열도 32x16 view를 사용한다. recorder가 저장한 60x60 depth는 원시 거리 영상이 아니라 정규화된 network input이다. depth_aug.py의 near/far 값으로 0.2..3.0 m 축에 역변환해 표시하며 이는 원거리 clipping과 no-hit를 구별하지 못한다. 각 프레임에는 RGB 시각, 최근접 map 시각, 둘 사이 차이를 함께 표시한다.
- map_t에서 해당 RGB 시각에 가장 가까운 실제 map sample을 찾는다. 허용 범위를 넘는 경우는 영상을 계속 붙들고 있지 않고 오류로 처리한다. 따라서 결손 시각을 반복 표시해 연속 관측처럼 보이게 하지 않는다.
- CLI 예시: python -m foothold_s2.eval.render_depth_compare --video <verified-run>.mp4 --npz <verified-run>_feet.npz --metadata <verified-run>.json --output <new-output>_depth-compare.mp4

## 좌표 정합 확인

고정 recorder는 발의 world XY/Z, roll/pitch를 저장하지만 로봇 base의 world XY와 yaw 또는 quaternion 시계열은 NPZ에 저장하지 않는다. map은 로봇 yaw 정렬 좌표이며 map_t는 있지만 지도 원점의 world transform은 없다. 카메라 view는 매 프레임 robot 위치를 이용해 갱신하지만 해당 카메라 pose와 투영 정보도 파일에 기록하지 않는다. GT no-hit ray는 코드에서 -1 m sentinel로 바뀌지만 해당 값을 실제 지면 높이 -1 m와 구분할 별도 mask는 저장되지 않는다.

이 자료만으로 depth나 height-map을 로봇 주변의 바닥 또는 원본 RGB 위에 위치 정합해 그리는 것은 불가능하다. 본 도구는 정렬을 추정하거나 그럴듯하게 보간하지 않으며 별도 패널로만 비교한다. 월드 위에 그릴 때 필요한 추가 계측은 map timestamp마다 base root_pos_w XYZ와 root_quat_w WXYZ, 지도 origin/축 방향/resolution, RGB 카메라 pose 및 projection/intrinsics다. 당시 depth 카메라 extrinsics도 저장해 map, depth, RGB의 좌표 변환을 검증해야 한다.

## CPU 검증 및 근거 범위

- CPU known-input 시험 7개가 통과했다. sentinel 0..511 배열은 (0,0)=0, (0,1)=1, (1,0)=16, (31,15)=511로 복원했고, 25 fps 예시 frame t=0.12 s는 map t=0.10 s를 선택해 차이 0.02 s를 표시했다. depth 정규화 값 0, 0.5, 1은 코드 NEAR/FAR 기준으로 0.2, 1.6, 3.0 m에 대응했다. 수치 등급은 CPU 시험이다.
- 합성 RGB와 합성 NPZ를 임시 폴더에 만들고 실제 CPU ffmpeg로 5프레임 진단 MP4를 생성한 뒤 ffprobe로 재확인했다. 임시 산출물은 시험 후 제거했다. 수치 등급은 CPU 시험이다.
- 배열 shape, 범위, timestamp 수식은 고정 recorder 및 model source에 근거한다. CPU sentinel은 reshape 순서를 확인하지만, 실제 Isaac Lab ray-grid의 첫 cell 방향과 월드 orientation, 실험 NPZ 영상 동기화, 출력 외관과 사람의 해석은 측정하지 않았다. depth 값은 정규화 입력을 되돌린 표시값이며 원거리 clipping과 no-hit는 미확인 상태로 남는다. 수치 등급은 코드 계약이며 실제 simulator 동작은 미확인이다.
- 실제 로봇 주변 월드 overlay는 pose 원자료가 없어 미생성이다. 재구성 품질, GT 대비 오차, 보행 성공 여부를 이 보조 영상만으로 판정하지 않는다.

## 학습 시점 원자료와 평가 재생의 구분

- 고정본 record_sol23f.py는 adapters.load_policy로 저장 checkpoint를 불러 평가 episode를 새로 실행한다. 해당 MP4/NPZ는 checkpoint 재생 평가자료이며 원래 학습에서 policy가 본 입력 · 행동 시계열의 복원이 아니다.
- 기존 StepEvidence는 iteration 요약 JSONL로 종료 항목, 접촉 발 XY 이동속도 통계, 관절 자세 요약, 카메라 설정, action delay 등을 기록한다. MapStatsRecorder는 iteration별 GT/refined/실제 선택 지도 통계 평균을 남긴다. 두 경로 모두 학습 중 매 step의 depth2 · GT/rough/refined 배열 · 발 trajectory 전체를 보존하지 않는다.
- foothold_s2/eval/train_trace.py는 별도 명시 호출형 observer다. 호출자는 source를 training 또는 replay_evaluation으로 명시하고, perception에 tap을 연결한 뒤 rollout update/step 번호, 같은 시점의 환경 상태와 actor action을 전달한다. tap은 실제 perception.step의 depth2/tick/first/use_gt/GT 입력과 _advance에서 나온 rough/refined를 detach해 CPU 배열로 복사한다. observer는 terrain_type에 따라 고정 8 env를 결정적으로 분산 선택하고 update 0..24, 100..124 등의 window만 모은다. 각 update shard를 float32 NPZ로 원자 게시하고 SHA-256과 complete/incomplete 상태를 manifest에 갱신한다.
- 필수 trace field는 depth2(2x60x60), tick/first/use_gt, GT/rough/refined(각 32x16), root pos/quaternion, 발 위치/XY 속도/접촉, 관절 q/qdot, 실제 명령, terrain type/level, episode id/reset, actor action이다. step 수가 모자란 update는 incomplete, 일부 update가 빠진 window는 완료로 승격되지 않는다. 중도 종료 상태도 manifest에서 in_progress 또는 incomplete로 식별한다.
- 이 observer는 runner나 학습 코드를 수정하지 않으며 import만으로 동작하지 않는다. root가 학습 loop의 실제 perception.step 전후와 actor action이 준비된 지점에서 연결해야 한다. 새 training/Kit/GPU 실행과 실제 관측 기록은 없고, source 구분 및 shard 계약만 CPU fixture로 검증했다.
- 연결 순서는 attach_perception(runner.perception), 매 rollout의 begin_update(it), 각 alg.act 이후 env.step 전에 capture_step(it, step_k, env_fields), rollout 완료 후 end_update(it), 종료 시 close()다. perception tap이 제공하는 입력/지도 snapshot은 observer가 env_fields와 병합하므로 root는 같은 env 상태와 actor_action만 넘기면 된다.
- 렌더와 observer 시험을 합쳐 CPU 15개, 기존 recorder/seq_video 계약 회귀시험 24개, 총 39개가 통과했다. 수치 등급은 CPU 시험이다.
