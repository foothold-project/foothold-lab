> 분류: A/정책학습 · 앱 전달 (start 모드 새 판 = 정본 3 · agent 가 이 문서 하나로 진행)
> 작성: planner-lx · 2026-11-17 11:3x v0.1 (lead 11:22 의뢰 · 팀장 11/17 지시 요지: 팀원 전달 문서를 정본 3 으로 갱신하고 agent 가 바로 읽고 진행할 수 있게)
> 근거: 묶음 `start-m15500-app/` (이 폴더 · 만든 기록은 lab 가지 `feature/fable-25a-jay` 커밋 `6fbd0eb1`) · 그 안의 `CONTRACT.md` · `contract.json` · `parity.json` · 정본 3 기록 문서 (아래 링크) · 앞 판 문서 `HANDOFF-APP-DEVELOPER.md` v0.4 · `APP-AGENT-GUIDE-1109.md` v0.2 · reviewer-lx 초안 `APP-HANDOFF-DRAFT-1116` 3.2a 절 (읽기)
> 요지: start 모드의 정책을 m13000 에서 **m15500 (정본 3)** 으로 바꾼다. ONNX 입출력은 앞 판과 같아서 앱 실행기는 그대로다. 바꿀 것은 파일 · sha 와 명령 상한 몇 칸이고, 새로 알아야 할 것은 둘이다: 속도 보정이 ONNX 안에 들어 있다 (앱이 더하지 않는다) · 걷는 속도를 앱이 0.4~0.8 m/s 로 고정할 필요가 없다
> 상태: v0.1 · 묶음 만듦 · CPU 같은 출력 확인 끝 · 앱 적용 · 브라우저 · 폰 · 실기는 미확인 · PR 로 올림 (main 병합은 팀장)

# start 새 판 · 정본 3 (m15500) 앱 전달

## 0. 한눈에

| 물음 | 답 |
|---|---|
| 무엇인가 | Go2 기본 보행 정책의 새 판. 속도 명령 (앞뒤 vx · 옆 vy · 회전 wz) 을 받아 걷는다. 학습 실험 EX-42 의 E1F 단계 `model_250.pt` 이고 처음부터 누적 15,500 update 다. 뒤 단계 (지형 · 미션) 가 모두 이 저장본에서 갈라져 나가서 「정본 3」 이라 부른다 |
| 어디 있나 | 이 폴더의 `start-m15500-app/` (ONNX 둘 · 계약 · 같은 출력 확인 · 시험 벡터 · `SHA256SUMS`) |
| 앞 판 (m13000) 과 무엇이 같은가 | ONNX 입력 9 · 출력 4 의 이름 · 순서 · 모양 · 자료형. 지도 모드 셋 (정답 · 복원 · 끔) 과 파일 고르는 법. 상태 되먹임. 그래서 **실행기 코드는 고칠 것이 없다** |
| 무엇이 다른가 | 파일 이름 · sha · 명령 학습 범위 (옆 · 회전 · 걸으며 회전이 넓어짐) · 속도 보정이 ONNX 안에 있음 · 지각 가중치가 학습 평균 판 |
| 앱이 할 일 | 1 절의 여섯 단계 |
| 아직 안 된 것 | 듬성한 지형 (징검돌 · 틈) 은 배우지 않았다. 계단을 올라 멈췄다 다시 갈 때 한쪽으로 도는 약점이 있다 (4 절) |

## 1. 할 일 (순서대로 · agent 용)

`APP-AGENT-GUIDE-1109.md` 의 ① (정책 교체) 을 폴더 · 파일 이름 · sha 만 바꿔 그대로 반복한다. 그 문서의 ②~④ 는 이미 했으면 다시 하지 않는다.

### 1-1. 받기

```bash
# 일 폴더 (새 빈 폴더) 에서. main 에 병합되기 전이면 REF=feature/planner-canon3-app-handoff-1117 로 받는다 (이 문서를 올린 가지).
REF=main
mkdir -p start-m15500-app && cd start-m15500-app
P=inbox/jay/20261103-policy-handoff/start-m15500-app
for f in start-m15500_map_on.onnx start-m15500_map_off.onnx contract.json parity.json CONTRACT.md SHA256SUMS \
         test_vectors_flat20.json test_vectors_flat20_reconstruction.json test_vectors_flat20_gt.json test_vectors_flat20_off.json; do
  curl -fsSL -o "$f" "https://raw.githubusercontent.com/foothold-project/foothold-lab/$REF/$P/$f"
done
sha256sum -c SHA256SUMS 2>/dev/null | grep -v ': OK$'    # 받은 열 파일에서 OK 가 아닌 줄이 없어야 한다 (안 받은 npz 줄은 「없음」 으로 나온다)
```

