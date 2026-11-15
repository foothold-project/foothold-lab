> 분류: A/정책학습 · ASTRA 의뢰 17ae · S2 B step7 (17ad 결함 수정과 plumbing 보강) 좁은 1회 확인
> 작성: 오흥재 (lead 세션 · Claude 작성) · 2026-10-15 19:12
> 근거: `VERIFY-astra-17ad.md` 5절 (완성된 변경분 + 결함 수정 + CPU 증거를 한 묶음으로 1회) · 저장소 사본 `night-tools-20261013/s2_step7/` (99개 파일, 목록 `SHA256SUMS.txt` SHA256 `868b6d2780b468454838f0cfdaa1a6df68afa9a4a22205a8ef1dfa884b38ac11`) · sol 보고 `s2_step7/REPORT-s2-step7.md` · lead 재실행 `s2_step7/evidence_s2_step7/lead_rerun_1908/summary.json`
> 요지: 17ad 가 짚은 장치 결박 · USD 격리 · 기동표 · 시험 의존 · mount · plumbing 일곱 곳을 닫은 step7 이다. 이 묶음이 17ad 결함을 닫았는지, 그리고 첫 참석 plumbing(GPU 0, 4차 수집 뒤)을 lead 검증 기록 + 팀장의 단회 동의로 진행해도 되는 범위를 묻는다
> 상태: 의뢰 (GPU 둘 다 계산 0 · 승인 json 없음 · 4차 수집은 팀장 새 동의 대기)

# ASTRA 17ae

비판적이면서도 냉정하고 현실적인 전문가로서 답해 주십시오. 분량 `VERIFY-astra-17ae.md` 한 파일, 첫 줄 한 문장 판정. 코드 수정 · GPU · Isaac · 커밋 금지, em dash 금지. 17ad 에서 닫힌 것은 다시 보지 말고 아래만 봐 주세요. 확인됨 / 추정 / 미확인을 나눠 주세요. 닫힌 A3 와 전체 S2 설계는 요구하지 않습니다.

## 사실 (직접 읽을 것)

- **시험 재실행:** sol 의 `evidence_s2_step7/final2` 와 lead 의 `lead_rerun_1908` 이 같은 수다. 깨끗한 복사본에서 Python `-I`, `CUDA_VISIBLE_DEVICES=-1`, `isaac311-moects/python.exe -B`, 시험 파일 31개 전부 실행(31/31), 정상 PASS 라벨 **273**, 그 뒤 변이 **54/54 CAUGHT**(첫 FAIL = 지정 want). sol 보고서 본문은 「271」 이라고 적었지만 원시 요약은 273 이다. 본문이 틀렸고 원시 요약을 따른다. 첫 실패 기록은 `evidence_s2_step7/FIRST-FAILURES.md`. GPU · Isaac 실행 0회.
- **17ad 항목별 대응 (sol 보고 기준, 직접 대조 부탁):**
  1. P1 장치 결박: `s2_device_binding_a2.py` 에서 `cudaDeviceGetPCIBusId` 호출을 없애고 A3 에서 실제 Kit 으로 두 번 기록된 방식(`str(torch.cuda.get_device_properties(0).uuid)` 와 Kit `/physics/cudaDevice` `/renderer/activeGpu` 가 관측된 0)으로 바꿨다.
  2. P1 USD 격리: `usd_isolate_run_v3.py`(SHA `30dc2ea9…`)를 번들에 넣고 실행별 `out_root/usd` 를 `FOOTHOLD_USD_ROOT` 로 전달, Go2 가 URDF 변환 cfg(`UnitreeUrdfFileCfg`)이므로 기대 변환 수 1 로 고정, 사전 root 부재 · 변환 상태 · assigned 기록 · 생성 USD · 실제 stage 참조 경로 대조 중 하나라도 다르면 HOLD.
  3. 기동표: 1043 셸의 실제 무접미사 `isaac_slot.py`(SHA `90ae613b…`) `usd_isolate_run.py`(`366a3c13…`)로 정정, 당시 바이트는 미확인으로 표기.
  4. P2 시험 묶음: `s2_step3/` `s2_step2/` fixture 를 묶어 깨끗한 폴더에서 재현.
  5. mount: `scanner._offset` 을 런타임에 읽어(모든 env 같음 · 회전 단위 · 유한) 아니면 HOLD.
  6. plumbing: 실행기와 자식이 함께 1~2 iteration · 600 s · 단회 claim 강제, 시작/완료 iteration · vector step · transition · optimizer step · bootstrap/reset 센서 읽기 분리, checkpoint 내용에 표지 · manifest · 부모 SHA, 부모는 내용 SHA 로 고정, 최종 cfg 내용 · SHA · 부모 cfg 대비 차이, 그룹별 grad (actor · critic · map encoder · map projection · student encoder), 새 객체 strict load 로 같은 입력의 action/value 를 사전 허용치 1e-6 으로 비교, 두 번째 arm 은 첫 plumbing PASS · 가족 정리 · 사람 검토 · 팀장 직접 동의 파일 필요, 성공 표기는 `plumbing_checks=PASS` `stage0_passed=false` `performance_verified=false`, 조우 수 `unmeasured`, 작은 N 허용(2~1,024).
