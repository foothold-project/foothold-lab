# M91 Linux 이식 전 CPU 변경 보고

> 분류: EX-42 실행 이식
> 작성: runner · 2026-11-08
> 근거: analyst Linux/Windows pins 보고서 §2 34~38행 · RULES-HUB M14/M21 · FAILURE-LOG R6
> 요지: Linux 동작은 machine profile로 분기하고 Windows 장치 배정과 경로 동작은 보존했다.
> 상태: CPU 회귀시험 통과 · Linux 호스트 실측 미확인

| 요청 | 구현 및 근거 위치 | 답을 아는 CPU 반례와 결과 | Windows 동작 | Linux 실측 |
|---|---|---|---|---|
| run.log_dir 이전 영수증 · analyst §2 34행 | [ex42_training_entry.py](../../foothold_s2/scripts/ex42_training_entry.py#L99) 는 원 manifest 및 체크포인트 SHA를 그대로 검사한다. 복사 위치가 다르면 명시적 relocation receipt가 있어야 하며, receipt는 source/target, manifest·checkpoint·plan·approval·parent SHA를 묶는다. 생성기와 검증기는 같은 파일의 238행, 271행이다. `rebase_files_for_resume`는 코드 핀 재기준용이라 run.log_dir 이전 증거로 사용하지 않았다. | [test_ex42_training_entry_cpu.py](../../foothold_s2/tests/test_ex42_training_entry_cpu.py) 실제 저장 manifest/checkpoint로 receipt 생성·검증 통과, receipt 누락·SHA/대상 변경 반례 거절. | 경로가 그대로면 기존 경로 검증 유지. | Linux에서 파일 복사와 실제 resume 미측정. |
| 기기 경로 7 필수 + 20 선택 · analyst §2 35행 | [machine_profile.py](../../foothold_s2/machine_profile.py#L22) 에 경로 목록과 POSIX/Windows 절대경로 검사를 두고, [AI-WS01-linux.yaml](../../machines/AI-WS01-linux.yaml) 은 경로를 호스트 환경변수로 받는다. 경로를 못 받거나 D:/ 경로를 쓰면 Linux profile 로드가 거절된다. | [test_machine_profile_cpu.py](../../foothold_s2/tests/test_machine_profile_cpu.py) 7+20 경로의 env 치환, 선택값 생략, 누락 필수값 및 Linux의 D:/ 필수·선택값 거절 확인. | [AI-WS01-windows.yaml](../../machines/AI-WS01-windows.yaml) 의 기존 C:/·D:/ 값 보존, Windows 경로 로드 시험 통과. | 실제 Linux 변수값·설치 경로는 제공되지 않아 미확인. |
| GPU 역할 · UUID · 화면 GPU · analyst §2 38행 | machine profile은 `training`, `p1_evaluation`, `screen` 각각의 CUDA 번호와 UUID를 요구한다. [ex42_training_entry.py](../../foothold_s2/scripts/ex42_training_entry.py#L34) 는 학습 장치를 profile과 대조해 cuda:0만 허용한다. [ex42_chain.py](../../foothold_s2/ex42_chain.py#L36) 는 Linux P1 명령의 Isaac311 Python, 실제 `eval_map_modes`, manifest의 model_N, 지도 3모드, 64 env/300 step/headless, 프로필 장치를 검증하고 profile P1 GPU에 등록한다. Windows profile은 P1 GPU1을 유지한다. | [test_ex42_chain_cpu.py](../../foothold_s2/tests/test_ex42_chain_cpu.py) Linux의 완전한 실제 형식 argv가 GPU0 queue item을 만들고, python 별칭 또는 다른 장치 명령은 거절됨. Windows profile의 P1 GPU1 회귀시험 통과. [test_machine_profile_cpu.py](../../foothold_s2/tests/test_machine_profile_cpu.py) 학습 cuda:1 거절. | Windows profile의 GPU0 학습 · GPU1 P1/화면 배정 유지. | Linux UUID는 `${GPU0_UUID}`/`${GPU1_UUID}`로만 구성. 대상 호스트의 `nvidia-smi` UUID와 화면 장치 대응은 미측정. |
| C층 P1 표식 · analyst §2 37행 | [c_layer_queue.py](../../foothold_s2/eval/c_layer_queue.py#L88) 는 hardcode된 GPU1 표식 대신 profile의 P1 GPU에 해당하는 표식 및 queue 설정을 검사하고, 녹화 장치는 profile의 화면 GPU와 대조한다. | [test_c_layer_queue.py](../../foothold_s2/tests/test_c_layer_queue.py) profile과 일치하는 Linux marker/config/화면 GPU 통과, D:/ marker 또는 장치 불일치 거절. | Windows profile은 기존 GPU1 표식을 유지한다. | 실제 Linux C층 실행과 GPU 표식 경합은 미측정. |

## 검증

- isaac311 CPU의 EX-42 관련 및 변경 영향 시험: `160 passed, 1 skipped in 33.40s`.
- 바뀐 모듈과 시험의 pyflakes: `train_start.py` 이외 파일 0건. `train_start.py`에는 기준 커밋에도 있던 5개 진단(미사용 import 3개, 중복 dict 키 2개)이 그대로 있으며, 새 진단은 없다.
- compileall 및 `git diff --check`: 통과.
- Kit/GPU 및 Linux 호스트 실행은 하지 않았다. Linux UUID, 실제 설치 경로, P1 장치 선택과 화면 GPU 대응은 미확인 상태다.