저장소를 통째로 받았다면 그 폴더에서 `sha256sum -c SHA256SUMS` 가 13 줄 모두 OK 여야 한다. 폴더의 `.gitattributes` 가 `* -text` 라 Windows 에서 받아도 sha 가 같다.

### 1-2. 파일과 sha (앱의 허용 목록에 넣는 값)

| 파일 | 쓰임 | 크기 (바이트) | sha256 |
|---|---|---|---|
| `start-m15500_map_on.onnx` | 지도 켬 (정답 · 복원 모드) | 5,816,755 | `df91c2d772c7d054e33c74fca479e79550cfd228d7682402f7eef4a0865e279f` |
| `start-m15500_map_off.onnx` | 지도 끔 | 5,826,586 | `be6c8b103d3b39503447ee71076ec199e5ed0688c3540ccfe449a96d6e2a9a41` |
| `contract.json` | 기계 계약 (`app_onnx` 칸은 앞 판과 같음) | | `5759e105cdfe44bf80eae2162d233e3fa9f985124694935a040519408aeec17d` |
| `test_vectors_flat20_reconstruction.json` (= `test_vectors_flat20.json`) | 복원 모드 시험 벡터 | | `90f4eae3e20409ac9061254dcf7fe49bf6dc5da8747b629b0f72890b7f2cbd8e` |
| `test_vectors_flat20_gt.json` | 정답 모드 시험 벡터 | | `55421a7c9b57b204ac8ff4cec0851edbc26c0f92aa2e62e954e94267f67b0308` |
| `test_vectors_flat20_off.json` | 끔 모드 시험 벡터 | | `1dc548690becda8336c204d65e0cc1be11f10c9b8e322fe3f27913f7a2fb00dc` |

나머지 (npz · `parity.json` · `CONTRACT.md`) 의 sha 는 폴더 `SHA256SUMS` 에 있다.

### 1-3. 앱에서 바꿀 곳

앞 판 지시서 (`APP-AGENT-GUIDE-1109.md` ① 의 「바꿀 곳」 표) 가 m6000 → m13000 으로 바꾼 바로 그 자리들을 m13000 → m15500 으로 바꾼다. 그 표의 줄 번호는 foothold-app `dev` `2f1ef45` 기준이라 지금 dev 에서는 옮겨졌을 수 있다. **줄 번호가 아니라 `start-m13000` 글자를 검색해서 찾는다.**

```bash
# foothold-app 작업 사본에서
grep -rn "start-m13000\|4799677a\|8317548f" --include='*.js' --include='*.mjs' --include='*.py' --include='*.md' --include='*.json' . | grep -v node_modules
```

찾은 자리마다: 파일 이름 `start-m13000_map_on/off.onnx` → `start-m15500_map_on/off.onnx` · sha → 1-2 의 값 · 폴더 `start-m13000-app` → `start-m15500-app` · 출처 문서 줄 (`docs/POLICY-PROVENANCE.md`) 에 크기와 이 문서 경로.

### 1-4. 넣지 말 것 · 고치지 말 것

- **속도 보정을 앱에 넣지 않는다.** 이 정책은 학습 때 「지각이 추정한 앞 속도」 를 느린 띠 (0~0.3 m/s) 에서 조금 낮추는 보정 (b = 0.010 m/s) 을 쓴다. 그 식은 **ONNX 그래프 안에 이미 들어 있다.** 앱이 같은 보정을 한 번 더 하면 두 번 걸려 느린 걸음이 달라진다. ONNX 입력에도 이 값은 없다.
- **입력을 98 칸으로 바꾸지 않는다.** 98 은 ONNX 안쪽 actor 의 입력 수 (몸감각 45 + 지각 추정 51 + 자세 명령 2) 다. 지각 추정 51 칸은 ONNX 가 깊이 영상에서 스스로 만들고, 자세 명령 2 칸은 ONNX 안에서 0 으로 고정돼 있다. 앱이 넣는 것은 앞 판과 똑같은 아홉 입력이다: `obs45` [1,45] · `hist` [1,10,45] · `depth2` [1,2,60,60] · `h_prop` [1,128] · `h_terr` [1,128] · `depth_tick` · `first_after_reset` · `use_gt` (bool [1]) · `gt_map` [1,32,16].
- 지각 가중치 (학습 평균 판) 도 ONNX 안의 일이다. 앱이 할 것은 없다.

### 1-5. 명령 상한 (앱이 깎는 값)

