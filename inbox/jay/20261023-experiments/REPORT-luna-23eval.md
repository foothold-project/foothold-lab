> 분류: C/기록
> 작성: 오흥재 (luna 반영) · 2026-10-23
> 근거: luna 고정본5651b5f6 · 결합 학습 코드82331727 · sol-23a 60a53441 · foothold_s2/eval/seq_video.py · foothold_s2/eval/adapters.py
> 요지: B flat/rough 및 native TopDown 평가 녹화 진입점에 고정 물리 · 명령 · 지도 시각화 계약을 적용
> 상태: CPU 계약 확인 · Kit/GPU 실구동 미확인

# SOL-23f B · START-TopDown 평가 녹화 연결

원문 출처: luna의 완료 커밋 `5651b5f64a79fba793c18dc895a67df32e1f9c42`. lead_tmp가 머리 형식과 결합 출처만 보충했다. 본문의 작업자 CPU 결과와 실제 Kit 미확인은 구분한다.

## 바뀐 파일과 범위

- `foothold_s2/eval/record_sol23f.py`: `seq_video.py --recorder` 가 전달하는 JSON `--policy` 사양을 읽는 새 진입점이다. B는 등록된 B 환경 설정과 동일한 `random_rough` 생성기를 쓰며 flat noise `(0.0, 0.003)`, rough noise `(0.01, 0.06)`, 난이도 `0.5` 및 seed를 기록한다. TopDown은 등록된 `FootholdS2-Go2-S2-23f-TopDown-v0` task를 사용하고 native sparse side table에서 terrain type과 level을 지정한다. generator curriculum은 `True`로 유지해 생성 타일 행과 level 검증을 맞추고, env의 terrain-level curriculum만 비활성화한다. `gym.make` 전에 START의 `AUG.enabled=False`도 적용한다.
- 행동과 latent는 `mean`을 강제로 고정해 셸의 `S2_Z` · `S2_ACT` 환경 변수에 좌우되지 않게 했다. 지도 입력은 `saved` · `pred` · `gt` 중 하나이며, 초기 상태와 reset 후에 같은 `use_gt` 마스크를 적용한다. `pred` 에서는 추론 tick의 `use_gt`가 한 번이라도 켜지면 실패 처리한다. pred/gt 덮어쓰기는 체크포인트에 reconstruction map 입력이 있을 때만 허용한다.
- TopDown은 체크포인트에서 복원된 `depth_delay_ticks=0`을 요구하고, 다른 값이면 녹화를 거부한다. 이 worktree의 고정 기준 60a53441 `load_s2_runner`는 이 키를 아직 복원하지 않는다. lead가 알려준 sol f5bfc15c 변경과 결합되어야 TopDown의 지연 계약 검사가 통과한다. adapters.py는 이 worktree에서 수정하지 않았다.
- Kit을 import하기 전에 `tensordict`를 먼저 import한다. 이 순서는 기존 access violation 이력에 대응하지만 Kit 실행은 하지 않아 실제 재현 여부는 미확인이다.
- 네 명령 segment가 바뀔 때 command cfg의 `fixed_cmd`와 `resampling_time_range`를 함께 설정하고 live command tensor도 갱신한다. reset 또는 기본 4초 resample 후에도 해당 segment 명령을 유지하도록 CPU fake term으로 시험했다.
- `physics_mode=fixed|training`을 추가했다. 기본 `fixed`는 B와 EX23 기준의 마찰 범위(정적 0.8, 동적 0.6)를 고정하고 질량 · COM · actuator gain · motor strength · 외력 및 지연 무작위 event를 끄며 reset 자세 · 관절 범위도 고정한다. `training`은 task config의 이벤트를 변경하지 않는다. seq_video 경유 시 JSON 사양에 `physics_mode`를 넣을 수 있고, recorder 직접 실행은 `--physics-mode`로 덮어쓸 수 있다. JSON에는 적용 config와 runtime 물성 readback을 저장하며, 현재 readback은 simulator API가 제공하지 않는 항목을 `unavailable`로 적는다. 동일 Kit에서 B와 EX23를 맞춰 실제 재측정한 것은 아니다.
- GT · rough · refined 지도는 각각 512값을 32x16으로 reshape하고 공통 높이 범위 `[-1, 1] m`를 쓴다. depth 60x60은 별도 `[0, 6] m` 표시 범위를 쓴다. 그림에서도 높이 지도는 2:1 가로세로를 보존한다. CPU 시험은 shape와 scale 계약을 확인했다.
- 12초, 초당 25프레임, 네 개 3초 명령(전진 0.5, 전진 1.0, yaw +1.2, yaw -1.2)을 만들고, 매 물리 step을 NPZ에 저장한다. NPZ에는 seq_video 필수 필드와 발 XY/Z 및 접촉, 관절각, roll/pitch, 명령, 속도 응답, done/time-out/종료 항목, 같은 `map_t`의 depth/GT/rough/refined 지도와 `use_gt`가 들어간다. reset을 넘어짐으로 자동 판정하지 않는다.
- 지도 PNG는 recorder 시도의 보조 그림으로 만들고, 지도 수치 배열은 정식 feet NPZ에 보존한다. 기존 `seq_video.py`가 정식 결과와 SHA 영수증에 포함하는 파일은 MP4 · JSON · feet NPZ 세 개이므로 PNG는 receipt에 포함되지 않는다.
- JSON에는 task ID와 선택 지형, seed, mean 모드, STEP 계약, 체크포인트 SHA-256, recorder와 의존 소스 SHA-256을 기록한다. 기존 `s2_lab/record_seq.py`, 학습 runner, adapters, 공용 s2_lab 원본은 수정하지 않았다.
- 종료 시 컨테이너를 마무리하고 Python stdout/stderr를 flush한 뒤 `os._exit(0|1)`을 호출한다. `env.close()`와 `app.close()`는 기다리지 않는다. CPU 주입형 시험에서 두 stream flush가 종료 함수보다 앞서는 순서를 확인했지만, Kit shutdown 실제 동작은 미확인이다.

