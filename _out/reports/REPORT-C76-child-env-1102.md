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

## 낮은 위험 두 건 후속

계획 검사에서 `--device cuda:0|cuda:1` 정확히 한 번과 전 칸 동일 장치를 요구한다. 기록기가 종료 코드 0을 냈더라도 child.log에 Python Traceback이 있으면 해당 시도를 기술 실패로 남기고 정본 영상은 만들지 않는다. CPU 반례는 `--device cpu`, 칸 사이 장치 혼합, rc0와 Traceback 조합이다. 후속 대기열 시험 결과는 24 passed이다.

## C4 화면 감사 후속

검사 결과에 매 프레임 흰 Go2 몸 후보의 화면 bbox와 후보 수를 남긴다. 회색·흰 지형 전체의 흰 픽셀 비율만으로 로봇 가시성을 주장하지 않으며, 몸 후보가 없는 프레임은 실패한다. 이는 RGB의 형태 기반 화면 후보이고 semantic segmentation 증명은 아니다. 첫 Kit 촬영의 실제 화면을 사람이 확인해야 한다.

밝기만 1단계 번갈아 변하는 정지 영상은 그레이 영상 차분의 공간 표준편차와 25프레임 연속 조건으로 거절한다. styled 1920×1080의 아래 360행은 장면과 분리해 전 프레임 밝기를 검사한다. verifier의 로봇 없는 흰 지형 · 밝기 흔들림 · 검은 아래 띠 반례를 CPU 시험에 넣었다. 기존 A층 원본 375프레임 한 편(`C:/Users/AI-WS01/s2_lab/ex40_main_20261031_041313/video_a/parent_m1500/EX34-SB10-pyramid_stairs_L1_env23-m1500-fwd_back_probe_prop_only-1x/review.mp4`, SHA256 580bfa2e277b65a875c6e39203aa0d11818ef33181e090570618c50b67f1afe5)은 후보 375/375 · 저변동 연속 0 · 감사 PASS였다. 이는 C층 첫 Kit 편의 품질 결과가 아니다.

관련 C층 CPU 시험 35 passed, ruff F · pyflakes 0건. 첫 실제 Kit 편의 raw와 styled 영수증 검사는 lead가 새 고정본으로 실행한 뒤 확인한다.
