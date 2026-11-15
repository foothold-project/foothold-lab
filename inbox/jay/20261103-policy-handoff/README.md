> 분류: A/정책학습 · 정책 → 앱 전달 묶음 안내 (색인)
> 작성: 오흥재 · lead 세션 · 2026-11-03 16:3x v0.1 · 2026-11-09 10:3x v0.4 (start 새 판 start-m13000 · 만드는 명령)
> 근거: 이 폴더의 문서 셋 · WORKLIST D107 · D108 · D144 · D162 · D169 · foothold-app dev `20f3d066` (2026-11-03 09:19Z)
> 요지: 정책을 앱에 넘기는 일을 문서 셋으로 나눴다. 사람마다 자기 문서 하나만 읽으면 되고, 세 문서는 같은 이름 규칙과 같은 저장소 배치를 쓴다
> 상태: v0.4 · start 새 판 `start-m13000-app/` (EX-42 0 단계 m13000) · 앞 판 start-demo(PR #571) · ame2-demo(PR #574 + 보완) 그대로 · 앱 적용은 `HANDOFF-APP-DEVELOPER.md` v0.4 하나만 본다

# 정책 → 앱 전달 묶음

| 문서 | 누가 읽나 | 무엇을 하게 되나 |
|---|---|---|
| [HANDOFF-APP-DEVELOPER.md](HANDOFF-APP-DEVELOPER.md) | 오현민 (앱) | 앱에 「모드」 넷(nvidia · start · ame2 · go2)을 두고, 모드마다 값을 통째로 갈아 끼우는 구조를 만든다. 답(값)을 먼저 준다 |
| [HANDOFF-AME2-WORKER.md](HANDOFF-AME2-WORKER.md) | 임석헌 (AME-2) | 지시문 하나로 AME-2 저장본에서 ONNX · contract.json · 확인 기록을 뽑아 올린다 |
| [HANDOFF-START-m6000-ONNX.md](HANDOFF-START-m6000-ONNX.md) | 오흥재 · lead (START) | m6000 ONNX 묶음이 무엇이고 어디까지 확인됐는지, 앱에 넘기기 전에 남은 것 |
| [MAKE-APP-BUNDLE.md](MAKE-APP-BUNDLE.md) · `make_start_app_bundle.py` | START 묶음을 만드는 세션 누구나 | 저장본 경로 · sha · 이름을 주면 같은 꼴의 묶음이 명령 하나로 나온다(m13000 첫 사용) |
| [start-m13000-app/CONTRACT.md](start-m13000-app/CONTRACT.md) | 오현민 (앱) · lead | m13000 이 m6000 과 무엇이 다른지(입출력은 같음 · 후진 범위 1.3) |

## 지금 사실 (2026-11-03 16:3x)

- 앱(foothold-app dev `6740de88`)에 들어 있는 정책은 **둘**: `foothold-v2`(기본, 예전 v2 정책) · `ame2-demo`(석헌 님 AME-2 teacher m14999). 둘 다 ONNX 를 기본으로 돌리고(ORT Web WASM · Worker), 실패하면 예전 f32 JS 계산으로 되돌린다(앱 `docs/spec/11-POLICY-ADAPTER.md:332~382`).
- **START(우리 m6000) 는 아직 앱에 넘기지 않았다.** 앱에도 없다(`mobile/sim/policy-adapters.js:2` 「START remains undefined」). ONNX 묶음만 준비돼 있다.
- 앱의 시뮬 전진 상한은 오늘 1.5 m/s 로 올라갔다(앱 커밋 `280a02c0`).

## start 새 판 (2026-11-09 · v0.4)

- start 모드의 지금 판은 `start-m13000-app/` 이다. 저장본 EX-42 0 단계 `model_1000.pt`(누적 13000 update) · sha `20365a2c…`. 팀장 11/09 10:0x 「m13000 ONNX 를 git 으로 팀원 · 앱에 전달하고 앞으로 같은 절차로 반복」.
- m6000 에서 바뀐 것: ① 파일 이름 · sha ② actor 안의 자세 명령 2 칸(학습 내내 0 이라 ONNX 안에서 0 고정 · 앱 입력 아님) ③ 학습 때 지도가 정답 고정에서 정답 · 복원 섞음으로 ④ 후진 학습 범위 −1.0 → −1.3 (앱 상한 후진 1.3). ONNX 입출력 이름 · 모양 · 자료형은 같다. 자세한 표는 `start-m13000-app/CONTRACT.md` §1.
- 같은 출력 확인(CPU onnxruntime 1.28.0): 합성 최대 7.63e-6 · Kit 기록 입력 9 × 20 스텝 되먹임 최대 3.46e-6. Kit 기록은 m6000 이 몬 궤적이라 m13000 이 스스로 걸은 궤적은 아니다(미확인으로 둠).
- 다음 판(E0 · E1 …)은 `MAKE-APP-BUNDLE.md` 의 명령 하나로 같은 꼴을 만든다.

## 이름 규칙 (팀장 11/03 17:0x · D169 를 대체) · 네 문서 공통

| 모드 · 코드 키 | 지금 이름(데모) | 최종 이름 | 묶음 format | 무엇 |
|---|---|---|---|---|
| `nvidia` | `nvidia-demo` (앱의 지금 `foothold-v2`) | `nvidia-foothold-v2` | (앱 기존 `policy_v2.onnx` · f32) | NVIDIA 기반으로 학습한 예전 v2 정책. 지금은 앱의 JS MLP 계산이 원본 actor 와 맞는지만 확인 |
| `start` | `start-demo` (저장본 m6000) | `start-oh2l2` | `start-demo-onnx/1` | 우리 START 계열 |
| `ame2` | `ame2-demo` (저장본 m14999) | `ame2-oh2l2` | `ame2-demo-onnx/1` | 석헌 님 AME-2 계열 |
| `go2` | (새로) | `go2-demo` | 정책 없음 | SDK 로 받은 실기 Go2 움직임(관절 · 자세)을 시뮬 화면에 그리기만. 실기는 순정 Go2 Sport 모드 |

- ONNX 파일 이름 = 이름 + `.onnx` (start 는 `_map_on` · `_map_off` 둘). 앱 adapter id 도 같은 이름. 어느 저장본인지는 contract.json 의 `checkpoint` · `checkpoint_sha256` 에 적는다.
- 최종 모델은 최종 이름으로 ONNX 를 새로 받는다. 입출력 이름 · 모양이 바뀌면 format 끝 `/1` 을 올린다.

## 진행 순서 (팀장 11/03 17:0x)

1. 석헌 님이 `HANDOFF-AME2-WORKER.md` 지시문으로 ame2-demo 묶음을 만들어 PR.
2. lead 가 start-demo 묶음을 같은 꼴로 마무리(`HANDOFF-START-m6000-ONNX.md` §3).
3. **팀장이 두 PR 을 검증**한 뒤 현민 님에게 전달.
4. 현민 님이 `HANDOFF-APP-DEVELOPER.md` 대로 앱에 적용. 앱 구조(모드 등록부 · 실행기)는 1~3 을 기다리지 않고 먼저 만든다(값은 앱 문서 §1 에 이미 있다).

## 저장소 배치 (ONNX 도 lab 에 올린다 · 팀장 11/03 17:0x)

```
inbox/jay/20261103-policy-handoff/<이름>-app/        앱이 보는 폴더 둘: start-m13000-app/ (v0.4 · 앞 판 start-demo-app/) · ame2-demo-app/
  <이름>.onnx            ONNX (start-demo 는 start-demo_map_on.onnx · start-demo_map_off.onnx)
  CONTRACT.md            사람이 읽는 조건표 (값마다 파일:줄 · 등급)
  contract.json          앱이 옮겨 적는 기계 계약 (입출력 이름 · 모양 · 식 · 값 · checkpoint · 각 ONNX 의 sha256 · bytes)
  parity.json            원본 대 ONNX 같은 출력 확인 (스텝 수 · 최대 차이 · 통과)
  test_vectors_flat20.json  앱이 자기 구현을 맞춰 볼 입력과 정답 출력 (같은 내용 .npz 도, 꼴은 앱 문서 §2-5a)
  SHA256SUMS             이 폴더 모든 파일의 sha256
```

- 앱은 `start-demo-app/` · `ame2-demo-app/` 둘만 본다. ame2 는 석헌 님 제출 폴더 `inbox/lim/20261103-policy-handoff/ame2-demo/` (참고 · 제출 기록) 의 파일을 그대로 복사하고 lead 보완(json 시험 벡터 · app_onnx.json)을 더했다.
- 나중 판 이름: 학습 완료 판은 `start-oh2l2-app/` · `ame2-oh2l2-app/` 로 같은 꼴의 폴더를 새로 만든다(D170 최종 이름 + `-app`). 학습 도중 판은 누적 update 수로 `start-m<누적>-app/` (예: `start-m13000-app/` · v0.4 에서 처음 씀, 최종 이름 규칙은 그대로).
- 문서 · 계약 · 확인 기록이 모두 ONNX 의 sha256 을 가리키므로, 앱은 받은 ONNX 의 sha256 이 contract.json · SHA256SUMS 와 같을 때만 쓴다.
- 한 파일 100 MB 를 넘으면 GitHub 가 거절한다(ONNX 는 수 MB 라 괜찮다 · .pt 는 올리지 않는다).
- 앱 저장소에는 ONNX 를 커밋하지 않고, lab 의 이 폴더에서 앱 자산 폴더(`FH_POLICY_ONNX_SRC`)로 복사한다(앱 spec 11:321,387,422-423).

올리는 법(AGENTS 규칙): main 에서 브랜치 `inbox-<이름>-<무엇>` → 자기 `inbox/<이름>/` 아래만 커밋 → PR → 팀장 머지. `docs/` 는 건드리지 않는다. 문장에 em dash(가로로 긴 줄표)를 쓰지 않는다.