## CPU 검증

알고 있는 입력 recorder 계약 시험은 15개, 기존 `test_seq_video.py`는 9개로 총 24개가 통과했다. 기존 8개 계약에 더해 generator/env curriculum 구분과 AUG 비활성화, tensordict 선적재 순서, reset/resample 뒤 명령 고정, fixed/training 물리 설정, 물성 runtime readback, 32x16 공통 지도 scale, 성공/실패 rc의 flush 후 종료 순서를 fake object로 확인했다. `py_compile`과 기존 단위 시험의 plan-only JSON 출력도 확인했다. 계획 출력은 네 명령, 12초, 300 frame 및 seq_video 소비 경로를 포함한다.

`seq_video.py` 검증기 대조 결과, JSON은 checkpoint 절대경로 · label · scene · 300 frame · 최소 밝기 · 네 segment 합계 12초를 요구하고, NPZ는 `t, seg, dt, seg_s, foot_z, foot_contact, vx, wz`와 시간축/샘플 수를 요구한다. 새 recorder 출력은 이 키를 포함하도록 작성했다. 고정 checkpoint로 parent의 ffprobe/ffmpeg 포함 전체 검증을 실제 실행한 것은 아니며, Kit/GPU 환경의 생성 · reset · 물성 readback · 종료와 receipt 성공은 미확인이다.

## 실행 예시

작업 worktree 루트에서 Isaac Lab Python을 지정해 실행한다. 아래 B 예시는 flat과 rough를 각각 별도 이름으로 실행한다.

```powershell
$policy = '{"experiment":"B","terrain":"flat","seed":42,"map_mode":"saved","physics_mode":"fixed"}'
python -m foothold_s2.eval.seq_video <out> B_flat $policy <checkpoint.pt> B-flat flat cuda:0 --python <isaaclab-python> --recorder foothold_s2/eval/record_sol23f.py
```

TopDown은 `scene` 인자를 `rough`로 고정 전달하고 실제 sparse terrain type과 level은 JSON에 넣는다.

```powershell
$policy = '{"experiment":"TD","terrain_type":"stepping_beams","level":7,"seed":42,"map_mode":"pred","physics_mode":"fixed"}'
python -m foothold_s2.eval.seq_video <out> TD_stepping_beams_L7 $policy <checkpoint.pt> TD-L7 rough cuda:0 --python <isaaclab-python> --recorder foothold_s2/eval/record_sol23f.py
```

예시는 실행 안내일 뿐이다. 이 변경 중에는 Kit/GPU 실행이나 촬영을 하지 않았다. 공유 체크아웃 및 push도 사용하지 않았다.
