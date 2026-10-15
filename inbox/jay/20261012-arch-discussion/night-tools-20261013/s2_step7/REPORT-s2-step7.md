# S2 B step7 · ASTRA 17ad 결함 수정 보고

> 분류: A/정책학습 · CPU 구현 보고
> 작성: Codex Worker · 2026-10-15
> 근거: TASK-codex-worker-s2-B-fix17ad.md · VERIFY-astra-17ad.md · `s2_step7/evidence_s2_step7/` 원시 시험
> 요지: 장치 결박과 USD 격리를 고치고 배관 참석 계약을 보강한 step7 사본을 CPU에서 검증했다.
> 상태: CPU 시험 통과 · GPU·Isaac 미실행 · 실제 첫 참석과 ASTRA 재검 미확인

## 산출물과 변경

새 `codexE/s2_step7/`에 step6을 복사해 수정했다. step6, 저장소 공유 체크아웃, `_eval`, 기존 slot·guard, 부모 코드와 원자료 쓰기는 0이다. `s2_step7/S2-STEP7-USAGE.md`에 입력과 HOLD 경계를 적었다. `s2_step7/S2-STEP5-LAUNCH-PARITY.md`는 1043 셸의 실제 무접미사 `isaac_slot.py`와 `usd_isolate_run.py` argv로 정정했다. 현재 파일 SHA는 각각 `90ae613b0e7e791fa24bf82866eb0a0285eafe5cd10f0e201ba2f5af9fa19c47`, `366a3c13aac3499e711ea717441ae7e3da67871302b5c6e432b1cbc20ea0a87f`다. 당시 1043 실행 영수증은 찾지 못했으므로 당시 바이트는 미확인이다.

`s2_device_binding_a2.py`는 설치 torch 2.7.0+cu128에 없는 `cudart().cudaDeviceGetPCIBusId` 호출을 없애고 A3에서 두 번 기록된 `str(torch.cuda.get_device_properties(0).uuid)` 방식으로 결박한다. Kit `/physics/cudaDevice`와 `/renderer/activeGpu`가 모두 관측된 0이어야 한다. 누락·다른 UUID·다른 Kit 장치는 HOLD다. 설치 torch의 API 존재 여부는 CUDA 초기화 없이 직접 확인했고, 실제 GPU 매핑은 이 세션에서 재지 않았다. A3 attempt2·3의 `device_binding.json`은 같은 UUID와 Kit 0 기록을 읽어 확인했다. 그 기록의 실기 사실을 이번 step7 실행 증거로 승격하지 않았다.

`s2_train_contract.py`, `s2_train_manifest.py`, `s2_train_launch.py`는 SHA `30dc2ea930f400948474b11c648aa389ff495d2a1bd764b4b9b984b931d11efb`의 검증된 `usd_isolate_run_v3.py`를 번들에 넣고, 매 실행 `out_root/usd`를 `FOOTHOLD_USD_ROOT`로 전달한다. 설치 Go2 cfg는 `UnitreeUrdfFileCfg`, Isaac Lab `spawn_from_urdf()`는 `UrdfConverter`를 한 번 생성해 반환 USD를 stage 참조에 전달한다. 그래서 기대 변환 수를 1로 고정했다. 감독기는 사전 root 부재, 변환 상태와 assigned 기록, 생성 USD, 실제 stage 참조 경로를 대조한다. 한 항목이라도 다르면 HOLD다. 변환 수 1과 참조 검사는 CPU 정적·가짜 단계 시험까지만 확인됐고 실제 Isaac 관측은 미확인이다.

`s2_train_entry_17v.py`는 RayCaster `cfg.offset.pos`의 +20 m 광선 시작점과 별개인 `scanner._offset`을 실제 런타임에 읽어 모든 env의 이동 0, 회전 단위, 유한 값을 확인한다. 못 읽거나 다르면 HOLD다. 실제 cfg 내용·SHA와 부모 cfg 차이를 결과에 보존하고 중력, 접촉, root 고정, reset 개입을 검사한다. 관측 차원은 E1 부모와 비교한다. 조우 수는 `unmeasured`로 적는다.

배관 범위는 실행기와 자식에서 1~2 PPO iteration, 같은 checkpoint interval, 600초 이하, 단회 claim을 강제한다. 작은 N은 사전 봉인하며 batch 나눗셈을 먼저 검사한다. 시작·완료 iteration, vector step, transition, optimizer step, 초기 bootstrap·reset 센서 읽기를 분리한다. checkpoint 내용에 배관 표지·manifest SHA·E1 부모 SHA를 넣는다. 부모는 이름이 아닌 내용 SHA로 고정해 파일명을 바꾼 배관 checkpoint도 거절한다. live RayCaster는 packet 유효성 검사를 유지한다. synthetic 지도는 실제 Isaac 관측에 주입하는 경로를 만들었고 CPU FakeS2Env와 구분한다. CPU Fake 결과는 감독기의 live 증거 관문에서 HOLD다.

