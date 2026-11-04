# C층 cap2 비0 환경 로봇 가시성 결함
> 분류: A/평가
> 작성: 오흥재 · scripter 반영 · 2026-11-04
> 근거: cap2 실제 실패 66회 · env12 실패 진단 · 고정본 GPU1 한 칸 재촬영
> 요지: 선택한 복제 로봇의 USD 가시성을 복원해 비0 환경의 촬영과 분할 검사를 통과시켰다.
> 상태: 촬영 결함 확인됨 · 전체 C층 재개는 lead 판단 대기

## 원인

- 기존 cap2 계획 `D:\mai-tmp\c_layer_m6000_gpu1_remainder_v34\cap2\plan.json`은 `c-layer-v34-run-25f0aec6` 기록기를 고정했다. 그 기록기는 다른 로봇 루트 63개를 숨기지만 선택 로봇 루트의 원래 `invisible` 값을 되돌리지 않았다. 실행 원자료 `out\attempts\balance_beams_L0_eval_gt\03\EX40-balance_beams_L0_env12-m6000-eval_gt-1x\segmentation_failure.json`에서 env12 선택 로봇 라벨 0 · 화면 픽셀 0, RGB 그림에도 로봇이 없다.
- 기존 cap2의 `failure.json` 66개는 env7 54개 · env12 12개 모두 `recorder child exit 1`이다. 성공 영수증 4개는 모두 env0이다. 같은 계열의 이전 GPU1 env5 시험(`D:\mai-tmp\c_layer_visibility_fix_v1\smoke_gpu1_out`)에서는 선택 루트가 `invisible`에서 `inherited`로 바뀌고 선택 로봇 47,166픽셀 · 다른 로봇 0픽셀로 촬영됐다.
- 실패 로그 R6·R20·M02·M08에 따라 cap2 실행 사본과 원본 실패 폴더를 보존했다. 고정 코드와 실제 자식 실행 경로를 확인했다.

## 수정과 시험

- `cd41b19d`: C층에서 선택 로봇 루트를 `MakeVisible()`로 복원하고 나머지 루트 63개의 `invisible`을 확인해 영수증에 전후 가시성을 남긴다. `4bde9787`: GPU 대기열이 자식 기록기를 시작할 때 실제 `source_root`를 `PYTHONPATH`에 전달한다. 첫 예행 큐 98번은 이 경로가 없어 `ModuleNotFoundError: foothold_s2`로 중단됐고, 그 출력은 보존했다.
- isaac311 CPU 시험 38 PASS. 비0 env12·선택 루트 결손·다른 루트 노출 반례와 저장소 밖 작업 디렉터리에서 실제 자식 Python import를 포함한다. 수정 코드의 고정 사본은 `D:\mai-wt\foothold-lab\c76-cap2-visible-4bde9787`이며 변경 0건이다.
- 새 216칸 계획 `D:\mai-tmp\scripter\c76_cap2_visible_v2\plan.json`, SHA256 `6936f3e4598b85b2a87576d174a4e7d248b3cad5439b9da05054fd0fc33727ba`. 같은 EX-40 m6000 저장본 SHA `d5e9ec400f33d74d97e7c69d4ab2092d4980195141bb8b30e683730eecd6b6f5`를 쓴다.
- GPU1 대기열 107번의 `balance_beams_L0_eval_gt`, env12 실제 촬영은 종료 코드 0. 기록 450프레임, 원본·합성 전 프레임 검사 각각 PASS. 선택 로봇의 첫 가시성 `invisible` → `inherited`, 전체 프레임 선택 로봇 픽셀 최소 32,922 · 최대 49,059, 다른 로봇 픽셀 최대 0. `review.mp4` SHA256 `6a8179bda34ab1c6dce551ecf0ccb71d8168b9364e0414cd296c35d527904e73`, `styled.mp4` SHA256 `618a2c04856b369046d0c213e37e410e9bc05563b1c240a33f2d31226f051f1e`. 1.0초 그림 `D:\mai-tmp\scripter\c76_cap2_visible_v2\env12_frame1s.png`를 직접 열어 선택 로봇 한 대가 보이는 것을 확인했다.
- 촬영 자신의 `attempt.json.result=fail`은 `review_feet.npz.done` 4회(0.90 · 2.38 · 3.14 · 4.88초)를 센 판정이다. 네 번 모두 `termination_terms=foot_below_ground`, `time_out=false`이며 넘어짐의 물리 원인은 미확인이다. 마지막 reset 뒤 6.0 · 17.6초에 로봇이 서 있는 장면과 모순되지 않는다. 이 한 칸을 정책의 성공 영수증으로 세지 않는다.

## 다음 연결

기존 cap2 실패 66개와 새 시험 산출은 별개 폴더에 남아 있다. lead가 C층 dispatcher 재개 범위와 출력 폴더를 정한 뒤 새 고정 사본·계획 SHA를 소비해야 한다. `out` 폴더의 실패를 성공으로 소급하거나 기존 계획의 recorder SHA를 덮어쓰지 않는다.
