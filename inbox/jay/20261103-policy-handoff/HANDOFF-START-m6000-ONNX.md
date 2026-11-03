> 분류: A/정책학습 · START m6000 ONNX 전달 파악 문서
> 작성: 오흥재 (lead 세션) · 2026-11-03 16:3x v0.1
> 근거: 조건표 정본 `inbox/jay/20261101-app/APP-POLICY-CONTRACT-m6000.md` v0.3.1 (lead 가지 dc81513c) · 묶음 `D:/mai-tmp/lead/start-demo-onnx/` (scripter 34982e13 묶음을 D169 이름으로 바꾼 사본, ONNX 바이트 같음) · scripter `REPORT-W89-m6000-ONNX-CPU-1102.md` · 내보내기 `foothold_s2/deploy/export_ex40_w89.py`
> 요지: m6000 은 지각(TR-Net · I-E, GRU 둘) + actor 를 ONNX 두 파일(지도 켬 · 끔)로 내보냈고, 합성 입력으로 PyTorch 와 최대 5e-6 차이다. **아직 팀원에게 넘기지 않았다.** 넘기기 전에 실제 학습 기록 입력으로 같은 출력 확인 · 시험 벡터 · ORT Web 확인 · 묶음 파일 셋이 남았다
> 상태: v0.1 · 전달 전(D144 팀장 결정 대기) · 앱 쪽은 상태 되먹임 실행기가 먼저 필요(HANDOFF-APP-DEVELOPER §2-3)

# START m6000 ONNX 전달 파악

이름 규칙 · 저장소 배치는 같은 폴더 `README.md`. 앱이 받는 쪽 값은 `HANDOFF-APP-DEVELOPER.md` §1.2 `start` 열.

## 1. 무엇이 있나

| 항목 | 값 | 확인 |
|---|---|---|
| 저장본 | `C:/Users/AI-WS01/s2_lab/ex40_main_20261031_041313/main/EX-40-B-main_20261031_041337_26240/model_6000.pt` · sha256 `d5e9ec40…` | 실측 |
| 이름 | `start-demo` (최종 `start-oh2l2`) · format `start-demo-onnx/1` | D169 |
| ONNX | `start-demo_map_on.onnx` 5,808,798 B sha `81c7e079…` · `start-demo_map_off.onnx` 5,818,629 B sha `5d1b7bf3…` | 실측(16:13 원본과 같음) |
| 입력 9 | `obs45[1,45] · hist[1,10,45] · depth2[1,2,60,60] · h_prop[1,128] · h_terr[1,128] · depth_tick[1] · first_after_reset[1] · use_gt[1] · gt_map[1,512]` | contract.json |
| 출력 4 | `action[1,12] · h_prop_next[1,128] · h_terr_next[1,128] · recon_map[1,32,16]` | contract.json |
| ONNX 밖에서 할 일 | a 를 ±17 로 자르고 목표각 = 기본 + 0.25 × a · 이력 10 × 45 · 깊이 두 프레임 지연 · GRU 상태 되먹임 | contract.json `action` · `state` |
| 같은 출력 확인 | ONNX checker 두 그래프 PASS(287 · 352 node) · ORT CPU 대 PyTorch 최대 차이: action 5.0e-6 · h 2.4e-6 · recon 4.0e-6(첫 스텝 · 이어진 스텝 · 깊이 틱 없음 · 정답 지도 · 끔) | `comparison.json` · **합성 입력** |

## 2. 두 계열을 섞지 않게 (START 대 AME-2)

앱은 모드 키로 값을 통째로 갈아 끼우므로(앱 문서 §2-1) 학습 방식이 달라도 문제가 되지 않는다. 문제가 되는 것은 **공통 기본값이 한 모드에 새어 들어갈 때**다. START 에서 특히 조심할 셋:

| 칸 | START 값 | 섞이면 생기는 일 |
|---|---|---|
| calf 토크 | 45.43 N·m · 속도 15.70 (DCMotor 곡선) | 앱 공통 23.5 가 들어가면 계단에서 무릎 힘이 반으로 잘린다 |
| 지도 | 32 × 16 · 5 cm · 높이 1 채널 · 몸 기준 상대 높이 | AME-2 의 29 × 13 × 3(+0.27) 함수를 쓰면 숫자 뜻이 달라 땅을 잘못 본다 |
| 상태 | GRU 둘 · 이력 10 | 되먹이지 않으면 매 스텝 처음 걸음처럼 움직인다 |

## 3. 넘기기 전에 남은 것 (lead 가 맡김)

| # | 할 일 | 왜 | 담당 |
|---|---|---|---|
| 1 | 실제 학습 기록 입력으로 같은 출력: m6000 을 Isaac 에서 20 스텝 돌려 obs45 · hist · depth2 · h · action 을 기록하고 ONNX 에 그대로 넣어 action 1e-4 이하 | 지금 확인은 합성 입력이라 실제 입력 정렬(깊이 지연 · 이력 순서)을 못 본다 | runner 또는 scripter |
| 2 | `test_vectors_flat20.json` · `.npz` (위 1 의 평지 20 스텝, 지도 모드 셋 각각 · 꼴은 앱 문서 §2-5a · format `start-demo-test-vectors/1`) | 앱이 상태 되먹임까지 맞춰 볼 답 | 같음 |
| 3 | ORT Web(브라우저 WASM)에서 같은 입력 → 같은 출력 | 앱이 쓰는 실행기 | 현민 님 또는 scripter |
| 4 | `SHA256SUMS` · `CONTRACT.md`(= 조건표 정본 사본) · ONNX 두 파일을 같은 폴더에 | README 배치 | lead |
| 5 | 팀장 검증 뒤 현민 님에게 전달(README 진행 순서) | D144 | **팀장** |

## 4. 저장소에 놓을 꼴 (README 배치 그대로)

```
inbox/jay/20261103-policy-handoff/start-demo/
  CONTRACT.md            ← inbox/jay/20261101-app/APP-POLICY-CONTRACT-m6000.md v0.3.1 사본(정본은 그대로 두고 가리킴)
  contract.json          ← D:/mai-tmp/lead/start-demo-onnx/contract.json
  parity.json            ← comparison.json + 3 의 1 결과
  test_vectors_flat20.json · test_vectors_flat20.npz
  SHA256SUMS
  start-demo_map_on.onnx · start-demo_map_off.onnx
```

## 5. 미확인

- 실제 카메라 · IMU · 관절 스트림 정렬, ORT Web · Jetson 실행, 실기 안전 제어, 추론 속도(scripter 보고서 26 행).
- 실기 calf 토크 · 속도 한계(공식 파일 둘이 다름, 조건표 §3.2a).