| 명령 | m13000 학습 범위 | m15500 학습 범위 | 앱 상한을 어떻게 |
|---|---|---|---|
| 전진 vx | 0.1~1.5 | 0.1~1.5 | 그대로 (1.5) |
| 후진 vx | −1.3~−0.2 | −1.3~−0.2 | 그대로 (1.3) |
| 옆 \|vy\| | 0.2~0.6 | **0.1~0.8** | 0.5 → 0.8 까지 올릴 수 있다 |
| 제자리 회전 \|wz\| | 0.3~1.5 | **0.15~1.5** | 그대로 (1.2) · 느린 쪽 0.15 까지 됨 |
| 걸으며 회전 | wz 0.2~1.0 · vx 0.3~0.8 | **wz 0.1~1.0 · vx 0.3~1.2** | wz 1.0 그대로 · 그때의 vx 는 1.2 까지 |
| 대각 | vx 0.3~0.6 · vy 0.2~0.5 | 같음 | 그대로 |
| 걷는 중 회전 덧붙임 | 없음 | 걷는 명령의 25 % 에 wz 0.2~0.6 을 얹어 학습 | 직진 중 작은 방향 고침을 주어도 된다 |

범위 밖 값은 앱이 자른다. 상한을 실제로 올릴지는 앱 담당이 화면 · 안전을 보고 정한다. 이 표는 「학습이 다룬 범위」 만 적는다. 값의 출처는 학습 기동 로그의 명령 줄 (`EX42_SEGMENT_COMMANDS`) 이고 `start-m15500-app/CONTRACT.md` 1 절에 같은 표가 있다.

### 1-6. 걷는 속도를 고정하지 않는다 (목표 찍기 · 조이스틱)

앞 판까지 앱은 START 모드에서 걷는 속도를 0.4~0.8 m/s 로 고정해 두었다 (reviewer-lx 초안 3.2a 절의 설명 · foothold-app `dev` `1afae1ed` 기준 · 내가 앱 코드를 열어 확인하지는 않았다). 이 판에서는 그 고정이 필요 없다.

| 무엇 | 바꿀 것 | 까닭 |
|---|---|---|
| 조이스틱 · 목표 찍기 때 속도 | 고정을 풀고 1-5 범위 안의 값을 그대로 준다 (느린 0.1 m/s 포함) | 이 판은 느린 띠 0.1~0.3 m/s 와, 방향이 계속 바뀌는 명령 (깃발 따라가기) 을 학습했다. 느린 전진 0.1 m/s 명령에 실제 0.094 m/s 로 걷는다 (정답 지도 · 시뮬 64 대 가운데 57 대가 기준 안) |
| 목표 지점 → 속도 명령 | 학습이 쓴 식을 그대로 옮긴다: lab 코드 `foothold_s2/commands/mixed_core.py` 의 `flag_step`. 몸 기준 목표 방향의 단위 벡터 × 속도 v 를 (vx, vy) 로 주고, 동시에 wz = 방향 각을 ±1 rad/s 로 자른 값. v 가 0.3 m/s 보다 작으면 제자리 회전 | 정책은 이 식이 만든 명령으로 배웠다. 식이 같으면 시뮬에서 본 움직임이 앱에서 그대로 나온다 |
| 움직이는 모양 | 「먼저 돌고 나서 직진」 이 아니라 「걸으며 돈다」 (vx · vy · wz 를 한꺼번에 준다) | 깃발이 옆 90 도에 있을 때 약 1.9 초에 몸이 깃발 쪽을 본다 (시뮬 64 / 64 도착) |

- 이 절은 모드 2 (START 보행 + 속도 명령) 에만 해당한다. 석헌 님 AME-2 모드는 목표 지점을 받는 정책이라 앱의 기존 경로 계획을 그대로 쓴다.
- 고친 뒤에는 이 표 아래에 foothold-app 커밋 sha 를 적는다.

### 1-7. 확인 (답을 아는 입력으로 먼저)

