# C층 비0 env 로봇 가시성 고침
> 분류: C/운영 · 인프라 · 자동화 · 깃 · 웹 · 예산 · 일정
> 작성: 오흥재 · scripter 반영 · 2026-11-03
> 근거: GPU1 역계단 L0 진단 영수증, 고정 코드 5027e4ad, CPU 알려진 입력 13건
> 요지: 선택된 env 5 로봇이 USD에서 invisible이어서 첫 프레임과 분할 ID에서 사라진 원인을 확인했다.
> 상태: 원인 확인, 새 녹화기·두 GPU 계획 CPU 검사 통과, Kit 두 칸 확인 전

## 원인

`D:/mai-tmp/c_layer_seg_probe_v1/out/attempts/pyramid_stairs_inv_L0_eval_gt/01/.../segmentation_failure.json`의 선택 root는 `/World/envs/env_5/Robot`, `root_visibility=invisible`, 로봇 라벨 0개, 선택 로봇 픽셀 0개다. `camera.root_in_frame=true`, RGB 평균 105이고 실제 PNG에는 지도·명령 표시는 있으나 로봇 몸체가 없다. 물리 상태 불변 렌더만 8번 다시 해도 같았다. 같은 GPU1의 일반 계단 env 0은 첫 프레임 로봇 픽셀 40,577로 성공했다. 따라서 이번 실패는 카메라 검정이나 정책 낙하가 아니라 **선택 로봇 USD 가시성이 꺼진 상태**다. GPU0에서 실패한 stage_stairs env 22도 같은 경로일 가능성이 크지만 Kit로 아직 재확인하지 않았다.

고정 `record_c_layer.py`의 `hide_nonselected_robot_roots` 호출은 나머지 63 root를 숨기면서 선택 root가 실제로 visible인지 단언하지 않았다. 새 녹화기는 선택 root에 `UsdGeom.Imageable.MakeVisible()`을 호출하고 계산된 가시성이 `inherited`, 다른 63 root는 모두 `invisible`인지 단언한다. 실패하면 정본 영상을 만들지 않고 RGB·라벨 진단을 보존한다. 원본 5027e4ad 사본은 수정하지 않았다.

## 새 고정 파일·계획

| 항목 | 경로 · SHA256 |
|---|---|
| 샤드 래퍼 | `D:/mai-tmp/c_layer_visibility_fix_v1/c_layer_shard.py` · 계획의 `execution_shard.runner_sha256`에 고정 |
| 녹화기 | GPU0·GPU1 코드 바이트 동일 · `6d7048f1c0f5d8d4aaeff9ab68e7b97db81b044132edf98056048daccadda9c8` · 보조 코드 SHA도 import 전에 검사 |
| visibility 보조 코드 | `68122ec230735a38d5291e5cd65efc4b0045eab68718d1afa4b96633f7c9f8ac` |
| GPU1 본 샤드 | `D:/mai-tmp/c_layer_visibility_fix_v1/gpu1/diagnostic_plan.json` · `dadac1abfd55d7d1ff70186f99719eda81b7d019f6249d31771192e1588a1e77` |
| GPU0 본 샤드 | `D:/mai-tmp/c_layer_visibility_fix_v1/gpu0/diagnostic_plan.json` · `ac1839cbf79850546145689d5dfb739d1dc661c03425c068eaedeba6d2048171` |
| GPU1 한 칸 시험 | `D:/mai-tmp/c_layer_visibility_fix_v1/smoke_gpu1/diagnostic_plan.json` · `ad29d5422f7871d52c308b568519ec17343ce09571df3d68ba01364144a88319` |
| GPU0 한 칸 시험 | `D:/mai-tmp/c_layer_visibility_fix_v1/smoke_gpu0/diagnostic_plan.json` · `3b4b3d360f9b9267757b62407eb5c7e9bb28ef4c4d51c3d88691608f23a4a2b7` |

본 샤드의 out은 원래 GPU별 out이다. 옛 성공 영수증은 당시 recorder SHA로 보존한다. 옛 기술 실패 6건과 GPU0 실패 2건은 새 recorder SHA의 3회 상한에 포함하지 않아 고친 코드로 동일 시드 재시도가 가능하다. 옛 `shard_holds` 파일은 역사적 기록이며 새 판 성공으로 자동 삭제하지 않는다.

