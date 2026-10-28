> 분류: C/운영 · 인프라 · 자동화 · 깃 · 웹 · 예산 · 일정
> 작성: 오흥재 (scripter 반영) · 2026-10-28
> 근거: VERIFY-W28-b8ee8eb2.md · 기존 render_queue_26d.py · 설치 Isaac Lab app_launcher.py · CPU 반례
> 요지: 기존 렌더러와 W28 claim을 같은 파일 잠금에 연결하고 GPU 등록 번호와 자식 장치 인자를 결박
> 상태: CPU 수정 시험 통과 · GPU/Kit/serve 미실행 · 기존 프로세스 전환 대기

# W28 검증 지적 두 건 수정

## V1 · 기존 렌더러 claim

기존 `render_queue_26d.py`의 호환판을 runner 원본 기준 별도 worktree `scripter-w28-renderer`에서 커밋 `32da73f9`로 만들었다. 렌더러는 영상 건 직전 W28 queue의 OS 잠금 안에서 `legacy_claims`를 등록한다. 새 queue에 이미 `running` claim이 있으면 렌더 자식을 시작하지 않고 기다린다. 반대로 렌더 자식 실행 중이면 새 queue의 `claim_one`이 거절한다. 렌더 건 완료 시 소유 token으로 해제하며, 프로세스 비정상 종료로 남은 claim은 자동 재실행 없이 검토 대기다. 새 renderer의 실제 CLI는 `--w28-queue`와 `--w28-module`을 필수로 받는다.

verifier의 답을 아는 입력과 같은 상황을 CPU에서 재생했다. 새 claim이 있는 동안 기존 렌더러의 자식 호출 0회, 상태 `waiting`, 이유 `w28_new_queue_claimed`였다. 새 claim을 끝낸 뒤 자식 호출 1회로 완료됐다. 반대 순서에서 렌더 자식 실행 중 새 queue는 `legacy_renderer_claim_requires_review`로 거절했다. 브리지 없는 실제 runner 호출은 예외로 거절했다. `test_w28_renderer_bridge.py` 3 PASS, 기존 `test_runner_26m_queue.py` 10 PASS다.

**운영 경계:** 현재 메모리에 적재된 옛 renderer는 바뀌지 않았다. 그 프로세스가 자연 종료한 사실과 새 호환판이 **같은 절대 queue 경로**로 다시 시작한 사실을 lead가 확인하기 전에는 W28 `serve`를 띄우면 안 된다. 기존 P1 평가 사슬도 아직 이 queue에 claim을 쓰지 않는다. P1 운영 전환을 완료하기 전에는 전체 GPU 작업 단일 대기열이라고 말할 수 없다.

## V2 · GPU 인자

GPU job은 `gpu_uuid`를 필수로 두고, `gpu=1`이면 각 자식 명령의 `--device cuda:1`을 정확히 하나 요구한다. `gpu=1`에 `cuda:0`을 넣은 원래 반례는 등록 시 `ValueError`다. 실행 직전 `nvidia-smi --id N --query-gpu=uuid`의 값이 등록 UUID와 다르면 자식을 시작하지 않는다. 자식 환경은 상속된 `CUDA_VISIBLE_DEVICES`를 제거하고 `CUDA_DEVICE_ORDER=PCI_BUS_ID`를 지정한다. CPU compose는 CUDA 장치 인자를 거절하고 가시성을 빈 값으로 둔다. 별도 렌더 장치 플래그는 의미가 확인되지 않아 등록을 거절한다.

설치 `C:/isaac/IsaacLab/source/isaaclab/isaaclab/app/app_launcher.py:670~705`는 `--device cuda:N`의 N을 `device_id`, `active_gpu`, `physics_gpu`로 전달한다. CPU 대역에서 UUID 불일치 때 자식 호출 0회, 정상 UUID 입력에서는 실행·검증 자식 모두 장치 환경을 받는 것을 확인했다. 실제 Isaac/Kit에서 CUDA 번호와 렌더 장치의 물리 UUID가 같은지는 GPU를 실행하지 않아 미확인이다. 운영자는 첫 실측 영수증에서 이를 확인해야 한다.

## 시험과 변경 바이트

- W28 queue와 영상 점검 CPU unittest: 13 PASS.
- renderer 상호 점유 CPU unittest: 3 PASS. 기존 renderer queue 시험: 10 PASS.
- 두 worktree의 `ruff check --select F`, `git diff --check` 통과. GPU·Kit·serve·기존 프로세스 중단 없음.
- `queue_w28.py` SHA256 `89c4b71974ace780ccd417d5158f5508e3af3dd9855ad2fd5b117f3c9053696d`.
- `test_queue_w28.py` SHA256 `cebcbcc9732063be6b0be775b8fd4098eccadf4bdffffdd3a5f3fbd0dfc8b038`.
- `README-W28.md` SHA256 `c032b9ebfdb7fc3261e85c606b65a3828c37bf11cdd4e45ffdbdce845603a293`.
- renderer `render_queue_26d.py` SHA256 `4c703900e1a8828167c2e1d7f4bae4de5e3c40db0b7516ce2d98c0441f12718c`.
- renderer `test_w28_renderer_bridge.py` SHA256 `72161a7bd03dce46cfbebb0a19438222d62b54a254ae0243ec34a71cdc3d67f3`.

lead가 두 커밋을 함께 검토하고 기존 소비자 전환을 정해야 한다. 이 문서나 CPU 시험은 GPU 기동 승인 증거가 아니다.
