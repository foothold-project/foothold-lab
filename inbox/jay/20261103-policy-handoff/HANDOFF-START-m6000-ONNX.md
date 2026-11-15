> 분류: A/정책학습 · START m6000 ONNX 전달 파악 문서
> 작성: 오흥재 · lead 세션 · 2026-11-03 16:3x v0.1
> 근거: 조건표 정본 `inbox/jay/20261101-app/APP-POLICY-CONTRACT-m6000.md` v0.3.1 (lead 가지 dc81513c) · 묶음 `D:/mai-tmp/lead/start-demo-onnx/` (scripter 34982e13 묶음을 D169 이름으로 바꾼 사본, ONNX 바이트 같음) · scripter `REPORT-W89-m6000-ONNX-CPU-1102.md` · 내보내기 `foothold_s2/deploy/export_ex40_w89.py`
> 요지: m6000 은 지각(TR-Net · I-E, GRU 둘) + actor 를 ONNX 두 파일(지도 켬 · 끔)로 내보냈고, 합성 입력으로 PyTorch 와 최대 5e-6 차이다. **아직 팀원에게 넘기지 않았다.** 넘기기 전에 실제 학습 기록 입력으로 같은 출력 확인 · 시험 벡터 · ORT Web 확인 · 묶음 파일 셋이 남았다
> 상태: v0.2 · **전달 완료**(lab PR #571 머지 · foothold-app#259 에 알림) · 실제 Isaac 입력 20 스텝 상태 되먹임 최대 차이 3.46e-6 · 남은 것 없음(앱 적용은 현민 님) · **2026-11-09: start 새 판은 `start-m13000-app/` (m6000 에서 바뀐 것은 그 폴더 `CONTRACT.md` §1 · 만드는 명령 `MAKE-APP-BUNDLE.md`). 이 문서는 m6000 기록으로 남긴다**

# START m6000 ONNX 전달 파악

앱이 받는 쪽 일은 `HANDOFF-APP-DEVELOPER.md` §1.2 `start` 열 · §3-3.

## 공통 규칙 (이 문서만 보고 일할 수 있게 같은 내용을 세 문서에 모두 둔다 · 2026-11-03 19:3x 판)

**이름(D170 · go2 지금 이름 D175).** 모드 코드 키 `nvidia` · `start` · `ame2` · `go2`. 지금 이름 `nvidia-demo`(앱의 옛 `foothold-v2`) · `start-demo`(저장본 m6000) · `ame2-demo`(저장본 m14999) · `go2-demo`(정책 없음, 실기 Sport 모드 상태를 그리기만). 최종 이름 `nvidia-foothold-v2` · `start-oh2l2` · `ame2-oh2l2` · `go2-oh2l2`. ONNX 파일 = 이름 + `.onnx`(start 는 `_map_on` · `_map_off` 둘). 묶음 format = 이름 + `-onnx/1`, 입출력이 바뀌면 `/1` 을 올린다.

**진행 순서.** ① lead 가 start-demo 묶음 · 석헌 님이 ame2-demo 묶음을 PR ② 팀장이 PR 검증 · 머지 ③ 현민 님이 앱에 적용. 현민 님은 ①을 기다리지 않고 앱 구조부터 만든다(값은 앱 문서에 있다).

**묶음 폴더(ONNX 도 lab 에 올린다).** `inbox/<올린 사람>/20261103-policy-handoff/<이름>/` 에 `<이름>.onnx` · `CONTRACT.md` · `contract.json`(입출력 이름 · dims · type · 실측 순서 · 각 ONNX sha256, 앱 adapter `onnx` 꼴은 `app_onnx` 칸) · `parity.json` · `test_vectors_flat20.json` 과 `.npz` · `SHA256SUMS` · `.gitattributes`(`* -text`, 바이트 그대로). 한 파일 100 MB 아래. 앱 저장소에는 ONNX 를 커밋하지 않고 이 폴더에서 복사해 sha256 을 맞춰 쓴다.

**정해진 것(다시 묻지 않는다).** ONNX 하나를 웹 시뮬과 실기가 함께 쓴다 · **앱 ONNX 실행기는 상태 출력(GRU)을 다음 호출 입력으로 되먹이고 입력 자료형(bool 포함)을 계약대로 만든다**(현민 님 몫, 앱 문서 §2-3 · §3-2) · start 는 f32 JS 신경망을 만들지 않는다 · 모드별 값은 통째로 갈아 끼우고 공통 기본값을 쓰지 않는다 · 지도 함수는 모드마다 따로 · ONNX 는 lab 공개 저장소에 올린다.

**미확인:** 명령 가속 제한 값(D108) · 정해질 때까지 지금 앱 동작 유지(가속 제한 없음).

**올리는 법.** main 에서 브랜치 → 자기 `inbox/<이름>/` 아래만 커밋 → PR → 팀장 머지. `docs/` 는 건드리지 않는다. 문장에 em dash(가로로 긴 줄표)를 쓰지 않는다.

## 1. 무엇이 있나

| 항목 | 값 | 확인 |
|---|---|---|
| 저장본 | `C:/Users/AI-WS01/s2_lab/ex40_main_20261031_041313/main/EX-40-B-main_20261031_041337_26240/model_6000.pt` · sha256 `d5e9ec40…` | 실측 |
| 이름 | `start-demo` (최종 `start-oh2l2`) · format `start-demo-onnx/1` | D169 |
| ONNX | `start-demo_map_on.onnx` 5,808,798 B sha `81c7e079…` · `start-demo_map_off.onnx` 5,818,629 B sha `5d1b7bf3…` | 실측(16:13 원본과 같음) |
| 입력 9 | `obs45[1,45] · hist[1,10,45] · depth2[1,2,60,60] · h_prop[1,128] · h_terr[1,128] · depth_tick[1] · first_after_reset[1] · use_gt[1] · gt_map[1,32,16]` (플래그 셋은 bool) | contract.json |
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

## 3. 넘기기 전에 한 것 (모두 끝남 · PR #571)

| # | 할 일 | 왜 | 담당 |
|---|---|---|---|
| 1 | 실제 학습 기록 입력으로 같은 출력: m6000 을 Isaac 에서 20 스텝 돌려 obs45 · hist · depth2 · h · action 을 기록하고 ONNX 에 그대로 넣어 action 1e-4 이하 | 지금 확인은 합성 입력이라 실제 입력 정렬(깊이 지연 · 이력 순서)을 못 본다 | runner 또는 scripter |
| 2 | `test_vectors_flat20.json` · `.npz` (위 1 의 평지 20 스텝, 지도 모드 셋 각각 · 꼴은 앱 문서 §2-5a · format `start-demo-test-vectors/1`) | 앱이 상태 되먹임까지 맞춰 볼 답 | 같음 |
| 3 | ORT Web(브라우저 WASM)에서 같은 입력 → 같은 출력 | 앱이 쓰는 실행기 | 현민 님 또는 scripter |
| 4 | `SHA256SUMS` · `CONTRACT.md`(= 조건표 정본 사본) · ONNX 두 파일을 같은 폴더에 | README 배치 | lead |
| 5 | 팀장 검증 뒤 현민 님에게 전달 | 끝(11/03 18:2x) | 팀장 |

## 4. 저장소에 놓을 꼴 (README 배치 그대로)

```
inbox/jay/20261103-policy-handoff/start-demo-app/
  CONTRACT.md            ← inbox/jay/20261101-app/APP-POLICY-CONTRACT-m6000.md v0.3.1 사본(정본은 그대로 두고 가리킴)
  contract.json          ← D:/mai-tmp/lead/start-demo-onnx/contract.json
  parity.json            ← comparison.json + 3 의 1 결과
  test_vectors_flat20.json · test_vectors_flat20.npz
  SHA256SUMS
  start-demo_map_on.onnx · start-demo_map_off.onnx
```

## 5. 미확인

- 미확인: 실기 카메라 · IMU · 관절 스트림 정렬, Jetson 실행, 실기 안전 제어 · 정해질 때까지 start 는 웹 시뮬 전용.
- 미확인: 브라우저 ORT Web 출력 · 추론 시간(20 ms 기한) · 정해질 때까지 앱 시험(`HANDOFF-APP-DEVELOPER.md` §2-4)이 잰다.
- 미확인: 실기 calf 토크 · 속도 한계(공식 파일 둘이 다름, 조건표 §3.2a) · 정해질 때까지 학습 값(45.43 N·m · 15.7 rad/s)을 넘지 않게 자른다.
