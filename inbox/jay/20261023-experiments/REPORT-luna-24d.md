> 분류: C/기록 · 2026-10-24
> 작성: 오흥재 (luna 문서 반영) · 2026-10-24
> 근거: lead 요청 · record_sol23f.py · seq_video.py · ex23r_500 영상 원장
> 요지: EX23와 B의 model_500 flat/rough 네 영상을 영수증과 조건 대조 뒤 2x2로 합치는 CPU 도구
> 상태: CPU 알려진 입력 검증 완료 · 실제 B 입력 대기

# LUNA-24d · EX23/B model_500 동기 비교

## 도구 계약

`foothold_s2/eval/compare_ex23_b500.py`는 MP4 하나마다 같은 이름의 JSON, `_feet.npz`, `.done`을 찾는다. `seq_video.verify_done`으로 세 파일과 checkpoint SHA 영수증을 확인하고, JSON checkpoint 경로/SHA가 영수증과 일치하는지도 확인한다. 검사 하나라도 실패하면 비교 영상을 만들지 않는다.

각 촬영은 `experiment`와 지형(flat 또는 rough), checkpoint 파일명 `model_500.pt`, seed, fixed physics 설정 및 실제 물성 readback, latent/action mean mode, 요청 map mode와 실제 GT 선택, 300 frame·25 fps·12초, 4개 명령 segment, physics step을 명시해야 한다. 네 영상의 seed·physics signature·policy mode·map 선택·physics step이 모두 같아야 한다. 각 실험은 flat/rough가 같은 checkpoint 경로와 SHA를 써야 한다. 이 값이 없거나 다르면 비교 불가로 종료한다.

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

`$S/videos/mid500_1022/ex23r_500/run_flat` 및 `run_rough` JSON은 같은 EX23 checkpoint `logs/rsl_rl/foothold_s2_x23/2026-10-22_21-52-26_ex23-g1/model_500.pt`를 가리킨다. 로컬 파일 존재와 SHA-256 `343bb15665abf76a2e58b96d274b74d8703f84c779b2667028bee8a39d93511e`를 확인했다. 두 MP4는 CPU `ffprobe`에서 각각 300 frame, 25/1 fps, 12초이며 JSON 명령도 요청한 네 개 3초 구간과 일치한다.

이 파일들은 새 비교 입력으로 재사용할 수 없다. 두 `.done` 파일 내용은 JSON 영수증이 아닌 `done` 텍스트여서 소비기 검증이 `receipt_invalid`로 실패했다. JSON에도 `experiment`, `seed`, `fps`, `duration_s`, `physics`, `policy_modes`, `map_modes`가 빠져 있어 고정 물리·mean/mean·실제 map 선택 일치를 확인할 수 없다. 따라서 EX23 flat/rough를 포함해 새로 영수증을 발급한 네 입력이 필요하며, 과거 영상의 외관만 보고 조건 동일성을 추정하지 않는다.

## 검증

`python -m unittest foothold_s2.eval.tests.test_compare_ex23_b500 -v`는 CPU 생성 테스트 영상 네 개를 영수증 검증 후 합치고, 결과 MP4를 다시 `ffprobe`해 300 frame 및 25/1 fps를 확인했다. seed 불일치와 단순 텍스트 `.done` marker는 각각 거부됐다. GPU·Kit·학습·원본 수정은 수행하지 않았으며 실제 EX23/B 결과 입력은 아직 없어 실험 비교 영상은 만들지 않았다.