1. 시험 벡터: `HANDOFF-APP-DEVELOPER.md` 2-4 의 방법 그대로, 세 모드 (`reconstruction` · `gt` · `off`) 의 20 스텝을 앱 실행기로 돌려 `expected` 와 최대 차이 1e-4 안인지 본다. 앞 판에서 통과하던 시험이 파일만 바꿔 다시 통과해야 한다.
2. 보정을 두 번 걸지 않았는지: 시험 벡터가 통과하면 앱이 보정을 더하지 않은 것이다 (더했다면 행동이 0.01 넘게 달라져 1 에서 걸린다).
3. 느린 걸음: 시뮬 화면에서 전진 0.1 m/s 명령을 6 초 준다. 약 0.4~0.6 m 를 가면 맞다 (출발 가속 때문에 0.1 × 6 보다 조금 짧다). 제자리에 서 있거나 1 m 넘게 가면 명령이 정책까지 가는 길 (가감속 제한 · 상한 깎기) 을 본다.
4. 보고: `APP-AGENT-GUIDE-1109.md` ⑥ 과 같은 자리 (lab 이슈 #591) 에 「m15500 으로 바꿈 · 시험 벡터 세 모드 최대 차이 · 느린 걸음 거리」 를 적는다.

## 2. 묶음 안 (m13000 과 같은 꼴)

```
start-m15500-app/
  start-m15500_map_on.onnx · start-m15500_map_off.onnx    ONNX 둘
  CONTRACT.md            m13000 과 다른 것만 적은 조건표
  contract.json          기계 계약 (format start-m15500-onnx/1 · app_onnx 칸 · vx_corr 칸 · perception_weights 칸)
  parity.json            같은 출력 확인 기록
  test_vectors_flat20{,_reconstruction,_gt,_off}.{json,npz}   평지 20 스텝 입력과 정답 출력
  SHA256SUMS
make_canon3_app_bundle.py   이 묶음을 만든 명령 (make_start_app_bundle.py 에서 두 곳을 고친 사본)
```

`contract.json` 에 새로 생긴 칸 둘: `vx_corr` (보정식 · b 0.010 · `inside_graph: true`) 와 `perception_weights` (`source: ema`). 앱이 읽어 쓸 필요는 없고 기록이다.

## 3. 같은 출력 확인 (CPU · 만든 쪽에서 한 것)

| 확인 | 결과 |
|---|---|
| PyTorch 대 onnxruntime · 합성 입력 12 경우 | 최대 차이 1.05e-5 (기준 3e-5) |
| PyTorch 대 onnxruntime · Kit 기록 입력 9 경우 × 20 스텝 (GRU 되먹임) | 최대 차이 7.48e-6 (기준 1e-4) |
| 보정이 ONNX 안에 들었나 | 보정을 뺀 PyTorch 와는 행동 차이 0.013~0.017 인데 ONNX 는 보정 넣은 PyTorch 와 같다 |
| 보정식이 학습 코드와 같은가 | 학습 함수와 격자 1,601 점 대조 · 차이 0 |
| ONNX 입출력이 앞 판과 같은가 | 같다 (m6000 계약의 `app_onnx` 칸과 한 칸씩 대조) |
| 다시 만들면 같은가 | 세 번 만들어 폴더 전체가 바이트까지 같음 |

실행 환경: onnxruntime 1.32.0 · onnx 1.22.0 · torch 2.7.0 (CPU). 기록 입력은 m6000 이 로봇을 몰 때 남긴 것이라 이 표는 「ONNX 가 PyTorch 와 같은 답을 낸다」 까지만 말한다. 걸음 성적은 4 절이다.

## 4. 이 판이 하는 것 · 못 하는 것 (시뮬 64 대 · 시드 하나)

| 과제 | 정답 지도 | 복원 지도 | 지도 끔 |
|---|---|---|---|
| 느린 전진 0.1 m/s (평탄 L0 · 기준 안에 든 수) | 57 | 55 | 59 |
| 깃발 따라가기 (옆 90 · 뒤 180 도에서 출발 · 도착 수) | 64 | 64 | 64 |
| 계단 올라 멈췄다 다시 가기 (도착 수) | 22 | 46 | 5 |

- 평탄 · 완만한 지형에서 전진 · 옆 · 뒤 · 회전 · 정지 · 깃발 따라가기를 한다.
- **약점 1**: 계단을 올라 멈췄다 다시 출발할 때 일부가 한쪽으로 약 35 도 돌아 층계참을 벗어난다 (복원 지도에서 64 대 가운데 18 대). 앱에서 계단 위 정지 뒤 재출발을 시연할 때는 이것을 알고 한다.
- **약점 2**: 듬성한 지형 (징검돌 · 틈 · 외다리) 은 아직 배우지 않았다. 다음 단계 (E2 이후) 의 일이다.
- 반복 시드를 재지 않았다. 숫자는 시드 42 한 번이다.

자세한 기록 · 계보 · 영상: [정본 3 기록 문서](https://github.com/foothold-project/foothold-lab/blob/feature/fable-25a-jay/inbox/jay/20261102-ex42/CANON3-E1F-m250-1117.md) (lab 가지 `feature/fable-25a-jay`).

## 5. 미확인

- 미확인: 앱 Node · 브라우저 ORT (WASM) 에서의 최대 차이와 추론 시간. 1-7 의 1 을 통과해야 이 판을 켠다.
- 미확인: 이 저장본이 Kit 에서 스스로 걸을 때의 입력으로 한 ONNX 같은 출력 확인.
- 미확인: 실기 (Orin · 깊이 카메라 · 관절 스트림 정렬 · 안전 제어). 이 묶음은 웹 시뮬용이다. 실기에서 50 Hz 로 도는 길은 따로 정한다.
- 미확인: 1-6 의 「앱이 지금 속도를 0.4~0.8 로 고정한다」 는 앱 코드 사실 (reviewer-lx 초안을 옮김). 고치기 전에 앱 코드에서 그 자리를 먼저 찾는다.
