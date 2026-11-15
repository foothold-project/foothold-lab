# C층 GPU0 분할 픽셀 실패 진단
> 분류: C/운영 · 인프라 · 자동화 · 깃 · 웹 · 예산 · 일정
> 작성: 오흥재 · scripter 반영 · 2026-11-03
> 근거: GPU0 한 칸 원영수증, GPU1 env5 통과, 고정 녹화기 5027e4ad
> 요지: GPU0 실패의 두 가능한 조건을 구분할 첫 프레임 마스크 진단을 추가했다.
> 상태: GPU1 가시성 고침 Kit 통과, GPU0 원인 미확정 · 한 칸 진단 대기

GPU1 env5는 새 가시성 고침 뒤 `captured`로 통과했다. GPU0 env0의 `D:/mai-tmp/c_layer_visibility_fix_v1/smoke_gpu0_out/attempts/pyramid_stairs_L0_eval_gt/01/child.log:270-277`은 `require_single_visible_robot`에서 실패했다. 이 검사는 `selected_robot_pixels<80` **또는** `other_robot_pixels!=0`이면 같은 예외를 내므로 현 영수증만으로 GPU0의 분할 출력 결함이나 다른 로봇 노출을 확정할 수 없다. 앞선 선택 root 가시성 단언은 통과했다. 실패 시 MP4·review JSON이 남지 않아 픽셀 수 원자료가 없었다.

새 진단 녹화기는 그 예외 직전의 `mask_evidence`(선택·다른 로봇 픽셀 수), `idToLabels` 로봇 경로, USD 선택 root 가시성, 카메라, 첫 RGB를 `segmentation_failure.json`과 PNG로 보존하고 실패는 그대로 실패로 둔다. 본 GPU1 실행 사본·계획은 수정하지 않았다. 새 GPU0 계획 `D:/mai-tmp/c_layer_gpu0_mask_probe2/diagnostic_plan.json` SHA `60e04fbaccbfbcdf29843a9a931a903b8c76cbf009de2ec883e7308dddca178e`, recorder SHA `a80eb7f9297820a6c923ef50169f05cdbc31d3efd78bf91daec4b6920c281005`. 큐 216칸 등록 CPU 검사는 통과했다.

Lead가 GPU0에 한 칸만 실행할 명령:

```powershell
$env:PYTHONPATH='D:/mai-wt/foothold-lab/c-layer-run-5027e4ad'; $env:TMP='D:/mai-tmp/c_layer_gpu0_mask_probe2/tmp'; $env:TEMP=$env:TMP; & 'C:/Users/AI-WS01/anaconda3/envs/isaac311/python.exe' 'D:/mai-wt/foothold-lab/c-layer-run-5027e4ad/foothold_s2/eval/c_layer_queue.py' 'D:/mai-tmp/c_layer_gpu0_mask_probe2/diagnostic_plan.json' --out 'D:/mai-tmp/c_layer_gpu0_mask_probe2/out' --run-one --only-cell pyramid_stairs_L0_eval_gt
```

한 번의 결과에서 `selected_robot_pixels`와 `other_robot_pixels`를 읽으면 분기가 정해진다. 선택 픽셀이 0이고 RGB에 로봇이 있으면 GPU0 분할 라벨/버퍼 문제, RGB에도 없으면 GPU0 렌더 가시성 문제다. 다른 로봇 픽셀이 양수면 숨김 범위를 고쳐야 한다. 같은 진단에서도 분할 출력이 비거나 불안정해 원인별 안전한 고침을 입증할 수 없으면 GPU0를 C층 정본 촬영에서 제외하고 GPU1만 쓴다. 문턱 완화나 수동 성공 영수증은 하지 않는다.

CPU 알려진 입력 8건 통과. 새 Python과 생성 녹화기 `ruff F`·`pyflakes` 0건. GPU·Kit은 scripter가 실행하지 않았다.
