> 분류: C/기록 · 2026-10-24
> 작성: 오흥재 (luna 문서 반영) · 2026-10-24
> 근거: lead 요청 · record_sol23f.py · seq_video.py · ex23r_500 영상 원장
> 요지: EX23와 B의 model_500 flat/rough 네 영상을 영수증과 조건 대조 뒤 2x2로 합치는 CPU 도구
> 상태: CPU 알려진 입력 검증 완료 · 실제 B 입력 대기

# LUNA-24d · EX23/B model_500 동기 비교

## 도구 계약

`foothold_s2/eval/compare_ex23_b500.py`는 MP4 하나마다 같은 이름의 JSON, `_feet.npz`, `.done`을 찾는다. `seq_video.verify_done`으로 세 파일과 checkpoint SHA 영수증을 확인하고, JSON checkpoint 경로/SHA가 영수증과 일치하는지도 확인한다. 검사 하나라도 실패하면 비교 영상을 만들지 않는다.

두 정책 모두 `record_sol23f.py`의 B 평가 환경에서 촬영되므로 JSON `experiment`는 `B`여야 한다. 비교대상 정책 역할은 EX23 checkpoint SHA `343bb15665abf76a2e58b96d274b74d8703f84c779b2667028bee8a39d93511e`와 JSON label `EX-23`으로 확인하고, B 역할은 명시된 B 입력 슬롯·B label 및 다른 checkpoint SHA로 확인한다. 각 촬영은 지형(flat 또는 rough), checkpoint 파일명 `model_500.pt`, seed, fixed physics 설정 및 실제 물성 readback, latent/action mean mode, 요청 map mode와 실제 GT 선택, 300 frame·25 fps·12초, 4개 명령 segment, physics step을 명시해야 한다. 네 영상의 seed·physics signature·policy mode·map 선택·physics step이 모두 같아야 한다. 각 역할의 flat/rough는 같은 checkpoint 경로와 SHA를 써야 하며, 같은 지형의 EX23/B는 `task_selection`과 `perception_timing`도 일치해야 한다. 필요한 값이 없거나 다르면 비교 불가로 종료한다.

영상은 위 flat, 아래 rough, 왼쪽 EX23, 오른쪽 B로 배열한다. 각 패널에 실험·지형·model_500 라벨을 붙이고 1280×720, 300 frame, 25 fps MP4와 입력 영수증·조건 SHA를 담은 JSON을 새 경로에 쓴다. `ffmpeg`는 CPU `libx264`로 실행하며 기존 입력을 덮어쓰지 않는다. 명령 구간은 전진 0.5 m/s, 전진 1.0 m/s, 좌회전 1.2 rad/s, 우회전 -1.2 rad/s를 각각 3초로 둔다.

## 사용법

네 입력 MP4의 형제 JSON·feet NPZ·성공 `.done`이 준비된 뒤 저장소 루트에서 실행한다.

```powershell
python -m foothold_s2.eval.compare_ex23_b500 `
  --flat-ex23 <EX23-flat.mp4> --flat-b <B-flat.mp4> `
  --rough-ex23 <EX23-rough.mp4> --rough-b <B-rough.mp4> `
  --out <새-경로/EX23-B-model500.mp4>
```

기본 글꼴은 `C:/Windows/Fonts/arial.ttf`이다. 다른 환경은 `--fontfile <폰트 파일>`을 지정한다.

## 기존 EX23 model_500 원장 대조

기존 `$S/videos/mid500_1022/ex23r_500/run_flat` 및 `run_rough` 자료는 JSON이 가리키는 EX23 checkpoint `logs/rsl_rl/foothold_s2_x23/2026-10-22_21-52-26_ex23-g1/model_500.pt`를 찾았고 SHA-256은 `343bb15665abf76a2e58b96d274b74d8703f84c779b2667028bee8a39d93511e`였다. MP4도 각각 300 frame, 25/1 fps, 12초이며 명령 구간이 맞지만 `.done`이 텍스트였고 metadata가 부족해 비교할 수 없었다.

## 새 EX23 입력 재검

요청받은 `$S/run_20261024/ex23_model500_flat/review.*`와 `ex23_model500_rough/review.*` 원자료를 읽기 전용으로 `seq_video.verify_done` 및 새 helper에서 각각 검사했다. 둘 다 영수증이 통과했고 동일 EX23 checkpoint SHA가 지정값과 일치했다. JSON `experiment=B`는 B 평가 환경을 뜻하며, EX23 역할은 해당 checkpoint SHA와 label `EX-23 model_500`으로 확인했다. 양쪽 모두 seed 42, fixed physics, mean/mean, saved map 및 실제 `use_gt=true`, 300 frame·25 fps·12초, 동일 4 segment, depth delay 1 tick이다. NPZ `dt=0.02`와 JSON `step_contract.physics_dt_s=0.02`, `physics_steps=600`도 일치했다. Flat과 rough의 task selection 지형 및 noise 범위는 각 scene에 맞게 달랐고, terrain pair끼리 비교할 때 같은 조건인지를 helper가 검사한다.

실제 JSON 사본으로 seed, checkpoint SHA, policy mode, terrain을 각각 바꾼 CPU 반례를 실행해 네 경우 모두 거부됨을 확인했다. 실제 B flat/rough는 아직 전달되지 않아 네 영상 통합 및 실험 비교는 미확인이다.

## 검증

`python -m unittest foothold_s2.eval.tests.test_compare_ex23_b500 -v`는 CPU 생성 영상 네 개를 영수증 검증 후 합치고, 결과 MP4를 다시 `ffprobe`해 300 frame 및 25/1 fps를 확인했다. seed 불일치와 단순 텍스트 `.done` marker는 각각 거부됐다. 실제 EX23 두 파일의 영수증·조건·NPZ 시각축 검사도 통과했다. GPU·Kit·학습·원본 수정은 수행하지 않았으며, B 입력이 없어 실험 비교 영상은 만들지 않았다.
