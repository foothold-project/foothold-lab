# C층 m6000 첫 칸 계획 재고정
> 분류: A/평가 · 일반화 벤치마크 · 지표
> 작성: 오흥재 · 2026-11-02
> 근거: 팀장 17:3x 지시 · D131 · `plan_c_layer.py` · 실제 EX-40 m6000 저장본
> 요지: HEAD `53153453`의 queue · recorder · composer를 D: 계획에 고정하고 첫 칸 기동 명령을 제공한다.
> 상태: CPU 계획과 첫 기록기 예행 확인 · Kit 촬영은 lead 담당

## 계획

| 항목 | 확인값 |
|---|---|
| 계획 | `D:/mai-tmp/c_layer_m6000/plan.json` · SHA256 `c1670755bfef3e3b70a217e32f5fff3695d45e6b9c53253e37bf2a5609bc0f58` |
| 출력 | `D:/mai-tmp/c_layer_m6000/out` |
| 등록 | 216/216칸 · 첫 칸 `pyramid_stairs_L0_eval_gt` · seed 42~45 중 첫 시도 42 |
| 장치 | 모든 216행 `cuda:1` · `CUDA_VISIBLE_DEVICES` 제거 · PCI 버스 순서 |
| 정본 저장본 | `model_6000.pt` · SHA256 `d5e9ec400f33d74d97e7c69d4ab2092d4980195141bb8b30e683730eecd6b6f5` |
| policy 소스 | `C:/mai/wt/foothold-lab/lead-w80-recorder` · clean HEAD `fc1ef1d5` · 기존 C76 소스 계약 유지 |
| queue | `D:/mai-wt/foothold-lab/scripter-c76/foothold_s2/eval/c_layer_queue.py` · SHA256 `3d45030283ff5a929b9b469fe436a9e115a8c82da0e02b88b591557a0bf53c81` |
| recorder | 같은 사본 `foothold_s2/eval/video25/record_c_layer.py` · SHA256 `96014f8d5f3bd30a35099b83e0f637fed3b983a7ca2d517d0930595d2217306b` |
| composer | 같은 사본 `foothold_s2/eval/video25/compose_25e_v2style10.py` · SHA256 `569acdaa69a30bfdbbcf5b37c63c302b1966693cdfb72a89d4641493653088ed` |
| 재생 목록 | `D:/mai-tmp/c_layer_m6000/_playlists` · 기존 C: 목록 불변 |

기존 C: 계획은 수정하지 않았다. 우선순위 표식은 기존 `C:/Users/AI-WS01/s2_lab/c_layer_m6000/priority/` 세 파일을 읽는다. 높은 우선순위 표식이 있으면 queue가 촬영을 양보한다. 새 계획의 SHA 및 소스 SHA를 queue가 기동 전 다시 대조한다.

## lead가 실행할 첫 칸 명령 · PowerShell

```powershell
Set-Location 'D:/mai-wt/foothold-lab/scripter-c76'
$p = 'C:/Users/AI-WS01/anaconda3/envs/isaac311'
$env:TMP = 'D:/mai-tmp/scripter'
$env:TEMP = 'D:/mai-tmp/scripter'
$env:CONDA_PREFIX = $p
$env:OMNI_KIT_ACCEPT_EULA = 'YES'
$env:CUDA_DEVICE_ORDER = 'PCI_BUS_ID'
$env:PYTHONUNBUFFERED = '1'
$env:PYTHONUTF8 = '1'
$env:KMP_DUPLICATE_LIB_OK = 'TRUE'
Remove-Item Env:CUDA_VISIBLE_DEVICES -ErrorAction SilentlyContinue
$env:PATH = "$p;$p/Library/mingw-w64/bin;$p/Library/usr/bin;$p/Library/bin;$p/Scripts;$p/bin;$env:PATH"
$env:PYTHONPATH = 'D:/mai-wt/foothold-lab/scripter-c76'
& "$p/python.exe" -m foothold_s2.eval.c_layer_queue 'D:/mai-tmp/c_layer_m6000/plan.json' --out 'D:/mai-tmp/c_layer_m6000/out' --run-one --only-cell 'pyramid_stairs_L0_eval_gt'
if ($LASTEXITCODE -ne 0) { throw "C76 first cell failed with rc $LASTEXITCODE" }
```

첫 호출은 이 칸의 seed 한 건을 촬영한다. 성공과 실패 두 역할을 모두 채우려면 같은 명령을 결과 판독 뒤 다시 호출한다. `--only-cell`이 있으므로 다른 215칸은 촬영하지 않는다. 이 명령은 내가 실행하지 않았다.

## CPU 확인

- `c_layer_queue` 계획 검증: `expected=216, ready=216, missing=0`.
- 첫 기록기 `--plan-only`: seed 42, 지도 `eval_gt`, 450프레임, 저장본 SHA 일치. `review.mp4`는 label 이름의 상위 폴더 아래에 둔 실제 queue 경로로 시험했다.
- 실제 Kit 녹화, GPU 메모리, 첫 프레임, 전 프레임 검사는 미확인. lead의 첫 칸 결과가 필요하다.
