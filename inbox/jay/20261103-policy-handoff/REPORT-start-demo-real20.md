> 분류: A/정책학습
> 작성: 오흥재 (scripter 반영) · 2026-11-03
> 근거: EX-40 m6000 실제 저장본 · Kit 기록 9건 · ORT CPU 재생 · HANDOFF-APP-DEVELOPER §2-5a
> 요지: start-demo ONNX 두 파일은 실제 Kit 입력 9×20스텝에서 PyTorch action·hidden과 최대 3.4571e-6 차이
> 상태: 전달 묶음 준비 · ORT Web과 앱 입력 연결은 미확인

# start-demo m6000 실입력 20스텝 확인

## 묶음

`D:/mai-tmp/lead/start-demo/`에 D170 파일 이름의 ONNX 두 개, `CONTRACT.md`, `contract.json`, 합성·실입력 `parity.json`, 평지 벡터 JSON 세 벌·NPZ 세 벌과 합본 NPZ, `SHA256SUMS`를 만들었다. `SHA256SUMS`는 13개 파일을 가리키며 각 파일의 실제 해시를 다시 계산해 일치했다. 같은 입력으로 다른 폴더에 다시 생성한 SHA256SUMS도 바이트 일치했다. 최종 SHA256SUMS 자체의 SHA256은 `d71d647d61b1cf29e5c935fd47621b480a3714e3140d2743934949bea466fdeb`이다.

ONNX 두 파일은 바이트를 바꾸지 않았다. `start-demo_map_on.onnx`는 `81c7e079516058ee6243f6edd11efa8f0da239c6cc86fbca791bda5bcd82f110`, `start-demo_map_off.onnx`는 `5d1b7bf39aa0d9fb8ae33bf33dad82902165d53679ccd7ec5df727a0b70fe037`이다. 저장본 `model_6000.pt`의 실제 SHA256은 `d5e9ec400f33d74d97e7c69d4ab2092d4980195141bb8b30e683730eecd6b6f5`이다.

## 실제 입력과 비교

기록 코드는 `foothold_s2/deploy/capture_ex40_real20.py`이다. `FootholdS2-Go2-S2-SB-v0` 등록 cfg에서 EX-40 m6000의 actor·지각을 불러왔고, 관측·깊이 카메라·지도·이력·GRU 경로는 실제 평가기의 `S2Policy`를 썼다. 평가용으로 DR·지연·커리큘럼을 껐다. 1 env, 시드 42, 명령 전진 0.5 m/s로 20스텝씩 기록했다. 지형은 영 잡음 평지 참조 칸, 원래 `random_rough` L0, 원래 `stage_stairs` L2이다. 첫 칸은 학습 지형 분포의 무작위 표본이 아니라 평지 참조다. 모든 조합에서 reset 0회, `eval_gt`의 GT 사용 20/20, `eval_pred`와 `probe_prop_only`의 GT 사용 0/20이었다. 기록 원본은 `D:/mai-tmp/scripter/start_demo_real20_20261103_try03/`이다.

`package_ex40_real20.py`가 원본 NPZ 해시·스텝 수·지도 플래그를 다시 확인하고 ORT CPU에 넣었다. 각 스텝에서 ORT의 `h_prop_next`·`h_terr_next`를 다음 스텝 입력으로 넣었으며, 원본 PyTorch action·hidden·복원 지도를 모두 비교했다. 기준은 각 출력의 최대 절댓값 차이 `1e-4`다.

| 지형 | 복원 지도 | 지도 끔 | 정답 지도 |
|---|---:|---:|---:|
| 평지 참조 | 3.4571e-6 | 2.8611e-6 | 1.4306e-6 |
| rough L0 | 3.2783e-6 | 1.9074e-6 | 2.4438e-6 |
| 계단 L2 | 1.9669e-6 | 2.3842e-6 | 1.5199e-6 |

표는 각 조합 네 출력 가운데 가장 큰 차이다. 합성 입력 비교의 최대 차이는 `5.0068e-6`이다. 평지 시험 벡터는 `test_vectors_flat20_{reconstruction,off,gt}.json`·`.npz` 각 한 벌이고, 기본 `test_vectors_flat20.json`은 reconstruction과 바이트가 같다. 합본 `test_vectors_flat20.npz`도 세 모드를 담는다. JSON은 `start-demo-test-vectors/1`, 20스텝, `state_feedback=true`, ONNX SHA를 기록한다.

최종 JSON을 앱과 같은 방식으로 다시 읽어 펼친 배열을 실제 ONNX 모양·타입으로 복원한 뒤 ORT hidden 되먹임 20스텝을 재실행했다. 최대 차이는 reconstruction `3.4571e-6`, off `2.8611e-6`, gt `1.4306e-6`으로 모두 통과했다.

## 실행 실패와 한계

처음 두 Kit 기동은 각각 cuda:1과 cuda:0에서 Python `access violation`으로 끝났고 기록은 없었다. 기존 `record_c_layer.py:277`에 명시된 Kit 선행 `tensordict` import를 빠뜨린 것이 원인으로 유력하다. 이를 적용한 세 번째 cuda:1 기동은 9건을 모두 기록하고 rc 0이었다. 첫 완주 때 Isaac `app.close()`가 Python의 후속 영수증 쓰기 전에 프로세스를 끝내 `capture.json`이 없었다. 9개 NPZ의 필드·20스텝·유한성·지도 플래그와 `try03.log` 완료 줄을 CPU에서 다시 읽어 영수증을 복원했고, 기록기 소스는 이후 영수증을 close 전에 쓰게 고쳤다. 이 수정판의 Kit 재기동은 하지 않았다. 원본 기록기 실행 SHA는 `c485625f1d5a80c6f266125e68a5450d1d666e168815056fd884b465ec2d0a31`이며 복원 경위는 `capture.json`에 남겼다.

`HANDOFF-APP-DEVELOPER.md` §2-3은 플래그 셋을 float32로 쓰라고 하지만 실제 ONNX 입력 타입은 `tensor(bool)`이다. 묶음의 `contract.json`과 JSON 벡터는 실제 그래프 타입인 bool을 기록했다. 앱 연동 전에 해당 문구와 실행기 입력 타입을 맞춰야 한다. ORT Web·브라우저·Jetson·실기 안전 제어는 이번에 재지 않았다.

CPU 시험 `python -m unittest foothold_s2.deploy.test_package_ex40_real20 -v` 3건 통과했다. 알려진 상태 되먹임과 잘못된 7번째 action, 비유한 정답 출력 반례를 확인했다. Kit 로그는 `D:/mai-tmp/scripter/start_demo_real20_20261103_try03.log`, 첫 두 충돌 로그는 같은 폴더의 `try01.log`·`try02.log`이다.
