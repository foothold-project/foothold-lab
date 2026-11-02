> 분류: 운영
> 작성: scripter · 2026-11-02
> 근거: C층 첫 촬영 child.log EOFError · foothold_s2/eval/seq_video.sh:15-16 · c_layer_queue.py
> 요지: C층 기록기와 합성기 자식 환경을 표준 Kit 블록으로 고정했다.
> 상태: CPU 확인됨 · Kit 재확인 대기

# C76 자식 환경 고침

첫 촬영에서 Isaac EULA 입력 대기가 EOFError로 끝났다. 대기열은 예행에 PYTHONUTF8만 전달했고 본 촬영과 합성기에는 별도 환경을 전달하지 않았다.

`recorder_child_env`가 기록기 Python 실행 파일의 환경 루트를 CONDA_PREFIX로 잡고, `seq_video.sh`와 같은 Library 경로를 PATH 앞에 둔다. OMNI_KIT_ACCEPT_EULA=YES, CUDA_DEVICE_ORDER=PCI_BUS_ID, PYTHONUNBUFFERED=1, KMP_DUPLICATE_LIB_OK=TRUE, PYTHONUTF8=1을 예행·본 촬영·합성기 세 호출에 똑같이 전달한다. 자식에서는 CUDA_VISIBLE_DEVICES를 제거해 계획의 cuda:1이 PCI 순서 기준으로 해석되도록 한다. 부모 환경은 바꾸지 않는다.

isaac311 CPU 시험: `python -m pytest foothold_s2/tests/test_c_layer_queue.py -q` 결과 22 passed. 실제 Python 자식의 환경 값과 세 subprocess 호출의 환경을 각각 확인했다. `ruff check --select F`와 pyflakes는 모두 0건이었다. Kit 촬영 성공 여부는 아직 미확인이다.

실행 중인 `scripter-w75-w76` 사본과 `C:/Users/AI-WS01/s2_lab/c_layer_m6000/plan.json`은 수정하지 않았다. 기존 계획은 대기열 경로와 SHA256을 이전 코드로 고정한다. 새 코드 채택 시 lead가 별도 계획 사본의 `queue`와 `queue_sha256`을 새 고정 사본으로 다시 묶어야 한다. 이미 기록된 첫 기술 실패는 그대로 보존한다.