`s2_ppo_17v.py`와 `s2_plumbing.py`는 actor, critic, map encoder, map projection, student encoder별 clipping 전 grad norm, optimizer 포함, 실제 LR, 변경 tensor 수·최대 차이·유한 값을 남긴다. 첫 B backward에서 0 초기화된 map projection 상류 encoder grad 0은 허용하고, 두 번째에는 projection과 map encoder 연결을 확인한다. 저장한 policy와 별개의 새 객체에 디스크 state를 strict load해 동일 입력의 deterministic action/value를 사전 허용치 `1e-6`으로 비교하며 optimizer/control state도 대조한다. 환경 resume는 지원하지 않는다. W=50 이후 동결 해제를 이 짧은 시험으로 확인했다고 주장하지 않는다.

첫 arm의 `RUN_COMPLETE_UNVERIFIED`만으로 둘째를 시작하지 않는다. 첫 배관 검사 PASS, 가족 정리, 사람 검토, 두 번째 단회에 대한 팀장 직접 동의 파일과 해시를 요구한다. STOP·마감·가족 또는 잠금 정리 미확인 시 HOLD다. 최종 영수증은 Job 가족 정리 뒤 다시 쓰고 별도 SHA 파일을 남긴다. 성공 표기는 실행 상태와 별도로 `plumbing_checks=PASS`, `stage0_passed=false`, `performance_verified=false`로 제한한다.

## CPU 시험과 첫 실패

해석기 `C:/Users/AI-WS01/anaconda3/envs/isaac311-moects/python.exe -B`, `CUDA_VISIBLE_DEVICES=-1`로 시험했다. 최종 원시 요약 `s2_step7/evidence_s2_step7/final2/summary.json`: 깨끗한 임시 사본의 31개 시험 파일을 Python `-I`로 실행, 정상 단계 **271 PASS**, 이어서 변이 **54/54 CAUGHT**이고 모든 변이의 첫 FAIL은 지정 want와 같았다. 실제 E1 부모를 CPU에서 strict load한 arm A 1회와 B 2회 PPO, 저장·새 객체 load·출력 비교를 포함한다. 가짜 감독기 시험은 실제 GPU 참석 증거로 세지 않았다.

첫 실패는 `s2_step7/evidence_s2_step7/FIRST-FAILURES.md`에 순서대로 남겼다. 특히 초기 CPU Namespace의 `barrier_contract` 누락, 예전 parity 문자열, USD root 없는 fixture, 오래된 tracker 시험, 복사 시험의 step3 import, 변이 실행기의 `--out` 누락을 수정했다. 이후 CPU FakeS2Env가 live 증거 관문에서 HOLD된 것은 의도한 판정으로 유지했다. 기존 `h5py_after_kit`, `tensordict_after_kit`, `no_job_assign`는 소스 문자열 변이다. CPU에서 실제 h5py·torch·tensordict import가 성공하고 Kit가 미import임은 별도로 확인했지만, Kit 네이티브 적재 순서와 실제 Job 가족 정리는 미확인이다. CPU Job Object 시험은 소유 자식의 자연 종료만 확인했으며 프로세스를 죽이지 않았다.

## 미확인과 인계

실제 GPU UUID·bus·Kit/PhysX 결박, Go2 URDF 변환과 stage 참조, RayCaster `_offset`, 최종 cfg, 실센서 packet 신선도, 합성 지도의 Isaac 관측 주입, PPO 자원량, VRAM·디스크, Job 가족 정리는 이 세션에서 측정하지 않았다. 실기에서 하나라도 증거가 없으면 HOLD하도록 코드에 남겼다. 특히 OpenUSD `GetMetadata("references")`의 현 stage 적용은 정적 소스 대조만 했고 실기 호출 결과는 미확인이다. 실제 N=1,024 수용, 지형 조우·성능, 장기 안정성, 환경 resume도 미확인이다. 0단계 A3.2와 4차 수집은 lead 범위다. 팀장 결정값과 승인 JSON은 만들지 않았다.

lead는 동결된 `S2-STEP7-SHA256SUMS.txt`대로 완결 묶음을 복사하고 CPU 재실행 뒤 ASTRA에 17ad 변경분과 원시 증거만 좁게 보낼 수 있다. 첫 GPU 참석은 그 검토 및 팀장의 해당 단회 직접 동의 뒤 별도 판단 대상이다. #550 댓글은 초안만 만들고 게시하지 않았다.
