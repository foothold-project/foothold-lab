> 분류: A/정책학습 · START 앱 묶음을 만드는 절차 (명령 하나)
> 작성: 오흥재 · lead 세션 · 2026-11-09 10:3x v0.1
> 근거: `make_start_app_bundle.py` (이 폴더) · m6000 내보내기 `foothold_s2/deploy/export_ex40_w89.py` · `verify_ex40_w89.py` (34982e13) · 실입력 비교 `package_ex40_real20.py` (a10af76f) · 팀장 11/09 10:0x 「앞으로 같은 절차로 반복」
> 요지: 저장본 경로 · sha · 이름 셋을 주면 `start-demo-app/` 과 같은 꼴의 폴더(ONNX 둘 · 계약 · 같은 출력 확인 · 시험 벡터 · SHA256SUMS)가 나온다. 같은 입력이면 모든 파일이 바이트까지 같다
> 상태: v0.1 · start-m13000 으로 두 번 돌려 13 파일 바이트 같음 · m6000 으로 돌려 lab 의 start-demo ONNX 두 파일과 바이트 같음 · CPU 만 씀

# START 앱 묶음 만드는 법

## 1. 명령 하나

PowerShell 이 아니라 Git Bash 에서. GPU 를 쓰지 않는다(스크립트가 두 자식 프로세스에 `CUDA_VISIBLE_DEVICES=` 를 건다).

```bash
H=<lab 작업 사본>/inbox/jay/20261103-policy-handoff
python $H/make_start_app_bundle.py all \
  --checkpoint "C:/Users/AI-WS01/s2_lab/<run>/main/<run 폴더>/model_<N>.pt" \
  --sha256 <저장본 sha256> \
  --name start-m<누적 update> \
  --label "<실험> <단계> model_<N> = cumulative m<누적>" \
  --contract-md <새로 쓴 CONTRACT.md> \
  --out $H/start-m<누적 update>-app
```

이번 판(m13000)에 실제로 쓴 값:

```bash
python $H/make_start_app_bundle.py all \
  --checkpoint "C:/Users/AI-WS01/s2_lab/ex42_main_20261108_123914/main/EX-42-B-stagezero_20261108_123914/model_1000.pt" \
  --sha256 20365a2c6d70f94f65f1114471f7df198e56d86db6d02d89cea43c666b95e768 \
  --name start-m13000 \
  --label "EX-42 stage 0 (EX42_0_T0_prime) model_1000 = cumulative m13000" \
  --contract-md D:/mai-tmp/lead/onnx-m13000-1109/CONTRACT-start-m13000.md \
  --out $H/start-m13000-app
```

이미 올린 판을 다시 만들어 맞춰 보려면 `--contract-md` 에 그 폴더의 `CONTRACT.md` 사본을 주고 `--out` 을 다른 자리로 준 뒤 `diff -r $H/start-m13000-app <다른 자리>` 가 비어 있는지 본다.

`python` 은 onnxruntime 이 있는 base anaconda(`C:/Users/AI-WS01/anaconda3/python.exe`). torch 쪽은 스크립트가 isaac311(`--torch-python`)로 따로 부른다. m6000 때와 같은 나눔이다(torch 와 onnxruntime 을 한 프로세스에 두지 않는다).

## 2. 스크립트가 하는 일 (순서)

1. 저장본 sha256 을 재서 `--sha256` 과 다르면 멈춘다. `--out` 이 이미 있으면 멈춘다.
2. 저장본 옆 `manifest.json` 의 `git.head`(학습한 코드)에서 `foothold_s2` 를 `git archive` 로 꺼낸다. 학습 때 소스가 바뀐 채였거나(`dirty_diff_bytes`), 꺼낸 `start_perception.py` 의 sha 가 학습 때 불러온 것과 다르면 멈춘다.
3. m6000 때 쓴 스크립트 넷을 고정 커밋에서 그대로 얹는다: 내보내기 · 합성 비교(34982e13), 실입력 기록 상수 · 20 스텝 비교(a10af76f).
4. torch 단계(isaac311): m6000 내보내기 함수를 그대로 부르고, 저장본을 읽는 함수 하나만 바꾼다(원래 것은 iter 6000 · m6000 sha · actor 96 칸에 묶여 있다). actor 입력이 98 칸이면 자세 명령 2 칸을 그래프 안에서 0 으로 붙인다. ONNX checker · 합성 입력 12 경우 · Kit 기록 입력 9 경우 × 20 스텝의 PyTorch 답을 만든다.
5. ORT 단계(base): 합성 비교(기준 3e-5) · 20 스텝 되먹임 비교(기준 1e-4)를 m6000 함수 그대로 돌린다. ONNX 입출력이 `start-demo-app/contract.json` 의 `app_onnx` 칸과 한 칸이라도 다르면 멈춘다(그때는 format 을 `/2` 로 올리고 앱 문서를 손으로 고친다).
6. 통과하면 폴더를 만든다: ONNX 둘 · `CONTRACT.md`(준 파일 사본) · `contract.json` · `parity.json` · 시험 벡터 json 넷 · npz 넷 · `.gitattributes`(`* -text`) · `SHA256SUMS`.

## 3. 사람이 할 일 (스크립트 앞뒤)

| 때 | 할 일 |
|---|---|
| 앞 | 이름을 정한다. 학습 도중 판은 `start-m<누적 update>`, 학습 완료 판은 `start-oh2l2` (README 이름 규칙) |
| 앞 | `CONTRACT.md` 를 새로 쓴다: 앞 판과 다른 것만 표로(저장본 · actor 입력 · 학습 지도 · 명령 범위). 명령 범위는 run 폴더 `ex42_application.jsonl` 의 `stage_config.ranges` 같은 실제 기록에서 옮긴다. 숫자(같은 출력 차이)는 첫 실행의 `parity.json` 을 보고 적은 뒤 다시 돌린다 |
| 뒤 | 같은 명령을 다른 `--out` 으로 한 번 더 돌려 `diff -r` 가 비어 있는지 본다 |
| 뒤 | 폴더 안에서 `sha256sum -c SHA256SUMS` 전부 OK |
| 뒤 | `README.md` · `HANDOFF-APP-DEVELOPER.md` 의 파일 표를 새 판으로 바꾸고 「앞 판에서 바뀐 것」 을 적는다 |
| 뒤 | 브랜치 · PR(main 머지는 팀장). ONNX 는 LFS 가 아니라 보통 파일로 올린다(start-demo · ame2-demo 와 같음, 폴더 `.gitattributes` 가 `* -text`) |

## 4. 알아 둘 것

- 실입력 기록(`D:/mai-tmp/scripter/start_demo_real20_20261103_try03/`)은 m6000 이 몬 Kit 기록이다. 새 저장본에는 GRU 상태만 자기 것으로 이어 넣으므로 「입력 정렬과 ONNX 가 같은 답을 내는가」 를 보는 시험이고, 새 저장본이 스스로 걸은 궤적이 아니다. 새 기록이 필요하면 GPU 와 Kit 이 드는 `capture_ex40_real20.py` 를 따로 돌리고 `--capture-dir` 로 준다.
- 시험 벡터 npz 는 zip 시각을 1980-01-01 로 고정해 쓴다(같은 배열이면 같은 바이트).
- 이 기기 경로가 기본값이다(`--torch-python` · `--ort-python` · `--capture-dir`). 다른 기기에서는 셋을 넘긴다.