- **sol 이 인정한 미확인:** 실제 GPU UUID · bus · Kit/PhysX 결박, Go2 URDF 변환과 stage 참조, `_offset`, 최종 cfg, 실센서 packet 신선도, 합성 지도의 Isaac 관측 주입, PPO 자원량, VRAM · 디스크, 가족 정리. OpenUSD `GetMetadata("references")` 의 현 stage 적용은 정적 소스 대조만. 소스 문자열 변이(`h5py_after_kit` 등)는 native 적재 순서의 증거가 아니라고 보고서에 적었다.
- 같은 사본의 지도 계산 모듈 6개는 0단계 A3 번들과 바이트가 같다. 0단계는 지금 A3.2(커밋 57932407, 시험 203 PASS · 변이 28/28 외)가 4차 수집을 팀장 동의 한 줄 앞에 두고 있다.

## 질문

1. 17ad 의 P1 두 개와 P2, 기동표, mount, 변이 · 영수증 문구, plumbing 일곱 곳이 **닫혔는가**. 닫히지 않은 줄이 있으면 파일 · 줄로. 특히 (a) 장치 결박이 실기에서 막힐 지점 (b) USD 격리의 「기대 변환 수 1」 근거와 stage 참조 대조가 첫 실기에서 틀릴 가능성 (c) 합성 지도 주입 경로가 실제 Isaac 관측에 들어가는 지점의 타당성.
2. **첫 참석 plumbing 의 사전 고정값:** lead 가 제안한다. GPU 0, arm A 먼저, 입력 경로 `synthetic_known_answer`(실센서 미검증 상태에서 PPO 와 관측 경로만 보려는 것) 또는 `live_raycaster_unverified` 중 무엇이 먼저인가, N=32, iteration=1, 두 번째 arm(B) 은 첫 PASS 와 팀장의 별도 동의 뒤에만. 이 값들이 적절한가, 바꿀 것은. (rollout_steps · epochs · minibatches 는 sol 의 기본 시험값을 쓰되 실행 전 manifest 에 고정한다.)
3. 이 묶음이 닫혔다는 판정이면 **첫 plumbing 단회는 lead 검증 기록 + 팀장의 단회 직접 동의**로 진행해도 되는가(17ad 5절). 그 전에 더 필요한 CPU 증거가 있으면 지정해 달라.
4. 4차 수집(0단계 A3.2, GPU 0)과 이 plumbing 의 순서: 17ad 권고대로 4차 종료 · 가족 정리 · lease 해제 확인 뒤 같은 GPU 0 에서. 4차가 HOLD 로 끝나도 plumbing 을 이어도 되는 조건은(17ad: native crash · 장치 격리 · 미정리 프로세스 · 공유 자산 결함이 원인이면 안 됨).
5. 합격 표기 중 「가족 정리 확인」 을 감독기 영수증 말고 어떤 독립 실측(프로세스 목록 · NVML 컴퓨트 프로세스 수 · lease 해제)으로 남길지 최소 요건.

## 하지 말 것

- 무인, 자동 재시도, 후속 학습, A/B 비교 시작, 200/2000 update 허용으로 읽히는 표현. 17z 무인 보류는 유지.
