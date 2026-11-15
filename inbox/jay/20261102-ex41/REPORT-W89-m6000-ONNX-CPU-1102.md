# W89 EX-40 m6000 지각망과 actor ONNX CPU 준비
> 분류: A/정책학습
> 작성: 오흥재 · 2026-11-02
> 근거: EX-40 m6000 저장본 · agent.yaml · START 지각 코드 · ONNX Runtime CPU 출력
> 요지: TR-Net, I-E의 GRU 둘, actor를 지도 켬과 지도 토큰 끔 그래프로 내보내고 PyTorch와 같은 입력을 대조했다.
> 상태: CPU 확인, 실제 로봇 · Kit · GPU 확인 전

## 입력과 구조

- 저장본 `C:/Users/AI-WS01/s2_lab/ex40_main_20261031_041313/main/EX-40-B-main_20261031_041337_26240/model_6000.pt` SHA256 `d5e9ec400f33d74d97e7c69d4ab2092d4980195141bb8b30e683730eecd6b6f5`, `iter=6000`. 실제 `perception_cfg`는 `map_input=reconstruction`, `est_mode=learned`, `force_gt=true`다.
- `params/agent.yaml:26,28~36`은 actor 관측 정규화 끔, `[512,256,128]`와 ELU다. 저장본 actor 첫 층 96→512, 마지막 128→12를 엄격히 로드한다. 지각 추정 51은 코드 순서 `[mu16,v3,zf16,zb16]`이고 현재 관측 45와 이어 붙인다.
- 그래프 입력은 `obs45[1,45]`, `hist[1,10,45]`, `depth2[1,2,60,60]`, 두 GRU hidden `[1,128]`, `depth_tick`, `first_after_reset`, `use_gt`, `gt_map[1,32,16]`이다. 출력은 raw `action[1,12]`, 두 다음 hidden, `recon_map[1,32,16]`이다. 깊이 정규화, 이력 · 지연 프레임 조립, action clip ±17과 `기본 관절각 + 0.25 × action`은 그래프 밖 계약이다.
- `map_on`은 `use_gt=false`일 때 재구성 지도, `true`일 때 진단용 정답 지도를 받는다. `map_off`는 지도 토큰을 attention에서 마스킹하는 별도 고정 그래프다. 두 모드를 하나의 입력 플래그로 추적하면 현재 Python 분기가 trace 시 고정되므로 분리했다. 같은 입력의 두 모드 action은 CPU에서 최대 차이 0.378152였고, 모드 차이가 실제로 유지된다.

## 산출과 검증

| 파일 | 바이트 | SHA256 |
|---|---:|---|
| `D:/mai-tmp/scripter/w89_export/ex40_m6000_map_on.onnx` | 5,808,798 | `81c7e079516058ee6243f6edd11efa8f0da239c6cc86fbca791bda5bcd82f110` |
| `D:/mai-tmp/scripter/w89_export/ex40_m6000_map_off.onnx` | 5,818,629 | `5d1b7bf39aa0d9fb8ae33bf33dad82902165d53679ccd7ec5df727a0b70fe037` |
| `D:/mai-tmp/scripter/w89_export/contract.json` | 1,587 | `f1aca5f432860762eb2fcbbd896f9d25feb67912fde7e134158b56ac7c4a698d` |
| `D:/mai-tmp/scripter/w89_export/comparison.json` | 2,645 | `145f8e5682c25b872db2ca0f1344ad57e43b11ebd67ace0d809dcdfff6c368cf` |

- ONNX checker는 두 그래프 모두 PASS(각 287 · 352 node). ONNX Runtime CPU는 첫 스텝, 이어진 스텝, 깊이 틱 없음, 정답 지도, 지도 토큰 끔과 hidden을 실제로 이어 준 3스텝 시퀀스에서 PyTorch 원본과 대조했다. 12개 케이스 × 4개 출력의 최대 절대 차이 `5.0067901611328125e-6`, 지정 허용 오차 `3e-5` 이하다. 각 case 값은 `comparison.json`에 있다.
- `foothold_s2/tests/test_export_ex40_w89.py` 3 passed. 저장본 SHA 불일치 거절, actor 열과 지도 끔의 실제 출력 변화, 출력 차원과 유한성을 확인했다. 새 Python 3개는 pyflakes와 ruff F 오류 0건.
- 이 검증 입력은 답을 아는 CPU 합성 입력이다. 실제 카메라 · IMU · 관절 스트림과의 입력 정렬, ONNX Runtime Web/Jetson, 실기 안전 제어와 성능은 미확인이다. m6000 학습은 `force_gt=true`였으므로 재구성 지도 추론의 성적을 이 수치로 주장하지 않는다.

## 재실행 명령

`PYTHONPATH`를 이 worktree로 두고 첫 명령은 isaac311 Python, 둘째는 torch와 ONNX Runtime 충돌을 피하기 위해 base Python에서 실행한다. 결과를 새 출력 폴더로 내보낼 것.

```powershell
$env:PYTHONPATH='D:/mai-wt/foothold-lab/scripter-w78-video'; $env:TMP='D:/mai-tmp/scripter'; $env:TEMP=$env:TMP; & 'C:/Users/AI-WS01/anaconda3/envs/isaac311/python.exe' -m foothold_s2.deploy.export_ex40_w89 --checkpoint 'C:/Users/AI-WS01/s2_lab/ex40_main_20261031_041313/main/EX-40-B-main_20261031_041337_26240/model_6000.pt' --output 'D:/mai-tmp/scripter/w89_export_new'
& 'C:/Users/AI-WS01/anaconda3/envs/isaac311/python.exe' -m foothold_s2.deploy.verify_ex40_w89 fixtures --checkpoint 'C:/Users/AI-WS01/s2_lab/ex40_main_20261031_041313/main/EX-40-B-main_20261031_041337_26240/model_6000.pt' --expected-sha256 d5e9ec400f33d74d97e7c69d4ab2092d4980195141bb8b30e683730eecd6b6f5 --out 'D:/mai-tmp/scripter/w89_fixtures_new'
& 'C:/Users/AI-WS01/anaconda3/python.exe' -m foothold_s2.deploy.verify_ex40_w89 compare --onnx-dir 'D:/mai-tmp/scripter/w89_export_new' --fixtures 'D:/mai-tmp/scripter/w89_fixtures_new' --report 'D:/mai-tmp/scripter/w89_export_new/comparison.json'
```