## Lead가 할 Kit 한 칸 확인 · GPU별 명령 한 줄

기존 GPU 반복기가 해당 장치와 원 out을 점유하지 않는 때에 실행한다. 시험 out은 기존 out과 분리되어 정본 성공 영수증에 섞이지 않는다.

GPU0 · 알려진 env 0 일반 계단:

```powershell
$env:PYTHONPATH='D:/mai-wt/foothold-lab/c-layer-run-5027e4ad'; $env:TMP='D:/mai-tmp/c_layer_visibility_fix_v1/gpu0_tmp'; $env:TEMP=$env:TMP; & 'C:/Users/AI-WS01/anaconda3/envs/isaac311/python.exe' 'D:/mai-wt/foothold-lab/c-layer-run-5027e4ad/foothold_s2/eval/c_layer_queue.py' 'D:/mai-tmp/c_layer_visibility_fix_v1/smoke_gpu0/diagnostic_plan.json' --out 'D:/mai-tmp/c_layer_visibility_fix_v1/smoke_gpu0_out' --run-one --only-cell pyramid_stairs_L0_eval_gt
```

GPU1 · 실패했던 env 5 역계단:

```powershell
$env:PYTHONPATH='D:/mai-wt/foothold-lab/c-layer-run-5027e4ad'; $env:TMP='D:/mai-tmp/c_layer_visibility_fix_v1/gpu1_tmp'; $env:TEMP=$env:TMP; & 'C:/Users/AI-WS01/anaconda3/envs/isaac311/python.exe' 'D:/mai-wt/foothold-lab/c-layer-run-5027e4ad/foothold_s2/eval/c_layer_queue.py' 'D:/mai-tmp/c_layer_visibility_fix_v1/smoke_gpu1/diagnostic_plan.json' --out 'D:/mai-tmp/c_layer_visibility_fix_v1/smoke_gpu1_out' --run-one --only-cell pyramid_stairs_inv_L0_eval_gt
```

두 칸 모두 `child.log` Traceback 0, `review.json` 첫 `robot_instance_evidence.selected_robot_pixels>=80`, `other_robot_pixels=0`, `render_visibility.visibility_check.selected_visibility_after=inherited`, 다른 로봇 63대 invisible, `raw_frame_audit.json`과 `styled_frame_audit.json` PASS, 성공 영수증과 MP4 SHA를 확인한다. 두 칸이 통과한 뒤 lead가 기존 반복기를 칸 경계에서 새 샤드 래퍼·본 계획으로 교체한다:

```powershell
& 'C:/Users/AI-WS01/anaconda3/envs/isaac311/python.exe' 'D:/mai-tmp/c_layer_visibility_fix_v1/c_layer_shard.py' 'D:/mai-tmp/c_layer_visibility_fix_v1/gpu0/diagnostic_plan.json' --out 'D:/mai-tmp/c_layer_m6000_phase1_gpu0/out' --gpu 0
& 'C:/Users/AI-WS01/anaconda3/envs/isaac311/python.exe' 'D:/mai-tmp/c_layer_visibility_fix_v1/c_layer_shard.py' 'D:/mai-tmp/c_layer_visibility_fix_v1/gpu1/diagnostic_plan.json' --out 'D:/mai-tmp/c_layer_m6000_phase1_v2/out' --gpu 1
```

## CPU 검증과 한계

`test_c_layer_shard_cpu.py`와 `test_c_layer_seg_probe_cpu.py` 13 PASS. 비0 env의 invisible→inherited, env0 유지, 선택 root가 여전히 invisible인 돌연변이와 다른 로봇이 visible인 돌연변이를 구분한다. 실제 옛 GPU1 기술 실패 6건은 새 녹화기 SHA에서 HOLD 아님을 확인했다. 새 계획 두 개 모두 고정 큐 `ready=216`, 새 샤드 `state=checked` 108칸씩 통과했다. 바뀐 Python과 생성 녹화기 `ruff F`·`pyflakes` 0건. `pxr`는 CPU isaac311에서 import되지 않아 실제 USD `MakeVisible` 효과와 두 칸 영상은 **Kit 확인 전**이다. GPU·Kit은 scripter가 실행하지 않았다.
